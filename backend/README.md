# CrowdCast Backend

API CrowdCast menggunakan **Python 3.12**, **FastAPI**, dan **SQLAlchemy async** dengan PostgreSQL. Aplikasi aktif menyediakan `GET /health` (liveness), `GET /health/ready` (readiness, memeriksa database), dan dokumentasi OpenAPI. Skema database (User, Camera, CrowdRecord, Prediction) dikelola dengan Alembic. Endpoint monitoring, prediksi, status live, dan stream video tersedia di `/api/v1`. Data asli berasal dari vision worker (`python -m app.worker`) yang mengirim hasil hitungan lewat endpoint ingest. Autentikasi pengguna belum terhubung.

## Prasyarat

- Python 3.12 dengan pip dan dukungan virtual environment.
- Docker Desktop untuk menjalankan PostgreSQL lokal melalui `docker-compose.yml` di root repository.
- Perintah berikut menggunakan PowerShell dan dimulai dari root repository. Pastikan `python --version` menunjukkan Python 3.12 sebelum membuat environment.

## Setup

1. Masuk ke folder backend:

   ```powershell
   cd backend
   ```

2. Buat virtual environment sekali untuk checkout ini:

   ```powershell
   python -m venv .venv
   ```

3. Instal dependency pengembangan dan pengujian:

   ```powershell
   .\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
   ```

Perintah menggunakan interpreter virtual environment secara langsung sehingga aktivasi PowerShell tidak diperlukan. `requirements-dev.txt` juga memasang dependency runtime dari `requirements.txt`.

## Setup AI (Opsional, untuk Eksperimen Vision)

Dependency AI dipisah dari `requirements.txt` agar CI tidak mengunduh PyTorch. Langkah ini diperlukan untuk menjalankan vision worker dan skrip di `experiments/`.

