# CrowdCast Backend

Backend API dan layanan kecerdasan buatan (Computer Vision & Prediksi) untuk CrowdCast, dikembangkan menggunakan **Python 3.12** dan **FastAPI**.

## Persiapan Lingkungan

Pastikan berada di direktori `backend`:

```powershell
cd backend
```

Jika virtual environment belum dibuat:
```powershell
python -m venv .venv
```

Aktivasi virtual environment:
```powershell
.\.venv\Scripts\Activate.ps1
```

Instal dependensi:
```powershell
pip install -r requirements-dev.txt
```

Salin konfigurasi environment:
```powershell
Copy-Item .env.example .env
```

## Menjalankan Server

Jalankan server pengembangan FastAPI dengan Uvicorn:

```powershell
uvicorn app.main:app --reload --port 8000
```

- Endpoint verifikasi kesehatan: `http://localhost:8000/health`
- Dokumentasi interaktif Swagger UI: `http://localhost:8000/docs`

## Menjalankan Pengujian

Eksekusi pengujian otomatis dengan pytest:

```powershell
pytest -q
```
