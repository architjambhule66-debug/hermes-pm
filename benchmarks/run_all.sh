#!/bin/bash

# Hermes Benchmarking Suite
# Runs all benchmarks and generates comparison report

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPTS_DIR="$SCRIPT_DIR/scripts"
RESULTS_DIR="$SCRIPT_DIR/results/raw"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Ensure results directory exists
mkdir -p "$RESULTS_DIR"

# Function to print colored status messages
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if poetry is available
check_poetry() {
    if command -v poetry &> /dev/null; then
        return 0
    else
        return 1
    fi
}

# Run benchmark for a specific tool and tier
run_benchmark() {
    local tool=$1
    local tier=$2
    local script="$SCRIPTS_DIR/bench_${tool}.py"
    
    if [ ! -f "$script" ]; then
        print_error "Script not found: $script"
        return 1
    fi
    
    print_status "Running $tool benchmark for $tier..."
    
    if python3 "$script" "$tier"; then
        print_success "$tool $tier completed"
        return 0
    else
        print_error "$tool $tier failed"
        return 1
    fi
}

# Main execution
main() {
    echo ""
    echo "======================================================"
    echo "  Hermes Benchmarking Suite"
    echo "======================================================"
    echo ""
    
    # Get list of tiers to run
    TIERS=("tier1_basic" "tier2_ml" "tier3_full")
    
    # Parse command line arguments
    if [ "$1" == "--quick" ]; then
        print_warning "Quick mode: Running tier1_basic only"
        TIERS=("tier1_basic")
    elif [ -n "$1" ]; then
        print_warning "Running only tier: $1"
        TIERS=("$1")
    fi
    
    # Check which tools are available
    TOOLS=("hermes" "pip")
    if check_poetry; then
        print_status "Poetry detected, will include in benchmarks"
        TOOLS+=("poetry")
    else
        print_warning "Poetry not found, skipping poetry benchmarks"
    fi
    
    echo ""
    print_status "Will benchmark: ${TOOLS[@]}"
    print_status "Tiers: ${TIERS[@]}"
    echo ""
    
    # Confirm before proceeding
    if [ "$2" != "--no-confirm" ]; then
        read -p "This will take 30-60 minutes. Continue? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_warning "Aborted by user"
            exit 0
        fi
    fi
    
    # Track start time
    START_TIME=$(date +%s)
    FAILED_BENCHMARKS=()
    
    # Run benchmarks
    for tier in "${TIERS[@]}"; do
        echo ""
        echo "------------------------------------------------------"
        echo "  Tier: $tier"
        echo "------------------------------------------------------"
        
        for tool in "${TOOLS[@]}"; do
            if ! run_benchmark "$tool" "$tier"; then
                FAILED_BENCHMARKS+=("${tool}_${tier}")
            fi
            echo ""
        done
    done
    
    # Calculate elapsed time
    END_TIME=$(date +%s)
    ELAPSED=$((END_TIME - START_TIME))
    MINUTES=$((ELAPSED / 60))
    SECONDS=$((ELAPSED % 60))
    
    echo ""
    echo "======================================================"
    echo "  Benchmark Execution Complete"
    echo "======================================================"
    echo ""
    print_status "Total time: ${MINUTES}m ${SECONDS}s"
    
    # Report any failures
    if [ ${#FAILED_BENCHMARKS[@]} -gt 0 ]; then
        print_error "Failed benchmarks: ${FAILED_BENCHMARKS[@]}"
    else
        print_success "All benchmarks completed successfully"
    fi
    
    # Generate comparison report
    echo ""
    print_status "Generating comparison report..."
    
    if python3 "$SCRIPTS_DIR/compare.py"; then
        print_success "Report generated: $SCRIPT_DIR/results/report.md"
        echo ""
        echo "View the report with:"
        echo "  cat benchmarks/results/report.md"
        echo "  or"
        echo "  open benchmarks/results/report.md"
    else
        print_error "Failed to generate comparison report"
        exit 1
    fi
    
    echo ""
    echo "======================================================"
    print_success "Benchmarking suite finished!"
    echo "======================================================"
    echo ""
}

# Run main function
main "$@"
