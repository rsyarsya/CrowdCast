# Progress Week 5

**Periode:** 25 September–1 Oktober 2026<br>
**Status:** Rancangan dan kerangka awal tersedia

## Ringkasan

Pada Week 5, tim memusatkan pekerjaan pada penentuan arsitektur teknologi serta penyiapan fondasi backend CrowdCast. Hasil yang terdokumentasi mencakup penetapan matriks tech stack (FastAPI, Next.js, PostgreSQL/SQLAlchemy, serta JWT Bearer), pengorganisasian struktur folder modular backend, serta penyiapan kerangka aplikasi dasar untuk pengujian awal.

Progress ini merupakan dokumentasi perancangan teknis dan inisiasi fondasi backend. Implementasi koneksi database, skema migrasi, pipeline video/AI, model prediksi, serta integrasi dashboard belum dinyatakan selesai.

## Deliverable

| Deliverable | Status | Tautan |
| --- | --- | --- |
| Matriks keputusan teknologi | Tersedia | [#keputusan-teknologi](#keputusan-teknologi) |
| Struktur folder dan rancangan modul | PROPOSED | [#organisasi-dan-struktur-backend](#organisasi-dan-struktur-backend) |
| Kerangka awal FastAPI dan verifikasi | Tersedia | [#kerangka-aplikasi-dan-verifikasi](#kerangka-aplikasi-dan-verifikasi) |

## Progress yang Dilaporkan

### Keputusan Teknologi

Pilihan teknologi dirancang untuk menyatukan API dan integrasi AI dalam satu lingkungan runtime Python, serta menjaga keselarasan dengan kebutuhan frontend Next.js.

| Komponen | Pilihan | Status dan Alasan |
| --- | --- | --- |
| Backend Framework | Python 3.12 + FastAPI | **DECIDED**. Satu ekosistem Python untuk backend API dan integrasi modul AI tanpa overhead multi-runtime. |
| Frontend | Next.js (TypeScript) | **DECIDED**. Dikerjakan terpisah oleh anggota tim; backend menyediakan API JSON dan dokumentasi Swagger interaktif. |
| Database & ORM | PostgreSQL + SQLAlchemy | **DECIDED**. PostgreSQL sebagai database relasional dan SQLAlchemy sebagai ORM. Menggunakan konfigurasi environment variable (`DATABASE_URL`). |
| Migrasi Skema | Alembic | **PROPOSED**. Direncanakan untuk versioning dan migrasi skema tabel saat implementasi model database dimulai. |
| Layanan Cloud DB | Supabase atau Azure Database for PostgreSQL | **TBD**. Kesamaan engine PostgreSQL memudahkan deployment cloud departemen pada akhir proyek. |
| Deteksi & Tracking | Ultralytics YOLOv8n/YOLO11n + ByteTrack | **PROPOSED**. Deteksi kelas person berbasis COCO dan tracking antar-frame terintegrasi. |
| Prediksi Keramaian | PyTorch / Time-Series Regression | **PROPOSED**. PyTorch disiapkan untuk permodelan deret waktu, didukung baseline regresi/moving average sederhana untuk kestabilan demo awal. |
| Pengiriman Video | MP4 rekaman sebagai input, MJPEG stream untuk dashboard | **PROPOSED**. Fallback video rekaman diproses dan frame beranotasi disalurkan via MJPEG stream agar mudah ditampilkan di tag `<img>` browser. |
| Data Monitoring | HTTP Polling JSON & WebSocket | **PROPOSED**. Polling berkala untuk pembacaan status berkala, dengan opsi WebSocket untuk update telemetri real-time. |
| Autentikasi | JWT Bearer (Operator & Administrator) | **DECIDED**. OAuth2 password bearer flow dengan hashing bcrypt untuk kontrol akses bertingkat. |

### Organisasi dan Struktur Backend

Struktur direktori pada folder `backend/` dirancang modular untuk memisahkan logika API, skema data, konfigurasi, dan modul pemrosesan video/AI:

```text
backend/
├── app/
│   ├── main.py             # Aplikasi aktif: routing & endpoint /health
│   ├── core/               # Konfigurasi aplikasi dan fungsi security/JWT
│   ├── db/                 # Sesi database dan deklarasi base ORM
│   ├── models/             # Model relasional (User, Camera, CrowdRecord, Prediction)
│   ├── schemas/            # Skema validasi Pydantic (request/response contract)
│   └── services/           # Modul pemrosesan AI (video ingestion, YOLO, forecasting)
├── tests/
│   └── test_health.py      # Pengujian otomatis endpoint aplikasi
├── data/
│   ├── videos/             # Sampel video rekaman untuk pengujian fallback
│   └── models/             # Bobot model AI (YOLO / checkpoint prediksi)
├── requirements.txt        # Dependensi runtime utama
├── requirements-dev.txt    # Dependensi pengembangan dan pengujian
├── .env.example            # Template konfigurasi environment
└── README.md               # Panduan instalasi dan eksekusi lokal
```

### Kerangka Aplikasi dan Verifikasi

- Menginisiasi kerangka FastAPI minimal dengan endpoint verifikasi `GET /health` yang mengembalikan respon `{"status":"ok"}` dengan kode HTTP 200.
- Dokumentasi interaktif Swagger UI otomatis tersedia pada rute `/docs` untuk mempermudah koordinasi kontrak API dengan pengembang frontend.
- Menyusun pengujian unit otomatis pada `backend/tests/test_health.py` menggunakan `pytest` dan `httpx` TestClient.
- Pengujian otomatis dapat dijalankan melalui lingkungan virtual Python:
  ```powershell
  .\.venv\Scripts\python.exe -m pytest -q
  ```
- Endpoint `/health` saat ini berfungsi memvalidasi kesiapan proses server backend; integrasi database aktif, autentikasi, serta inferensi AI akan diaktifkan secara bertahap pada iterasi berikutnya.

## Kontribusi Anggota

| Anggota | Kontribusi yang dilaporkan |
| --- | --- |
| Raditya Azhar Ananta | Menetapkan arsitektur teknologi backend dan AI, menyusun struktur modul backend, serta menginisiasi kerangka dasar FastAPI dan pengujian awal. |

## Kendala

- Pemilihan varian model deteksi dan horizon prediksi masih membutuhkan validasi pada video rekaman pengujian serta ketersediaan dataset deret waktu.
- Skema database PostgreSQL dan migrasi Alembic masih perlu dihubungkan dan diverifikasi pada siklus request backend.
- Mekanisme pengiriman streaming frame dan polling data monitoring perlu diselaraskan dengan kebutuhan tampilan antarmuka tim frontend.

## Tindak Lanjut

- Mengimplementasikan skema relasional tabel database menggunakan SQLAlchemy dan menyiapkan migrasi dengan Alembic.
- Membangun pipeline pembacaan video rekaman dan menguji inferensi model deteksi YOLO beserta tracking ByteTrack.
- Mengevaluasi ketersediaan dataset deret waktu kerumunan dan menentukan baseline model prediksi keramaian jangka pendek.
- Menyepakati kontrak endpoint API monitoring serta format pertukaran data bersama tim frontend.
