# tg-admin-bot-python

В данном боте есть 2 роли: администратор и пользователь

Цель бота: перенаправлять вопросы пользователей администратору и ответы администратора пользователям


## Команды
Доступные команды для пользователя:
- `/start` - Начать бота
- `/contact` - Написать вопрос администратору
- `/see_questions` - Посмотреть на вопросы и ответы


Доступные команды для администратора:
- `/start` - Начать бота
- `/see_questions` - Посмотреть на неотвеченные вопросы
- `/answer` - Позволяет ответить на вопрос
- `/see_answers` - Посмотреть на отвеченные вопросы


## Запуск:
- `git clone https://github.com/artem-streltsov/tg-admin-bot-python`
- `cd tg-admin-bot-python`
- внесите данные в `config.txt` файл, для примера смотреть `config.example`
- `python3 -m venv venv`
- `source venv/bin/activate`
- `pip install -r requirements.txt`
- `python3 app.py`
- Для остановки, нажмите `Ctrl+C` и выполните команду `deactivate`


## Описание
Программа использует `config.txt` файл для хранения токена для бота, chatID администратора, путь к базе данных, смотреть `config.example`.

База данных - `sqlite3`.
