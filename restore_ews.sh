#!/bin/bash

clear

echo "=================================================="
echo "🚀 EWS AUTO RESTORE SYSTEM"
echo "=================================================="

PROJECT_DIR="/home/pi/Downloads/PBL_EWS_NEW/PBL_EWS"

# ==================================================
# UPDATE SYSTEM
# ==================================================
echo "📦 Update package..."
sudo apt update -y

# ==================================================
# INSTALL DEPENDENCY SYSTEM
# ==================================================
echo "🛠 Install system dependency..."

sudo apt install -y \
python3-pip \
python3-venv \
git \
postgresql \
postgresql-contrib \
libpq-dev \
build-essential

# ==================================================
# CLONE / UPDATE GITHUB
# ==================================================
if [ ! -d "$PROJECT_DIR" ]; then

    echo "📥 Clone repository..."

    mkdir -p /home/pi/Downloads/PBL_EWS_NEW

    git clone git@github.com:WatasiManusia55/PBL_EWS.git "$PROJECT_DIR"

else

    echo "🔄 Pull latest repository..."

    cd "$PROJECT_DIR" || exit

    git pull origin main

fi

# ==================================================
# MASUK PROJECT
# ==================================================
cd "$PROJECT_DIR" || exit

# ==================================================
# VENV
# ==================================================
echo "🐍 Setup Python venv..."

rm -rf venv

python3 -m venv venv

source venv/bin/activate

python -m pip install --upgrade pip

# ==================================================
# INSTALL PYTHON PACKAGE
# ==================================================
echo "📚 Install Python dependency..."

pip install -r requirements.txt

# ==================================================
# POSTGRESQL START
# ==================================================
echo "🛢 Start PostgreSQL..."

sudo systemctl enable postgresql
sudo systemctl start postgresql

# ==================================================
# CREATE DATABASE
# ==================================================
echo "🛢 Setup database..."

sudo -u postgres psql <<EOF

CREATE USER pi WITH PASSWORD 'ews';

ALTER USER pi CREATEDB;

CREATE DATABASE ews_banjir OWNER pi;

GRANT ALL PRIVILEGES ON DATABASE ews_banjir TO pi;

EOF

# ==================================================
# RUN APP
# ==================================================
echo "🚀 Starting app.py..."

python app.py
