import json
import uuid
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# Файл для сохранения данных
USERS_DB_FILE = "users_db.json"
ADMIN_ID = ""  # Замените на Telegram ID администратора

# Загрузка базы данных
try:
    with open(USERS_DB_FILE, "r") as file:
        users_db = json.load(file)
except FileNotFoundError:
    users_db = {}

def save_users_db():
    """Сохраняет данные пользователей."""
    with open(USERS_DB_FILE, "w") as file:
        json.dump(users_db, file, indent=4)

# Товары
products = {
    1: {"name": "🧸 Игрушка 1", "price": 500},
    2: {"name": "🚗 Игрушка 2", "price": 300},
    3: {"name": "🐻 Игрушка 3", "price": 700},
}

# Команды
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.message.from_user.id)
    if user_id not in users_db:
        users_db[user_id] = {"phone": None, "orders": [], "balance": 1000}
        save_users_db()

    keyboard = [
        [InlineKeyboardButton("📞 Добавить номер телефона", callback_data="set_phone")],
        [InlineKeyboardButton("🛒 Оформить заказ", callback_data="new_order")],
        [InlineKeyboardButton("👤 Профиль", callback_data="view_profile")],
        [InlineKeyboardButton("💰 Баланс", callback_data="view_balance")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "*👋 Добро пожаловать!*\n\n"
        "Я бот, который поможет вам:\n"
        "📞 Добавить ваш номер телефона.\n"
        "🛒 Оформить заказ.\n"
        "👤 Узнать информацию о вашем профиле.\n"
        "💰 Проверить текущий баланс.\n\n"
        "Выберите действие, нажав на кнопку ниже:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )


# Установка номера телефона
async def set_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        "📞 *Добавление номера телефона:*\n\n"
        "Введите ваш номер телефона в формате `+1234567890`.\n"
        "Это поможет нам связаться с вами по заказу.",
        parse_mode="Markdown"
    )
    context.chat_data["step"] = "phone"

async def handle_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.message.from_user.id)
    step = context.chat_data.get("step")

    if step == "phone":
        phone = update.message.text
        if not phone.startswith("+") or not phone[1:].isdigit():
            await update.message.reply_text(
                "❌ *Ошибка:*\n\n"
                "Номер телефона должен начинаться с `+` и содержать только цифры. Попробуйте снова.",
                parse_mode="Markdown"
            )
            return
        users_db[user_id]["phone"] = phone
        save_users_db()
        await update.message.reply_text("✅ *Номер телефона сохранен!*", parse_mode="Markdown")
        context.chat_data["step"] = None

    elif step == "address":
        address = update.message.text
        context.chat_data["address"] = address
        await update.message.reply_text(
            "📝 *Добавьте комментарий к заказу:*\n\n"
            "Например, уточните удобное время доставки или другие детали.",
            parse_mode="Markdown"
        )
        context.chat_data["step"] = "comment"

    elif step == "comment":
        comment = update.message.text
        context.chat_data["comment"] = comment
        await finalize_order(update, context)

    else:
        await update.message.reply_text("❌ Неожиданный ввод. Пожалуйста, начните заново.")


# Просмотр профиля
async def view_profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user_id = str(query.from_user.id)
    user_data = users_db.get(user_id, {"phone": "Не указан", "balance": 0, "orders": []})
    phone = user_data.get("phone", "Не указан")
    balance = user_data.get("balance", 0)
    orders_count = len(user_data.get("orders", []))

    await query.message.reply_text(
        f"👤 *Ваш профиль:*\n\n"
        f"📞 *Телефон:* {phone}\n"
        f"💰 *Баланс:* {balance}₽\n"
        f"🛒 *Количество заказов:* {orders_count}\n\n"
        "Вы можете вернуться в меню или продолжить покупки.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Главное меню", callback_data="main_menu")]])
    )

# Просмотр баланса
async def view_balance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user_id = str(query.from_user.id)
    balance = users_db[user_id].get("balance", 0)

    await query.message.reply_text(
        f"💰 *Ваш текущий баланс:*\n\n"
        f"{balance}₽",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Главное меню", callback_data="main_menu")]])
    )

# Кнопка возврата в главное меню
async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await start(update.callback_query, context)

