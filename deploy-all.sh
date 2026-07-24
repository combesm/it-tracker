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

# Detect existing domain/IP from opencve.cfg if present, otherwise fallback to PRIMARY_IP
EXISTING_DOMAIN=""
if [ -f "opencve_data/conf/opencve.cfg" ]; then
    EXISTING_DOMAIN=$(grep -E "^server_name = " opencve_data/conf/opencve.cfg | cut -d'=' -f2 | tr -d ' \r')
fi

SERVER_DOMAIN="${SERVER_DOMAIN:-${EXISTING_DOMAIN:-$PRIMARY_IP}}"
echo "-> Detected primary IP: $PRIMARY_IP"
echo "-> Using server domain/IP: $SERVER_DOMAIN"

# 4. Generate local configuration if not exists
mkdir -p opencve_data/conf opencve_data/db
if [ ! -f "opencve_data/conf/opencve.cfg" ]; then
    echo "-> Generating opencve_data/conf/opencve.cfg with random secret key..."
    SECRET_KEY=$(openssl rand -hex 24)
    cat <<EOF > opencve_data/conf/opencve.cfg
[core]
server_name = ${SERVER_DOMAIN}
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
    echo "-> opencve_data/conf/opencve.cfg already exists. Updating server_name to ${SERVER_DOMAIN}..."
    sed -i "s/^server_name = .*/server_name = ${SERVER_DOMAIN}/" opencve_data/conf/opencve.cfg
fi

# 5. Build and run OpenCVE services
echo "-> Starting OpenCVE Docker stack..."
$DOCKER_COMPOSE -f docker-compose.opencve.yml build
$DOCKER_COMPOSE -f docker-compose.opencve.yml up -d

# Check if Uptime Kuma is enabled in existing environment/config
ENABLE_UPTIME_KUMA="true"
if [ -f .env ]; then
    ENV_VAL=$(grep -E "^ENABLE_UPTIME_KUMA=" .env | cut -d'=' -f2 | tr -d '\r')
    if [ "$ENV_VAL" = "false" ]; then
        ENABLE_UPTIME_KUMA="false"
    fi
fi

if [ "$ENABLE_UPTIME_KUMA" = "true" ]; then
    echo "-> Starting Uptime Kuma Docker stack..."
    mkdir -p uptime_data
    # Ensure correct permissions for the Uptime Kuma container (UID 1000)
    sudo chown -R 1000:1000 uptime_data
    $DOCKER_COMPOSE -f docker-compose.uptime.yml up -d
else
    echo "-> Uptime Kuma is disabled. Stopping container if running..."
    $DOCKER_COMPOSE -f docker-compose.uptime.yml down 2>/dev/null || true
fi

# Check if Vigil365 is enabled in existing environment/config
ENABLE_VIGIL365="true"
if [ -f .env ]; then
    ENV_VAL=$(grep -E "^ENABLE_VIGIL365=" .env | cut -d'=' -f2 | tr -d '\r')
    if [ "$ENV_VAL" = "false" ]; then
        ENABLE_VIGIL365="false"
    fi
fi

if [ "$ENABLE_VIGIL365" = "true" ]; then
    echo "-> Setting up Vigil365..."
    if [ ! -d "vigil365" ]; then
        echo "-> Cloning Vigil365 repository..."
        git clone https://github.com/sameerk27/vigil365.git vigil365
    fi
    echo "-> Applying SQLite patch for Vigil365..."
    python3 patch_vigil.py
    mkdir -p vigil_data
    $DOCKER_COMPOSE -f docker-compose.vigil.yml up -d --build
else
    echo "-> Vigil365 is disabled. Stopping container if running..."
    $DOCKER_COMPOSE -f docker-compose.vigil.yml down 2>/dev/null || true
fi

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

# Generate IT-Tracker administrator credentials if not exists
if [ ! -f "it_tracker_creds.txt" ]; then
    echo "-> Generating dedicated IT-Tracker administrator credentials..."
    TRACKER_USER="admin"
    TRACKER_PASSWORD=$(openssl rand -hex 16)
    
    # Save credentials locally
    cat <<EOF > it_tracker_creds.txt
username: ${TRACKER_USER}
password: ${TRACKER_PASSWORD}
EOF
    chmod 600 it_tracker_creds.txt
    echo "-> IT-Tracker administrator credentials created successfully. Saved in it_tracker_creds.txt"
