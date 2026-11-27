# Deployment Backend CrowdCast

Arsitektur produksi memisahkan **edge** dan **cloud**:

```
Laptop/edge (GPU)                        Cloud (Azure)
+------------------------+   HTTPS      +---------------------------------+
| python -m app.worker   | -----------> | Caddy (443, TLS otomatis)       |
| YOLO + forecast        |  X-Worker-Key|   -> API FastAPI (1 proses)     |
| video/RTSP lokal       |              |   -> PostgreSQL                 |
+------------------------+              +---------------------------------+
                                                   ^ HTTPS (REST, SSE, MJPEG)
                                         Dashboard Next.js (di-deploy tim FE)
```

Worker tetap berjalan dekat sumber video karena butuh GPU. Worker hanya membutuhkan URL API dan `WORKER_API_KEY`, tidak pernah memegang kredensial database. Image API tidak memuat PyTorch atau OpenCV (sekitar 200 MB).

API wajib berjalan sebagai **satu proses dan satu replika**: status live, frame video, dan event SSE disimpan di memori proses.

## Opsi A: Satu VM dengan Docker Compose

Cocok untuk VM Azure atau VM lain dengan Docker. Stack: PostgreSQL 17, API, dan Caddy yang mengurus sertifikat HTTPS.

1. Siapkan VM Linux dengan Docker Engine dan plugin Compose. Buka port 80 dan 443 di firewall/NSG. Arahkan DNS `API_DOMAIN` ke IP publik VM.
2. Clone repository, lalu dari folder `deploy/`:

   ```sh
   cp .env.example .env
   python3 -c "import secrets; print(secrets.token_hex(32))"   # ulangi untuk tiap secret
   nano .env
   docker compose up -d --build
   ```

3. Container API menjalankan `alembic upgrade head` setiap start (matikan dengan `MIGRATE_ON_START=false`). Buat administrator pertama:

   ```sh
   docker compose exec api python -m app.scripts.seed --admin-only
   ```

4. Periksa `https://<API_DOMAIN>/health/ready` dan `https://<API_DOMAIN>/docs`.
5. Daftarkan kamera lewat Swagger (`POST /api/v1/cameras`, ROI berupa list titik 0..1). Untuk mengisi riwayat awal dari CSV:

   ```sh
   docker compose cp ../backend/experiments/outputs/phase3/kabukicho_minutes.csv api:/tmp/minutes.csv
   docker compose exec api python -m app.scripts.backfill_records --camera CAM-02 --csv /tmp/minutes.csv
   ```

   File CSV ada di laptop yang menjalankan eksperimen; salin ke VM lebih dulu bila belum ada.

Hapus prediksi lebih dari 30 hari setiap malam lewat cron di VM (`crontab -e`):

```
30 2 * * * cd /path/to/CrowdCast/deploy && docker compose exec -T api python -m app.scripts.prune --days 30
```

Log API: `docker compose logs -f api`. Setiap baris memuat `rid=<request id>` yang sama dengan header `X-Request-ID` dan field `request_id` pada error 500.

Update versi: `git pull` lalu `docker compose up -d --build`. Backup database:

```sh
docker compose exec db pg_dump -U crowdcast crowdcast > backup-$(date +%F).sql
```

## Opsi B: Azure Container Apps dan Azure Database for PostgreSQL

Bila departemen memberi akses PaaS:

1. **Database**: buat Azure Database for PostgreSQL Flexible Server (versi 17 atau 16), database `crowdcast`. Izinkan akses dari Container Apps. URL wajib memakai TLS:

   ```
   postgresql+asyncpg://<user>:<password>@<server>.postgres.database.azure.com:5432/crowdcast?ssl=require
   ```

2. **Image**: dari root repository, build dan simpan ke Azure Container Registry:

   ```sh
   az acr build --registry <acr> --image crowdcast-api:<versi> backend
   ```

3. **Container App**: image dari ACR, ingress eksternal ke port 8000, **min dan max replica 1**. Isi environment variable (gunakan *secrets* untuk nilai rahasia): `DATABASE_URL`, `SECRET_KEY`, `WORKER_API_KEY`, `BACKEND_CORS_ORIGINS`, `FIRST_SUPERUSER_EMAIL`, `FIRST_SUPERUSER_PASSWORD`, `FORWARDED_ALLOW_IPS=*`. HTTPS disediakan Azure, jadi Caddy tidak dipakai.
4. Buat admin pertama lewat console container: `python -m app.scripts.seed --admin-only`.

Azure App Service for Containers juga bisa dipakai dengan langkah serupa (`WEBSITES_PORT=8000`, satu instance, Always On aktif).

## Menjalankan worker ke API cloud

Di laptop, `backend/.env` cukup berisi `WORKER_API_KEY` yang sama dengan server:

```powershell
.\.venv\Scripts\python.exe -m app.worker --camera CAM-02 --api https://<API_DOMAIN>
```

Atau isi `WORKER_API_URL=https://<API_DOMAIN>` di `backend/.env`. Kamera harus sudah terdaftar di database cloud, dan `source` kamera menunjuk ke path video di laptop (atau pakai `--source`).

## Catatan

- Stream MJPEG mengirim sekitar 10 frame per detik dari laptop ke cloud lalu ke setiap penonton. Bila bandwidth upload terbatas, turunkan `--stream-fps` di worker.
- Event SSE mengirim heartbeat tiap 15 detik agar koneksi tidak diputus proxy. Bila platform tetap memutus koneksi panjang, frontend membuka ulang `EventSource` dengan tiket baru.
- Status live hilang saat API restart dan kembali begitu worker mengirim data lagi. Riwayat, prediksi, dan alert tersimpan di PostgreSQL.
