#!/bin/bash
# File: scripts/deploy.sh
# 📜 Deployment Script

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
ENVIRONMENT="production"
SKIP_TESTS=false
SKIP_BACKUP=false
FORCE_DEPLOY=false

echo -e "${BLUE}🚀 FlaskVerseHub Deployment Script${NC}"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -e|--environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        --skip-tests)
            SKIP_TESTS=true
            shift
            ;;
        --skip-backup)
            SKIP_BACKUP=true
            shift
            ;;
        --force)
            FORCE_DEPLOY=true
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo "Options:"
            echo "  -e, --environment ENV  Deployment environment (production, staging)"
            echo "  --skip-tests          Skip running tests before deployment"
            echo "  --skip-backup         Skip database backup"
            echo "  --force              Force deployment without confirmations"
            echo "  -h, --help           Show this help message"
            exit 0
            ;;
        *)
            echo -e "${RED}❌ Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

echo -e "${YELLOW}📋 Deployment Configuration:${NC}"
echo "  Environment: $ENVIRONMENT"
echo "  Skip Tests: $SKIP_TESTS"
echo "  Skip Backup: $SKIP_BACKUP"
echo "  Force Deploy: $FORCE_DEPLOY"
echo

# Confirmation for production
if [ "$ENVIRONMENT" = "production" ] && [ "$FORCE_DEPLOY" = false ]; then
    echo -e "${YELLOW}⚠️ You are about to deploy to PRODUCTION!${NC}"
    read -p "Are you sure you want to continue? (yes/no): " -r
    echo
    if [ "$REPLY" != "yes" ]; then
        echo -e "${YELLOW}🚫 Deployment cancelled${NC}"
        exit 0
    fi
fi

# Check if we're on the correct branch for production
if [ "$ENVIRONMENT" = "production" ]; then
    CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
    if [ "$CURRENT_BRANCH" != "main" ]; then
        echo -e "${RED}❌ Production deployments must be from 'main' branch${NC}"
        echo "  Current branch: $CURRENT_BRANCH"
        exit 1
    fi
fi

# Check for uncommitted changes
if [ -n "$(git status --porcelain)" ]; then
    echo -e "${RED}❌ You have uncommitted changes. Please commit or stash them${NC}"
    exit 1
fi

# Pull latest changes
echo -e "${YELLOW}📥 Pulling latest changes...${NC}"
git pull origin $(git rev-parse --abbrev-ref HEAD)

# Run tests unless skipped
if [ "$SKIP_TESTS" = false ]; then
    echo -e "${BLUE}🧪 Running tests before deployment...${NC}"
    ./scripts/run_tests.sh
    
    if [ $? -ne 0 ]; then
        echo -e "${RED}❌ Tests failed. Deployment aborted${NC}"
        exit 1
    fi
    echo -e "${GREEN}✅ All tests passed${NC}"
fi

# Load environment-specific configuration
ENV_FILE=".env.$ENVIRONMENT"
if [ -f "$ENV_FILE" ]; then
    echo -e "${YELLOW}⚙️ Loading environment configuration: $ENV_FILE${NC}"
    set -a  # automatically export all variables
    source "$ENV_FILE"
    set +a
else
    echo -e "${YELLOW}⚠️ Environment file $ENV_FILE not found, using defaults${NC}"
fi

# Database backup (production only)
if [ "$ENVIRONMENT" = "production" ] && [ "$SKIP_BACKUP" = false ]; then
    echo -e "${BLUE}💾 Creating database backup...${NC}"
    BACKUP_FILE="backup_$(date +%Y%m%d_%H%M%S).sql"
    
    if [ -n "$DATABASE_URL" ] && [[ $DATABASE_URL == postgresql* ]]; then
        pg_dump $DATABASE_URL > "backups/$BACKUP_FILE"
        echo -e "${GREEN}✅ Database backup created: backups/$BACKUP_FILE${NC}"
    else
        echo -e "${YELLOW}⚠️ Skipping database backup (SQLite or no DATABASE_URL)${NC}"
    fi
fi

# Build Docker image
echo -e "${BLUE}🐳 Building Docker image...${NC}"
IMAGE_TAG="flaskversehub:$(git rev-parse --short HEAD)"
docker build -f docker/Dockerfile -t $IMAGE_TAG .

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Docker build failed${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Docker image built: $IMAGE_TAG${NC}"

# Deploy based on environment
case $ENVIRONMENT in
    "production")
        deploy_production
        ;;
    "staging")
        deploy_staging
        ;;
    *)
        echo -e "${RED}❌ Unknown environment: $ENVIRONMENT${NC}"
        exit 1
        ;;
esac

