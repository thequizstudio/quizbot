import discord
import asyncio
import json
import random
from discord.ext import commands

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Load questions from JSON
with open("questions.json", "r") as f:
    questions = json.load(f)

current_question = None
answered_users = set()
scores = {}
quiz_running = False
quiz_channel_id = YOUR_CHANNEL_ID_HERE  # Replace with your channel ID

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}")
    channel = bot.get_channel(quiz_channel_id)
    await channel.send("📢 Quiz bot is ready! Starting the first round...")
    await start_quiz()

async def start_quiz():
    global current_question, answered_users, scores, quiz_running

    quiz_running = True
    answered_users.clear()
    scores.clear()

    channel = bot.get_channel(quiz_channel_id)
    used_questions = []

    for i in range(10):  # 10-question round
        question = random.choice([q for q in questions if q not in used_questions])
        used_questions.append(question)
        current_question = question
        answered_users.clear()

        await channel.send(f"❓ Question {i + 1}: {question['question']}")

        try:
            await asyncio.wait_for(wait_for_answers(channel, question), timeout=10.0)
        except asyncio.TimeoutError:
            await channel.send(f"⏰ Time's up! The correct answer was: **{question['answer']}**")

        await asyncio.sleep(6)  # wait before next question

    # End of the quiz
    await channel.send("🎉 The round is over! Final scores:")
    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    leaderboard = "\n".join(
        [f"{idx + 1}. <@{user_id}> - {score} pts" for idx, (user_id, score) in enumerate(sorted_scores)]
    )
    await channel.send(leaderboard)

    quiz_running = False
    # No auto-restart here

async def wait_for_answers(channel, question):
    def check(m):
        return (
            m.channel.id == channel.id
            and m.author != bot.user
            and m.author.id not in answered_users
        )

    correct_answer = question["answer"].strip().lower()
    answered_correctly = False

    while True:
        message = await bot.wait_for("message", check=check)

        user_answer = message.content.strip().lower()
        user_id = message.author.id

        if not user_id in scores:
            scores[user_id] = 0

        if user_answer == correct_answer:
            if not answered_correctly:
                scores[user_id] += 15  # 10 + 5 bonus for fastest
                await channel.send(f"✅ {message.author.mention} got it right first! (+15 pts)")
                answered_correctly = True
            else:
                scores[user_id] += 10
                await channel.send(f"✅ {message.author.mention} also got it right! (+10 pts)")

            await channel.send(f"🏅 Your total: {scores[user_id]} pts")
            answered_users.add(user_id)
        else:
            answered_users.add(user_id)

        # Stop if someone answered correctly
        if answered_correctly:
            break

bot.run("YOUR_BOT_TOKEN_HERE")
