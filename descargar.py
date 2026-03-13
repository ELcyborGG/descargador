import yt_dlp
import os

def descargar(url, formato="mp4"):
    carpeta = os.path.join(os.path.expanduser("~"), "Downloads", "Descargador")
    os.makedirs(carpeta, exist_ok=True)

    if formato == "mp3":
        opciones = {
            "format": "bestaudio/best",
            "outtmpl": f"{carpeta}/%(title)s.%(ext)s",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
            }],
        }
    else:
        opciones = {
            "format": "best",
            "outtmpl": f"{carpeta}/%(title)s.%(ext)s",
        }

    with yt_dlp.YoutubeDL(opciones) as ydl:
        print(f"Descargando: {url}")
        ydl.download([url])
        print("¡Listo! Guardado en:", carpeta)

# Prueba
url = input("Pega la URL: ")
fmt = input("Formato (mp3 o mp4): ")
descargar(url, fmt)