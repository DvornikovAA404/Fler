# bot.py
import discord
from discord.ext import commands
from datetime import datetime, timezone
import re
from difflib import get_close_matches
from typing import List
from discord import app_commands
from discord.utils import get
import re
from typing import Optional


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
# ---------- служебные парсеры ----------
def parse_location_line(text: str) -> tuple[str, list[str]] | None:
    """Возвращает (комната, [выходы]) или None если формат неверный."""
    if ':' not in text:
        return None
    room, exits_str = text.split(':', 1)
    exits = [e.strip() for e in exits_str.split(',') if e.strip()]
    return room.strip(), exits

# ---------- автокомплит ----------
async def room_autocomplete(interaction: discord.Interaction, current: str):
    channel = bot.get_channel(ROOMS_SOURCE_CHANNEL_ID)
    if not channel or not isinstance(interaction.channel, discord.TextChannel):
        return []

    # определяем текущую комнату по названию канала
    current_room = interaction.channel.name
    exits = []

    async for msg in channel.history(limit=None):
        parsed = parse_location_line(msg.content)
        if parsed and parsed[0].lower() == current_room.lower():
            exits = [e for e in parsed[1] if current.lower() in e.lower()]
            break

    return [app_commands.Choice(name=e, value=e) for e in exits][:25]

