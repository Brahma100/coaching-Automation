# Production Deployment (Ubuntu)

This guide upgrades the app to a production-grade deployment with Gunicorn + Uvicorn, systemd services, Cloudflare Tunnel, static React build, healthchecks, and SQLite backups.

## 1) Server prerequisites
1. Install system packages:
```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip sqlite3 nodejs npm
```
2. Create a dedicated user:
```bash
sudo useradd -m -s /bin/bash coachapp
```
3. Create app directory and set ownership:
```bash
sudo mkdir -p /opt/coaching_automation
sudo chown -R coachapp:coachapp /opt/coaching_automation
```

## 2) App installation
1. Copy repo into `/opt/coaching_automation` (as `coachapp`).
2. Create Python venv and install deps:
```bash
cd /opt/coaching_automation
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```
3. Build frontend:
```bash
cd /opt/coaching_automation/frontend
npm ci
npm run build
```
4. Ensure migrations are applied:
```bash
cd /opt/coaching_automation
. .venv/bin/activate
alembic upgrade head
```

## 3) Environment variables
1. Copy `.env.production.example` to `.env`:
```bash
cp /opt/coaching_automation/.env.production.example /opt/coaching_automation/.env
```
2. Update:
   - `APP_BASE_URL`
   - `FRONTEND_BASE_URL`
   - `TELEGRAM_BOT_TOKEN`
   - `AUTH_SECRET`

## 4) Gunicorn config
Use `deploy/gunicorn.conf.py`:
```text
bind = 127.0.0.1:8000
workers = (CPU * 2) + 1
worker_class = uvicorn.workers.UvicornWorker
timeout = 60
```

## 5) systemd service (backend)
1. Copy:
```bash
sudo cp /opt/coaching_automation/deploy/coaching-app.service /etc/systemd/system/coaching-app.service
```
2. Enable + start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable coaching-app
sudo systemctl start coaching-app
```

## 6) cloudflared tunnel
1. Install cloudflared:
```bash
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb -o /tmp/cloudflared.deb
sudo dpkg -i /tmp/cloudflared.deb
```
2. Create tunnel & credentials (Cloudflare docs).
3. Copy config:
```bash
sudo mkdir -p /etc/cloudflared
sudo cp /opt/coaching_automation/deploy/cloudflared/config.yml /etc/cloudflared/config.yml
sudo chown -R cloudflared:cloudflared /etc/cloudflared
```
4. Install systemd service:
```bash
sudo cp /opt/coaching_automation/deploy/cloudflared.service /etc/systemd/system/cloudflared.service
sudo systemctl daemon-reload
sudo systemctl enable cloudflared
sudo systemctl start cloudflared
```

## 7) Healthcheck
Endpoint:
```text
GET /health -> {"status":"ok"}
```
Local check:
```bash
curl -s http://127.0.0.1:8000/health
```

## 8) Logging
Journald:
```bash
sudo journalctl -u coaching-app -f
sudo journalctl -u cloudflared -f
```
Optional journald tuning:
```bash
sudo mkdir -p /etc/systemd/journald.conf.d
printf "[Journal]\nSystemMaxUse=500M\nSystemMaxFileSize=50M\n" | sudo tee /etc/systemd/journald.conf.d/size.conf
sudo systemctl restart systemd-journald
```

Optional logrotate for backup logs:
```bash
sudo tee /etc/logrotate.d/coaching-backup <<'EOF'
/var/log/coaching_automation_backup.log {
  daily
  rotate 14
  compress
  missingok
  notifempty
  copytruncate
}
EOF
```

## 9) SQLite backups
1. Install the backup script:
```bash
sudo cp /opt/coaching_automation/deploy/backup_sqlite.sh /usr/local/bin/backup_coaching_db.sh
sudo chmod +x /usr/local/bin/backup_coaching_db.sh
```
2. Add cron (daily at 02:00):
```bash
sudo crontab -e
```
Add:
```text
0 2 * * * /usr/local/bin/backup_coaching_db.sh >> /var/log/coaching_automation_backup.log 2>&1
```
Backups go to:
```text
/var/backups/coaching_automation
```

## 10) Nginx (optional)
If you prefer Nginx in front of Gunicorn:
```bash
sudo apt install -y nginx
sudo cp /opt/coaching_automation/deploy/nginx.conf /etc/nginx/sites-available/coaching_automation
sudo ln -s /etc/nginx/sites-available/coaching_automation /etc/nginx/sites-enabled/coaching_automation
sudo nginx -t
sudo systemctl restart nginx
```

## 11) Start/stop commands
```bash
sudo systemctl start coaching-app
sudo systemctl stop coaching-app
sudo systemctl restart coaching-app
sudo systemctl status coaching-app
```

## 12) React static serving
`frontend/dist` is served directly by FastAPI at `/` (SPA fallback enabled). Rebuild after frontend changes:
```bash
cd /opt/coaching_automation/frontend
npm run build
sudo systemctl restart coaching-app
```
