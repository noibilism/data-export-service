# Bank Statement Export Service

A production-ready Python service for exporting bank statement data with intelligent deduplication, background processing, S3 storage, and comprehensive dashboard management.

## 🚀 Quick Start

### Testing with SQLite (Recommended for Development)

```bash
# 1. Install dependencies
pip3 install flask sqlalchemy prometheus-flask-exporter

# 2. Initialize test database
python3 test_init_db.py

# 3. Start the test server
python3 test_app.py

# 4. Access the dashboard
open http://localhost:5001/dashboard
```

**Test API Key**: `sk_dbGYC7Gw-CfDa3n1ritzO7sdzNwqJ-0o8iwuJMlhNTI`

## 🏗️ Architecture Overview

The service is built with a microservices architecture optimized for large-scale data exports:

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Client App    │───▶│   Flask API     │───▶│  Celery Worker  │
│                 │    │ (API Key Auth)  │    │ (Background)    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │                        │
                                ▼                        ▼
                       ┌─────────────────┐    ┌─────────────────┐
                       │  Export MySQL   │    │ Transactions DB │
                       │   (Metadata)    │    │  (Read-only)    │
                       └─────────────────┘    └─────────────────┘
                                │                        │
                                ▼                        ▼
                       ┌─────────────────┐    ┌─────────────────┐
                       │   Dashboard     │    │   Amazon S3     │
                       │ (Monitoring)    │    │ (CSV Storage)   │
                       └─────────────────┘    └─────────────────┘
