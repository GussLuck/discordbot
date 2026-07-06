# Discord Bot Básico

Un bot simple de Discord en Python con comandos básicos.

## Requisitos

- Python 3.8 o superior
- pip (gestor de paquetes de Python)

## Configuración

### 1. Crear un entorno virtual

```bash
python -m venv venv

# En macOS/Linux:
source venv/bin/activate

# En Windows:
venv\Scripts\activate
```

### 2. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 3. Obtener el token del bot

1. Ve a [Discord Developer Portal](https://discord.com/developers/applications)
2. Haz clic en "New Application"
3. Dale un nombre a tu bot
4. Ve a la pestaña "Bot" y haz clic en "Add Bot"
5. Bajo "TOKEN", haz clic en "Copy"
6. Copia el token

### 4. Configurar las variables de entorno

1. Copia `.env.example` a `.env`:
   ```bash
   cp .env.example .env
   ```

2. Abre el archivo `.env` y pega tu token:
   ```
   DISCORD_TOKEN=tu_token_aqui
   ```

### 5. Configurar permisos del bot

1. En Developer Portal, ve a "OAuth2" → "URL Generator"
2. Selecciona estos scopes: `bot`
3. Selecciona estos permisos:
   - Send Messages
   - Read Messages/View Channels
   - Read Message History
4. Copia la URL generada y abre en tu navegador
5. Selecciona el servidor donde quieres agregar el bot

## Ejecutar el bot

```bash
python main.py
```

Deberías ver algo como:
```
NombreDelBot#1234 se ha conectado a Discord
```

## Comandos disponibles

- `!ping` - Muestra la latencia del bot
- `!hola` - El bot te saluda
- `!ayuda` - Muestra los comandos disponibles

## Agregar comandos personalizados

Abre `main.py` y agrega nuevos comandos con el decorador `@bot.command()`:

```python
@bot.command(name='micomando', help='Descripción del comando')
async def micomando(ctx):
    await ctx.send('Mi respuesta')
```

## Solución de problemas

- **Token inválido**: Verifica que copiaste correctamente el token en `.env`
- **Permisos insuficientes**: Asegúrate de que el bot tiene permisos en el servidor
- **Bot no responde**: Verifica que el bot esté online y que uses el prefijo correcto (`!`)
