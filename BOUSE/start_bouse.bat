@echo off
setlocal
cd /d "%~dp0"

set "EDBO_PORT=8501"
set "DESC_PORT=8502"

echo ========================================
echo   BOUSE 一键启动 ^(经典栈^)
echo   conda 环境: edbo
echo   EDBO         http://localhost:%EDBO_PORT%
echo   Descriptors  http://localhost:%DESC_PORT%
echo ----------------------------------------
echo   EDBO+ 不在此启动
echo   请另开: start_edbo_plus.bat
echo   ^(conda: edbo_plus · :8503^)
echo ========================================
echo.

call "%~dp0resolve_edbo_python.bat"
if not defined PY (
  echo [ERROR] Cannot find conda env "edbo" python.
  echo Create/activate it first: conda activate edbo
  pause
  exit /b 1
)
echo Using [edbo]: %PY%
echo %PY% | findstr /I "\\envs\\edbo_plus\\" >nul
if not errorlevel 1 (
  echo [ERROR] 解析到了 edbo_plus。一键启动只用于经典 edbo。
  pause
  exit /b 1
)
echo.

start "BOUSE-EDBO (edbo :8501)" cmd /k "cd /d ""%~dp0edbo"" && ""%PY%"" -m streamlit run app.py --server.port %EDBO_PORT% --browser.gatherUsageStats false"
timeout /t 2 /nobreak >nul
start "BOUSE-Descriptors (edbo :8502)" cmd /k "cd /d ""%~dp0descriptors"" && ""%PY%"" -m streamlit run app.py --server.port %DESC_PORT% --browser.gatherUsageStats false"

echo.
echo Started in two windows ^(env: edbo^).
echo EDBO+: start_edbo_plus.bat ^(env: edbo_plus · :8503^)
echo.
pause
exit /b 0
