#!/usr/bin/env bash
#
# EP1 CLI Flasher Wrapper Script
# Creates a virtual environment, installs dependencies, and runs the flasher
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"
FLASHER_SCRIPT="$SCRIPT_DIR/ep1-flasher.py"

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

print_header() {
	echo -e "${BLUE}${BOLD}$1${NC}"
}

print_success() {
	echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
	echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
	echo -e "${RED}✗${NC} $1"
}

# Check if the venv is ready to use (exists and has packages)
venv_is_ready() {
	if [ ! -d "$VENV_DIR" ]; then
		return 1
	fi

	# Check if key packages are available in venv
	source "$VENV_DIR/bin/activate"
	python -c "import requests" 2>/dev/null || return 1
	python -c "import serial" 2>/dev/null || return 1
	python -c "import esptool" 2>/dev/null || return 1
	deactivate 2>/dev/null || true

	return 0
}

# Check if Python 3 is available
check_python() {
	if ! command -v python3 &>/dev/null; then
		print_error "Python 3 not found. Please install Python 3.7 or later."
		exit 1
	fi

	PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
	print_success "Python $PYTHON_VERSION found"

	# Check version is >= 3.7
	if ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 7) else 1)'; then
		print_error "Python 3.7 or later is required"
		exit 1
	fi
}

# Create virtual environment if it doesn't exist
create_venv() {
	if [ -d "$VENV_DIR" ]; then
		print_success "Virtual environment already exists"
	else
		print_header "Creating virtual environment..."
		python3 -m venv "$VENV_DIR"
		print_success "Virtual environment created"
	fi
}

# Activate virtual environment
activate_venv() {
	source "$VENV_DIR/bin/activate"
}

# Install Python dependencies
install_dependencies() {
	print_header "Installing Python dependencies..."

	# Upgrade pip first
	python3 -m pip install --upgrade pip --quiet

	# Install requirements
	pip install --quiet -r "$SCRIPT_DIR/requirements.txt"

	print_success "Python dependencies installed"
}

# Run the flasher
run_flasher() {
	exec python3 "$FLASHER_SCRIPT" "$@"
}

# Main script - checks if setup is needed first
main() {
	# Quick check if everything is ready - if so, run silently
	if venv_is_ready; then
		activate_venv
		run_flasher "$@"
	fi

	# Need to do setup - show output
	echo ""
	print_header "EP1 CLI Flasher - Environment Setup"
	echo ""

	check_python
	create_venv
	activate_venv
	install_dependencies

	echo ""
	run_flasher "$@"
}

main "$@"
