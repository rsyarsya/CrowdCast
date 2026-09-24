# Perancangan Struktur Data Monitoring

**Kontributor:** Raditya Azhar Ananta — Backend dan AI Engineer  
**Periode:** Week 4, 18–24 September 2026  
**Status rancangan:** PROPOSED

## Tujuan

Menentukan data monitoring yang dibutuhkan dashboard CrowdCast sebagai acuan awal pertukaran data antara AI, backend, dan frontend. Satu objek mewakili kondisi satu kamera atau sumber video pada satu waktu pengamatan.

Rancangan ini mengikuti baseline Camera dan CrowdRecord pada [dokumentasi proyek](../index.html#entity-relationship-diagram). Penentuan framework, database, endpoint API, dan implementasi model AI berada di luar pekerjaan ini.

## Tabel Atribut

Semua atribut berikut wajib tersedia pada setiap objek simulasi.

| Kebutuhan dashboard | Atribut | Tipe data logis | Representasi JSON | Makna dan aturan | Contoh nilai |
| --- | --- | --- | --- | --- | --- |
| ID kamera | `camera_id` | String | String | Identitas kamera/sumber video; tidak kosong dan tetap sama untuk sumber yang sama. | `"CAM-01"` |
| Lokasi | `location` | String | String | Nama area yang dipantau kamera; tidak kosong. | `"Lobi Gedung A"` |
| Waktu pencatatan | `timestamp` | Datetime dengan zona waktu | String ISO 8601 | Waktu pengamatan yang diwakili data, bukan waktu data diterima dashboard. Contoh menggunakan WIB (`+07:00`). | `"2026-09-23T10:00:00+07:00"` |
| Jumlah orang | `people_count` | Integer nonnegatif | Number bernilai bulat | Jumlah orang pada saat pengamatan, bukan akumulasi pengunjung. Nilai minimal `0`; nol berarti pengamatan tanpa orang, bukan kegagalan pengamatan. | `18` |
| Status keramaian | `crowd_status` | String dengan pilihan terbatas | String | Hanya `"Sepi"`, `"Normal"`, atau `"Ramai"`, dengan kapitalisasi tersebut. | `"Normal"` |

JSON tidak memiliki tipe datetime atau integer terpisah. Datetime direpresentasikan sebagai string, sedangkan integer dikirim sebagai number tanpa bagian pecahan. Tipe kolom penyimpanan belum ditentukan.

## Hubungan dengan Model Data

- `camera_id` menghubungkan pengamatan dengan Camera; `location` berasal dari metadata Camera.
- `timestamp`, `people_count`, dan `crowd_status` mengikuti atribut pengamatan pada CrowdRecord.
- Lokasi disertakan dalam objek dashboard agar identitas area dapat ditampilkan bersama hasil pengamatan. Ini bukan keputusan untuk menduplikasi lokasi pada tabel CrowdRecord.
- `record_id` pada baseline penyimpanan tidak ditambahkan ke contoh karena tugas ini hanya mencakup lima atribut dashboard yang diminta. Rancangan ini tidak menghapus atribut tersebut dari baseline.

## Data Simulasi dan Asumsi

Bukti contoh tersedia di [monitoring-simulation.json](../data/monitoring-simulation.json), berupa array tiga objek pengamatan:

| Kamera | Lokasi fiktif | Waktu pengamatan (WIB) | Jumlah orang | Status ilustratif |
| --- | --- | --- | --- | --- |
| CAM-01 | Lobi Gedung A | 23 September 2026, 10:00:00 | 0 | Sepi |
| CAM-01 | Lobi Gedung A | 23 September 2026, 10:01:00 | 18 | Normal |
| CAM-01 | Lobi Gedung A | 23 September 2026, 10:02:00 | 37 | Ramai |

Seluruh nilai dibuat untuk simulasi, bukan hasil deteksi AI atau pengamatan CCTV. Label status diisi secara ilustratif; pasangan jumlah dan status di atas tidak menetapkan rentang klasifikasi.

- **DECIDED:** Istilah status mengikuti proyek: Sepi, Normal, dan Ramai.
- **PROPOSED:** Lima atribut dan representasinya menjadi rancangan awal data dashboard.
- **Asumsi simulasi:** Satu kamera, satu lokasi fiktif, zona waktu WIB, dan selang waktu satu menit. Selang ini bukan keputusan interval pencatatan sistem.
- **TBD:** Threshold klasifikasi berdasarkan lokasi/data serta pemilihan stack dan penyimpanan.

## Pemeriksaan Bukti

Periksa bahwa file dapat dibaca parser JSON, setiap objek memiliki tepat lima atribut sesuai tabel, jumlah orang berupa bilangan bulat nonnegatif, timestamp valid dan berzona waktu, serta status hanya menggunakan tiga istilah resmi. Ketiga objek harus terurut berdasarkan waktu, mengacu pada kamera/lokasi yang sama, dan mencakup ketiga status serta jumlah orang nol.

Pemeriksaan ini memvalidasi struktur dan konsistensi contoh; tidak menguji akurasi AI atau kebenaran threshold klasifikasi.