1. Pasang PyTorch versi CUDA **lebih dulu**. Ambil perintah dari [pytorch.org/get-started](https://pytorch.org/get-started/locally/) (pilih Stable, Windows, Pip, Python, versi CUDA terbaru yang tersedia), lalu jalankan dengan interpreter venv, misalnya:

   ```powershell
   .\.venv\Scripts\python.exe -m pip install torch torchvision --index-url https://download.pytorch.org/whl/<versi-cuda>
   ```

   Bila langkah ini dilewati, `ultralytics` akan menarik torch CPU-only dari PyPI.

2. Pasang dependency AI:

   ```powershell
   .\.venv\Scripts\python.exe -m pip install -r requirements-ai.txt
   ```

3. Simpan dataset dan video di `data/` (diabaikan Git), lalu periksa environment:

   ```powershell
   .\.venv\Scripts\python.exe experiments\check_env.py
   ```

Jangan commit video, dataset, atau bobot model (`*.pt`).

## Database Lokal

PostgreSQL 17 dijalankan melalui Docker dari **root repository**:

```powershell
docker compose up -d db
```

Container `crowdcast-db` membuka port host **5433** (bukan 5432) agar tidak bentrok dengan PostgreSQL native yang mungkin sudah terpasang. Saat pertama dibuat, container menyiapkan dua database: `crowdcast` untuk pengembangan dan `crowdcast_test` untuk pytest. Kredensial `crowdcast/crowdcast` hanya untuk lokal.

Hentikan dengan `docker compose stop db`. Perintah `docker compose down -v` menghapus volume beserta seluruh data lokal.

## Konfigurasi Environment

Konfigurasi dibaca oleh [`app/core/config.py`](app/core/config.py) dari environment variable dan `backend/.env`. Environment variable menang atas `.env`. Salin template hanya jika `.env` belum tersedia:

```powershell
Copy-Item .env.example .env
```

`DATABASE_URL` dan `SECRET_KEY` wajib diisi; aplikasi menolak start bila keduanya kosong. Buat `SECRET_KEY` dengan:

```powershell
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48))"
```

Jangan commit `.env`.

## Migrasi dan Data Awal

Dari folder `backend`, terapkan skema terbaru ke database pada `.env`, lalu isi data awal:

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m app.scripts.seed
```

Seed membuat kamera demo `CAM-01` (Lobi Gedung A), memuat tiga pengamatan dari [`monitoring-simulation.json`](../docs/data/monitoring-simulation.json), menambahkan tiga prediksi simulasi (`is_simulation: true`), dan membuat akun administrator dari `FIRST_SUPERUSER_EMAIL`/`FIRST_SUPERUSER_PASSWORD` bila keduanya diisi. Seed aman dijalankan berulang. Threshold kamera demo (Normal >= 10, Ramai >= 30) masih placeholder.

Setelah mengubah model di `app/models/`, buat migrasi baru lalu periksa isinya sebelum commit:

```powershell
.\.venv\Scripts\python.exe -m alembic revision --autogenerate -m "describe the change"
.\.venv\Scripts\python.exe -m alembic upgrade head
```

Waktu disimpan sebagai `timestamptz` (UTC) dan akan dikirim API dalam zona `TIMEZONE` (default `Asia/Jakarta`). Status keramaian disimpan sebagai teks `Sepi`/`Normal`/`Ramai` yang dijaga CHECK constraint.

## Menjalankan Server

1. Dari folder `backend`, jalankan:

   ```powershell
   .\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
   ```

2. Buka `http://localhost:8000/health` untuk respons HTTP 200 dan `{"status":"ok"}`, atau `http://localhost:8000/docs` untuk Swagger UI.

Mode `--reload` digunakan untuk pengembangan lokal. `/health` hanya menandakan proses berjalan dan tidak menyentuh database. `/health/ready` menjalankan `SELECT 1`: HTTP 200 bila database menjawab, HTTP 503 bila tidak.

## Endpoint API

Swagger UI (`/docs`) adalah sumber kebenaran kontrak. Ringkasan endpoint `/api/v1` saat ini:

| Endpoint | Respons |
| --- | --- |
| `GET /cameras` | Daftar kamera: `camera_id`, `name`, `location`, `is_active`. Sumber video tidak pernah dikirim. |
| `GET /cameras/{camera_id}/monitoring/latest` | Pengamatan terbaru, bentuk sama dengan `MonitoringRecord` di frontend. |
| `GET /cameras/{camera_id}/monitoring?start=&end=&limit=` | Riwayat urut waktu naik. Tanpa `start`, mengembalikan `limit` data terbaru (default 500, maksimal 2000). `start`/`end` wajib memakai offset zona waktu. |
| `GET /cameras/{camera_id}/predictions/latest` | Prediksi terbaru per horizon (5/15/30 menit), termasuk `target_time` dan `is_simulation`. |
| `GET /cameras/{camera_id}/live` | Jumlah dan status saat ini dari vision worker (`people_count`, `smoothed_count`, `crowd_status`, `is_stale`). Status live memakai dwell time 30 detik sehingga tidak berkedip. |
| `GET /cameras/{camera_id}/stream` | Video beranotasi MJPEG (`multipart/x-mixed-replace`), bisa langsung dipakai sebagai `src` tag `<img>`. |

`camera_id` adalah kode publik kamera (misalnya `CAM-01`). Waktu dikirim dalam zona `TIMEZONE` (default WIB, `+07:00`). Error 404 memakai kode stabil pada `detail`: `camera_not_found`, `no_monitoring_data`, `no_prediction`, `no_live_data`, atau `no_stream`. Endpoint baca belum memerlukan login.

Endpoint `/api/v1/ingest/cameras/{camera_id}/...` (`GET config`, `POST records`, `PUT live`, `PUT frame`) hanya untuk vision worker dan wajib memakai header `X-Worker-Key` yang sama dengan `WORKER_API_KEY`. Bila `WORKER_API_KEY` kosong, endpoint ingest menolak semua permintaan (HTTP 503).

## Vision Worker

Worker memutar video rekaman seolah CCTV live, menjalankan YOLO (`yolo11n`, imgsz 960, tile 2x2, conf 0.15) 2 kali per detik, lalu mengirim record per menit, status live, dan frame beranotasi 10 fps ke API. Worker tidak memakai kredensial database; konfigurasi kamera (sumber video, ROI, threshold) diambil dari API.

1. Pasang dependency AI (lihat Setup AI) dan isi `WORKER_API_KEY` di `.env`:

   ```powershell
   .\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

2. Daftarkan kamera dan isi riwayat awal (sekali saja):

   ```powershell
   .\.venv\Scripts\python.exe -m app.scripts.register_camera --code CAM-02 --name "Kabukicho" --location "Kabukicho, Shinjuku" --source data/videos/kabukicho_night_2026-08-25_720p.mp4 --roi experiments/configs/roi/kabukicho.json --normal 4 --ramai 8
   .\.venv\Scripts\python.exe -m app.scripts.backfill_records --camera CAM-02 --csv experiments/outputs/phase3/kabukicho_minutes.csv
   ```

   Backfill memuat hitungan per menit dari pemrosesan rekaman 12 jam dan menggeser waktunya agar berakhir tepat sebelum sekarang.

3. Jalankan API (bagian sebelumnya), lalu di terminal lain:

   ```powershell
   .\.venv\Scripts\python.exe -m app.worker --camera CAM-02 --start-minute 300
   ```

   `--start-minute 300` memulai dari pukul 23:00 JST pada rekaman (jam ramai). Video diulang saat habis. Hentikan dengan Ctrl+C; record menit terakhir tetap dikirim.

4. Periksa `http://localhost:8000/api/v1/cameras/CAM-02/live` dan buka `http://localhost:8000/api/v1/cameras/CAM-02/stream` di browser.

Status live dan frame disimpan di memori proses API, jadi API harus berjalan sebagai **satu proses** (jangan memakai `--workers` > 1) dan status hilang saat API restart. Riwayat tetap aman di database. Worker memakai sekitar 2,5 GB RAM dan GPU; dengan RAM 8 GB, tutup aplikasi berat saat menjalankan Docker, API, worker, dan frontend bersamaan.

## Pengujian

Pastikan container database berjalan, lalu dari folder `backend` jalankan:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Test selalu memakai database `crowdcast_test` (lihat [`tests/conftest.py`](tests/conftest.py)), bukan database pengembangan pada `.env`. Pytest menjalankan `alembic upgrade head` pada database test di awal sesi, mengosongkan tabel setelah setiap test database, dan memeriksa bahwa model selalu sesuai migrasi terakhir. URL test dapat diganti melalui `TEST_DATABASE_URL`. Job `backend-test` pada [CI repository](../.github/workflows/main.yml) menjalankan PostgreSQL 17 sebagai service container lalu menjalankan pytest yang sama.

## Organisasi Kode

- [`app/main.py`](app/main.py): `create_app()`, CORS, dan lifespan yang membuat serta menutup engine database.
- [`app/api/`](app/api/): router health, router `/api/v1` (`v1/cameras.py`), dan dependency bersama (`deps.py`, session database per request).
- [`app/schemas/`](app/schemas/): schema respons API, termasuk konversi waktu ke WIB.
- [`app/services/`](app/services/): query monitoring (`monitoring.py`), state live dan frame di memori (`live.py`), serta pipeline dan detector vision (`vision/`).
- [`app/worker/`](app/worker/): vision worker (`python -m app.worker`): replay video, thread deteksi, overlay MJPEG, dan client ingest.
- [`app/core/`](app/core/): konfigurasi (`get_settings()`) serta hashing password dan JWT.
- [`app/db/`](app/db/): base ORM dan pembuatan engine/session async.
- [`app/models/`](app/models/): model ORM User, Camera, CrowdRecord, Prediction, dan enum status.
- [`alembic/`](alembic/): environment dan file migrasi skema.
- [`app/scripts/`](app/scripts/): `seed.py` (kamera demo, riwayat simulasi, administrator), `register_camera.py`, dan `backfill_records.py`.
- [`docker/postgres-init/`](docker/postgres-init/): script inisialisasi container PostgreSQL lokal.
- [`tests/`](tests/): pengujian backend.
- `requirements.txt`, `requirements-dev.txt`, `requirements-ai.txt`: dependency runtime, pengembangan, dan AI (worker dan eksperimen).

Lihat [README utama](../README.md) untuk workflow Git dan [laporan Week 6](../docs/progress/week-06.md) untuk bukti verifikasi.
