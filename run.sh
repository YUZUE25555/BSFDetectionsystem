#!/bin/bash
cd "$(dirname "$0")/pg"

if [ ! -f "venv/bin/python" ]; then
    echo "ยังไม่ได้ติดตั้งโปรแกรม กรุณารัน ../install.sh ก่อนครับ"
    read -p "กด Enter เพื่อปิดหน้าต่างนี้..."
    exit 1
fi

source venv/bin/activate
python main.py
