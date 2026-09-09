# CrowdCast

## Project Senior Project TI

**Departemen Teknologi Elektro dan Teknologi Informasi**  
Fakultas Teknik  
Universitas Gadjah Mada

## Anggota Kelompok

- Nama 1 — NIM
- Nama 2 — NIM
- Nama 3 — NIM
- Nama 4 — NIM

---

## Nama Produk

**CrowdCast**

## Jenis Produk

Sistem monitoring dan prediksi kepadatan kerumunan berbasis web yang
mengintegrasikan jaringan komputer, dan artificial
intelligence.

## Latar Belakang dan Permasalahan

Keramaian pada kampus, tempat wisata, pusat perbelanjaan, ruang publik, dan lokasi acara dapat berubah dalam waktu singkat. Jika tidak dipantau dengan baik, kondisi tersebut dapat menyebabkan antrean, menurunkan kenyamanan pengunjung, menghambat operasional, serta meningkatkan risiko keselamatan.

Meskipun banyak lokasi telah memiliki CCTV, pemanfaatannya masih bergantung pada pengamatan manual. Petugas harus memantau video secara terus-menerus untuk mengetahui kondisi suatu area. Cara ini kurang efisien dan belum memberikan informasi kuantitatif mengenai jumlah orang atau tingkat keramaian secara cepat. Sistem people counting sederhana juga umumnya hanya menunjukkan kondisi saat ini, sehingga pengelola belum dapat mengantisipasi peningkatan keramaian.

Berdasarkan permasalahan tersebut, dibutuhkan sistem yang dapat menganalisis video CCTV secara otomatis, menghitung jumlah orang, mengklasifikasikan kondisi area menjadi Sepi, Normal, atau Ramai, serta memberikan prediksi keramaian dalam beberapa menit ke depan. Pada tahap awal, sistem dikembangkan dan dijalankan secara lokal untuk mengurangi kebutuhan biaya cloud serta mempermudah proses pengujian menggunakan CCTV maupun recorded video.

## Ide Solusi

Solusi yang diusulkan adalah **CrowdCast**, yaitu sistem pemantauan keramaian berbasis kecerdasan buatan yang memproses video CCTV secara lokal pada komputer atau perangkat *edge*. Sistem menggunakan model YOLO untuk mendeteksi manusia dan ByteTrack untuk melacak objek antar-frame agar jumlah orang dapat dihitung dengan lebih stabil.

Jumlah orang yang terdeteksi pada area tertentu dianalisis menggunakan *region of interest* dan *rolling average*, kemudian diklasifikasikan menjadi tiga kondisi, yaitu Sepi, Normal, dan Ramai. Sistem juga menyimpan riwayat jumlah orang secara lokal dan menggunakannya untuk memperkirakan kondisi keramaian dalam 5, 15, dan 30 menit berikutnya.

Hasil analisis ditampilkan melalui *dashboard* lokal yang berisi jumlah orang, status keramaian, tren perubahan, dan peringatan apabila area sedang atau diperkirakan menjadi ramai. Sistem dapat menerima CCTV secara langsung melalui RTSP maupun recorded video yang diputar sebagai simulasi aliran CCTV. Pada tahap pengembangan saat ini, video dan data analitik tidak dikirim ke cloud sehingga pemrosesan dapat dilakukan dengan biaya yang lebih rendah dan privasi video lebih terjaga.

## Analisis Kompetitor

Kompetitor CrowdCast dapat dibagi menjadi tiga kategori, yaitu pemantauan CCTV manual, sistem people counting sederhana, dan platform video surveillance berbasis AI seperti 3dEYE. Pemantauan manual bergantung pada perhatian petugas dan tidak menghasilkan analisis otomatis. Sistem people counting sederhana dapat menghitung jumlah orang, tetapi biasanya belum menyediakan prediksi keramaian atau rekomendasi tindakan operasional.

3dEYE memiliki fitur yang lebih luas, seperti pengelolaan banyak kamera, penyimpanan video, pelacakan objek, people counting, analitik okupansi, dan notifikasi keamanan. Namun, 3dEYE berfokus pada platform video surveillance berskala luas, sedangkan CrowdCast difokuskan pada pemantauan keramaian dan prediksi jangka pendek untuk satu lokasi dengan kebutuhan yang lebih sederhana.

CrowdCast memiliki keunggulan berupa pemrosesan lokal, kebutuhan infrastruktur yang lebih ringan, fokus pada klasifikasi dan prediksi keramaian, serta penyajian informasi yang langsung mendukung keputusan operasional. Keterbatasannya adalah sistem belum mendukung pengelolaan banyak lokasi dan belum menggunakan cloud computing, sehingga akses jarak jauh dan skalabilitasnya masih terbatas.