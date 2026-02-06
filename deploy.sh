#!/bin/bash
set -e

# =============================================================================
# Cloud Run Deployment Script for CRM Microservice
# Usage: ./deploy.sh [development|production]
# =============================================================================

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get environment from argument (default: development)
ENVIRONMENT="${1:-development}"

# Validate environment
if [ "$ENVIRONMENT" != "development" ] && [ "$ENVIRONMENT" != "production" ]; then
    echo -e "${RED}Error: Invalid environment '$ENVIRONMENT'${NC}"
    echo "Usage: $0 [development|production]"
    exit 1
fi

echo -e "${BLUE}=== CRM Microservice - Cloud Run Deployment ===${NC}"
echo -e "${YELLOW}Environment: ${ENVIRONMENT}${NC}"
echo ""

# =============================================================================
# Configuration
# =============================================================================

PROJECT_ID="${GCP_PROJECT_ID:-shopify-473015}"
REGION="${GCP_REGION:-us-central1}"

# Environment-specific configuration (aligned with .github/workflows/deploy.yml)
if [ "$ENVIRONMENT" = "development" ]; then
    SERVICE_NAME="crm-microservice-dev"
    MEMORY="512Mi"
    CPU="1"
    MIN_INSTANCES="0"
    MAX_INSTANCES="10"
    LOG_LEVEL="INFO"
    DEBUG="true"
    # Secret Manager secret names for development
    DB_DSN_SECRET="DB_DSN"
    API_KEY_SECRET="API_KEY"
else  # production
    SERVICE_NAME="crm-microservice"
    MEMORY="1Gi"
    CPU="2"
    MIN_INSTANCES="1"
    MAX_INSTANCES="100"
    LOG_LEVEL="WARNING"
    DEBUG="false"
    # Secret Manager secret names for production
    DB_DSN_SECRET="DB_DSN_PROD"
    API_KEY_SECRET="API_KEY_PROD"
fi

# Cloud SQL Instance Connection Name (required for secure Cloud SQL Proxy connection)
# Format: project:region:instance
INSTANCE_CONNECTION_NAME="${INSTANCE_CONNECTION_NAME:-${PROJECT_ID}:${REGION}:chekoutai-db}"

# Use consistent image name (same as CI/CD pipeline)
IMAGE_NAME="gcr.io/${PROJECT_ID}/crm-microservice"

# =============================================================================
# Production Confirmation
# =============================================================================

if [ "$ENVIRONMENT" = "production" ]; then
    echo -e "${RED}WARNING: You are about to deploy to PRODUCTION!${NC}"
    echo ""
    read -p "Type 'yes' to confirm production deployment: " -r
    echo
    if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
        echo -e "${YELLOW}Deployment cancelled.${NC}"
        exit 0
    fi
fi

# =============================================================================
# Pre-deployment Checks
# =============================================================================

# Check if .env file exists
if [ -f ".env" ]; then
    echo -e "${YELLOW}Loading environment variables from .env file...${NC}"
    set -a
    source <(grep -v '^#' .env | grep -v '^$' | sed 's/\r$//')
    set +a
else
    echo -e "${YELLOW}Warning: .env file not found. Using environment variables.${NC}"
fi

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo -e "${RED}Error: gcloud CLI is not installed.${NC}"
    echo "Visit: https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Check authentication
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" &> /dev/null; then
    echo -e "${YELLOW}Not authenticated. Running gcloud auth login...${NC}"
    gcloud auth login
fi

# =============================================================================
# Deployment Summary
# =============================================================================

echo ""
echo -e "${BLUE}Deployment Configuration:${NC}"
echo "   Environment:    $ENVIRONMENT"
echo "   Service Name:   $SERVICE_NAME"
echo "   Project:        $PROJECT_ID"
echo "   Region:         $REGION"
echo "   Resources:      ${MEMORY} RAM, ${CPU} CPU"
echo "   Scaling:        ${MIN_INSTANCES}-${MAX_INSTANCES} instances"
echo "   Cloud SQL:      ${INSTANCE_CONNECTION_NAME}"
echo "   Log Level:      $LOG_LEVEL"
echo ""

# =============================================================================
# Note: Secrets are stored in Google Secret Manager (same as CI/CD pipeline)
# Required secrets: DB_DSN, DB_DSN_PROD, CRM_ENCRYPTION_KEY, API_KEY, API_KEY_PROD
# =============================================================================

# =============================================================================
# Build and Deploy
# =============================================================================

# Set project
echo -e "${YELLOW}Setting project to: ${PROJECT_ID}${NC}"
gcloud config set project ${PROJECT_ID}

# Enable required APIs
echo -e "${YELLOW}Enabling required APIs...${NC}"
gcloud services enable cloudbuild.googleapis.com run.googleapis.com containerregistry.googleapis.com secretmanager.googleapis.com

# Build and push Docker image
echo -e "${YELLOW}Building and pushing Docker image...${NC}"
gcloud builds submit --tag ${IMAGE_NAME}:latest .

# Deploy to Cloud Run (aligned with .github/workflows/deploy.yml)
echo -e "${YELLOW}Deploying to Cloud Run...${NC}"
gcloud run deploy ${SERVICE_NAME} \
    --image ${IMAGE_NAME}:latest \
    --platform managed \
    --region ${REGION} \
    --port 8000 \
    --memory ${MEMORY} \
    --cpu ${CPU} \
    --timeout 300 \
    --concurrency 80 \
    --min-instances ${MIN_INSTANCES} \
    --max-instances ${MAX_INSTANCES} \
    --allow-unauthenticated \
    --add-cloudsql-instances=${INSTANCE_CONNECTION_NAME} \
    --set-env-vars="ENVIRONMENT=${ENVIRONMENT},DEBUG=${DEBUG},LOG_LEVEL=${LOG_LEVEL},INSTANCE_CONNECTION_NAME=${INSTANCE_CONNECTION_NAME}" \
    --set-secrets="DB_DSN=${DB_DSN_SECRET}:latest,CRM_ENCRYPTION_KEY=CRM_ENCRYPTION_KEY:latest,API_KEY=${API_KEY_SECRET}:latest"

# =============================================================================
# Post-deployment
# =============================================================================

# Get the service URL
SERVICE_URL=$(gcloud run services describe ${SERVICE_NAME} \
    --region ${REGION} \
    --format 'value(status.url)')

# Health check
echo -e "${YELLOW}Testing health endpoint...${NC}"
sleep 5
if curl -sf "${SERVICE_URL}/health" > /dev/null 2>&1; then
    echo -e "${GREEN}Health check passed!${NC}"
elif curl -sf "${SERVICE_URL}/healthz" > /dev/null 2>&1; then
    echo -e "${GREEN}Health check passed!${NC}"
else
    echo -e "${YELLOW}Warning: Health check failed - service may still be starting${NC}"
fi

# Print summary
echo ""
echo -e "${GREEN}=============================================="
echo "Deployment Complete!"
echo "=============================================="
echo "Environment:  ${ENVIRONMENT}"
echo "Service:      ${SERVICE_NAME}"
echo "URL:          ${SERVICE_URL}"
echo "Project:      ${PROJECT_ID}"
echo "Region:       ${REGION}"
echo "==============================================${NC}"
