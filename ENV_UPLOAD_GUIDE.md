# Hướng dẫn tạo và upload file .env lên Jenkins

## Bước 1: Tạo file .env từ template

```bash
# Copy từ template
cp env.example .env

# Hoặc tạo thủ công
cat > .env << 'EOF'
# Storage Configuration
STORAGE_ROOT=/opt/rerun/uploads
DATA_DIR=/opt/rerun/uploads

# Nginx Configuration  
NGINX_INPUT_BASE_URL=http://192.168.210.100:8083/files
NGINX_PORT=8083

# API Configuration
API_PORT=8000
API_HOST=0.0.0.0

# Docker Configuration
API_ADJUST_IMAGE=api-adjust:latest
COMPOSE_PROJECT=api-adjust

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json

# Environment
ENVIRONMENT=production
DEBUG=false
EOF
```

## Bước 2: Upload file .env lên Jenkins

1. **Vào Jenkins Dashboard**
2. **Manage Jenkins** → **Manage Credentials**
3. **Click vào credential "rerun-env"**
4. **Click "Update"**
5. **Upload file .env** bạn vừa tạo
6. **Click "Save"**

## Bước 3: Kiểm tra credential

1. **Vào credential "rerun-env"**
2. **Kiểm tra file đã được upload**
3. **Test download file**

## Bước 4: Test pipeline

1. **Vào Jenkins job "api-adjust"**
2. **Click "Build Now"**
3. **Xem build logs**
4. **Kiểm tra stage "Prepare environment file"**

## Bước 5: Kiểm tra trên server

```bash
# Kiểm tra containers
ssh root@192.168.210.100 "docker ps"

# Kiểm tra API
ssh root@192.168.210.100 "curl http://localhost:8000/healthz"

# Kiểm tra nginx
ssh root@192.168.210.100 "curl http://localhost:8083"

# Kiểm tra logs
ssh root@192.168.210.100 "docker logs api-adjust"
```
