import os
import random
import sqlite3
from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import commands, tasks
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
DB_PATH = "bot_data.db"

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)
start_time = datetime.now(timezone.utc)


def db_conn():
    return sqlite3.connect(DB_PATH)


def init_db():
    conn = db_conn()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER,
            guild_id INTEGER,
            xp INTEGER DEFAULT 0,
            level INTEGER DEFAULT 1,
            balance INTEGER DEFAULT 0,
            last_daily TEXT,
            PRIMARY KEY (user_id, guild_id)
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS guild_config (
            guild_id INTEGER PRIMARY KEY,
            log_channel_id INTEGER,
            ticket_category_id INTEGER,
            automod_enabled INTEGER DEFAULT 0,
            anti_link_enabled INTEGER DEFAULT 0
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS warnings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            guild_id INTEGER,
            moderator_id INTEGER,
            reason TEXT,
            created_at TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            channel_id INTEGER,
            message TEXT,
            remind_at TEXT,
            sent INTEGER DEFAULT 0
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS shop_roles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER,
            role_id INTEGER,
            price INTEGER,
            UNIQUE(guild_id, role_id)
        )
        """
    )
    conn.commit()
    conn.close()


def ensure_user(user_id: int, guild_id: int):
    conn = db_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT OR IGNORE INTO users (user_id, guild_id) VALUES (?, ?)",
        (user_id, guild_id),
    )
    conn.commit()
    conn.close()


def add_balance(user_id: int, guild_id: int, amount: int):
    ensure_user(user_id, guild_id)
    conn = db_conn()
    cur = conn.cursor()
    cur.execute(
        "UPDATE users SET balance = balance + ? WHERE user_id = ? AND guild_id = ?",
        (amount, user_id, guild_id),
    )
    conn.commit()
    conn.close()


def spend_balance(user_id: int, guild_id: int, amount: int) -> bool:
    ensure_user(user_id, guild_id)
    conn = db_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT balance FROM users WHERE user_id = ? AND guild_id = ?",
        (user_id, guild_id),
    )
    balance = cur.fetchone()[0]
    if balance < amount:
        conn.close()
        return False
    cur.execute(
        "UPDATE users SET balance = balance - ? WHERE user_id = ? AND guild_id = ?",
        (amount, user_id, guild_id),
    )
    conn.commit()
    conn.close()
    return True


def get_profile(user_id: int, guild_id: int):
    ensure_user(user_id, guild_id)
    conn = db_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT xp, level, balance, last_daily FROM users WHERE user_id = ? AND guild_id = ?",
        (user_id, guild_id),
    )
    row = cur.fetchone()
    conn.close()
    return row


def set_guild_config(guild_id: int, field: str, value: int):
    conn = db_conn()
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO guild_config (guild_id) VALUES (?)", (guild_id,))
    cur.execute(f"UPDATE guild_config SET {field} = ? WHERE guild_id = ?", (value, guild_id))
    conn.commit()
    conn.close()


def get_guild_config(guild_id: int):
    conn = db_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT log_channel_id, ticket_category_id, automod_enabled, anti_link_enabled FROM guild_config WHERE guild_id = ?",
        (guild_id,),
    )
    row = cur.fetchone()
    conn.close()
    if row is None:
        return {"log_channel_id": None, "ticket_category_id": None, "automod": 0, "anti_link": 0}
    return {
        "log_channel_id": row[0],
        "ticket_category_id": row[1],
        "automod": row[2],
        "anti_link": row[3],
    }


def add_shop_role(guild_id: int, role_id: int, price: int):
    conn = db_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT OR REPLACE INTO shop_roles (guild_id, role_id, price) VALUES (?, ?, ?)",
        (guild_id, role_id, price),
    )
    conn.commit()
    conn.close()


def remove_shop_role(guild_id: int, role_id: int):
    conn = db_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM shop_roles WHERE guild_id = ? AND role_id = ?", (guild_id, role_id))
    conn.commit()
    conn.close()


def get_shop_roles(guild_id: int):
    conn = db_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT role_id, price FROM shop_roles WHERE guild_id = ? ORDER BY price ASC",
        (guild_id,),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


async def send_log(guild: discord.Guild, text: str):
    cfg = get_guild_config(guild.id)
    if not cfg["log_channel_id"]:
        return
    channel = guild.get_channel(cfg["log_channel_id"])
    if channel:
        await channel.send(text)


class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Abrir Ticket", style=discord.ButtonStyle.green, custom_id="ticket_open")
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        assert interaction.guild is not None
        cfg = get_guild_config(interaction.guild.id)
        category = interaction.guild.get_channel(cfg["ticket_category_id"]) if cfg["ticket_category_id"] else None
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            interaction.guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True),
        }
        name = f"ticket-{interaction.user.name}".lower().replace(" ", "-")
        channel = await interaction.guild.create_text_channel(name=name[:90], overwrites=overwrites, category=category)
        close_view = CloseTicketView()
        await channel.send(
            f"{interaction.user.mention} ticket creado. Explica tu problema y un moderador te respondera.",
            view=close_view,
        )
        await interaction.response.send_message(f"Ticket creado: {channel.mention}", ephemeral=True)


class CloseTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Cerrar Ticket", style=discord.ButtonStyle.red, custom_id="ticket_close")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Cerrando ticket en 3 segundos...", ephemeral=True)
        await send_log(interaction.guild, f"Ticket cerrado: {interaction.channel.mention} por {interaction.user.mention}")
        await interaction.channel.delete(delay=3)


class AdminPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def _check_admin(self, interaction: discord.Interaction) -> bool:
        if interaction.guild is None:
            await interaction.response.send_message("Este panel solo funciona en servidores.", ephemeral=True)
            return False
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Necesitas permisos de administrador.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Toggle AutoMod", style=discord.ButtonStyle.blurple, custom_id="admin_toggle_automod")
    async def toggle_automod(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_admin(interaction):
            return
        cfg = get_guild_config(interaction.guild.id)
        enabled = 0 if cfg["automod"] else 1
        set_guild_config(interaction.guild.id, "automod_enabled", enabled)
        await interaction.response.send_message(
            f"AutoMod {'activado' if enabled else 'desactivado'} desde panel.", ephemeral=True
        )

    @discord.ui.button(label="Toggle Anti-Link", style=discord.ButtonStyle.blurple, custom_id="admin_toggle_antilink")
    async def toggle_antilink(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_admin(interaction):
            return
        cfg = get_guild_config(interaction.guild.id)
        enabled = 0 if cfg["anti_link"] else 1
        set_guild_config(interaction.guild.id, "anti_link_enabled", enabled)
        await interaction.response.send_message(
            f"Anti-link {'activado' if enabled else 'desactivado'} desde panel.", ephemeral=True
        )

    @discord.ui.button(label="Publicar Panel Ticket", style=discord.ButtonStyle.green, custom_id="admin_post_ticket_panel")
    async def post_ticket_panel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_admin(interaction):
            return
        embed = discord.Embed(
            title="Soporte",
            description="Pulsa el boton para abrir un ticket privado con el staff.",
            color=discord.Color.green(),
        )
        await interaction.channel.send(embed=embed, view=TicketView())
        await interaction.response.send_message("Panel de tickets publicado.", ephemeral=True)


@tasks.loop(seconds=30)
async def reminder_worker():
    now_iso = datetime.now(timezone.utc).isoformat()
    conn = db_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, user_id, channel_id, message FROM reminders WHERE sent = 0 AND remind_at <= ?",
        (now_iso,),
    )
    rows = cur.fetchall()
    for reminder_id, user_id, channel_id, message in rows:
        channel = bot.get_channel(channel_id)
        if channel:
            await channel.send(f"<@{user_id}> recordatorio: {message}")
        cur.execute("UPDATE reminders SET sent = 1 WHERE id = ?", (reminder_id,))
    conn.commit()
    conn.close()


@bot.event
async def on_ready():
    init_db()
    if not reminder_worker.is_running():
        reminder_worker.start()
    bot.add_view(TicketView())
    bot.add_view(CloseTicketView())
    bot.add_view(AdminPanelView())
    try:
        synced = await bot.tree.sync()
        print(f"{bot.user} conectado. Slash commands sincronizados: {len(synced)}")
    except Exception as exc:
        print(f"Error sincronizando comandos: {exc}")


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or message.guild is None:
        return

    cfg = get_guild_config(message.guild.id)
    content_lower = message.content.lower()

    if cfg["automod"]:
        banned_words = ["spam", "scam", "estafa"]
        if any(word in content_lower for word in banned_words):
            await message.delete()
            await message.channel.send(f"{message.author.mention}, mensaje eliminado por AutoMod.", delete_after=5)
            await send_log(message.guild, f"AutoMod elimino mensaje de {message.author.mention} por palabra bloqueada.")
            return

    if cfg["anti_link"] and ("http://" in content_lower or "https://" in content_lower):
        if not message.author.guild_permissions.manage_messages:
            await message.delete()
            await message.channel.send(f"{message.author.mention}, links no permitidos en este servidor.", delete_after=5)
            await send_log(message.guild, f"Anti-link elimino mensaje con link de {message.author.mention}.")
            return

    ensure_user(message.author.id, message.guild.id)
    xp_gain = random.randint(5, 12)
    conn = db_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT xp, level FROM users WHERE user_id = ? AND guild_id = ?",
        (message.author.id, message.guild.id),
    )
    xp, level = cur.fetchone()
    new_xp = xp + xp_gain
    next_level_xp = level * 100

    if new_xp >= next_level_xp:
        level += 1
        new_xp -= next_level_xp
        add_balance(message.author.id, message.guild.id, 50)
        await message.channel.send(
            f"{message.author.mention} subiste a nivel **{level}** y ganaste **50** monedas!"
        )

    cur.execute(
        "UPDATE users SET xp = ?, level = ? WHERE user_id = ? AND guild_id = ?",
        (new_xp, level, message.author.id, message.guild.id),
    )
    conn.commit()
    conn.close()

    await bot.process_commands(message)


@bot.tree.command(name="ping", description="Muestra latencia del bot")
async def slash_ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"Pong! {round(bot.latency * 1000)}ms")


@bot.tree.command(name="perfil", description="Muestra tu perfil de nivel y economia")
async def slash_profile(interaction: discord.Interaction, usuario: discord.Member | None = None):
    if interaction.guild is None:
        await interaction.response.send_message("Este comando solo funciona en servidores.", ephemeral=True)
        return
    member = usuario or interaction.user
    xp, level, balance, _ = get_profile(member.id, interaction.guild.id)
    embed = discord.Embed(title=f"Perfil de {member.display_name}", color=discord.Color.blue())
    embed.add_field(name="Nivel", value=str(level), inline=True)
    embed.add_field(name="XP", value=str(xp), inline=True)
    embed.add_field(name="Monedas", value=str(balance), inline=True)
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="daily", description="Reclama tu recompensa diaria")
async def slash_daily(interaction: discord.Interaction):
    if interaction.guild is None:
        await interaction.response.send_message("Este comando solo funciona en servidores.", ephemeral=True)
        return
    ensure_user(interaction.user.id, interaction.guild.id)
    now = datetime.now(timezone.utc)

    conn = db_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT last_daily FROM users WHERE user_id = ? AND guild_id = ?",
        (interaction.user.id, interaction.guild.id),
    )
    last_daily = cur.fetchone()[0]

    if last_daily:
        last_dt = datetime.fromisoformat(last_daily)
        if now - last_dt < timedelta(hours=24):
            remaining = timedelta(hours=24) - (now - last_dt)
            hours = int(remaining.total_seconds() // 3600)
            minutes = int((remaining.total_seconds() % 3600) // 60)
            await interaction.response.send_message(
                f"Ya reclamaste tu daily. Vuelve en {hours}h {minutes}m.", ephemeral=True
            )
            conn.close()
            return

    reward = random.randint(100, 250)
    cur.execute(
        "UPDATE users SET balance = balance + ?, last_daily = ? WHERE user_id = ? AND guild_id = ?",
        (reward, now.isoformat(), interaction.user.id, interaction.guild.id),
    )
    conn.commit()
    conn.close()
    await interaction.response.send_message(f"Reclamaste tu daily: **{reward}** monedas.")


@bot.tree.command(name="leaderboard", description="Ranking de niveles del servidor")
async def slash_leaderboard(interaction: discord.Interaction):
    if interaction.guild is None:
        await interaction.response.send_message("Este comando solo funciona en servidores.", ephemeral=True)
        return
    conn = db_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT user_id, level, xp FROM users WHERE guild_id = ? ORDER BY level DESC, xp DESC LIMIT 10",
        (interaction.guild.id,),
    )
    rows = cur.fetchall()
    conn.close()

    if not rows:
        await interaction.response.send_message("No hay datos aun.")
        return

    lines = []
    for index, (user_id, level, xp) in enumerate(rows, start=1):
        lines.append(f"{index}. <@{user_id}> - Nivel {level} ({xp} XP)")
    await interaction.response.send_message("\n".join(lines))


@bot.tree.command(name="warn", description="Advertir a un usuario")
@app_commands.default_permissions(moderate_members=True)
async def slash_warn(interaction: discord.Interaction, usuario: discord.Member, razon: str = "Sin razon"):
    if interaction.guild is None:
        await interaction.response.send_message("Este comando solo funciona en servidores.", ephemeral=True)
        return
    conn = db_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO warnings (user_id, guild_id, moderator_id, reason, created_at) VALUES (?, ?, ?, ?, ?)",
        (usuario.id, interaction.guild.id, interaction.user.id, razon, datetime.now(timezone.utc).isoformat()),
    )
    cur.execute(
        "SELECT COUNT(*) FROM warnings WHERE user_id = ? AND guild_id = ?",
        (usuario.id, interaction.guild.id),
    )
    total_warns = cur.fetchone()[0]
    conn.commit()
    conn.close()
    await interaction.response.send_message(
        f"{usuario.mention} advertido. Total de warns: **{total_warns}**. Razon: {razon}"
    )
    await send_log(interaction.guild, f"{interaction.user.mention} advirtio a {usuario.mention}. Razon: {razon}")


@bot.tree.command(name="warnings", description="Ver advertencias de un usuario")
@app_commands.default_permissions(moderate_members=True)
async def slash_warnings(interaction: discord.Interaction, usuario: discord.Member):
    if interaction.guild is None:
        await interaction.response.send_message("Este comando solo funciona en servidores.", ephemeral=True)
        return
    conn = db_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT reason, created_at FROM warnings WHERE user_id = ? AND guild_id = ? ORDER BY id DESC LIMIT 10",
        (usuario.id, interaction.guild.id),
    )
    rows = cur.fetchall()
    conn.close()

    if not rows:
        await interaction.response.send_message(f"{usuario.mention} no tiene warns.")
        return

    lines = [f"- {reason} ({created_at[:19]})" for reason, created_at in rows]
    await interaction.response.send_message(f"Warns de {usuario.mention}:\n" + "\n".join(lines))


@bot.tree.command(name="clear", description="Borra mensajes del canal")
@app_commands.default_permissions(manage_messages=True)
async def slash_clear(interaction: discord.Interaction, cantidad: app_commands.Range[int, 1, 100]):
    if interaction.channel is None:
        await interaction.response.send_message("Canal invalido.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    deleted = await interaction.channel.purge(limit=cantidad)
    await interaction.followup.send(f"Mensajes eliminados: {len(deleted)}", ephemeral=True)


@bot.tree.command(name="mute", description="Silencia a un usuario por minutos")
@app_commands.default_permissions(moderate_members=True)
async def slash_mute(
    interaction: discord.Interaction,
    usuario: discord.Member,
    minutos: app_commands.Range[int, 1, 10080],
    razon: str = "Sin razon",
):
    until = datetime.now(timezone.utc) + timedelta(minutes=minutos)
    await usuario.timeout(until, reason=razon)
    await interaction.response.send_message(
        f"{usuario.mention} silenciado por {minutos} minutos. Razon: {razon}"
    )
    await send_log(interaction.guild, f"{interaction.user.mention} silencio a {usuario.mention} por {minutos}m")


@bot.tree.command(name="ticketpanel", description="Publica panel para crear tickets")
@app_commands.default_permissions(manage_channels=True)
async def slash_ticket_panel(interaction: discord.Interaction):
    embed = discord.Embed(
        title="Soporte",
        description="Pulsa el boton para abrir un ticket privado con el staff.",
        color=discord.Color.green(),
    )
    await interaction.response.send_message(embed=embed, view=TicketView())


@bot.tree.command(name="setlog", description="Define canal de logs del bot")
@app_commands.default_permissions(administrator=True)
async def slash_set_log(interaction: discord.Interaction, canal: discord.TextChannel):
    if interaction.guild is None:
        await interaction.response.send_message("Este comando solo funciona en servidores.", ephemeral=True)
        return
    set_guild_config(interaction.guild.id, "log_channel_id", canal.id)
    await interaction.response.send_message(f"Canal de logs configurado en {canal.mention}")


@bot.tree.command(name="setticketcategory", description="Define categoria donde se crean tickets")
@app_commands.default_permissions(administrator=True)
async def slash_set_ticket_category(interaction: discord.Interaction, categoria: discord.CategoryChannel):
    if interaction.guild is None:
        await interaction.response.send_message("Este comando solo funciona en servidores.", ephemeral=True)
        return
    set_guild_config(interaction.guild.id, "ticket_category_id", categoria.id)
    await interaction.response.send_message(f"Categoria de tickets configurada: {categoria.name}")


@bot.tree.command(name="automod", description="Activa o desactiva AutoMod basico")
@app_commands.default_permissions(administrator=True)
async def slash_automod(interaction: discord.Interaction, activo: bool):
    if interaction.guild is None:
        await interaction.response.send_message("Este comando solo funciona en servidores.", ephemeral=True)
        return
    set_guild_config(interaction.guild.id, "automod_enabled", 1 if activo else 0)
    await interaction.response.send_message(f"AutoMod {'activado' if activo else 'desactivado'}.")


@bot.tree.command(name="antilink", description="Bloquea links para usuarios sin permisos")
@app_commands.default_permissions(administrator=True)
async def slash_antilink(interaction: discord.Interaction, activo: bool):
    if interaction.guild is None:
        await interaction.response.send_message("Este comando solo funciona en servidores.", ephemeral=True)
        return
    set_guild_config(interaction.guild.id, "anti_link_enabled", 1 if activo else 0)
    await interaction.response.send_message(f"Anti-link {'activado' if activo else 'desactivado'}.")


@bot.tree.command(name="recordatorio", description="Crea un recordatorio en minutos")
async def slash_reminder(interaction: discord.Interaction, minutos: app_commands.Range[int, 1, 10080], mensaje: str):
    remind_at = datetime.now(timezone.utc) + timedelta(minutes=minutos)
    conn = db_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO reminders (user_id, channel_id, message, remind_at) VALUES (?, ?, ?, ?)",
        (interaction.user.id, interaction.channel_id, mensaje, remind_at.isoformat()),
    )
    conn.commit()
    conn.close()
    await interaction.response.send_message(f"Recordatorio guardado para {minutos} minutos.", ephemeral=True)


@bot.tree.command(name="status", description="Muestra estado del bot")
async def slash_status(interaction: discord.Interaction):
    delta = datetime.now(timezone.utc) - start_time
    hours, remainder = divmod(int(delta.total_seconds()), 3600)
    minutes, seconds = divmod(remainder, 60)
    embed = discord.Embed(title="Estado del Bot", color=discord.Color.blurple())
    embed.add_field(name="Latencia", value=f"{round(bot.latency * 1000)}ms", inline=True)
    embed.add_field(name="Uptime", value=f"{hours}h {minutes}m {seconds}s", inline=True)
    embed.add_field(name="Servidores", value=str(len(bot.guilds)), inline=True)
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="adminpanel", description="Publica un panel de administracion con botones")
@app_commands.default_permissions(administrator=True)
async def slash_admin_panel(interaction: discord.Interaction):
    embed = discord.Embed(
        title="Panel Admin",
        description="Usa estos botones para activar funciones sin escribir comandos.",
        color=discord.Color.orange(),
    )
    await interaction.response.send_message(embed=embed, view=AdminPanelView())


@bot.tree.command(name="shop_addrole", description="Agrega o actualiza un rol en la tienda")
@app_commands.default_permissions(administrator=True)
async def slash_shop_addrole(
    interaction: discord.Interaction,
    rol: discord.Role,
    precio: app_commands.Range[int, 1, 1000000],
):
    if interaction.guild is None:
        await interaction.response.send_message("Este comando solo funciona en servidores.", ephemeral=True)
        return
    add_shop_role(interaction.guild.id, rol.id, precio)
    await interaction.response.send_message(f"Rol {rol.mention} agregado a la tienda por {precio} monedas.")


@bot.tree.command(name="shop_removerole", description="Quita un rol de la tienda")
@app_commands.default_permissions(administrator=True)
async def slash_shop_remove_role(interaction: discord.Interaction, rol: discord.Role):
    if interaction.guild is None:
        await interaction.response.send_message("Este comando solo funciona en servidores.", ephemeral=True)
        return
    remove_shop_role(interaction.guild.id, rol.id)
    await interaction.response.send_message(f"Rol {rol.mention} eliminado de la tienda.")


@bot.tree.command(name="shop", description="Muestra la tienda de roles")
async def slash_shop(interaction: discord.Interaction):
    if interaction.guild is None:
        await interaction.response.send_message("Este comando solo funciona en servidores.", ephemeral=True)
        return
    rows = get_shop_roles(interaction.guild.id)
    if not rows:
        await interaction.response.send_message("La tienda esta vacia. Un admin debe cargar roles.")
        return

    embed = discord.Embed(title="Tienda de Roles", color=discord.Color.gold())
    for role_id, price in rows[:25]:
        role = interaction.guild.get_role(role_id)
        if role:
            embed.add_field(name=role.name, value=f"Precio: {price} monedas", inline=False)
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="buyrole", description="Compra un rol de la tienda")
async def slash_buy_role(interaction: discord.Interaction, rol: discord.Role):
    if interaction.guild is None:
        await interaction.response.send_message("Este comando solo funciona en servidores.", ephemeral=True)
        return

    rows = get_shop_roles(interaction.guild.id)
    price = None
    for role_id, item_price in rows:
        if role_id == rol.id:
            price = item_price
            break

    if price is None:
        await interaction.response.send_message("Ese rol no esta en la tienda.", ephemeral=True)
        return

    if rol in interaction.user.roles:
        await interaction.response.send_message("Ya tienes ese rol.", ephemeral=True)
        return

    if interaction.guild.me is not None and rol >= interaction.guild.me.top_role:
        await interaction.response.send_message(
            "No puedo asignar ese rol porque esta por encima de mi rol mas alto.",
            ephemeral=True,
        )
        return

    if not spend_balance(interaction.user.id, interaction.guild.id, price):
        await interaction.response.send_message("No tienes monedas suficientes.", ephemeral=True)
        return

    try:
        await interaction.user.add_roles(rol, reason="Compra en tienda")
    except discord.Forbidden:
        add_balance(interaction.user.id, interaction.guild.id, price)
        await interaction.response.send_message("No tengo permisos para asignar ese rol.", ephemeral=True)
        return

    await interaction.response.send_message(f"Compra completada: obtuviste {rol.mention} por {price} monedas.")


@bot.event
async def on_command_error(ctx, error):
    await ctx.send(f"Error: {error}")


if __name__ == "__main__":
    bot.run(TOKEN)
