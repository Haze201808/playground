local wezterm = require("wezterm")

local mux = wezterm.mux
wezterm.on("gui-startup", function(cmd)
    local _, _, window = mux.spawn_window(cmd or {})
    window:gui_window():maximize()
end)

local config = wezterm.config_builder()
local act = wezterm.action

wezterm.on("update-right-status", function(window, pane)
    window:set_right_status(window:active_workspace())
end)

config.keys = {
    -- direction
    { mods = "CTRL|SHIFT", key = "h", action = act.ActivatePaneDirection("Left") },
    { mods = "CTRL|SHIFT", key = "j", action = act.ActivatePaneDirection("Down") },
    { mods = "CTRL|SHIFT", key = "k", action = act.ActivatePaneDirection("Up") },
    { mods = "CTRL|SHIFT", key = "l", action = act.ActivatePaneDirection("Right") },

    -- Switch to workspaces
    { mods = "CTRL|SHIFT", key = "y", action = act.SwitchToWorkspace({ name = "default" }) },
    { mods = "CTRL|SHIFT", key = "u", action = act.SwitchToWorkspace({ name = "monitoring", spawn = { args = { "top" } } }) },
    { mods = "CTRL|SHIFT", key = "i", action = act.SwitchToWorkspace },
    { mods = "CTRL|SHIFT", key = "b", action = act.ShowLauncherArgs({ flags = "FUZZY|WORKSPACES" }) },

    -- ★ 追加: Alt + 1〜5 でのタブ切り替え
    { mods = "ALT", key = "1", action = act.ActivateTab(0) },
    { mods = "ALT", key = "2", action = act.ActivateTab(1) },
    { mods = "ALT", key = "3", action = act.ActivateTab(2) },
    { mods = "ALT", key = "4", action = act.ActivateTab(3) },
    { mods = "ALT", key = "5", action = act.ActivateTab(4) },

    -- ★ 追加: 追記型（上書き）のログ保存機能
    {
        mods = "CTRL|SHIFT",
        key = "s",
        action = wezterm.action_callback(function(window, pane)
            local log_dir = wezterm.home_dir .. "/Documents/terminal_logs/"
            local date = wezterm.time.now():format("%Y%m%d")
            local pane_id = pane:pane_id()
            
            -- 例: 20260526_tab0_wezterm.log
            local filepath = log_dir .. date .. "_tab" .. pane_id .. "_wezterm.log"
            local text = pane:get_lines_as_text(10000)
            
            local f = io.open(filepath, "w")
            if f then
                f:write(text)
                f:close()
                window:toast_notification('WezTerm', 'ログを更新しました: ' .. filepath, nil, 4000)
            else
                window:toast_notification('WezTerm', '保存エラー: フォルダが存在するか確認してください', nil, 4000)
            end
        end),
    },
}

config.color_scheme = "Tokyo Night (Gogh)"
config.default_domain = "WSL:Ubuntu-22.04"
-- config.enable_tab_bar = false
-- config.font = wezterm.font("Hack Nerd Font Mono")
config.font_size = 10
config.window_decorations = "INTEGRATED_BUTTONS"

-- ★ 追加: ターミナルで過去に遡れる行数を増やす
config.scrollback_lines = 10000

return config