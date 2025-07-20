import os
import aiohttp
import zipfile
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

UPLOAD_SERVER_URL = "https://upload-server-1.onrender.com/upload"

app = Client("my_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB per file

# Хранилище временных данных по media_group_id
media_groups = {}  # media_group_id: {"messages": [...], "timer": task}

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)


async def upload_to_server(file_path: str) -> str:
    try:
        async with aiohttp.ClientSession() as session:
            with open(file_path, "rb") as f:
                data = aiohttp.FormData()
                data.add_field('file', f, filename=os.path.basename(file_path))
                async with session.post(UPLOAD_SERVER_URL, data=data) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        url = result.get("url")
                        if url:
                            return url
                        else:
                            return "Ошибка: ссылка не получена"
                    else:
                        return f"Ошибка загрузки: HTTP {resp.status}"
    except Exception as e:
        return f"Ошибка: {str(e)}"


def get_file_size(message: Message):
    if message.document:
        return message.document.file_size
    elif message.video:
        return message.video.file_size
    elif message.animation:
        return message.animation.file_size
    elif message.photo:
        # Фото — размер самого большого фото
        # Но тут message.photo — объект Photo, не список, исправлено ниже
        return message.photo.file_size
    return None


async def process_media_group(media_group_id):
    data = media_groups.pop(media_group_id, None)
    if not data:
        return

    messages = data["messages"]

    # Проверяем размер каждого файла
    for m in messages:
        size = get_file_size(m)
        if size and size > MAX_FILE_SIZE:
            await messages[0].reply(f"❌ Один из файлов слишком большой (>5 МБ): {m.document.file_name if m.document else 'файл'}")
            return

    # Отправляем первое сообщение и начинаем редактировать его
    reply_msg = await messages[0].reply("Скачиваю файлы и упаковываю в архив...")

    temp_dir = os.path.join(DOWNLOAD_DIR, f"temp_{media_group_id}")
    os.makedirs(temp_dir, exist_ok=True)

    filenames = []
    for m in messages:
        filename = None
        if m.document:
            filename = m.document.file_name
        elif m.video:
            filename = f"{m.video.file_id}.mp4"
        elif m.animation:
            filename = f"{m.animation.file_id}.gif"
        elif m.photo:
            filename = f"{m.photo.file_id}.jpg"

        file_path = await m.download(file_name=os.path.join(temp_dir, filename or "file"))
        filenames.append(file_path)

    zip_filename = f"archive_{media_group_id}.zip"
    zip_path = os.path.join(DOWNLOAD_DIR, zip_filename)

    with zipfile.ZipFile(zip_path, 'w') as zipf:
        for file in filenames:
            zipf.write(file, arcname=os.path.basename(file))

    # Удаляем временные скачанные файлы
    for file in filenames:
        if os.path.exists(file):
            os.remove(file)
    if os.path.exists(temp_dir):
        os.rmdir(temp_dir)

    # Редактируем сообщение
    await reply_msg.edit("Загружаю архив на сервер...")

    link = await upload_to_server(zip_path)

    # Редактируем сообщение и отправляем ссылку
    await reply_msg.edit(f"Ссылка на скачивание архива:\n{link}")

    if os.path.exists(zip_path):
        os.remove(zip_path)


@ app.on_message(filters.media)
async def handle_files(client: Client, message: Message):
    media_group_id = message.media_group_id

    if media_group_id:
        # Сохраняем сообщение в хранилище по media_group_id
        if media_group_id not in media_groups:
            media_groups[media_group_id] = {"messages": [], "timer": None}

        media_groups[media_group_id]["messages"].append(message)

        # Отменяем предыдущий таймер, если есть
        timer = media_groups[media_group_id]["timer"]
        if timer:
            timer.cancel()

        # Запускаем новый таймер (3 секунды) для обработки всей группы
        media_groups[media_group_id]["timer"] = asyncio.create_task(
            delayed_process(media_group_id)
        )

    else:
        # Обработка одиночных файлов
        size = get_file_size(message)
        if size and size > MAX_FILE_SIZE:
            await message.reply("❌ Файл слишком большой. Максимум 5 МБ.")
            return

        # Отправляем первое сообщение
        reply_msg = await message.reply("Скачиваю файл...")

        file_name = None
        if message.document:
            file_name = message.document.file_name
        elif message.video:
            file_name = f"{message.video.file_id}.mp4"
        elif message.animation:
            file_name = f"{message.animation.file_id}.gif"
        elif message.photo:
            file_name = f"{message.photo.file_id}.jpg"

        file_path = await message.download(file_name=os.path.join(DOWNLOAD_DIR, file_name or "file"))

        # Редактируем сообщение
        await reply_msg.edit("Загружаю файл на сервер...")

        link = await upload_to_server(file_path)

        # Редактируем сообщение и отправляем ссылку
        await reply_msg.edit(f"Ссылка на скачивание:\n{link}")

        if os.path.exists(file_path):
            os.remove(file_path)


async def delayed_process(media_group_id):
    await asyncio.sleep(3)  # Ждем 3 секунды, чтобы собрать все файлы
    await process_media_group(media_group_id)


if __name__ == "__main__":
    print("Бот запускается...")
    app.run()
