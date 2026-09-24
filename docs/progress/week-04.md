# Progress Week 4

**Periode:** 18–24 September 2026<br>
**Status:** Rancangan awal tersedia

## Ringkasan

Pada Week 4, tim melanjutkan perencanaan teknis dengan menyusun alur pemrosesan video dan kebutuhan data monitoring. Diagram alur menghubungkan input video, hasil penghitungan orang, status keramaian, penyimpanan, serta tampilan monitoring dan riwayat. Rancangan data melengkapi alur tersebut dengan atribut yang akan digunakan dashboard.

Hasil minggu ini berupa artefak perancangan dan data simulasi. Implementasi pemrosesan video, API, penyimpanan, serta integrasi dashboard belum dinyatakan selesai.

## Deliverable

| Deliverable | Status | Tautan |
| --- | --- | --- |
| Diagram alur pemrosesan video | Rancangan selesai disusun | [Alur Pemrosesan Video](../images/week-04-video-processing-flow.png) |
| Tabel atribut monitoring | PROPOSED | [Struktur Data Monitoring](../design/monitoring-data.html) |
| Contoh data monitoring | Simulasi tersedia | [JSON Simulasi](../data/monitoring-simulation.json) |

## Progress yang Dilaporkan

### Alur Pemrosesan Video

- Menyusun urutan pengambilan frame dan waktu pengamatan, deteksi orang, penghitungan, penentuan status, serta penyimpanan hasil.
- Menambahkan percabangan jumlah nol ketika tidak ada orang terdeteksi pada frame yang diproses.
- Menghubungkan data tersimpan dengan monitoring, riwayat, dan prediksi secara konseptual.
- Menyiapkan penggunaan video rekaman sebagai input pengujian awal.

### Struktur Data Monitoring

- Mengidentifikasi lima atribut dashboard: `camera_id`, `location`, `timestamp`, `people_count`, dan `crowd_status`.
- Menentukan makna atribut, tipe data dasar, dan contoh nilai tanpa mengunci pilihan framework atau database.
- Menyusun tiga contoh pengamatan dalam JSON untuk menggambarkan perubahan kondisi satu kamera.
- Memeriksa format JSON, konsistensi atribut, dan waktu pengamatan. Status keramaian pada contoh masih bersifat ilustratif.

## Kontribusi Anggota

| Anggota | Kontribusi yang dilaporkan |
| --- | --- |
| Rasyadwa Arsya Irnantyanto | Menentukan cakupan alur video, menyusun tahapan pemrosesan, dan mendokumentasikan rancangan. |
| Raditya Azhar Ananta | Berkolaborasi dalam flowchart dan peninjauan percabangan deteksi, serta menyusun tabel atribut dan JSON simulasi monitoring. |

## Kendala

- Akses CCTV langsung belum dipastikan; video rekaman menjadi input pengujian awal.
- Threshold Sepi, Normal, dan Ramai belum ditetapkan berdasarkan lokasi atau data pengujian.
- Metode prediksi masih perlu ditentukan setelah kebutuhan dan ketersediaan data diperjelas.

## Tindak Lanjut

- Meninjau rancangan data bersama tim agar sesuai dengan kebutuhan tampilan dan hasil pemrosesan video.
- Menentukan video rekaman yang akan digunakan dan memulai pengujian alur deteksi serta penghitungan.
- Menetapkan aturan klasifikasi berdasarkan karakteristik lokasi dan hasil pengujian.
- Menyepakati stack serta kontrak API sebelum implementasi backend dan penyimpanan.
