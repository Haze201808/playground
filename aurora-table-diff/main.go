// aurora-table-diff: Auroraの複数テーブルについて、1日1回のスナップショットを取得し
// 前回スナップショットとの差分を記録するCLIツール。
//
// 動作の流れ（テーブルごとに実施）:
//
//  1. 今回分のデータを取得する（B）
//  2. snapshots/<table>.json に前回分（A）があれば、AとBを比較しdiffを
//     diffs/<今日の日付>_<table>.json に保存する（差分の有無に関わらず保存する）
//  3. Aは archive/<Aが取得された日付>_<table>.json に移動する
//  4. Bを snapshots/<table>.json として保存する（=snapshotsには常に最新1件だけが残る）
//
// 使い方:
//
//	go run . run
//
// 設定は config.json (config.example.json をコピーして編集) に書く。
package main

import (
	"database/sql"
	"encoding/csv"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"time"

	_ "github.com/lib/pq"
)

type TableConfig struct {
	Name    string   `json:"name"`
	OrderBy string   `json:"order_by"` // 主キー相当のカラム名（差分比較のキーにも使う）
	Columns []string `json:"columns"`  // 空なら SELECT *
}

type Config struct {
	Host     string        `json:"host"`
	Port     int           `json:"port"`
	User     string        `json:"user"`
	Password string        `json:"password"`
	DBName   string        `json:"dbname"`
	SSLMode  string        `json:"sslmode"`
	Tables   []TableConfig `json:"tables"`
}

const (
	snapshotDir = "snapshots"
	archiveDir  = "archive"
	diffDir     = "diffs"
)

// SnapshotFile はsnapshots/配下・archive/配下に保存する1テーブル分のデータ形式。
// Dateは「このデータをいつ取得したか」を保持し、archiveへの移動時のファイル名に使う。
type SnapshotFile struct {
	Date string                   `json:"date"`
	Rows []map[string]interface{} `json:"rows"`
}

// DiffResult はdiffs/配下に保存する1テーブル分の差分結果。
type DiffResult struct {
	Table      string                   `json:"table"`
	BeforeDate string                   `json:"before_date"`
	AfterDate  string                   `json:"after_date"`
	Added      []map[string]interface{} `json:"added"`
	Removed    []map[string]interface{} `json:"removed"`
	Changed    []map[string]interface{} `json:"changed"` // 各要素: {order_byのカラム名: 値, "fields": {変更カラム: {before, after}}}
}

func main() {
	if len(os.Args) < 2 {
		printUsage()
		os.Exit(1)
	}

	cfg, err := loadConfig("config.json")
	if err != nil {
		fmt.Fprintf(os.Stderr, "config.jsonの読み込みに失敗しました: %v\n", err)
		os.Exit(1)
	}

	switch os.Args[1] {
	case "run":
		if err := run(cfg); err != nil {
			fmt.Fprintf(os.Stderr, "実行に失敗しました: %v\n", err)
			os.Exit(1)
		}
	case "csv":
		date := time.Now().Format("20060102")
		if len(os.Args) >= 3 {
			date = os.Args[2]
		}
		if err := runCSV(cfg, date); err != nil {
			fmt.Fprintf(os.Stderr, "CSV出力に失敗しました: %v\n", err)
			os.Exit(1)
		}
	default:
		printUsage()
		os.Exit(1)
	}
}

func printUsage() {
	fmt.Println(`aurora-table-diff

  go run . run             全テーブルについて今回分を取得し、前回分との差分を記録する
  go run . csv [YYYYMMDD]  指定日（省略時は当日）のdiff結果をCSVに変換する`)
}

func loadConfig(path string) (*Config, error) {
	b, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var cfg Config
	if err := json.Unmarshal(b, &cfg); err != nil {
		return nil, err
	}
	if len(cfg.Tables) == 0 {
		return nil, fmt.Errorf("config.jsonにtables（対象テーブルのリスト）を1つ以上指定してください")
	}
	for _, t := range cfg.Tables {
		if t.Name == "" || t.OrderBy == "" {
			return nil, fmt.Errorf("各tableにはnameとorder_by（比較キーとなるカラム名）が必要です")
		}
	}
	return &cfg, nil
}

// --- DB接続 & データ取得 ---

func connect(cfg *Config) (*sql.DB, error) {
	sslmode := cfg.SSLMode
	if sslmode == "" {
		sslmode = "require"
	}
	dsn := fmt.Sprintf("host=%s port=%d user=%s password=%s dbname=%s sslmode=%s",
		cfg.Host, cfg.Port, cfg.User, cfg.Password, cfg.DBName, sslmode)
	db, err := sql.Open("postgres", dsn)
	if err != nil {
		return nil, err
	}
	if err := db.Ping(); err != nil {
		db.Close()
		return nil, fmt.Errorf("接続確認に失敗しました（A5で繋がる設定と合っているか確認してください）: %w", err)
	}
	return db, nil
}

