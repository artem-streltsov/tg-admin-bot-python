import sqlite3
import requests
import signal
import sys

def load_config(file_path):
    config = {}
    with open(file_path, 'r') as file:
        for line in file:
            if line.strip() and "=" in line:
                key, value = line.strip().split("=", 1)
                config[key] = value
    return config

config = load_config('config.txt')

TOKEN = config.get('BOT_TOKEN')
DATABASE_PATH = config.get('DATABASE_PATH')
BASE_URL = f"https://api.telegram.org/bot{TOKEN}"

admin_chat_id_str = config.get('ADMIN_CHAT_ID')
if admin_chat_id_str is None:
    raise ValueError("Переменная среды ADMIN_CHAT_ID не установлена")
try:
    ADMIN_ID = int(admin_chat_id_str)
except ValueError:
    raise ValueError("ADMIN_CHAT_ID должен быть числом.")


class Database:
    def __init__(self, db_path):
        self.conn = sqlite3.connect(db_path)
        self.create_tables()

    def create_tables(self):
        with self.conn:
            self.conn.execute('''CREATE TABLE IF NOT EXISTS messages (
                                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                                    user_id INTEGER,
                                    username TEXT DEFAULT "",
                                    question TEXT,
                                    answered INTEGER DEFAULT 0,
                                    answer TEXT DEFAULT ""
                                )''')

    def save_message(self, user_id, username, question):
        with self.conn:
            cur = self.conn.cursor()
            cur.execute("INSERT INTO messages (user_id, username, question) VALUES (?, ?, ?)", 
                        (user_id, username, question))
            return cur.lastrowid

    def get_pending_messages(self):
        with self.conn:
            return self.conn.execute("SELECT id, username, question FROM messages WHERE answered = 0").fetchall()

    def get_answered_messages(self):
        with self.conn:
            return self.conn.execute("SELECT id, username, question, answer FROM messages WHERE answered = 1").fetchall()

    def get_user_messages(self, username):
        with self.conn:
            return self.conn.execute("SELECT question, answer FROM messages WHERE username=?", (username,)).fetchall()

    def get_message_by_id(self, question_id):
        with self.conn:
            return self.conn.execute("SELECT user_id, username, question FROM messages WHERE id=?", (question_id,)).fetchone()

    def update_message_answer(self, question_id, answer):
        with self.conn:
            self.conn.execute("UPDATE messages SET answer=?, answered=1 WHERE id=?", (answer, question_id))

    def close(self):
        self.conn.close()


