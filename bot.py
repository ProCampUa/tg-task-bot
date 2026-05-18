import os
import logging
import asyncio
import httpx
import json
import re
from datetime import date, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler
from database import init_db, add_task, complete_task, get_tasks
from scheduler import setup_scheduler
from calendar_sync import add_event

TOKEN = os.environ.get("TOKEN", "")
CLAUDE_KEY = os.environ.get("CLAUDE_KEY", "")

logging.basicConfig(level=logging.INFO)

async def ask_claude(text, sender, chat_id):
    today = date.today().isoformat()
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    tasks = get_tasks(chat_id)
    tasks_str = ""
    for t in tasks:
        status = "vykonano" if t[6] == "vypolneno" else "prostrocheno" if (t[5] and t[5] < today) else "v roboti"
        tasks_str += "#" + str(t[0]) + " " + str(t[2]) + " -> " + str(t[3] or "-") + " deadline:" + str(t[5] or "-") + " [" + status + "]\n"

    prompt = (
        "Potochni zavdannya grupy:\n" + (tasks_str or "nemae zavdan") + "\n\n"
        "Povidomlennya vid " + sender + ": \"" + text + "\"\n"
        "Sogodni: " + today + ", zavtra: " + tomorrow + "\n\n"
        "Vidpovid TILKY odnym iz tsikh JSON formativ:\n"
        "1. Yaksho ye zavdannya: {\"type\":\"task\",\"title\":\"shcho zrobyty\",\"assignee\":\"komu\",\"deadline\":\"YYYY-MM-DD\",\"time\":\"HH:MM abo null\"}\n"
        "2. Yaksho dodaty v kalendar: {\"type\":\"calendar\",\"title\":\"nazva\",\"assignee\":\"komu\",\"deadline\":\"YYYY-MM-DD\",\"time\":\"HH:MM\",\"time_end\":\"HH:MM abo null\"}\n"
        "3. Yaksho pytannya pro zavdannya: {\"type\":\"question\",\"answer\":\"vidpovid ukrainskoyu\"}\n"
        "4. Inше: {\"type\":\"none\"}\n"
        "TILKY JSON, bez poyasnen!"
    )
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={"x-api-key": CLAUDE_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                json={"model": "claude-haiku-4-5-20251001", "max_tokens": 300, "messages": [{"role": "user", "content": prompt}]},
                timeout=15
            )
            data = r.json()
            text_resp = data["content"][0]["text"].strip()
            m = re.search(r'\{.*\}', text_resp, re.DOTALL)
            if m:
                return json.loads(m.group())
            return {"type": "none"}
    except Exception as e:
        print("Claude error:", e)
        return {"type": "none"}

def build_task_keyboard(task_id):
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Виконано", callback_data="done_" + str(task_id))
    ]])

async def send_tasks_list(chat_id, bot_or_update, is_bot=False):
    tasks = get_tasks(chat_id)
    today = date.today().isoformat()
    active = [t for t in tasks if t[6] != "vypolneno"]
    if not active:
        text = "Активних завдань немає! 🎉"
        if is_bot:
            await bot_or_update.send_message(chat_id=chat_id, text=text)
        else:
            await bot_or_update.message.reply_text(text)
        return
    from collections import defaultdict
    grouped = defaultdict(list)
    for t in active:
        assignee = t[3] or "Без відповідального"
        grouped[assignee].append(t)

    for assignee, atasks in grouped.items():
        lines = ["👤 <b>" + assignee + "</b>", ""]
        buttons = []
        for t in atasks:
            status = "🔴" if (t[5] and t[5] < today) else "🔵"
            deadline = t[5] or "—"
            lines.append(status + " " + t[2])
            lines.append("    📅 " + deadline)
            lines.append("")
            buttons.append([InlineKeyboardButton("✅ " + t[2][:30], callback_data="done_" + str(t[0]))])

        full_text = "\n".join(lines).strip()
        keyboard = InlineKeyboardMarkup(buttons)

        if is_bot:
            await bot_or_update.send_message(chat_id=chat_id, text=full_text, parse_mode="HTML", reply_markup=keyboard)
        else:
            await bot_or_update.message.reply_text(full_text, parse_mode="HTML", reply_markup=keyboard)

