# GitHub Actions Development Deployment

The deployment workflow builds immutable API and web images, publishes them to
GitHub Container Registry (GHCR), copies the Compose deployment descriptors to
the server, applies Alembic migrations, and waits for the API readiness check.

It deploys automatically after the `CI` workflow succeeds on `main`. It can also
be started manually from the GitHub Actions page. Runtime credentials remain in
the server-side `.env` file and are not copied through GitHub Actions.

## Server prerequisites

The deployment user must be able to run Docker without `sudo`. The server must
already have:

- Docker Engine, the Docker Compose plugin, `curl`, and an SSH server.
- `/opt/edu-dawnsynch/.env` populated from `.env.example` and mode `600`.
- The external Docker networks `enterprise-review-net` and `ai-network`.
- PostgreSQL, Redis, Qdrant, and LiteLLM attached to those networks using the
  names or aliases documented in the project README.
- Outbound HTTPS access to `ghcr.io` so the workflow can authenticate and pull
  this repository's private packages.

Create the deployment directory and grant it to the deployment user:

```bash
sudo mkdir -p /opt/edu-dawnsynch
sudo chown deploy:deploy /opt/edu-dawnsynch
```

The workflow logs the deployment user in to GHCR over SSH using `GHCR_USERNAME`
and `GHCR_PAT`. Use a dedicated token with only the package-read access needed to
pull this repository's private images. Docker stores this login in the deployment
user's Docker configuration on the server.

## Deployment SSH key

Create a dedicated key locally, without overwriting an existing SSH key:

```bash
ssh-keygen -t ed25519 -f ./edu_dawnsynch_deploy -C edu-dawnsynch-github-actions
```

Append `edu_dawnsynch_deploy.pub` to the deployment user's
`~/.ssh/authorized_keys`. Store the private key in GitHub and remove the local
copy after verifying the deployment.

Capture and verify the server host key from a trusted network:

```bash
ssh-keyscan -H YOUR_SERVER_HOSTNAME
```

Compare the fingerprint with `ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub`
on the server before trusting it.

## GitHub environment

Create a GitHub environment named `development` and add these environment
secrets:

| Secret | Value |
| --- | --- |
| `VM_HOST` | Server hostname or IP address |
| `VM_SSH_PORT` | SSH port; optional when using `22` |
| `VM_USER` | Dedicated non-root deployment user |
| `VM_APP_DIR` | `/opt/edu-dawnsynch` |
| `VM_SSH_KEY` | Complete private deployment key |
| `VM_KNOWN_HOSTS` | Verified `ssh-keyscan -H` output |
| `GHCR_USERNAME` | GitHub account that owns the package-read token |
| `GHCR_PAT` | Token permitted to pull the private GHCR images |

For an ARM64 server, create the repository variable
`DEPLOY_PLATFORMS=linux/arm64`. The default is `linux/amd64`. A multi-platform
value such as `linux/amd64,linux/arm64` publishes one image usable on both.

The workflow uses the built-in `GITHUB_TOKEN` to publish packages. Repository
Actions settings must permit workflow package writes. `GHCR_PAT` is used only by
the remote server to pull the resulting private images; it is not placed in the
repository's Git remote URL.

## First deployment

1. Confirm the server `.env` and shared infrastructure.
2. Confirm the deployment user can run `docker ps` and `docker compose version`.
3. Push to `main` and wait for `CI` to succeed, or run **Deploy Development**
   manually from GitHub Actions.
4. Inspect the workflow's `Deploy and verify` step.
5. Verify `https://api-dev.example.com/health/live` through the configured TLS
   reverse proxy.

The server writes `.release.env` after a successful deployment. If readiness
fails, the script restores the previous application image references. Database
migrations are not automatically downgraded, so migrations must remain backward
compatible with the immediately preceding application release.

## Manual server verification

```bash
cd /opt/edu-dawnsynch
docker compose --env-file .env -f docker-compose.yml -f docker-compose.deploy.yml ps
docker compose --env-file .env -f docker-compose.yml -f docker-compose.deploy.yml logs --tail=100
curl -fsS http://127.0.0.1:8010/health/ready
```
