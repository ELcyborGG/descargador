from flask import Flask, request, jsonify, send_file
import yt_dlp
import os
import re
import sys
import shutil
import subprocess
import tempfile
import threading
import time
import urllib.request
import uuid

app = Flask(__name__)
archivos_listos = {}
imagenes = {}   # job_id -> lista de rutas (cuando la publicacion era de fotos)
trabajos = {}   # job_id -> (carpeta temporal, hora de creacion)

EXT_IMAGEN = {"jpg", "jpeg", "png", "webp", "gif", "heic", "avif", "bmp"}
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


def limpiar_viejos():
    """Cada 10 min borra las descargas con mas de 30 min para que no se llene el disco."""
    while True:
        time.sleep(600)
        ahora = time.time()
        for jid, (carpeta, creado) in list(trabajos.items()):
            if ahora - creado > 1800:
                shutil.rmtree(carpeta, ignore_errors=True)
                trabajos.pop(jid, None)
                archivos_listos.pop(jid, None)
                imagenes.pop(jid, None)


threading.Thread(target=limpiar_viejos, daemon=True).start()


# ---------------------------------------------------------------- cookies

def buscar_cookies(*nombres):
    """Busca un archivo de cookies junto al servidor o en los Secret Files de Render (/etc/secrets)."""
    for carpeta in (os.path.dirname(os.path.abspath(__file__)), "/etc/secrets"):
        for nombre in nombres:
            ruta = os.path.join(carpeta, nombre)
            if os.path.exists(ruta):
                return ruta
    return None


def cookies_de(url):
    u = url.lower()
    if "instagram.com" in u:
        return buscar_cookies("www.instagram.com_cookies.txt", "instagram.com_cookies.txt", "instagram_cookies.txt")
    if "facebook.com" in u or "fb.watch" in u or "fb.com" in u:
        return buscar_cookies("www.facebook.com_cookies.txt", "facebook.com_cookies.txt", "facebook_cookies.txt")
    if "tiktok.com" in u:
        return buscar_cookies("www.tiktok.com_cookies.txt", "tiktok.com_cookies.txt", "tiktok_cookies.txt")
    return None


# ---------------------------------------------------------------- imagenes

def _buscar_imagenes(carpeta):
    encontradas = []
    for raiz, _, nombres in os.walk(carpeta):
        for n in nombres:
            ext = n.rsplit(".", 1)[-1].lower() if "." in n else ""
            if ext in EXT_IMAGEN:
                encontradas.append(os.path.join(raiz, n))
    return encontradas


def _gallery_dl(url, tmpdir):
    """Intenta bajar las imagenes con gallery-dl. Devuelve (rutas, detalle_del_error)."""
    cmd = [sys.executable, "-m", "gallery_dl", "-D", tmpdir, "--no-mtime", "-R", "3"]
    cookies = cookies_de(url)
    if cookies:
        cmd += ["-C", cookies]
    cmd.append(url)
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=240)
    except subprocess.TimeoutExpired:
        return [], "gallery-dl se demoró demasiado"
    archivos = _buscar_imagenes(tmpdir)
    if archivos:
        return archivos, ""
    salida = (r.stderr or "") + "\n" + (r.stdout or "")
    lineas = [l.strip() for l in salida.splitlines() if l.strip()]
    claves = [l for l in lineas if any(k in l.lower() for k in ("error", "warning", "login", "cookie", "unauthor"))]
    return [], " ".join((claves or lineas)[-2:])[:250]


def _embed_instagram(url, tmpdir):
    """Plan B para Instagram sin cuenta: la pagina 'embed' de una publicacion publica trae la foto."""
    m = re.search(r"instagram\.com/(?:[^/]+/)?(?:p|reel|tv)/([A-Za-z0-9_-]+)", url)
    if not m:
        return []
    try:
        req = urllib.request.Request(
            f"https://www.instagram.com/p/{m.group(1)}/embed/captioned/",
            headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"},
        )
        html = urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "ignore")
        texto = html.replace('\\"', '"').replace("\\/", "/").replace("\\u0026", "&").replace("&amp;", "&")
        candidatos = []
        patrones = (r'class="EmbeddedMediaImage"[^>]*?src="([^"]+)"', r'"display_url":"(https:[^"]+)"')
        for patron in patrones:
            for u in re.findall(patron, texto):
                if u not in candidatos:
                    candidatos.append(u)
        rutas = []
        for i, u in enumerate(candidatos, 1):
            rq = urllib.request.Request(u, headers={"User-Agent": UA})
            with urllib.request.urlopen(rq, timeout=30) as resp:
                if not resp.headers.get("Content-Type", "").startswith("image/"):
                    continue
                datos = resp.read()
            ruta = os.path.join(tmpdir, f"embed_{i}.jpg")
            with open(ruta, "wb") as f:
                f.write(datos)
            rutas.append(ruta)
        return rutas
    except Exception:
        return []


