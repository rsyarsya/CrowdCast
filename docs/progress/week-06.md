# Progress Week 6

**Periode:** 2–4 Oktober 2026<br>
**Disusun per:** 4 Oktober 2026<br>
**Status:** Verifikasi lokal dan CI berhasil; menunggu review

## Ringkasan

Tim melanjutkan fondasi aplikasi CrowdCast dengan scaffold frontend Next.js dan verifikasi otomatis untuk backend serta frontend. Frontend menyediakan halaman awal dan endpoint `GET /health`. Konfigurasi alias Vitest diperbaiki agar pengujian route handler dapat berjalan. Workflow GitHub Actions diperluas untuk menjalankan pengujian backend, pengujian frontend, pemeriksaan TypeScript, lint, dan build produksi.

Backend FastAPI telah tersedia pada `main` melalui [PR #35](https://github.com/rsyarsya/CrowdCast/pull/35). Scaffold frontend dan perbaikan test berada pada [PR #36](https://github.com/rsyarsya/CrowdCast/pull/36), sementara CI dan laporan ini disiapkan pada [draft PR #37](https://github.com/rsyarsya/CrowdCast/pull/37). PR #37 bergantung pada penyelesaian PR #36. Keduanya menunggu approval anggota lain sebelum Squash and Merge; scaffold frontend belum dinyatakan terintegrasi pada `main` saat laporan ini disusun.

## Deliverable

| Deliverable | Bukti | Status |
| --- | --- | --- |
| Scaffold frontend Next.js dan TypeScript | [PR #36](https://github.com/rsyarsya/CrowdCast/pull/36), commit `acb6394` | Tersedia pada branch `540091` |
| Konfigurasi alias Vitest | Commit `00e067b` pada PR #36 | Test lokal lulus |
| CI backend dan frontend | Commit `31d27bc` pada PR #37 | Ketiga job lulus di GitHub Actions |
| Laporan verifikasi Week 6 | Dokumen ini | Menunggu review |

## Hasil Pengujian Lokal

Pemeriksaan dilakukan pada Windows dengan Python 3.12.14 dan Node.js 22.21.0, setelah instalasi dependency dari requirements dan lockfile repository.

| Pemeriksaan | Hasil |
| --- | --- |
| Backend: `python -m pytest -q` | 1 test lulus, 1 warning deprecation |
| Frontend: `npm ci` | Instalasi berhasil |
| Frontend: `npm run test` | 1 test lulus |
| Frontend: `npm run typecheck` | Lulus |
| Frontend: `npm run lint` | Lulus |
| Frontend: `npm run build` | Build produksi berhasil |

Test backend dan frontend memeriksa `GET /health` secara terpisah dengan HTTP 200 dan JSON `{"status":"ok"}`. Pengujian ini memvalidasi respons dasar aplikasi; koneksi jaringan frontend–backend belum diuji.

## Verifikasi GitHub Actions

Workflow tetap berjalan pada push ke `main`/`dev` dan PR menuju kedua branch tersebut. Tiga job independen menggunakan Ubuntu dengan timeout 10 menit:

- `repository-check`: pemeriksaan struktur repository dan conflict marker.
- `backend-test`: Python 3.12, instalasi requirements, dan pytest; cache pip mengikuti file requirements.
- `frontend-check`: Node.js 22, instalasi lockfile dengan `npm ci`, Vitest, TypeScript, ESLint, dan build; cache npm mengikuti lockfile.

Ketiga job berhasil pada [run 37178062762](https://github.com/rsyarsya/CrowdCast/actions/runs/37178062762), yang menguji commit `31d27bc` pada 4 Oktober 2026. Hasil lokal di atas dicatat terpisah dari hasil CI. Penambahan laporan ini akan memicu pemeriksaan ulang pada commit dokumentasi terbaru.

## Kontribusi Berdasarkan Commit

| Anggota | Bukti dan kontribusi |
| --- | --- |
| Ghaisan Rifqi Kamiel (`GhaisaniCan`) | Commit `acb6394`: scaffold frontend, route health, test, dan tooling awal. |
| Rasyadwa Arsya Irnantyanto (`rsyarsya`) | Commit `00e067b`: perbaikan alias Vitest; commit `31d27bc`: integrasi CI; penyusunan laporan verifikasi Week 6. |
| Raditya Azhar Ananta (`raditazar`) | PR #35: fondasi backend dan test health yang digunakan sebagai dasar verifikasi minggu ini. |

## Kendala dan Batas Verifikasi

- Test frontend awal gagal karena alias `@/` belum dikenali Vitest; konfigurasi alias telah ditambahkan dan test kembali lulus.
- Backend menghasilkan warning deprecation Starlette/httpx; warning tidak menyebabkan kegagalan test saat ini.
- Instalasi frontend memberikan peringatan deprecation dependency. Tidak dilakukan upgrade dependency dalam pekerjaan ini.
- Modul konfigurasi, database, dan security yang belum diaktifkan masih membutuhkan kelengkapan dependency dan verifikasi tersendiri. Kelulusan test health tidak mencakup modul tersebut.
- Database, autentikasi, pemrosesan video/AI, penghitungan orang, klasifikasi, prediksi, dashboard monitoring, dan cloud belum dinyatakan selesai.
- Persetujuan anggota lain diperlukan agar PR #36 dan PR #37 dapat di-merge mengikuti workflow tim.

## Tindak Lanjut

- Selesaikan review PR #36, lalu Squash and Merge tanpa menghapus branch NIU.
- Sinkronkan `534714` dengan `origin/main`, periksa diff PR #37, dan pastikan CI pada commit terbaru berhasil sebelum review akhir dan merge.
- Pertahankan [Issue #25](https://github.com/rsyarsya/CrowdCast/issues/25) terbuka karena functional testing seluruh MVP belum selesai.
- Lanjutkan kontrak API/data, endpoint monitoring, serta kelengkapan dependency dan pengujian modul backend secara bertahap.
