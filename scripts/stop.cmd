@echo off
echo Arret de tous les services Precis...
rem /T = arbre de processus : netstat n'expose que le reloader uvicorn, alors que
rem c'est son worker (enfant) qui herite de la socket et continue de servir.
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000" ^| findstr "LISTENING"') do taskkill /F /T /PID %%a >NUL 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":3000" ^| findstr "LISTENING"') do taskkill /F /T /PID %%a >NUL 2>&1
echo Tous les services sont arretes.
