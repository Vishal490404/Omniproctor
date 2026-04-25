# Deploying OmniProctor WebClient to an Azure VM

End-to-end recipe for hosting the API + SPA + Postgres on a single Linux Azure
VM using Docker Compose. Tested against Ubuntu 22.04 LTS but any Docker-capable
distro works.

---

## 1. Provision the VM

| Setting          | Recommended                                            |
| ---------------- | ------------------------------------------------------ |
| Image            | Ubuntu Server 22.04 LTS - x64                          |
| Size             | `Standard_B2s` (2 vCPU / 4 GB RAM) for ≤ ~50 students. Bump to `Standard_D2s_v5` for larger cohorts. |
| Disk             | 64 GB Premium SSD                                      |
| Auth             | SSH public key                                         |
| Inbound ports    | SSH (22), HTTP (80), HTTPS (443), and **8001** (kiosk → API) |
| Public IP        | Static, with a DNS name (`omniproctor.example.com`)    |

Open the right NSG rules from the portal, or via CLI:

```bash
az network nsg rule create -g <rg> --nsg-name <nsg> --name HTTP    --priority 1001 --access Allow --protocol Tcp --destination-port-ranges 80
az network nsg rule create -g <rg> --nsg-name <nsg> --name HTTPS   --priority 1002 --access Allow --protocol Tcp --destination-port-ranges 443
az network nsg rule create -g <rg> --nsg-name <nsg> --name KioskAPI --priority 1003 --access Allow --protocol Tcp --destination-port-ranges 8001
```

> **Why expose 8001?** The kiosk (running on the student's PC) talks to the
> FastAPI backend directly using the `apiBase` baked into the
> `omniproctor-browser://` launch link. If you put the API behind a reverse
> proxy on 443, set `API_BASE_URL=https://omniproctor.example.com/api/v1`
> instead and skip rule 1003.

---

## 2. Bootstrap Docker on the VM

```bash
ssh azureuser@<vm-public-ip>

# Install Docker Engine + Compose v2
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg git
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
    sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
    https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | \
    sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Run docker without sudo (logout/login after)
sudo usermod -aG docker $USER
```

---

## 3. Pull the source and configure

```bash
cd /opt
sudo git clone https://github.com/<your-org>/Omniproctor.git
sudo chown -R $USER:$USER Omniproctor
cd Omniproctor/WebClient

cp .env.example .env
nano .env
```

Set these values in `.env` (the prod compose file refuses to start without them):

```ini
# What students' PCs will hit. Use https + your DNS once TLS is wired up.
API_BASE_URL=http://<vm-public-ip>:8001/api/v1

# Long random string. Generate one with: openssl rand -hex 32
SECRET_KEY=...

# Rotate from the dev default
POSTGRES_PASSWORD=...

# Lock CORS down to the SPA host once you have a DNS name
CORS_ORIGINS=["http://<vm-public-ip>","https://omniproctor.example.com"]
```

---

## 4. Bring the stack up

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

Verify:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
curl -fsS http://localhost/healthz                  # frontend
curl -fsS http://localhost:8001/health              # API
curl -fsS http://localhost/config.js                # confirms API_BASE_URL was injected
```

Then hit `http://<vm-public-ip>/` from a browser and log in.

---

## 5. (Recommended) Terminate TLS in front of the stack

The simplest path is **Caddy** running as a fourth container. Drop this
fragment into a `docker-compose.tls.yml` file alongside the others:

```yaml
services:
  caddy:
    image: caddy:2
    restart: always
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - caddy_data:/data
      - caddy_config:/config
    depends_on:
      - webclient-frontend
      - webclient-api
volumes:
  caddy_data:
  caddy_config:
```

`Caddyfile`:

```Caddyfile
omniproctor.example.com {
    reverse_proxy /api/* webclient-api:8000
    reverse_proxy /*     webclient-frontend:80
}
```

Then re-up with all three files and remove the public 80/8001 mappings on the
other services to make Caddy the only ingress:

```bash
docker compose -f docker-compose.yml \
               -f docker-compose.prod.yml \
               -f docker-compose.tls.yml up -d
```

Update `.env` so `API_BASE_URL=https://omniproctor.example.com/api/v1` and
`docker compose restart webclient-frontend` to push the change.

---

## 6. Day-2 operations

| Task                    | Command                                                                                                  |
| ----------------------- | -------------------------------------------------------------------------------------------------------- |
| View logs               | `docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f --tail=200`                     |
| Restart frontend only   | `docker compose -f docker-compose.yml -f docker-compose.prod.yml restart webclient-frontend`             |
| Apply code update       | `git pull && docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build`              |
| Switch API URL          | edit `.env` → `docker compose -f docker-compose.yml -f docker-compose.prod.yml restart webclient-frontend` |
| Postgres backup         | `docker compose exec db pg_dump -U omniproctor omniproctor > backup-$(date +%F).sql`                     |
| Postgres restore        | `cat backup.sql \| docker compose exec -T db psql -U omniproctor omniproctor`                            |
| Drop & rebuild DB       | `docker compose down -v && docker compose -f ... up -d`                                                  |

---

## 7. Drop in the kiosk installer

After running PyInstaller + Inno Setup (see `Browser/OmniProctorBrowser.iss`),
copy `OmniProctorSetup-<version>.exe` to the VM as
`WebClient/installers/OmniProctorKioskSetup.exe` (note the *renamed* file).
Students will then download it from the dashboard (which calls
`GET /api/v1/downloads/installer/windows`).

```bash
scp OmniProctorSetup-0.1.0.exe azureuser@<vm>:/opt/Omniproctor/WebClient/installers/OmniProctorKioskSetup.exe
```

No restart needed - the directory is bind-mounted read-only into the API
container.

---

## 8. Troubleshooting

| Symptom                                                     | Cause / fix                                                                                  |
| ----------------------------------------------------------- | -------------------------------------------------------------------------------------------- |
| Frontend loads, but every API call is `Network Error`       | `/config.js` returned an empty `API_BASE_URL`. Check `.env` and `docker compose logs webclient-frontend`. |
| Kiosk launches but never sends telemetry                    | The embedded `apiBase` in the launch link is unreachable from the student's PC. Confirm port 8001 is open in the NSG, or move to HTTPS via Caddy. |
| `POSTGRES_PASSWORD must be set in .env`                     | You skipped step 3. Edit `.env` and re-run the `up -d` command.                              |
| `502 Bad Gateway` from Caddy after rotating images          | One service is still rebuilding. `docker compose ps` will show its health.                   |
| Disk filling up                                             | Container logs - the prod compose caps each at 50 MB. Old image layers: `docker system prune -af`. |
