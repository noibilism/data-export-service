#!/bin/bash

# Statement Service Deployment Script
# This script automates the deployment of the Statement Service
# Supports both Docker and conventional Python virtual environment deployments
#
# FEATURES:
# - Interactive parameter collection with sensible defaults
# - Support for both Docker and conventional deployments
# - Automatic database initialization and migration
# - Comprehensive health checks and verification
# - Service management (systemd for conventional deployment)
# - Environment file generation
# - Test mode for validation without deployment
#
# USAGE:
#   ./deploy.sh                  # Interactive deployment
#   ./deploy.sh --docker         # Deploy using Docker
#   ./deploy.sh --conventional   # Deploy using conventional method
#   ./deploy.sh --test           # Test mode (dry run)
#   ./deploy.sh --help           # Show help information
#
# REQUIREMENTS:
# Docker deployment:
#   - Docker and Docker Compose installed
#   - Sufficient disk space for containers
#
# Conventional deployment:
#   - Python 3.8+ installed
#   - systemd (for service management)
#   - MySQL client libraries
#   - Redis server accessible
#
# CONFIGURATION:
# The script will prompt for:
#   - Service configuration (port, environment, secret key)
#   - Database credentials (export and transactions databases)
#   - Redis configuration
#   - S3 settings (bucket, region, AWS credentials)
#   - Celery worker settings

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Banner
print_banner() {
    echo -e "${BLUE}"
    echo "================================================"
    echo "    Statement Service Deployment Script"
    echo "================================================"
    echo -e "${NC}"
}

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Prompt for user input with default value
prompt_input() {
    local prompt="$1"
    local default="$2"
    local var_name="$3"
    local is_password="$4"
    
    if [ "$is_password" = "true" ]; then
        echo -n "$prompt"
        if [ -n "$default" ]; then
            echo -n " [default: ****]: "
        else
            echo -n ": "
        fi
        read -s input
        echo
    else
        echo -n "$prompt"
        if [ -n "$default" ]; then
            echo -n " [default: $default]: "
        else
            echo -n ": "
        fi
        read input
    fi
    
    if [ -z "$input" ] && [ -n "$default" ]; then
        input="$default"
    fi
    
    eval "$var_name='$input'"
}

# Validate required parameters
validate_required() {
    local value="$1"
    local name="$2"
    
    if [ -z "$value" ]; then
        log_error "$name is required but not provided"
        exit 1
    fi
}

# Show help information
show_help() {
    cat << EOF
Statement Service Deployment Script

USAGE:
    $0 [OPTIONS]

OPTIONS:
    -h, --help          Show this help message
    -t, --test          Test mode (dry run without actual deployment)
    -d, --docker        Use Docker deployment method
    -c, --conventional  Use conventional deployment method

DESCRIPTION:
    This script deploys the Statement Service using either Docker or conventional
    Python virtual environment methods. It will prompt for necessary configuration
    parameters including database credentials, S3 settings, and service configuration.

EXAMPLES:
    $0                  # Interactive deployment with method selection
    $0 --docker         # Deploy using Docker
    $0 --conventional   # Deploy using conventional method
    $0 --test           # Test the script without actual deployment

EOF
}

# Main deployment function
main() {
    # Parse command line arguments
    local test_mode=false
    local deployment_method=""
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_help
                exit 0
                ;;
            -t|--test)
                test_mode=true
                shift
                ;;
            -d|--docker)
                deployment_method="docker"
                shift
                ;;
            -c|--conventional)
                deployment_method="conventional"
                shift
                ;;
            *)
                log_error "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done
    
    print_banner
    
    log_info "Starting Statement Service deployment..."
    
    if [ "$test_mode" = true ]; then
        log_info "Running in test mode - no actual deployment will occur"
    fi
    
    # Check if we're in the correct directory
    if [ ! -f "app.py" ] || [ ! -f "docker-compose.yml" ]; then
        log_error "Please run this script from the statement_service directory"
        exit 1
    fi
    
    # Deployment method selection
    if [ -z "$deployment_method" ]; then
        echo
        log_info "Select deployment method:"
        echo "1) Docker (Recommended)"
        echo "2) Conventional (Python virtual environment)"
        echo
        
        while true; do
            prompt_input "Enter your choice (1 or 2)" "1" "DEPLOYMENT_METHOD"
            
            case $DEPLOYMENT_METHOD in
                1)
                    DEPLOYMENT_TYPE="docker"
                    log_info "Selected: Docker deployment"
                    break
                    ;;
                2)
                    DEPLOYMENT_TYPE="conventional"
                    log_info "Selected: Conventional deployment"
                    break
                    ;;
                *)
                    log_warning "Invalid choice. Please enter 1 or 2."
                    ;;
            esac
        done
    else
        DEPLOYMENT_TYPE="$deployment_method"
        log_info "Selected: $DEPLOYMENT_TYPE deployment"
    fi
    
    # Collect deployment parameters
    collect_parameters "$test_mode"
    
    if [ "$test_mode" = true ]; then
        log_success "Test mode completed successfully!"
        log_info "Configuration would be saved to .env file"
        log_info "Deployment method: $DEPLOYMENT_TYPE"
        log_info "Service would be deployed on port: $SERVICE_PORT"
        exit 0
    fi
    
    # Create environment file
    create_env_file ".env"
    
    # Execute deployment based on selected method
    if [ "$DEPLOYMENT_TYPE" = "docker" ]; then
        deploy_docker
    else
        deploy_conventional
    fi
    
    # Verify deployment
    verify_deployment
    
    log_success "Deployment completed successfully!"
    print_access_info
}

