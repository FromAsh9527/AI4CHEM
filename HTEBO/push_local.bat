@echo off
chcp 65001 >nul
REM 在本机 AI4CHEM 仓库根目录双击运行，或：push_local.bat
cd /d "%~dp0\.."
echo === AI4CHEM 本机 push HTEBO ===
echo 当前目录: %CD%
git status -sb
echo.
echo 将添加 HTEBO/ 下所有未忽略文件...
git add HTEBO/
git status -sb
echo.
set /p MSG=提交说明（直接回车使用默认）: 
if "%MSG%"=="" set MSG=HTEBO: 同步本机开题与材料
git diff --cached --quiet
if %errorlevel%==0 (
  echo 没有新改动需要提交，尝试直接 push...
) else (
  git commit -m "%MSG%"
)
for /f "tokens=*" %%b in ('git branch --show-current') do set BR=%%b
echo.
echo 推送到 origin/%BR% ...
git push -u origin %BR%
if %errorlevel% neq 0 (
  echo.
  echo push 失败。若从未拉过云分支，请先执行：
  echo   git fetch origin
  echo   git checkout cursor/safe-transfer-s5-plan
  echo   git pull origin cursor/safe-transfer-s5-plan
  pause
  exit /b 1
)
echo.
echo 完成。GitHub 分支: %BR%
pause
