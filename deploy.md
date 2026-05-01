# Deploy

## 环境变量

### 后端

- `INTERNAL_API_KEY`
  - 用于服务端 SSR 请求绕过公开 API 的限速。
  - 需要与前端服务端的 `INTERNAL_API_KEY` 保持一致。

- `ADMIN_API_KEY`
  - 用于 `/api/admin/*` 管理接口鉴权。
  - 前端 `/admin` 页面会要求手动输入这个值。

### 前端服务端

- `API_BASE_URL`
  - Next.js 服务端访问后端 API 的内部地址。
  - 例如：`http://127.0.0.1:8000`

- `NEXT_PUBLIC_API_BASE_URL`
  - 浏览器侧公开使用的后端地址。
  - 例如：`https://api.example.com`

- `INTERNAL_API_KEY`
  - Next.js SSR 请求后端时附带的隐藏 key。
  - 需要与后端 `INTERNAL_API_KEY` 完全一致。

### 可选

- `PUBLIC_API_RATE_LIMIT_PER_MINUTE`
  - 公开 GET API 的每分钟限速阈值。
  - 默认值：`60`

## 说明

- 首页 `/` 和播放页 `/play/[id]` 是 SSR，会通过前端服务端携带隐藏 `INTERNAL_API_KEY` 请求后端。
- 浏览器不会看到 SSR 使用的 `INTERNAL_API_KEY`。
- `/admin` 不走这个隐藏 key，而是使用单独的 `ADMIN_API_KEY`。

## 手动部署

### 1. 准备运行环境

- 安装 MongoDB，并确认可访问。
- 安装 Python 3.11 或更高版本。
- 安装 Node.js 20 或更高版本。
- 建议服务器上准备两个目录：
  - 项目目录：当前仓库
  - 日志目录：例如 `/var/log/spider-for-acg`

### 2. 后端部署

进入后端目录：

```bash
cd /path/to/spider-for-acg/backend
```

创建虚拟环境并安装依赖：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
```

推荐在项目根目录或 `backend/` 目录放置 `.env` 或 `.env.local`。

后端会按以下顺序自动加载：

1. 根目录 `.env`
2. 根目录 `.env.local`
3. `backend/.env`
4. `backend/.env.local`

建议使用 `backend/.env.local`。

示例：

```env
MONGODB_URI=mongodb://127.0.0.1:27017
MONGODB_DB=anime_db
MONGODB_ANIME_COLLECTION=anime
MONGODB_DOMAIN_COLLECTION=discovered_domains
INTERNAL_API_KEY=your-internal-api-key
ADMIN_API_KEY=your-admin-api-key
PUBLIC_API_RATE_LIMIT_PER_MINUTE=60
```

如果你不想使用 env 文件，也可以手动 `export`：

```bash
export MONGODB_URI='mongodb://127.0.0.1:27017'
export MONGODB_DB='anime_db'
export MONGODB_ANIME_COLLECTION='anime'
export MONGODB_DOMAIN_COLLECTION='discovered_domains'
export INTERNAL_API_KEY='your-internal-api-key'
export ADMIN_API_KEY='your-admin-api-key'
export PUBLIC_API_RATE_LIMIT_PER_MINUTE='60'
```

启动 FastAPI：

```bash
uvicorn api.app:app --host 127.0.0.1 --port 8000
```

如果要直接对公网监听：

```bash
uvicorn api.app:app --host 0.0.0.0 --port 8000
```

### 3. 爬虫与 API 配置统一

现在爬虫和 API 已统一读取同一套后端 env 配置。

关键变量：

- `MONGODB_URI`
- `MONGODB_DB`
- `MONGODB_ANIME_COLLECTION`
- `MONGODB_DOMAIN_COLLECTION`
- `INTERNAL_API_KEY`
- `ADMIN_API_KEY`
- `PUBLIC_API_RATE_LIMIT_PER_MINUTE`

因此不需要再手工同步修改 [backend/config/settings.py](/Users/quyue/www/spider-for-acg/backend/config/settings.py) 里的 Mongo 默认值，除非你想改默认回退配置。

### 4. 前端部署

进入前端目录：

```bash
cd /path/to/spider-for-acg/frontend
```

安装依赖：

```bash
npm install
```

Next.js 原生支持 `.env`、`.env.local`、`.env.production`。

建议使用 `frontend/.env.local`：

```env
API_BASE_URL=http://127.0.0.1:8000
NEXT_PUBLIC_API_BASE_URL=https://api.example.com
INTERNAL_API_KEY=your-internal-api-key
```

如果你不想使用 env 文件，也可以手动 `export`：

```bash
export API_BASE_URL='http://127.0.0.1:8000'
export NEXT_PUBLIC_API_BASE_URL='https://api.example.com'
export INTERNAL_API_KEY='your-internal-api-key'
```

构建前端：

```bash
npm run build
```

启动生产服务：

```bash
npm run start -- --hostname 127.0.0.1 --port 3000
```

如果要直接对公网监听：

```bash
npm run start -- --hostname 0.0.0.0 --port 3000
```

### 5. 反向代理

推荐使用 Nginx 或 Caddy：

- `https://your-site.example.com` -> `http://127.0.0.1:3000`
- `https://api.example.com` -> `http://127.0.0.1:8000`

