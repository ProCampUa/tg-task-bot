from apscheduler.schedulers.background import BackgroundScheduler
from database import get_all_chats, get_tasks_due_tomorrow, get_tasks
from datetime import date, timedelta
import asyncio

async def send_reminders(bot, send_tasks_fn):
    for chat_id in get_all_chats():
        tasks = get_tasks(chat_id)
        today = date.today().isoformat()
        active = [t for t in tasks if t[6] != "vypolneno"]
        if not active:
            continue
        # Нагадування з тегом відповідального
        for t in active:
            assignee = t[3] or ""
            tag = "@" + assignee.replace("@","") if assignee else ""
            if t[5] and t[5] < today:
                msg = "🔴 <b>Прострочено!</b> " + tag + "\nЗавдання: <b>" + t[2] + "</b>\nДедлайн був: " + t[5]
            elif t[5] == today:
                msg = "⚠️ <b>Сьогодні дедлайн!</b> " + tag + "\nЗавдання: <b>" + t[2] + "</b>"
            elif t[5] == (date.today() + timedelta(days=1)).isoformat():
                msg = "⏰ <b>Завтра дедлайн!</b> " + tag + "\nЗавдання: <b>" + t[2] + "</b>"
            else:
                continue
            try:
                await bot.send_message(chat_id=chat_id, text=msg, parse_mode="HTML")
            except Exception as e:
                print("Помилка:", e)
        # Список всіх активних завдань
        await send_tasks_fn(chat_id, bot, is_bot=True)

def setup_scheduler(bot, loop, send_tasks_fn):
    scheduler = BackgroundScheduler(timezone="Europe/Kiev")

    # О 09:00
    scheduler.add_job(
        lambda: asyncio.run_coroutine_threadsafe(send_reminders(bot, send_tasks_fn), loop),
        "cron", hour=9, minute=0
    )
    # О 19:00
    scheduler.add_job(
        lambda: asyncio.run_coroutine_threadsafe(send_reminders(bot, send_tasks_fn), loop),
        "cron", hour=19, minute=0
    )

    scheduler.start()
    return scheduler
