#!/bin/bash
# File: scripts/run_tests.sh
# 📜 Test Execution Script

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🧪 Running FlaskVerseHub Test Suite${NC}"

# Check if virtual environment is activated
if [ -z "$VIRTUAL_ENV" ]; then
    echo -e "${YELLOW}⚠️ Virtual environment not detected. Activating...${NC}"
    if [ -f "venv/bin/activate" ]; then
        source venv/bin/activate
    else
        echo -e "${RED}❌ Virtual environment not found. Run setup_dev.sh first${NC}"
        exit 1
    fi
fi

# Set test environment
export FLASK_ENV=testing
export DATABASE_URL=sqlite:///:memory:

# Parse command line arguments
COVERAGE=false
VERBOSE=false
SPECIFIC_TEST=""

while [[ $# -gt 0 ]]; do
    case $1 in
        -c|--coverage)
            COVERAGE=true
            shift
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -t|--test)
            SPECIFIC_TEST="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo "Options:"
            echo "  -c, --coverage    Run tests with coverage report"
            echo "  -v, --verbose     Run tests with verbose output"
            echo "  -t, --test PATH   Run specific test file or directory"
            echo "  -h, --help        Show this help message"
            exit 0
            ;;
        *)
            echo -e "${RED}❌ Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

# Install test dependencies if not already installed
echo -e "${YELLOW}📦 Checking test dependencies...${NC}"
pip install -q -r requirements/test.txt

# Run linting first
echo -e "${BLUE}🔍 Running code quality checks...${NC}"

# Check code formatting with black
if command -v black &> /dev/null; then
    echo -e "${YELLOW}  → Checking code formatting...${NC}"
    black --check --diff app tests || {
        echo -e "${RED}❌ Code formatting issues found. Run 'black app tests' to fix${NC}"
        exit 1
    }
    echo -e "${GREEN}✅ Code formatting OK${NC}"
fi

# Run flake8 for linting
if command -v flake8 &> /dev/null; then
    echo -e "${YELLOW}  → Running linting...${NC}"
    flake8 app tests --max-line-length=127 --extend-ignore=E203,W503
    echo -e "${GREEN}✅ Linting passed${NC}"
fi

# Run security checks
if command -v bandit &> /dev/null; then
    echo -e "${YELLOW}  → Running security scan...${NC}"
    bandit -r app/ -ll -f json -o bandit-report.json || {
        echo -e "${YELLOW}⚠️ Security issues found. Check bandit-report.json${NC}"
    }
    echo -e "${GREEN}✅ Security scan complete${NC}"
fi

# Prepare test command
TEST_CMD="pytest"

if [ "$VERBOSE" = true ]; then
    TEST_CMD="$TEST_CMD -v"
fi

if [ "$COVERAGE" = true ]; then
    TEST_CMD="$TEST_CMD --cov=app --cov-report=html --cov-report=term --cov-report=xml"
fi

if [ -n "$SPECIFIC_TEST" ]; then
    TEST_CMD="$TEST_CMD $SPECIFIC_TEST"
fi

# Run the tests
echo -e "${BLUE}🧪 Running tests...${NC}"
echo -e "${YELLOW}Command: $TEST_CMD${NC}"

$TEST_CMD

TEST_EXIT_CODE=$?

# Display results
echo
if [ $TEST_EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}🎉 All tests passed!${NC}"
    
    if [ "$COVERAGE" = true ]; then
        echo -e "${BLUE}📊 Coverage report generated:${NC}"
        echo "  → HTML: htmlcov/index.html"
        echo "  → XML: coverage.xml"
        
        # Open coverage report if on macOS
        if [[ "$OSTYPE" == "darwin"* ]] && command -v open &> /dev/null; then
            read -p "Open coverage report in browser? (y/n): " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                open htmlcov/index.html
            fi
        fi
    fi
else
    echo -e "${RED}❌ Some tests failed${NC}"
    exit $TEST_EXIT_CODE
fi

# Run integration tests if all unit tests pass
if [ -d "tests/integration" ] && [ $TEST_EXIT_CODE -eq 0 ]; then
    echo -e "${BLUE}🔄 Running integration tests...${NC}"
    pytest tests/integration/ -v
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ Integration tests passed${NC}"
    else
        echo -e "${RED}❌ Integration tests failed${NC}"
        exit 1
    fi
fi

# Performance tests (if they exist)
if [ -d "tests/performance" ] && [ $TEST_EXIT_CODE -eq 0 ]; then
    echo -e "${BLUE}⚡ Running performance tests...${NC}"
    pytest tests/performance/ -v
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ Performance tests passed${NC}"
    else
        echo -e "${YELLOW}⚠️ Performance tests failed (non-blocking)${NC}"
    fi
fi

echo
echo -e "${GREEN}🏆 Test suite execution complete!${NC}"

# Display test summary
if [ "$COVERAGE" = true ]; then
    echo -e "${BLUE}📈 Test Coverage Summary:${NC}"
    coverage report --show-missing | tail -n 3
fi