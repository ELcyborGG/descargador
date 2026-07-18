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
                    "outtmpl": f"{tmpdir}/%(title)s.%(ext)s",
                    "quiet": True,
                    "no_warnings": True,
                    "http_headers": {
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                        "Accept-Language": "en-US,en;q=0.9",
                    },
                }

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
