@echo off
setlocal
cd /d "%~dp0"
call "%USERPROFILE%\miniforge3\condabin\conda.bat" activate cgcourse
if errorlevel 1 (
    echo Nao foi possivel ativar cgcourse. Consulte README.md.
    pause
    exit /b 1
)
python jogo.py
if errorlevel 1 pause
