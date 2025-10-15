# Hướng dẫn cấu hình server cho API Adjust

## 📋 **Tổng quan cấu hình**

Dựa trên file `env.example` và code `api_server.py`, server cần được cấu hình như sau:

## 🔧 **1. Cấu hình Environment Variables**

### **Tạo file .env trên server:**

```bash
# SSH vào server
ssh root@192.168.210.100

# Tạo file .env
cat > /opt/api-adjust/.env << 'EOF'
# Storage Configuration
STORAGE_ROOT=/data/rrd
DATA_DIR=./data

# Web Server Configuration (for file access)
NGINX_INPUT_BASE_URL=http://192.168.210.100:8001/files

# API Configuration
API_PORT=8001
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

## 📁 **2. Cấu hình thư mục dữ liệu**

### **Tạo cấu trúc thư mục:**

```bash
# Tạo thư mục chính
mkdir -p /opt/api-adjust/data

# Tạo thư mục con
mkdir -p /opt/api-adjust/data/origin    # RRD files input
mkdir -p /opt/api-adjust/data/process   # RRD files output

# Cấu hình quyền
chmod 755 /opt/api-adjust/data
chmod 755 /opt/api-adjust/data/origin
chmod 755 /opt/api-adjust/data/process
```

## 🌐 **3. Cấu hình Nginx trên server (nếu cần)**

### **Tạo nginx config cho file serving:**

```bash
# Tạo nginx config
cat > /etc/nginx/sites-available/api-adjust << 'EOF'
server {
    listen 80;
    server_name 192.168.210.100;

    # Serve static files
    location /files/ {
        alias /opt/api-adjust/data/;
        autoindex on;
        autoindex_exact_size off;
        autoindex_localtime on;
    }

    # Proxy API requests
    location /api/ {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Health check
    location /healthz {
        proxy_pass http://127.0.0.1:8001/healthz;
    }
}
EOF

# Enable site
ln -s /etc/nginx/sites-available/api-adjust /etc/nginx/sites-enabled/
nginx -t
systemctl reload nginx
```

## 🐳 **4. Cấu hình Docker**

### **Tạo docker-compose.yml:**

```bash
# Tạo docker-compose.yml
cat > /opt/api-adjust/docker-compose.yml << 'EOF'
version: '3.8'
services:
  api:
    image: api-adjust:latest
    container_name: api-adjust
    restart: unless-stopped
    env_file:
      - .env
    environment:
      STORAGE_ROOT: /data/rrd
    ports:
      - "8001:8001"
    volumes:
      - ./data:/data/rrd
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8001/healthz')"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s
EOF
```

## 🚀 **5. Deploy và Start**

### **Deploy application:**

```bash
# Vào thư mục project
cd /opt/api-adjust

# Pull latest image
docker pull api-adjust:latest

# Start services
docker-compose up -d

# Kiểm tra status
docker ps
docker logs api-adjust
```

## 🔍 **6. Kiểm tra cấu hình**

### **Test API endpoints:**

```bash
# Health check
curl http://192.168.210.100:8001/healthz

# Test file access
curl http://192.168.210.100:8001/files/

# Test API
curl -X POST http://192.168.210.100:8001/api/adjust-pose \
  -H "Content-Type: application/json" \
  -d '{
    "input_rel_path": "test.rrd",
    "xyz": [0.0, 0.0, 0.0],
    "rpy": [0.0, 0.0, 0.0]
  }'
```

## 📊 **7. Workflow hoạt động**

### **Quy trình xử lý:**

```
1. Web upload file RRD → Lưu vào /opt/api-adjust/data/origin/
2. Web gọi API: POST /api/adjust-pose
3. API đọc file từ origin/ theo input_rel_path
4. API xử lý file RRD
5. API lưu kết quả vào process/
6. API trả về URL của file đã xử lý
```

### **Cấu trúc thư mục:**

```
/opt/api-adjust/
├── .env                    # Environment variables
├── docker-compose.yml      # Docker configuration
├── data/                   # Data directory
│   ├── origin/            # Input RRD files
│   └── process/           # Output RRD files
└── logs/                  # Application logs
```

## 🔧 **8. Monitoring và Logs**

### **Xem logs:**

```bash
# Container logs
docker logs api-adjust

# Application logs
tail -f /opt/api-adjust/logs/app.log

# System logs
journalctl -u docker
```

### **Restart service:**

```bash
# Restart container
docker-compose restart

# Rebuild và restart
docker-compose down
docker-compose up -d --build
```

## ⚠️ **9. Troubleshooting**

### **Lỗi thường gặp:**

```bash
# Kiểm tra container status
docker ps -a

# Kiểm tra logs
docker logs api-adjust

# Kiểm tra quyền thư mục
ls -la /opt/api-adjust/data/

# Kiểm tra port
netstat -tlnp | grep :8001
```

### **Fix quyền:**

```bash
# Fix ownership
chown -R 1000:1000 /opt/api-adjust/data/

# Fix permissions
chmod -R 755 /opt/api-adjust/data/
```
