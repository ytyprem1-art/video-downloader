# 🎬 Ultimate Video Downloader + Stats

Aplikasi GUI downloader custom yang ringan, praktis, dan dilengkapi dengan fitur otomatis optimasi file video.

> ⚠️ **IMPORTANT NOTE (Just For Fun):** 
> Project ini dibuat murni untuk keperluan belajar koding (edukasi), eksperimen GUI Tkinter, dan seru-seruan saja (*just for fun*). Tidak ada niat komersial, pelanggaran hak cipta, ataupun plagiarisme di dalam project ini. Kami sangat menghormati para pengembang library open-source asli!

---

## 💡 Informasi Project & Credits
Program ini dibangun dengan memanfaatkan beberapa kode publik (*public code*) dan library open-source luar biasa yang tersedia secara gratis di internet, serta dikembangkan dengan bantuan kecerdasan buatan:

* **yt-dlp**: Digunakan sebagai engine utama untuk mendownload video umum dari YouTube dan berbagai media sosial pada Tab 1.
* **phub (Engine v5.1.2)**: Digunakan sebagai engine khusus di Tab 2. 
    * *Source Asli Library:* Project ini menggunakan core API dari [EchterAlsFake/unofficial-api-for-pornhub](https://github.com/EchterAlsFake/unofficial-api-for-pornhub). Big thanks dan apresiasi setinggi-tingginya kepada kreator asli atas library Python-nya yang luar biasa!
* **FFmpeg**: Berperan penting di latar belakang untuk melakukan ritual *auto-fix* index video hasil download agar lancar jaya dan tidak mengalami *freeze* saat di-fast forward.
* **AI Collaboration**: Project ini dirancang, di-debug dari error spasi/indentasi, dan disempurnakan fiturnya (seperti sistem pipa log hitam *real-time* dan detektor otomatis koneksi macet) dengan bantuan **AI (Gemini)** sebagai partner diskusi coding harian.

---

## 🚀 Cara Pakai (Versi Standalone EXE)
Jika Anda malas menjalankan file python mentah, silakan langsung download versi matangnya di tab **Releases** di sebelah kanan halaman ini!
1. Pastikan koneksi internet / VPN Anda (seperti Cloudflare WARP) sudah menyala.
2. Download file `.zip` dari menu *Releases*, lalu ekstrak.
3. Jalankan `tk_downloader -FINAL.exe`.
4. Jika di tengah jalan proses download macet (terbaca *Request Error*), cukup **Restart Aplikasi** Anda untuk mereset antrean memori.
