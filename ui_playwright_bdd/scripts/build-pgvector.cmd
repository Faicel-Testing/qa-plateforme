@echo off
setlocal
set "PGROOT=C:\Program Files\PostgreSQL\18"
call "C:\Program Files (x86)\Microsoft Visual Studio\2019\BuildTools\VC\Auxiliary\Build\vcvars64.bat"
if errorlevel 1 exit /b 1
cd /d "%~dp0..\.qa-rag\pgvector-src"
nmake /F Makefile.win
if errorlevel 1 exit /b 1
exit /b 0
