# CrowdCast Frontend

Antarmuka web CrowdCast untuk pemantauan keramaian berbasis **Computer Vision & Artificial Intelligence**, dikembangkan menggunakan **Next.js 16 (App Router)** dan **TypeScript**.

## Persiapan Lingkungan

Pastikan berada di direktori `frontend`:

```powershell
cd frontend
```

Instal dependensi:

```powershell
npm install
```

Salin konfigurasi environment:

```powershell
Copy-Item .env.example .env.local
```

## Menjalankan Server

Jalankan server pengembangan Next.js:

```powershell
npm run dev
```

- Aplikasi web: `http://localhost:3000`
- Endpoint verifikasi kesehatan: `http://localhost:3000/health`

## Membangun untuk Produksi

```powershell
npm run build
npm run start
```

## Menjalankan Pengujian

Eksekusi pengujian otomatis dengan Vitest:

```powershell
npm run test
```

Pemeriksaan tipe dan linting:

```powershell
npm run typecheck
npm run lint
```

## Struktur Proyek

```text
frontend/
├── src/
│   └── app/                # App Router: layout, halaman, dan route handler
│       ├── layout.tsx      # Kerangka tata letak global
│       ├── page.tsx        # Halaman beranda
│       ├── globals.css     # Gaya global
│       └── health/route.ts # Endpoint verifikasi kesehatan GET /health
├── tests/
│   └── health.test.ts      # Pengujian otomatis endpoint kesehatan
├── .env.example            # Template konfigurasi environment
├── next.config.ts          # Konfigurasi Next.js
├── tsconfig.json           # Konfigurasi TypeScript
├── vitest.config.ts        # Konfigurasi pengujian Vitest
├── eslint.config.mjs       # Konfigurasi ESLint
├── package.json            # Dependensi dan skrip npm
└── README.md               # Panduan instalasi dan eksekusi lokal
```
