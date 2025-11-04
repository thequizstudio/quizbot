from dotenv import load_dotenv
import os
import discord
from discord.ext import commands
import json
import random
import asyncio
from rapidfuzz import fuzz

LEADERBOARD_FILE = "leaderboard.json"

def load_questions():
    with open("questions.json", "r") as f:
        data = json.load(f)
        print(f"Loaded {len(data)} questions.")
        return data

questions = load_questions()

current_question = None
current_answer = None  # fix: no .title() here
players = {}  # current round scores
game_active = False
current_round_questions = []
current_question_index = 0
answered_correctly = []  # list of (player, points)
answered_this_round = set()
quiz_channel_id = None
NUMBER_OF_QUESTIONS_PER_ROUND = 3
DELAY_BETWEEN_ROUNDS = 30
accepting_answers = False

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

async def send_boxed_message(channel, message):
    boxed = f"```{message}```"
    await channel.send(boxed)

def load_leaderboard():
    if os.path.exists(LEADERBOARD_FILE):
        try:
            with open(LEADERBOARD_FILE, "r") as f:
                data = json.load(f)
                if not isinstance(data, dict):
                    print("Leaderboard file malformed, resetting.")
                    return {}
                return data
        except Exception as e:
            print(f"Error reading leaderboard file: {e}")
            return {}
    return {}

def save_leaderboard(data):
    try:
        with open(LEADERBOARD_FILE, "w") as f:
            json.dump(data, f, indent=2)
        print("Leaderboard saved successfully.")
    except Exception as e:
        print(f"Error saving leaderboard: {e}")

leaderboard_data = load_leaderboard()

@bot.event
async def on_ready():
    print(f"Bot connected as {bot.user}!")
    global quiz_channel_id
    while not bot.guilds:
        print("Waiting for guilds...")
        await asyncio.sleep(1)
    guild = bot.guilds[0]
    print(f"Connected to guild: {guild.name} ({guild.id})")

    for channel in guild.text_channels:
        perms = channel.permissions_for(guild.me)
        print(f"Checking channel: {channel.name} ({channel.id}), send_messages={perms.send_messages}, read_messages={perms.read_messages}")
        if perms.send_messages and perms.read_messages:
            quiz_channel_id = channel.id
            print(f"Quiz will run in channel: {channel.name}")
            await start_new_round(guild)
            return
    print("No suitable channel found to run the quiz.")

async def start_new_round(guild):
    global game_active, players, answered_this_round, current_question_index, current_round_questions, accepting_answers, answered_correctly

    if game_active:
        print("Quiz already running; ignoring new round request.")
        return

    print("Starting new round...")
    game_active = True
    players.clear()
    answered_this_round.clear()
    current_question_index = 0
    current_round_questions = random.sample(questions, min(NUMBER_OF_QUESTIONS_PER_ROUND, len(questions)))
    accepting_answers = False
    answered_correctly = []

    for member in guild.members:
        if not member.bot:
            players[member.display_name] = 0

    channel = bot.get_channel(quiz_channel_id)
    if channel:
        await send_boxed_message(channel, f"🎉 New quiz round starting! {len(current_round_questions)} questions ahead!")
        await ask_next_question(channel)
    else:
        print("Quiz channel not found!")
        game_active = False

