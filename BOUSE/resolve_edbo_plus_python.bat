@echo off
REM Sets PY to ...\envs\edbo_plus\python.exe for caller
set "ENV_NAME=edbo_plus"
set "PY="
for %%D in (
  "%USERPROFILE%\miniconda3\envs\%ENV_NAME%\python.exe"
  "%USERPROFILE%\anaconda3\envs\%ENV_NAME%\python.exe"
  "%USERPROFILE%\mambaforge\envs\%ENV_NAME%\python.exe"
  "%USERPROFILE%\miniforge3\envs\%ENV_NAME%\python.exe"
  "C:\ProgramData\miniconda3\envs\%ENV_NAME%\python.exe"
  "C:\ProgramData\anaconda3\envs\%ENV_NAME%\python.exe"
  "%LOCALAPPDATA%\miniconda3\envs\%ENV_NAME%\python.exe"
  "%LOCALAPPDATA%\anaconda3\envs\%ENV_NAME%\python.exe"
) do (
  if exist "%%~D" (
    set "PY=%%~D"
    goto :EOF
  )
)
where conda >nul 2>&1
if not errorlevel 1 (
  for /f "delims=" %%I in ('conda run -n %ENV_NAME% python -c "import sys; print(sys.executable)" 2^>nul') do (
    if exist "%%I" set "PY=%%I"
  )
)