```

## ✨ Key Features

### 🔐 **Security & Authentication**
- **API Key Authentication**: Secure, manageable API keys with SHA-256 hashing
- **Admin Dashboard**: Web interface for API key management
- **Access Control**: Fine-grained permissions and key lifecycle management

### 📊 **Monitoring & Management**
- **Real-time Dashboard**: Bootstrap-powered web interface
- **Export Analytics**: Job statistics, success rates, and performance metrics
- **System Health**: Database connectivity, queue status, and resource monitoring
- **Prometheus Integration**: Comprehensive metrics collection

### 🚀 **Performance & Scalability**
- **Intelligent Deduplication**: SHA256-based duplicate prevention
- **Streaming Queries**: Memory-efficient processing of 10M+ row datasets
- **Background Processing**: Non-blocking API with Celery workers
- **Retry Logic**: Automatic retry with exponential backoff

### 💾 **Data Management**
- **S3 Integration**: Multipart uploads and secure pre-signed URLs
- **Multiple Database Support**: MySQL for production, SQLite for testing
- **Data Integrity**: Transaction-safe operations with rollback support

### Export Flow

1. **Client Request**: POST to `/api/export` with table name and date range
2. **Deduplication Check**: System checks for existing exports using SHA256 hash
3. **Job Queuing**: If new export needed, Celery task is queued
4. **Background Processing**: Worker streams data from transactions DB to CSV
5. **S3 Upload**: CSV file uploaded to S3 with multipart support
6. **Status Update**: Export metadata updated with file URL and metrics
7. **Client Retrieval**: GET `/api/export/{reference_id}` returns pre-signed URL

## Deployment Options

### Option 1: Docker Deployment (Recommended)

#### Prerequisites
- Docker 20.10+
- Docker Compose 2.0+
- AWS S3 bucket with appropriate permissions

#### Quick Start

1. **Clone and Configure**:
   ```bash
   git clone <repository-url>
   cd statement_service
   cp .env.example .env
   ```

2. **Update Environment Variables**:
   ```bash
   # Edit .env file with your credentials
   nano .env
   ```
   
   Required variables:
   ```env
   # AWS S3 Configuration
   AWS_ACCESS_KEY_ID=your_aws_access_key
   AWS_SECRET_ACCESS_KEY=your_aws_secret_key
   AWS_REGION=us-east-1
   S3_BUCKET=your-statement-exports-bucket
   
   # Security
   SECRET_KEY=your_super_secret_flask_key
   
   # Database (if using external)
   TRANSACTIONS_DATABASE_URL=mysql+pymysql://user:pass@host:port/transactions
   ```

3. **Start Services**:
   ```bash
   docker-compose up -d
   ```

4. **Verify Deployment**:
   ```bash
   # Check all services are running
   docker-compose ps
   
   # View logs
   docker-compose logs -f api
   ```

#### Service Endpoints
- **API**: http://localhost:5000
- **Flower (Monitoring)**: http://localhost:5555
- **Prometheus Metrics**: http://localhost:5000/metrics

### Option 2: AWS EC2 Ubuntu Deployment

#### EC2 Instance Requirements
- **Instance Type**: t3.medium or larger (2 vCPU, 4GB RAM minimum)
- **Storage**: 20GB+ EBS volume
- **Security Groups**: 
  - Port 22 (SSH)
  - Port 5000 (API)
  - Port 5555 (Flower - optional)
  - Port 3306 (MySQL - if external access needed)
  - Port 6379 (Redis - internal only)

#### Step-by-Step Installation

1. **Launch EC2 Instance**:
   ```bash
   # Connect to your EC2 instance
   ssh -i your-key.pem ubuntu@your-ec2-ip
   ```

2. **System Updates**:
   ```bash
   sudo apt update && sudo apt upgrade -y
   sudo apt install -y python3 python3-pip python3-venv git mysql-server redis-server
   ```

3. **Install Docker (Alternative)**:
   ```bash
   # If you prefer Docker on EC2
   curl -fsSL https://get.docker.com -o get-docker.sh
   sudo sh get-docker.sh
   sudo usermod -aG docker ubuntu
   sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
   sudo chmod +x /usr/local/bin/docker-compose
   ```

4. **Application Setup**:
   ```bash
   # Clone repository
   git clone <repository-url>
   cd statement_service
   
   # Create virtual environment
   python3 -m venv venv
   source venv/bin/activate
   
   # Install dependencies
   pip install -r requirements.txt
   ```

5. **Database Setup**:
   ```bash
   # Configure MySQL
   sudo mysql_secure_installation
   
   # Create databases
   sudo mysql -u root -p
   ```
   
   ```sql
   CREATE DATABASE export_service;
   CREATE DATABASE transactions;
   CREATE USER 'export_user'@'localhost' IDENTIFIED BY 'secure_password';
   CREATE USER 'readonly_user'@'localhost' IDENTIFIED BY 'readonly_password';
   GRANT ALL PRIVILEGES ON export_service.* TO 'export_user'@'localhost';
   GRANT SELECT ON transactions.* TO 'readonly_user'@'localhost';
   FLUSH PRIVILEGES;
   EXIT;
   ```
   
   ```bash
   # Initialize tables
   python migrations/create_exports_table.py
   ```

6. **Environment Configuration**:
   ```bash
   # Create production environment file
   cp .env.example .env
   nano .env
   ```
   
   Update with production values:
   ```env
   DATABASE_URL=mysql+pymysql://export_user:secure_password@localhost/export_service
   TRANSACTIONS_DATABASE_URL=mysql+pymysql://readonly_user:readonly_password@localhost/transactions
   CELERY_BROKER_URL=redis://localhost:6379/0
   CELERY_RESULT_BACKEND=redis://localhost:6379/0
   
   # AWS Configuration
   AWS_ACCESS_KEY_ID=your_access_key
   AWS_SECRET_ACCESS_KEY=your_secret_key
   S3_BUCKET=your-bucket-name
   
   # Security
   SECRET_KEY=your_production_secret_key
   JWT_SECRET_KEY=your_jwt_secret_key
   
   # Production settings
   FLASK_ENV=production
   LOG_LEVEL=INFO
   ```

7. **Service Configuration with Systemd**:
   
   Create API service:
   ```bash
   sudo nano /etc/systemd/system/statement-api.service
   ```
   
   ```ini
   [Unit]
   Description=Statement Export API
   After=network.target mysql.service redis.service
   
   [Service]
   Type=exec
   User=ubuntu
   WorkingDirectory=/home/ubuntu/statement_service
   Environment=PATH=/home/ubuntu/statement_service/venv/bin
   ExecStart=/home/ubuntu/statement_service/venv/bin/gunicorn --bind 0.0.0.0:5000 --workers 4 --timeout 300 app:app
   Restart=always
   RestartSec=3
   
   [Install]
   WantedBy=multi-user.target
   ```
   
   Create Celery worker service:
   ```bash
   sudo nano /etc/systemd/system/statement-worker.service
   ```
   
   ```ini
   [Unit]
   Description=Statement Export Celery Worker
   After=network.target redis.service
   
   [Service]
   Type=exec
   User=ubuntu
   WorkingDirectory=/home/ubuntu/statement_service
   Environment=PATH=/home/ubuntu/statement_service/venv/bin
   ExecStart=/home/ubuntu/statement_service/venv/bin/celery -A workers.celery_app worker --loglevel=info --concurrency=2
   Restart=always
   RestartSec=3
   
   [Install]
   WantedBy=multi-user.target
   ```
   
   Create Celery beat service:
   ```bash
   sudo nano /etc/systemd/system/statement-beat.service
   ```
   
   ```ini
   [Unit]
   Description=Statement Export Celery Beat
   After=network.target redis.service
   
   [Service]
   Type=exec
   User=ubuntu
   WorkingDirectory=/home/ubuntu/statement_service
   Environment=PATH=/home/ubuntu/statement_service/venv/bin
   ExecStart=/home/ubuntu/statement_service/venv/bin/celery -A workers.celery_app beat --loglevel=info
   Restart=always
   RestartSec=3
   
   [Install]
   WantedBy=multi-user.target
   ```

8. **Start Services**:
   ```bash
   # Reload systemd and start services
   sudo systemctl daemon-reload
   sudo systemctl enable statement-api statement-worker statement-beat
   sudo systemctl start statement-api statement-worker statement-beat
   
   # Check status
   sudo systemctl status statement-api
   sudo systemctl status statement-worker
   sudo systemctl status statement-beat
   ```

9. **Configure Nginx (Optional)**:
   ```bash
   sudo apt install nginx
   sudo nano /etc/nginx/sites-available/statement-service
   ```
   
   ```nginx
   server {
       listen 80;
       server_name your-domain.com;
   
       location / {
           proxy_pass http://127.0.0.1:5000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
           proxy_read_timeout 300;
           proxy_connect_timeout 300;
           proxy_send_timeout 300;
       }
   }
   ```
   
   ```bash
   sudo ln -s /etc/nginx/sites-available/statement-service /etc/nginx/sites-enabled/
   sudo nginx -t
   sudo systemctl restart nginx
   ```

## AWS Infrastructure Setup

### S3 Bucket Configuration

1. **Create S3 Bucket**:
   ```bash
   aws s3 mb s3://your-statement-exports-bucket --region us-east-1
   ```

2. **Set Bucket Policy**:
   ```json
   {
       "Version": "2012-10-17",
       "Statement": [
           {
               "Sid": "AllowServiceAccess",
               "Effect": "Allow",
               "Principal": {
                   "AWS": "arn:aws:iam::YOUR-ACCOUNT:user/statement-service-user"
               },
               "Action": [
                   "s3:GetObject",
                   "s3:PutObject",
                   "s3:DeleteObject"
               ],
               "Resource": "arn:aws:s3:::your-statement-exports-bucket/*"
           }
       ]
   }
   ```

3. **Configure Lifecycle Policy**:
   ```json
   {
       "Rules": [
           {
               "ID": "DeleteOldExports",
               "Status": "Enabled",
               "Expiration": {
                   "Days": 30
               }
           }
       ]
   }
   ```

### IAM User Setup

1. **Create IAM User**:
   ```bash
   aws iam create-user --user-name statement-service-user
   ```

2. **Attach Policy**:
   ```json
   {
       "Version": "2012-10-17",
       "Statement": [
           {
               "Effect": "Allow",
               "Action": [
                   "s3:GetObject",
                   "s3:PutObject",
                   "s3:DeleteObject",
                   "s3:ListBucket"
               ],
               "Resource": [
                   "arn:aws:s3:::your-statement-exports-bucket",
                   "arn:aws:s3:::your-statement-exports-bucket/*"
               ]
           }
       ]
   }
   ```

3. **Generate Access Keys**:
   ```bash
   aws iam create-access-key --user-name statement-service-user
   ```

## 📡 API Usage

### 🔐 Authentication

The API uses secure API key authentication. You can manage API keys through the dashboard:

1. **Access Dashboard**: `http://your-server:5001/dashboard`
2. **Navigate to API Keys**: Click "API Key Management" section
3. **Create New Key**: Click "Create API Key" and provide a name
4. **Copy Key**: Save the generated key securely (shown only once)

