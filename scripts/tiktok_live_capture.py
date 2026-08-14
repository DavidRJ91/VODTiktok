from __future__ import annotations

import json
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from common import env, probe_duration_seconds

_SCRIPT_DIR = Path(__file__).parent


class TikTokLiveError(RuntimeError):
    pass


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


def validate_tiktok_url(url: str) -> None:
    if not url:
        raise TikTokLiveError("No se ha proporcionado ninguna URL de TikTok.")
    if "tiktok.com" not in url.lower():
        raise TikTokLiveError("Introduce una URL válida de TikTok.")


def _cookies_file() -> str | None:
    candidate = env("TIKTOK_COOKIES_FILE") or env("COOKIES_FILE")
    if candidate and Path(candidate).exists():
        return candidate
    return None


def _base_ytdlp_args() -> list[str]:
    args = [sys.executable, str(_SCRIPT_DIR / "ytdlp_patch.py"), "--no-warnings"]
    cookies = _cookies_file()
    if cookies:
        print(f"Usando cookies de TikTok: {cookies}")
        args += ["--cookies", cookies]
    return args


def get_live_metadata(url: str) -> dict:
    validate_tiktok_url(url)
    p = subprocess.run(
        _base_ytdlp_args()
        + ["--dump-single-json", "--skip-download",
           "--retries", "5", "--extractor-retries", "5", url],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if p.returncode != 0:
        msg = (p.stderr or p.stdout).strip()
        raise TikTokLiveError("No se pudo consultar el LIVE con yt-dlp:\n" + msg[-2500:])
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
    try:
        return get_live_info(url).is_live
    except Exception:
        return False


def _fallback_live_info() -> LiveInfo:
    return LiveInfo(title="TikTok LIVE", uploader="", room_id="", is_live=True)


def _find_output_file(folder: Path) -> Path | None:
    if not folder.exists():
        return None
    extensions = {".mp4", ".mkv", ".webm", ".ts", ".flv"}
    candidates = [
        p for p in folder.iterdir()
        if p.is_file()
        and p.suffix.lower() in extensions
        and not p.name.endswith(".part")
        and p.stat().st_size > 0
    ]
    return max(candidates, key=lambda p: p.stat().st_mtime) if candidates else None


def _remux_flv_to_mp4(filepath: Path) -> Path:
    if filepath.suffix.lower() != ".flv":
        return filepath
    out = filepath.with_suffix(".mp4")
    p = subprocess.run(
        ["ffmpeg", "-y", "-i", str(filepath), "-c", "copy", "-movflags", "+faststart", str(out)],
        capture_output=True,
        text=True,
    )
    if p.returncode == 0 and out.exists() and out.stat().st_size > 0:
        try:
            filepath.unlink()
        except OSError:
            pass
        print(f"Remux FLV -> MP4: {out.name}")
        return out
    print("AVISO: no se pudo remuxear a MP4; se mantiene el archivo FLV.")
    return filepath


def _get_info_without_blocking(url: str) -> LiveInfo:
    try:
        info = get_live_info(url)
        print("Metadatos detectados:")
        print(f"  title: {info.title}")
        print(f"  uploader: {info.uploader}")
        print(f"  room_id: {info.room_id}")
        print(f"  is_live: {info.is_live}")
        if not info.is_live:
            print("AVISO: yt-dlp indica que no está live; se intentará capturar igualmente.")
        return info
    except Exception as exc:
        print("No se pudieron obtener metadatos completos; se intentará capturar directamente.")
        print(f"Motivo: {exc}")
        return _fallback_live_info()


def _stop_process(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    try:
        process.send_signal(signal.SIGINT)
        process.wait(timeout=90)
        return
    except Exception:
        pass
    if process.poll() is None:
        try:
            process.terminate()
            process.wait(timeout=30)
            return
        except Exception:
            pass
    if process.poll() is None:
        process.kill()
        process.wait()


def capture_live_segment(url: str, output_dir: str | Path, max_seconds: int | None, tag: str) -> CaptureResult:
    validate_tiktok_url(url)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    max_attempts = 10
    retry_delay = 15
    last_error = ""

    for attempt in range(1, max_attempts + 1):
        print(f"\n=== INTENTO {attempt}/{max_attempts} DE CAPTURA DE TIKTOK LIVE ===")
        info = _get_info_without_blocking(url)
        output_template = str(output_dir / f"{tag}_attempt{attempt}_%(epoch)s.%(ext)s")

        cmd = _base_ytdlp_args() + [
            "--retries", "10",
            "--fragment-retries", "10",
            "--extractor-retries", "5",
            "--retry-sleep", "http:5",
            "--retry-sleep", "fragment:3",
            "--socket-timeout", "30",
            "--concurrent-fragments", "1",
            "-f", "best[ext=flv]/best",
            "--no-part",
            "--remux-video", "mp4",
            "-o", output_template,
            url,
        ]

        process = None
        try:
            print("Ejecutando:", " ".join(cmd))
            started = time.monotonic()
            process = subprocess.Popen(cmd)

            while process.poll() is None:
                if max_seconds is not None and time.monotonic() - started >= max_seconds:
                    print("Tiempo máximo de grabación alcanzado.")
                    _stop_process(process)
                    break
                time.sleep(1)

            if process.poll() is None:
                _stop_process(process)

            filepath = _find_output_file(output_dir)
            if filepath is not None and filepath.stat().st_size >= 256 * 1024:
                filepath = _remux_flv_to_mp4(filepath)
                duration = probe_duration_seconds(filepath)
                print(f"Captura válida: {filepath}")
                return CaptureResult(str(filepath), duration, info)

            last_error = f"yt-dlp terminó con código {process.returncode} sin generar un vídeo válido."
            print(last_error)

        except KeyboardInterrupt:
            if process is not None:
                _stop_process(process)
            raise
        except Exception as exc:
            last_error = str(exc)
            print(f"Error durante el intento {attempt}: {last_error}")
            if process is not None and process.poll() is None:
                _stop_process(process)

        if attempt < max_attempts:
            print(f"Esperando {retry_delay} segundos antes de reintentar...")
            time.sleep(retry_delay)

    raise TikTokLiveError(
        f"No se pudo capturar el TikTok LIVE después de {max_attempts} intentos.\n\nÚltimo error:\n{last_error}"
    )
