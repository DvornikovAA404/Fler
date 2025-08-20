# bot.py
import discord
from discord.ext import commands
from datetime import datetime, timezone
import re
from difflib import get_close_matches
from typing import List
from discord import app_commands
from discord.utils import get

# ══════════ НАСТРОЙКИ ══════════
BOT_PREFIX = "!!!!"
ALLOWED_ROLE_IDS = [1407717900491554949]  # ID ролей, которым разрешены команды
LOG_CHANNEL_ID = 1407718346081964053  # ID канала, куда писать логи
ROOMS_SOURCE_CHANNEL_ID = 1407726599889092779  # канал, где каждое сообщение = название
ALLOWED_CATEGORY_ID     = 1407729261321916459
# ════════════════════════════════

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=BOT_PREFIX, intents=intents, help_command=None)

# --------------------- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---------------------
def has_allowed_role(user: discord.Member) -> bool:
    return any(role.id in ALLOWED_ROLE_IDS for role in user.roles)

# ------------------------------------------------------------------
# УНИВЕРСАЛЬНОЕ ЛОГИРОВАНИЕ
# level: "success" | "warn" | "error"
# ------------------------------------------------------------------

async def room_autocomplete(interaction: discord.Interaction, current: str):
    """Возвращает до 25 названий, начинающихся с current."""
    channel = bot.get_channel(ROOMS_SOURCE_CHANNEL_ID)
    if not channel:
        return []

    names = []
    async for msg in channel.history(limit=None):
        if msg.content and msg.content.strip():
            names.append(msg.content.strip())

    # уникальные, отсортированные, фильтр
    matches = [name for name in sorted(set(names))
               if current.lower() in name.lower()][:25]
    return [discord.app_commands.Choice(name=name, value=name) for name in matches]

async def log_action(channel: discord.TextChannel | None,
                     author: discord.Member | discord.User,
                     description: str,
                     extra: str = "",
                     level: str = "success",
                     send_dm: bool = True):
    color_map = {"success": 0x1e8e3e, "warn": 0xff7800, "error": 0x990000}

    compact = (
        f"{description} | {author.display_name} | "
        f"{extra}"
    ).strip()

    embed = discord.Embed(description=compact,
                          color=color_map[level],
                          timestamp=datetime.now(timezone.utc))

    log_ch = bot.get_channel(LOG_CHANNEL_ID)
    if log_ch:
        await log_ch.send(embed=embed)

    if send_dm and author != bot.user:
        try:
            await author.send(embed=embed)
        except discord.Forbidden:
            pass
# ------------------------------------------------------------------
#  КОМАНДЫ ОЧИСТКИ (со встроенным логированием и раскраской embed’ов)
# ------------------------------------------------------------------

@bot.command(name="очистить")
@commands.has_permissions(manage_messages=True)
async def очистить(ctx: commands.Context, count: int):
    """!очистить <N> — удалить последние N сообщений."""
    try:
        if not has_allowed_role(ctx.author):
            await log_action(ctx.channel, ctx.author,
                             "Недостаточно прав для использования команды `очистить`.",
                             level="warn")
            return

        await ctx.message.delete()
        deleted = await ctx.channel.purge(limit=count)
        await log_action(ctx.channel, ctx.author,
                         f"Успешно удалено {len(deleted)} сообщений.",
                         level="success")
    except commands.BadArgument:
        await log_action(ctx.channel, ctx.author,
                         "Ошибка синтаксиса: `!очистить <целое-число>`.",
                         level="warn")
    except Exception as e:
        await log_action(ctx.channel, ctx.author,
                         f"Не удалось выполнить `очистить`: {e}",
                         level="error")

