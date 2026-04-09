# discord.py

## Bot Setup

Use `commands.Bot` with explicit intents. Never use `discord.Client` directly unless you need zero command handling:

```python
import discord
from discord.ext import commands

intents = discord.Intents.default()
intents.message_content = True  # Required for prefix commands
intents.members = True          # Required for member events — privileged, enable in portal

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

bot.run("TOKEN")  # Load from env, never hardcode
```

Only request privileged intents (`message_content`, `members`, `presences`) you actually use. Discord requires justification for these during verification.

## Commands

### Slash Commands (preferred)

Use `app_commands` for slash commands. Sync the command tree on ready or via a sync command — don't sync on every startup in production:

```python
from discord import app_commands

@bot.tree.command(name="ping", description="Check latency")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"Pong! {round(bot.latency * 1000)}ms")

# Sync once after changes, not on every on_ready
@bot.command()
@commands.is_owner()
async def sync(ctx):
    synced = await bot.tree.sync()
    await ctx.send(f"Synced {len(synced)} commands")
```

### Hybrid Commands

Support both prefix and slash with `@bot.hybrid_command()`:

```python
@bot.hybrid_command(name="greet", description="Greet someone")
async def greet(ctx, member: discord.Member):
    await ctx.send(f"Hello, {member.mention}!")
```

### Prefix Commands

```python
@bot.command()
async def info(ctx, user: discord.Member = None):
    user = user or ctx.author
    await ctx.send(f"{user.display_name} joined {user.joined_at:%Y-%m-%d}")
```

## Cogs (Extensions)

Cogs organize related commands, events, and state. Always use cogs for anything beyond a trivial bot:

```python
# cogs/moderation.py
from discord.ext import commands

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(description="Kick a member")
    @commands.has_permissions(kick_members=True)
    async def kick(self, ctx, member: discord.Member, *, reason: str = None):
        await member.kick(reason=reason)
        await ctx.send(f"Kicked {member.display_name}")

    @commands.Cog.listener()
    async def on_member_join(self, member):
        channel = member.guild.system_channel
        if channel:
            await channel.send(f"Welcome, {member.mention}!")

async def setup(bot):
    await bot.add_cog(Moderation(bot))
```

Load cogs at startup:

```python
# bot.py
import os

async def load_extensions(bot):
    for filename in os.listdir("./cogs"):
        if filename.endswith(".py"):
            await bot.load_extension(f"cogs.{filename[:-3]}")

@bot.event
async def on_ready():
    await load_extensions(bot)
```

## Views, Buttons, and Selects

Use `discord.ui.View` for interactive components. Always set a timeout:

```python
class ConfirmView(discord.ui.View):
    def __init__(self, author_id: int):
        super().__init__(timeout=60.0)
        self.author_id = author_id
        self.confirmed = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("Not for you.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.confirmed = True
        self.stop()
        await interaction.response.edit_message(content="Confirmed.", view=None)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.confirmed = False
        self.stop()
        await interaction.response.edit_message(content="Cancelled.", view=None)

    async def on_timeout(self):
        self.confirmed = False
        self.stop()
```

### Select Menus

```python
class RoleSelect(discord.ui.View):
    @discord.ui.select(
        placeholder="Pick a role...",
        options=[
            discord.SelectOption(label="Red", value="red"),
            discord.SelectOption(label="Blue", value="blue"),
        ],
    )
    async def select_role(self, interaction: discord.Interaction, select: discord.ui.Select):
        await interaction.response.send_message(f"You picked: {select.values[0]}", ephemeral=True)
```

## Embeds

```python
embed = discord.Embed(
    title="Server Info",
    description=f"Members: {ctx.guild.member_count}",
    color=discord.Color.blurple(),
)
embed.set_thumbnail(url=ctx.guild.icon.url if ctx.guild.icon else None)
embed.add_field(name="Created", value=f"{ctx.guild.created_at:%Y-%m-%d}", inline=True)
embed.set_footer(text=f"Requested by {ctx.author}")
await ctx.send(embed=embed)
```

## Error Handling

Handle errors at command level and globally. Always respond to the user — silent failures are confusing:

```python
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("You don't have permission to do that.")
    elif isinstance(error, commands.MemberNotFound):
        await ctx.send("Member not found.")
    elif isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f"Try again in {error.retry_after:.0f}s.")
    else:
        await ctx.send("Something went wrong.")
        raise error  # Re-raise unexpected errors for logging

# Per-command error handler
@kick.error
async def kick_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("You need kick permissions.")
```

For app commands, use the tree error handler:

```python
@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message("No permission.", ephemeral=True)
    else:
        await interaction.response.send_message("Something went wrong.", ephemeral=True)
        raise error
```

## Common Gotchas

- **Forgetting to enable intents** — `message_content` is privileged. Without it, `on_message` receives empty content. Enable in both code AND the Developer Portal.
- **Syncing slash commands on every startup** — `tree.sync()` is rate-limited. Sync manually via an owner-only command, not in `on_ready`.
- **Not checking `message.author == bot.user`** — Without this guard in `on_message`, the bot replies to itself in an infinite loop.
- **Blocking the event loop** — `time.sleep()`, synchronous HTTP, or CPU-heavy work blocks all events. Use `asyncio.sleep()`, `aiohttp`, and `bot.loop.run_in_executor()` for blocking calls.
- **Ephemeral state in Views** — Views don't survive bot restarts. For persistent interactions (ticket systems, polls), store state in a database and reconstruct views on startup.
- **Responding to interactions twice** — An interaction can only be responded to once. Use `interaction.response.send_message()` first, then `interaction.followup.send()` for additional messages.

## Best Practices

- **Use cogs from the start.** Even small bots grow. One cog per feature domain.
- **Load tokens from environment variables.** Never commit tokens. Use `os.environ["DISCORD_TOKEN"]` or a `.env` file with `python-dotenv`.
- **Use `aiohttp` for HTTP calls**, not `requests`. The bot runs an async event loop — synchronous I/O blocks everything.
- **Set command cooldowns** with `@commands.cooldown(rate, per, type)` to prevent abuse.
- **Use `ephemeral=True`** for error messages and sensitive responses so only the invoker sees them.
- **Prefer slash commands over prefix commands.** They have built-in argument validation, autocomplete, and discoverability.
- **Don't shard until 1,000+ guilds.** Premature sharding wastes resources and adds complexity.
- **Use `discord.utils.get()` and `discord.utils.find()`** over manual iteration for lookups.
- **Log with Python's `logging` module**, not `print()`. discord.py uses the `discord` logger — configure it at startup.
