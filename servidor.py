from flask import Flask, request, jsonify, send_file
import yt_dlp
import os
import tempfile

app = Flask(__name__)

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

        if formato == "mp3":
            opciones = {
                "format": "bestaudio/best",
                "outtmpl": f"{tmpdir}/%(title)s.%(ext)s",
                "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3"}],
                "quiet": True,
            }
        else:
            opciones = {
                "format": "best[ext=mp4]/best",
                "outtmpl": f"{tmpdir}/%(title)s.%(ext)s",
                "quiet": True,
            }

        with yt_dlp.YoutubeDL(opciones) as ydl:
            ydl.download([url])

        archivo = next(
            (os.path.join(tmpdir, f) for f in os.listdir(tmpdir)),
            None
        )

        if not archivo:
            return jsonify({"status": "error", "mensaje": "No se pudo descargar"}), 500

        return send_file(
            archivo,
            as_attachment=True,
            download_name=os.path.basename(archivo)
        )

    except Exception as e:
        return jsonify({"status": "error", "mensaje": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
    