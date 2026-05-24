#!/bin/bash

set -e

clear

echo "=================================================="
echo "🚀 SAFE GITHUB PUSH START"
echo "=================================================="

# ==================================================
# MASUK PROJECT
# ==================================================
PROJECT_DIR="$HOME/Downloads/PBL_EWS_NEW/PBL_EWS"
REPO_URL="git@github.com:WatasiManusia55/PBL_EWS.git"

echo "📁 Masuk project..."

cd "$PROJECT_DIR" || {
    echo "❌ Folder project tidak ditemukan"
    exit 1
}

# ==================================================
# CEK REPOSITORY GIT
# ==================================================
echo "🔍 Checking git repository..."

if [ -d .git ]; then
    if ! git fsck >/dev/null 2>&1; then
        echo "⚠️ Repository git corrupt!"
        echo "🧹 Rebuild repository..."

        rm -rf .git

        git init
        git branch -M main
    fi
else
    echo "🆕 Init repository baru..."

    git init
    git branch -M main
fi

# ==================================================
# BUAT .gitignore
# ==================================================
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

# CSV Export
sensor_data.csv
flood_prediction_log.csv

# OS
.DS_Store
Thumbs.db
EOF

# ==================================================
# REMOVE SECRET TRACKING
# ==================================================
echo "🔒 Membersihkan file rahasia..."

git rm --cached serviceAccountKey.json 2>/dev/null || true
git rm --cached .env 2>/dev/null || true
git rm --cached mediamtx 2>/dev/null || true

# ==================================================
# GIT CONFIG
# ==================================================
echo "👤 Checking git identity..."

git config user.name >/dev/null 2>&1 || \
git config --global user.name "WatasiManusia55"

git config user.email >/dev/null 2>&1 || \
git config --global user.email "kosarino1655@gmail.com"

# ==================================================
# FIX BRANCH MAIN
# ==================================================
git checkout -B main

# ==================================================
# ADD FILE
# ==================================================
echo "📦 Menambahkan file aman..."

git add .

# ==================================================
# COMMIT
# ==================================================
echo "📝 Commit..."

if git diff --cached --quiet; then
    echo "⚠️ Tidak ada perubahan"
else
    git commit -m "Update PBL_EWS - $(date '+%Y-%m-%d %H:%M:%S')"
fi

# ==================================================
# REMOTE
# ==================================================
echo "🌍 Set remote..."

git remote remove origin 2>/dev/null || true
git remote add origin "$REPO_URL"

# ==================================================
# PUSH
# ==================================================
echo "🚀 Push ke GitHub..."

git push -u origin main --force

echo "=================================================="
echo "✅ DONE PUSH GITHUB"
echo "=================================================="