# Генерация заказа
async def confirm_order(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    order_id = query.data.split("_")[1]
    user_id = str(query.from_user.id)

    order = next((o for o in users_db[user_id]["orders"] if o["order_id"] == order_id), None)
    if not order:
        await query.message.reply_text("❌ Ошибка: заказ не найден.")
        return

    # Отправка заказа администратору
    await context.bot.send_message(
        ADMIN_ID,
        f"🎉 *Новый заказ:*\n\n"
        f"📞 *Телефон клиента:* {users_db[user_id]['phone']}\n"
        f"🛍️ *Товар:* {order['product']['name']}\n"
        f"🏠 *Адрес доставки:* {order['address']}\n"
        f"📝 *Комментарий:* {order['comment']}\n"
        f"💵 *Стоимость:* {order['product']['price']}₽\n"
        f"🆔 *Номер заказа:* {order_id}",
        parse_mode="Markdown"
    )

    # Сообщение пользователю
    await query.message.reply_text(
        "✅ *Ваш заказ был успешно отправлен администратору!*\n\n"
        "Спасибо за покупку! Вы можете вернуться в меню.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Главное меню", callback_data="main_menu")]]),
        parse_mode="Markdown"
    )

# Отмена заказа
async def cancel_order(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.message.reply_text(
        "❌ *Ваш заказ был отменен.*\n\n"
        "Вы можете вернуться в меню или начать заново.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Главное меню", callback_data="main_menu")]]),
        parse_mode="Markdown"
    )
async def finalize_order(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.message.from_user.id)
    product = context.chat_data.get("selected_product")
    address = context.chat_data.get("address", "Не указано")
    comment = context.chat_data.get("comment", "Нет комментария")
    balance = users_db[user_id]["balance"]
    price = product["price"]
    remaining_balance = balance - price if balance >= price else "Недостаточно средств"
    order_id = str(uuid.uuid4())

    users_db[user_id]["orders"].append({
        "product": product,
        "address": address,
        "comment": comment,
        "order_id": order_id
    })
    users_db[user_id]["balance"] = remaining_balance if isinstance(remaining_balance, int) else balance
    save_users_db()

    keyboard = [
        [InlineKeyboardButton("✅ Сгенерировать заказ", callback_data=f"confirm_{order_id}")],
        [InlineKeyboardButton("❌ Отменить заказ", callback_data=f"cancel_{order_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"🎉 *Ваш заказ:*\n\n"
        f"🛍️ *Товар:* {product['name']}\n"
        f"📞 *Ваш номер телефона:* {users_db[user_id]['phone']}\n"
        f"📝 *Ваш комментарий:* {comment}\n"
        f"🏠 *Адрес доставки:* {address}\n"
        f"💵 *Стоимость:* {price}₽\n"
        f"💰 *Остаток баланса:* {remaining_balance}₽\n"
        f"🆔 *Номер заказа:* {order_id}\n\n"
        "Что хотите сделать?",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

    context.chat_data.clear()
# Выбор товара
async def select_product(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    product_id = int(query.data.split("_")[1])
    context.chat_data["selected_product"] = products[product_id]

    await query.message.reply_text(
        "🏠 *Введите адрес доставки или номер почтового отделения:*",
        parse_mode="Markdown"
    )
    context.chat_data["step"] = "address"


# Новый заказ
async def new_order(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user_id = str(query.from_user.id)
    phone = users_db[user_id].get("phone")

    if not phone:
        await query.message.reply_text(
            "❌ *Ошибка:*\n\n"
            "Сначала добавьте ваш номер телефона, чтобы оформить заказ.",
            parse_mode="Markdown"
        )
        return

    keyboard = [[InlineKeyboardButton(f"{p['name']} ({p['price']}₽)", callback_data=f"select_{pid}")]
                for pid, p in products.items()]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.reply_text(
        "🛒 *Выберите товар для заказа:*\n\n"
        "Нажмите на одну из кнопок ниже, чтобы выбрать товар.",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )


# Основная функция
def main():
    app = ApplicationBuilder().token("").build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(view_profile, pattern="^view_profile$"))
    app.add_handler(CallbackQueryHandler(view_balance, pattern="^view_balance$"))
    app.add_handler(CallbackQueryHandler(main_menu, pattern="^main_menu$"))
    app.add_handler(CallbackQueryHandler(confirm_order, pattern="^confirm_"))
    app.add_handler(CallbackQueryHandler(cancel_order, pattern="^cancel_"))
    # Добавьте другие обработчики по необходимости
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(set_phone, pattern="^set_phone$"))
    app.add_handler(CallbackQueryHandler(new_order, pattern="^new_order$"))
    app.add_handler(CallbackQueryHandler(select_product, pattern="^select_\\d+$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_input))

    app.run_polling()

if __name__ == "__main__":
    main()
