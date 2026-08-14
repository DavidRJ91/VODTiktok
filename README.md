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

Opcionales, solo si te aparece el error descrito en "Solución de problemas":

- `TIKTOK_COOKIES` (contenido de un fichero cookies.txt de una sesión logueada)
- `TIKTOK_PROXY` (URL de un proxy residencial, ej. `http://user:pass@host:puerto`)

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

## Solución de problemas

### "The channel is not currently live" con el canal realmente en directo

Es un problema conocido y muy reportado de `yt-dlp` con TikTok: TikTok bloquea
agresivamente las IPs de datacenter (incluidas las de los runners de GitHub
Actions) y les sirve una página de captcha en vez de la información real del
LIVE; `yt-dlp` interpreta esa respuesta como "no está en directo". No es un
fallo de este proyecto ni indica que el LIVE no exista.

Orden recomendado para solucionarlo:

1. Confirma que ves el error también con `yt-dlp` actualizado (`pip install -U yt-dlp`) — TikTok cambia su web con frecuencia y las versiones antiguas fallan más.
2. Exporta las cookies de una sesión de TikTok logueada en tu navegador (extensión tipo "Get cookies.txt") y guárdalas como el secret `TIKTOK_COOKIES`. Ayuda, aunque no siempre es suficiente por sí solo.
3. Si sigue fallando, añade un proxy residencial en el secret `TIKTOK_PROXY`. Es la solución más fiable porque evita por completo el bloqueo por IP de datacenter, a costa de depender de un servicio de proxy de pago.
4. Alternativa a 3: usa un [runner autoalojado](https://docs.github.com/actions/hosting-your-own-runners) en una IP no perteneciente a un datacenter conocido, en vez del runner `ubuntu-latest` de GitHub.

## Limitaciones

- TikTok puede cambiar su sistema y `yt-dlp` puede dejar de acceder a determinados LIVE.
- GitHub Actions tiene límites de duración y almacenamiento.
- La captura empieza desde el momento de conexión; no recupera automáticamente lo emitido antes.
- Úsalo solo con contenido que tengas derecho a grabar y subir a YouTube.