class TelegramBot:
    def __init__(self, token, admin_id, db):
        self.token = token
        self.admin_id = admin_id
        self.db = db
        self.user_states = {}
        self.base_url = f"https://api.telegram.org/bot{token}"

    def send_message(self, chat_id, text):
        data = {'chat_id': chat_id, 'text': text}
        requests.post(f"{self.base_url}/sendMessage", data=data)

    def get_updates(self, offset):
        params = {'offset': offset}
        return requests.get(f"{self.base_url}/getUpdates", params=params).json()

    def parse_question_id(self, chat_id, text):
        try:
            if text.startswith("/answer_"):
                question_id = int(text.split("_")[1])
            else:
                question_id = int(text)

            message = self.db.get_message_by_id(question_id)
            if message:
                return question_id, message
            else:
                self.send_message(chat_id, "Вопрос с таким ID не найден.")
                return None, None

        except (ValueError, IndexError):
            self.send_message(chat_id, "Пожалуйста, введите корректный числовой ID.")
            return None, None

    def handle_admin_message(self, chat_id, text):
        if text == "/start":
            self.send_message(chat_id, "Добро пожаловать, Вы - администратор. Вы можете использовать команды:\n/see_questions - посмотреть вопросы\n/answer - ответить на вопрос\n/see_answers - посмотреть Ваши ответы.")
        elif text == "/see_questions":
            messages = self.db.get_pending_messages()
            if not messages:
                self.send_message(chat_id, "Нет новых вопросов.")
            else:
                self.send_messages_list(chat_id, messages, "answer")
        elif text == "/see_answers":
            messages = self.db.get_answered_messages()
            if not messages:
                self.send_message(chat_id, "Нет отвеченных вопросов.")
            else:
                self.send_answered_list(chat_id, messages)
        elif text == "/answer":
            self.user_states[chat_id] = "awaiting_question_id"
            self.send_message(chat_id, "Пожалуйста, укажите ID вопроса, на который хотите ответить.")
        elif self.user_states.get(chat_id) == "awaiting_question_id" or text.startswith("/answer_"):
            question_id, message = self.parse_question_id(chat_id, text)
            if question_id:
                self.user_states[chat_id] = f"answering_{question_id}"
                self.send_message(chat_id, "Пожалуйста, введите сообщение для отправки пользователю.")
        elif self.user_states.get(chat_id, "").startswith("answering_"):
            question_id = int(self.user_states[chat_id].split("_")[1])
            self.db.update_message_answer(question_id, text)
            message = self.db.get_message_by_id(question_id)
            self.send_answer_to_user(message[0], message[2], text)
            self.send_message(chat_id, "Сообщение отправлено пользователю.")
            self.user_states[chat_id] = ""
        else:
            self.send_message(chat_id, "Неизвестная команда.\nДоступные команды:\n/see_questions\n/see_answers\n/answer")

    def handle_user_message(self, chat_id, username, text):
        if text == "/start":
            self.send_message(chat_id, "Здравствуйте! Вы можете использовать команды:\n/contact - связаться с администратором\n/see_questions - посмотреть на ваши вопросы.")
        elif text == "/contact":
            self.user_states[chat_id] = "awaiting_message"
            self.send_message(chat_id, "Напишите мне сообщение, которое нужно отправить администратору.")
        elif text == "/see_questions":
            messages = self.db.get_user_messages(username)
            self.send_user_messages_list(chat_id, messages)
        elif self.user_states.get(chat_id) == "awaiting_message":
            message_id = self.db.save_message(chat_id, username, text)
            self.notify_admin(username, text, message_id)
            self.send_message(chat_id, "Ваше сообщение отправлено администратору.")
            self.user_states[chat_id] = ""
        else:
            self.send_message(chat_id, "Неизвестная команда. Вы можете использовать команды:\n/contact - связаться с администратором\n/see_questions - посмотреть на ваши вопросы.")

    def send_messages_list(self, chat_id, messages, command_prefix):
        response = ""
        for msg in messages:
            response += f"ID: {msg[0]}\nПользователь: {msg[1]}\nСообщение: {msg[2]}\nОтветить: /{command_prefix}_{msg[0]}\n\n"
        self.send_message(chat_id, response)

    def send_answered_list(self, chat_id, messages):
        response = ""
        for msg in messages:
            response += f"ID: {msg[0]}\nПользователь: {msg[1]}\nВопрос:\n{msg[2]}\nОтвет:\n{msg[3]}\n\n"
        self.send_message(chat_id, response)

    def send_user_messages_list(self, chat_id, messages):
        if messages:
            response = "Ваши вопросы\n\n"
            for msg in messages:
                response += f"Вопрос:\n{msg[0]}\nОтвет:\n{msg[1]}\n\n"
        else:
            response = "У Вас нет вопросов."
        self.send_message(chat_id, response)

    def send_answer_to_user(self, user_id, question, answer):
        response = f"Вы получили новый ответ!\nВаш вопрос:\n{question}\nОтвет администратора:\n{answer}\n"
        self.send_message(user_id, response)

    def notify_admin(self, username, message, question_id):
        admin_msg = f"Новый вопрос\nОт: @{username}\nВопрос:\n{message}\nОтветить: /answer_{question_id}"
        self.send_message(ADMIN_ID, admin_msg)


def shutdown_handler(signum, frame):
    db.close()
    sys.exit(0)

signal.signal(signal.SIGINT, shutdown_handler)
signal.signal(signal.SIGTERM, shutdown_handler)

if __name__ == "__main__":
    db = Database(DATABASE_PATH)
    bot = TelegramBot(TOKEN, ADMIN_ID, db)

    offset = 0
    try:
        while True:
            updates = bot.get_updates(offset)
            for update in updates.get('result', []):
                if 'message' in update:
                    message = update['message']
                    chat_id = message['chat']['id']
                    text = message.get('text')
                    username = message['from']['username']

                    if chat_id == ADMIN_ID:
                        bot.handle_admin_message(chat_id, text)
                    else:
                        bot.handle_user_message(chat_id, username, text)

                offset = update['update_id'] + 1
    except Exception as e:
        print(f"Ошибка: {e}")
    finally:
        db.close()
        print("Бот остановлен.")
