#!/bin/bash

clear
echo "=================================================="
echo "🚀 SAFE GITHUB PUSH START"
echo "=================================================="

cd ~/Documents/Backend/PBL_EWS || exit

echo "📁 Masuk project..."

# =========================
# BUAT .gitignore
# =========================
echo "🛡 Membuat .gitignore"

cat > .gitignore <<EOF
# Python
venv/
__pycache__/
*.pyc

# Laravel
/vendor/
/node_modules/
/storage/logs/*
.env

# Secret
serviceAccountKey.json
*.pem
*.key

# Binary besar
mediamtx
*.db
*.sqlite
*.log
*.zip
*.tar.gz

# OS
.DS_Store
Thumbs.db
EOF

# =========================
# REMOVE SECRET DARI TRACKING
# =========================
echo "🔒 Membersihkan file rahasia..."

git rm --cached serviceAccountKey.json 2>/dev/null
git rm --cached .env 2>/dev/null
git rm --cached mediamtx 2>/dev/null

# =========================
# INIT GIT KALAU BELUM ADA
# =========================
if [ ! -d .git ]; then
    git init
fi

# =========================
# FIX BRANCH MAIN
# =========================
git checkout -B main

# =========================
# ADD FILE
# =========================
echo "📦 Menambahkan file aman..."
git add .

# =========================
# COMMIT
# =========================
echo "📝 Commit..."
git commit -m "Update PBL_EWS - $(date '+%Y-%m-%d %H:%M:%S')" || echo "Tidak ada perubahan"

# =========================
# REMOTE
# =========================
echo "🌍 Set remote..."

git remote remove origin 2>/dev/null
git remote add origin git@github.com:WatasiManusia55/PBL_EWS.git

# =========================
# PUSH
# =========================
echo "🚀 Push ke GitHub..."
git push -u origin main --force

echo "=================================================="
echo "✅ DONE PUSH GITHUB"
echo "=================================================="