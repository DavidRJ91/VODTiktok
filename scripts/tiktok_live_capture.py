from __future__ import annotations

import json
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from common import probe_duration_seconds


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


def validate_tiktok_url(url: str):
    if not url or "tiktok.com" not in url.lower():
        raise TikTokLiveError("Introduce una URL válida de TikTok.")


def get_live_metadata(url: str) -> dict:
    validate_tiktok_url(url)

    p = subprocess.run(
        [
            sys.executable,
            "-m",
            "yt_dlp",
            "--dump-single-json",
            "--skip-download",
            "--no-warnings",
            "--retries",
            "3",
            "--extractor-retries",
            "3",
            url,
        ],
        capture_output=True,
        text=True,
    )

    if p.returncode != 0:
        msg = (p.stderr or p.stdout).strip()
        raise TikTokLiveError(
            "No se pudo consultar el LIVE con yt-dlp:\n" + msg[-2500:]
        )

    try:
        return json.loads(p.stdout)
    except json.JSONDecodeError as exc:
        raise TikTokLiveError(
            "yt-dlp no devolvió metadatos JSON válidos."
        ) from exc


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


def _find_output_file(folder: Path) -> Path | None:
    if not folder.exists():
        return None

    candidates = [
        p for p in folder.iterdir()
        if p.is_file()
        and p.suffix.lower() in {
            ".mp4",
            ".mkv",
            ".webm",
            ".ts",
            ".flv",
        }
        and not p.name.endswith(".part")
    ]

    if not candidates:
        return None

    return max(candidates, key=lambda p: p.stat().st_size)


def capture_live_segment(
    url: str,
    output_dir: str | Path,
    max_seconds: int | None,
    tag: str,
) -> CaptureResult:

    validate_tiktok_url(url)

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    max_attempts = 10
    retry_delay = 15
    last_error = ""

    for attempt in range(1, max_attempts + 1):

        print(
            f"\n=== Intento {attempt}/{max_attempts} "
            f"de conectar con TikTok LIVE ==="
        )

        try:
            info = get_live_info(url)

            if not info.is_live:
                raise TikTokLiveError(
                    "El TikTok LIVE no está activo "
                    "o yt-dlp no puede acceder a él."
                )

            output_template = str(
                output_dir / f"{tag}_attempt{attempt}_%(epoch)s.%(ext)s"
            )

            cmd = [
                sys.executable,
                "-m",
                "yt_dlp",
                "--no-warnings",

                "--retries",
                "10",

                "--fragment-retries",
                "10",

                "--extractor-retries",
                "5",

                "--retry-sleep",
                "http:5",

                "--retry-sleep",
                "fragment:3",

                "--socket-timeout",
                "30",

                "--concurrent-fragments",
                "1",

                "--no-part",

                "--remux-video",
                "mp4",

                "-f",
                "best",

                "-o",
                output_template,

                url,
            ]

            print("Iniciando yt-dlp...")
            process = subprocess.Popen(cmd)

            started = time.monotonic()

            try:
                while process.poll() is None:

                    if (
                        max_seconds is not None
                        and time.monotonic() - started >= max_seconds
                    ):
                        print(
                            "Tiempo máximo alcanzado. "
                            "Finalizando captura..."
                        )

                        process.send_signal(signal.SIGINT)

                        try:
                            process.wait(timeout=90)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait()

                        break

                    time.sleep(1)

                if process.poll() is None:
                    process.wait(timeout=90)

            except KeyboardInterrupt:
                process.send_signal(signal.SIGINT)

                try:
                    process.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    process.kill()

                raise

            filepath = _find_output_file(output_dir)

            if filepath and filepath.stat().st_size >= 512 * 1024:

                print(
                    f"Captura correcta: {filepath} "
                    f"({filepath.stat().st_size} bytes)"
                )

                return CaptureResult(
                    filepath=str(filepath),
                    duration_seconds=probe_duration_seconds(filepath),
                    info=info,
                )

            last_error = (
                f"yt-dlp terminó con código {process.returncode} "
                "sin generar un vídeo válido."
            )

        except Exception as exc:
            last_error = str(exc)
            print(f"Error en el intento {attempt}: {last_error}")

        if attempt < max_attempts:
            print(
                f"Esperando {retry_delay} segundos antes de reintentar..."
            )
            time.sleep(retry_delay)

    raise TikTokLiveError(
        "No se pudo capturar el TikTok LIVE después de "
        f"{max_attempts} intentos.\n"
        f"Último error: {last_error}"
    )