@bot.command(name="очиститьюзера")
@commands.has_permissions(manage_messages=True)
async def очиститьюзера(ctx: commands.Context, count: int, member: discord.Member):
    """!очиститьюзера <N> @Пользователь — удалить N сообщений от участника."""
    try:
        if not has_allowed_role(ctx.author):
            await log_action(ctx.channel, ctx.author,
                             "Недостаточно прав для использования команды `очиститьюзера`.",
                             level="warn")
            return

        await ctx.message.delete()

        def check(msg):
            return msg.author == member

        deleted = await ctx.channel.purge(limit=200, check=check, bulk=True)
        to_delete = deleted[:count]

        # Добираем оставшиеся вручную, если нужно
        if len(to_delete) < count:
            async for msg in ctx.channel.history(limit=None):
                if msg.author == member and msg not in to_delete:
                    await msg.delete()
                    to_delete.append(msg)
                    if len(to_delete) >= count:
                        break

        await log_action(ctx.channel, ctx.author,
                         f"Удалено {len(to_delete)} сообщений от {member}.",
                         level="success")
    except commands.MissingRequiredArgument:
        await log_action(ctx.channel, ctx.author,
                         "Ошибка синтаксиса: `!очиститьюзера <N> @Пользователь`.",
                         level="warn")
    except Exception as e:
        await log_action(ctx.channel, ctx.author,
                         f"Не удалось выполнить `очиститьюзера`: {e}",
                         level="error")

@bot.command(name="очиститьфразы")
@commands.has_permissions(manage_messages=True)
async def очиститьфразы(ctx: commands.Context, count: int, *, phrase: str):
    """!очиститьфразы <N> "фраза" — удалить N сообщений, содержащих фразу."""
    try:
        if not has_allowed_role(ctx.author):
            await log_action(ctx.channel, ctx.author,
                             "Недостаточно прав для использования команды `очиститьфразы`.",
                             level="warn")
            return

        await ctx.message.delete()

        def check(msg):
            return phrase.lower() in msg.content.lower()

        deleted = await ctx.channel.purge(limit=200, check=check, bulk=True)
        to_delete = deleted[:count]

        if len(to_delete) < count:
            async for msg in ctx.channel.history(limit=None):
                if phrase.lower() in msg.content.lower() and msg not in to_delete:
                    await msg.delete()
                    to_delete.append(msg)
                    if len(to_delete) >= count:
                        break

        await log_action(ctx.channel, ctx.author,
                         f"Удалено {len(to_delete)} сообщений, содержащих «{phrase}».",
                         level="success")
    except commands.BadArgument:
        await log_action(ctx.channel, ctx.author,
                         "Ошибка синтаксиса: `!очиститьфразы <N> \"фраза\"`.",
                         level="warn")
    except Exception as e:
        await log_action(ctx.channel, ctx.author,
                         f"Не удалось выполнить `очиститьфразы`: {e}",
                         level="error")

@bot.command(name="точнаяочистка")
@commands.has_permissions(manage_messages=True)
async def точнаяочистка(ctx: commands.Context, count: int, *, phrase: str):
    """!точнаяочистка <N> "фраза" — удалить N сообщений, где текст = фразе."""
    try:
        if not has_allowed_role(ctx.author):
            await log_action(ctx.channel, ctx.author,
                             "Недостаточно прав для использования команды `точнаяочистка`.",
                             level="warn")
            return

        await ctx.message.delete()

        def check(msg):
            return msg.content.lower() == phrase.lower()

        deleted = await ctx.channel.purge(limit=200, check=check, bulk=True)
        to_delete = deleted[:count]

        if len(to_delete) < count:
            async for msg in ctx.channel.history(limit=None):
                if msg.content.lower() == phrase.lower() and msg not in to_delete:
                    await msg.delete()
                    to_delete.append(msg)
                    if len(to_delete) >= count:
                        break

        await log_action(ctx.channel, ctx.author,
                         f"Удалено {len(to_delete)} сообщений, точно совпадающих с «{phrase}».",
                         level="success")
    except commands.BadArgument:
        await log_action(ctx.channel, ctx.author,
                         "Ошибка синтаксиса: `!точнаяочистка <N> \"фраза\"`.",
                         level="warn")
    except Exception as e:
        await log_action(ctx.channel, ctx.author,
                         f"Не удалось выполнить `точнаяочистка`: {e}",
                         level="error")

