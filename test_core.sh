#!/bin/bash
# Hermes Core Functionality Test Suite
# Run this script after making changes to verify all core features work correctly

set -e  # Exit on first error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test counters
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

# Get the hermes executable path
HERMES_BIN="$(pwd)/.venv/bin/hermes"
PYTHON_BIN="$(pwd)/.venv/bin/python"

# Create temp directory for tests
TEST_DIR="/tmp/hermes-test-$(date +%s)"

# Cleanup function
cleanup() {
    if [ -d "$TEST_DIR" ]; then
        rm -rf "$TEST_DIR"
    fi
}

trap cleanup EXIT

# Test result helper
assert_success() {
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓${NC} $1"
        PASSED_TESTS=$((PASSED_TESTS + 1))
        return 0
    else
        echo -e "${RED}✗${NC} $1"
        FAILED_TESTS=$((FAILED_TESTS + 1))
        return 1
    fi
}

assert_equals() {
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    if [ "$1" = "$2" ]; then
        echo -e "${GREEN}✓${NC} $3"
        PASSED_TESTS=$((PASSED_TESTS + 1))
        return 0
    else
        echo -e "${RED}✗${NC} $3 (expected: '$2', got: '$1')"
        FAILED_TESTS=$((FAILED_TESTS + 1))
        return 1
    fi
}

assert_contains() {
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    if echo "$1" | grep -q "$2"; then
        echo -e "${GREEN}✓${NC} $3"
        PASSED_TESTS=$((PASSED_TESTS + 1))
        return 0
    else
        echo -e "${RED}✗${NC} $3 (expected to contain: '$2')"
        FAILED_TESTS=$((FAILED_TESTS + 1))
        return 1
    fi
}

assert_file_exists() {
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    if [ -f "$1" ]; then
        echo -e "${GREEN}✓${NC} $2"
        PASSED_TESTS=$((PASSED_TESTS + 1))
        return 0
    else
        echo -e "${RED}✗${NC} $2 (file not found: $1)"
        FAILED_TESTS=$((FAILED_TESTS + 1))
        return 1
    fi
}

assert_file_not_exists() {
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    if [ ! -e "$1" ]; then
        echo -e "${GREEN}✓${NC} $2"
        PASSED_TESTS=$((PASSED_TESTS + 1))
        return 0
    else
        echo -e "${RED}✗${NC} $2 (file should not exist: $1)"
        FAILED_TESTS=$((FAILED_TESTS + 1))
        return 1
    fi
}

assert_dir_not_exists() {
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    if [ ! -d "$1" ]; then
        echo -e "${GREEN}✓${NC} $2"
        PASSED_TESTS=$((PASSED_TESTS + 1))
        return 0
    else
        echo -e "${RED}✗${NC} $2 (directory should not exist: $1)"
        FAILED_TESTS=$((FAILED_TESTS + 1))
        return 1
    fi
}

assert_import_fails() {
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    local module=$1
    local message=$2
    
    # Use the test project's Python, not the dev environment
    local TEST_PYTHON=".venv/bin/python"
    
    if [ ! -f "$TEST_PYTHON" ]; then
        echo -e "${RED}✗${NC} $message (test venv python not found)"
        FAILED_TESTS=$((FAILED_TESTS + 1))
        return 1
    fi
    
    if $TEST_PYTHON -c "import $module" 2>&1 | grep -q "ModuleNotFoundError"; then
        echo -e "${GREEN}✓${NC} $message"
        PASSED_TESTS=$((PASSED_TESTS + 1))
        return 0
    else
        echo -e "${RED}✗${NC} $message (module '$module' should not be importable)"
        FAILED_TESTS=$((FAILED_TESTS + 1))
        return 1
    fi
}

# Print header
echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║         HERMES CORE FUNCTIONALITY TEST SUITE              ║${NC}"
echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo ""

# Check if hermes is installed
if [ ! -f "$HERMES_BIN" ]; then
    echo -e "${RED}Error: Hermes not found at $HERMES_BIN${NC}"
    echo "Please run: uv pip install -e ."
    exit 1
fi

echo -e "${YELLOW}Using Hermes:${NC} $HERMES_BIN"
echo -e "${YELLOW}Test directory:${NC} $TEST_DIR"
echo ""

