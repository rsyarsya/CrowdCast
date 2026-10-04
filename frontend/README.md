# CrowdCast Frontend

Scaffold antarmuka CrowdCast menggunakan **Next.js 16 (App Router)**, **React**, dan **TypeScript**. Aplikasi aktif menampilkan halaman awal serta menyediakan `GET /health`. Dashboard monitoring, autentikasi, streaming video, dan konsumsi API backend belum diimplementasikan.

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

Scaffold belum menggunakan `NEXT_PUBLIC_API_BASE_URL`. [`.env.example`](.env.example) menyiapkan alamat backend lokal untuk integrasi berikutnya; `.env.local` belum diperlukan untuk halaman awal atau health.

Saat integrasi API mulai dikerjakan, salin template hanya jika `.env.local` belum tersedia:

```powershell
Copy-Item .env.example .env.local
```

Jangan menimpa konfigurasi lokal yang sudah ada atau commit `.env.local`. Variabel `NEXT_PUBLIC_*` tersedia untuk browser sehingga hanya boleh berisi konfigurasi publik, bukan secret.

## Menjalankan Server

1. Dari folder `frontend`, jalankan:

   ```powershell
   npm run dev
   ```

2. Buka aplikasi pada `http://localhost:3000` atau health pada `http://localhost:3000/health`.

Endpoint health menghasilkan HTTP 200 dan `{"status":"ok"}` untuk aplikasi frontend sendiri. Endpoint ini belum memeriksa koneksi backend.

## Pengujian dan Pemeriksaan

Dari folder `frontend`, jalankan berurutan:

```powershell
npm run test
npm run typecheck
npm run lint
npm run build
```

Vitest menggunakan environment Node dan alias `@` menuju `src` melalui [`vitest.config.ts`](vitest.config.ts). Test health memanggil route handler secara langsung; belum menguji navigasi browser atau integrasi antaraplikasi. Job `frontend-check` pada [CI repository](../.github/workflows/main.yml) menjalankan seluruh pemeriksaan tersebut setelah `npm ci`.

Untuk menjalankan hasil build secara lokal, setelah build berhasil:

```powershell
npm run start
```

GitHub Pages CrowdCast menerbitkan dokumentasi dari `docs/`; aplikasi frontend belum dideploy melalui Pages.

## Organisasi Kode

- [`src/app/`](src/app/): App Router, root layout, halaman awal, global CSS, dan route health.
- [`tests/`](tests/): test frontend yang tersedia.
- `next.config.ts`, `tsconfig.json`, `eslint.config.mjs`, dan `vitest.config.ts`: konfigurasi build dan pemeriksaan.
- `package.json` dan `package-lock.json`: skrip serta dependency frontend.

Tambahkan komponen UI dan modul pemanggilan API ketika fitur tersebut mulai dibangun. Struktur mengikuti kode yang tersedia; belum diperlukan folder tambahan untuk modul yang belum diimplementasikan.

Lihat [README utama](../README.md) untuk workflow Git dan [laporan Week 6](../docs/progress/week-06.md) untuk bukti verifikasi.
