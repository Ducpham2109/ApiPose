# Huong dan Trien khai API Adjust bang Jenkins + Docker Compose

Tai lieu nay mo ta toan bo quy trinh tu luc Jenkins lay source code, build image, deploy container cho den khi Nginx reverse proxy phuc vu duong dan `/opt/rerun/public/uploads`.

## 1. Kien truc tong quat
- Jenkins chay pipeline tu repo nay (su dung Jenkinsfile o thu muc goc).
- Pipeline build Docker image, chay smoke test, sau do goi `docker compose` de khoi dong ca backend FastAPI (`api`) va reverse proxy (`nginx`).
- Tat ca file RRD duoc luu o thu muc `/opt/rerun/public/uploads` tren may chu va duoc mount vao ca hai container o che do read/write (api) va read-only (nginx).

## 2. Chuan bi may chu Jenkins (192.168.210.100)
1. Cai dat Docker Engine + Docker Compose v2 (`docker compose`).
2. Them user `jenkins` vao group `docker`, dang xuat/dang nhap lai de nhan quyen.
3. Cai dat Git de Jenkins co the clone repository.
4. Tao va cap quyen thu muc du lieu:
   ```bash
   sudo mkdir -p /opt/rerun/public/uploads
   sudo chown jenkins:jenkins /opt/rerun/public/uploads
   ```
5. Neu server dang chay Nginx tren host, hay giai phong cong 80 hoac sua gia tri bien `NGINX_PORT` trong compose (mac dinh 8083).
6. Chu an file `.env` production va tao Jenkins credential nhu muc 3.3.

## 3. Tao job Jenkins
### 3.1 Pipeline script from SCM
- Jenkins ? New Item ? Pipeline ? dat ten (vi du `api-adjust`).
- Definition: `Pipeline script from SCM`.
- SCM: `Git`, nhap repository URL va credential neu can.
- Branches to build: `*/main` (hoac nhanh tuong ung).
- Script Path: `Jenkinsfile`.
- Agent: chi dinh node co Docker neu muon.

> Stage `Checkout` trong Jenkinsfile da goi `checkout scm`, vi vay khong can script thu cong de lay source.

### 3.2 Credential khac (neu can)
- Pipeline hien chi build/deploy noi bo, chua push registry. Neu muon push, them credential rieng va mo rong Jenkinsfile sau.

### 3.3 Credential file `.env`
- Tao credential kieu **Secret file** voi ID `api-adjust-env`.
- Noi dung toi thieu:
  ```env
  STORAGE_ROOT=/opt/rerun/public/uploads
  NGINX_INPUT_BASE_URL=http://<ten-may-hoac-ip>:8083/opt/rerun/public/uploads
  ```
- Khi pipeline chay, neu workspace chua co `.env` se tu dong copy tu credential nay.

## 4. Luong pipeline trong Jenkinsfile
Cac stage chinh:
1. **Checkout**: lay code tu Git.
2. **Prepare environment file**: tao `.env` tu credential neu chua co.
3. **Build image**: build Docker image, tag `api-adjust:build-${BUILD_NUMBER}` va mot tag `latest` tam thoi.
4. **Smoke test image**: chay container tam, goi `python -m compileall` de dam bao cac module load duoc.
5. **Deploy**:
   - Export cac bien `API_ADJUST_IMAGE`, `DATA_DIR`, `STORAGE_ROOT`, `NGINX_PORT` (mac dinh `8083`).
   - Tao thu muc du lieu neu chua ton tai.
   - Chay `docker compose -p api-adjust -f jenkins/docker-compose.deploy.yml up -d --remove-orphans --force-recreate`.

`post` block luon don thu muc tam va in log `api-adjust` neu stage that bai.

## 5. docker-compose.deploy.yml
- Dinh nghia 2 service:
  - **api**: chay image vua build, mount `/opt/rerun/public/uploads` vao `/data/rrd`, expose cong `8000`, co healthcheck `/healthz`.
  - **nginx**: image `nginx:1.25-alpine`, phu thuoc service `api` o trang thai healthy, publish `${NGINX_PORT:-8083}:80`, mount thu muc du lieu read-only va file cau hinh `./nginx/api-adjust.conf` vao thu muc config mac dinh.
- Chi so `depends_on` dam bao nginx chi khoi dong khi backend san sang.

## 6. FastAPI health endpoint
- File `api_server.py` co endpoint moi `GET /healthz` tra ve `{"status": "ok"}` cho Docker va Nginx kiem tra suc khoe.

## 7. Cau hinh Nginx trong Docker
- Mau cau hinh nam o `jenkins/nginx/api-adjust.conf` va duoc mount vao container.
- `location /opt/rerun/public/uploads/` su dung `alias /opt/rerun/public/uploads/` (da mount tu host) de phuc vu file t?nh.
- `location /opt/rerun/public/uploads/api/` reverse proxy toi backend thong qua ten service `api:8000`.
- `location = /opt/rerun/public/uploads/healthz` goi thang vao endpoint health cua backend.
- Muon doi cong ben ngoai, thay doi bien `NGINX_PORT` truoc khi goi docker compose (vi du 80 neu host khong chay Nginx khac).
- Neu can HTTPS, co the
  1. Mo rong image Nginx de cai certbot.
  2. Hoac dat mot reverse proxy/ingress HTTPS khac ben ngoai.

## 8. Kiem tra sau khi pipeline hoan tat
- `docker ps` kiem tra `api-adjust` (FastAPI) va `api-adjust-nginx` dang chay, trang thai healthy.
- `curl http://127.0.0.1:8000/healthz` (tu server) de xac nhan backend.
- `curl http://<domain-hoac-ip>:8083/opt/rerun/public/uploads/healthz` de xac nhan Nginx.
- Gui thu request POST toi `http://<domain-hoac-ip>:8083/opt/rerun/public/uploads/api/adjust-pose` voi payload mau de dam bao pipeline hoan chinh.

## 9. Cap nhat client/test
- Neu su dung `test_api.py`, sua bien `url` thanh `http://<domain-hoac-ip>:8083/opt/rerun/public/uploads/api/adjust-pose` (hoac link HTTPS neu ban dat them TLS).

## 10. Ghi chu van hanh
- Anh Docker se tang theo tung `BUILD_NUMBER`; dung `docker image prune` dinh ky de don dep.
- Xem log nhanh: `docker logs api-adjust` hoac `docker logs api-adjust-nginx`.
- Thu muc `/opt/rerun/public/uploads` nam tren host; can sao luu dinh ky theo yeu cau.
