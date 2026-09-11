import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice
import time
import sqlite3
import threading
import os
from http.server import HTTPServer, BaseHTTPRequestHandler

TOKEN = os.getenv('BOT_TOKEN', '8924716382:AAFegcX8tY54K-rOXVK3Gg4lmp9xjTf-QX4')
bot = telebot.TeleBot(TOKEN)

DB_NAME = 'casino_data.db'
GAME_COOLDOWN = 3.5
ACTION_COOLDOWN = 1.0
BONUS_COOLDOWN = 86400
BROADCAST_INTERVAL = 5 * 3600

# ==================== ВЕБ-СЕРВЕР ДЛЯ RENDER ====================
class DummyWebHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()
        html_page = """
        <!DOCTYPE html>
        <html lang="ru">
        <head>
            <meta charset="UTF-8">
            <title>Casino Bot Status</title>
            <style>
                body { background-color: #0f172a; color: #ffffff; font-family: sans-serif; text-align: center; padding-top: 100px; }
                .card { background: #1e293b; display: inline-block; padding: 40px; border-radius: 15px; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }
                h1 { color: #38bdf8; margin-bottom: 10px; }
                p { color: #94a3b8; font-size: 18px; }
                .status { display: inline-block; width: 12px; height: 12px; background: #22c55e; border-radius: 50%; margin-right: 8px; }
            </style>
        </head>
        <body>
            <div class="card">
                <h1>🎰 Telegram Casino Bot</h1>
                <p><span class="status"></span> Сервис активно работает в фоновом режиме!</p>
            </div>
        </body>
        </html>
        """
        self.wfile.write(html_page.encode('utf-8'))

    def log_message(self, format, *args):
        return

