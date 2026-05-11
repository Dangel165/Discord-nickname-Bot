import logging
import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv


load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("club-role-bot")


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "club_role_bot.db"

TOKEN = os.getenv("DISCORD_TOKEN", "").strip()
WELCOME_TITLE = os.getenv("WELCOME_TITLE", "입장 안내")
WELCOME_MESSAGE = os.getenv(
    "WELCOME_MESSAGE",
    "본인 소속 버튼을 누른 뒤 이름만 입력해주세요.",
)

intents = discord.Intents.default()
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)
PERSISTENT_VIEW_ADDED = False


class ClubRoleNotManageable(Exception):
    pass


@dataclass(slots=True)
class GuildSettings:
    guild_id: int
    welcome_channel_id: int | None = None
    join_role_id: int | None = None


@dataclass(frozen=True, slots=True)
class ClubOption:
    key: str
    region: str
    university: str
    club: str


HONAM_CLUBS: tuple[ClubOption, ...] = (
    ClubOption("mokpo", "호남", "국립목포대학교", "SecuMaster"),
    ClubOption("dongshin", "호남", "동신대학교", "HawkIS"),
    ClubOption("woosuk", "호남", "우석대학교", "APS"),
    ClubOption("chosun", "호남", "조선대학교", "HackerLogin"),
)


def connect_db() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH)


