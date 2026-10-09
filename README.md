# CrowdCast

CrowdCast adalah proyek Senior Project Teknologi Informasi DTETI UGM untuk pemantauan dan prediksi kepadatan kerumunan berbasis video/CCTV. Target MVP mencakup deteksi dan penghitungan orang, status **Sepi, Normal, atau Ramai**, riwayat monitoring, dan prediksi jangka pendek melalui dashboard web. Produk akhir ditujukan untuk mengintegrasikan **jaringan komputer, komputasi awan, dan kecerdasan buatan**.

## Status Implementasi

Per 4 Oktober 2026, aplikasi menyediakan scaffold FastAPI dan Next.js, halaman awal frontend, endpoint `GET /health` pada masing-masing aplikasi, serta CI untuk pengujian, lint, dan build.

Database, autentikasi, pipeline video/AI, penghitungan orang, klasifikasi, prediksi, dashboard monitoring, dan integrasi frontend–backend belum tersedia sebagai alur end-to-end. Pengembangan awal bersifat **local-first**; recorded video menjadi fallback resmi bila live CCTV tidak tersedia. Cloud tetap menjadi requirement produk akhir.

## Organisasi Repository

| Lokasi | Tanggung jawab |
| --- | --- |
| [frontend/](frontend/README.md) | Antarmuka Next.js, route frontend, dan test frontend. |
| [backend/](backend/README.md) | API FastAPI, test backend, dan fondasi penyimpanan serta pemrosesan. |
| [docs/](docs/index.md) | Requirement, desain, data simulasi, progress, dan sumber GitHub Pages. |
| [.github/workflows/](.github/workflows/main.yml) | Pemeriksaan repository, test, lint, dan build otomatis. |

Frontend dan backend memiliki dependency masing-masing. Struktur dipertahankan di root; belum diperlukan workspace npm atau pemindahan aplikasi ke `apps/`. Tambahkan modul mengikuti kebutuhan implementasi, bukan folder kosong untuk fitur yang belum tersedia.

## Pengembangan Lokal

1. Clone repository dan masuk ke root:

   ```powershell
   git clone https://github.com/rsyarsya/CrowdCast.git
   cd CrowdCast
   ```

2. Ikuti [panduan backend](backend/README.md) menggunakan Python 3.12. Server berjalan pada `http://localhost:8000`; Swagger UI tersedia pada `/docs`.
3. Pada terminal terpisah, ikuti [panduan frontend](frontend/README.md) menggunakan Node.js 22 dan npm. Aplikasi berjalan pada `http://localhost:3000`.

Kedua endpoint `/health` memeriksa aplikasi masing-masing. Menjalankan kedua server belum menghubungkan frontend dengan backend. File `.env.example` menyiapkan konfigurasi untuk fitur berikutnya; scaffold aktif belum menggunakannya.

## Verifikasi

Perintah pengujian tersedia pada README masing-masing aplikasi. [CrowdCast CI](.github/workflows/main.yml) menjalankan tiga job independen:

- `repository-check`: struktur repository dan conflict marker.
- `backend-test`: instalasi requirements dan pytest pada Python 3.12.
- `frontend-check`: `npm ci`, Vitest, TypeScript, ESLint, dan production build pada Node.js 22.

CI dipicu pada PR menuju `main`/`dev` dan push ke kedua branch tersebut. GitHub Pages menerbitkan dokumentasi dari `docs/`; aplikasi Next.js dan server FastAPI belum dideploy melalui Pages.

## Dokumentasi Proyek

- [GitHub Pages](https://rsyarsya.github.io/CrowdCast/) dan [sumber dokumentasi](docs/index.md).
- [Week 5: fondasi backend dan keputusan stack](docs/progress/week-05.md).
- [Week 6: verifikasi backend/frontend dan CI](docs/progress/week-06.md).
- [Rancangan data monitoring](docs/design/monitoring-data.md).
- [Issue](https://github.com/rsyarsya/CrowdCast/issues) dan [Project Board](https://github.com/users/rsyarsya/projects/2).

Laporan progress merekam keadaan saat disusun. Status review atau merge terbaru tersedia pada PR yang ditautkan di laporan.

## Kontribusi dan Workflow Git

Gunakan branch anggota permanen: `534714` (Rasyadwa), `539913` (Raditya), dan `540091` (Ghaisan). Semua perubahan masuk ke `main` melalui PR. Jangan direct push atau force push ke `main`, dan jangan force push ke branch anggota lain.

1. Selesaikan PR aktif sebelum memulai tugas berikutnya pada branch NIU yang sama.
2. Dengan working tree bersih, sinkronkan branch sebelum tugas baru. Contoh untuk `534714`:

   ```powershell
   git fetch origin
   git switch 534714
   git merge origin/534714
   git merge origin/main
   git push origin 534714
   ```

3. Kerjakan satu tugas per PR, periksa diff, stage file secara eksplisit, dan jalankan pemeriksaan relevan. Pisahkan perubahan logis ke commit Conventional Commits berbahasa Inggris, misalnya `docs(readme): clarify local setup instructions`.
4. Push ke branch NIU, lalu buat PR menuju `main` secara eksplisit. Push tidak otomatis membuat PR baru.
5. Dapatkan minimal satu approval anggota lain dan pastikan pemeriksaan berhasil. Gunakan **Squash and Merge** dan pertahankan branch NIU.

Jangan commit `.env`, credential, model weights, dataset besar, dependency lokal, atau hasil build. Gunakan placeholder pada `.env.example` dan `git revert` untuk membatalkan perubahan yang sudah masuk `main`.

## Pengembangan Backend

Lihat [panduan menjalankan dan menguji backend](backend/README.md) serta [progres Week 5](docs/progress/week-05.md). Kerangka awal menyediakan `/health`; database, autentikasi, dan AI belum diintegrasikan.

## Kelompok 03 LabDas 1

- Rasyadwa Arsya Irnantyanto — 24/534174/TK/59283
- Ghaisan Rifqi Kamiel — 24/540091/TK/59899
- Raditya Azhar Ananta — 24/539913/TK/59881
