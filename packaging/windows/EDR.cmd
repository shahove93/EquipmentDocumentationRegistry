@echo off
set "edrPowerShell=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
if defined PROCESSOR_ARCHITEW6432 set "edrPowerShell=%SystemRoot%\Sysnative\WindowsPowerShell\v1.0\powershell.exe"
"%edrPowerShell%" -NoProfile -ExecutionPolicy Bypass -File "%~dp0launcher.ps1" %*
exit /b %errorlevel%
