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

Swagger UI (`/docs`) adalah sumber kebenaran kontrak.

### Login

Semua endpoint `/cameras` dan `/users` membutuhkan token. Alurnya:

1. `POST /api/v1/auth/login` dengan form `username` (email) dan `password`. Respons berisi `access_token`, `token_type: "bearer"`, dan `expires_in` (detik, default 8 jam).
2. Kirim header `Authorization: Bearer <access_token>` pada request berikutnya. `GET /api/v1/auth/me` mengembalikan user yang sedang login.

Di Swagger, klik tombol **Authorize**, isi email pada kolom `username` beserta password, lalu semua request dari Swagger otomatis membawa token. Akun administrator pertama dibuat oleh seed dari `FIRST_SUPERUSER_EMAIL`/`FIRST_SUPERUSER_PASSWORD`; akun lain dibuat admin lewat `POST /api/v1/users`.

Role dibaca ulang dari database di setiap request, jadi perubahan role atau penonaktifan akun langsung berlaku walaupun token lama belum kedaluwarsa. Login yang gagal karena email tidak terdaftar, password salah, atau akun nonaktif selalu menjawab `401 invalid_credentials`, sehingga tidak membocorkan email mana yang terdaftar.

### Monitoring (operator dan admin)

| Endpoint | Respons |
| --- | --- |
| `GET /cameras` | Daftar kamera: `camera_id`, `name`, `location`, `is_active`. Sumber video tidak pernah dikirim. |
| `GET /cameras/{camera_id}/monitoring/latest` | Pengamatan terbaru, bentuk sama dengan `MonitoringRecord` di frontend. |
| `GET /cameras/{camera_id}/monitoring?start=&end=&limit=` | Riwayat urut waktu naik. Tanpa `start`, mengembalikan `limit` data terbaru (default 500, maksimal 2000). `start`/`end` wajib memakai offset zona waktu. |
| `GET /cameras/{camera_id}/predictions/latest` | Prediksi terbaru per horizon (5/15/30 menit), termasuk `target_time` dan `is_simulation`. |
| `GET /cameras/{camera_id}/live` | Jumlah dan status saat ini dari vision worker (`people_count`, `smoothed_count`, `crowd_status`, `is_stale`). Status live memakai dwell time 30 detik sehingga tidak berkedip. |
| `GET /cameras/{camera_id}/stream` | Video beranotasi MJPEG (`multipart/x-mixed-replace`). Menerima header `Authorization` atau `?ticket=` (lihat Realtime). |

### Realtime (operator dan admin)

Dashboard tidak perlu polling. Server mengirim event lewat Server-Sent Events (SSE): satu arah dari server ke browser, dibuka dengan `EventSource` bawaan browser.

| Endpoint | Fungsi |
| --- | --- |
| `POST /cameras/{camera_id}/ticket` | Tiket untuk `/stream` dan `/events` kamera itu: `{ticket, expires_in}`. |
| `POST /alerts/ticket` | Tiket untuk `/alerts/events`. |
| `GET /cameras/{camera_id}/events` | Event `live` (setiap update worker, sekitar 2 kali per detik), `record` (record menit baru), `prediction` (list prediksi 5/15/30), dan `alert` (alert dibuka, diperbarui, ditutup, atau di-ack). Bentuk `data` sama dengan respons REST masing-masing. Status live terakhir dikirim saat koneksi dibuka. |
| `GET /alerts/events` | Event `alert` dari semua kamera, untuk badge notifikasi. |

`<img>` dan `EventSource` tidak bisa mengirim header `Authorization`, jadi ketiga route `GET` di atas juga menerima `?ticket=`. Tiket berlaku `STREAM_TICKET_SECONDS` (default 60 detik), hanya untuk kamera atau topik yang disebut, dan hanya diperiksa saat koneksi dibuka; koneksi yang sudah berjalan tidak diputus. Saat `EventSource` error, frontend meminta tiket baru lalu membuka koneksi lagi. Tiket tidak bisa dipakai sebagai Bearer token. Saat tidak ada event, server mengirim baris komentar `: ping` tiap `SSE_HEARTBEAT_SECONDS` (default 15) agar proxy tidak memutus koneksi.

Contoh dari terminal:

```powershell
curl.exe -N "http://localhost:8000/api/v1/cameras/CAM-02/events?ticket=<ticket>"
```

### Peringatan Ramai (operator dan admin)

Alert dibuat otomatis dari data yang dikirim worker, tanpa langkah manual:

- `crowded`: terbuka saat record per menit berstatus Ramai, tertutup pada record berikutnya yang tidak Ramai.
- `forecast_crowded`: satu alert per horizon (5/15/30 menit), terbuka saat prediksi horizon itu Ramai dan tertutup saat prediksi berikutnya tidak Ramai.