# Collect deployment parameters
collect_parameters() {
    local test_mode=${1:-false}
    log_info "Collecting deployment parameters..."
    echo
    
    # Service Configuration
    log_info "=== Service Configuration ==="
    prompt_input "Service port" "5000" "SERVICE_PORT"
    prompt_input "Environment (development/production)" "production" "ENVIRONMENT"
    prompt_input "Secret key (leave empty to generate)" "" "SECRET_KEY"
    
    # Generate secret key if not provided
    if [ -z "$SECRET_KEY" ]; then
        SECRET_KEY=$(openssl rand -hex 32 2>/dev/null || python3 -c "import secrets; print(secrets.token_hex(32))" 2>/dev/null || echo "change-this-secret-key-in-production")
        log_info "Generated secret key"
    fi
    
    echo
    
    # Database Configuration
    log_info "=== Database Configuration ==="
    prompt_input "Export database host" "localhost" "EXPORT_DB_HOST"
    prompt_input "Export database port" "3306" "EXPORT_DB_PORT"
    prompt_input "Export database name" "export_db" "EXPORT_DB_NAME"
    prompt_input "Export database username" "export_user" "EXPORT_DB_USER"
    prompt_input "Export database password" "" "EXPORT_DB_PASSWORD" "true"
    if [ "$test_mode" = true ] && [ -z "$EXPORT_DB_PASSWORD" ]; then
        EXPORT_DB_PASSWORD="test_password"
        log_info "Using test password for export database"
    else
        validate_required "$EXPORT_DB_PASSWORD" "Export database password"
    fi
    
    echo
    prompt_input "Transactions database host" "localhost" "TRANSACTIONS_DB_HOST"
    prompt_input "Transactions database port" "3307" "TRANSACTIONS_DB_PORT"
    prompt_input "Transactions database name" "transactions_db" "TRANSACTIONS_DB_NAME"
    prompt_input "Transactions database username" "transactions_user" "TRANSACTIONS_DB_USER"
    prompt_input "Transactions database password" "" "TRANSACTIONS_DB_PASSWORD" "true"
    if [ "$test_mode" = true ] && [ -z "$TRANSACTIONS_DB_PASSWORD" ]; then
        TRANSACTIONS_DB_PASSWORD="test_password"
        log_info "Using test password for transactions database"
    else
        validate_required "$TRANSACTIONS_DB_PASSWORD" "Transactions database password"
    fi
    
    echo
    
    # Redis Configuration
    log_info "=== Redis Configuration ==="
    prompt_input "Redis host" "localhost" "REDIS_HOST"
    prompt_input "Redis port" "6379" "REDIS_PORT"
    prompt_input "Redis password (leave empty if none)" "" "REDIS_PASSWORD" "true"
    
    echo
    
    # S3 Configuration
    log_info "=== S3 Configuration ==="
    prompt_input "S3 bucket name" "" "S3_BUCKET_NAME"
    if [ "$test_mode" = true ] && [ -z "$S3_BUCKET_NAME" ]; then
        S3_BUCKET_NAME="test-bucket"
        log_info "Using test bucket name"
    else
        validate_required "$S3_BUCKET_NAME" "S3 bucket name"
    fi
    prompt_input "S3 region" "us-east-1" "S3_REGION"
    prompt_input "AWS Access Key ID" "" "AWS_ACCESS_KEY_ID"
    if [ "$test_mode" = true ] && [ -z "$AWS_ACCESS_KEY_ID" ]; then
        AWS_ACCESS_KEY_ID="test_access_key"
        log_info "Using test AWS access key"
    else
        validate_required "$AWS_ACCESS_KEY_ID" "AWS Access Key ID"
    fi
    prompt_input "AWS Secret Access Key" "" "AWS_SECRET_ACCESS_KEY" "true"
    if [ "$test_mode" = true ] && [ -z "$AWS_SECRET_ACCESS_KEY" ]; then
        AWS_SECRET_ACCESS_KEY="test_secret_key"
        log_info "Using test AWS secret key"
    else
        validate_required "$AWS_SECRET_ACCESS_KEY" "AWS Secret Access Key"
    fi
    
    echo
    
    # Celery Configuration
    log_info "=== Celery Configuration ==="
    prompt_input "Number of Celery workers" "2" "CELERY_WORKERS"
    prompt_input "Celery log level (INFO/DEBUG/WARNING/ERROR)" "INFO" "CELERY_LOG_LEVEL"
    
    echo
    
    # Additional Configuration for conventional deployment
    if [ "$DEPLOYMENT_TYPE" = "conventional" ]; then
        log_info "=== Additional Configuration ==="
        prompt_input "Python executable path" "python3" "PYTHON_EXEC"
        prompt_input "Virtual environment name" "venv" "VENV_NAME"
        prompt_input "Service user (leave empty for current user)" "" "SERVICE_USER"
        prompt_input "Service directory" "/opt/statement_service" "SERVICE_DIR"
    fi
    
    log_success "Parameters collected successfully"
}

