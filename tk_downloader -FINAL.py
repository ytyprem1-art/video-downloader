import os
import sys
import threading
import tkinter as tk
import random
import urllib.request
import webbrowser
import pyperclip
import asyncio
import time
from urllib.parse import urlparse, parse_qs
from phub import Client
from tkinter import messagebox, filedialog
from tkinter.scrolledtext import ScrolledText
from tkinter.ttk import Progressbar, Combobox, Notebook

# --- Cek Module ---
try:
    import pyperclip
    # Kita tidak perlu import YoutubeDL sebagai library lagi karena memakai .exe eksternal
except ImportError:
    messagebox.showerror("Error", "Module kurang. Install: pip install pyperclip")
    sys.exit()

# --- Setup Path & FFmpeg / yt-dlp Eksternal (Mode 1 Folder) ---
# Karena ini mode folder, base_path akan mengarah ke tempat .exe GUI berada
base_path = os.path.dirname(os.path.abspath(sys.argv[0]))

ffmpeg_path = os.path.join(base_path, "ffmpeg", "bin")
os.environ["PATH"] += os.pathsep + ffmpeg_path

# Path absolut mengarah ke yt-dlp.exe yang satu folder dengan aplikasi
ytdlp_bin_path = os.path.join(base_path, "yt-dlp.exe")

# --- FUNGSI FORMAT SIZE ---
def format_size(bytes_size):
    if bytes_size is None: return "N/A"
    for unit in ['B', 'KiB', 'MiB', 'GiB']:
        if bytes_size < 1024.0: return f"{bytes_size:.2f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.2f} TiB"

# --- FUNGSI CARI PROXY ---
def get_auto_proxies(status_label):
    status_label.config(text="Mengambil list proxy...", fg="orange")
    urls = [
        "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=5000&country=all&ssl=all&anonymity=all",
        "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=socks5&timeout=5000&country=all&ssl=all&anonymity=all"
    ]
    all_proxies = []
    for api in urls:
        try:
            with urllib.request.urlopen(api) as response:
                data = response.read().decode('utf-8')
                found = [x.strip() for x in data.strip().split('\n') if x.strip()]
                prefix = "http://" if "protocol=http" in api else "socks5://"
                all_proxies.extend([prefix + p for p in found])
        except: continue
    return all_proxies

# --- FUNGSI POPUP SUKSES ---
def show_success_popup(folder_path):
    popup = tk.Toplevel(root)
    popup.title("Sukses")
    popup.geometry("450x180")
    try: popup.iconbitmap(os.path.join(base_path, "icon.ico"))
    except: pass
    
    msg = f"Mantap! Download Selesai.\nFile tersimpan di:\n{folder_path}"
    lbl = tk.Label(popup, text=msg, wraplength=420, padx=20, pady=20, font=("Arial", 10))
    lbl.pack()
    
    btn_frame = tk.Frame(popup)
    btn_frame.pack(pady=10)
    
    def open_folder():
        try: os.startfile(folder_path)
        except: pass
        popup.destroy()
        
    btn_open = tk.Button(btn_frame, text="📂 Buka Folder", command=open_folder, bg="#e0f7fa", width=15, height=2)
    btn_open.pack(side=tk.LEFT, padx=10)
    btn_ok = tk.Button(btn_frame, text="OK", command=popup.destroy, width=10, height=2)
    btn_ok.pack(side=tk.LEFT, padx=10)