else
    echo "-> IT-Tracker credentials file it_tracker_creds.txt already exists. Skipping generation."
    TRACKER_USER=$(grep "username:" it_tracker_creds.txt | awk '{print $2}')
    TRACKER_PASSWORD=$(grep "password:" it_tracker_creds.txt | awk '{print $2}')
fi

# Automatically write/update .env file
echo "-> Configuring/Updating .env file with OpenCVE and IT-Tracker credentials..."
PREV_UPTIME_KUMA="true"
PREV_VIGIL365="true"
PREV_TENANT_ID="YOUR_TENANT_ID"
PREV_CLIENT_ID="YOUR_CLIENT_ID"
PREV_CLIENT_SECRET="YOUR_CLIENT_SECRET"
if [ -f .env ]; then
    ENV_VAL=$(grep -E "^ENABLE_UPTIME_KUMA=" .env | cut -d'=' -f2 | tr -d '\r')
    if [ "$ENV_VAL" = "false" ]; then
        PREV_UPTIME_KUMA="false"
    fi
    ENV_VIGIL=$(grep -E "^ENABLE_VIGIL365=" .env | cut -d'=' -f2 | tr -d '\r')
    if [ "$ENV_VIGIL" = "false" ]; then
        PREV_VIGIL365="false"
    fi
    VAL_TENANT=$(grep -E "^VIGIL365_TENANT_ID=" .env | cut -d'=' -f2- | tr -d '\r')
    [ -n "$VAL_TENANT" ] && PREV_TENANT_ID="$VAL_TENANT"
    VAL_CLIENT=$(grep -E "^VIGIL365_CLIENT_ID=" .env | cut -d'=' -f2- | tr -d '\r')
    [ -n "$VAL_CLIENT" ] && PREV_CLIENT_ID="$VAL_CLIENT"
    VAL_SECRET=$(grep -E "^VIGIL365_CLIENT_SECRET=" .env | cut -d'=' -f2- | tr -d '\r')
    [ -n "$VAL_SECRET" ] && PREV_CLIENT_SECRET="$VAL_SECRET"
fi

cat <<EOF > .env
# Informations de connexion OpenCVE pour l'IT-Tracker
OPENCVE_URL=http://opencve-webserver:8000/opencve
OPENCVE_USER=${API_USER}
OPENCVE_PASSWORD=${API_PASSWORD}
OPENCVE_HOST_HEADER=${SERVER_DOMAIN}

# Informations d'administration pour l'IT-Tracker
TRACKER_ADMIN_USER=${TRACKER_USER}
TRACKER_ADMIN_PASSWORD=${TRACKER_PASSWORD}

# Intégration Uptime Kuma
ENABLE_UPTIME_KUMA=${PREV_UPTIME_KUMA}

# Intégration Vigil365 (M365 Security Alert Dashboard)
ENABLE_VIGIL365=${PREV_VIGIL365}
VIGIL365_TENANT_ID=${VIGIL365_TENANT_ID:-$PREV_TENANT_ID}
VIGIL365_CLIENT_ID=${VIGIL365_CLIENT_ID:-$PREV_CLIENT_ID}
VIGIL365_CLIENT_SECRET=${VIGIL365_CLIENT_SECRET:-$PREV_CLIENT_SECRET}
EOF

# 9. Build and run IT-Tracker service
echo "-> Starting IT-Tracker Docker stack..."
mkdir -p data
$DOCKER_COMPOSE -f docker-compose.yml up -d --build

# 10. Start CPE/CVE data import asynchronously (runs inside the container in background)
echo "-> Triggering background CPE/CVE data import..."
docker exec -d opencve-webserver opencve import-data --confirm

echo "=========================================================="
echo "   Deployment Complete!"
echo "   - Inventory App: http://${PRIMARY_IP}/"
echo "   - OpenCVE: http://${PRIMARY_IP}/opencve/"
if [ "$ENABLE_UPTIME_KUMA" = "true" ]; then
echo "   - Uptime Kuma: http://${PRIMARY_IP}:3001/"
fi
if [ "$ENABLE_VIGIL365" = "true" ]; then
echo "   - Vigil365: http://${PRIMARY_IP}/vigil (ou http://${PRIMARY_IP}:3003/)"
fi
echo "=========================================================="
echo "   To view import logs run: docker logs -f opencve-webserver"
echo "=========================================================="
