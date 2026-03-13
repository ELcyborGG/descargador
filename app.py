import customtkinter as ctk
import threading
import yt_dlp
import os
import json
from datetime import datetime

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

CARPETA = os.path.join(os.path.expanduser("~"), "Downloads", "Descargador")
FFMPEG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ffmpeg-8.0.1-essentials_build", "bin", "ffmpeg.exe")
HISTORIAL_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "historial.json")
os.makedirs(CARPETA, exist_ok=True)

def cargar_historial():
    if os.path.exists(HISTORIAL_FILE):
        with open(HISTORIAL_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def guardar_historial(titulo, url, fmt):
    historial = cargar_historial()
    historial.insert(0, {
        "titulo": titulo,
        "url": url,
        "formato": fmt,
        "fecha": datetime.now().strftime("%d/%m/%Y %H:%M")
    })
    historial = historial[:50]
    with open(HISTORIAL_FILE, "w", encoding="utf-8") as f:
        json.dump(historial, f, ensure_ascii=False, indent=2)

def nombre_unico(carpeta, titulo, ext):
    base = os.path.join(carpeta, f"{titulo}.{ext}")
    if not os.path.exists(base):
        return titulo
    i = 1
    while os.path.exists(os.path.join(carpeta, f"{titulo} GG{i}.{ext}")):
        i += 1
    return f"{titulo} GG{i}"

app = ctk.CTk()
app.title("Descargador")
app.geometry("560x600")
app.resizable(False, False)

tabview = ctk.CTkTabview(app, width=540, height=560)
tabview.pack(padx=10, pady=10)
tab_descargar = tabview.add("Descargar")
tab_historial = tabview.add("Historial")

# --- TAB DESCARGAR ---
ctk.CTkLabel(tab_descargar, text="Descargador de Videos", font=ctk.CTkFont(size=20, weight="bold")).pack(pady=15)

url_entry = ctk.CTkEntry(tab_descargar, placeholder_text="Pega la URL aquí (video o lista)...", width=480)
url_entry.pack(pady=8)

formato_var = ctk.StringVar(value="mp4")
frame_formato = ctk.CTkFrame(tab_descargar, fg_color="transparent")
frame_formato.pack(pady=5)
ctk.CTkRadioButton(frame_formato, text="MP4 (mejor calidad)", variable=formato_var, value="mp4").pack(side="left", padx=20)
ctk.CTkRadioButton(frame_formato, text="MP3 (audio)", variable=formato_var, value="mp3").pack(side="left", padx=20)

estado = ctk.CTkLabel(tab_descargar, text="Esperando...", text_color="gray")
estado.pack(pady=8)

barra = ctk.CTkProgressBar(tab_descargar, width=480)
barra.pack(pady=5)
barra.set(0)

log_box = ctk.CTkTextbox(tab_descargar, width=480, height=160, state="disabled")
log_box.pack(pady=8)

def log(msg):
    log_box.configure(state="normal")
    log_box.insert("end", msg + "\n")
    log_box.see("end")
    log_box.configure(state="disabled")

def hook(d):
    if d["status"] == "downloading":
        pct = d.get("_percent_str", "...").strip()
        estado.configure(text=f"Descargando: {pct}", text_color="white")
        try:
            p = float(d.get("_percent_str", "0%").replace("%", "").strip()) / 100
            barra.set(p)
        except:
            pass
    elif d["status"] == "finished":
        estado.configure(text="Procesando archivo...", text_color="yellow")
        barra.set(1)

def descargar():
    url = url_entry.get().strip()
    if not url:
        estado.configure(text="Por favor pega una URL", text_color="red")
        return

    fmt = formato_var.get()
    
    opciones_base = {
    "ffmpeg_location": FFMPEG,
    "progress_hooks": [hook],
    "quiet": True,
    "no_warnings": True,
    "overwrites": True,
}

    if fmt == "mp3":
        opciones = {
            **opciones_base,
            "format": "bestaudio/best",
            "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3"}],
        }
    else:
        opciones = {
            **opciones_base,
            "format": "bestvideo[vcodec^=avc1]+bestaudio[acodec^=mp4a]/bestvideo+bestaudio/best",
            "merge_output_format": "mp4",
            "postprocessors": [{
                "key": "FFmpegVideoConvertor",
                "preferedformat": "mp4",
            }],
        }

    estado.configure(text="Iniciando...", text_color="white")
    btn.configure(state="disabled")
    log_box.configure(state="normal")
    log_box.delete("1.0", "end")
    log_box.configure(state="disabled")

    def run():
        try:
            with yt_dlp.YoutubeDL(opciones) as ydl:
                info = ydl.extract_info(url, download=False)
                if "entries" in info:
                    entradas = list(info["entries"])
                    total = len(entradas)
                    log(f"Lista de reproducción: {total} videos")
                    for i, entry in enumerate(entradas, 1):
                        titulo = entry.get("title", f"video_{i}")
                        ext = "mp3" if fmt == "mp3" else "mp4"
                        nombre = nombre_unico(CARPETA, titulo, ext)
                        opciones["outtmpl"] = f"{CARPETA}/{nombre}.%(ext)s"
                        log(f"[{i}/{total}] {titulo}")
                        with yt_dlp.YoutubeDL(opciones) as ydl2:
                            ydl2.download([entry["webpage_url"]])
                        guardar_historial(titulo, entry["webpage_url"], fmt)
                else:
                    titulo = info.get("title", "video")
                    ext = "mp3" if fmt == "mp3" else "mp4"
                    nombre = nombre_unico(CARPETA, titulo, ext)
                    opciones["outtmpl"] = f"{CARPETA}/{nombre}.%(ext)s"
                    log(f"Descargando: {titulo}")
                    with yt_dlp.YoutubeDL(opciones) as ydl2:
                        ydl2.download([url])
                    guardar_historial(titulo, url, fmt)

            estado.configure(text="¡Descarga completada!", text_color="lightgreen")
            log(f"✓ ¡Listo! Guardado en: {CARPETA}")
            actualizar_historial()
        except Exception as e:
            estado.configure(text="Error en la descarga", text_color="red")
            log(f"Error: {str(e)}")
        finally:
            btn.configure(state="normal")
            barra.set(0)

    threading.Thread(target=run, daemon=True).start()

btn = ctk.CTkButton(tab_descargar, text="Descargar", command=descargar, width=200, height=40)
btn.pack(pady=10)

# --- TAB HISTORIAL ---
historial_box = ctk.CTkScrollableFrame(tab_historial, width=500, height=460)
historial_box.pack(padx=10, pady=10)

def actualizar_historial():
    for widget in historial_box.winfo_children():
        widget.destroy()
    historial = cargar_historial()
    if not historial:
        ctk.CTkLabel(historial_box, text="No hay descargas aún", text_color="gray").pack(pady=20)
        return
    for item in historial:
        frame = ctk.CTkFrame(historial_box, fg_color=("#2b2b2b", "#1e1e1e"))
        frame.pack(fill="x", pady=3, padx=5)
        ctk.CTkLabel(frame, text=item["titulo"][:55], font=ctk.CTkFont(size=12, weight="bold"), anchor="w").pack(anchor="w", padx=10, pady=(6, 0))
        ctk.CTkLabel(frame, text=f"{item['formato'].upper()}  •  {item['fecha']}", text_color="gray", font=ctk.CTkFont(size=11), anchor="w").pack(anchor="w", padx=10, pady=(0, 6))

actualizar_historial()
app.mainloop()
