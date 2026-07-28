@echo off
setlocal
cd /d "%~dp0"
call "%~dp0resolve_edbo_python.bat"
if not defined PY (
  echo [ERROR] Cannot find conda env "edbo" python.
  echo 经典 EDBO 必须用环境: edbo
  echo EDBO+ 请用 start_edbo_plus.bat ^(环境 edbo_plus^)
  pause
  exit /b 1
)
echo ========================================
echo   经典 EDBO  ^(conda: edbo^)
echo   http://localhost:8501
echo   勿与 edbo_plus / :8503 混用
echo ========================================
echo Using: %PY%
echo %PY% | findstr /I "\\envs\\edbo_plus\\" >nul
if not errorlevel 1 (
  echo [ERROR] 解析到了 edbo_plus 环境。请改用 start_edbo_plus.bat
  pause
  exit /b 1
)
cd /d "%~dp0edbo"
"%PY%" -m streamlit run app.py --server.port 8501 --browser.gatherUsageStats false
pause