func buildQuery(t TableConfig) string {
	cols := "*"
	if len(t.Columns) > 0 {
		cols = ""
		for i, c := range t.Columns {
			if i > 0 {
				cols += ", "
			}
			cols += c
		}
	}
	return fmt.Sprintf("SELECT %s FROM %s ORDER BY %s", cols, t.Name, t.OrderBy)
}

func rowsToMaps(rows *sql.Rows) ([]map[string]interface{}, error) {
	columns, err := rows.Columns()
	if err != nil {
		return nil, err
	}
	var result []map[string]interface{}
	for rows.Next() {
		values := make([]interface{}, len(columns))
		ptrs := make([]interface{}, len(columns))
		for i := range values {
			ptrs[i] = &values[i]
		}
		if err := rows.Scan(ptrs...); err != nil {
			return nil, err
		}
		row := map[string]interface{}{}
		for i, col := range columns {
			v := values[i]
			if b, ok := v.([]byte); ok {
				v = string(b) // []byte(bytea等)はJSON化しやすいよう文字列化
			}
			row[col] = v
		}
		result = append(result, row)
	}
	return result, rows.Err()
}

func fetchRows(db *sql.DB, t TableConfig) ([]map[string]interface{}, error) {
	rows, err := db.Query(buildQuery(t))
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	return rowsToMaps(rows)
}

// --- パス ---

func snapshotPath(tableName string) string {
	return filepath.Join(snapshotDir, fmt.Sprintf("%s.json", tableName))
}

func archivePath(tableName, date string) string {
	return filepath.Join(archiveDir, date, fmt.Sprintf("%s.json", tableName))
}

func diffPath(tableName, date string) string {
	return filepath.Join(diffDir, date, fmt.Sprintf("%s.json", tableName))
}

func diffCSVPath(tableName, date string) string {
	return filepath.Join(diffDir, date, fmt.Sprintf("%s.csv", tableName))
}

// --- 本処理 ---

func run(cfg *Config) error {
	db, err := connect(cfg)
	if err != nil {
		return err
	}
	defer db.Close()

	for _, dir := range []string{snapshotDir, archiveDir, diffDir} {
		if err := os.MkdirAll(dir, 0o755); err != nil {
			return err
		}
	}

	today := time.Now().Format("20060102")

	for _, t := range cfg.Tables {
		if err := processTable(db, t, today); err != nil {
			fmt.Fprintf(os.Stderr, "table=%s: %v\n", t.Name, err)
		}
	}
	return nil
}

func processTable(db *sql.DB, t TableConfig, today string) error {
	newRows, err := fetchRows(db, t)
	if err != nil {
		return fmt.Errorf("データ取得に失敗しました: %w", err)
	}

	sp := snapshotPath(t.Name)
	old, hasOld, err := loadSnapshotFileIfExists(sp)
	if err != nil {
		return fmt.Errorf("既存スナップショットの読み込みに失敗しました: %w", err)
	}

	if hasOld {
		diff := buildDiff(t, old, newRows, today)
		if err := writeJSON(diffPath(t.Name, today), diff); err != nil {
			return fmt.Errorf("diffの保存に失敗しました: %w", err)
		}
		ap := archivePath(t.Name, old.Date)
		if err := os.MkdirAll(filepath.Dir(ap), 0o755); err != nil {
			return fmt.Errorf("archiveディレクトリの作成に失敗しました: %w", err)
		}
		if err := os.Rename(sp, ap); err != nil {
			return fmt.Errorf("archiveへの移動に失敗しました: %w", err)
		}
		fmt.Printf("[%s] diff保存: %s (追加%d/削除%d/変更%d) / archive移動: %s\n",
			t.Name, diffPath(t.Name, today), len(diff.Added), len(diff.Removed), len(diff.Changed), ap)
	} else {
		fmt.Printf("[%s] 初回取得のためdiffなし。今回分をsnapshotとして保存します\n", t.Name)
	}

	newSnapshot := SnapshotFile{Date: today, Rows: newRows}
	if err := writeJSON(sp, newSnapshot); err != nil {
		return fmt.Errorf("snapshotの保存に失敗しました: %w", err)
	}
	fmt.Printf("[%s] snapshot保存: %s (%d件)\n", t.Name, sp, len(newRows))

	return nil
}

func writeJSON(path string, v interface{}) error {
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	f, err := os.Create(path)
	if err != nil {
		return err
	}
	defer f.Close()
	enc := json.NewEncoder(f)
	enc.SetIndent("", "  ")
	return enc.Encode(v)
}

func loadSnapshotFileIfExists(path string) (SnapshotFile, bool, error) {
	b, err := os.ReadFile(path)
	if err != nil {
		if os.IsNotExist(err) {
			return SnapshotFile{}, false, nil
		}
		return SnapshotFile{}, false, err
	}
	var sf SnapshotFile
	if err := json.Unmarshal(b, &sf); err != nil {
		return SnapshotFile{}, false, err
	}
	return sf, true, nil
}