@bot.command(name="очиститьдо")
@commands.has_permissions(manage_messages=True)
async def очиститьдо(ctx: commands.Context, date_str: str):
    """!очиститьдо ДД.ММ.ГГГГ — удалить все сообщения до указанной даты (включительно)."""
    try:
        if not has_allowed_role(ctx.author):
            await log_action(ctx.channel, ctx.author,
                             "Недостаточно прав для использования команды `очиститьдо`.",
                             level="warn")
            return

        await ctx.message.delete()
        try:
            until_date = datetime.strptime(date_str, "%d.%m.%Y").replace(tzinfo=timezone.utc)
        except ValueError:
            await log_action(ctx.channel, ctx.author,
                             "Неверный формат даты: используйте ДД.ММ.ГГГГ.",
                             level="warn")
            return

        deleted = await ctx.channel.purge(after=until_date, oldest_first=True, bulk=True)
        await log_action(ctx.channel, ctx.author,
                         f"Удалено {len(deleted)} сообщений до {date_str}.",
                         level="success")
    except Exception as e:
        await log_action(ctx.channel, ctx.author,
                         f"Не удалось выполнить `очиститьдо`: {e}",
                         level="error")


# --------------------- HELP ---------------------
@bot.command(aliases=["помоги", "help"])
async def help_cmd(ctx: commands.Context):
    """!help — отправляет список команд в личные сообщения."""
    await ctx.message.delete()
    embed = discord.Embed(
        title="Команды очистки чата",
        description="Все команды требуют одну из разрешённых ролей.",
        color=0x00bfff
    )
    embed.add_field(
        name=f"{BOT_PREFIX}очистить <N>",
        value="Удалить последние N сообщений.",
        inline=False
    )
    embed.add_field(
        name=f"{BOT_PREFIX}очиститьюзера <N> @Пользователь",
        value="Удалить последние N сообщений от конкретного участника.",
        inline=False
    )
    embed.add_field(
        name=f"{BOT_PREFIX}очиститьфразы <N> \"фраза\"",
        value="Удалить N сообщений, содержащих указанную фразу (регистр не учитывается).",
        inline=False
    )
    embed.add_field(
        name=f"{BOT_PREFIX}точнаяочистка <N> \"фраза\"",
        value="Удалить N сообщений, текст которых **точно совпадает** с указанной фразой.",
        inline=False
    )
    embed.add_field(
        name=f"{BOT_PREFIX}очиститьдо ДД.ММ.ГГГГ",
        value="Удалить все сообщения до указанной даты (включительно).",
        inline=False
    )
    try:
        await ctx.author.send(embed=embed)
    except discord.Forbidden:
        await ctx.send("Не получается отправить вам личное сообщение. Возможно, у вас закрыты ЛС.", delete_after=10)

# --------------------- Slash ----------------------

