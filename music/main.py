import discord
from discord.ext import commands
import asyncio, random, json, os
from dotenv import load_dotenv
from rapidfuzz import fuzz
import aiohttp

load_dotenv()

TOKEN = os.getenv("MUSIC_DISCORD_TOKEN")
MUSIC_TEXT_CHANNEL = int(os.getenv("MUSIC_TEXT_CHANNEL"))
MUSIC_VOICE_CHANNEL = int(os.getenv("MUSIC_VOICE_CHANNEL"))

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

scores = {}
current_song = None
answer_found = False
fastest_answered = False

def load_songs():
    with open("songs.json", "r", encoding="utf-8") as f:
        return json.load(f)

async def play_snippet(vc, url):
    FFMPEG_OPTIONS = {
        "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
        "options": "-vn"
    }
    vc.play(discord.FFmpegPCMAudio(url, **FFMPEG_OPTIONS))

@bot.event
async def on_ready():
    print(f"{bot.user} is live as the Music Trivia Bot 🎵")
    await start_music_round()

async def start_music_round():
    channel = bot.get_channel(MUSIC_TEXT_CHANNEL)
    vc_channel = bot.get_channel(MUSIC_VOICE_CHANNEL)
    songs = load_songs()
    random.shuffle(songs)

    if not vc_channel:
        await channel.send("❌ Voice channel not found.")
        return

    vc = await vc_channel.connect()
    await channel.send("🎶 **Welcome to Music Trivia!** Guess the song title as fast as you can!")

    for i, song in enumerate(songs[:10], 1):
        global current_song, answer_found, fastest_answered
        current_song, answer_found, fastest_answered = song, False, False

        await channel.send(f"▶️ **Song {i}/10** — listen carefully!")
        await play_snippet(vc, song["preview_url"])
        await asyncio.sleep(10)
        vc.stop()

        if not answer_found:
            await channel.send(f"⏰ Time's up! The answer was **{song['title']}** by *{song['artist']}*.")
        await asyncio.sleep(6)

    await vc.disconnect()
    await show_leaderboard(channel)
    await channel.send("🎵 Round complete! Type `!music` to start another game.")

@bot.event
async def on_message(message):
    global answer_found, fastest_answered
    if message.author.bot or message.channel.id != MUSIC_TEXT_CHANNEL:
        return

    if current_song and not answer_found:
        guess = message.content.lower()
        correct = current_song["answer"].lower()
        ratio = fuzz.partial_ratio(guess, correct)
        if ratio >= 80:
            answer_found = True
            user = message.author

            if not fastest_answered:
                fastest_answered = True
                scores[user] = scores.get(user, 0) + 15
                await message.channel.send(f"⚡ {user.mention} got it first! **{current_song['title']}** (+15 pts)")
            else:
                scores[user] = scores.get(user, 0) + 10
                await message.channel.send(f"✅ {user.mention} got it! **{current_song['title']}** (+10 pts)")
    await bot.process_commands(message)

async def show_leaderboard(channel):
    if not scores:
        await channel.send("No correct answers this round.")
        return

    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    leaderboard = "\n".join(
        [f"**{i+1}. {user.display_name}** — {points} pts" for i, (user, points) in enumerate(sorted_scores)]
    )
    await channel.send(f"🏆 **Final Leaderboard:**\n{leaderboard}")

@bot.command(name="music")
async def manual_start(ctx):
    await ctx.send("🎧 Starting a new music trivia round!")
    await start_music_round()

bot.run(TOKEN)
