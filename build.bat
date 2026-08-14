@echo off
REM ==========================================
REM Kombajn Leśny PRO — lokalna budowa EXE
REM ==========================================
REM Wymaga: pip install pyinstaller
REM Wymaga: pip install -r requirements.txt

echo Budowanie KombajnLesnyPRO.exe...
pyinstaller --noconfirm kombajn_lesny.spec
echo.
if exist "dist\KombajnLesnyPRO.exe" (
    echo ✅ Gotowe! Plik: dist\KombajnLesnyPRO.exe
) else (
    echo ❌ Błąd budowy — sprawdź logi powyżej.
)
pause