### 📤 Create Export Job

```bash
curl -X POST http://your-server:5000/api/export \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d '{
    "account_id": "123456",
    "table_name": "bank_transactions",
    "date_from": "2024-01-01",
    "date_to": "2024-01-31",
    "force_refresh": false
  }'
```

**Response**:
```json
{
  "reference_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "PENDING",
  "reused": false,
  "message": "Export job queued successfully"
}
```

### 📊 Check Export Status

```bash
curl -X GET http://your-server:5000/api/export/550e8400-e29b-41d4-a716-446655440000 \
  -H "Authorization: Bearer YOUR_API_KEY"
```

**Response (Completed)**:
```json
{
  "reference_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "COMPLETED",
  "table_name": "bank_transactions",
  "date_from": "2024-01-01",
  "date_to": "2024-01-31",
  "file_url": "https://presigned-s3-url.com/file.csv",
  "file_size": 2048576,
  "row_count": 50000,
  "created_at": "2024-01-15T10:30:00Z",
  "completed_at": "2024-01-15T10:35:00Z"
}
```

## 📊 Dashboard & Management

### 🖥️ Web Dashboard

Access the comprehensive dashboard at `http://your-server:5001/dashboard`

**Features:**
- **Export Analytics**: Real-time job statistics and success rates
- **System Health**: Database connectivity and queue status monitoring
- **Performance Metrics**: Response times, throughput, and resource usage
- **Interactive Charts**: Visual representation of export trends

