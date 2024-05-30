#установи: npm install pip
#установи: pip install python-telegram-bot Flask
#если pip не находит то пиши: py -m pip install python-telegram-bot Flask
#запуск: py .\telegram-bot.py
import sqlite3
import re
from datetime import datetime
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    CallbackContext,
    ConversationHandler,
    CallbackQueryHandler,
)

TOKEN = '7306458483:AAHoYQSzkyV6oGDPvdyiybsobPzPWaQIt28'
DATABASE = './Admin.db'

# Настройка начального состояния для регистрации клиента
(START, FULL_NAME, PHONE, FEATURE, MASTER, DATE, TIME) = range(7)

# Валидаторы
def is_valid_phone(phone):
    return re.match(r'^\+?\d{10,15}$', phone)

def is_valid_date(date_str):
    try:
        datetime.strptime(date_str, '%Y-%m-%d')
        return True
    except ValueError:
        return False

def is_valid_time(time_str):
    try:
        datetime.strptime(time_str, '%H:%M')
        return True
    except ValueError:
        return False

# Обработчик команды /start
async def start(update: Update, context: CallbackContext) -> int:
    await update.message.reply_text('Добро пожаловать! Введите ваше ФИО:')
    return FULL_NAME

# Обработчики каждого этапа диалога
async def get_full_name(update: Update, context: CallbackContext) -> int:
    context.user_data['full_name'] = update.message.text
    await update.message.reply_text('Введите ваш телефон (например, +1234567890):')
    return PHONE

async def get_phone(update: Update, context: CallbackContext) -> int:
    phone = update.message.text
    if not is_valid_phone(phone):
        await update.message.reply_text('Неверный формат телефона. Пожалуйста, введите правильный номер телефона (например, +1234567890):')
        return PHONE

    context.user_data['phone'] = phone
    await update.message.reply_text('Введите особенности:')
    return FEATURE

async def get_feature(update: Update, context: CallbackContext) -> int:
    context.user_data['feature'] = update.message.text
    
    # Получение списка мастеров из базы данных
    masters = get_masters()
    buttons = [[InlineKeyboardButton(m['full_name'], callback_data=str(m['id']))] for m in masters]
    reply_markup = InlineKeyboardMarkup(buttons)
    await update.message.reply_text('Выберите мастера:', reply_markup=reply_markup)
    return MASTER

async def button(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    await query.answer()
    master_id = query.data
    context.user_data['master_id'] = int(master_id)
    
    await query.edit_message_text(text=f"Вы выбрали мастера: {get_master_name(master_id)}")
    await query.message.reply_text('Введите дату (ГГГГ-ММ-ДД):', reply_markup=ReplyKeyboardRemove())
    return DATE

async def get_date(update: Update, context: CallbackContext) -> int:
    date_str = update.message.text
    if not is_valid_date(date_str):
        await update.message.reply_text('Неверный формат даты. Пожалуйста, введите правильную дату в формате ГГГГ-ММ-ДД:')
        return DATE

    context.user_data['date'] = date_str
    
    # Получение доступного времени для выбранного мастера и даты
    available_times = get_available_times(context.user_data['master_id'], context.user_data['date'])
    buttons = [InlineKeyboardButton(time, callback_data=time) for time in available_times]
    # Организовать кнопки в 3 столбика
    keyboard = [buttons[i:i + 3] for i in range(0, len(buttons), 3)]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('Выберите время:', reply_markup=reply_markup)
    return TIME

async def get_time(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    await query.answer()
    time_str = query.data

    if not is_valid_time(time_str):
        await query.message.reply_text('Неверный формат времени. Пожалуйста, выберите время из предложенных вариантов:')
        return TIME

    context.user_data['time'] = time_str

    # Добавление клиента в базу данных
    add_client_to_db(context.user_data)
    await query.edit_message_text(text='Клиент успешно добавлен!')
    await query.message.reply_text('Для новой регистрации нажмите /start')
    return ConversationHandler.END

# Отмена процесса добавления клиента
async def cancel(update: Update, context: CallbackContext) -> int:
    await update.message.reply_text('Добавление клиента отменено.', reply_markup=ReplyKeyboardRemove())
    await update.message.reply_text('Для новой регистрации нажмите /start')
    return ConversationHandler.END

# Функции для работы с базой данных
def connect_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def get_masters():
    conn = connect_db()
    cur = conn.cursor()
    cur.execute("SELECT id, full_name FROM master")
    masters = cur.fetchall()
    conn.close()
    return masters

def get_master_name(master_id):
    conn = connect_db()
    cur = conn.cursor()
    cur.execute("SELECT full_name FROM master WHERE id=?", (master_id,))
    master = cur.fetchone()
    conn.close()
    return master['full_name']

def get_available_times(master_id, date):
    conn = connect_db()
    cur = conn.cursor()
    cur.execute("SELECT time FROM appointments WHERE master_id=? AND date=?", (master_id, date))
    booked_times = [row['time'] for row in cur.fetchall()]
    conn.close()
    
    start_time = 10  # Начало работы (10:00)
    end_time = 18  # Конец работы (18:00)
    times = []
    
    for hour in range(start_time, end_time + 1):
        for minute in range(0, 60, 30):
            time = f"{hour:02d}:{minute:02d}"
            if time not in booked_times:
                times.append(time)
    
    return times

def add_client_to_db(client_data):
    conn = connect_db()
    cur = conn.cursor()
    
    # Добавление клиента в таблицу client
    cur.execute("INSERT INTO client (full_name, phone, feature) VALUES (?, ?, ?)", 
                (client_data['full_name'], client_data['phone'], client_data['feature']))
    client_id = cur.lastrowid
    
    # Добавление записи в таблицу appointments
    cur.execute("INSERT INTO appointments (master_id, client_id, date, time) VALUES (?, ?, ?, ?)",
                (client_data['master_id'], client_id, client_data['date'], client_data['time']))
    
    conn.commit()
    conn.close()

# Настройка обработчиков команд и сообщений
def main():
    application = Application.builder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            FULL_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_full_name)],
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)],
            FEATURE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_feature)],
            MASTER: [CallbackQueryHandler(button)],
            DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_date)],
            TIME: [CallbackQueryHandler(get_time)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        per_message=False
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler('cancel', cancel))  # Обработчик команды /cancel

    application.run_polling()

if __name__ == '__main__':
    main()
