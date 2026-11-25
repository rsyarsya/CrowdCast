# CrowdCast Frontend

Scaffold antarmuka CrowdCast menggunakan **Next.js 16 (App Router)**, **React**, dan **TypeScript**. Aplikasi aktif menampilkan halaman awal, menyediakan `GET /health`, dan dashboard `/dashboard` yang membaca data monitoring serta prediksi dari API backend. Autentikasi, halaman History, auto-refresh, dan streaming video belum diimplementasikan.

## Prasyarat

- Node.js 22 dan npm, sesuai job CI frontend.
- Perintah berikut menggunakan PowerShell dan dimulai dari root repository.

## Setup

1. Masuk ke folder frontend:

   ```powershell
   cd frontend
   ```

2. Instal dependency mengikuti lockfile yang dilacak:

   ```powershell
   npm ci
   ```

Gunakan `npm ci` untuk setup dan verifikasi yang dapat diulang. Saat sengaja menambahkan atau memperbarui dependency dengan npm, sertakan perubahan `package.json` dan `package-lock.json` dalam commit yang sama.

## Konfigurasi Environment

Salin template hanya jika `.env.local` belum tersedia:

```powershell
Copy-Item .env.example .env.local
```

| Variabel | Default | Fungsi |
| --- | --- | --- |
| `NEXT_PUBLIC_API_BASE_URL` | `http://localhost:8000` | Alamat backend; dashboard memanggil `/api/v1` di alamat ini. |
| `NEXT_PUBLIC_DEFAULT_CAMERA_ID` | `CAM-01` | Kamera yang ditampilkan dashboard. |
| `NEXT_PUBLIC_MONITORING_SOURCE` | `api` | `mock` menampilkan data simulasi lokal tanpa backend, misalnya untuk demo UI. |

Jangan menimpa konfigurasi lokal yang sudah ada atau commit `.env.local`. Variabel `NEXT_PUBLIC_*` tersedia untuk browser sehingga hanya boleh berisi konfigurasi publik, bukan secret.

## Menjalankan Server

1. Dari folder `frontend`, jalankan:

   ```powershell
   npm run dev
   ```

2. Buka aplikasi pada `http://localhost:3000`, dashboard pada `http://localhost:3000/dashboard`, atau health pada `http://localhost:3000/health`.

Dashboard membutuhkan backend yang berjalan dan sudah di-seed (lihat [panduan backend](../backend/README.md)). Bila backend tidak dapat dihubungi, dashboard menampilkan pesan, bukan halaman error. Dashboard dirender ulang setiap request, sehingga data terbaru muncul saat halaman di-refresh.

Endpoint health menghasilkan HTTP 200 dan `{"status":"ok"}` untuk aplikasi frontend sendiri dan tidak memeriksa koneksi backend.

## Pengujian dan Pemeriksaan

Dari folder `frontend`, jalankan berurutan:

```powershell
npm run test
npm run typecheck
npm run lint
npm run build
```

Vitest menggunakan environment Node dan alias `@` menuju `src` melalui [`vitest.config.ts`](vitest.config.ts). Test accessor dan dashboard mengganti `fetch` dengan mock sehingga tidak membutuhkan backend; test ini memeriksa URL request, pemetaan kode error, serta tampilan saat backend mati atau prediksi belum ada.

Bila npm global memakai `legacy-peer-deps=true`, peer dependency seperti `@testing-library/dom` tidak terpasang dan test komponen gagal. Jalankan `npm ci --legacy-peer-deps=false` untuk repository ini. Job `frontend-check` pada [CI repository](../.github/workflows/main.yml) menjalankan seluruh pemeriksaan tersebut setelah `npm ci`.

Untuk menjalankan hasil build secara lokal, setelah build berhasil:

```powershell
npm run start
```

GitHub Pages CrowdCast menerbitkan dokumentasi dari `docs/`; aplikasi frontend belum dideploy melalui Pages.

## Organisasi Kode

- [`src/app/`](src/app/): App Router, root layout, halaman awal, dashboard (beserta error boundary), global CSS, dan route health.
- [`src/components/`](src/components/): komponen presentasional dashboard (props-in, tanpa fetching).
- [`src/lib/monitoring/`](src/lib/monitoring/): tipe kontrak API, accessor data, dan data mock.
- [`tests/`](tests/): test frontend yang tersedia.
- `next.config.ts`, `tsconfig.json`, `eslint.config.mjs`, dan `vitest.config.ts`: konfigurasi build dan pemeriksaan.
- `package.json` dan `package-lock.json`: skrip serta dependency frontend.

Tambahkan komponen UI dan modul pemanggilan API ketika fitur tersebut mulai dibangun. Struktur mengikuti kode yang tersedia; belum diperlukan folder tambahan untuk modul yang belum diimplementasikan.

Lihat [README utama](../README.md) untuk workflow Git dan [laporan Week 6](../docs/progress/week-06.md) untuk bukti verifikasi.
