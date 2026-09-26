# Deploying RoomMate Bot to a VPS

This guide sets up a fresh **Ubuntu 24.04** server so that the bot runs 24/7 in Docker, with
PostgreSQL, the Mini App over HTTPS, daily backups and a hardened SSH. It needs about 1 vCPU,
1.5 GB of RAM and 10 GB of disk.

```
┌──────────────── VPS (ufw: 22, 80, 443) ────────────────┐
│  docker compose -f docker-compose.prod.yml             │
│   ├─ bot       long polling → api.telegram.org        │
│   ├─ postgres  volume "postgres-data", no open port   │
│   ├─ webapp    FastAPI + React build, internal :8000  │
│   └─ caddy     :80/:443, HTTPS → webapp               │
│  cron 03:30 → scripts/backup_db.sh → backups/*.dump   │
└────────────────────────────────────────────────────────┘
```

The bot uses **long polling**, so the bot itself needs no open port. The Mini App needs HTTPS
(a Telegram requirement): Caddy gets a free Let's Encrypt certificate for `WEBAPP_DOMAIN`. With
no domain of your own, [sslip.io](https://sslip.io) works: `194-62-105-206.sslip.io` resolves to
`194.62.105.206`. Only one instance may run per bot token: stop any local copy before starting
the server one.

Commands marked `local$` run on your computer. `server$` means the server, as the `deploy` user.

## 1. Prepare the server (once)

Before you start, you should be able to log in with an SSH key: `local$ ssh root@SERVER_IP`.

### 1.1 Create an admin user and harden SSH

```bash
local$ ssh root@SERVER_IP

# A key-only user with sudo. It has no password, so sudo must not ask for one.
adduser --disabled-password --gecos "" deploy
usermod -aG sudo deploy
install -d -m 700 -o deploy -g deploy /home/deploy/.ssh
install -m 600 -o deploy -g deploy /root/.ssh/authorized_keys /home/deploy/.ssh/authorized_keys
echo "deploy ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/90-deploy && chmod 440 /etc/sudoers.d/90-deploy
visudo -c
```

**Stop here and check from a second terminal** that `local$ ssh deploy@SERVER_IP 'sudo -n true && echo ok'`
prints `ok`. Only then disable password and root logins. Keep the root session open until the
last check passes: if something goes wrong, you can still fix it from there.

```bash
cat > /etc/ssh/sshd_config.d/00-hardening.conf <<'EOF'
# Key-only SSH access, no direct root login.
# Sorted first on purpose: sshd uses the first value it finds for each option,
# and cloud images ship 50-cloud-init.conf with "PasswordAuthentication yes".
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin no
PubkeyAuthentication yes
PermitEmptyPasswords no
EOF
sshd -t && sshd -T | grep -Ei '^(passwordauthentication|permitrootlogin) '
systemctl restart ssh
```

Check again from a new terminal:

```bash
local$ ssh deploy@SERVER_IP true && echo "deploy: ok"
local$ ssh root@SERVER_IP true   # must fail: Permission denied (publickey)
```

From now on log in as `deploy` and use `sudo`.

### 1.2 Firewall, fail2ban, automatic security updates

```bash
local$ ssh deploy@SERVER_IP

sudo apt-get update && sudo apt-get -y upgrade
sudo apt-get install -y ufw fail2ban python3-systemd unattended-upgrades

# ufw: only SSH (rate limited), HTTP and HTTPS. Allow SSH before enabling!
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw limit 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw --force enable

# fail2ban: ban an IP for 1 hour after 5 failed SSH logins within 10 minutes.
sudo tee /etc/fail2ban/jail.d/sshd.local >/dev/null <<'EOF'
[sshd]
enabled  = true
backend  = systemd
port     = ssh
maxretry = 5
findtime = 10m
bantime  = 1h
EOF
sudo systemctl enable --now fail2ban && sudo systemctl restart fail2ban

# Daily security updates (the Ubuntu default origin list includes only -security).
sudo tee /etc/apt/apt.conf.d/20auto-upgrades >/dev/null <<'EOF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
APT::Periodic::AutocleanInterval "7";
EOF
```

> ⚠️ Docker publishes container ports **around** ufw (it writes its own iptables rules). This
> is why `docker-compose.prod.yml` publishes no ports except Caddy's 80/443. Never add
> `ports:` to the `postgres` service.

### 1.3 Docker

Use the official Docker repository (not the snap):

```bash
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Rotate container logs globally: 10 MB × 3 files per container.
echo '{"log-driver": "json-file", "log-opts": {"max-size": "10m", "max-file": "3"}}' \
  | sudo tee /etc/docker/daemon.json >/dev/null
sudo systemctl restart docker
sudo usermod -aG docker deploy   # log out and in again to use docker without sudo
```

If `/var/run/reboot-required` exists after the upgrade, run `sudo reboot`.

## 2. First deployment

```bash
local$ ssh deploy@SERVER_IP

sudo install -d -o deploy -g deploy /opt/roommate-bot
git clone https://github.com/Xaveron/roommate-bot.git /opt/roommate-bot
cd /opt/roommate-bot

cp .env.example .env
chmod 600 .env
sed -i "s/^POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=$(openssl rand -hex 24)/" .env
sed -i "s/^WEBAPP_DOMAIN=.*/WEBAPP_DOMAIN=$(curl -s https://api.ipify.org | tr . -).sslip.io/" .env
nano .env        # set BOT_TOKEN (from @BotFather), ADMIN_IDS if you like
```

Start the stack. The first build takes a few minutes, and database migrations run
automatically on start:

```bash
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs -f bot     # Ctrl+C to stop watching
```

A healthy start ends with `Starting @your_bot_username`. Check the Mini App too. The first
start of Caddy needs a few seconds to get the certificate:

```bash
curl -s https://$(grep ^WEBAPP_DOMAIN= .env | cut -d= -f2)/api/health    # {"status":"ok"}
docker compose -f docker-compose.prod.yml logs caddy | grep -i certificate
```

In Telegram, the private chat with the bot now has a **📱 App** button next to the message field.

Then enable the daily backup:

```bash
sudo install -m 644 deploy/roommate-backup.cron /etc/cron.d/roommate-backup
scripts/backup_db.sh      # the first backup, right now
```

Tip: add `alias dc='docker compose -f /opt/roommate-bot/docker-compose.prod.yml'` to
`~/.bashrc` to shorten the commands below.

## 3. Everyday operations

| Task | Command (in `/opt/roommate-bot`) |
|---|---|
| Status | `docker compose -f docker-compose.prod.yml ps` |
| Follow bot logs | `docker compose -f docker-compose.prod.yml logs -f bot` |
| Last hour of logs | `docker compose -f docker-compose.prod.yml logs --since 1h bot` |
| Restart the bot | `docker compose -f docker-compose.prod.yml restart bot` |
| Stop everything | `docker compose -f docker-compose.prod.yml down` (data stays in the volume) |
| SQL console | `docker compose -f docker-compose.prod.yml exec postgres psql -U roommate roommate` |
| Disk usage | `docker system df`, `df -h /` |
| Banned IPs | `sudo fail2ban-client status sshd` |

Logs are rotated by Docker: at most 5 × 10 MB per container.

## 4. Updating

```bash
cd /opt/roommate-bot
scripts/backup_db.sh                                   # always back up before an update
git pull
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml logs --since 5m bot
docker image prune -f                                  # drop old image layers
```

New migrations run automatically when the bot starts. If an update goes wrong, check out the
previous commit and rebuild: `git checkout <commit> && docker compose -f docker-compose.prod.yml up -d --build`.
If that update had already changed the database schema, also restore the backup you took
before it (next section).

## 5. Backups and restore

`scripts/backup_db.sh` writes a compressed `pg_dump` (custom format) to `backups/` and keeps
the newest 14. Cron runs it daily at 03:30 server time (usually UTC, check with `timedatectl`)
and logs to `backups/backup.log`. To run it at another time, edit `/etc/cron.d/roommate-backup`.
Every dump is read back with `pg_restore --list` before it counts as done.

```bash
ls -lh backups/                                  # available dumps
KEEP=30 scripts/backup_db.sh                     # a manual dump, keep 30 this time
tail backups/backup.log                          # cron history
```

**Keep a copy off the server** too. The VPS disk is a single point of failure:

```bash
local$ rsync -av deploy@SERVER_IP:/opt/roommate-bot/backups/ ~/roommate-backups/
```

**Restore.** The script asks for confirmation, first takes a safety dump of the current
state, stops the bot, restores and starts the bot again:

```bash
scripts/restore_db.sh backups/roommate-20260926-033000.dump
```

To move to a new server, set it up with sections 1–2, copy a dump into its `backups/` and run
`scripts/restore_db.sh` there. Then stop the old server so only one bot polls Telegram.

## 6. Troubleshooting

| Symptom in the logs | Cause and fix |
|---|---|
| `Telegram rejected BOT_TOKEN` | Wrong token in `.env`. Fix it, then `docker compose -f docker-compose.prod.yml up -d` |
| `TelegramConflictError: terminated by other getUpdates request` | Another copy of the bot runs with the same token (e.g. on a laptop). Stop it |
| `set POSTGRES_PASSWORD in .env` | The variable is empty. Generate it as in section 2 **before** the first start: the database keeps the password it was created with |
| Bot restarts in a loop | `docker compose -f docker-compose.prod.yml logs --tail 50 bot` shows the reason |
| Caddy: `challenge failed` / no certificate | Ports 80 and 443 must be reachable from the internet (ufw, provider firewall), and `WEBAPP_DOMAIN` must resolve to this server. Don't delete the `caddy-data` volume: Let's Encrypt limits how often certificates are issued |
| Mini App says "session expired" | Telegram's `initData` is older than `WEBAPP_INITDATA_MAX_AGE` (24 h). Reopen the app |
| No reminders at the expected time | Check the room timezone and quiet hours in `/settings`. The server clock doesn't matter, rooms use their own timezone |