# ============================================================================
# TEST 1: hermes init
# ============================================================================
echo -e "${BLUE}[TEST 1]${NC} hermes init"
mkdir -p "$TEST_DIR/test-init"
cd "$TEST_DIR/test-init"

$HERMES_BIN init > /dev/null 2>&1
assert_success "Command executes without errors"

assert_file_exists "pyproject.toml" "Creates pyproject.toml"
assert_file_exists "hermes.lock" "Creates hermes.lock"
assert_file_exists ".venv/bin/python" "Creates virtual environment"

# Check lockfile format
LOCKFILE_CONTENT=$(cat hermes.lock)
assert_contains "$LOCKFILE_CONTENT" "version = 1" "Lockfile has correct format"

echo ""

# ============================================================================
# TEST 2: hermes add (single package)
# ============================================================================
echo -e "${BLUE}[TEST 2]${NC} hermes add (single package)"
mkdir -p "$TEST_DIR/test-add"
cd "$TEST_DIR/test-add"
$HERMES_BIN init > /dev/null 2>&1

$HERMES_BIN add certifi > /dev/null 2>&1
assert_success "Add package executes successfully"

# Check pyproject.toml
PYPROJECT=$(cat pyproject.toml)
assert_contains "$PYPROJECT" "certifi" "Package added to pyproject.toml"

# Check hermes.lock
LOCKFILE=$(cat hermes.lock)
assert_contains "$LOCKFILE" "certifi" "Package added to lockfile"

# Check installation
CERTIFI_PATH=$(find .venv/lib -type d -name "certifi" 2>/dev/null | head -1)
if [ -n "$CERTIFI_PATH" ]; then
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    PASSED_TESTS=$((PASSED_TESTS + 1))
    echo -e "${GREEN}✓${NC} certifi installed in site-packages"
else
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    FAILED_TESTS=$((FAILED_TESTS + 1))
    echo -e "${RED}✗${NC} certifi installed in site-packages"
fi

echo ""

# ============================================================================
# TEST 3: hermes add (package with dependencies)
# ============================================================================
echo -e "${BLUE}[TEST 3]${NC} hermes add (package with dependencies)"
mkdir -p "$TEST_DIR/test-add-deps"
cd "$TEST_DIR/test-add-deps"
$HERMES_BIN init > /dev/null 2>&1

$HERMES_BIN add requests > /dev/null 2>&1
assert_success "Add package with dependencies"

# Check that dependencies were installed
LIST_OUTPUT=$($HERMES_BIN list 2>&1)
assert_contains "$LIST_OUTPUT" "requests" "requests in package list"
assert_contains "$LIST_OUTPUT" "certifi" "certifi (dependency) in package list"
assert_contains "$LIST_OUTPUT" "urllib3" "urllib3 (dependency) in package list"
assert_contains "$LIST_OUTPUT" "idna" "idna (dependency) in package list"

echo ""

# ============================================================================
# TEST 4: hermes list
# ============================================================================
echo -e "${BLUE}[TEST 4]${NC} hermes list"
cd "$TEST_DIR/test-add-deps"

LIST_OUTPUT=$($HERMES_BIN list 2>&1)
assert_contains "$LIST_OUTPUT" "Installed packages" "Shows header"
assert_contains "$LIST_OUTPUT" "packages installed" "Shows package count"

# Empty project test
mkdir -p "$TEST_DIR/test-list-empty"
cd "$TEST_DIR/test-list-empty"
$HERMES_BIN init > /dev/null 2>&1

LIST_EMPTY=$($HERMES_BIN list 2>&1)
assert_contains "$LIST_EMPTY" "No packages installed" "Shows correct message for empty project"

echo ""

# ============================================================================
# TEST 5: hermes remove (with orphan cleanup)
# ============================================================================
echo -e "${BLUE}[TEST 5]${NC} hermes remove (with orphan cleanup)"
mkdir -p "$TEST_DIR/test-remove"
cd "$TEST_DIR/test-remove"
$HERMES_BIN init > /dev/null 2>&1
$HERMES_BIN add requests > /dev/null 2>&1

# Count packages before removal
BEFORE_COUNT=$($HERMES_BIN list 2>&1 | grep -c "│")