deploy_docker() {
    log_info "Starting Docker deployment..."
    
    # Check Docker prerequisites
    if ! command_exists docker; then
        log_error "Docker is not installed. Please install Docker first."
        log_info "Visit: https://docs.docker.com/get-docker/"
        exit 1
    fi
    
    if ! command_exists docker-compose; then
        log_error "Docker Compose is not installed. Please install Docker Compose first."
        log_info "Visit: https://docs.docker.com/compose/install/"
        exit 1
    fi
    
    # Check if Docker daemon is running
    if ! docker info >/dev/null 2>&1; then
        log_error "Docker daemon is not running. Please start Docker first."
        exit 1
    fi
    
    log_success "Docker prerequisites check passed"
    
    # Stop existing containers if running
    log_info "Stopping existing containers..."
    docker-compose down --remove-orphans 2>/dev/null || true
    
    # Update docker-compose.yml with environment variables
    update_docker_compose
    
    # Pull latest images
    log_info "Pulling Docker images..."
    docker-compose pull
    
    # Build application image
    log_info "Building application image..."
    docker-compose build
    
    # Start services
    log_info "Starting services..."
    docker-compose up -d
    
    # Wait for services to be ready
    log_info "Waiting for services to start..."
    sleep 10
    
    # Initialize databases
    initialize_databases_docker
    
    log_success "Docker deployment completed"
}

