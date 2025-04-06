from dotenv import load_dotenv
import os
import discord
from discord.ext import commands
import json
import random
from rapidfuzz import fuzz

CHANNEL_ID = 1358391826716950622  # Replace with your actual channel ID

def load_questions():
    with open("questions.json", "r") as f:
        return json.load(f)

questions = load_questions()
current_question = None
current_answer = None
players = {}
joined_players = set()
game_active = False

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"Quiz bot is online as {bot.user}!")

@bot.command()
async def joinquiz(ctx):
    if ctx.channel.id != CHANNEL_ID:
        return
    joined_players.add(ctx.author.id)
    await ctx.send(f"{ctx.author.name} has joined the quiz!")

@bot.command()
async def leavequiz(ctx):
    if ctx.channel.id != CHANNEL_ID:
        return
    joined_players.discard(ctx.author.id)
    await ctx.send(f"{ctx.author.name} has left the quiz.")

@bot.command()
async def startquiz(ctx):
    global game_active, current_question, current_answer
    if ctx.channel.id != CHANNEL_ID:
        return

    if game_active:
        await ctx.send("A quiz is already running!")
        return

    if not joined_players:
        await ctx.send("No players have joined yet! Use `!joinquiz` to join.")
        return

    game_active = True
    players.clear()

    q = random.choice(questions)
    current_question = q["question"]
    current_answer = q["answer"].lower()

    await ctx.send(f"🧠 Quiz started! First question:\n**{current_question}**")

@bot.event
async def on_message(message):
    global current_question, current_answer

    # Don't let the bot respond to its own messages
    if message.author == bot.user:
        return

    # Ignore messages from outside the quiz channel or when the game is inactive
    if message.channel.id != CHANNEL_ID or not game_active:
        return

    # Check if the user is in the quiz
    if message.author.id not in joined_players:
        return

    # Check if the message matches the current question answer
    if current_question and fuzz.ratio(message.content.lower().strip(), current_answer) >= 85:
        player = message.author.name
        players[player] = players.get(player, 0) + 1
        await message.channel.send(f"✅ Correct, {player}! 🎉")

        # Get the next question
        q = random.choice(questions)
        current_question = q["question"]
        current_answer = q["answer"].lower()
        await message.channel.send(f"Next question:\n**{current_question}**")

    else:
        await message.channel.send(f"❌ Not quite right, {message.author.name}!")

    await bot.process_commands(message)

@bot.command()
async def leaderboard(ctx):
    if ctx.channel.id != CHANNEL_ID:
        return

    if not players:
        await ctx.send("No scores yet.")
        return

    sorted_scores = sorted(players.items(), key=lambda x: x[1], reverse=True)
    leaderboard_text = "\n".join([f"{name}: {score}" for name, score in sorted_scores])
    await ctx.send(f"🏆 Leaderboard:\n{leaderboard_text}")

@bot.command()
async def endquiz(ctx):
    global game_active
    if ctx.channel.id != CHANNEL_ID:
        return

    if not game_active:
        await ctx.send("No quiz is running.")
        return

    game_active = False
    await ctx.send("🛑 Quiz ended. Thanks for playing!")

# Run your bot
load_dotenv()
bot.run(os.getenv("DISCORD_TOKEN"))
