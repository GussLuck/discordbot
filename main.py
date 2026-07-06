import os
from dotenv import load_dotenv
import discord
from discord.ext import commands
import random
from datetime import datetime

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)
start_time = datetime.now()

@bot.event
async def on_ready():
    print(f'{bot.user} se ha conectado a Discord')

@bot.command(name='ping', help='Responde con pong')
async def ping(ctx):
    await ctx.send(f'Pong! {round(bot.latency * 1000)}ms')

@bot.command(name='hola', help='Saluda al usuario')
async def hola(ctx):
    await ctx.send(f'¡Hola {ctx.author.name}!')

@bot.command(name='ayuda', help='Muestra los comandos disponibles')
async def ayuda(ctx):
    embed = discord.Embed(title='Comandos Disponibles', color=discord.Color.blue())
    embed.add_field(name='!ping', value='Muestra la latencia del bot', inline=False)
    embed.add_field(name='!hola', value='El bot te saluda', inline=False)
    embed.add_field(name='!ayuda', value='Muestra este mensaje', inline=False)
    embed.add_field(name='!dado', value='Lanza un dado (1-6)', inline=False)
    embed.add_field(name='!moneda', value='Lanza una moneda', inline=False)
    embed.add_field(name='!usuario', value='Muestra información del usuario', inline=False)
    embed.add_field(name='!servidor', value='Muestra información del servidor', inline=False)
    embed.add_field(name='!avatar [@usuario]', value='Muestra el avatar del usuario', inline=False)
    embed.add_field(name='!8ball [pregunta]', value='La bola mágica responde tu pregunta', inline=False)
    embed.add_field(name='!random [min] [max]', value='Genera un número aleatorio', inline=False)
    embed.add_field(name='!limpia [cantidad]', value='Elimina mensajes (requiere admin)', inline=False)
    embed.add_field(name='!uptime', value='Tiempo que lleva el bot activo', inline=False)
    await ctx.send(embed=embed)

@bot.command(name='dado', help='Lanza un dado')
async def dado(ctx):
    resultado = random.randint(1, 6)
    embed = discord.Embed(title='🎲 Lanzamiento de Dado', description=f'Resultado: **{resultado}**', color=discord.Color.green())
    await ctx.send(embed=embed)

@bot.command(name='moneda', help='Lanza una moneda')
async def moneda(ctx):
    resultado = random.choice(['Cara', 'Cruz'])
    emoji = '🪙'
    embed = discord.Embed(title=f'{emoji} Lanzamiento de Moneda', description=f'Resultado: **{resultado}**', color=discord.Color.gold())
    await ctx.send(embed=embed)

@bot.command(name='usuario', help='Muestra información del usuario')
async def usuario(ctx, member: discord.Member = None):
    member = member or ctx.author
    embed = discord.Embed(title='Información del Usuario', color=discord.Color.purple())
    embed.set_thumbnail(url=member.avatar.url)
    embed.add_field(name='Nombre', value=member.name, inline=False)
    embed.add_field(name='ID', value=member.id, inline=False)
    embed.add_field(name='Cuenta creada', value=member.created_at.strftime('%d/%m/%Y'), inline=False)
    embed.add_field(name='Se unió al servidor', value=member.joined_at.strftime('%d/%m/%Y'), inline=False)
    embed.add_field(name='Roles', value=', '.join([role.name for role in member.roles[1:]]) or 'Ninguno', inline=False)
    await ctx.send(embed=embed)

@bot.command(name='servidor', help='Muestra información del servidor')
async def servidor(ctx):
    guild = ctx.guild
    embed = discord.Embed(title='Información del Servidor', color=discord.Color.red())
    embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
    embed.add_field(name='Nombre', value=guild.name, inline=False)
    embed.add_field(name='ID', value=guild.id, inline=False)
    embed.add_field(name='Miembros', value=guild.member_count, inline=False)
    embed.add_field(name='Canales', value=len(guild.channels), inline=False)
    embed.add_field(name='Roles', value=len(guild.roles), inline=False)
    embed.add_field(name='Creado', value=guild.created_at.strftime('%d/%m/%Y'), inline=False)
    embed.add_field(name='Propietario', value=guild.owner.name, inline=False)
    await ctx.send(embed=embed)

@bot.command(name='avatar', help='Muestra el avatar del usuario')
async def avatar(ctx, member: discord.Member = None):
    member = member or ctx.author
    embed = discord.Embed(title=f'Avatar de {member.name}', color=discord.Color.cyan())
    embed.set_image(url=member.avatar.url)
    await ctx.send(embed=embed)

@bot.command(name='8ball', help='La bola mágica responde')
async def magic_8ball(ctx, *, pregunta=None):
    if not pregunta:
        await ctx.send('¡Debes hacer una pregunta! Uso: `!8ball [pregunta]`')
        return
    
    respuestas = [
        'Sí', 'No', 'Tal vez', 'Probablemente', 'Definitivamente',
        'Sin dudas', 'Muy probable', 'Poco probable', 'Pregunta más tarde',
        'No se puede determinar', 'Absolutamente no', 'Claro que sí'
    ]
    respuesta = random.choice(respuestas)
    embed = discord.Embed(title='🔮 La Bola Mágica', description=f'Pregunta: *{pregunta}*\n\nRespuesta: **{respuesta}**', color=discord.Color.magenta())
    await ctx.send(embed=embed)

@bot.command(name='random', help='Genera un número aleatorio')
async def random_number(ctx, min_num: int = 1, max_num: int = 100):
    if min_num >= max_num:
        await ctx.send('El número mínimo debe ser menor que el máximo.')
        return
    resultado = random.randint(min_num, max_num)
    embed = discord.Embed(title='🎲 Número Aleatorio', description=f'Entre {min_num} y {max_num}\n\nResultado: **{resultado}**', color=discord.Color.blue())
    await ctx.send(embed=embed)

@bot.command(name='limpia', help='Elimina mensajes (requiere admin)')
async def limpia(ctx, cantidad: int = 1):
    if not ctx.author.guild_permissions.administrator:
        await ctx.send('❌ No tienes permisos para usar este comando.')
        return
    
    if cantidad < 1 or cantidad > 100:
        await ctx.send('Debes especificar entre 1 y 100 mensajes para eliminar.')
        return
    
    await ctx.channel.purge(limit=cantidad + 1)
    embed = discord.Embed(title='✅ Mensajes Eliminados', description=f'Se han eliminado **{cantidad}** mensajes.', color=discord.Color.green())
    await ctx.send(embed=embed, delete_after=5)

@bot.command(name='uptime', help='Tiempo que lleva el bot activo')
async def uptime(ctx):
    delta = datetime.now() - start_time
    horas, residuo = divmod(int(delta.total_seconds()), 3600)
    minutos, segundos = divmod(residuo, 60)
    embed = discord.Embed(title='⏱️ Tiempo de Actividad', description=f'**{horas}h {minutos}m {segundos}s**', color=discord.Color.green())
    await ctx.send(embed=embed)

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send('Comando no encontrado. Usa `!ayuda` para ver los comandos disponibles.')
    else:
        await ctx.send(f'Error: {error}')

if __name__ == '__main__':
    bot.run(TOKEN)
