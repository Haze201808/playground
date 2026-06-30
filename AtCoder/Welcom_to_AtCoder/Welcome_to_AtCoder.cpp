#include <iostream>
#include <string>

using namespace std;

int main() {
  //ios::sync_with_stdio(false);
  // cin.tie(NULL);

  int a,b,c;
  string s;

  cin >> a;
  cin >> b >> c;
  cin >> s;

  cout << a + b + c << " " << s << "\n";

  return 0;
}


/* #include<stdio.h>
int main()
{
    int a,b,c;
    char s[101];

    scanf("%d", &a);
    // スペース区切りの整数の入寮区
    scanf("%d %d", &b,&c);
    //文字列の入力
    scanf("%s",s);
    //出力
    printf("%d %s\n", a+b+c,s);
    return 0;


}
*/