def descargar_imagenes(url, tmpdir):
    """Baja todas las imagenes de una publicacion (1, 3, 10...) y devuelve las rutas en orden."""
    archivos, detalle = _gallery_dl(url, tmpdir)
    if not archivos and "instagram.com" in url.lower():
        archivos = _embed_instagram(url, tmpdir)
    if not archivos:
        extra = ""
        u = url.lower()
        if cookies_de(url) is None and any(x in u for x in ("instagram.com", "facebook.com", "fb.watch")):
            extra = " Lo más probable es que al servidor le falten las cookies de esa red (login)."
        raise RuntimeError(
            f"Publicación de fotos: no pude sacar las imágenes.{extra} Detalle: {detalle or 'gallery-dl no devolvió nada'}"
        )

    # Orden de la publicacion = orden en que se fueron bajando
    archivos.sort(key=lambda p: (os.path.getmtime(p), p))
    finales = []
    for i, ruta in enumerate(archivos, 1):
        ext = ruta.rsplit(".", 1)[-1].lower()
        base = re.sub(r"[^A-Za-z0-9_-]+", "_", os.path.splitext(os.path.basename(ruta))[0])[:40]
        nuevo = os.path.join(tmpdir, f"{i:02d}_{base}.{ext}")
        if ruta != nuevo:
            os.replace(ruta, nuevo)
        finales.append(nuevo)
    return finales


def parece_publicacion_de_fotos(mensaje):
    m = mensaje.lower()
    return any(k in m for k in ("no video", "unsupported url", "no video formats", "no media"))


# ---------------------------------------------------------------- rutas

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
        job_id = uuid.uuid4().hex[:12]
        trabajos[job_id] = (tmpdir, time.time())

        def entregar_fotos():
            lista = descargar_imagenes(url, tmpdir)
            imagenes[job_id] = lista
            archivos_listos[job_id] = lista[0]

        def procesar():
            try:
                # Links de fotos de TikTok: directo a imagenes
                if formato == "img" or (formato == "mp4" and "/photo/" in url):
                    entregar_fotos()
                    return

                opciones_base = {
                    # Truncamos el titulo a 80 caracteres para evitar "File name too long"
                    "outtmpl": f"{tmpdir}/%(title).80s.%(ext)s",
                    "restrictfilenames": True,
                    "quiet": True,
                    "no_warnings": True,
                    "http_headers": {"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"},
                }

                if "youtube.com" in url or "youtu.be" in url:
                    cookies_path = buscar_cookies("www.youtube.com_cookies.txt")
                    if cookies_path:
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

                try:
                    with yt_dlp.YoutubeDL(opciones) as ydl:
                        ydl.download([url])
                except Exception as e:
                    # Si no era un video sino una publicacion de fotos, se bajan las fotos
                    if formato == "mp4" and parece_publicacion_de_fotos(str(e)):
                        entregar_fotos()
                        return
                    raise

                archivo = next((os.path.join(tmpdir, f) for f in os.listdir(tmpdir)), None)
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
    respuesta = {"status": "listo", "filename": os.path.basename(archivo)}
    if job_id in imagenes:
        respuesta["files"] = [os.path.basename(p) for p in imagenes[job_id]]
    return jsonify(respuesta)


@app.route("/file/<job_id>")
def get_file(job_id):
    if job_id not in archivos_listos:
        return jsonify({"status": "error", "mensaje": "No listo"}), 404
    archivo = archivos_listos[job_id]
    if str(archivo).startswith("error:"):
        return jsonify({"status": "error"}), 500
    return send_file(archivo, as_attachment=True, download_name=os.path.basename(archivo))


@app.route("/file/<job_id>/<int:n>")
def get_imagen(job_id, n):
    lista = imagenes.get(job_id)
    if not lista or n < 0 or n >= len(lista) or not os.path.exists(lista[n]):
        return jsonify({"status": "error", "mensaje": "Imagen no disponible"}), 404
    return send_file(lista[n], as_attachment=True, download_name=os.path.basename(lista[n]))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
