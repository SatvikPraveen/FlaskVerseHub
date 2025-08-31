#!/bin/bash
# File: scripts/setup_dev.sh
# 📜 Development Environment Setup Script

set -e

echo "🚀 Setting up FlaskVerseHub development environment..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 is not installed. Please install Python 3.8+${NC}"
    exit 1
fi

# Check Python version
python_version=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
required_version="3.8"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then
    echo -e "${RED}❌ Python $python_version found. Please install Python 3.8+${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Python $python_version found${NC}"

# Create virtual environment
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}📦 Creating virtual environment...${NC}"
    python3 -m venv venv
    echo -e "${GREEN}✅ Virtual environment created${NC}"
else
    echo -e "${GREEN}✅ Virtual environment already exists${NC}"
fi

# Activate virtual environment
echo -e "${YELLOW}🔄 Activating virtual environment...${NC}"
source venv/bin/activate

# Upgrade pip
echo -e "${YELLOW}⬆️ Upgrading pip...${NC}"
pip install --upgrade pip

# Install dependencies
echo -e "${YELLOW}📚 Installing dependencies...${NC}"
pip install -r requirements/dev.txt

# Copy environment file if it doesn't exist
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}⚙️ Creating .env file from template...${NC}"
    cp .env.example .env
    echo -e "${GREEN}✅ Please edit .env file with your configuration${NC}"
else
    echo -e "${GREEN}✅ .env file already exists${NC}"
fi

# Check if database exists, if not initialize it
if [ ! -f "flaskversehub.db" ]; then
    echo -e "${YELLOW}🗄️ Initializing database...${NC}"
    export FLASK_APP=manage.py
    flask db init
    flask db migrate -m "Initial migration"
    flask db upgrade
    echo -e "${GREEN}✅ Database initialized${NC}"
    
    # Ask if user wants to seed the database
    read -p "Do you want to seed the database with sample data? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        flask db seed
        echo -e "${GREEN}✅ Database seeded with sample data${NC}"
    fi
    
    # Ask if user wants to create an admin user
    read -p "Do you want to create an admin user? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        flask user create-admin
        echo -e "${GREEN}✅ Admin user created${NC}"
    fi
else
    echo -e "${GREEN}✅ Database already exists${NC}"
fi

# Create necessary directories
echo -e "${YELLOW}📁 Creating necessary directories...${NC}"
mkdir -p uploads/vault uploads/avatars logs

# Set proper permissions
chmod 755 uploads/vault uploads/avatars logs

# Check if Redis is available (optional)
if command -v redis-server &> /dev/null; then
    echo -e "${GREEN}✅ Redis is available${NC}"
else
    echo -e "${YELLOW}⚠️ Redis is not installed. Install Redis for caching and session storage${NC}"
fi

# Check if PostgreSQL is available (optional)
if command -v psql &> /dev/null; then
    echo -e "${GREEN}✅ PostgreSQL is available${NC}"
else
    echo -e "${YELLOW}⚠️ PostgreSQL is not installed. Using SQLite for development${NC}"
fi

echo -e "${GREEN}🎉 Development environment setup complete!${NC}"
echo
echo -e "${YELLOW}To start the development server:${NC}"
echo "  source venv/bin/activate"
echo "  python manage.py"
echo
echo -e "${YELLOW}Or use Flask directly:${NC}"
echo "  export FLASK_APP=manage.py"
echo "  flask run --debug"
echo
echo -e "${YELLOW}To run tests:${NC}"
echo "  pytest"
echo
echo -e "${YELLOW}To access the application:${NC}"
echo "  http://localhost:5000"
echo
echo -e "${GREEN}Happy coding! 🚀${NC}"