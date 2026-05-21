import re
import logging
import gdown
import zipfile
import shutil
import json
import os

from datetime import datetime
from pathlib import Path

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)

from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    CallbackQueryHandler
)

logging.basicConfig(level=logging.INFO)

# =========================
# CONFIG
# =========================

BOT_TOKEN = os.environ.get("BOT_TOKEN")

ADMIN_IDS = [
    int(x)
    for x in os.environ.get("ADMIN_IDS", "").split(",")
    if x.strip()
]

DATA_DIR = "extracted_files"
ZIP_FILE = "data.zip"

CODES_FILE = "access_codes.json"
USERS_FILE = "users_db.json"
STATS_FILE = "stats.json"

ACCESS_CODES = {}
USERS_DB = {}
STATS = {}

# =========================
# LOAD DATA
# =========================

def load_all_data():

    global ACCESS_CODES, USERS_DB, STATS

    if os.path.exists(CODES_FILE):

        try:

            with open(CODES_FILE, "r") as f:
                ACCESS_CODES = json.load(f)

        except:
            ACCESS_CODES = {}

    if os.path.exists(USERS_FILE):

        try:

            with open(USERS_FILE, "r") as f:
                USERS_DB = json.load(f)

        except:
            USERS_DB = {}

    if os.path.exists(STATS_FILE):

        try:

            with open(STATS_FILE, "r") as f:
                STATS = json.load(f)

        except:
            STATS = {}

# =========================
# SAVE DATA
# =========================

def save_all_data():

    with open(CODES_FILE, "w") as f:
        json.dump(ACCESS_CODES, f)

    with open(USERS_FILE, "w") as f:
        json.dump(USERS_DB, f)

    with open(STATS_FILE, "w") as f:
        json.dump(STATS, f)

# =========================
# CHECK CODE
# =========================

def is_code_valid(user_id, code):

    if code not in ACCESS_CODES:
        return False, "❌ الكود غير موجود"

    code_data = ACCESS_CODES[code]

    if code_data["expires_at"]:

        expires = datetime.fromisoformat(
            code_data["expires_at"]
        )

        if datetime.now() > expires:
            return False, "⏰ انتهت صلاحية الكود"

    if (
        code_data["max_uses"] > 0
        and code_data["used_count"] >= code_data["max_uses"]
    ):

        return False, "❌ تم استهلاك الكود"

    return True, "✅"

# =========================
# EXTRACT DRIVE ID
# =========================

def extract_drive_id(url):

    patterns = [
        r"/file/d/([a-zA-Z0-9_-]+)",
        r"id=([a-zA-Z0-9_-]+)",
        r"/open\?id=([a-zA-Z0-9_-]+)"
    ]

    for pattern in patterns:

        match = re.search(pattern, url)

        if match:
            return match.group(1)

    return None

# =========================
# URL TO COMBO
# =========================

async def convert_url_to_combo(url):

    try:

        match = re.search(
            r':([^/:]+:[^/]+)$',
            url
        )

        if match:
            return match.group(1).strip()

        if ':' in url:

            parts = url.split(':')

            if len(parts) >= 2:
                return ':'.join(parts[-2:])

        return None

    except:
        return None

# =========================
# MAIN MENU
# =========================

def get_main_menu():

    keyboard = [

        [
            InlineKeyboardButton(
                "🔍 البحث",
                callback_data="search"
            ),

            InlineKeyboardButton(
                "📁 الملفات",
                callback_data="files"
            )
        ],

        [
            InlineKeyboardButton(
                "🔄 Combo Converter",
                callback_data="converter"
            ),

            InlineKeyboardButton(
                "📊 الإحصائيات",
                callback_data="stats"
            )
        ],

        [
            InlineKeyboardButton(
                "💳 الاشتراك",
                callback_data="subscription"
            ),

            InlineKeyboardButton(
                "⚙️ الإعدادات",
                callback_data="settings"
            )
        ],

        [
            InlineKeyboardButton(
                "❓ المساعدة",
                callback_data="help"
            ),

            InlineKeyboardButton(
                "🆔 معلوماتي",
                callback_data="myinfo"
            )
        ]
    ]

    return InlineKeyboardMarkup(keyboard)

# =========================
# START
# =========================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    load_all_data()

    user_id = update.effective_user.id
    first_name = update.effective_user.first_name

    if str(user_id) not in USERS_DB:

        USERS_DB[str(user_id)] = {

            "first_name": first_name,
            "joined": datetime.now().isoformat(),
            "status": "free",
            "searches": 0,
            "conversions": 0,
            "access_code": None
        }

        save_all_data()

    welcome_text = (
        f"🤖 أهلاً {first_name}\n\n"
        f"بوت البحث والتحويل جاهز 🚀"
    )

    await update.message.reply_text(
        welcome_text,
        reply_markup=get_main_menu()
    )

# =========================
# BUTTONS
# =========================

async def button_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    await query.answer()

    if query.data == "search":

        await query.edit_message_text(
            "🔍 أرسل كلمة البحث"
        )

        context.user_data["mode"] = "search"

    elif query.data == "converter":

        await query.edit_message_text(
            "📤 أرسل ملف TXT للتحويل"
        )

        context.user_data["mode"] = "converter"

    elif query.data == "stats":

        user_id = str(update.effective_user.id)

        user_data = USERS_DB.get(user_id, {})

        await query.edit_message_text(
            f"📊 Searches: {user_data.get('searches',0)}\n"
            f"🔄 Conversions: {user_data.get('conversions',0)}"
        )

    elif query.data == "help":

        await query.edit_message_text(
            "💬 أرسل رابط Google Drive ZIP ثم ابحث."
        )

    elif query.data == "myinfo":

        user = update.effective_user

        await query.edit_message_text(
            f"👤 {user.first_name}\n"
            f"🆔 {user.id}"
        )

    elif query.data == "back":

        await query.edit_message_text(
            "🏠 القائمة الرئيسية",
            reply_markup=get_main_menu()
        )

