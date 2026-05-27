#include <bits/stdc++.h>
using namespace std;

int main() {
    int a[100];
    int N;
    cin >> N;
    
    for (int i = 0; i < N; i++) {
        cin >> a[i];
    }
    
    sort(a, a + N, greater<int>());

    int alice = 0,bob =0;

    for (int i = 0; i < N; i++) {
        if (i % 2 ==0) {
            alice = alice + a[i];
        } else {
            bob = bob + a[i];
        }
    }

    int diff;
    diff = alice - bob;

    cout << diff << endl;

    return 0;

}
