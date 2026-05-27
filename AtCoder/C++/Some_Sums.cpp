#include <bits/stdc++.h>
using namespace std;

int main() {
    long long N, A, B;
    cin >> N >> A >> B;

    long long total = 0;
    int i = 1;

    while(i <= N){
        int sum = 0;
        int tmp = i;
        while (tmp > 0){
            sum += tmp % 10;
            tmp /= 10;
        }

        if (A <= sum && sum <= B) {
            total += i;
        }

        i++;

    } 

    cout << total << endl;

    return 0;
}