### 🔑 API Key Management

Manage API keys through the admin interface at `http://your-server:5001/admin/api-keys`

**Capabilities:**
- **Create Keys**: Generate new API keys with custom names and descriptions
- **Monitor Usage**: Track last used timestamps and activity
- **Lifecycle Management**: Activate, deactivate, and delete keys
- **Security**: SHA-256 hashed storage with prefix display

**API Key Features:**
- Secure generation with `sk_` prefix
- Usage tracking and analytics
- Granular access control
- One-time display for security

### 📈 Real-time Monitoring

**Dashboard Sections:**
1. **Export Statistics**: Success rates, average processing time
2. **Recent Exports**: Latest job status and details
3. **System Health**: Database, queue, and service status
4. **API Key Management**: Create and manage authentication keys

**Auto-refresh**: Dashboard updates every 30 seconds for real-time monitoring

## 🔧 Monitoring and Maintenance

### Health Checks

```bash
# API Health
curl http://your-server:5000/health

# Prometheus Metrics
curl http://your-server:5000/metrics

# Celery Monitoring
# Access Flower dashboard at http://your-server:5555
```

### Log Management

```bash
# Docker logs
docker-compose logs -f api
docker-compose logs -f worker

# Systemd logs (EC2)
sudo journalctl -u statement-api -f
sudo journalctl -u statement-worker -f

# Application logs
tail -f logs/statement_service.log
```

### Performance Tuning

1. **Celery Workers**: Scale based on CPU and memory usage
   ```bash
   # Increase worker concurrency
   celery -A workers.celery_app worker --concurrency=4
   ```

2. **Database Optimization**:
   - Add indexes on frequently queried fields
   - Use read replicas for transactions database
   - Configure connection pooling

3. **S3 Optimization**:
   - Use appropriate storage class (Standard-IA for infrequent access)
   - Configure multipart upload thresholds
   - Implement intelligent tiering

### Backup and Recovery

1. **Database Backups**:
   ```bash
   # Automated backup script
   mysqldump -u root -p export_service > backup_$(date +%Y%m%d).sql
   ```

2. **Configuration Backups**:
   ```bash
   # Backup environment and configs
   tar -czf config_backup_$(date +%Y%m%d).tar.gz .env docker-compose.yml
   ```

## Troubleshooting

### Common Issues

1. **Database Connection Errors**:
   ```bash
   # Check MySQL status
   sudo systemctl status mysql
   
   # Test connection
   mysql -u export_user -p -h localhost export_service
   ```

2. **S3 Upload Failures**:
   ```bash
   # Test AWS credentials
   aws s3 ls s3://your-bucket-name
   
   # Check IAM permissions
   aws iam get-user-policy --user-name statement-service-user --policy-name S3Access
   ```

3. **Celery Worker Issues**:
   ```bash
   # Check Redis connection
   redis-cli ping
   
   # Monitor Celery tasks
   celery -A workers.celery_app inspect active
   ```

4. **Memory Issues**:
   ```bash
   # Monitor memory usage
   htop
   
   # Reduce chunk size in config
   export CHUNK_SIZE=5000
   ```

### Performance Monitoring

```bash
# System metrics
htop
iotop
df -h

# Application metrics
curl http://localhost:5000/metrics | grep export

# Database performance
mysql -u root -p -e "SHOW PROCESSLIST;"
```

## Security Considerations

1. **Environment Variables**: Never commit secrets to version control
2. **JWT Tokens**: Use strong secrets and appropriate expiration times
3. **Database Access**: Use read-only credentials for transactions database
4. **S3 Security**: Implement least-privilege IAM policies
5. **Network Security**: Use VPC and security groups appropriately
6. **SSL/TLS**: Configure HTTPS in production with proper certificates

## Scaling Considerations

1. **Horizontal Scaling**: Deploy multiple API instances behind a load balancer
2. **Worker Scaling**: Scale Celery workers based on queue depth
3. **Database Scaling**: Use read replicas and connection pooling
4. **Caching**: Implement Redis caching for frequently accessed data
5. **CDN**: Use CloudFront for S3 file distribution

## License

This project is licensed under the MIT License.