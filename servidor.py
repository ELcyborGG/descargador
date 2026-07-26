from flask import Flask, request, jsonify, send_file
import yt_dlp
import os
import tempfile
import threading
 
app = Flask(__name__)
archivos_listos = {}
 
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
                opciones_base = {
                    # Truncamos el titulo a 80 caracteres para evitar "File name too long"
                    # en posts con descripciones/hashtags muy largos (comun en TikTok/Facebook)
                    "outtmpl": f"{tmpdir}/%(title).80s.%(ext)s",
                    "restrictfilenames": True,
                    "quiet": True,
                    "no_warnings": True,
                    "http_headers": {
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                        "Accept-Language": "en-US,en;q=0.9",
                    },
                }
 
                # Solo agrega cookies si es un link de YouTube (Instagram/TikTok siguen sin cookies)
                if "youtube.com" in url or "youtu.be" in url:
                    cookies_path = os.path.join(os.path.dirname(__file__), "www.youtube.com_cookies.txt")
                    if os.path.exists(cookies_path):
                        opciones_base["cookiefile"] = cookies_path
 
                if formato == "mp3":
                    opciones = {
                        **opciones_base,
                        "format": "bestaudio/best",
                        "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3"}],
                    }
                else:
                    opciones = {
                        **opciones_base,
                        "format": "bestvideo[height<=720]+bestaudio/bestvideo+bestaudio/best",
                        "merge_output_format": "mp4",
                    }
 
                with yt_dlp.YoutubeDL(opciones) as ydl:
                    ydl.download([url])
 
                archivo = next(
                    (os.path.join(tmpdir, f) for f in os.listdir(tmpdir)), None
                )
                if archivo:
                    archivos_listos[job_id] = archivo
                else:
                    archivos_listos[job_id] = "error:No se encontro archivo"
 
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
