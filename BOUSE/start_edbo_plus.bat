@echo off
setlocal
cd /d "%~dp0"
call "%~dp0resolve_edbo_plus_python.bat"
if not defined PY (
  echo [ERROR] Cannot find conda env "edbo_plus" python.
  echo EDBO+ 必须用环境: edbo_plus
  echo 经典 EDBO 请用 start_edbo.bat ^(环境 edbo^)
  pause
  exit /b 1
)
echo ========================================
echo   EDBO+  ^(conda: edbo_plus^)
echo   http://localhost:8503
echo   勿与经典 edbo / :8501 混用
echo ========================================
echo Using: %PY%
echo %PY% | findstr /I "\\envs\\edbo\\" >nul
if not errorlevel 1 (
  echo %PY% | findstr /I "\\envs\\edbo_plus\\" >nul
  if errorlevel 1 (
    echo [ERROR] 解析到了经典 edbo 环境。请改用 start_edbo.bat
    pause
    exit /b 1
  )
)
cd /d "%~dp0edbo_plus"
"%PY%" run_app.py
pause
