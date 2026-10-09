# CrowdCast Backend

Scaffold API CrowdCast menggunakan **Python 3.12** dan **FastAPI**. Aplikasi aktif menyediakan `GET /health` dan dokumentasi OpenAPI. Database, autentikasi, dan pemrosesan video/AI belum terhubung ke aplikasi.

## Prasyarat

- Python 3.12 dengan pip dan dukungan virtual environment.
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

## Konfigurasi Environment

Scaffold `app/main.py` belum memuat `.env`. [`.env.example`](.env.example) berisi placeholder untuk database, autentikasi, dan AI tahap berikutnya; file tersebut belum diperlukan untuk menjalankan health.

Saat implementasi konfigurasi dimulai, salin template hanya jika `.env` belum tersedia, lalu isi konfigurasi lokal:

```powershell
Copy-Item .env.example .env
```

Jangan menimpa konfigurasi lokal yang sudah ada atau commit `.env`. Modul konfigurasi, security, database, dan model User belum menjadi bagian runtime aktif; dependency resmi saat ini hanya mencukupi scaffold dan test health.

## Menjalankan Server

1. Dari folder `backend`, jalankan:

   ```powershell
   .\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
   ```

2. Buka `http://localhost:8000/health` untuk respons HTTP 200 dan `{"status":"ok"}`, atau `http://localhost:8000/docs` untuk Swagger UI.

Mode `--reload` digunakan untuk pengembangan lokal. Health memeriksa respons dasar aplikasi, bukan kesiapan database, autentikasi, atau model AI.

## Pengujian

Dari folder `backend`, jalankan:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Test pada [`tests/test_health.py`](tests/test_health.py) memeriksa HTTP 200 dan payload health menggunakan FastAPI TestClient. Job `backend-test` pada [CI repository](../.github/workflows/main.yml) menjalankan perintah yang sama pada Python 3.12 setelah instalasi dependency.

## Organisasi Kode

- [`app/main.py`](app/main.py): entrypoint FastAPI dan route health aktif.
- [`app/core/`](app/core/): kode awal konfigurasi dan security; belum digunakan entrypoint.
- [`app/db/`](app/db/): fondasi sesi database; koneksi belum diintegrasikan.
- [`app/models/`](app/models/): model User awal; migrasi dan persistensi belum aktif.
- [`tests/`](tests/): pengujian backend.
- `requirements.txt` dan `requirements-dev.txt`: dependency runtime dan pengembangan.

Tambahkan pemisahan routing, schema, dan service ketika implementasinya mulai tersedia. Pemrosesan AI dapat ditempatkan sebagai service backend terlebih dahulu; pemisahan layanan dievaluasi ketika kebutuhan runtime atau deployment sudah jelas.

Lihat [README utama](../README.md) untuk workflow Git dan [laporan Week 6](../docs/progress/week-06.md) untuk bukti verifikasi.