$HERMES_BIN remove requests > /dev/null 2>&1
assert_success "Remove command executes"

# Check all packages removed (including orphans)
LIST_AFTER=$($HERMES_BIN list 2>&1)
assert_contains "$LIST_AFTER" "No packages installed" "All packages removed including orphans"

# Check lockfile is empty
LOCKFILE=$(cat hermes.lock)
if echo "$LOCKFILE" | grep -F "package = []" > /dev/null; then
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    PASSED_TESTS=$((PASSED_TESTS + 1))
    echo -e "${GREEN}✓${NC} Lockfile cleared"
else
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    FAILED_TESTS=$((FAILED_TESTS + 1))
    echo -e "${RED}✗${NC} Lockfile cleared"
fi

# Check filesystem cleanup
REQUESTS_PATH=$(find .venv/lib -type d -name "requests" 2>/dev/null | head -1)
if [ -z "$REQUESTS_PATH" ]; then
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    PASSED_TESTS=$((PASSED_TESTS + 1))
    echo -e "${GREEN}✓${NC} requests directory removed"
else
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    FAILED_TESTS=$((FAILED_TESTS + 1))
    echo -e "${RED}✗${NC} requests directory removed (found at: $REQUESTS_PATH)"
fi

CERTIFI_PATH=$(find .venv/lib -type d -name "certifi" 2>/dev/null | head -1)
if [ -z "$CERTIFI_PATH" ]; then
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    PASSED_TESTS=$((PASSED_TESTS + 1))
    echo -e "${GREEN}✓${NC} certifi directory removed"
else
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    FAILED_TESTS=$((FAILED_TESTS + 1))
    echo -e "${RED}✗${NC} certifi directory removed (found at: $CERTIFI_PATH)"
fi

# Check import fails
assert_import_fails "requests" "requests cannot be imported after removal"

echo ""

# ============================================================================
# TEST 6: hermes remove --keep-deps
# ============================================================================
echo -e "${BLUE}[TEST 6]${NC} hermes remove --keep-deps"
mkdir -p "$TEST_DIR/test-keep-deps"
cd "$TEST_DIR/test-keep-deps"
$HERMES_BIN init > /dev/null 2>&1
$HERMES_BIN add httpx > /dev/null 2>&1

# Count packages before
BEFORE_LIST=$($HERMES_BIN list 2>&1)
BEFORE_PKG_COUNT=$(echo "$BEFORE_LIST" | grep -c "│" || echo "0")

$HERMES_BIN remove httpx --keep-deps > /dev/null 2>&1
assert_success "Remove with --keep-deps executes"

# Check httpx removed but dependencies remain
LIST_AFTER=$($HERMES_BIN list 2>&1)
assert_contains "$LIST_AFTER" "certifi" "Dependencies kept (certifi)"
assert_contains "$LIST_AFTER" "anyio" "Dependencies kept (anyio)"

# But httpx should be gone
if echo "$LIST_AFTER" | grep -q "httpx"; then
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    FAILED_TESTS=$((FAILED_TESTS + 1))
    echo -e "${RED}✗${NC} httpx removed from list"
else
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    PASSED_TESTS=$((PASSED_TESTS + 1))
    echo -e "${GREEN}✓${NC} httpx removed from list"
fi

# Check httpx cannot be imported
assert_import_fails "httpx" "httpx cannot be imported after removal"

echo ""

# ============================================================================
# TEST 7: hermes sync
# ============================================================================
echo -e "${BLUE}[TEST 7]${NC} hermes sync"
mkdir -p "$TEST_DIR/test-sync"
cd "$TEST_DIR/test-sync"
$HERMES_BIN init > /dev/null 2>&1
$HERMES_BIN add certifi > /dev/null 2>&1

# Remove venv to simulate fresh install
rm -rf .venv
$HERMES_BIN init > /dev/null 2>&1  # Recreate venv

$HERMES_BIN sync > /dev/null 2>&1
assert_success "Sync command executes"

# Check package installed
LIST_OUTPUT=$($HERMES_BIN list 2>&1)
assert_contains "$LIST_OUTPUT" "certifi" "Package restored from lockfile"

echo ""

