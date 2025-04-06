from dotenv import load_dotenv
import os
import discord
from discord.ext import commands
import json
import random
import asyncio
from rapidfuzz import fuzz
import time  # Import time for tracking response time

# Load questions from JSON
def load_questions():
    with open("questions.json", "r") as f:
        data = json.load(f)
        print(f"Loaded {len(data)} questions.")
        return data

questions = load_questions()
current_question = None
current_answer = None
players = {}
joined_players = set()
game_active = False
current_round_questions = []
current_question_index = 0
answered_correctly = False

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

time_limit = 10  # Time limit in seconds for answering each question.
question_start_time = None  # To track when the question was asked.

@bot.event
async def on_ready():
    print(f"Quiz bot is online as {bot.user}!")

@bot.command()
async def joinquiz(ctx):
    joined_players.add(ctx.author.id)
    await ctx.send(f"{ctx.author.name} has joined the quiz!")

@bot.command()
async def leavequiz(ctx):
    joined_players.discard(ctx.author.id)
    await ctx.send(f"{ctx.author.name} has left the quiz.")

@bot.command()
async def startquiz(ctx):
    global game_active, current_question, current_answer, current_round_questions, current_question_index

    if game_active:
        await ctx.send("A quiz is already running!")
        return

    if not joined_players:
        await ctx.send("No players have joined yet! Use !joinquiz to join.")
        return

    game_active = True
    players.clear()
    current_question_index = 0
    current_round_questions = random.sample(questions, 10)

    await ctx.send("🧠 Quiz started! 10 questions coming up!")
    await ask_next_question(ctx.channel)

async def ask_next_question(channel):
    global current_question, current_answer, current_question_index, answered_correctly, game_active, question_start_time

    if current_question_index >= 10:
        game_active = False
        await channel.send("🎉 Round over!")
        await show_leaderboard(channel)
        
        # Start a new game after 30 seconds
        await asyncio.sleep(30)  # Wait for 30 seconds before starting a new game
        await channel.send("⏳ Starting a new game soon! Join using `!joinquiz`.")
        await startquiz(channel)  # Start a new game in the same channel
        return

    q = current_round_questions[current_question_index]
    current_question = q["question"]
    current_answer = q["answer"].lower()
    answered_correctly = False

    current_question_index += 1
    
    # Track the time when the question is asked
    question_start_time = time.time()
    await channel.send(f"❓ Question {current_question_index}:\n**{current_question}**")

    await asyncio.sleep(time_limit)  # Wait for answers
    if not answered_correctly:
        await channel.send(f"⏰ Time's up! The correct answer was: **{current_answer}**")
    await asyncio.sleep(8)  # Wait before the next question
    await ask_next_question(channel)

@bot.command()
async def leaderboard(ctx):
    await show_leaderboard(ctx.channel)

async def show_leaderboard(channel):
    if not players:
        await channel.send("No scores yet.")
        return

    sorted_scores = sorted(players.items(), key=lambda x: x[1], reverse=True)
    leaderboard_text = "\n".join([f"{name}: {score}" for name, score in sorted_scores])
    await channel.send(f"🏆 Final Leaderboard:\n{leaderboard_text}")

@bot.command()
async def endquiz(ctx):
    global game_active
    if not game_active:
        await ctx.send("No quiz is running.")
        return

    game_active = False
    await ctx.send("🛑 Quiz ended. Starting a new round in 30 seconds...")

    # Start a countdown before the next game
    await asyncio.sleep(30)  # Wait for 30 seconds
    await ctx.send("⏳ Starting a new game soon! Join using `!joinquiz`.")
    await startquiz(ctx)  # Automatically start a new game

@bot.event
async def on_message(message):
    global current_question, current_answer, answered_correctly, question_start_time

    await bot.process_commands(message)

    if message.author.bot or not game_active or not current_question:
        return

    if message.author.id not in joined_players:
        return

    user_answer = message.content.strip()
    match_score = fuzz.ratio(user_answer.lower(), current_answer)

    if match_score >= 85 and not answered_correctly:
        answered_correctly = True
        player = message.author.name

        # Calculate the time taken to answer
        time_taken = time.time() - question_start_time  # Get the time since the question was asked
        time_taken = min(time_taken, time_limit)  # Ensure max time taken does not exceed the limit

        # Determine points based on time taken
        points = max(0, 15 - int(time_taken))  # Subtract points based on time taken, down to 0 points
        players[player] = players.get(player, 0) + points  # Update player score

        await message.channel.send(
            f"⚡ Fastest Finger! ✅ Correct, {player}! +{points} points 🎉 (Total: {players[player]} points)"
        )

# Start the bot
load_dotenv()
bot.run(os.getenv("DISCORD_TOKEN"))