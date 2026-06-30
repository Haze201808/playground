#include <iostream>
#include <algorithm>

using namespace std;

int main() {
    // 入力を受け取る変数
    long long A, B, C, X, Y;
    cin >> A >> B >> C >> X >> Y;

    // 答えとなる最小金額（非常に大きな値で初期化）
    long long min_price = 2e18; // 十分に大きな値

    // ABピザを何枚買うか（i枚）で全探索
    // 必要なAとBをすべてABピザで作る場合、最大で 2 * max(X, Y) 枚必要になる
    for (int i = 0; i <= 2 * max(X, Y); i += 2) {
        // ABピザをi枚買ったときに得られるAピザとBピザの枚数
        long long current_A = i / 2;
        long long current_B = i / 2;

        // 足りない分のAピザを単品で買う
        long long need_A = max(0LL, X - current_A);
        // 足りない分のBピザを単品で買う
        long long need_B = max(0LL, Y - current_B);

        // 合計金額を計算
        long long price = (long long)i * C + need_A * A + need_B * B;

        // 最小値を更新
        min_price = min(min_price, price);
    }

    cout << min_price << endl;

    return 0;
}