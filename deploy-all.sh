#!/usr/bin/env bash

# Exit immediately if a command exits with a non-zero status
set -e

echo "=========================================================="
echo "   Starting OpenCVE & Nginx Reverse Proxy Deployment"
echo "=========================================================="

# 1. Check Docker & Docker Compose installation
if ! command -v docker &> /dev/null; then
    echo "Error: Docker is not installed on this system." >&2
    exit 1
fi

if docker compose version &> /dev/null; then
    DOCKER_COMPOSE="docker compose"
elif docker-compose version &> /dev/null; then
    DOCKER_COMPOSE="docker-compose"
else
    echo "Error: Docker Compose is not installed on this system." >&2
    exit 1
fi

echo "-> Found Compose executable: $DOCKER_COMPOSE"

# 2. Install Nginx if not already installed
if ! command -v nginx &> /dev/null; then
    echo "-> Installing Nginx..."
    sudo apt-get update && sudo apt-get install -y nginx
else
    echo "-> Nginx is already installed."
fi

# 3. Clone OpenCVE Docker repository to build target if not exists
if [ ! -d "opencve-docker" ]; then
    echo "-> Cloning official OpenCVE Docker repository..."
    git clone https://github.com/opencve/opencve-docker.git opencve-docker
else
    echo "-> OpenCVE Docker folder already exists."
    # Restore original Dockerfile to ensure sed works consistently
    git -C opencve-docker checkout Dockerfile
fi

# Fix Debian Buster EOL/archived repositories issue by using python:3.8-slim-bullseye as base image
echo "-> Fixing base image EOL repositories issue in Dockerfile..."
sed -i 's/python:3.8-slim-buster/python:3.8-slim-bullseye/g' opencve-docker/Dockerfile

# Fix passlib/bcrypt compatibility crash by pinning bcrypt < 4.0.0 in Dockerfile
echo "-> Pinning bcrypt version in Dockerfile to fix passlib bug..."
sed -i '/RUN python3 -m pip install \/opencve\//i RUN python3 -m pip install "bcrypt<4.0.0"' opencve-docker/Dockerfile

# Disable registration emails to avoid HTTP 500 when SMTP is not configured
echo "-> Disabling Flask-User registration emails in Dockerfile..."
python3 patch_dockerfile.py

# Detect primary IP address or fallback to localhost
PRIMARY_IP=$(hostname -I | awk '{print $1}')
if [ -z "$PRIMARY_IP" ]; then
    PRIMARY_IP="localhost"
fi
echo "-> Detected primary IP: $PRIMARY_IP"

# 4. Generate local configuration if not exists
mkdir -p opencve_data/conf opencve_data/db
if [ ! -f "opencve_data/conf/opencve.cfg" ]; then
    echo "-> Generating opencve_data/conf/opencve.cfg with random secret key..."
    SECRET_KEY=$(openssl rand -hex 24)
    cat <<EOF > opencve_data/conf/opencve.cfg
[core]
server_name = ${PRIMARY_IP}
secret_key = ${SECRET_KEY}
database_uri = postgresql://opencve:opencvepassword@postgres-opencve:5432/opencve
celery_broker_url = redis://redis-opencve:6379/0
celery_result_backend = redis://redis-opencve:6379/1
celery_lock_url = redis://redis-opencve:6379/2
display_welcome = False
display_terms = False
include_analytics = False
cves_per_page = 20
vendors_per_page = 20
products_per_page = 20
cwes_per_page = 20
reports_per_page = 20
alerts_per_page = 20
tags_per_page = 20
activities_per_page = 20
use_reverse_proxy = True
reports_cleanup_days = 0
display_recaptcha = False
recaptcha_site_key =
recaptcha_secret_key =

[api]
ratelimit_enabled = False
ratelimit_value = 3600/hour
ratelimit_storage_url = redis://redis-opencve:6379/2

[mail]
email_adapter = smtp
email_from = no-reply@opencve.io
smtp_server = localhost
smtp_port = 465
smtp_use_tls = True
smtp_use_ssl = False
smtp_username =
smtp_password =
EOF
else
    echo "-> opencve_data/conf/opencve.cfg already exists."
fi

# 5. Build and run OpenCVE services
echo "-> Starting OpenCVE Docker stack..."
$DOCKER_COMPOSE -f docker-compose.opencve.yml build
$DOCKER_COMPOSE -f docker-compose.opencve.yml up -d

# 6. Apply Nginx Configuration
if [ -f "nginx-opencve.conf" ]; then
    echo "-> Applying Nginx proxy configuration..."
    sudo cp nginx-opencve.conf /etc/nginx/sites-available/default
    echo "-> Restarting Nginx service..."
    sudo systemctl restart nginx
else
    echo "Error: nginx-opencve.conf not found!" >&2
    exit 1
fi

# 7. Upgrade OpenCVE database schema
echo "-> Waiting for database container to be ready and upgrading db schema..."
until docker exec opencve-webserver opencve upgrade-db &> /dev/null; do
    echo "   Database not ready yet, retrying in 5 seconds..."
    sleep 5
done
echo "-> Database schema upgraded successfully."

# 8. Create API administrator account
if [ ! -f "opencve_api_creds.txt" ]; then
    echo "-> Creating dedicated OpenCVE API administrator..."
    API_USER="api_admin"
    API_PASSWORD=$(openssl rand -hex 16)
    
    # Save credentials locally
    cat <<EOF > opencve_api_creds.txt
username: ${API_USER}
password: ${API_PASSWORD}
EOF
    chmod 600 opencve_api_creds.txt
    
    # Execute interactive user creation non-interactively via stdin pipe
    printf "${API_PASSWORD}\n${API_PASSWORD}\n" | docker exec -i opencve-webserver opencve create-user ${API_USER} api@opencve.local --admin
    echo "-> API administrator created successfully. Credentials saved in opencve_api_creds.txt"
else
    echo "-> API credentials file opencve_api_creds.txt already exists. Skipping user creation."
    API_USER=$(grep "username:" opencve_api_creds.txt | awk '{print $2}')
    API_PASSWORD=$(grep "password:" opencve_api_creds.txt | awk '{print $2}')
fi

# Automatically write/update .env file
echo "-> Configuring/Updating .env file with OpenCVE credentials..."
cat <<EOF > .env
# Informations de connexion OpenCVE pour l'IT-Tracker
OPENCVE_URL=http://opencve-webserver:8000/opencve
OPENCVE_USER=${API_USER}
OPENCVE_PASSWORD=${API_PASSWORD}
OPENCVE_HOST_HEADER=${PRIMARY_IP}
EOF

# 9. Start CPE/CVE data import asynchronously (runs inside the container in background)
echo "-> Triggering background CPE/CVE data import..."
docker exec -d opencve-webserver opencve import-data --confirm

echo "=========================================================="
echo "   Deployment Complete!"
echo "   - Inventory App: http://${PRIMARY_IP}/"
echo "   - OpenCVE: http://${PRIMARY_IP}/opencve/"
echo "=========================================================="
echo "   To view import logs run: docker logs -f opencve-webserver"
echo "=========================================================="
