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

### 3. (Recomendado) Cookies de TikTok — `TIKTOK_COOKIES`

TikTok requiere un token (`msToken`) para devolver los datos del LIVE; sin él, `yt-dlp` suele fallar con el error falso **"The channel is not currently live"**. La forma más fiable de evitarlo es aportar cookies de una sesión con TikTok:

1. Instala la extensión **"Get cookies.txt LOCALLY"** en Chrome/Edge y entra a `tiktok.com` iniciando sesión.
2. Exporta las cookies (formato Netscape) y codifícalas en base64:

   ```bash
   # En Windows (PowerShell):
   Get-Content -Raw cookies.txt | ConvertTo-Base64 | Set-Content -NoNewline tiktok_cookies_b64.txt
   # En Linux/macOS:
   base64 -w0 cookies.txt > tiktok_cookies_b64.txt
   ```

3. Copia el contenido de `tiktok_cookies_b64.txt` en el secret `TIKTOK_COOKIES` de GitHub Actions.

> Las cookies caducan; si dejan de funcionar, expórtalas de nuevo. El secret es opcional: sin él el workflow reintenta igualmente (con menos probabilidad de éxito).

### 4. GitHub Pages

En `Settings → Pages`:

- Source: Deploy from a branch
- Branch: `main`
- Folder: `/docs`

### 5. Token para la interfaz

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
