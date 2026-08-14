from __future__ import annotations
import json, os, signal, subprocess, sys, time
from dataclasses import dataclass
from pathlib import Path
from common import probe_duration_seconds

class TikTokLiveError(RuntimeError):
    pass

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

def get_live_metadata(url: str) -> dict:
    validate_tiktok_url(url)
    p = subprocess.run(
        [sys.executable, "-m", "yt_dlp", "--dump-single-json",
         "--skip-download", "--no-warnings", *_extra_ytdlp_args(), url],
        capture_output=True, text=True
    )
    if p.returncode != 0:
        msg = (p.stderr or p.stdout).strip()
        hint = ""
        if "not currently live" in msg.lower() or "captcha" in msg.lower():
            hint = ("\n\nEsto suele pasar cuando TikTok bloquea la IP del runner "
                    "(datacenter) y sirve una página de captcha en vez del estado real. "
                    "Prueba a definir el secret TIKTOK_COOKIES (cookies de una sesión "
                    "logueada) o TIKTOK_PROXY (proxy residencial).")
        raise TikTokLiveError("No se pudo consultar el LIVE con yt-dlp:\n" + msg[-2500:] + hint)
    try:
        return json.loads(p.stdout)
    except json.JSONDecodeError as exc:
        raise TikTokLiveError("yt-dlp no devolvió metadatos JSON válidos.") from exc

def get_live_info(url: str) -> LiveInfo:
    d = get_live_metadata(url)
    return LiveInfo(
        title=d.get("title") or "TikTok LIVE",
        uploader=d.get("uploader") or d.get("channel") or "",
        room_id=str(d.get("id") or ""),
        is_live=bool(d.get("is_live")),
    )

def is_live(url: str) -> bool:
    return get_live_info(url).is_live

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
        "--no-warnings", "--no-part",
        "--remux-video", "mp4",
        "-f", "best",
        "-o", output_template,
        *_extra_ytdlp_args(),
        url,
    ]
    process = subprocess.Popen(cmd)
    started = time.monotonic()
    stopped_by_limit = False

    try:
        while process.poll() is None:
            if max_seconds is not None and time.monotonic() - started >= max_seconds:
                stopped_by_limit = True
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

    filepath = _find_output_file(output_dir)
    if filepath.stat().st_size < 1024 * 512:
        raise TikTokLiveError("La captura generó un archivo demasiado pequeño.")

    return CaptureResult(
        filepath=str(filepath),
        duration_seconds=probe_duration_seconds(filepath),
        info=info,
    )