# --- FUNGSI DOWNLOAD UTAMA MENGGUNAKAN ENGINE EKSTERNAL (REAL-TIME PROGRESS) ---
def download_video(url, output_dir, progress_var, resolution, mode, manual_proxy, status_label, stats_label):
    import subprocess
    import re
    
    # Ambil list file di folder sebelum download dimulai untuk pengecekan fisik nanti
    try: files_before = set(os.listdir(output_dir))
    except Exception: files_before = set()
    
    # Validasi fisik eksistensi core engine
    if not os.path.exists(ytdlp_bin_path):
        status_label.config(text="Error Engine Hilang", fg="red")
        messagebox.showerror("Error", "File 'yt-dlp.exe' tidak ditemukan!\nHarap taruh file yt-dlp.exe di dalam folder aplikasi.")
        return

    # Clean up file sementara (.part)
    for f in os.listdir(output_dir):
        if f.endswith('.part'):
            try: os.remove(os.path.join(output_dir, f))
            except: pass

    # Penanganan Kriteria Format Resolusi
    selected_res_code = resolution.split(' ')[0]
    if selected_res_code != "best" and selected_res_code != "MP3":
        ydl_format = f'bestvideo[height<={selected_res_code}]+bestaudio/best'
    elif selected_res_code == "MP3":
        ydl_format = 'bestaudio/best'
    else:
        ydl_format = 'bestvideo+bestaudio/best'
        
    fix_ffmpeg_dir = os.path.normpath(ffmpeg_path)

# Bangun argumen command line murni tanpa argumen postprocessor yang bikin crash
    cmd = [
        ytdlp_bin_path,
        url,
        "-f", ydl_format,
        "-o", os.path.join(output_dir, "%(title).100s - %(id)s.%(ext)s"),
        "--no-overwrites",
        "--continue",
        "--ffmpeg-location", fix_ffmpeg_dir,
        # TRICK AMAN: Biarkan yt-dlp nge-merge bebas, lalu remux otomatis hasilnya ke mp4 standar
        "--remux-video", "mp4",
        "--extractor-args", "youtube:player_client=default"
    ]
    
    if selected_res_code == "MP3":
        cmd.extend(["-x", "--audio-format", "mp3", "--audio-quality", "192K"])

    # Logika Sistem Proxy / Direct
    if mode == "Manual" and manual_proxy.strip():
        raw_p = manual_proxy.strip()
        if not raw_p.startswith("http") and not raw_p.startswith("socks"): raw_p = "http://" + raw_p
        cmd.extend(["--proxy", raw_p])
    elif mode == "Auto":
        pool = get_auto_proxies(status_label)
        if pool:
            random.shuffle(pool)
            cmd.extend(["--proxy", pool[0]])

    status_label.config(text="Menghubungkan ke server...", fg="blue")
    stats_label.config(text="Starting...", fg="gray")

    try:
        # FIX PAMUNGKAS: Duplikat environment sistem dan suntikkan PATH FFmpeg secara paksa ke dalam Popen
        sistem_env = os.environ.copy()
        sistem_env["PATH"] = fix_ffmpeg_dir + os.pathsep + sistem_env.get("PATH", "")

        # PENGATURAN POPEN dengan injeksi env=sistem_env
        process = subprocess.Popen(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.STDOUT, 
            text=True, 
            bufsize=1, 
            universal_newlines=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
            env=sistem_env # <-- Ini yang bikin yt-dlp.exe dipaksa melek melihat FFmpeg!
        )
        
        title_found = "Video/Audio"
        
        # Baca output yt-dlp secara live selama proses mendownload
        while True:
            line = process.stdout.readline()
            if not line and process.poll() is not None:
                break
                
            if not line:
                continue

            clean_line = line.strip()

            if "[download] Destination:" in clean_line:
                filename = os.path.basename(clean_line.split("Destination:")[1].strip())
                title_found = filename[:40] + "..."
                status_label.config(text=f"Mendownload: {title_found}", fg="blue")

            progress_match = re.search(r'\[download\]\s+(\d+\.\d+)%\s+of\s+([^\s]+)\s+at\s+([^\s]+)', clean_line)
            
            if progress_match:
                pct = float(progress_match.group(1))
                total_size = progress_match.group(2)
                speed = progress_match.group(3)
                
                progress_var.set(int(pct))
                stats_text = f"{pct}% | Total ~{total_size} | Speed: {speed}"
                stats_label.config(text=stats_text, fg="#006400")
                
            elif "[download] 100%" in clean_line or "Merging formats" in clean_line:
                progress_var.set(100)
                status_label.config(text="Memproses / Menggabungkan Audio Video...", fg="blue")
                stats_label.config(text="Sedikit lagi selesai...", fg="blue")

        # --- PROCESS WAIT SEBELUM CEK FISIK ---
        process.wait() 

        # Cek apakah ada file fisik baru berformat mp4 atau mp3 yang berukuran valid (> 10 KB)
        try:
            files_after = set(os.listdir(output_dir))
            new_files = files_after - files_before
        except Exception:
            new_files = set()
            
        valid_download = False
        for f in new_files:
            full_path = os.path.join(output_dir, f)
            if (f.endswith('.mp4') or f.endswith('.mp3') or f.endswith('.mkv')) and os.path.getsize(full_path) > 10240:
                valid_download = True
                break

        if valid_download or process.returncode == 0:
            progress_var.set(100)
            status_label.config(text="Semua Download Selesai!", fg="green")
            stats_label.config(text="100% Complete & Optimized", fg="green")
            root.after(0, lambda: show_success_popup(output_dir))
        else:
            raise Exception("Terjadi kendala saat mengunduh via engine eksternal.")
            
    except Exception as e:
        status_label.config(text="Gagal.", fg="red")
        stats_label.config(text="", fg="black")
        messagebox.showerror("Gagal Total", f"Proses Gagal.\nDetail: {str(e)[:150]}\n\nSolusi: Pastikan URL benar atau gunakan VPN.")
    
    progress_var.set(0)