// --- 差分計算 ---

func keyOf(row map[string]interface{}, orderBy string) string {
	return fmt.Sprintf("%v", row[orderBy])
}

func buildDiff(t TableConfig, old SnapshotFile, newRows []map[string]interface{}, today string) DiffResult {
	orderBy := t.OrderBy

	oldMap := map[string]map[string]interface{}{}
	for _, r := range old.Rows {
		oldMap[keyOf(r, orderBy)] = r
	}
	newMap := map[string]map[string]interface{}{}
	for _, r := range newRows {
		newMap[keyOf(r, orderBy)] = r
	}

	result := DiffResult{
		Table:      t.Name,
		BeforeDate: old.Date,
		AfterDate:  today,
		Added:      []map[string]interface{}{},
		Removed:    []map[string]interface{}{},
		Changed:    []map[string]interface{}{},
	}

	var addedKeys, removedKeys, changedKeys []string
	for k := range newMap {
		if _, ok := oldMap[k]; !ok {
			addedKeys = append(addedKeys, k)
		}
	}
	for k := range oldMap {
		if _, ok := newMap[k]; !ok {
			removedKeys = append(removedKeys, k)
		}
	}
	for k, o := range oldMap {
		n, ok := newMap[k]
		if !ok {
			continue
		}
		if !rowEqual(o, n) {
			changedKeys = append(changedKeys, k)
		}
	}
	sort.Strings(addedKeys)
	sort.Strings(removedKeys)
	sort.Strings(changedKeys)

	for _, k := range addedKeys {
		result.Added = append(result.Added, newMap[k])
	}
	for _, k := range removedKeys {
		result.Removed = append(result.Removed, oldMap[k])
	}
	for _, k := range changedKeys {
		entry := map[string]interface{}{
			orderBy:  oldMap[k][orderBy],
			"fields": fieldDiff(oldMap[k], newMap[k]),
		}
		result.Changed = append(result.Changed, entry)
	}

	return result
}

func rowEqual(a, b map[string]interface{}) bool {
	ab, _ := json.Marshal(a)
	bb, _ := json.Marshal(b)
	return string(ab) == string(bb)
}

func fieldDiff(before, after map[string]interface{}) map[string]interface{} {
	keys := map[string]bool{}
	for k := range before {
		keys[k] = true
	}
	for k := range after {
		keys[k] = true
	}

	out := map[string]interface{}{}
	for k := range keys {
		bv := before[k]
		av := after[k]
		if fmt.Sprint(bv) != fmt.Sprint(av) {
			out[k] = map[string]interface{}{"before": bv, "after": av}
		}
	}
	return out
}

// --- CSV出力 ---

func runCSV(cfg *Config, date string) error {
	for _, t := range cfg.Tables {
		if err := exportDiffCSV(t, date); err != nil {
			fmt.Fprintf(os.Stderr, "table=%s: %v\n", t.Name, err)
		}
	}
	return nil
}

func exportDiffCSV(t TableConfig, date string) error {
	jsonPath := diffPath(t.Name, date)
	b, err := os.ReadFile(jsonPath)
	if err != nil {
		if os.IsNotExist(err) {
			fmt.Printf("[%s] %s が無いためスキップします\n", t.Name, jsonPath)
			return nil
		}
		return err
	}
	var diff DiffResult
	if err := json.Unmarshal(b, &diff); err != nil {
		return err
	}

	csvPath := diffCSVPath(t.Name, date)
	f, err := os.Create(csvPath)
	if err != nil {
		return err
	}
	defer f.Close()

	w := csv.NewWriter(f)
	defer w.Flush()

	if err := w.Write([]string{"type", "key", "field", "before", "after"}); err != nil {
		return err
	}

	orderBy := t.OrderBy

	for _, row := range diff.Added {
		key := fmt.Sprint(row[orderBy])
		for field, val := range row {
			if err := w.Write([]string{"added", key, field, "", fmt.Sprint(val)}); err != nil {
				return err
			}
		}
	}
	for _, row := range diff.Removed {
		key := fmt.Sprint(row[orderBy])
		for field, val := range row {
			if err := w.Write([]string{"removed", key, field, fmt.Sprint(val), ""}); err != nil {
				return err
			}
		}
	}
	for _, entry := range diff.Changed {
		key := fmt.Sprint(entry[orderBy])
		fields, _ := entry["fields"].(map[string]interface{})
		for field, v := range fields {
			pair, _ := v.(map[string]interface{})
			before := fmt.Sprint(pair["before"])
			after := fmt.Sprint(pair["after"])
			if err := w.Write([]string{"changed", key, field, before, after}); err != nil {
				return err
			}
		}
	}

	fmt.Printf("[%s] CSV出力: %s\n", t.Name, csvPath)
	return nil
}
