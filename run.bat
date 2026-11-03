@echo off
cd /d "%~dp0pg"

if not exist "venv\Scripts\pythonw.exe" (
    echo ยังไม่ได้ติดตั้งโปรแกรม กรุณาดับเบิลคลิก ..\install.bat ก่อนครับ
    pause
    exit /b 1
)

rem ใช้ pythonw เพื่อไม่ให้มีหน้าต่าง console ดำๆ โผล่มา (เหมือนแอปทั่วไป)
rem หากเปิดแล้วไม่มีอะไรเกิดขึ้น ให้ดูข้อผิดพลาดในไฟล์ error.log
start "" venv\Scripts\pythonw.exe main.py 2> error.log