# --- FUNGSI GUI ---
def start_download():
    url = url_entry.get() or pyperclip.paste()
    if not url: return messagebox.showwarning("Kosong", "URL Kosong!")
    
    if "spotify.com" in url: messagebox.showerror("Spotify Tidak Support", "Aplikasi ini TIDAK BISA download dari Spotify (DRM)."); return
    output_dir = filedialog.askdirectory()
    if not output_dir: return
    threading.Thread(target=download_video, args=(url, output_dir, progress_var, selected_res.get(), mode_var.get(), manual_proxy_entry.get(), status_label, stats_label), daemon=True).start()


def update_status(text, fg="black"):
    root.after(0, lambda: status_label.config(text=text, fg=fg))


def update_stats(text, fg="gray"):
    root.after(0, lambda: stats_label.config(text=text, fg=fg))


def update_status_adult(text, fg="white"):
    root.after(0, lambda: status_label_adult.config(text=text, fg=fg))


def update_stats_adult(text, fg="gray"):
    root.after(0, lambda: stats_label_adult.config(text=text, fg=fg))


class TextRedirector:
    def __init__(self, widget):
        self.widget = widget

    def write(self, text):
        if not text:
            return
        def append():
            self.widget.configure(state='normal')
            self.widget.insert(tk.END, text)
            self.widget.see(tk.END)
            self.widget.yview_moveto(1.0)
            self.widget.configure(state='disabled')
        root.after(0, append)

    def flush(self):
        pass


def update_progress_adult(value):
    root.after(0, lambda: progress_var_adult.set(value))