# ============================================================================
# TEST 8: hermes cache info
# ============================================================================
echo -e "${BLUE}[TEST 8]${NC} hermes cache info"
CACHE_OUTPUT=$($HERMES_BIN cache info 2>&1)
assert_success "Cache info command executes"

assert_contains "$CACHE_OUTPUT" "Cache location" "Shows cache location"
assert_contains "$CACHE_OUTPUT" "Total size" "Shows cache size"
assert_contains "$CACHE_OUTPUT" "Wheels cached" "Shows wheel count"

echo ""

# ============================================================================
# TEST 9: Complete workflow (add, list, remove, verify cleanup)
# ============================================================================
echo -e "${BLUE}[TEST 9]${NC} Complete workflow test"
mkdir -p "$TEST_DIR/test-workflow"
cd "$TEST_DIR/test-workflow"
$HERMES_BIN init > /dev/null 2>&1

# Add package
$HERMES_BIN add requests > /dev/null 2>&1
assert_success "Workflow: Add requests"

# Verify installation
if .venv/bin/python -c "import requests; requests.get('https://httpbin.org/get', timeout=5)" > /dev/null 2>&1; then
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    PASSED_TESTS=$((PASSED_TESTS + 1))
    echo -e "${GREEN}✓${NC} Workflow: requests is functional"
else
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    FAILED_TESTS=$((FAILED_TESTS + 1))
    echo -e "${RED}✗${NC} Workflow: requests is functional"
fi

# Remove package
$HERMES_BIN remove requests > /dev/null 2>&1
assert_success "Workflow: Remove requests"

# Verify complete cleanup
assert_import_fails "requests" "Workflow: requests cannot be imported"

REQUESTS_PATH=$(find .venv/lib -type d -name "requests" 2>/dev/null | head -1)
if [ -z "$REQUESTS_PATH" ]; then
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    PASSED_TESTS=$((PASSED_TESTS + 1))
    echo -e "${GREEN}✓${NC} Workflow: requests directory removed"
else
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    FAILED_TESTS=$((FAILED_TESTS + 1))
    echo -e "${RED}✗${NC} Workflow: requests directory removed (found at: $REQUESTS_PATH)"
fi

PYCACHE_PATH=$(find .venv/lib -type d -name "__pycache__" -path "*/requests/*" 2>/dev/null | head -1)
if [ -z "$PYCACHE_PATH" ]; then
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    PASSED_TESTS=$((PASSED_TESTS + 1))
    echo -e "${GREEN}✓${NC} Workflow: __pycache__ removed"
else
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    FAILED_TESTS=$((FAILED_TESTS + 1))
    echo -e "${RED}✗${NC} Workflow: __pycache__ removed (found at: $PYCACHE_PATH)"
fi

echo ""

# ============================================================================
# TEST 10: Version and help commands
# ============================================================================
echo -e "${BLUE}[TEST 10]${NC} Version and help commands"

VERSION_OUTPUT=$($HERMES_BIN --version 2>&1)
assert_contains "$VERSION_OUTPUT" "hermes version" "Version command works"

HELP_OUTPUT=$($HERMES_BIN --help 2>&1)
assert_contains "$HELP_OUTPUT" "Fast Python package manager" "Help command works"
assert_contains "$HELP_OUTPUT" "init" "Help shows init command"
assert_contains "$HELP_OUTPUT" "add" "Help shows add command"
assert_contains "$HELP_OUTPUT" "remove" "Help shows remove command"

echo ""

# ============================================================================
# FINAL REPORT
# ============================================================================
echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║                    TEST RESULTS                            ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "Total Tests:   ${BLUE}$TOTAL_TESTS${NC}"
echo -e "Passed:        ${GREEN}$PASSED_TESTS${NC}"
echo -e "Failed:        ${RED}$FAILED_TESTS${NC}"
echo ""

if [ $FAILED_TESTS -eq 0 ]; then
    echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║               ✓ ALL TESTS PASSED! ✓                       ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
    exit 0
else
    echo -e "${RED}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${RED}║               ✗ SOME TESTS FAILED ✗                       ║${NC}"
    echo -e "${RED}╚════════════════════════════════════════════════════════════╝${NC}"
    exit 1
fi
