import os
import requests
import gspread
import vk_api
import pytz
from flask import Flask
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from google.oauth2.service_account import Credentials

# ================= НАСТРОЙКИ =================
VK_TOKEN = os.getenv("vk1.a.8sOIhI8ydfOvaKFRPL9BYvu1A_oGwr1lJ9e-ioX3_8JgFmwnYJEdY2bmZATPGKo7_NWiYRaX2iCXICZbrIlfyOVTZrnFcDk4PruqPVMJFmE_oDyCzJPtOxrGmBIj4nV3bIpN1T_diMpCIDTnlUE7TzmBnLNAySEH2hY-EqEvEJkATyrR0bCLBkfE9kQADXX3sBo3nDiE4y5CXZoachBzig")
CHAT_ID = int(os.getenv("242"))
SPREADSHEET_NAME = os.getenv("Криминальная сфера")
TIMEZONE = pytz.timezone("Europe/Moscow")
# =============================================

# Flask (чтобы Render не засыпал)
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running"

# Google авторизация
scope = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]
creds = Credentials.from_service_account_file("credentials.json", scopes=scope)
gc = gspread.authorize(creds)
sheet = gc.open(SPREADSHEET_NAME).sheet1

# VK авторизация
vk_session = vk_api.VkApi(token=VK_TOKEN)
vk = vk_session.get_api()

last_row = 1

# ================= ЗАГРУЗКА ФАЙЛА В VK =================

def upload_file_to_vk(file_url):
    response = requests.get(file_url)
    file_name = "report_file"

    upload_server = vk.docs.getMessagesUploadServer(type="doc", peer_id=2000000000 + CHAT_ID)
    upload_url = upload_server["upload_url"]

    upload_response = requests.post(
        upload_url,
        files={"file": (file_name, response.content)}
    ).json()

    save = vk.docs.save(file=upload_response["file"])
    doc = save["doc"]

    return f"doc{doc['owner_id']}_{doc['id']}"

# ================= ОТПРАВКА ОТЧЕТА =================

def check_new_reports():
    global last_row
    rows = sheet.get_all_values()

    while last_row < len(rows):
        row = rows[last_row]

        nickname = row[1]
        type_mp = row[2]
        date = row[3]
        time = row[4]
        comment = row[5]
        file_link = row[6]

        attachment = upload_file_to_vk(file_link)

        message = f"""📋 Новый отчет!

Никнейм: {nickname}
Тип: {type_mp}
Время: {time}
Дата: {date}
Комментарий: {comment}
"""

        vk.messages.send(
            chat_id=CHAT_ID,
            message=message,
            attachment=attachment,
            random_id=0
        )

        last_row += 1

# ================= ДНЕВНАЯ СТАТИСТИКА =================

def daily_stats():
    today = datetime.now(TIMEZONE).strftime("%d.%m.%Y")
    rows = sheet.get_all_values()[1:]

    stats = {}

    for row in rows:
        if row[3] == today:
            nickname = row[1]
            type_mp = row[2]

            if nickname not in stats:
                stats[nickname] = {}

            stats[nickname][type_mp] = stats[nickname].get(type_mp, 0) + 1

    text = f"📊 Статистика за {today}\n\n"

    for nick, types in stats.items():
        text += f"{nick}\n"
        for t, count in types.items():
            text += f"{t} - {count} слежки\n"
        text += "\n"

    vk.messages.send(chat_id=CHAT_ID, message=text, random_id=0)

# ================= НЕДЕЛЬНАЯ СТАТИСТИКА =================

def weekly_stats():
    now = datetime.now(TIMEZONE)
    week_ago = now - timedelta(days=7)
    rows = sheet.get_all_values()[1:]

    scores = {}

    for row in rows:
        date_obj = datetime.strptime(row[3], "%d.%m.%Y")
        if week_ago <= date_obj <= now:
            nickname = row[1]
            scores[nickname] = scores.get(nickname, 0) + 2

    if not scores:
        return

    max_score = max(scores.values())
    top_user = max(scores, key=scores.get)
    scores[top_user] += 4

    text = "🏆 Итоги следящих\n\n"

    for nick, score in sorted(scores.items(), key=lambda x: x[1], reverse=True):
        text += f"{nick} - {score} баллов\n"

    text += f"\n🔥 Самый активный: {top_user} (+4 бонуса)"

    vk.messages.send(chat_id=CHAT_ID, message=text, random_id=0)

# ================= ПЛАНИРОВЩИК =================

scheduler = BackgroundScheduler(timezone=TIMEZONE)
scheduler.add_job(check_new_reports, "interval", seconds=30)
scheduler.add_job(daily_stats, "cron", hour=23, minute=30)
scheduler.add_job(weekly_stats, "cron", day_of_week="sun", hour=20, minute=0)
scheduler.start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)