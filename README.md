# TikTok LIVE.IS

Versión experimental basada en la arquitectura GitHub Pages + GitHub Actions + Python + YouTube.

## Qué hace

1. Pegas una URL de TikTok LIVE en la interfaz (GitHub Pages).
2. La interfaz dispara `process-tiktok-live.yml` (GitHub Actions).
3. GitHub Actions usa `yt-dlp` para capturar el LIVE.
4. El vídeo se sube a YouTube como público, oculto o privado (o programado).
5. El resultado se guarda en `run_status/<run_id>.json`.

## Instalación

### 1. Repositorio

Clona o copia estos archivos a tu repositorio (rama `main`). La interfaz está en `docs/`.

### 2. Secrets de GitHub Actions

En `Settings → Secrets and variables → Actions`, crea:

- `YOUTUBE_CLIENT_ID`
- `YOUTUBE_CLIENT_SECRET`
- `YOUTUBE_REFRESH_TOKEN`

El refresh token debe tener el scope `youtube.upload` (proyecto de Google Cloud con la API de YouTube Data v3 habilitada).

### 3. GitHub Pages

En `Settings → Pages`:

- Source: Deploy from a branch
- Branch: `main`
- Folder: `/docs`

### 4. Token para la interfaz

Crea un Fine-grained Personal Access Token para el repositorio con permiso **Actions: Read and write**. La interfaz lo guarda únicamente en `localStorage` del navegador.

## Uso

- **Modo Directo completo**: graba una sola vez durante `max_record_seconds` y sube un vídeo.
- **Modo Por partes**: graba partes de `chunk_seconds` y sube cada una como un vídeo distinto mientras el LIVE siga activo.

## Primera prueba

- Modo: `Directo completo`
- Visibilidad: `Oculto`
- Máximo de grabación: poca duración (por ejemplo 1 minuto)

## Limitaciones

- TikTok puede cambiar su sistema y `yt-dlp` puede dejar de acceder a determinados LIVE.
- GitHub Actions tiene límites de duración (máx. 360 min en este workflow) y almacenamiento.
- La captura empieza desde el momento de conexión; no recupera lo emitido antes.
- Úsalo solo con contenido que tengas derecho a grabar y subir a YouTube.
