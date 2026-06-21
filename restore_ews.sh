#!/bin/bash

set -e

echo "=================================================="
echo "🚀 EWS AUTO RESTORE SYSTEM (STABLE VERSION)"
echo "=================================================="

PROJECT_DIR="/home/pi/Downloads/PBL_EWS_NEW/PBL_EWS"
REPO_URL="https://github.com/WatasiManusia55/PBL_EWS.git"

# ==================================================
# 1. FIX SYSTEM STATE (WAJIB)
# ==================================================
echo "🧹 Fixing broken package state..."

sudo dpkg --configure -a || true
sudo apt --fix-broken install -y || true

# ==================================================
# 2. UPDATE SYSTEM
# ==================================================
echo "📦 Updating system..."
sudo apt update -y

# ==================================================
# 3. INSTALL DEPENDENCIES
# ==================================================
echo "🛠 Installing system dependencies..."

sudo apt install -y \
python3-pip \
python3-venv \
git \
postgresql \
postgresql-contrib \
libpq-dev \
build-essential

# ==================================================
# 4. CLONE / UPDATE REPO (FIXED)
# ==================================================
echo "📥 Preparing project directory..."

mkdir -p /home/pi/Downloads/PBL_EWS_NEW

if [ ! -d "$PROJECT_DIR/.git" ]; then
    echo "📥 Cloning repository..."
    rm -rf "$PROJECT_DIR"
    git clone "$REPO_URL" "$PROJECT_DIR"
else
    echo "🔄 Updating repository..."
    cd "$PROJECT_DIR"
    git pull origin main
fi

# ==================================================
# 5. VALIDATE PROJECT DIR
# ==================================================
if [ ! -d "$PROJECT_DIR" ]; then
    echo "❌ ERROR: Project directory not found!"
    exit 1
fi

cd "$PROJECT_DIR"

# ==================================================
# 6. SETUP VIRTUAL ENV (SAFE RESET)
# ==================================================
echo "🐍 Setting up virtual environment..."

if [ -d "venv" ]; then
    rm -rf venv
fi

python3 -m venv venv
source venv/bin/activate

pip install --upgrade pip

# ==================================================
# 7. INSTALL PYTHON REQUIREMENTS
# ==================================================
echo "📚 Installing Python dependencies..."

if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
else
    echo "⚠️ requirements.txt not found!"
fi

# ==================================================
# 8. START POSTGRESQL
# ==================================================
echo "🛢 Starting PostgreSQL..."
sudo systemctl enable postgresql
sudo systemctl start postgresql

# ==================================================
# 9. CREATE DATABASE (SAFE CHECK)
# ==================================================
echo "🛢 Setting up database..."

sudo -u postgres psql <<EOF
DO \$\$
BEGIN
   IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'pi') THEN
      CREATE USER pi WITH PASSWORD 'ews';
   END IF;
END
\$\$;

ALTER USER pi CREATEDB;

DO \$\$
BEGIN
   IF NOT EXISTS (SELECT FROM pg_database WHERE datname = 'ews_banjir') THEN
      CREATE DATABASE ews_banjir OWNER pi;
   END IF;
END
\$\$;

GRANT ALL PRIVILEGES ON DATABASE ews_banjir TO pi;
EOF

# ==================================================
# 10. RUN APP
# ==================================================
echo "🚀 Starting application..."

if [ -f "app.py" ]; then
    python app.py
else
    echo "❌ app.py not found!"
    exit 1
fi