async def button_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    if data.startswith("done_"):
        task_id = int(data.replace("done_", ""))
        user = query.from_user.first_name or ""
        tasks = get_tasks(query.message.chat.id)
        task = next((t for t in tasks if t[0] == task_id), None)
        task_title = task[2] if task else "Завдання #" + str(task_id)
        await query.answer()
        ok = complete_task(task_id, query.message.chat.id)
        if ok:
            await query.edit_message_text(
                "✅ <b>Виконано!</b> — " + user + "\n" + query.message.text,
                parse_mode="HTML"
            )
            await ctx.bot.send_message(
                chat_id=query.message.chat.id,
                text="✅ <b>" + task_title + "</b> виконав <b>" + user + "</b>!",
                parse_mode="HTML"
            )

async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    text = update.message.text

    if not text.startswith("!"):
        return

    text = text[1:].strip()

    sender = update.effective_user.first_name or "Unknown"
    chat_id = update.effective_chat.id
    print("Перевірка:", text)
    result = await ask_claude(text, sender, chat_id)
    print("Результат:", result)

    if result.get("type") == "task":
        task_id = add_task(
            chat_id=chat_id,
            title=result.get("title", text),
            assignee=result.get("assignee", "-"),
            assignee_id=None,
            deadline=result.get("deadline", "")
        )
        time_str = result.get("time", "")
        time_part = " о " + time_str if time_str and time_str != "null" else ""
        keyboard = build_task_keyboard(task_id)
        await update.message.reply_text(
            "<b>Завдання створено!</b>\n"
            + "📌 " + str(result.get("title","")) + "\n"
            + "👤 Відповідальний: " + str(result.get("assignee","")) + "\n"
            + "<b>Дедлайн: " + str(result.get("deadline","")) + time_part + "</b>",
            parse_mode="HTML",
            reply_markup=keyboard
        )
    elif result.get("type") == "calendar":
        cal_link = add_event(
            result.get("title",""),
            result.get("assignee", sender),
            result.get("deadline",""),
            result.get("time",""),
            result.get("time_end", None)
        )
        if cal_link:
            time_end_str = result.get("time_end","")
            time_range = str(result.get("time",""))
            if time_end_str and time_end_str != "null":
                time_range += " - " + time_end_str
            await update.message.reply_text(
                "📅 <b>Додано в календар!</b>\n"
                + "📌 " + str(result.get("title","")) + "\n"
                + "<b>Дата: " + str(result.get("deadline","")) + " о " + time_range + "</b>\n"
                + "<a href='" + cal_link + "'>Відкрити в Google Calendar</a>",
                parse_mode="HTML"
            )
        else:
            await update.message.reply_text("Помилка додавання в календар")
    elif result.get("type") == "question":
        await update.message.reply_text(result.get("answer", ""))

async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await send_tasks_list(update.effective_chat.id, update)

async def cmd_done(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Вкажи ID: /done 5")
        return
    try:
        task_id = int(ctx.args[0])
    except ValueError:
        await update.message.reply_text("ID має бути числом")
        return
    ok = complete_task(task_id, update.effective_chat.id)
    await update.message.reply_text("Завдання виконано!" if ok else "Завдання не знайдено")

async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "<b>Task Manager Bot</b>\n\n"
        "Додавай ! перед повідомленням:\n\n"
        "<b>! Serhii зробити звіт до п'ятниці</b>\n"
        "<b>! Додай в календар зустріч сьогодні о 15:00-16:00</b>\n\n"
        "/status — всі активні завдання\n"
        "/done ID — відмітити виконаним\n"
        "/help — допомога",
        parse_mode="HTML"
    )

async def main():
    init_db()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("done", cmd_done))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("start", cmd_help))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    async with app:
        loop = asyncio.get_event_loop()
        setup_scheduler(app.bot, loop, send_tasks_list)
        print("Бот запущено!")
        await app.start()
        await app.updater.start_polling()
        await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
