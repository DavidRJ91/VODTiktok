from __future__ import annotations
import json, os, re, signal, subprocess, sys, time
from dataclasses import dataclass
from pathlib import Path
import requests
from common import probe_duration_seconds

class TikTokLiveError(RuntimeError):
    pass

_BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

def _extra_ytdlp_args() -> list[str]:
    """Argumentos opcionales para yt-dlp: cookies de una sesión logueada y/o
    proxy. TikTok bloquea agresivamente las IPs de datacenter (incluidas las
    de los runners de GitHub Actions) y responde con una página de captcha;
    yt-dlp interpreta eso como 'canal no en directo'. Definir TIKTOK_COOKIES
    y/o TIKTOK_PROXY como secrets suele solucionarlo."""
    args: list[str] = []
    cookies = os.environ.get("TIKTOK_COOKIES", "").strip()
    if cookies:
        cookies_path = Path(os.environ.get("RUNNER_TEMP", ".")) / "tiktok_cookies.txt"
        cookies_path.write_text(cookies, encoding="utf-8")
        args += ["--cookies", str(cookies_path)]
    proxy = os.environ.get("TIKTOK_PROXY", "").strip()
    if proxy:
        args += ["--proxy", proxy]
    return args

def _tiktok_cookie_jar() -> dict:
    """Cookies de una sesión logueada (mismo secret TIKTOK_COOKIES, formato
    Netscape cookies.txt), para las peticiones directas de abajo."""
    raw = os.environ.get("TIKTOK_COOKIES", "").strip()
    jar = {}
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) >= 7:
            jar[parts[5]] = parts[6]
    return jar

def _extract_username(url: str) -> str | None:
    m = re.search(r"tiktok\.com/@([^/?#]+)", url)
    return m.group(1) if m else None

def _direct_room_id(username: str) -> str | None:
    """Lee el room_id embebido en la página pública del LIVE (una petición
    normal, la misma página que carga cualquier visitante en su navegador)."""
    try:
        r = requests.get(
            f"https://www.tiktok.com/@{username}/live",
            headers={"User-Agent": _BROWSER_UA, "Accept-Language": "en-US"},
            cookies=_tiktok_cookie_jar(), timeout=15,
        )
    except requests.RequestException:
        return None
    m = re.search(r'"roomId"\s*:\s*"(\d+)"', r.text)
    room_id = m.group(1) if m else None
    # "0" es el placeholder habitual de TikTok cuando no hay sala activa
    # (puede quedar en el HTML de un perfil que ya no está en directo).
    return room_id if room_id and room_id != "0" else None

def _direct_is_alive(room_id: str) -> bool | None:
    """Confirma el estado del LIVE contra la API pública de TikTok
    (check_alive + room/info), igual que hace la propia web.

    check_alive es el endpoint dedicado exactamente a esta pregunta, así que
    se trata como señal principal. room/info es solo una confirmación
    adicional: si no da una respuesta clara (algo típico de un bloqueo de
    IP del runner, no de una sala que no existe), NO se usa para desmentir
    un check_alive positivo — solo lo desmiente si da un status explícito
    y distinto de "en directo"."""
    headers = {"User-Agent": _BROWSER_UA}
    cookies = _tiktok_cookie_jar()
    try:
        alive = requests.get(
            "https://webcast.tiktok.com/webcast/room/check_alive/",
            params={"aid": "1988", "region": "US", "room_ids": room_id, "user_is_login": "true"},
            headers=headers, cookies=cookies, timeout=15,
        ).json()
    except (requests.RequestException, ValueError):
        return None

    data_list = alive.get("data")
    if not isinstance(data_list, list) or not data_list or not data_list[0].get("alive"):
        return False

    try:
        info = requests.get(
            "https://webcast.tiktok.com/webcast/room/info/",
            params={"aid": "1988", "room_id": room_id},
            headers=headers, cookies=cookies, timeout=15,
        ).json()
        status = (info.get("data") or {}).get("status")
    except (requests.RequestException, ValueError, KeyError, TypeError):
        status = None

    if status is not None and str(status) != "2":
        return False  # contradicción clara -> no confiar en check_alive
    return True

@dataclass
class LiveInfo:
    title: str
    uploader: str
    room_id: str
    is_live: bool

@dataclass
class CaptureResult:
    filepath: str
    duration_seconds: int | None
    info: LiveInfo

def validate_tiktok_url(url: str):
    if not url or "tiktok.com" not in url.lower():
        raise TikTokLiveError("Introduce una URL válida de TikTok.")

def _ytdlp_dump_json(url: str) -> tuple[dict | None, str | None]:
    """Devuelve (metadatos, None) si yt-dlp tuvo éxito, o (None, error) si no."""
    p = subprocess.run(
        [sys.executable, "-m", "yt_dlp", "--dump-single-json",
         "--skip-download", "--no-warnings", *_extra_ytdlp_args(), url],
        capture_output=True, text=True
    )
    if p.returncode != 0:
        return None, (p.stderr or p.stdout).strip()
    try:
        return json.loads(p.stdout), None
    except json.JSONDecodeError:
        return None, "yt-dlp no devolvió metadatos JSON válidos."