# =========================
# HANDLE TXT FILE
# =========================

async def handle_document(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user_id = str(update.effective_user.id)

    document = update.message.document

    if not document.file_name.endswith(".txt"):

        await update.message.reply_text(
            "❌ أرسل TXT فقط"
        )

        return

    file = await context.bot.get_file(
        document.file_id
    )

    await file.download_to_drive("temp.txt")

    combos = []

    with open(
        "temp.txt",
        "r",
        encoding="utf-8",
        errors="ignore"
    ) as f:

        lines = f.readlines()

    status = await update.message.reply_text(
        "⏳ Processing..."
    )

    for line in lines:

        line = line.strip()

        if line:

            combo = await convert_url_to_combo(
                line
            )

            if combo:
                combos.append(combo)

    if not combos:

        await status.edit_text(
            "❌ لا توجد نتائج"
        )

        return

    output_file = "combos.txt"

    with open(
        output_file,
        "w",
        encoding="utf-8"
    ) as f:

        for combo in combos:
            f.write(combo + "\n")

    USERS_DB[user_id]["conversions"] += 1

    save_all_data()

    await status.edit_text(
        f"✅ تم استخراج {len(combos)}"
    )

    await update.message.reply_document(
        document=open(output_file, "rb"),
        filename="combos.txt"
    )

# =========================
# HANDLE TEXT
# =========================

async def handle_text(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    text = update.message.text.strip()

    mode = context.user_data.get("mode")

    # =========================
    # GOOGLE DRIVE
    # =========================

    if "drive.google.com" in text:

        file_id = extract_drive_id(text)

        if not file_id:

            await update.message.reply_text(
                "❌ رابط خاطئ"
            )

            return

        msg = await update.message.reply_text(
            "⬇️ Downloading..."
        )

        try:

            url = (
                f"https://drive.google.com/"
                f"uc?export=download&id={file_id}"
            )

            gdown.download(
                url,
                ZIP_FILE,
                quiet=False
            )

            await msg.edit_text(
                "📦 Extracting..."
            )

            if os.path.exists(DATA_DIR):
                shutil.rmtree(DATA_DIR)

            os.makedirs(
                DATA_DIR,
                exist_ok=True
            )

            with zipfile.ZipFile(
                ZIP_FILE,
                'r'
            ) as zip_ref:

                zip_ref.extractall(DATA_DIR)

            txt_files = list(
                Path(DATA_DIR).rglob("*.txt")
            )

            await msg.edit_text(
                f"✅ Loaded {len(txt_files)} files"
            )

        except Exception as e:

            await msg.edit_text(
                f"❌ {str(e)}"
            )

        return

    # =========================
    # SEARCH
    # =========================

    if mode == "search":

        keyword = text

        results = []

        msg = await update.message.reply_text(
            "🔍 Searching..."
        )

        txt_files = list(
            Path(DATA_DIR).rglob("*.txt")
        )

        for txt_file in txt_files:

            try:

                with open(
                    txt_file,
                    "r",
                    encoding="utf-8",
                    errors="ignore"
                ) as f:

                    for line in f:

                        if keyword.lower() in line.lower():
                            results.append(
                                line.strip()
                            )

            except:
                pass

        if not results:

            await msg.edit_text(
                "❌ No Results"
            )

            return

        output = "results.txt"

        with open(
            output,
            "w",
            encoding="utf-8"
        ) as f:

            for i, line in enumerate(results, 1):
                f.write(f"{i}. {line}\n")

        await msg.edit_text(
            f"✅ Found {len(results)}"
        )

        await update.message.reply_document(
            document=open(output, "rb"),
            filename="results.txt"
        )

# =========================
# ADMIN ADD CODE
# =========================

async def addcode_cmd(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user_id = update.effective_user.id

    if user_id not in ADMIN_IDS:

        await update.message.reply_text(
            "❌ Admin only"
        )

        return

    if len(context.args) < 3:

        await update.message.reply_text(
            "/addcode CODE USES DATE"
        )

        return

    code = context.args[0]

    max_uses = int(context.args[1])

    expiry_date = context.args[2]

    ACCESS_CODES[code] = {

        "max_uses": max_uses,
        "used_count": 0,
        "expires_at":
        f"{expiry_date}T23:59:59"
    }

    save_all_data()

    await update.message.reply_text(
        f"✅ Added {code}"
    )

# =========================
# MAIN
# =========================

def main():

    load_all_data()

    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .build()
    )

    app.add_handler(
        CommandHandler("start", start)
    )

    app.add_handler(
        CommandHandler("addcode", addcode_cmd)
    )

    app.add_handler(
        CallbackQueryHandler(button_callback)
    )

    app.add_handler(
        MessageHandler(
            filters.Document.ALL,
            handle_document
        )
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_text
        )
    )

    print("BOT ONLINE")

    app.run_polling()

# =========================

if __name__ == "__main__":
    main()
