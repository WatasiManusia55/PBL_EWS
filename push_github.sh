#!/bin/bash

set -e

echo "=================================================="
echo "🚀 SAFE GIT PUSH (PBL_EWS)"
echo "=================================================="

PROJECT_DIR="$HOME/Documents/ews/PBL_EWS"

# ==================================================
# MASUK FOLDER
# ==================================================
echo "📁 Masuk project..."

cd "$PROJECT_DIR" || {
    echo "❌ Folder PBL_EWS tidak ditemukan"
    exit 1
}

# ==================================================
# CEK GIT
# ==================================================
if [ ! -d ".git" ]; then
    echo "🆕 Bukan repo git. Init repository..."
    git init
    git branch -M main
fi

# ==================================================
# SET USER (AMAN)
# ==================================================
git config user.name "WatasiManusia55"
git config user.email "kosarino1655@gmail.com"

# ==================================================
# ADD SEMUA FILE
# ==================================================
echo "📦 Menambahkan semua perubahan..."
git add -A

# ==================================================
# CEK APA ADA PERUBAHAN
# ==================================================
if git diff --cached --quiet; then
    echo "⚠️ Tidak ada perubahan untuk di-commit"
    echo "=================================================="
    echo "❌ EXIT (tidak ada push)"
    exit 0
fi

# ==================================================
# COMMIT
# ==================================================
echo "📝 Commit perubahan..."
git commit -m "update PBL_EWS $(date '+%Y-%m-%d %H:%M:%S')"

# ==================================================
# CEK REMOTE
# ==================================================
if ! git remote get-url origin >/dev/null 2>&1; then
    echo "🌍 Set remote GitHub..."
    git remote add origin git@github.com:WatasiManusia55/PBL_EWS.git
fi

# ==================================================
# PUSH (AMAN TANPA FORCE)
# ==================================================
echo "🚀 Push ke GitHub..."

git push -u origin main

echo "=================================================="
echo "✅ PUSH BERHASIL"
echo "=================================================="