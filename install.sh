#!/bin/bash
APP_DIR="$(cd "$(dirname "$0")/pg" && pwd)" || exit 1
cd "$APP_DIR" || exit 1

echo "============================================"
echo "  กำลังติดตั้งระบบตรวจจับ BSF"
echo "============================================"
echo

if ! command -v python3 &> /dev/null; then
    echo "[ผิดพลาด] ไม่พบ Python3 บนเครื่องนี้"
    echo "กรุณาติดตั้งจาก https://www.python.org/downloads/ ก่อน"
    read -p "กด Enter เพื่อปิดหน้าต่างนี้..."
    exit 1
fi

echo "[1/3] กำลังสร้างพื้นที่ทำงาน (virtual environment)..."
python3 -m venv "$APP_DIR/venv"

echo "[2/3] กำลังติดตั้งไลบรารีที่จำเป็น..."
source "$APP_DIR/venv/bin/activate"
python -m pip install --upgrade pip > /dev/null
python -m pip install -r "$APP_DIR/requirements.txt"

echo "[3/3] เสร็จสิ้น!"
echo
echo "============================================"
echo "  ติดตั้งเสร็จแล้ว! ดับเบิลคลิก ../run.command"
echo "  (macOS) หรือรัน ../run.sh (Linux) เพื่อเปิดโปรแกรม"
echo "============================================"
read -p "กด Enter เพื่อปิดหน้าต่างนี้..."
