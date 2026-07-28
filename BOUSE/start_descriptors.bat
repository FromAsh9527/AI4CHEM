@echo off
setlocal
cd /d "%~dp0"
call "%~dp0resolve_edbo_python.bat"
if not defined PY (
  echo [ERROR] Cannot find conda env "edbo" python.
  echo 描述符与经典 EDBO 共用环境 edbo
  pause
  exit /b 1
)
echo ========================================
echo   描述符生成  ^(conda: edbo^)
echo   http://localhost:8502
echo ========================================
echo Using: %PY%
echo %PY% | findstr /I "\\envs\\edbo_plus\\" >nul
if not errorlevel 1 (
  echo [ERROR] 解析到了 edbo_plus。描述符请用 edbo 环境。
  pause
  exit /b 1
)
cd /d "%~dp0descriptors"
"%PY%" -m streamlit run app.py --server.port 8502 --browser.gatherUsageStats false
pause