Hanya ada satu alert terbuka per kamera, jenis, dan horizon. Data yang dikirim ulang atau datang terlambat tidak membuat duplikat dan tidak menutup alert.

| Endpoint | Fungsi |
| --- | --- |
| `GET /alerts?camera_id=&active=&start=&end=&limit=` | Daftar alert terbaru lebih dulu. `active=true` hanya yang masih terbuka. `start`/`end` menyaring `started_at` dan wajib memakai offset zona waktu. |
| `POST /alerts/{alert_id}/ack` | Menandai alert sudah dilihat, menyimpan waktu dan nama user. Ack kedua tidak mengubah apa pun. |

Field respons: `id`, `camera_id`, `location`, `kind`, `horizon_minutes` (null untuk `crowded`), `started_at`, `last_seen_at`, `ended_at`, `target_time` (perkiraan waktu Ramai untuk alert prediksi), `is_active`, `peak_count`, `acknowledged_at`, `acknowledged_by`.

### Manajemen (admin saja)

| Endpoint | Fungsi |
| --- | --- |
| `GET /cameras/{camera_id}/config` | Konfigurasi lengkap kamera: threshold, ROI, dan `source` dengan password tersensor (`rtsp://user:***@host/...`). |
| `POST /cameras` | Mendaftarkan kamera: `camera_id` (huruf besar, angka, `-`), `name`, `location`, `source`, `threshold_normal`, `threshold_ramai`, dan `roi` opsional (minimal 3 titik, koordinat 0–1). |
| `PATCH /cameras/{camera_id}` | Mengubah sebagian field. `is_active: false` menghentikan kamera tanpa menghapus riwayatnya; `roi: null` berarti seluruh frame dihitung. |
| `GET /users` | Daftar user tanpa password. |
| `POST /users` | Membuat user (`email`, `name`, `password` minimal 8 karakter, `role` `operator`/`admin`). |
| `PATCH /users/{user_id}` | Mengubah `name`, `role`, `password`, atau `is_active`. Admin tidak bisa menonaktifkan atau menurunkan role dirinya sendiri, sehingga selalu ada admin aktif. |

Tidak ada endpoint hapus permanen: menghapus kamera berarti menghapus seluruh riwayatnya, jadi kamera dan user cukup dinonaktifkan.

`camera_id` adalah kode publik kamera (misalnya `CAM-01`). Waktu dikirim dalam zona `TIMEZONE` (default WIB, `+07:00`). Error memakai kode stabil pada `detail`: 401 `not_authenticated`, `invalid_token`, `invalid_ticket`, atau `invalid_credentials`; 403 `forbidden`; 404 `camera_not_found`, `user_not_found`, `alert_not_found`, `no_monitoring_data`, `no_prediction`, `no_live_data`, atau `no_stream`; 409 `camera_code_exists` atau `email_already_exists`; 422 `cannot_modify_self` atau `invalid_thresholds`.

Endpoint `/api/v1/ingest/cameras/{camera_id}/...` (`GET config`, `POST records`, `PUT live`, `PUT frame`) hanya untuk vision worker, tidak memakai login user, dan wajib memakai header `X-Worker-Key` yang sama dengan `WORKER_API_KEY`. Bila `WORKER_API_KEY` kosong, endpoint ingest menolak semua permintaan (HTTP 503).

## Vision Worker

Worker memutar video rekaman seolah CCTV live, menjalankan YOLO (`yolo11n`, imgsz 960, tile 2x2, conf 0.15) 2 kali per detik, lalu mengirim record per menit, status live, dan frame beranotasi 10 fps ke API. Worker tidak memakai kredensial database; konfigurasi kamera (sumber video, ROI, threshold) diambil dari API.

1. Pasang dependency AI (lihat Setup AI) dan isi `WORKER_API_KEY` di `.env`:

   ```powershell
   .\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

2. Daftarkan kamera dan isi riwayat awal (sekali saja):

   ```powershell
   .\.venv\Scripts\python.exe -m app.scripts.register_camera --code CAM-02 --name "Kabukicho" --location "Kabukicho, Shinjuku" --source data/videos/kabukicho_night_2026-08-25_720p.mp4 --roi experiments/configs/roi/kabukicho.json --normal 4 --ramai 12
   .\.venv\Scripts\python.exe -m app.scripts.backfill_records --camera CAM-02 --csv experiments/outputs/phase3/kabukicho_minutes.csv
   ```

   Backfill memuat hitungan per menit dari pemrosesan rekaman 12 jam dan menggeser waktunya agar berakhir tepat sebelum sekarang.

   Setelah ROI diubah (`experiments/roi_tool.py --camera kabukicho --minutes 0 300 390 600`), jalankan ulang `experiments/phase3_dataset.py build` untuk dataset dan threshold baru, `register_camera` dengan threshold itu, lalu `backfill_records ... --replace` untuk mengganti seluruh riwayat kamera.

3. Jalankan API (bagian sebelumnya), lalu di terminal lain:

   ```powershell
   .\.venv\Scripts\python.exe -m app.worker --camera CAM-02 --start-minute 300
   ```

   `--start-minute 300` memulai dari pukul 23:00 JST pada rekaman (jam ramai). Video diulang saat habis. Hentikan dengan Ctrl+C; record menit terakhir tetap dikirim.

4. Periksa `http://localhost:8000/api/v1/cameras/CAM-02/live` dan buka `http://localhost:8000/api/v1/cameras/CAM-02/stream?ticket=<ticket>` di browser (tiket dari `POST /cameras/CAM-02/ticket` lewat Swagger).