deploy_production() {
    echo -e "${BLUE}🏭 Deploying to production...${NC}"
    
    # Stop existing containers
    echo -e "${YELLOW}⏹️ Stopping existing application...${NC}"
    docker-compose -f docker/docker-compose.yml down --remove-orphans
    
    # Run database migrations
    echo -e "${YELLOW}🗄️ Running database migrations...${NC}"
    docker run --rm \
        --network flaskverse_default \
        -e DATABASE_URL=$DATABASE_URL \
        $IMAGE_TAG flask db upgrade
    
    # Start new containers
    echo -e "${YELLOW}🚀 Starting new application...${NC}"
    docker-compose -f docker/docker-compose.yml up -d
    
    # Health check
    echo -e "${YELLOW}🏥 Performing health check...${NC}"
    sleep 30
    
    for i in {1..5}; do
        if curl -f http://localhost:8000/health > /dev/null 2>&1; then
            echo -e "${GREEN}✅ Health check passed${NC}"
            break
        fi
        
        if [ $i -eq 5 ]; then
            echo -e "${RED}❌ Health check failed after 5 attempts${NC}"
            echo -e "${YELLOW}🔄 Rolling back...${NC}"
            rollback_deployment
            exit 1
        fi
        
        echo -e "${YELLOW}⏳ Health check attempt $i failed, retrying...${NC}"
        sleep 10
    done
}

deploy_staging() {
    echo -e "${BLUE}🧪 Deploying to staging...${NC}"
    
    # Similar to production but with staging-specific steps
    docker-compose -f docker/docker-compose.dev.yml down --remove-orphans
    
    # Update staging environment
    docker run --rm \
        -e DATABASE_URL=$DATABASE_URL \
        $IMAGE_TAG flask db upgrade
    
    docker-compose -f docker/docker-compose.dev.yml up -d
    
    echo -e "${GREEN}✅ Staging deployment complete${NC}"
}

rollback_deployment() {
    echo -e "${YELLOW}🔄 Rolling back deployment...${NC}"
    
    # Get previous image
    PREVIOUS_IMAGE=$(docker images flaskversehub --format "table {{.Tag}}" | sed -n '2p')
    
    if [ -n "$PREVIOUS_IMAGE" ]; then
        echo -e "${YELLOW}📦 Rolling back to: flaskversehub:$PREVIOUS_IMAGE${NC}"
        
        # Update docker-compose with previous image
        sed -i.bak "s|image: flaskversehub:.*|image: flaskversehub:$PREVIOUS_IMAGE|g" docker/docker-compose.yml
        
        # Restart with previous image
        docker-compose -f docker/docker-compose.yml up -d
        
        echo -e "${GREEN}✅ Rollback complete${NC}"
    else
        echo -e "${RED}❌ No previous image found for rollback${NC}"
    fi
}

# Post-deployment tasks
post_deployment() {
    echo -e "${BLUE}🧹 Running post-deployment tasks...${NC}"
    
    # Clear application cache
    docker exec $(docker ps -qf "name=flaskversehub_app") flask cache clear || true
    
    # Warm up cache
    echo -e "${YELLOW}🔥 Warming up cache...${NC}"
    curl -s http://localhost:8000/ > /dev/null || true
    curl -s http://localhost:8000/knowledge_vault/ > /dev/null || true
    
    # Send deployment notification
    if [ -n "$SLACK_WEBHOOK" ]; then
        COMMIT_MESSAGE=$(git log -1 --pretty=format:'%s')
        COMMIT_AUTHOR=$(git log -1 --pretty=format:'%an')
        
        curl -X POST -H 'Content-type: application/json' \
            --data "{\"text\":\"🚀 FlaskVerseHub deployed to $ENVIRONMENT\\nCommit: $COMMIT_MESSAGE\\nAuthor: $COMMIT_AUTHOR\"}" \
            $SLACK_WEBHOOK > /dev/null 2>&1 || true
    fi
}

# Run deployment
if [ "$ENVIRONMENT" = "production" ]; then
    deploy_production
elif [ "$ENVIRONMENT" = "staging" ]; then
    deploy_staging
fi

# Run post-deployment tasks
post_deployment

echo
echo -e "${GREEN}🎉 Deployment to $ENVIRONMENT completed successfully!${NC}"
echo
echo -e "${BLUE}📊 Deployment Summary:${NC}"
echo "  Environment: $ENVIRONMENT"
echo "  Image: $IMAGE_TAG"
echo "  Commit: $(git rev-parse --short HEAD)"
echo "  Time: $(date)"
echo
echo -e "${YELLOW}🔗 Application URLs:${NC}"
if [ "$ENVIRONMENT" = "production" ]; then
    echo "  Application: https://flaskversehub.com"
    echo "  API: https://flaskversehub.com/api/v1"
    echo "  Dashboard: https://flaskversehub.com/dashboard"
else
    echo "  Application: http://staging.flaskversehub.com"
    echo "  API: http://staging.flaskversehub.com/api/v1"
fi

echo -e "${GREEN}✨ Happy deploying!${NC}"