def get_live_info(url: str) -> LiveInfo:
    validate_tiktok_url(url)
    data, err = _ytdlp_dump_json(url)

    if data and data.get("is_live"):
        return LiveInfo(
            title=data.get("title") or "TikTok LIVE",
            uploader=data.get("uploader") or data.get("channel") or "",
            room_id=str(data.get("id") or ""),
            is_live=True,
        )

    # yt-dlp no lo confirma (falló o dice que no está en directo). Antes de
    # darlo por perdido lo verificamos por nuestra cuenta contra la propia
    # API pública de TikTok: yt-dlp puede fallar por un bloqueo de IP del
    # runner sin que el LIVE esté realmente caído.
    username = _extract_username(url)
    if username:
        room_id = _direct_room_id(username)
        if room_id and _direct_is_alive(room_id):
            return LiveInfo(
                title=(data or {}).get("title") or f"TikTok LIVE de @{username}",
                uploader=username,
                room_id=room_id,
                is_live=True,
            )

    hint = ""
    if not data or "not currently live" in (err or "").lower() or "captcha" in (err or "").lower():
        hint = ("\n\nEsto suele pasar cuando TikTok bloquea la IP del runner (datacenter) "
                "y sirve una página de captcha en vez del estado real, y la verificación "
                "directa contra la API de TikTok tampoco ha podido confirmarlo. Prueba a "
                "definir el secret TIKTOK_COOKIES (cookies de una sesión logueada) o "
                "TIKTOK_PROXY (proxy residencial).")
    raise TikTokLiveError(
        "No se pudo confirmar que el LIVE está activo"
        + (f":\n{err[-2000:]}" if err else ".")
        + hint
    )

def is_live(url: str) -> bool:
    try:
        return get_live_info(url).is_live
    except TikTokLiveError:
        return False

def _find_output_file(folder: Path) -> Path:
    candidates = [p for p in folder.iterdir()
                  if p.is_file() and p.suffix.lower() in {".mp4",".mkv",".webm",".ts",".flv"}]
    if not candidates:
        raise TikTokLiveError("No se encontró ningún archivo de vídeo tras finalizar la captura.")
    return max(candidates, key=lambda p: p.stat().st_size)

def capture_live_segment(url: str, output_dir: str | Path, max_seconds: int | None, tag: str) -> CaptureResult:
    info = get_live_info(url)
    if not info.is_live:
        raise TikTokLiveError("El TikTok LIVE no está activo o yt-dlp no puede acceder a él.")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_template = str(output_dir / f"{tag}_%(epoch)s.%(ext)s")

    cmd = [
        sys.executable, "-m", "yt_dlp",
        "-v",  # temporal: para ver el comando exacto de ffmpeg y el contexto
                # justo antes del segfault. Se puede quitar una vez resuelto.
        "--no-warnings", "--no-part",
        "--remux-video", "mp4",
        "-f", "best",
        "-o", output_template,
        # yt-dlp fuerza ffmpeg para cualquier HLS marcado como directo
        # (is_live=True); --hls-prefer-native no tiene efecto en ese caso,
        # así que el único margen de maniobra es pasarle argumentos extra a
        # ese ffmpeg. -http_persistent 0 es un workaround conocido para
        # varios cuelgues/crashes de ffmpeg al leer HLS en directo.
        "--downloader-args", "ffmpeg_i:-http_persistent 0",
        *_extra_ytdlp_args(),
        url,
    ]

    def _run() -> int | None:
        process = subprocess.Popen(cmd)
        started = time.monotonic()
        try:
            while process.poll() is None:
                if max_seconds is not None and time.monotonic() - started >= max_seconds:
                    process.send_signal(signal.SIGINT)
                    break
                time.sleep(1)
            try:
                process.wait(timeout=90)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        finally:
            if process.poll() is None:
                process.kill()
        return process.returncode

    def _has_output() -> bool:
        return any(
            p.is_file() and p.suffix.lower() in {".mp4", ".mkv", ".webm", ".ts", ".flv"}
            for p in output_dir.iterdir()
        )

    for attempt in range(2):
        returncode = _run()
        if _has_output():
            break
        # returncode negativo = el proceso murió por una señal (p. ej. un
        # segfault de ffmpeg) sin llegar a escribir nada. Un único reintento
        # suele bastar para descartar un fallo puntual/transitorio.
        if attempt == 0 and returncode is not None and returncode < 0:
            continue
        break

    filepath = _find_output_file(output_dir)
    if filepath.stat().st_size < 1024 * 512:
        raise TikTokLiveError("La captura generó un archivo demasiado pequeño.")

    return CaptureResult(
        filepath=str(filepath),
        duration_seconds=probe_duration_seconds(filepath),
        info=info,
    )