### Prediksi 5/15/30 Menit

Setiap record menit selesai, worker memprediksi jumlah orang 5, 15, dan 30 menit ke depan lalu mengirimnya ke `POST /ingest/.../predictions`; hasilnya muncul di `GET /cameras/{camera_id}/predictions/latest` dengan `is_simulation: false`. Saat start, worker memuat riwayat terbaru dari API. Celah lebih dari 5 menit membuat riwayat dimulai ulang.

Model dipilih dengan eksperimen yang membandingkan naive, moving average, regresi linear (lag 30 menit), dan GRU kecil pada dataset per menit (split waktu 60/20/20):

```powershell
.\.venv\Scripts\python.exe experiments\phase5_forecast.py
```

Model dengan MAE validasi terendah disimpan ke `data/models/forecast/<camera>.json` atau `.pt` (tidak di-commit) dan otomatis dipakai worker. Tanpa file itu worker memakai moving average 10 menit. Opsi worker: `--forecast-model PATH` atau `--no-forecast`.

Status live dan frame disimpan di memori proses API, jadi API harus berjalan sebagai **satu proses** (jangan memakai `--workers` > 1) dan status hilang saat API restart. Riwayat tetap aman di database. Worker memakai sekitar 2,5 GB RAM dan GPU; dengan RAM 8 GB, tutup aplikasi berat saat menjalankan Docker, API, worker, dan frontend bersamaan.

## Pengujian

Pastikan container database berjalan, lalu dari folder `backend` jalankan:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Test selalu memakai database `crowdcast_test` (lihat [`tests/conftest.py`](tests/conftest.py)), bukan database pengembangan pada `.env`. Pytest menjalankan `alembic upgrade head` pada database test di awal sesi, mengosongkan tabel setelah setiap test database, dan memeriksa bahwa model selalu sesuai migrasi terakhir. URL test dapat diganti melalui `TEST_DATABASE_URL`. Job `backend-test` pada [CI repository](../.github/workflows/main.yml) menjalankan PostgreSQL 17 sebagai service container lalu menjalankan pytest yang sama.

## Organisasi Kode

- [`app/main.py`](app/main.py): `create_app()`, CORS, dan lifespan yang membuat serta menutup engine database.
- [`app/api/`](app/api/): router health, router `/api/v1` (`auth.py`, `alerts.py`, `cameras.py`, `realtime.py`, `camera_admin.py`, `users.py`, `ingest.py`), dan dependency bersama (`deps.py`: session database, user dari token, syarat admin).
- [`app/schemas/`](app/schemas/): schema respons API, termasuk konversi waktu ke WIB.
- [`app/services/`](app/services/): query monitoring (`monitoring.py`), aturan user dan kamera (`users.py`, `cameras.py`), pelacakan alert (`alerts.py`), state live, frame, dan event SSE di memori (`live.py`), serta pipeline dan detector vision (`vision/`).
- [`app/worker/`](app/worker/): vision worker (`python -m app.worker`): replay video, thread deteksi, overlay MJPEG, dan client ingest.
- [`app/core/`](app/core/): konfigurasi (`get_settings()`), hashing password, JWT, dan penyensoran kredensial pada URL sumber video.
- [`app/db/`](app/db/): base ORM dan pembuatan engine/session async.
- [`app/models/`](app/models/): model ORM User, Camera, CrowdRecord, Prediction, Alert, dan enum.
- [`alembic/`](alembic/): environment dan file migrasi skema.
- [`app/scripts/`](app/scripts/): `seed.py` (kamera demo, riwayat simulasi, administrator), `register_camera.py`, dan `backfill_records.py`.
- [`docker/postgres-init/`](docker/postgres-init/): script inisialisasi container PostgreSQL lokal.
- [`tests/`](tests/): pengujian backend.
- `requirements.txt`, `requirements-dev.txt`, `requirements-ai.txt`: dependency runtime, pengembangan, dan AI (worker dan eksperimen).

Lihat [README utama](../README.md) untuk workflow Git dan [laporan Week 6](../docs/progress/week-06.md) untuk bukti verifikasi.