@bot.tree.command(name="move", description="Переместиться в другую комнату")
@app_commands.describe(room="Название целевой комнаты")
@app_commands.autocomplete(room=room_autocomplete)
async def move(interaction: discord.Interaction, room: str):
    member = interaction.user
    guild = interaction.guild
    source_channel = interaction.channel

    # ---------- проверки ----------
    if not isinstance(source_channel, discord.TextChannel) or \
       source_channel.category_id != ALLOWED_CATEGORY_ID:
        await log_action(source_channel, member,
                         "/move вне категории", level="warn")
        return await interaction.response.send_message(
            "Команду можно использовать только в разрешённой категории.", ephemeral=True
        )

    list_ch = bot.get_channel(ROOMS_SOURCE_CHANNEL_ID)
    valid_rooms = {msg.content.strip() async for msg in list_ch.history(limit=None)
                   if msg.content and msg.content.strip()}
    if room not in valid_rooms:
        await log_action(source_channel, member,
                         f"нет локации: {room}", level="warn")
        return await interaction.response.send_message(
            f"Локация **{room}** отсутствует в списке.", ephemeral=True
        )

    target_channel = discord.utils.get(guild.text_channels,
                                       name=room,
                                       category_id=ALLOWED_CATEGORY_ID)
    if not target_channel:
        await log_action(source_channel, member,
                         f"канал вне категории: {room}", level="warn")
        return await interaction.response.send_message(
            f"Канал **{room}** не находится в разрешённой категории.", ephemeral=True
        )

    # ---------- перемещение ----------
    try:
        await target_channel.set_permissions(member, read_messages=True, send_messages=True)
        await interaction.response.send_message(
            f"{member.display_name} ушёл в {target_channel.mention}"
        )
        move_msg = await interaction.original_response()
        await source_channel.set_permissions(member, read_messages=False, send_messages=False)

        await log_action(
            None,
            member,
            "перемещён",
            extra=f"{source_channel.mention} → {target_channel.mention} [ССЫЛКА]({move_msg.jump_url})",
            level="success",
            send_dm=False
        )
    except discord.Forbidden:
        await log_action(source_channel, member,
                         "недостаточно прав", level="error")
        await interaction.response.send_message(
            "Не удалось изменить права.", ephemeral=True
        )


# --------------------- ЗАПУСК ---------------------
@bot.event
async def on_connect():
    now = datetime.now(timezone.utc)
    await log_action(None, bot.user, f"Флер подключилась к Discord ({now:%d.%m.%Y %H:%M:%S} UTC)", level="success")

@bot.event
async def on_ready():
    await bot.tree.sync()
    now = datetime.now(timezone.utc)
    await log_action(None, bot.user, f"Флер полностью готова к работе ({now:%d.%m.%Y %H:%M:%S} UTC)", level="success")

@bot.event
async def on_disconnect():
    now = datetime.now(timezone.utc)
    await log_action(None, bot.user, f"Бот отключился от Discord ({now:%d.%m.%Y %H:%M:%S} UTC)", level="warn")

@bot.event
async def on_command_error(ctx: commands.Context, error):
    # 1) Игнорируем ошибки, которые уже обработаны внутри команд
    if isinstance(error, commands.CommandNotFound):
        # Список всех зарегистрированных команд
        all_names = [cmd.name for cmd in bot.commands] + \
                    [alias for cmd in bot.commands for alias in cmd.aliases]

        entered = ctx.invoked_with            # то, что пользователь ввёл
        matches = get_close_matches(entered, all_names, n=1, cutoff=0.6)

        if matches:
            hint = f"Может, вы имели в виду `!{matches[0]}`?"
        else:
            hint = "Такой команды не существует. Используйте `!помощь` для списка."

        try:
            await ctx.author.send(hint)
        except discord.Forbidden:
            pass
        return

    # 2) Все остальные ошибки логируем как error
    await log_action(ctx.channel, ctx.author,
                     f"Ошибка бота: {error}",
                     level="error")

import asyncio
import signal
import sys

async def shutdown():
    if bot.is_closed():
        return
    try:
        await log_action(None, bot.user,
                         f"Флер завершила свою работу ({datetime.now(timezone.utc):%d.%m.%Y %H:%M:%S} UTC)",
                         level="error")
        # Даём шанс отправить embed
        await asyncio.sleep(1)
    except Exception:
        pass
    finally:
        await bot.close()

def handle_signal(signum, frame):
    asyncio.create_task(shutdown())

# регистрируем обработчики Ctrl+C / SIGTERM
signal.signal(signal.SIGINT,  handle_signal)
signal.signal(signal.SIGTERM, handle_signal)

bot.run('')