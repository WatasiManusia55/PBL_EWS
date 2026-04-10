#!/bin/bash

echo "=== MASUK KE PROJECT ==="
cd ~/Backend || exit

# Cek apakah folder ini sudah menjadi repository git
if [ ! -d ".git" ]; then
    echo "--- Inisialisasi Git Baru ---"
    git init
fi

echo "=== SET REMOTE (RESET BIAR AMAN) ==="
# Hapus remote lama jika ada, lalu tambah yang baru
git remote remove origin 2>/dev/null
git remote add origin git@github.com:WatasiManusia55/PBL_EWS.git

echo "=== ADD SEMUA FILE ==="
git add .

echo "=== COMMIT DATA ==="
# Cek apakah sudah pernah ada commit atau belum
if git rev-parse --verify HEAD >/dev/null 2>&1; then
    # Jika sudah ada, kita amend (ubah) commit terakhir
    echo "--- Mengupdate commit terakhir ---"
    git commit --amend -m "Update PBL_EWS - $(date +'%Y-%m-%d %H:%M:%S')" --date="$(date)"
else
    # Jika belum ada, buat commit pertama
    echo "--- Membuat commit pertama ---"
    git commit -m "Initial commit - $(date +'%Y-%m-%d %H:%M:%S')"
fi

echo "=== SET BRANCH MAIN ==="
git branch -M main

echo "=== PUSH KE GITHUB ==="
# Gunakan --force hanya jika kamu yakin ingin menimpa data di GitHub dengan data di Pi
git push -u origin main --force

echo "=== DONE PUSH KE GITHUB 🚀 ==="