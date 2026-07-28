@echo off
setlocal
cd /d "%~dp0"
call "%~dp0resolve_edbo_plus_python.bat"
if not defined PY (
  echo [ERROR] Cannot find conda env "edbo_plus" python.
  pause
  exit /b 1
)
echo Using: %PY%
"%PY%" -c "from edbo.plus.optimizer_botorch import EDBOplus; print('import OK')"
if errorlevel 1 (
  echo [ERROR] import failed
  pause
  exit /b 1
)
cd /d "%~dp0edbo_plus"
"%PY%" scripts\smoke_test.py
if errorlevel 1 (
  echo [ERROR] smoke test failed
  pause
  exit /b 1
)
"%PY%" scripts\ui_smoke_test.py
if errorlevel 1 (
  echo [ERROR] UI smoke test failed
  pause
  exit /b 1
)
echo.
echo EDBO+ local deploy + UI flow verified.
pause