async def ask_next_question(channel):
    global current_question, current_answer, current_question_index, answered_correctly, game_active, answered_this_round, accepting_answers

    if not game_active:
        return

    if current_question_index >= len(current_round_questions):
        game_active = False

        # Determine top scorer(s)
        if players:
            max_score = max(players.values())
            winners = [player for player, score in players.items() if score == max_score]
            winners_text = ", ".join(winners)
            await send_boxed_message(channel, f"🏁 Round over! And the winner is {winners_text}!")
        else:
            await send_boxed_message(channel, "🏁 Round over! No winners this round.")

        print("Round over, showing leaderboard...")
        await show_leaderboard(channel, round_over=True)
        await send_boxed_message(channel, f"Next round starting in {DELAY_BETWEEN_ROUNDS} seconds... Get ready!")
        await asyncio.sleep(DELAY_BETWEEN_ROUNDS)

        for guild in bot.guilds:
            if guild.get_channel(channel.id):
                await start_new_round(guild)
                return
        await send_boxed_message(channel, "⚠️ Could not find guild for quiz channel to start next round.")
        return

    q = current_round_questions[current_question_index]
    current_question = q["question"]
    current_answer = q["answer"].lower()  # Store answer lowercase for matching
    answered_correctly = []
    answered_this_round = set()
    accepting_answers = True

    current_question_index += 1

    perms = channel.permissions_for(channel.guild.me)
    print(f"Permissions in #{channel.name}: send_messages={perms.send_messages}, view_channel={perms.view_channel}")

    await send_boxed_message(channel, f"❓ Question {current_question_index}:\n**{current_question}**")

    try:
        await asyncio.sleep(10)
        accepting_answers = False

        if not answered_correctly:
            await send_boxed_message(channel, f"⏰ Time's up! No one answered correctly. The answer was: **{current_answer.title()}**")
        else:
            lines = []
            for i, (player, pts) in enumerate(answered_correctly, start=1):
                lines.append(f"{i}. {player} (+{pts} points)")
            winners_text = "\n".join(lines)
            await send_boxed_message(
                channel,
                f"⏰ Time's up! The correct answer was: **{current_answer.title()}**\n\n"
                f"🏅 Correct answers in order:\n{winners_text}"
            )

        await asyncio.sleep(7)
        if game_active:
            await ask_next_question(channel)
    except Exception as e:
        print(f"Error during question timing: {e}")

async def show_leaderboard(channel, round_over=False):
    global leaderboard_data

    if round_over:
        try:
            for player, score in players.items():
                leaderboard_data[player] = leaderboard_data.get(player, 0) + score
            save_leaderboard(leaderboard_data)
        except Exception as e:
            print(f"Error updating leaderboard: {e}")

    if not leaderboard_data:
        await send_boxed_message(channel, "Nobody scored anything so far! 💀")
        return

    sorted_scores = sorted(leaderboard_data.items(), key=lambda x: x[1], reverse=True)
    lines = [f"**{i+1}. {name}** ({score} points)" for i, (name, score) in enumerate(sorted_scores)]

    title = "🏆 **Daily Leaderboard ** 🏆" if round_over else "🏆 **Daily Leaderboard**"
    await send_boxed_message(channel, f"{title}\n" + "\n".join(lines))

@bot.command()
async def leaderboard(ctx):
    await show_leaderboard(ctx.channel)

@bot.command()
async def endquiz(ctx):
    global game_active
    if not game_active:
        await send_boxed_message(ctx, "No quiz is running.")
        return
    game_active = False
    await send_boxed_message(ctx, "🛑 Quiz ended.")

@bot.event
async def on_message(message):
    global current_question, current_answer, answered_correctly, game_active, answered_this_round, accepting_answers

    await bot.process_commands(message)

    if (
        message.author.bot
        or not game_active
        or not current_question
        or message.channel.id != quiz_channel_id
        or not accepting_answers
    ):
        return

    user_answer = message.content.strip()
    match_score = fuzz.ratio(user_answer.lower(), current_answer)

    if (
        match_score >= 85
        and message.author.id not in answered_this_round
        and len(answered_correctly) < 3
    ):
        answered_this_round.add(message.author.id)
        player = message.author.display_name
        points_awarded = [15, 10, 5][len(answered_correctly)]
        players[player] = players.get(player, 0) + points_awarded
        answered_correctly.append((player, points_awarded))
        # No immediate message; results shown after time is up
        return

    if game_active and message.author.display_name not in players and not message.author.bot:
        players[message.author.display_name] = players.get(message.author.display_name, 0)

load_dotenv()
bot.run(os.getenv("DISCORD_TOKEN"))