async def log_action(channel: discord.TextChannel | None,
                     author: discord.Member | discord.User,
                     description: str,
                     extra: str = "",
                     level: str = "success",
                     send_dm: bool = True):
    color_map = {"success": 0x1e8e3e, "warn": 0xff7800, "error": 0x990000}

    compact = (
        f"{description} |"
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

import re
from typing import Optional

URL_REGEX = re.compile(
    r"https?://(?:discord|discordapp)\.com/channels/(?P<guild>\d+)/(?P<channel>\d+)/(?P<message>\d+)"
)

def parse_msg_link(url: str) -> Optional[tuple[int, int, int]]:
    """Возвращает (guild_id, channel_id, message_id) или None."""
    match = URL_REGEX.match(url)
    if not match:
        return None
    return int(match.group("guild")), int(match.group("channel")), int(match.group("message"))

@bot.command(name="очиститьпосле")
@commands.has_permissions(manage_messages=True)
async def очиститьпосле(ctx: commands.Context, url: str, count: int):
    """!очиститьпосле <ссылка> <N> – удалить последние N сообщений, заканчивая указанным (включительно)."""
    try:
        if not has_allowed_role(ctx.author):
            await log_action(ctx.channel, ctx.author, "Недостаточно прав", level="warn")
            return
        await ctx.message.delete()

        parsed = parse_msg_link(url)
        if not parsed or parsed[0] != ctx.guild.id or parsed[1] != ctx.channel.id:
            await log_action(ctx.channel, ctx.author, "Ссылка некорректна", level="warn")
            return

        target_msg = await ctx.channel.fetch_message(parsed[2])

        # собираем последние N сообщений, заканчивая target_msg
        msgs_to_delete = []
        async for msg in ctx.channel.history(limit=None, oldest_first=False):
            if msg.id == target_msg.id:
                msgs_to_delete.append(msg)
                break
            msgs_to_delete.append(msg)
            if len(msgs_to_delete) >= count:
                break

        # если нашли меньше N – берём ровно то количество
        msgs_to_delete = msgs_to_delete[:count]

        for msg in msgs_to_delete:
            await msg.delete()

        await log_action(ctx.channel, ctx.author,
                         f"удалено {len(msgs_to_delete)} (до {target_msg.jump_url})",
                         level="success")
    except commands.BadArgument:
        await log_action(ctx.channel, ctx.author,
                         "Синтаксис: !очиститьпосле <ссылка> <целое-число>", level="warn")
    except Exception as e:
        await log_action(ctx.channel, ctx.author, f"ошибка: {e}", level="error")

# ---------- !очиститьдо ----------
@bot.command(name="очиститьдо")
@commands.has_permissions(manage_messages=True)
async def очиститьдо(ctx: commands.Context, url: str, count: int):
    """!очиститьдо <ссылка> <N> – удалить ровно N сообщений, начиная с указанного (включительно) и ранее."""
    try:
        if not has_allowed_role(ctx.author):
            await log_action(ctx.channel, ctx.author, "Недостаточно прав", level="warn")
            return
        await ctx.message.delete()

        parsed = parse_msg_link(url)
        if not parsed or parsed[0] != ctx.guild.id or parsed[1] != ctx.channel.id:
            await log_action(ctx.channel, ctx.author, "Ссылка некорректна", level="warn")
            return

        target_msg = await ctx.channel.fetch_message(parsed[2])
        before_dt = target_msg.created_at

        msgs_to_delete = []
        async for msg in ctx.channel.history(limit=None, before=before_dt, oldest_first=False):
            if len(msgs_to_delete) >= count - 1:
                break
            msgs_to_delete.append(msg)
        msgs_to_delete.append(target_msg)

        msgs_to_delete = msgs_to_delete[:count]

        for msg in msgs_to_delete:
            await msg.delete()

        await log_action(ctx.channel, ctx.author,
                         f"удалено {len(msgs_to_delete)} до {target_msg.jump_url}",
                         level="success")
    except commands.BadArgument:
        await log_action(ctx.channel, ctx.author,
                         "Синтаксис: !очиститьдо <ссылка> <целое-число>", level="warn")
    except Exception as e:
        await log_action(ctx.channel, ctx.author, f"ошибка: {e}", level="error")

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

# ---------- slash-команда ----------
@bot.tree.command(name="move", description="Переместиться в другую комнату")
@app_commands.describe(exit="Куда вы хотите пойти")
@app_commands.autocomplete(exit=room_autocomplete)
async def move(interaction: discord.Interaction, exit: str):
    member = interaction.user
    guild = interaction.guild
    source_channel = interaction.channel

    # 1. проверка категории начального канала
    if not isinstance(source_channel, discord.TextChannel) or \
       source_channel.category_id != ALLOWED_CATEGORY_ID:
        await log_action(None, member,
                         f"{member.display_name} /move вне категории",
                         extra="", level="warn", send_dm=False)
        return await interaction.response.send_message(
            "Команду можно использовать только в разрешённой категории.", ephemeral=True
        )

    current_room = source_channel.name

    # 2. парсим список выходов из текущей комнаты
    list_ch = bot.get_channel(ROOMS_SOURCE_CHANNEL_ID)
    allowed_exits = []
    async for msg in list_ch.history(limit=None):
        parsed = parse_location_line(msg.content)
        if parsed and parsed[0].lower() == current_room.lower():
            allowed_exits = parsed[1]
            break

    # 3. проверка, что целевая комната есть в списке выходов
    if exit not in allowed_exits:
        await log_action(source_channel, member,
                         f"{member.display_name} выхода нет: {exit}",
                         extra="", level="warn", send_dm=False)
        return await interaction.response.send_message(
            f"Из **{current_room}** нет выхода в **{exit}**.", ephemeral=True
        )

    # 4. проверка существования целевого канала
    target_channel = discord.utils.get(guild.text_channels,
                                       name=exit,
                                       category_id=ALLOWED_CATEGORY_ID)
    if not target_channel:
        await log_action(source_channel, member,
                         f"{member.display_name} канал не найден: {exit}",
                         extra="", level="warn", send_dm=False)
        return await interaction.response.send_message(
            f"Канал **{exit}** не существует или вне категории.", ephemeral=True
        )

    # 5. перемещение
    try:
        # открываем целевой
        await target_channel.set_permissions(member, read_messages=True, send_messages=True)

        # сообщение в целевой канал
        await target_channel.send(f"*Пришёл {member.mention}*")

        # сообщение в текущий канал
        await interaction.response.send_message(
            f"{member.display_name} ушёл в {target_channel.mention}"
        )
        move_msg = await interaction.original_response()

        # закрываем исходный
        await source_channel.set_permissions(member, read_messages=False, send_messages=False)

        # логируем
        await log_action(
            None,
            member,
            f"{member.display_name}",
            extra=f"{source_channel.mention} → {target_channel.mention} | [**ССЫЛКА**]({move_msg.jump_url})",
            level="success",
            send_dm=False
        )
    except discord.Forbidden:
        await log_action(source_channel, member,
                         f"{member.display_name} недостаточно прав",
                         extra="", level="error", send_dm=False)
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