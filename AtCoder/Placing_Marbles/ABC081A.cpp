#include <bits/stdc++.h>
using namespace std;

int main() {
    string s;
    cin >> s;
    int count = 0;

    // 1文字目
    if (s[0] == '1') {
        count++;
    }

    // 2文字目
    if (s[1] == '1') {
        count++;
    }

    // 3文字目
    if (s[2] == '1') {
        count++;
    }

    cout << count << endl;

    return 0;
}


