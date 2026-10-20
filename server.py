import asyncio
import json
import logging
import aiohttp
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import WebAppInfo, ReplyKeyboardBuilder

# --- НАСТРОЙКИ ---
BOT_TOKEN = "8994293061:AAFdpgoYjIRXOdHRdw897I7vPSX17Cf7UgQ"
WEB_APP_URL = "https://твой-сайт.ру" # Сюда потом вставим ссылку на твой сервер
BASE_URL = "https://asurso.ru"
# -----------------

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Хранилище сессий (в реальном проекте используй БД)
# Ключ: telegram_id, Значение: {'cookies': {...}, 'at': '...'}
user_sessions = {}

# --- ВЕБ-СЕРВЕР (ПРОКСИ) ---
async def handle_request(request: web.Request):
    """Принимает запросы от Mini App и проксирует их в АСУ РСО."""
    try:
        telegram_id = int(request.headers.get('X-Telegram-Id', 0))
        if not telegram_id:
            return web.json_response({'error': 'No Telegram ID'}, status=400)

        path = request.match_info.get('path', '')
        target_url = f"{BASE_URL}/{path}"
        
        # Получаем сессию пользователя
        session = user_sessions.get(telegram_id, {})
        cookies = session.get('cookies', {})

        async with aiohttp.ClientSession(cookies=cookies) as http_session:
            async with http_session.get(target_url, headers={
                'Accept': 'application/json',
                'User-Agent': 'Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36'
            }) as resp:
                # Сохраняем новые куки, если они пришли
                new_cookies = {c.key: c.value for c in http_session.cookie_jar}
                if new_cookies:
                    user_sessions[telegram_id] = {'cookies': new_cookies, 'at': ''}
                
                data = await resp.json()
                return web.json_response(data)
    except Exception as e:
        logging.error(f"Proxy error: {e}")
        return web.json_response({'error': str(e)}, status=500)

# --- TELEGRAM БОТ ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    builder = ReplyKeyboardBuilder()
    builder.button(text="🚀 Открыть дневник", web_app=WebAppInfo(url=WEB_APP_URL))
    await message.answer(
        "Привет! Нажми кнопку, чтобы открыть дневник. "
        "Вход произойдет автоматически.",
        reply_markup=builder.as_markup(resize_keyboard=True)
    )

# --- ЗАПУСК ---
async def main():
    # Настраиваем веб-сервер
    app = web.Application()
    app.router.add_get('/proxy/{path:.*}', handle_request)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8080) # Порт 8080
    await site.start()
    
    logging.info("Сервер запущен на порту 8080")
    
    # Запускаем бота
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())