deploy_conventional() {
    log_info "Starting conventional deployment..."
    
    # Check Python prerequisites
    if ! command_exists "$PYTHON_EXEC"; then
        log_error "Python executable '$PYTHON_EXEC' not found. Please install Python 3.8+ first."
        exit 1
    fi
    
    # Check Python version
    local python_version=$("$PYTHON_EXEC" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    log_info "Using Python version: $python_version"
    
    if ! "$PYTHON_EXEC" -c "import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)"; then
        log_error "Python 3.8 or higher is required. Found: $python_version"
        exit 1
    fi
    
    # Check for required system packages
    check_system_dependencies
    
    # Set up service directory
    setup_service_directory
    
    # Create Python virtual environment
    setup_virtual_environment
    
    # Install Python dependencies
    install_python_dependencies
    
    # Copy application files
    copy_application_files
    
    # Create systemd service files
    create_systemd_services
    
    # Initialize databases
    initialize_databases_conventional
    
    # Start services
    start_services
    
    log_success "Conventional deployment completed"
}

# Update docker-compose.yml with environment variables
update_docker_compose() {
    log_info "Updating docker-compose configuration..."
    
    # Create a temporary docker-compose override file
    cat > docker-compose.override.yml << EOF
version: '3.8'
services:
  app:
    environment:
      - FLASK_ENV=$ENVIRONMENT
      - SECRET_KEY=$SECRET_KEY
      - PORT=$SERVICE_PORT
      - EXPORT_DB_HOST=export_db
      - EXPORT_DB_PORT=3306
      - EXPORT_DB_NAME=$EXPORT_DB_NAME
      - EXPORT_DB_USER=$EXPORT_DB_USER
      - EXPORT_DB_PASSWORD=$EXPORT_DB_PASSWORD
      - TRANSACTIONS_DB_HOST=transactions_db
      - TRANSACTIONS_DB_PORT=3306
      - TRANSACTIONS_DB_NAME=$TRANSACTIONS_DB_NAME
      - TRANSACTIONS_DB_USER=$TRANSACTIONS_DB_USER
      - TRANSACTIONS_DB_PASSWORD=$TRANSACTIONS_DB_PASSWORD
      - REDIS_HOST=redis
      - REDIS_PORT=6379
      - REDIS_PASSWORD=$REDIS_PASSWORD
      - S3_BUCKET_NAME=$S3_BUCKET_NAME
      - S3_REGION=$S3_REGION
      - AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID
      - AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY
      - CELERY_BROKER_URL=redis://redis:6379/0
      - CELERY_RESULT_BACKEND=redis://redis:6379/0
    ports:
      - "$SERVICE_PORT:5000"
  
  worker:
    environment:
      - FLASK_ENV=$ENVIRONMENT
      - SECRET_KEY=$SECRET_KEY
      - EXPORT_DB_HOST=export_db
      - EXPORT_DB_PORT=3306
      - EXPORT_DB_NAME=$EXPORT_DB_NAME
      - EXPORT_DB_USER=$EXPORT_DB_USER
      - EXPORT_DB_PASSWORD=$EXPORT_DB_PASSWORD
      - TRANSACTIONS_DB_HOST=transactions_db
      - TRANSACTIONS_DB_PORT=3306
      - TRANSACTIONS_DB_NAME=$TRANSACTIONS_DB_NAME
      - TRANSACTIONS_DB_USER=$TRANSACTIONS_DB_USER
      - TRANSACTIONS_DB_PASSWORD=$TRANSACTIONS_DB_PASSWORD
      - REDIS_HOST=redis
      - REDIS_PORT=6379
      - REDIS_PASSWORD=$REDIS_PASSWORD
      - S3_BUCKET_NAME=$S3_BUCKET_NAME
      - S3_REGION=$S3_REGION
      - AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID
      - AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY
      - CELERY_BROKER_URL=redis://redis:6379/0
      - CELERY_RESULT_BACKEND=redis://redis:6379/0
      - CELERY_LOG_LEVEL=$CELERY_LOG_LEVEL
  
  export_db:
    environment:
      - MYSQL_ROOT_PASSWORD=$EXPORT_DB_PASSWORD
      - MYSQL_DATABASE=$EXPORT_DB_NAME
      - MYSQL_USER=$EXPORT_DB_USER
      - MYSQL_PASSWORD=$EXPORT_DB_PASSWORD
  
  transactions_db:
    environment:
      - MYSQL_ROOT_PASSWORD=$TRANSACTIONS_DB_PASSWORD
      - MYSQL_DATABASE=$TRANSACTIONS_DB_NAME
      - MYSQL_USER=$TRANSACTIONS_DB_USER
      - MYSQL_PASSWORD=$TRANSACTIONS_DB_PASSWORD
EOF
    
    log_success "Docker compose configuration updated"
}

# Initialize databases in Docker
initialize_databases_docker() {
    log_info "Initializing databases..."
    
    # Wait for databases to be ready
    log_info "Waiting for databases to be ready..."
    wait_for_database_docker "export_db" "$EXPORT_DB_NAME" "$EXPORT_DB_USER" "$EXPORT_DB_PASSWORD"
    wait_for_database_docker "transactions_db" "$TRANSACTIONS_DB_NAME" "$TRANSACTIONS_DB_USER" "$TRANSACTIONS_DB_PASSWORD"
    
    # Test Redis connection
    log_info "Testing Redis connection..."
    if ! docker-compose exec -T redis redis-cli ping >/dev/null 2>&1; then
        log_error "Redis is not responding"
        return 1
    fi
    log_success "Redis connection successful"
    
    # Run database initialization
    log_info "Running database migrations..."
    local max_attempts=3
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if docker-compose exec -T app python init_db.py; then
            log_success "Database initialization completed"
            return 0
        else
            log_warning "Database initialization attempt $attempt/$max_attempts failed"
            if [ $attempt -lt $max_attempts ]; then
                log_info "Retrying in 10 seconds..."
                sleep 10
            fi
            attempt=$((attempt + 1))
        fi
    done
    
    log_error "Database initialization failed after $max_attempts attempts"
    return 1
}

verify_deployment() {
    log_info "Verifying deployment..."
    
    # Verify service is running
    verify_service_running
    
    # Verify health endpoint
    verify_health_endpoint
    
    # Verify API endpoints
    verify_api_endpoints
    
    # Verify database connectivity
    verify_database_connectivity
    
    # Verify Celery worker
    verify_celery_worker
    
    log_success "All deployment verification checks passed!"
}

# Verify service is running
verify_service_running() {
    log_info "Verifying service is running..."
    
    if [ "$DEPLOYMENT_TYPE" = "docker" ]; then
        # Check Docker containers
        if ! docker-compose ps | grep -q "Up"; then
            log_error "Some Docker containers are not running"
            docker-compose ps
            return 1
        fi
        log_success "All Docker containers are running"
    else
        # Check systemd services
        if ! sudo systemctl is-active --quiet statement-service; then
            log_error "Statement service is not running"
            sudo systemctl status statement-service
            return 1
        fi
        
        if ! sudo systemctl is-active --quiet statement-service-worker; then
            log_warning "Statement service worker is not running"
            sudo systemctl status statement-service-worker
        else
            log_success "Statement service worker is running"
        fi
        
        log_success "Statement service is running"
    fi
}

# Verify health endpoint
verify_health_endpoint() {
    log_info "Verifying health endpoint..."
    
    local max_attempts=30
    local attempt=1
    local health_url="http://localhost:$SERVICE_PORT/health"
    
    log_info "Checking service health at $health_url"
    
    while [ $attempt -le $max_attempts ]; do
        if curl -s -f "$health_url" >/dev/null 2>&1; then
            log_success "Service is responding"
            
            # Test health endpoint response format
            local health_response=$(curl -s "$health_url")
            if echo "$health_response" | grep -q '"status"'; then
                log_success "Health endpoint format is correct"
                
                # Check if service is healthy
                if echo "$health_response" | grep -q '"healthy"'; then
                    log_success "Service reports as healthy"
                else
                    log_warning "Service may have health issues"
                    echo "Health response: $health_response"
                fi
            else
                log_warning "Health endpoint responded but format may be incorrect"
                echo "Response: $health_response"
            fi
            
            return 0
        fi
        
        log_info "Attempt $attempt/$max_attempts: Service not ready yet, waiting..."
        sleep 5
        attempt=$((attempt + 1))
    done
    
    log_error "Service failed to become healthy within expected time"
    show_deployment_logs
    return 1
}

# Verify API endpoints
verify_api_endpoints() {
    log_info "Verifying API endpoints..."
    
    local base_url="http://localhost:$SERVICE_PORT"
    
    # Test dashboard endpoint
    if curl -s -f "$base_url/dashboard" >/dev/null 2>&1; then
        log_success "Dashboard endpoint is accessible"
    else
        log_warning "Dashboard endpoint may not be accessible"
    fi
    
    # Test metrics endpoint
    if curl -s -f "$base_url/metrics" >/dev/null 2>&1; then
        log_success "Metrics endpoint is accessible"
    else
        log_warning "Metrics endpoint may not be accessible"
    fi
    
    # Test export endpoint (should require authentication)
    local export_response=$(curl -s -o /dev/null -w "%{http_code}" "$base_url/export")
    if [ "$export_response" = "401" ] || [ "$export_response" = "403" ]; then
        log_success "Export endpoint is properly protected (HTTP $export_response)"
    else
        log_warning "Export endpoint response unexpected (HTTP $export_response)"
    fi
}

# Verify database connectivity
verify_database_connectivity() {
    log_info "Verifying database connectivity..."
    
    # The health endpoint should already test database connectivity
    # But we can do additional checks here if needed
    local health_url="http://localhost:$SERVICE_PORT/health"
    local health_response=$(curl -s "$health_url" 2>/dev/null)
    
    if echo "$health_response" | grep -q '"database"'; then
        if echo "$health_response" | grep -q '"database".*"healthy"'; then
            log_success "Database connectivity verified through health endpoint"
        else
            log_error "Database connectivity issues detected"
            echo "Health response: $health_response"
            return 1
        fi
    else
        log_warning "Could not verify database connectivity from health endpoint"
    fi
}

# Verify Celery worker
verify_celery_worker() {
    log_info "Verifying Celery worker..."
    
    # Check through health endpoint
    local health_url="http://localhost:$SERVICE_PORT/health"
    local health_response=$(curl -s "$health_url" 2>/dev/null)
    
    if echo "$health_response" | grep -q '"celery"'; then
        if echo "$health_response" | grep -q '"celery".*"healthy"'; then
            log_success "Celery worker verified through health endpoint"
        else
            log_warning "Celery worker may have issues"
            echo "Health response: $health_response"
        fi
    else
        log_warning "Could not verify Celery worker from health endpoint"
    fi
    
    # Additional check for Docker deployment
    if [ "$DEPLOYMENT_TYPE" = "docker" ]; then
        if docker-compose ps worker | grep -q "Up"; then
            log_success "Celery worker container is running"
        else
            log_warning "Celery worker container may not be running"
        fi
    fi
}

# Show deployment logs for troubleshooting
show_deployment_logs() {
    log_info "Showing recent logs for troubleshooting..."
    
    if [ "$DEPLOYMENT_TYPE" = "docker" ]; then
        log_info "Docker container status:"
        docker-compose ps
        echo
        log_info "Recent application logs:"
        docker-compose logs --tail=20 app
        echo
        log_info "Recent worker logs:"
        docker-compose logs --tail=10 worker
    else
        log_info "Service status:"
        sudo systemctl status statement-service --no-pager -l
        echo
        log_info "Recent service logs:"
        sudo journalctl -u statement-service --no-pager -l -n 20
    fi
}

# Check system dependencies for conventional deployment
check_system_dependencies() {
    log_info "Checking system dependencies..."
    
    local missing_deps=()
    
    # Check for required system packages
    if ! command_exists curl; then
        missing_deps+=("curl")
    fi
    
    if ! command_exists systemctl; then
        log_warning "systemctl not found. Service management may not work properly."
    fi
    
    # Check for MySQL client (optional but recommended)
    if ! command_exists mysql && ! command_exists mariadb; then
        log_warning "MySQL/MariaDB client not found. Database operations may be limited."
    fi
    
    if [ ${#missing_deps[@]} -gt 0 ]; then
        log_error "Missing required dependencies: ${missing_deps[*]}"
        log_info "Please install them using your system package manager"
        exit 1
    fi
    
    log_success "System dependencies check passed"
}

# Set up service directory
setup_service_directory() {
    log_info "Setting up service directory: $SERVICE_DIR"
    
    # Create service directory
    if [ ! -d "$SERVICE_DIR" ]; then
        sudo mkdir -p "$SERVICE_DIR"
        log_info "Created service directory"
    fi
    
    # Set ownership
    if [ -n "$SERVICE_USER" ]; then
        sudo chown -R "$SERVICE_USER:$SERVICE_USER" "$SERVICE_DIR"
        log_info "Set ownership to $SERVICE_USER"
    else
        sudo chown -R "$(whoami):$(whoami)" "$SERVICE_DIR"
        log_info "Set ownership to current user"
    fi
    
    log_success "Service directory setup completed"
}

# Set up Python virtual environment
setup_virtual_environment() {
    log_info "Setting up Python virtual environment..."
    
    local venv_path="$SERVICE_DIR/$VENV_NAME"
    
    # Create virtual environment
    if [ ! -d "$venv_path" ]; then
        "$PYTHON_EXEC" -m venv "$venv_path"
        log_info "Created virtual environment at $venv_path"
    else
        log_info "Virtual environment already exists"
    fi
    
    # Activate virtual environment and upgrade pip
    source "$venv_path/bin/activate"
    pip install --upgrade pip
    
    log_success "Virtual environment setup completed"
}

# Install Python dependencies
install_python_dependencies() {
    log_info "Installing Python dependencies..."
    
    local venv_path="$SERVICE_DIR/$VENV_NAME"
    source "$venv_path/bin/activate"
    
    # Install requirements
    pip install -r requirements.txt
    
    log_success "Python dependencies installed"
}

# Copy application files
copy_application_files() {
    log_info "Copying application files..."
    
    # Copy all application files except venv and .git
    sudo rsync -av --exclude="$VENV_NAME" --exclude=".git" --exclude="__pycache__" \
        --exclude="*.pyc" --exclude=".env" ./ "$SERVICE_DIR/"
    
    # Copy environment file
    sudo cp .env "$SERVICE_DIR/.env"
    
    # Set proper permissions
    if [ -n "$SERVICE_USER" ]; then
        sudo chown -R "$SERVICE_USER:$SERVICE_USER" "$SERVICE_DIR"
    else
        sudo chown -R "$(whoami):$(whoami)" "$SERVICE_DIR"
    fi
    
    log_success "Application files copied"
}

# Create systemd service files
create_systemd_services() {
    log_info "Creating systemd service files..."
    
    local service_user="${SERVICE_USER:-$(whoami)}"
    local venv_path="$SERVICE_DIR/$VENV_NAME"
    
    # Create main application service
    sudo tee /etc/systemd/system/statement-service.service > /dev/null << EOF
[Unit]
Description=Statement Service Flask Application
After=network.target mysql.service redis.service
Wants=mysql.service redis.service

[Service]
Type=simple
User=$service_user
WorkingDirectory=$SERVICE_DIR
Environment=PATH=$venv_path/bin
EnvironmentFile=$SERVICE_DIR/.env
ExecStart=$venv_path/bin/python app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
    
    # Create Celery worker service
    sudo tee /etc/systemd/system/statement-service-worker.service > /dev/null << EOF
[Unit]
Description=Statement Service Celery Worker
After=network.target mysql.service redis.service statement-service.service
Wants=mysql.service redis.service

[Service]
Type=simple
User=$service_user
WorkingDirectory=$SERVICE_DIR
Environment=PATH=$venv_path/bin
EnvironmentFile=$SERVICE_DIR/.env
ExecStart=$venv_path/bin/celery -A workers.celery_app worker --loglevel=$CELERY_LOG_LEVEL --concurrency=$CELERY_WORKERS
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
    
    # Reload systemd
    sudo systemctl daemon-reload
    
    # Enable services
    sudo systemctl enable statement-service
    sudo systemctl enable statement-service-worker
    
    log_success "Systemd services created and enabled"
}

# Initialize databases for conventional deployment
initialize_databases_conventional() {
    log_info "Initializing databases..."
    
    # Test database connections first
    test_database_connection "$EXPORT_DB_HOST" "$EXPORT_DB_PORT" "$EXPORT_DB_NAME" "$EXPORT_DB_USER" "$EXPORT_DB_PASSWORD"
    test_database_connection "$TRANSACTIONS_DB_HOST" "$TRANSACTIONS_DB_PORT" "$TRANSACTIONS_DB_NAME" "$TRANSACTIONS_DB_USER" "$TRANSACTIONS_DB_PASSWORD"
    
    # Test Redis connection
    test_redis_connection
    
    local venv_path="$SERVICE_DIR/$VENV_NAME"
    
    # Change to service directory and activate venv
    cd "$SERVICE_DIR"
    source "$venv_path/bin/activate"
    
    # Run database initialization with retry logic
    local max_attempts=3
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if python init_db.py; then
            log_success "Database initialization completed"
            return 0
        else
            log_warning "Database initialization attempt $attempt/$max_attempts failed"
            if [ $attempt -lt $max_attempts ]; then
                log_info "Retrying in 5 seconds..."
                sleep 5
            fi
            attempt=$((attempt + 1))
        fi
    done
    
    log_error "Database initialization failed after $max_attempts attempts"
    return 1
}

# Start services for conventional deployment
start_services() {
    log_info "Starting services..."
    
    # Start main application
    sudo systemctl start statement-service
    
    # Wait a moment for the app to start
    sleep 5
    
    # Start worker
    sudo systemctl start statement-service-worker
    
    # Check service status
    if sudo systemctl is-active --quiet statement-service; then
        log_success "Statement service started successfully"
    else
        log_error "Failed to start statement service"
        sudo systemctl status statement-service
        return 1
    fi
    
    if sudo systemctl is-active --quiet statement-service-worker; then
        log_success "Statement service worker started successfully"
    else
        log_warning "Statement service worker may have issues"
        sudo systemctl status statement-service-worker
    fi
    
    log_success "Services started"
}

# Wait for database to be ready in Docker
wait_for_database_docker() {
    local container_name="$1"
    local db_name="$2"
    local db_user="$3"
    local db_password="$4"
    local max_attempts=30
    local attempt=1
    
    log_info "Waiting for $container_name database to be ready..."
    
    while [ $attempt -le $max_attempts ]; do
        if docker-compose exec -T "$container_name" mysql -u"$db_user" -p"$db_password" -e "SELECT 1" "$db_name" >/dev/null 2>&1; then
            log_success "$container_name database is ready"
            return 0
        fi
        
        log_info "Attempt $attempt/$max_attempts: $container_name not ready yet, waiting..."
        sleep 2
        attempt=$((attempt + 1))
    done
    
    log_error "$container_name database failed to become ready within expected time"
    return 1
}

# Test database connection for conventional deployment
test_database_connection() {
    local host="$1"
    local port="$2"
    local db_name="$3"
    local user="$4"
    local password="$5"
    
    log_info "Testing database connection to $host:$port/$db_name..."
    
    # Try to connect using mysql client if available
    if command_exists mysql; then
        if mysql -h"$host" -P"$port" -u"$user" -p"$password" -e "SELECT 1" "$db_name" >/dev/null 2>&1; then
            log_success "Database connection to $host:$port/$db_name successful"
            return 0
        else
            log_error "Failed to connect to database $host:$port/$db_name"
            log_info "Please ensure the database server is running and credentials are correct"
            return 1
        fi
    else
        log_warning "MySQL client not available, skipping database connection test"
        log_info "Database connection will be tested during application startup"
        return 0
    fi
}

# Test Redis connection for conventional deployment
test_redis_connection() {
    log_info "Testing Redis connection to $REDIS_HOST:$REDIS_PORT..."
    
    # Try to connect using redis-cli if available
    if command_exists redis-cli; then
        local redis_cmd="redis-cli -h $REDIS_HOST -p $REDIS_PORT"
        
        if [ -n "$REDIS_PASSWORD" ]; then
            redis_cmd="$redis_cmd -a $REDIS_PASSWORD"
        fi
        
        if $redis_cmd ping >/dev/null 2>&1; then
            log_success "Redis connection successful"
            return 0
        else
            log_error "Failed to connect to Redis at $REDIS_HOST:$REDIS_PORT"
            log_info "Please ensure Redis server is running and credentials are correct"
            return 1
        fi
    else
        log_warning "redis-cli not available, skipping Redis connection test"
        log_info "Redis connection will be tested during application startup"
        return 0
    fi
}

# Create environment file
create_env_file() {
    local env_file="$1"
    
    log_info "Creating environment file: $env_file"
    
    cat > "$env_file" << EOF
# Flask Configuration
FLASK_ENV=$ENVIRONMENT
SECRET_KEY=$SECRET_KEY
PORT=$SERVICE_PORT

# Export Database Configuration
EXPORT_DB_HOST=$EXPORT_DB_HOST
EXPORT_DB_PORT=$EXPORT_DB_PORT
EXPORT_DB_NAME=$EXPORT_DB_NAME
EXPORT_DB_USER=$EXPORT_DB_USER
EXPORT_DB_PASSWORD=$EXPORT_DB_PASSWORD

# Transactions Database Configuration
TRANSACTIONS_DB_HOST=$TRANSACTIONS_DB_HOST
TRANSACTIONS_DB_PORT=$TRANSACTIONS_DB_PORT
TRANSACTIONS_DB_NAME=$TRANSACTIONS_DB_NAME
TRANSACTIONS_DB_USER=$TRANSACTIONS_DB_USER
TRANSACTIONS_DB_PASSWORD=$TRANSACTIONS_DB_PASSWORD

# Redis Configuration
REDIS_HOST=$REDIS_HOST
REDIS_PORT=$REDIS_PORT
REDIS_PASSWORD=$REDIS_PASSWORD

# S3 Configuration
S3_BUCKET_NAME=$S3_BUCKET_NAME
S3_REGION=$S3_REGION
AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY

# Celery Configuration
CELERY_BROKER_URL=redis://$REDIS_HOST:$REDIS_PORT/0
CELERY_RESULT_BACKEND=redis://$REDIS_HOST:$REDIS_PORT/0
CELERY_WORKERS=$CELERY_WORKERS
CELERY_LOG_LEVEL=$CELERY_LOG_LEVEL
EOF
    
    log_success "Environment file created"
}

print_access_info() {
    echo
    log_success "=== Deployment Complete ==="
    echo
    log_info "Service Information:"
    echo "  - Service URL: http://localhost:$SERVICE_PORT"
    echo "  - Health Check: http://localhost:$SERVICE_PORT/health"
    echo "  - Dashboard: http://localhost:$SERVICE_PORT/dashboard"
    echo "  - Metrics: http://localhost:$SERVICE_PORT/metrics"
    echo
    log_info "Next Steps:"
    echo "  1. Create API keys via the admin interface"
    echo "  2. Test the health endpoint"
    echo "  3. Monitor logs for any issues"
    echo
    if [ "$DEPLOYMENT_TYPE" = "docker" ]; then
        log_info "Docker Commands:"
        echo "  - View logs: docker-compose logs -f"
        echo "  - Stop services: docker-compose down"
        echo "  - Restart services: docker-compose restart"
    else
        log_info "Service Management:"
        echo "  - Start service: systemctl start statement-service"
        echo "  - Stop service: systemctl stop statement-service"
        echo "  - View logs: journalctl -u statement-service -f"
    fi
    echo
}

# Run main function
main "$@"