这样前端和后端可以分别挂独立域名，并由反向代理处理 HTTPS。

### 6. 基本启动顺序

建议顺序：

1. 先启动 MongoDB
2. 再启动后端 API
3. 确认 `http://127.0.0.1:8000/docs` 可访问
4. 再构建并启动前端
5. 最后接入反向代理和域名

### 7. 手动验证

后端验证：

```bash
curl http://127.0.0.1:8000/
curl http://127.0.0.1:8000/api/stats
curl -H 'x-api-key: your-admin-api-key' http://127.0.0.1:8000/api/admin/overview
```

前端验证：

```bash
curl http://127.0.0.1:3000/
```

浏览器验证：

- 打开首页，确认动漫列表能显示
- 打开播放页，确认播放器和播放源能显示
- 打开 `/admin`，输入 `ADMIN_API_KEY`，确认能加载设置和爬虫源

### 8. 爬虫命令

进入后端目录：

```bash
cd /path/to/spider-for-acg/backend
source .venv/bin/activate
```

常用命令：

```bash
python run.py crawl -u 'https://www.yhdm7.net/article/lianqishiwannian.html' --max-depth 1
python run.py crawl -d 'www.yhdm7.net' --max-depth 2
python run.py incremental --limit 20 --min-hours 6
python run.py discover
python run.py full
```

### 9. 生产建议

- 后端和前端都建议交给 `systemd`、`supervisor` 或容器守护，而不是手工挂前台。
- 前端的 `INTERNAL_API_KEY` 必须与后端完全一致。
- `NEXT_PUBLIC_API_BASE_URL` 应该填浏览器真实访问到的后端地址。
- 不要把 `ADMIN_API_KEY` 暴露到前端公开环境变量。
- 如果后端部署在内网，建议让 `API_BASE_URL` 指向内网地址，以减少 SSR 请求绕路。

### 10.systemd 服务配置
[Unit]
Description=Spider for ACG Backend API
After=network.target mongod.service

[Service]
Type=simple
User=www-data
WorkingDirectory=/www/spider-for-acg/backend
EnvironmentFile=/www/spider-for-acg/backend/.env.local
ExecStart=/www/spider-for-acg/backend/.venv/bin/uvicorn api.app:app --host 0.0.0.0 --port 5001
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target

保存为 /etc/systemd/system/spider-acg-backend.service
sudo systemctl daemon-reload
sudo systemctl enable spider-acg-backend
sudo systemctl start spider-acg-backend
sudo systemctl status spider-acg-backend

更新：
cd /www/spider-for-acg
git pull

cd /www/spider-for-acg/backend
source .venv/bin/activate
pip install -r requirements.txt

sudo systemctl restart spider-acg-backend
journalctl -u spider-acg-backend -n 100 --no-pager

前端启动服务
pm2 start npm --name "spider-acg-frontend" -- start -- --hostname 0.0.0.0 --port 5002