def run_web_server():
    port = int(os.getenv("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), DummyWebHandler)
    print(f"🌐 Веб-сервер заглушка запущен на порту {port}")
    server.serve_forever()
# ===============================================================

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            balance INTEGER DEFAULT 1000,
            bet INTEGER DEFAULT 10,
            name TEXT,
            last_action REAL DEFAULT 0.0,
            last_bonus REAL DEFAULT 0.0
        )
    ''')
    cursor.execute("PRAGMA table_info(users)")
    columns = [column[1] for column in cursor.fetchall()]
    if 'last_bonus' not in columns:
        cursor.execute('ALTER TABLE users ADD COLUMN last_bonus REAL DEFAULT 0.0')
        
    conn.commit()
    conn.close()

def get_user(user):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    name = user.first_name if user.first_name else "Игрок"
    
    cursor.execute('SELECT balance, bet, last_action, last_bonus FROM users WHERE user_id = ?', (user.id,))
    row = cursor.fetchone()
    
    if not row:
        cursor.execute(
            'INSERT INTO users (user_id, balance, bet, name, last_action, last_bonus) VALUES (?, ?, ?, ?, ?, ?)',
            (user.id, 1000, 10, name, 0.0, 0.0)
        )
        conn.commit()
        balance, bet, last_action, last_bonus = 1000, 10, 0.0, 0.0
    else:
        balance, bet, last_action, last_bonus = row
        cursor.execute('UPDATE users SET name = ? WHERE user_id = ?', (name, user.id))
        conn.commit()
        
    conn.close()
    return {
        'balance': balance, 
        'bet': bet, 
        'last_action': last_action, 
        'last_bonus': last_bonus,
        'name': name
    }

def update_user_data(user_id, balance=None, bet=None, last_action=None, last_bonus=None):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    if balance is not None:
        cursor.execute('UPDATE users SET balance = ? WHERE user_id = ?', (balance, user_id))
    if bet is not None:
        cursor.execute('UPDATE users SET bet = ? WHERE user_id = ?', (bet, user_id))
    if last_action is not None:
        cursor.execute('UPDATE users SET last_action = ? WHERE user_id = ?', (last_action, user_id))
    if last_bonus is not None:
        cursor.execute('UPDATE users SET last_bonus = ? WHERE user_id = ?', (last_bonus, user_id))
    conn.commit()
    conn.close()

def get_top_users():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT name, balance FROM users ORDER BY balance DESC LIMIT 10')
    rows = cursor.fetchall()
    conn.close()
    return rows

def auto_broadcaster():
    while True:
        time.sleep(BROADCAST_INTERVAL)
        try:
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            cursor.execute('SELECT user_id FROM users')
            all_users = cursor.fetchall()
            conn.close()

            promo_text = (
                "⭐ **Бесплатные Telegram Stars!** ⭐\n\n"
                "Хочешь бесплатно получать звёздочки Telegram?\n"
                "Переходи в бота по ссылке ниже и забирай свои ⭐:\n\n"
                "👉 https://t.me/denddkilibot?start=_tgr_XNDqEMRjNTAy"
            )

            for (user_id,) in all_users:
                try:
                    bot.send_message(user_id, promo_text, parse_mode="Markdown")
                    time.sleep(0.05)
                except Exception:
                    pass
        except Exception as e:
            print(f"Ошибка при рассылке: {e}")

def get_main_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        KeyboardButton("🎰 ИГРАТЬ"),
        KeyboardButton("🎁 Ежедневный бонус"),
        KeyboardButton("⚙️ Ставка"),
        KeyboardButton("💰 Баланс"),
        KeyboardButton("🏆 Топ лидеров"),
        KeyboardButton("⭐ Магазин (XTR)"),
        KeyboardButton("💸 Вывод")
    )
    return markup

def get_games_menu():
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("🎰 Слот-машина (до х50)", callback_data="game_slot"),
        InlineKeyboardButton("🎲 Кубик (х3 за 6, х1.5 за 5)", callback_data="game_dice"),
        InlineKeyboardButton("🎯 Дартс (х3.5 яблочко, х1.5 рядом)", callback_data="game_darts"),
        InlineKeyboardButton("🎳 Боулинг (х4 страйк, х2 почти)", callback_data="game_bowling"),
        InlineKeyboardButton("🏀 Баскетбол (х2.5 попадание, х1.5 обод)", callback_data="game_basketball")
    )
    return markup

def get_bet_menu():
    markup = InlineKeyboardMarkup(row_width=3)
    markup.add(
        InlineKeyboardButton("10", callback_data="setbet_10"),
        InlineKeyboardButton("50", callback_data="setbet_50"),
        InlineKeyboardButton("100", callback_data="setbet_100"),
        InlineKeyboardButton("500", callback_data="setbet_500"),
        InlineKeyboardButton("1000", callback_data="setbet_1000"),
        InlineKeyboardButton("🔥 MAX (Все)", callback_data="setbet_max")
    )
    return markup

def get_shop_menu():
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("⭐ 50 монет — 6 ⭐ (Старт)", callback_data="buy_50_6"),
        InlineKeyboardButton("🌟 300 монет — 15 ⭐ (Выгодно)", callback_data="buy_300_15"),
        InlineKeyboardButton("🥉 1000 монет — 50 ⭐", callback_data="buy_1000_50"),
        InlineKeyboardButton("🥈 5000 монет — 200 ⭐", callback_data="buy_5000_200"),
        InlineKeyboardButton("🥇 15000 монет — 500 ⭐ (Топ!)", callback_data="buy_15000_500")
    )
    return markup

def get_withdraw_menu():
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("⭐ 15 Звёзд — 50 000 🪙", callback_data="withdraw_15"),
        InlineKeyboardButton("⭐ 50 Звёзд — 150 000 🪙", callback_data="withdraw_50")
    )
    return markup

@bot.message_handler(commands=['start'])
def start_cmd(message):
    u_data = get_user(message.from_user)
    bot.send_message(
        message.chat.id, 
        f"Добро пожаловать в CasinoBot! ⭐🎰\n\nТвой баланс: {u_data['balance']} 🪙.\n\nВыбирай действие в меню:", 
        reply_markup=get_main_menu()
    )

@bot.message_handler(func=lambda message: True)
def handle_text(message):
    user = message.from_user
    u_data = get_user(user)
    user_id = user.id
    now = time.time()

    if now - u_data['last_action'] < ACTION_COOLDOWN:
        return
    update_user_data(user_id, last_action=now)

    text = message.text

    if text == "🎰 ИГРАТЬ":
        bot.send_message(message.chat.id, f"🎰 Выбирай игру!\n🎲 Ваша текущая ставка: {u_data['bet']} 🪙", reply_markup=get_games_menu())
        
    elif text == "🎁 Ежедневный бонус":
        last_bonus = u_data['last_bonus']
        time_passed = now - last_bonus
        
        if time_passed >= BONUS_COOLDOWN:
            new_bal = u_data['balance'] + 50
            update_user_data(user_id, balance=new_bal, last_bonus=now)
            bot.send_message(
                message.chat.id, 
                f"🎉 **Ежедневный бонус получен!**\n\nВам начислено **+50 🪙**.\n💳 Ваш баланс: {new_bal} 🪙\n\nЗаходите завтра за новым бонусом!"
            )
        else:
            rem_seconds = int(BONUS_COOLDOWN - time_passed)
            hours = rem_seconds // 3600
            minutes = (rem_seconds % 3600) // 60
            bot.send_message(
                message.chat.id, 
                f"⏳ Вы уже забрали свой бонус сегодня!\n\nСледующий бонус будет доступен через **{hours} ч. {minutes} мин.**"
            )
        
    elif text == "⚙️ Ставка":
        bot.send_message(message.chat.id, f"⚙️ Ваша ставка: {u_data['bet']} 🪙.\nВыберите новую сумму:", reply_markup=get_bet_menu())
        
    elif text == "💰 Баланс":
        bot.send_message(message.chat.id, f"💳 Ваш баланс: {u_data['balance']} 🪙\n🎲 Текущая ставка: {u_data['bet']} 🪙")

    elif text == "🏆 Топ лидеров":
        top_users = get_top_users()
        leaderboard_text = "🏆 **ТОП-10 БОГАЧЕЙ КАЗИНО** 🏆\n\n"
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
        
        for idx, (name, bal) in enumerate(top_users):
            medal = medals[idx] if idx < len(medals) else "👤"
            leaderboard_text += f"{medal} **{name}** — {bal} 🪙\n"
            
        bot.send_message(message.chat.id, leaderboard_text, parse_mode="Markdown")
        
    elif text == "⭐ Магазин (XTR)":
        bot.send_message(message.chat.id, "🛒 Выберите пакет монет для покупки за Telegram Stars (XTR):", reply_markup=get_shop_menu())
        
    elif text == "💸 Вывод":
        bot.send_message(
            message.chat.id,
            f"💸 **Вывод Telegram Stars** ⭐\n\n"
            f"💳 Ваш текущий баланс: {u_data['balance']} 🪙\n\n"
            f"Выберите вариант вывода:",
            reply_markup=get_withdraw_menu(),
            parse_mode="Markdown"
        )

@bot.callback_query_handler(func=lambda call: call.data.startswith('withdraw_'))
def handle_withdraw(call):
    user = call.from_user
    u_data = get_user(user)
    user_id = user.id
    
    amount = call.data.split('_')[1]
    
    if amount == '15':
        cost = 50000
        stars = 15
    elif amount == '50':
        cost = 150000
        stars = 50
    else:
        return

    bal = u_data['balance']
    if bal < cost:
        bot.answer_callback_query(
            call.id, 
            f"❌ Недостаточно монет! Для вывода {stars} ⭐ нужно {cost} 🪙.\nВаш баланс: {bal} 🪙.", 
            show_alert=True
        )
    else:
        new_bal = bal - cost
        update_user_data(user_id, balance=new_bal)
        bot.answer_callback_query(call.id, "Заявка принята!")
        bot.send_message(
            call.message.chat.id,
            f"✅ **Заявка на вывод {stars} ⭐ создана!**\n\nЖдите, ваша заявка скоро будет принята.\n\n💳 Списано: {cost} 🪙\n💰 Остаток: {new_bal} 🪙",
            parse_mode="Markdown"
        )

@bot.callback_query_handler(func=lambda call: call.data.startswith('setbet_'))
def handle_setbet(call):
    user = call.from_user
    u_data = get_user(user)
    user_id = user.id
    val = call.data.split('_')[1]
    
    if val == 'max':
        new_bet = u_data['balance']
        if new_bet == 0:
            bot.answer_callback_query(call.id, "❌ Ваш баланс 0! Пополните счет.", show_alert=True)
            return
    else:
        new_bet = int(val)
        
    update_user_data(user_id, bet=new_bet)
    bot.answer_callback_query(call.id, f"Ставка изменена на {new_bet} 🪙")
    try:
        bot.edit_message_text(
            f"✅ Ваша ставка успешно изменена на {new_bet} 🪙.", 
            chat_id=call.message.chat.id, 
            message_id=call.message.message_id
        )
    except Exception:
        pass

@bot.callback_query_handler(func=lambda call: call.data.startswith('buy_'))
def handle_buy(call):
    parts = call.data.split('_')
    coins = int(parts[1])
    stars = int(parts[2])
    
    prices = [LabeledPrice(label=f"{coins} монет", amount=stars)]
    bot.send_invoice(
        call.message.chat.id,
        title=f"Пополнение: {coins} 🪙",
        description=f"Покупка {coins} монет за {stars} Telegram Stars (XTR).",
        invoice_payload=f"buy_{coins}",
        provider_token="",
        currency="XTR",
        prices=prices
    )
    bot.answer_callback_query(call.id)

@bot.pre_checkout_query_handler(func=lambda query: True)
def checkout(pre_checkout_query):
    bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@bot.message_handler(content_types=['successful_payment'])
def got_payment(message):
    user = message.from_user
    u_data = get_user(user)
    user_id = user.id
    
    payload = message.successful_payment.invoice_payload
    if payload.startswith("buy_"):
        coins_bought = int(payload.split('_')[1])
        new_bal = u_data['balance'] + coins_bought
        update_user_data(user_id, balance=new_bal)
        bot.send_message(
            message.chat.id, 
            f"✅ Успешная оплата! Вам начислено {coins_bought} 🪙.\n⭐ Баланс: {new_bal} 🪙. Желаем удачи!"
        )

@bot.callback_query_handler(func=lambda call: call.data.startswith('game_'))
def handle_game(call):
    user = call.from_user
    u_data = get_user(user)
    user_id = user.id
    now = time.time()

    time_passed = now - u_data['last_action']
    if time_passed < GAME_COOLDOWN:
        bot.answer_callback_query(
            call.id, 
            f"⏳ Подождите еще {round(GAME_COOLDOWN - time_passed, 1)} сек! Анимация еще не закончилась.", 
            show_alert=True
        )
        return

    bet = u_data['bet']
    bal = u_data['balance']
    
    if bet <= 0:
        bot.answer_callback_query(call.id, "❌ Ваша ставка 0. Увеличьте её в меню!", show_alert=True)
        return
        
    if bal < bet:
        bot.answer_callback_query(call.id, f"❌ Недостаточно монет! Баланс: {bal} 🪙, Ставка: {bet} 🪙.", show_alert=True)
        return

    new_bal = bal - bet
    update_user_data(user_id, balance=new_bal, last_action=now)
    bot.answer_callback_query(call.id, "Бросок сделан!")

    game_type = call.data.split('_')[1]
    emoji_map = {'slot': '🎰', 'dice': '🎲', 'darts': '🎯', 'bowling': '🎳', 'basketball': '🏀'}
    emoji = emoji_map.get(game_type, '🎲')

    msg = bot.send_dice(call.message.chat.id, emoji=emoji)
    val = msg.dice.value 

    time.sleep(3) 

    mult = 0
    text_result = ""

    if game_type == 'slot':
        if val == 64: mult = 50.0; text_result = "🎰 ДЖЕКПОТ! 777!"
        elif val in [1, 22, 43]: mult = 12.0; text_result = "🎉 Три одинаковых!"
        elif val in [16, 32, 48]: mult = 1.5; text_result = "✨ Пара символов!"
        else: text_result = "😢 Увы, не повезло."
            
    elif game_type == 'dice':
        if val == 6: mult = 3.0; text_result = "🎲 Выпала 6! Выигрыш x3!"
        elif val == 5: mult = 1.5; text_result = "🎲 Выпала 5! Выигрыш x1.5!"
        else: text_result = f"🎲 Выпало {val}. Проигрыш."
            
    elif game_type == 'darts':
        if val == 6: mult = 3.5; text_result = "🎯 ЯБЛОЧКО! (x3.5)"
        elif val == 5: mult = 1.5; text_result = "🎯 Почти в центр! (x1.5)"
        else: text_result = "🎯 Промах."
            
    elif game_type == 'bowling':
        if val == 6: mult = 4.0; text_result = "🎳 СТРАЙК! (x4)"
        elif val == 5: mult = 2.0; text_result = "🎳 Почти все кегли! (x2)"
        else: text_result = "🎳 Мимо кеглей."
            
    elif game_type == 'basketball':
        if val == 5: mult = 2.5; text_result = "🏀 ТОЧНЫЙ БРОСОК В СЕТКУ! (x2.5)"
        elif val == 4: mult = 1.5; text_result = "🏀 Попадание от дуги! (x1.5)"
        else: text_result = "🏀 Мяч не попал в корзину."

    win_amount = int(bet * mult)
    final_bal = new_bal + win_amount
    update_user_data(user_id, balance=final_bal)
    
    final_text = f"{text_result}\n\n"
    if win_amount > 0:
        final_text += f"🟢 Вы выиграли +{win_amount} 🪙! (Ставка: {bet})\n"
    else:
        final_text += f"🔴 Вы проиграли -{bet} 🪙.\n"
        
    final_text += f"💳 Ваш текущий баланс: {final_bal} 🪙"
    
    bot.send_message(call.message.chat.id, final_text)

if __name__ == '__main__':
    init_db()
    
    web_thread = threading.Thread(target=run_web_server, daemon=True)
    web_thread.start()

    broadcaster_thread = threading.Thread(target=auto_broadcaster, daemon=True)
    broadcaster_thread.start()
    
    print("✅ Бот запущен!")
    bot.infinity_polling(timeout=20, long_polling_timeout=10)