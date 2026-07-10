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

# 4. Generate local configuration if not exists
if [ ! -f "opencve.cfg" ]; then
    echo "-> Generating opencve.cfg with random secret key..."
    SECRET_KEY=$(openssl rand -hex 24)
    cat <<EOF > opencve.cfg
[core]
server_name = 192.168.0.110
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
    echo "-> opencve.cfg already exists."
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

# 8. Start CPE/CVE data import asynchronously (runs inside the container in background)
echo "-> Triggering background CPE/CVE data import..."
docker exec -d opencve-webserver opencve import-data --confirm

echo "=========================================================="
echo "   Deployment Complete!"
echo "   - Inventory App: http://192.168.0.110/"
echo "   - OpenCVE: http://192.168.0.110/opencve/"
echo "=========================================================="
echo "   To view import logs run: docker logs -f opencve-webserver"
echo "=========================================================="
