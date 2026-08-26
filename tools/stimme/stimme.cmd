@echo off
rem Ruft das Werkzeug mit seiner eigenen Umgebung auf, egal von wo.
"%~dp0.venv\Scripts\python.exe" "%~dp0stimme.py" %*
