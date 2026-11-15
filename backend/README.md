# CrowdCast Backend

API CrowdCast menggunakan **Python 3.12**, **FastAPI**, dan **SQLAlchemy async** dengan PostgreSQL. Aplikasi aktif menyediakan `GET /health` (liveness), `GET /health/ready` (readiness, memeriksa database), dan dokumentasi OpenAPI. Model data, autentikasi endpoint, dan pemrosesan video/AI belum terhubung ke aplikasi.

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

Dependency AI dipisah dari `requirements.txt` agar CI tidak mengunduh PyTorch. Langkah ini hanya diperlukan untuk menjalankan skrip di `experiments/`.

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

## Menjalankan Server

1. Dari folder `backend`, jalankan:

   ```powershell
   .\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
   ```

2. Buka `http://localhost:8000/health` untuk respons HTTP 200 dan `{"status":"ok"}`, atau `http://localhost:8000/docs` untuk Swagger UI.

Mode `--reload` digunakan untuk pengembangan lokal. `/health` hanya menandakan proses berjalan dan tidak menyentuh database. `/health/ready` menjalankan `SELECT 1`: HTTP 200 bila database menjawab, HTTP 503 bila tidak.

## Pengujian

Pastikan container database berjalan, lalu dari folder `backend` jalankan:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Test selalu memakai database `crowdcast_test` (lihat [`tests/conftest.py`](tests/conftest.py)), bukan database pengembangan pada `.env`. URL test dapat diganti melalui `TEST_DATABASE_URL`. Job `backend-test` pada [CI repository](../.github/workflows/main.yml) menjalankan PostgreSQL 17 sebagai service container lalu menjalankan pytest yang sama.

## Organisasi Kode

- [`app/main.py`](app/main.py): `create_app()`, CORS, dan lifespan yang membuat serta menutup engine database.
- [`app/api/`](app/api/): router (`health.py`) dan dependency bersama (`deps.py`, session database per request).
- [`app/core/`](app/core/): konfigurasi (`get_settings()`) serta hashing password dan JWT.
- [`app/db/`](app/db/): base ORM dan pembuatan engine/session async.
- [`app/models/`](app/models/): model ORM; migrasi Alembic ditambahkan pada fase model data.
- [`docker/postgres-init/`](docker/postgres-init/): script inisialisasi container PostgreSQL lokal.
- [`tests/`](tests/): pengujian backend.
- `requirements.txt`, `requirements-dev.txt`, `requirements-ai.txt`: dependency runtime, pengembangan, dan eksperimen AI.

Lihat [README utama](../README.md) untuk workflow Git dan [laporan Week 6](../docs/progress/week-06.md) untuk bukti verifikasi.
