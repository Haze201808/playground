Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "wsl.exe -d Ubuntu-22.04 -- zsh -l /home/okuhira/ghq/github.com/odx-sandbox/e-okuhira-sandbox/nomal-secmaster/aws-sso-login.sh", 0, False

