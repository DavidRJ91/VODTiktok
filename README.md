# TikTok LIVE.IS

Versión experimental basada en la arquitectura GitHub Pages + GitHub Actions + Python + YouTube.

## Qué hace

1. Pegas una URL de TikTok LIVE.
2. GitHub Pages dispara `process-tiktok-live.yml`.
3. GitHub Actions usa `yt-dlp` para comprobar y capturar el LIVE.
4. El vídeo se sube a YouTube como público, oculto o programado.
5. El resultado se guarda en `run_status/<run_id>.json`.

## Instalación

### 1. Crear el repositorio

Puedes partir de un fork de VOD.IS o crear un repositorio nuevo y copiar estos archivos.

### 2. Secrets de GitHub Actions

En `Settings → Secrets and variables → Actions`, crea:

- `YOUTUBE_CLIENT_ID`
- `YOUTUBE_CLIENT_SECRET`
- `YOUTUBE_REFRESH_TOKEN`

### 3. GitHub Pages

En `Settings → Pages`:

- Source: Deploy from a branch
- Branch: `main`
- Folder: `/docs`

### 4. Token para la interfaz

Crea un Fine-grained Personal Access Token para el repositorio. Debe poder disparar workflows y consultar Actions. La interfaz lo guarda únicamente en `localStorage` del navegador.

## Primera prueba

Usa un LIVE corto al que tengas derecho a grabar y republicar.

- Modo: `live_simple`
- Privacidad: `unlisted`

Para una prueba corta puedes editar temporalmente `MAX_RECORD_SECONDS` en el workflow o en el script.

## Limitaciones

- TikTok puede cambiar su sistema y `yt-dlp` puede dejar de acceder a determinados LIVE.
- GitHub Actions tiene límites de duración y almacenamiento.
- La captura empieza desde el momento de conexión; no recupera automáticamente lo emitido antes.
- Úsalo solo con contenido que tengas derecho a grabar y subir a YouTube.
