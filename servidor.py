from flask import Flask, request, jsonify, send_file
import yt_dlp
import os
import tempfile
import threading

app = Flask(__name__)
archivos_listos = {}
COOKIES = os.path.join(os.path.dirname(__file__), "www.youtube.com_cookies.txt")

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
        tmpdir = tempfile.mkdtemp()
        job_id = str(abs(hash(url + formato)))

        def procesar():
            try:
                if formato == "mp3":
                    opciones = {
                        "format": "bestaudio/best",
                        "outtmpl": f"{tmpdir}/%(title)s.%(ext)s",
                        "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3"}],
                        "cookiefile": COOKIES,
                        "quiet": True,
                    }
                else:
                    opciones = {
                        "format": "best",
                        "outtmpl": f"{tmpdir}/%(title)s.%(ext)s",
                        "cookiefile": COOKIES,
                        "quiet": True,
                    }
                with yt_dlp.YoutubeDL(opciones) as ydl:
                    ydl.download([url])
                archivo = next(
                    (os.path.join(tmpdir, f) for f in os.listdir(tmpdir)), None
                )
                if archivo:
                    archivos_listos[job_id] = archivo
            except Exception as e:
                archivos_listos[job_id] = f"error:{str(e)}"

        threading.Thread(target=procesar, daemon=True).start()
        return jsonify({"status": "procesando", "job_id": job_id})

    except Exception as e:
        return jsonify({"status": "error", "mensaje": str(e)}), 500

@app.route("/status/<job_id>")
def status(job_id):
    if job_id not in archivos_listos:
        return jsonify({"status": "procesando"})
    archivo = archivos_listos[job_id]
    if str(archivo).startswith("error:"):
        return jsonify({"status": "error", "mensaje": archivo[6:]})
    return jsonify({"status": "listo", "filename": os.path.basename(archivo)})

@app.route("/file/<job_id>")
def get_file(job_id):
    if job_id not in archivos_listos:
        return jsonify({"status": "error", "mensaje": "No listo"}), 404
    archivo = archivos_listos[job_id]
    if str(archivo).startswith("error:"):
        return jsonify({"status": "error"}), 500
    return send_file(archivo, as_attachment=True, download_name=os.path.basename(archivo))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
