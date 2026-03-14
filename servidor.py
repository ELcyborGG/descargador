from flask import Flask, request, jsonify
import yt_dlp
import os
import threading

app = Flask(__name__)

CARPETA = os.path.join(os.path.expanduser("~"), "Downloads", "Descargador")
os.makedirs(CARPETA, exist_ok=True)

@app.route("/")
def index():
    return "Servidor descargador activo"

@app.route("/download")
def download():
    url = request.args.get("url", "")
    formato = request.args.get("format", "mp4")

    if not url:
        return jsonify({"status": "error", "mensaje": "URL requerida"}), 400

    try:
        with yt_dlp.YoutubeDL({"quiet": True}) as ydl:
            info = ydl.extract_info(url, download=False)
        titulo = info.get("title", "video")

        threading.Thread(target=descargar, args=(url, formato, titulo), daemon=True).start()

        return jsonify({"status": "ok", "titulo": titulo, "mensaje": "Descarga iniciada"})
    except Exception as e:
        return jsonify({"status": "error", "mensaje": str(e)}), 500

def descargar(url, formato, titulo):
    if formato == "mp3":
        opciones = {
            "format": "bestaudio/best",
            "outtmpl": f"/tmp/{titulo}.%(ext)s",
            "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3"}],
        }
    else:
        opciones = {
            "format": "bestvideo[vcodec^=avc1]+bestaudio[acodec^=mp4a]/best",
            "outtmpl": f"/tmp/{titulo}.%(ext)s",
            "merge_output_format": "mp4",
        }
    with yt_dlp.YoutubeDL(opciones) as ydl:
        ydl.download([url])

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)