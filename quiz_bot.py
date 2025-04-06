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
joined_players = set()  # Keep track of players in the game
game_active = False
current_round_questions = []
current_question_index = 0
answered_correctly = False

intents = discord.Intents.default()
intents.message_content = True
intents.members = True  # Intents to allow member updates
bot = commands.Bot(command_prefix="!", intents=intents)

time_limit = 10  # Time limit in seconds for answering each question.
question_start_time = None  # To track when the question was asked.

@bot.event
async def on_ready():
    print(f"Quiz bot is online as {bot.user}!")
    
    # Start a quiz in the first available text channel of each server
    for guild in bot.guilds:
        for channel in guild.text_channels:
            if channel.permissions_for(guild.me).send_messages:  # Check if bot can send messages
                await start_game(channel)  # Start the game automatically in this channel
                break  # Remove this if you want to start in every text channel of the server

# Start the game in the given channel
async def start_game(channel):
    global game_active
    if game_active:
        return

    # Automatically enroll all members present in the channel
    for member in channel.members:
        if not member.bot:  # Ignore bot members
            joined_players.add(member.id)  # Auto-enroll

    game_active = True
    players.clear()  # Reset scores for a new game
    current_question_index = 0
    current_round_questions = random.sample(questions, 10)

    await channel.send("🧠 Quiz started! 10 questions coming up for all members!")
    await ask_next_question(channel)

async def ask_next_question(channel):
    global current_question, current_answer, current_question_index, answered_correctly, game_active, question_start_time

    if current_question_index >= 10:
        game_active = False
        await channel.send("🎉 Round over!")
        await show_leaderboard(channel)

        # Start a new game after 30 seconds
        await asyncio.sleep(30)  # Wait for 30 seconds
        await channel.send("⏳ Starting a new game soon!")
        
        await start_game(channel)  # Start a new game in the same channel
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

async def show_leaderboard(channel):
    if not players:
        await channel.send("No scores yet.")
        return

    sorted_scores = sorted(players.items(), key=lambda x: x[1], reverse=True)
    leaderboard_text = "\n".join([f"{name}: {score}" for name, score in sorted_scores])
    await channel.send(f"🏆 Final Leaderboard:\n{leaderboard_text}")

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