# NAS Docker deployment

This deployment exposes the Nginx web container on NAS port `8080` for initial
LAN verification. Do not create a router port-forward for this port and do not
publish API port 8001. When HTTPS public access is enabled later, bind Nginx to
`127.0.0.1:8080` and configure the NAS reverse proxy to forward the public
domain to that address.

## First deployment

1. Copy the repository (including `docker-compose.yml` and `deploy/`) to
   `\\albert-nas\Docker\Benchshop`.
2. Create `deploy/.env` by copying `deploy/.env.example`. Set
   `BOTEN_CORS_ORIGINS` to the exact public `https://` site origin, and set
   `BOTEN_DATA_DIR` to an absolute NAS directory if preferred.
3. Create the persistent data directory and copy the current database and
   uploaded catalog images into it:

   ```text
   <BOTEN_DATA_DIR>/boten.db
   <BOTEN_DATA_DIR>/uploads/catalog/
   ```

4. From the repository directory, run:

   ```sh
   docker compose up -d --build
   docker compose ps
   ```

The API container automatically applies Alembic migrations before starting.

## NAS reverse proxy

Point the existing HTTPS virtual host for the final domain to:

```text
http://127.0.0.1:8080
```

Enable WebSocket support if the NAS interface presents that option. Preserve the
`Host` and `X-Forwarded-*` headers. Do not add a separate `/api` route: Nginx in
this compose stack already proxies it internally.

## Operations

```sh
docker compose logs -f api
docker compose pull
docker compose up -d --build
docker compose exec api python -m backend.database_maintenance check
docker compose exec api python -m backend.database_maintenance backup --output-dir /data/backups --keep 30
docker compose exec api python -m backend.cleanup
```

Schedule the last two commands daily in NAS Task Scheduler. Back up the complete
data directory to a separate NAS volume or offsite location. Before upgrades,
create and verify a database backup; rollback is performed by restoring the
backup into `/data/boten.db` with the stack stopped.
