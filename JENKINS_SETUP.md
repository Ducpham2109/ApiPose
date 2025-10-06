# Hướng dẫn tạo Jenkins Pipeline Job

## Bước 1: Tạo Pipeline Job

1. **Vào Jenkins Dashboard**
2. **Click "New Item"**
3. **Nhập tên**: `api-adjust`
4. **Chọn "Pipeline"**
5. **Click "OK"**

## Bước 2: Cấu hình General Tab

### Description:
- Nhập mô tả: `API Adjust - FastAPI application deployment`

### Build Options:
- ✅ **Discard old builds**: Keep only the last 10 builds
- ✅ **Do not allow concurrent builds**: Để tránh conflict

### GitHub Connection:
- **GitHub project**: `https://github.com/Ducpham2109/api-adjust` (nếu có)

### Advanced Project Options:
- **This project is parameterized**: ✅ (để có thể chọn deploy gì)

## Bước 3: Cấu hình Pipeline Tab

### Pipeline Definition:
- **Definition**: **Pipeline script from SCM** (không phải Pipeline script)
- **SCM**: Git
- **Repository URL**: `https://github.com/Ducpham2109/api-adjust.git`
- **Credentials**: `github-token` (credential bạn đã tạo)
- **Branch Specifier**: `*/main`
- **Script Path**: `Jenkinsfile`

### Build Triggers:
- ✅ **Poll SCM**: `H/5 * * * *` (check mỗi 5 phút)
- Hoặc ✅ **GitHub hook trigger for GITScm polling** (nếu có webhook)

## Bước 4: Lưu và Test

1. **Click "Save"**
2. **Click "Build Now"** để test pipeline
3. **Xem build logs** để kiểm tra

## Bước 5: Kiểm tra kết quả

```bash
# Kiểm tra trên server
ssh root@192.168.210.100 "docker ps"
ssh root@192.168.210.100 "curl http://localhost:8000/healthz"
ssh root@192.168.210.100 "curl http://localhost:8083"
```