async def download_video_adult_async(url, output_dir):
    try:
        import phub
        import urllib.parse
        import subprocess
        import glob
        import asyncio
        
        # 1. Reset status visual awal
        status_label_adult.config(text="Status: Mengambil data video...", fg="#ff9900")
        progress_var_adult.set(5)
        root.update_idletasks()
        
        # Amankan stdout/stderr lama untuk dikembalikan nanti
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        
        # Bersihkan box log hitam sebelum mulai
        log_text_adult.configure(state='normal')
        log_text_adult.delete('1.0', tk.END)
        log_text_adult.configure(state='disabled')
        
        # Belokkan output print terminal ke box GUI
        sys.stdout = TextRedirector(log_text_adult)
        sys.stderr = TextRedirector(log_text_adult)

        # 2. NYALAKAN DETEKTIF SAKTI (Memantau error & kasih instruksi restart)
        is_downloading = True
        async def update_status_loop():
            titik = 0
            while is_downloading:
                tanda_titik = "." * (titik % 4)
                
                # Ambil seluruh teks yang ada di dalam kotak hitam GUI saat ini
                isi_log = log_text_adult.get("1.0", tk.END).lower()
                
                # Jika di dalam kotak hitam terdeteksi ada log eror request/timeout/curl
                if "request error" in isi_log or "timeout" in isi_log or "timed out" in isi_log:
                    status_label_adult.config(
                        text="⚠️ MACET! RESTART APLIKASI LU. Kalau masih error baru restart WARP/VPN!", 
                        fg="red", 
                        font=("Arial", 9, "bold")
                    )
                else:
                    # Kalau bersih, tetep tampilin status dinamis biasa
                    status_label_adult.config(
                        text=f"Status: Processing Engine 5.1.2{tanda_titik} (Cek Log di Bawah)", 
                        fg="#ff9900",
                        font=("Arial", 10, "normal")
                    )
                    
                cur_val = progress_var_adult.get()
                if cur_val < 85:
                    progress_var_adult.set(cur_val + 1)
                    
                root.update_idletasks()
                titik += 1
                await asyncio.sleep(0.8)

        # Langsung start loop detektifnya di background thread
        status_task = asyncio.create_task(update_status_loop())
        
        # 3. Proses API & Token
        client = phub.Client()
        video = await client.get_video(url)
        await video.ensure_html()
        judul_asli = video.title
        
        # 4. Proses Download Murni ke Folder Tujuan
        await video.download(quality="best", path=output_dir, no_title=False)
        
        # Matikan loop karena proses download sudah beres
        is_downloading = False
        await status_task
        
        # Kembalikan fungsi sistem stdout ke semula sebelum lanjut ke FFmpeg
        sys.stdout = old_stdout
        sys.stderr = old_stderr
        
        # 5. Cari file yang baru didownload di folder tujuan
        potongan_judul = "".join([c for c in judul_asli[:15] if c.isalnum() or c.isspace()]).strip()
        search_pattern = os.path.join(output_dir, f"*{potongan_judul}*.mp4")
        found_files = glob.glob(search_pattern)
        
        if not found_files:
            search_pattern = os.path.join(output_dir, "*.mp4")
            found_files = sorted(glob.glob(search_pattern), key=os.path.getmtime)
            
        if not found_files:
            raise FileNotFoundError("File hasil download tidak ditemukan oleh sistem.")
            
        file_mentah = found_files[-1]
        
        judul_bersih = "".join([c for c in judul_asli if c.isalnum() or c in ' -_']).strip()
        if not judul_bersih:
            parsed_url = urllib.parse.urlparse(url)
            queries = urllib.parse.parse_qs(parsed_url.query)
            viewkey = queries.get('viewkey', ['adult_video'])[0]
            judul_bersih = f"PHUB_{viewkey}"
            
        file_final = os.path.join(output_dir, f"{judul_bersih}_Fixed.mp4")
        if file_mentah.lower() == file_final.lower():
            file_final = os.path.join(output_dir, f"{judul_bersih}_Optimized.mp4")
        
        # 6. RITUAL AUTO-FIX FFMPEG (Hancurkan Bug Video Freeze!)
        status_label_adult.config(text="Status: Mengoptimalkan Index Video (FFmpeg)...", fg="#00ccff")
        progress_var_adult.set(90)
        root.update_idletasks()
        
        ffmpeg_exe = os.path.join(os.path.dirname(__file__), "ffmpeg", "ffmpeg.exe")
        if not os.path.exists(ffmpeg_exe):
            ffmpeg_exe = "ffmpeg"
            
        cmd = [
            ffmpeg_exe, "-y", "-i", file_mentah, 
            "-c", "copy", "-map_metadata", "0", "-movflags", "faststart", file_final
        ]
        
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        subprocess.run(cmd, startupinfo=startupinfo, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        if os.path.exists(file_mentah) and os.path.exists(file_final):
            os.remove(file_mentah)
            
        # 7. Selesai Sempurna!
        status_label_adult.config(text="Status: Download & Optimized Sukses! 🎉", fg="green")
        progress_var_adult.set(100)
        root.update_idletasks()
        
        messagebox.showinfo("Sukses", f"Mantap! Download Selesai & Video Mulus Teroptimasi.\n\nFile tersimpan di:\n{file_final}")
        
    except Exception as e:
        is_downloading = False
        progress_var_adult.set(0)
        err_text = str(e).lower()
        
        # Buka gembok kotak hitam biar bisa diisi manual jika lolos ke except fatal
        log_text_adult.configure(state='normal')
        log_text_adult.insert(tk.END, f"\n[FATAL ERROR]: {str(e)}\n")
        log_text_adult.insert(tk.END, "\n👉 SOLUSI: Close/Restart aplikasi downloader ini lalu coba lagi, bro!\n")
        log_text_adult.insert(tk.END, "   Kalau masih bandel mampet, baru restart Cloudflare WARP/VPN lu!\n")
        log_text_adult.see(tk.END)
        log_text_adult.configure(state='disabled')
        
        # Fallback teks merah tebal jika kena block except
        status_label_adult.config(text="⚠️ MACET! Close & Buka Ulang Aplikasinya!", fg="red")
        status_label_adult.config(font=("Arial", 10, "bold"))
            
        print(f"DEBUG ERROR: {str(e)}")
    finally:
        try:
            sys.stdout = old_stdout
            sys.stderr = old_stderr
        except NameError:
            pass


def start_download_adult():
    url = adult_url_entry.get() or pyperclip.paste()
    if not url: return messagebox.showwarning("Kosong", "URL Dewasa Kosong!")
    output_dir = filedialog.askdirectory()
    if not output_dir: return
    threading.Thread(target=lambda: asyncio.run(download_video_adult_async(url, output_dir)), daemon=True).start()


def toggle_manual_input():
    if mode_var.get() == "Manual":
        manual_proxy_entry.config(state="normal")
        tor_btn.config(state="normal", text="Dapatkan Tor Browser", command=open_tor_web)
    else:
        manual_proxy_entry.config(state="disabled")
        tor_btn.config(state="disabled", text="Dapatkan Tor Browser", command=open_tor_web) 

def open_tor_web(): webbrowser.open("https://www.torproject.org/download/")

def show_tutorial():
    top = tk.Toplevel(root)
    top.title("Panduan & Tips Proxy")
    top.geometry("500x750")
    try: top.iconbitmap(os.path.join(base_path, "icon.ico"))
    except: pass
    
    tor_proxy_ip = "socks5://127.0.0.1:9150"

    frame_tor_copy = tk.Frame(top)
    def copy_tor_ip():
        pyperclip.copy(tor_proxy_ip)
        messagebox.showinfo("Tersalin", f"IP {tor_proxy_ip} telah disalin!")

    def show_tor_explanation():
        tor_popup = tk.Toplevel(root)
        tor_popup.title("Cara Kerja Tor (The Onion Router)")
        tor_popup.geometry("550x700")
        try: tor_popup.iconbitmap(os.path.join(base_path, "icon.ico"))
        except: pass
        
        explanation_text = (
            "Jangan kaget kalau speed-nya lemot. Itu bukan karena komputer kamu, bukan karena Chrome dibuka, and bukan karena aplikasinya rusak.\n\n"
            "=== KENAPA TOR SANGAT LAMBAT? ===\n\n"
            "Koneksi Biasa (Direct): Komputer Kamu ➡ Server Video (Lurus, Cepat).\n"
            "Koneksi Tor: Komputer Kamu ➡ Komputer di Jerman ➡ Komputer di Rusia ➡ Komputer di Brazil ➡ Server Video.\n"
            "Data kamu dipantulkan ke **3 server acak (Relays)** di seluruh dunia sebelum sampai ke tujuan. Ini dilakukan supaya lokasi aslimu tidak bisa dilacak.\n\n"
            "*(CATATAN: Jerman, Rusia, Brasil hanyalah contoh. Relai Tor dipilih acak dari ribuan server di seluruh dunia.)*\n\n"
            "**Kelebihan:** Paling aman, tembus semua blokir, gratis.\n"
            "**Kekurangan:** Jarak tempuh data jadi jauh banget = **Speed Lelet.**\n\n"
            "----------------------------------------------------\n"
            "### Cara Kerja Tor (THE ONION ROUTER)\n\n"
            "1. Selalu **3 Relai**: Tor selalu merutekan koneksi kamu melalui **tiga server acak** yang disebut *relays* or *nodes*.\n\n"
            "2. **Node Masuk (Guard/Entry Node):** Tahu siapa kamu (IP asli), tapi tidak tahu apa yang kamu tuju.\n"
            "3. **Node Tengah (Middle Node):** Tidak tahu siapa kamu dan tidak tahu apa yang kamu tuju. Hanya meneruskan data.\n"
            "4. **Node Keluar (Exit Node):** Tahu apa yang kamu tuju (situs web), tapi tidak tahu siapa kamu (hanya melihat IP dari node tengah).\n\n"
            "**Acak & Berlapis:**\n"
            "Relai-relai ini dipilih secara acak. Seluruh data yang melewati mereka dienkripsi berlapis-lapis—seperti bawang bombay (onion). Inilah mengapa *downloading* terasa lambat, tetapi jaminan tembus blokirnya sangat tinggi.\n\n"
            "**Semua Aktivitas Sama:** Ya, bahkan untuk browsingan biasa, semua koneksi di Tor Browser selalu melewati tiga lapis relai acak ini."
        )
        tk.Label(tor_popup, text=explanation_text, justify="left", wraplength=520, padx=10, pady=10, font=("Arial", 9)).pack(anchor="w")
        tk.Button(tor_popup, text="Tutup", command=tor_popup.destroy).pack(pady=10)
    
    info_text_part1 = (
        "PANDUAN LENGKAP & TRIK RAHASIA\n\n"
        "1. MODE AUTO: Gacha proxy gratis (sering gagal).\n"
        "2. MODE MANUAL: Wajib untuk situs 18+.\n\n"
        "=== TRIK RAHASIA (TOR BROWSER) ===\n"
        "Ini cara GRATIS & PALING AMPUH tembus blokir:\n"
        "1. Download & Buka 'Tor Browser' lalu **klik connect** (biarkan terbuka).\n"
        "2. Di aplikasi ini, pilih 'Manual Proxy'.\n"
        "3. IP yang harus diisi di kolom proxy adalah:"
    )

    info_text_part2 = (
        "\n4. Klik Download. Dijamin tembus semua blokir!\n\n"
        "--------------------------------------------------\n"
        "JENIS-JENIS PROXY (WAJIB BACA!):\n\n"
        "1. NOA (Non-Anonymous): ❌ JANGAN PAKAI.\n"
        "Proxy ini 'jujur kacang ijo'. Dia bilang: 'Halo Pornhub, saya Proxy, dan ini IP asli si user dari Indonesia.'\n"
        "Akibat: Tetap kena blokir.\n\n"
        "2. ANM (Anonymous): ⚠️ LUMAYAN.\n"
        "Dia bilang: 'Halo, saya Proxy, tapi saya rahasikan IP asli user saya.'\n"
        "Akibat: Biasanya tembus, tapi situs tahu kamu pakai topeng.\n\n"
        "3. HIA (High Anonymous / Elite): ✅ TERBAIK.\n"
        "Dia bilang: 'Halo, saya user biasa.' (Dia pura-pura bukan proxy).\n"
        "Akibat: Website mengira itu koneksi murni. Paling ampuh.\n\n"
        "--------------------------------------------------\n"
        "CATATAN PENTING:\n"
        "Kalau pakai Auto/Manual masih tidak bisa, harap bersabar, resiko gratisan.\n\n"
        "SOLUSI TERAKHIR:\n"
        "Tolong aktifkan VPN di komputer kamu, lalu pilih mode 'Direct (Normal)' di aplikasi ini."
    )
    
    tk.Label(top, text=info_text_part1, justify="left", wraplength=480, padx=10, pady=10, font=("Arial", 9)).pack(anchor="w")
    
    tk.Label(frame_tor_copy, text=tor_proxy_ip, font=("Consolas", 10, "bold"), fg="blue").pack(side=tk.LEFT, padx=5)
    tk.Button(frame_tor_copy, text="📋 Salin", command=copy_tor_ip, font=("Arial", 8)).pack(side=tk.LEFT)
    tk.Button(frame_tor_copy, text="❓ Cara Kerja Tor", command=show_tor_explanation, font=("Arial", 8)).pack(side=tk.LEFT, padx=10)
    frame_tor_copy.pack(anchor="w", padx=15)
    
    tk.Label(top, text=info_text_part2, justify="left", wraplength=480, padx=10, pady=10, font=("Arial", 9)).pack(anchor="w")
    tk.Button(top, text="Tutup", command=top.destroy).pack(pady=10)

def show_supported_sites():
    top = tk.Toplevel(root)
    top.title("Daftar Situs Supported")
    top.geometry("450x600")
    try: top.iconbitmap(os.path.join(base_path, "icon.ico"))
    except: pass
    
    msg = (
        "Aplikasi ini menggunakan core yt-dlp yang mendukung RIBUAN situs.\n"
        "Berikut adalah daftar situs populer yang pasti bisa:\n\n"
        "🌍 SOSMED / UMUM:\n"
        "• YouTube, Facebook, Instagram\n"
        "• TikTok (No Watermark), Twitter (X)\n"
        "• Twitch, Vimeo, Dailymotion\n"
        "• Soundcloud, Bandcamp\n\n"
        "🔞 SITUS DEWASA (18+):\n"
        "• Pornhub, XVideos, XNXX\n"
        "• YouPorn, RedTube, Tube8\n"
        "• SpankBang, HentaiHaven\n"
        "• Dan ribuan situs tube lainnya...\n\n"
        "❌ NOT SUPPORTED:\n"
        "• Spotify (Enkripsi DRM)\n"
        "• Netflix/Disney+ (Enkripsi DRM)\n\n"
        "CATATAN:\n"
        "Untuk situs 18+, WAJIB menggunakan Proxy (Manual/Auto) atau VPN agar tidak error 'Timed Out' karena diblokir ISP."
    )
    
    lbl = tk.Label(top, text=msg, justify="left", padx=15, pady=15, font=("Arial", 10), wraplength=420)
    lbl.pack()
    tk.Button(top, text="OK, Mengerti", command=top.destroy).pack(pady=5)

# --- GUI SETUP ---
root = tk.Tk()
root.title("Ultimate Downloader + Stats")
root.geometry("420x700")

try:
    icon_path = os.path.join(base_path, "icon.ico")
    root.iconbitmap(icon_path)
except: pass

notebook = Notebook(root)
notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

frame_general = tk.Frame(notebook, bg="white")
tab_dewasa = tk.Frame(notebook, bg="#111111")
notebook.add(frame_general, text="🌍 Umum (YouTube/Sosmed)")
notebook.add(tab_dewasa, text="🔞 Khusus 18+ (PHub/XY)")

frame_top = tk.Frame(frame_general, bg="white")
frame_top.pack(pady=5)
tk.Button(frame_top, text="Panduan / Tutorial", command=show_tutorial, bg="#fffacd", fg="red").pack(side=tk.LEFT, padx=5)
tk.Button(frame_top, text="List Situs Supported", command=show_supported_sites, bg="#e0f7fa", fg="blue").pack(side=tk.LEFT, padx=5)

tk.Label(frame_general, text="Video URL:", bg="white").pack(pady=5)
url_entry = tk.Entry(frame_general, width=50)
url_entry.pack(pady=5)

tk.Label(frame_general, text="Format:", bg="white").pack(pady=5)
resolutions = ["best", "2160 (4K)", "1440 (2K)", "1080", "720", "480", "360", "MP3 (Audio Only)"]
selected_res = tk.StringVar(value="best")
Combobox(frame_general, textvariable=selected_res, values=resolutions, state="readonly").pack(pady=5)

tk.Label(frame_general, text="Pilih Mode Koneksi:", font=("Arial", 10, "bold"), bg="white").pack(pady=10)
mode_var = tk.StringVar(value="Direct")
frame_mode = tk.Frame(frame_general, bg="white")
frame_mode.pack()
tk.Radiobutton(frame_mode, text="Direct (Normal)", variable=mode_var, value="Direct", command=toggle_manual_input, bg="white").pack(anchor="w")
tk.Radiobutton(frame_mode, text="Auto Bypass (Gacha Proxy)", variable=mode_var, value="Auto", command=toggle_manual_input, bg="white").pack(anchor="w")
tk.Radiobutton(frame_mode, text="Manual Proxy (Isi Sendiri)", variable=mode_var, value="Manual", command=toggle_manual_input, bg="white").pack(anchor="w")

frame_manual = tk.Frame(frame_general, bg="white")
frame_manual.pack(pady=5)
manual_proxy_entry = tk.Entry(frame_manual, width=30, state="disabled")
manual_proxy_entry.pack(side=tk.LEFT, padx=5)
tor_btn = tk.Button(frame_manual, text="Dapatkan Tor Browser", command=open_tor_web, bg="lightblue", font=("Arial", 8), state="disabled")
tor_btn.pack(side=tk.LEFT)
tk.Label(frame_general, text="Contoh: 111.22.33.44:8080 (Otomatis +http)", font=("Arial", 8), fg="gray", bg="white").pack()

tk.Button(frame_general, text="DOWNLOAD", command=start_download, bg="#dddddd", height=2, width=20).pack(pady=15)

status_label = tk.Label(frame_general, text="Siap", fg="black", bg="white")
status_label.pack()

progress_var = tk.IntVar()
Progressbar(frame_general, maximum=100, variable=progress_var).pack(pady=5, fill=tk.X, padx=20)

stats_label = tk.Label(frame_general, text="0% | 0.00 MiB | Speed: 0.00 MiB/s", font=("Consolas", 9), fg="gray", bg="white")
stats_label.pack(pady=5)

frame_footer = tk.Frame(frame_general, bg="white")
frame_footer.pack(side=tk.BOTTOM, pady=10)
tk.Label(frame_footer, text="Created by GarlicPowder", font=("Segoe UI", 8, "italic"), fg="gray", bg="white").pack()
tk.Label(frame_footer, text="Discord: @vishkel01", font=("Segoe UI", 9, "bold"), fg="#5865F2", bg="white").pack()

adult_title = tk.Label(tab_dewasa, text="🔞 ADULT VIDEO DOWNLOADER 🔞", font=("Arial", 12, "bold"), fg="#ffa500", bg="#111111")
adult_title.pack(pady=(20, 10))

tk.Label(tab_dewasa, text="Masukkan URL Dewasa:", fg="white", bg="#111111").pack(pady=(5, 2))
adult_url_entry = tk.Entry(tab_dewasa, width=45, bg="#222222", fg="white", insertbackground="white", relief="flat")
adult_url_entry.pack(pady=5)

tk.Button(tab_dewasa, text="🚀 DOWNLOAD VIDEO", command=start_download_adult, bg="#333333", fg="#ffa500", activebackground="#444444", activeforeground="white", width=28, height=2).pack(pady=20)

status_label_adult = tk.Label(tab_dewasa, text="Status: Ready", fg="white", bg="#1a1a1a")
status_label_adult.pack(pady=(10, 2))

stats_label_adult = tk.Label(tab_dewasa, text="", fg="gray", bg="#1a1a1a")
stats_label_adult.pack(pady=(0, 10))

progress_var_adult = tk.IntVar()
progress_bar_adult = Progressbar(tab_dewasa, variable=progress_var_adult, length=300)
progress_bar_adult.pack(pady=5)

log_text_adult = ScrolledText(tab_dewasa, height=10, bg="#000000", fg="#ffffff", insertbackground="#ffffff", font=("Consolas", 10), wrap=tk.NONE)
log_text_adult.pack(padx=10, pady=(5, 10), fill=tk.BOTH, expand=True)
log_text_adult.configure(state='disabled')

warning_label_adult = tk.Label(tab_dewasa, text="⚠️ WAJIB menyalakan VPN (seperti ProtonVPN) atau Tor Proxy sebelum mendownload di tab ini agar koneksi tidak diblokir ISP.", fg="#ffcc66", bg="#111111", wraplength=380, justify="center", font=("Arial", 9, "bold"))
warning_label_adult.pack(pady=(10, 4))

tk.Label(tab_dewasa, text="💡 Tips: Pastikan Cloudflare WARP atau VPN sudah Anda nyalakan secara manual di PC sebelum mengklik download agar koneksi tidak diblokir ISP.", fg="#cccccc", bg="#111111", wraplength=380, justify="center", font=("Arial", 9)).pack(pady=(0, 10))

root.mainloop()