def init_db() -> None:
    with connect_db() as con:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS guild_settings (
                guild_id INTEGER PRIMARY KEY,
                welcome_channel_id INTEGER,
                join_role_id INTEGER
            )
            """
        )
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS club_role_settings (
                guild_id INTEGER NOT NULL,
                club_key TEXT NOT NULL,
                role_id INTEGER NOT NULL,
                PRIMARY KEY (guild_id, club_key, role_id)
            )
            """
        )
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS club_role_remove_settings (
                guild_id INTEGER NOT NULL,
                club_key TEXT NOT NULL,
                role_id INTEGER NOT NULL,
                PRIMARY KEY (guild_id, club_key, role_id)
            )
            """
        )
        info = con.execute("PRAGMA table_info(club_role_settings)").fetchall()
        primary_key_columns = {row[1] for row in info if row[5] > 0}
        if primary_key_columns == {"guild_id", "club_key"}:
            con.execute("ALTER TABLE club_role_settings RENAME TO club_role_settings_old")
            con.execute(
                """
                CREATE TABLE club_role_settings (
                    guild_id INTEGER NOT NULL,
                    club_key TEXT NOT NULL,
                    role_id INTEGER NOT NULL,
                    PRIMARY KEY (guild_id, club_key, role_id)
                )
                """
            )
            con.execute(
                """
                INSERT OR IGNORE INTO club_role_settings (guild_id, club_key, role_id)
                SELECT guild_id, club_key, role_id
                FROM club_role_settings_old
                """
            )
            con.execute("DROP TABLE club_role_settings_old")


def get_settings(guild_id: int) -> GuildSettings:
    with connect_db() as con:
        row = con.execute(
            """
            SELECT guild_id, welcome_channel_id, join_role_id
            FROM guild_settings
            WHERE guild_id = ?
            """,
            (guild_id,),
        ).fetchone()

    if row is None:
        return GuildSettings(guild_id=guild_id)
    return GuildSettings(
        guild_id=row[0],
        welcome_channel_id=row[1],
        join_role_id=row[2],
    )


def update_settings(
    guild_id: int,
    *,
    welcome_channel_id: int | None = None,
    join_role_id: int | None = None,
) -> GuildSettings:
    current = get_settings(guild_id)
    next_channel_id = current.welcome_channel_id if welcome_channel_id is None else welcome_channel_id
    next_role_id = current.join_role_id if join_role_id is None else join_role_id

    with connect_db() as con:
        con.execute(
            """
            INSERT INTO guild_settings (guild_id, welcome_channel_id, join_role_id)
            VALUES (?, ?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET
                welcome_channel_id = excluded.welcome_channel_id,
                join_role_id = excluded.join_role_id
            """,
            (guild_id, next_channel_id, next_role_id),
        )

    return GuildSettings(
        guild_id=guild_id,
        welcome_channel_id=next_channel_id,
        join_role_id=next_role_id,
    )


def get_club_option(club_key: str) -> ClubOption | None:
    for option in HONAM_CLUBS:
        if option.key == club_key:
            return option
    return None


def get_club_role_ids(guild_id: int, club_key: str) -> list[int]:
    with connect_db() as con:
        rows = con.execute(
            """
            SELECT role_id
            FROM club_role_settings
            WHERE guild_id = ? AND club_key = ?
            ORDER BY role_id
            """,
            (guild_id, club_key),
        ).fetchall()

    return [row[0] for row in rows]


def add_club_role_id(guild_id: int, club_key: str, role_id: int) -> None:
    with connect_db() as con:
        con.execute(
            """
            INSERT INTO club_role_settings (guild_id, club_key, role_id)
            VALUES (?, ?, ?)
            ON CONFLICT(guild_id, club_key, role_id) DO NOTHING
            """,
            (guild_id, club_key, role_id),
        )


def clear_club_role_ids(guild_id: int, club_key: str) -> None:
    with connect_db() as con:
        con.execute(
            """
            DELETE FROM club_role_settings
            WHERE guild_id = ? AND club_key = ?
            """,
            (guild_id, club_key),
        )


def get_club_remove_role_ids(guild_id: int, club_key: str) -> list[int]:
    with connect_db() as con:
        rows = con.execute(
            """
            SELECT role_id
            FROM club_role_remove_settings
            WHERE guild_id = ? AND club_key = ?
            ORDER BY role_id
            """,
            (guild_id, club_key),
        ).fetchall()

    return [row[0] for row in rows]


def add_club_remove_role_id(guild_id: int, club_key: str, role_id: int) -> None:
    with connect_db() as con:
        con.execute(
            """
            INSERT INTO club_role_remove_settings (guild_id, club_key, role_id)
            VALUES (?, ?, ?)
            ON CONFLICT(guild_id, club_key, role_id) DO NOTHING
            """,
            (guild_id, club_key, role_id),
        )


def clear_club_remove_role_ids(guild_id: int, club_key: str) -> None:
    with connect_db() as con:
        con.execute(
            """
            DELETE FROM club_role_remove_settings
            WHERE guild_id = ? AND club_key = ?
            """,
            (guild_id, club_key),
        )


def clean_nickname_part(value: str, label: str) -> str:
    cleaned = " ".join(value.strip().split())
    if not cleaned:
        raise ValueError(f"{label}을(를) 입력해주세요.")
    if "/" in cleaned or "(" in cleaned or ")" in cleaned:
        raise ValueError(f"{label}에는 '/', '(', ')' 문자를 사용할 수 없어요.")
    return cleaned


def build_nickname(club: str, name: str) -> str:
    nickname = f"{club}/{name}"
    if len(nickname) > 32:
        raise ValueError("서버별명이 너무 길어요. 동아리명과 이름을 조금 짧게 입력해주세요.")
    return nickname


def can_manage_role(guild: discord.Guild, role: discord.Role) -> bool:
    me = guild.me
    if me is None:
        return False
    return not role.managed and role != guild.default_role and role < me.top_role


async def set_member_nickname(
    member: discord.Member,
    club: str,
    name: str,
) -> str:
    club = clean_nickname_part(club, "동아리명")
    name = clean_nickname_part(name, "이름")
    nickname = build_nickname(club, name)
    await member.edit(nick=nickname, reason="Club nickname setup")
    return nickname


async def grant_club_roles(member: discord.Member, club_key: str) -> list[discord.Role]:
    role_ids = get_club_role_ids(member.guild.id, club_key)
    if not role_ids:
        return []

    roles = []
    for role_id in role_ids:
        role = member.guild.get_role(role_id)
        if role is None:
            continue

        if not can_manage_role(member.guild, role):
            raise ClubRoleNotManageable

        roles.append(role)

    if not roles:
        return []

    await member.add_roles(*roles, reason="Club button roles")
    return roles


async def remove_club_roles(member: discord.Member, club_key: str) -> list[discord.Role]:
    role_ids = get_club_remove_role_ids(member.guild.id, club_key)
    if not role_ids:
        return []

    roles = []
    for role_id in role_ids:
        role = member.guild.get_role(role_id)
        if role is None or role not in member.roles:
            continue

        if not can_manage_role(member.guild, role):
            raise ClubRoleNotManageable

        roles.append(role)

    if not roles:
        return []

    await member.remove_roles(*roles, reason="Club button role removal")
    return roles


class NicknameModal(discord.ui.Modal):
    def __init__(
        self,
        *,
        club: str | None = None,
        university: str | None = None,
        club_key: str | None = None,
    ) -> None:
        super().__init__(title="서버별명 설정")
        self.selected_club = club
        self.selected_university = university
        self.selected_club_key = club_key

        self.club_input: discord.ui.TextInput | None = None
        if club is None:
            self.club_input = discord.ui.TextInput(
                label="동아리명",
                placeholder="예: SecuMaster",
                max_length=20,
            )
            self.add_item(self.club_input)

        self.name_input = discord.ui.TextInput(
            label="이름",
            placeholder="예: 홍길동",
            max_length=20,
        )
        self.add_item(self.name_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("서버 안에서만 사용할 수 있어요.", ephemeral=True)
            return

        club = self.selected_club
        if club is None and self.club_input is not None:
            club = str(self.club_input.value)

        try:
            nickname = await set_member_nickname(
                interaction.user,
                str(club),
                str(self.name_input.value),
            )
            removed_roles = []
            granted_roles = []
            if self.selected_club_key is not None:
                removed_roles = await remove_club_roles(interaction.user, self.selected_club_key)
                granted_roles = await grant_club_roles(interaction.user, self.selected_club_key)
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return
        except discord.Forbidden:
            await interaction.response.send_message("서버별명 변경 권한이 부족해요.", ephemeral=True)
            return
        except ClubRoleNotManageable:
            await interaction.response.send_message(
                "서버별명은 변경했지만, 이 동아리 역할은 봇이 지급할 수 없어요. 관리자에게 봇 역할 위치를 확인해달라고 해주세요.",
                ephemeral=True,
            )
            return
        except discord.HTTPException:
            await interaction.response.send_message("서버별명을 변경하는 중 Discord 오류가 발생했어요.", ephemeral=True)
            return

        if self.selected_university is None:
            await interaction.response.send_message(f"서버별명을 `{nickname}`(으)로 설정했어요.", ephemeral=True)
            return

        role_text = ""
        if granted_roles:
            role_text = "\n지급 역할: " + ", ".join(role.mention for role in granted_roles)
        remove_text = ""
        if removed_roles:
            remove_text = "\n삭제 역할: " + ", ".join(role.mention for role in removed_roles)
        await interaction.response.send_message(
            f"`{self.selected_university} / {self.selected_club}` 선택 완료. 서버별명을 `{nickname}`(으)로 설정했어요.{role_text}{remove_text}",
            ephemeral=True,
        )


class HonamClubView(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=None)
        for option in HONAM_CLUBS:
            button = discord.ui.Button(
                label=f"{option.university} / {option.club}",
                style=discord.ButtonStyle.primary,
                custom_id=f"club_role_bot:honam:{option.key}",
            )
            button.callback = self.make_callback(option)
            self.add_item(button)

    def make_callback(self, option: ClubOption):
        async def callback(interaction: discord.Interaction) -> None:
            await interaction.response.send_modal(
                NicknameModal(club=option.club, university=option.university, club_key=option.key)
            )

        return callback


async def club_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:
    current_folded = current.casefold()
    choices = []
    for option in HONAM_CLUBS:
        label = f"{option.university} / {option.club}"
        if current_folded in label.casefold() or current_folded in option.club.casefold():
            choices.append(app_commands.Choice(name=label, value=option.key))
    return choices[:25]


async def send_welcome_prompt(guild: discord.Guild) -> bool:
    settings = get_settings(guild.id)
    if settings.welcome_channel_id is None:
        return False

    channel = guild.get_channel(settings.welcome_channel_id)
    if not isinstance(channel, discord.abc.Messageable):
        return False

    embed = discord.Embed(
        title=WELCOME_TITLE,
        description=(
            f"{WELCOME_MESSAGE}\n\n"
            "버튼을 누르면 이름 입력창이 열립니다."
        ),
        color=discord.Color.blurple(),
    )
    embed.set_footer(text="이름만 입력하면 서버별명과 역할이 자동으로 설정됩니다.")

    try:
        await channel.send(embed=embed, view=HonamClubView())
        return True
    except discord.Forbidden:
        logger.warning("Missing permission to send welcome prompt in guild %s", guild.id)
    except discord.HTTPException:
        logger.exception("Failed to send welcome prompt in guild %s", guild.id)
    return False


async def grant_join_role(member: discord.Member) -> None:
    settings = get_settings(member.guild.id)
    if settings.join_role_id is None:
        return

    role = member.guild.get_role(settings.join_role_id)
    if role is None:
        return

    if not can_manage_role(member.guild, role):
        logger.warning("Join role %s is not manageable in guild %s", role.id, member.guild.id)
        return

    try:
        await member.add_roles(role, reason="Automatic join role")
    except discord.Forbidden:
        logger.warning("Missing permission to grant join role in guild %s", member.guild.id)
    except discord.HTTPException:
        logger.exception("Failed to grant join role in guild %s", member.guild.id)


@bot.event
async def on_ready() -> None:
    global PERSISTENT_VIEW_ADDED

    init_db()
    if not PERSISTENT_VIEW_ADDED:
        bot.add_view(HonamClubView())
        PERSISTENT_VIEW_ADDED = True

    logger.info("Logged in as %s (%s)", bot.user, bot.user.id if bot.user else "unknown")

    if bot.application_id is not None:
        await bot.http.bulk_upsert_global_commands(bot.application_id, payload=[])
        logger.info("Cleared global slash commands")

    for guild in bot.guilds:
        bot.tree.copy_global_to(guild=guild)
        await bot.tree.sync(guild=guild)
        logger.info("Synced slash commands to guild %s", guild.id)


@bot.event
async def on_guild_join(guild: discord.Guild) -> None:
    bot.tree.copy_global_to(guild=guild)
    await bot.tree.sync(guild=guild)
    logger.info("Synced slash commands to new guild %s", guild.id)


@bot.event
async def on_member_join(member: discord.Member) -> None:
    await grant_join_role(member)


@bot.tree.command(name="별명설정", description="서버별명을 (동아리명/이름) 형식으로 변경합니다.")
@app_commands.describe(
    동아리명="서버별명에 표시할 동아리명",
    이름="서버별명에 표시할 이름",
)
async def nickname_setup(
    interaction: discord.Interaction,
    동아리명: str,
    이름: str,
) -> None:
    if interaction.guild is None or not isinstance(interaction.user, discord.Member):
        await interaction.response.send_message("서버 안에서만 사용할 수 있는 명령어예요.", ephemeral=True)
        return

    try:
        nickname = await set_member_nickname(interaction.user, 동아리명, 이름)
    except ValueError as exc:
        await interaction.response.send_message(str(exc), ephemeral=True)
        return
    except discord.Forbidden:
        await interaction.response.send_message("서버별명 변경 권한이 부족해요.", ephemeral=True)
        return
    except discord.HTTPException:
        await interaction.response.send_message("서버별명을 변경하는 중 Discord 오류가 발생했어요.", ephemeral=True)
        return

    await interaction.response.send_message(f"서버별명을 `{nickname}`(으)로 설정했어요.", ephemeral=True)


@bot.tree.command(name="입장채널설정", description="새 멤버 입장 안내 메시지를 보낼 채널을 설정합니다.")
@app_commands.describe(channel="입장 안내 메시지를 보낼 채널")
@app_commands.checks.has_permissions(manage_guild=True)
async def set_welcome_channel(
    interaction: discord.Interaction,
    channel: discord.TextChannel,
) -> None:
    if interaction.guild is None:
        await interaction.response.send_message("서버 안에서만 사용할 수 있는 명령어예요.", ephemeral=True)
        return

    update_settings(interaction.guild.id, welcome_channel_id=channel.id)
    await interaction.response.send_message(f"입장 안내 채널을 {channel.mention}(으)로 설정했어요.", ephemeral=True)


@bot.tree.command(name="입장메시지보내기", description="설정된 입장 채널에 고정용 대학/동아리 선택 버튼 메시지를 보냅니다.")
@app_commands.checks.has_permissions(manage_guild=True)
async def send_welcome_message(interaction: discord.Interaction) -> None:
    if interaction.guild is None:
        await interaction.response.send_message("서버 안에서만 사용할 수 있는 명령어예요.", ephemeral=True)
        return

    sent = await send_welcome_prompt(interaction.guild)
    if not sent:
        await interaction.response.send_message(
            "입장 메시지를 보내지 못했어요. `/입장채널설정`을 먼저 하거나 봇의 채널 보기/메시지 보내기 권한을 확인해주세요.",
            ephemeral=True,
        )
        return

    await interaction.response.send_message("입장 안내 버튼 메시지를 보냈어요. 필요하면 그 메시지를 채널에 고정해주세요.", ephemeral=True)


@bot.tree.command(name="입장역할설정", description="새 멤버에게 자동 지급할 역할을 설정합니다.")
@app_commands.describe(role="새 멤버에게 자동 지급할 역할")
@app_commands.checks.has_permissions(manage_guild=True)
async def set_join_role(
    interaction: discord.Interaction,
    role: discord.Role,
) -> None:
    if interaction.guild is None:
        await interaction.response.send_message("서버 안에서만 사용할 수 있는 명령어예요.", ephemeral=True)
        return

    if not can_manage_role(interaction.guild, role):
        await interaction.response.send_message(
            "그 역할은 봇이 지급할 수 없어요. 봇 역할을 해당 역할보다 위로 올리고 관리형 역할이 아닌지 확인해주세요.",
            ephemeral=True,
        )
        return

    update_settings(interaction.guild.id, join_role_id=role.id)
    await interaction.response.send_message(f"입장 자동 역할을 {role.mention}(으)로 설정했어요.", ephemeral=True)


@bot.tree.command(name="동아리역할설정", description="호남지역 대학/동아리 버튼의 역할을 초기화하고 새 역할 1개로 설정합니다.")
@app_commands.describe(
    동아리="역할을 연결할 호남지역 대학/동아리",
    role="해당 버튼을 누른 멤버에게 지급할 역할",
)
@app_commands.autocomplete(동아리=club_autocomplete)
@app_commands.checks.has_permissions(manage_guild=True)
async def set_club_role(
    interaction: discord.Interaction,
    동아리: str,
    role: discord.Role,
) -> None:
    if interaction.guild is None:
        await interaction.response.send_message("서버 안에서만 사용할 수 있는 명령어예요.", ephemeral=True)
        return

    option = get_club_option(동아리)
    if option is None:
        await interaction.response.send_message("알 수 없는 동아리예요. 자동완성 목록에서 선택해주세요.", ephemeral=True)
        return

    if not can_manage_role(interaction.guild, role):
        await interaction.response.send_message(
            "그 역할은 봇이 지급할 수 없어요. 봇 역할을 해당 역할보다 위로 올리고 관리형 역할이 아닌지 확인해주세요.",
            ephemeral=True,
        )
        return

    clear_club_role_ids(interaction.guild.id, option.key)
    add_club_role_id(interaction.guild.id, option.key, role.id)
    await interaction.response.send_message(
        f"`{option.university} / {option.club}` 버튼 역할을 {role.mention} 하나로 설정했어요.",
        ephemeral=True,
    )


@bot.tree.command(name="동아리역할추가", description="호남지역 대학/동아리 버튼에 지급할 역할을 추가합니다.")
@app_commands.describe(
    동아리="역할을 추가할 호남지역 대학/동아리",
    role="해당 버튼을 누른 멤버에게 추가 지급할 역할",
)
@app_commands.autocomplete(동아리=club_autocomplete)
@app_commands.checks.has_permissions(manage_guild=True)
async def add_club_role(
    interaction: discord.Interaction,
    동아리: str,
    role: discord.Role,
) -> None:
    if interaction.guild is None:
        await interaction.response.send_message("서버 안에서만 사용할 수 있는 명령어예요.", ephemeral=True)
        return

    option = get_club_option(동아리)
    if option is None:
        await interaction.response.send_message("알 수 없는 동아리예요. 자동완성 목록에서 선택해주세요.", ephemeral=True)
        return

    if not can_manage_role(interaction.guild, role):
        await interaction.response.send_message(
            "그 역할은 봇이 지급할 수 없어요. 봇 역할을 해당 역할보다 위로 올리고 관리형 역할이 아닌지 확인해주세요.",
            ephemeral=True,
        )
        return

    add_club_role_id(interaction.guild.id, option.key, role.id)
    role_ids = get_club_role_ids(interaction.guild.id, option.key)
    roles = [interaction.guild.get_role(role_id) for role_id in role_ids]
    role_text = ", ".join(role.mention for role in roles if role is not None)
    await interaction.response.send_message(
        f"`{option.university} / {option.club}` 버튼 역할에 {role.mention}을(를) 추가했어요.\n현재 지급 역할: {role_text}",
        ephemeral=True,
    )


@bot.tree.command(name="동아리역할삭제설정", description="호남지역 대학/동아리 버튼에서 제거할 역할을 초기화하고 새 역할 1개로 설정합니다.")
@app_commands.describe(
    동아리="역할 제거를 연결할 호남지역 대학/동아리",
    role="해당 버튼을 누른 멤버에게서 제거할 역할",
)
@app_commands.autocomplete(동아리=club_autocomplete)
@app_commands.checks.has_permissions(manage_guild=True)
async def set_club_remove_role(
    interaction: discord.Interaction,
    동아리: str,
    role: discord.Role,
) -> None:
    if interaction.guild is None:
        await interaction.response.send_message("서버 안에서만 사용할 수 있는 명령어예요.", ephemeral=True)
        return

    option = get_club_option(동아리)
    if option is None:
        await interaction.response.send_message("알 수 없는 동아리예요. 자동완성 목록에서 선택해주세요.", ephemeral=True)
        return

    if not can_manage_role(interaction.guild, role):
        await interaction.response.send_message(
            "그 역할은 봇이 제거할 수 없어요. 봇 역할을 해당 역할보다 위로 올리고 관리형 역할이 아닌지 확인해주세요.",
            ephemeral=True,
        )
        return

    clear_club_remove_role_ids(interaction.guild.id, option.key)
    add_club_remove_role_id(interaction.guild.id, option.key, role.id)
    await interaction.response.send_message(
        f"`{option.university} / {option.club}` 버튼 삭제 역할을 {role.mention} 하나로 설정했어요.",
        ephemeral=True,
    )


@bot.tree.command(name="동아리역할삭제추가", description="호남지역 대학/동아리 버튼에서 제거할 역할을 추가합니다.")
@app_commands.describe(
    동아리="역할 제거를 추가할 호남지역 대학/동아리",
    role="해당 버튼을 누른 멤버에게서 추가로 제거할 역할",
)
@app_commands.autocomplete(동아리=club_autocomplete)
@app_commands.checks.has_permissions(manage_guild=True)
async def add_club_remove_role(
    interaction: discord.Interaction,
    동아리: str,
    role: discord.Role,
) -> None:
    if interaction.guild is None:
        await interaction.response.send_message("서버 안에서만 사용할 수 있는 명령어예요.", ephemeral=True)
        return

    option = get_club_option(동아리)
    if option is None:
        await interaction.response.send_message("알 수 없는 동아리예요. 자동완성 목록에서 선택해주세요.", ephemeral=True)
        return

    if not can_manage_role(interaction.guild, role):
        await interaction.response.send_message(
            "그 역할은 봇이 제거할 수 없어요. 봇 역할을 해당 역할보다 위로 올리고 관리형 역할이 아닌지 확인해주세요.",
            ephemeral=True,
        )
        return

    add_club_remove_role_id(interaction.guild.id, option.key, role.id)
    role_ids = get_club_remove_role_ids(interaction.guild.id, option.key)
    roles = [interaction.guild.get_role(role_id) for role_id in role_ids]
    role_text = ", ".join(role.mention for role in roles if role is not None)
    await interaction.response.send_message(
        f"`{option.university} / {option.club}` 버튼 삭제 역할에 {role.mention}을(를) 추가했어요.\n현재 삭제 역할: {role_text}",
        ephemeral=True,
    )


@bot.tree.command(name="설정확인", description="현재 입장 채널과 입장 자동 역할 설정을 확인합니다.")
@app_commands.checks.has_permissions(manage_guild=True)
async def show_config(interaction: discord.Interaction) -> None:
    if interaction.guild is None:
        await interaction.response.send_message("서버 안에서만 사용할 수 있는 명령어예요.", ephemeral=True)
        return

    settings = get_settings(interaction.guild.id)
    channel_text = "미설정"
    role_text = "미설정"

    if settings.welcome_channel_id is not None:
        channel = interaction.guild.get_channel(settings.welcome_channel_id)
        channel_text = channel.mention if isinstance(channel, discord.TextChannel) else "삭제되었거나 찾을 수 없음"

    if settings.join_role_id is not None:
        role = interaction.guild.get_role(settings.join_role_id)
        role_text = role.mention if role is not None else "삭제되었거나 찾을 수 없음"

    club_role_lines = []
    club_remove_role_lines = []
    for option in HONAM_CLUBS:
        club_role_ids = get_club_role_ids(interaction.guild.id, option.key)
        if not club_role_ids:
            club_role_text = "미설정"
        else:
            club_roles = [interaction.guild.get_role(role_id) for role_id in club_role_ids]
            mentions = [role.mention for role in club_roles if role is not None]
            missing_count = len(club_role_ids) - len(mentions)
            if missing_count:
                mentions.append(f"삭제되었거나 찾을 수 없음 {missing_count}개")
            club_role_text = ", ".join(mentions)
        club_role_lines.append(f"- {option.university} / {option.club}: {club_role_text}")

        club_remove_role_ids = get_club_remove_role_ids(interaction.guild.id, option.key)
        if not club_remove_role_ids:
            club_remove_role_text = "미설정"
        else:
            club_remove_roles = [interaction.guild.get_role(role_id) for role_id in club_remove_role_ids]
            remove_mentions = [role.mention for role in club_remove_roles if role is not None]
            missing_remove_count = len(club_remove_role_ids) - len(remove_mentions)
            if missing_remove_count:
                remove_mentions.append(f"삭제되었거나 찾을 수 없음 {missing_remove_count}개")
            club_remove_role_text = ", ".join(remove_mentions)
        club_remove_role_lines.append(f"- {option.university} / {option.club}: {club_remove_role_text}")

    await interaction.response.send_message(
        "입장 안내 채널: "
        f"{channel_text}\n입장 자동 역할: {role_text}\n\n"
        "동아리 버튼 역할:\n"
        + "\n".join(club_role_lines)
        + "\n\n동아리 버튼 삭제 역할:\n"
        + "\n".join(club_remove_role_lines),
        ephemeral=True,
    )


@set_welcome_channel.error
@send_welcome_message.error
@set_join_role.error
@set_club_role.error
@add_club_role.error
@set_club_remove_role.error
@add_club_remove_role.error
@show_config.error
async def admin_command_error(
    interaction: discord.Interaction,
    error: app_commands.AppCommandError,
) -> None:
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message("서버 관리 권한이 있는 사람만 사용할 수 있어요.", ephemeral=True)
        return
    raise error


if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN is missing. Create .env from .env.example first.")

bot.run(TOKEN)
