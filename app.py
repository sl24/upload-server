from flask import Flask, request, send_from_directory, jsonify, render_template_string, redirect, url_for, abort, after_this_request
import os
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import uuid

app = Flask(__name__)

app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5 MB

@app.errorhandler(413)
def request_entity_too_large(error):
    return jsonify({"error": "Файл слишком большой. Лимит — 5MB."}), 413

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

ADMIN_PASSWORD = "admin123"
DELETE_AFTER_DAYS = 7
DELETE_AFTER_DOWNLOAD = False

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'mp3', 'pdf', 'txt', 'zip', 'rar', 'docx', 'py'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def is_expired(file_path):
    file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
    return datetime.now() - file_mtime > timedelta(days=DELETE_AFTER_DAYS)

def generate_unique_filename(original_filename):
    name, ext = os.path.splitext(secure_filename(original_filename))
    unique_id = uuid.uuid4().hex[:8]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{name}_{timestamp}_{unique_id}{ext}"

def get_today_folder():
    today_str = datetime.now().strftime("%Y-%m-%d")
    folder_path = os.path.join(UPLOAD_FOLDER, today_str)
    os.makedirs(folder_path, exist_ok=True)
    return folder_path

@app.route('/')
def home():
    return "🚀 Файлообменник на Render работает!"

@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return jsonify({"error": "Файл не найден"}), 400

    file = request.files['file']
    original_filename = file.filename

    if not original_filename or not allowed_file(original_filename):
        return jsonify({"error": "Недопустимый тип файла"}), 400

    filename = generate_unique_filename(original_filename)
    today_folder = get_today_folder()
    filepath = os.path.join(today_folder, filename)

    try:
        file.save(filepath)
        print(f"[UPLOAD] Сохранён файл: {filename} в папке {today_folder}")
    except Exception as e:
        print(f"[ERROR] Ошибка при сохранении: {e}")
        return jsonify({"error": f"Ошибка сохранения файла: {str(e)}"}), 500

    base_url = "https://" + request.host
    # Ссылка с датой папкой в пути
    relative_path = os.path.relpath(filepath, UPLOAD_FOLDER).replace("\\", "/")
    return jsonify({"url": f"{base_url}/files/{relative_path}"})


@app.route('/files/<path:filename>')
def serve_file(filename):
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    if not os.path.exists(filepath) or not allowed_file(filename):
        abort(404)

    if is_expired(filepath):
        os.remove(filepath)
        abort(404)

    @after_this_request
    def remove_file(response):
        try:
            if DELETE_AFTER_DOWNLOAD and os.path.exists(filepath):
                os.remove(filepath)
                print(f"[INFO] Удалён файл после скачивания: {filename}")
        except Exception as e:
            print(f"[ERROR] Ошибка удаления после скачивания: {e}")
        return response

    directory = os.path.dirname(filepath)
    fname = os.path.basename(filepath)
    return send_from_directory(
        directory,
        fname,
        as_attachment=True,
        download_name=fname
    )


@app.route('/list', methods=['GET'])
def list_files():
    password = request.args.get("password", "")
    if password != ADMIN_PASSWORD:
        return "🔒 Доступ запрещён. Укажи параметр ?password=admin123", 403

    # Чистим просроченные файлы по всем датам
    for date_folder in os.listdir(UPLOAD_FOLDER):
        folder_path = os.path.join(UPLOAD_FOLDER, date_folder)
        if os.path.isdir(folder_path):
            for f in os.listdir(folder_path):
                path = os.path.join(folder_path, f)
                if os.path.isfile(path) and is_expired(path):
                    os.remove(path)

    # Собираем все файлы со всеми подпапками
    files = []
    for date_folder in sorted(os.listdir(UPLOAD_FOLDER), reverse=True):
        folder_path = os.path.join(UPLOAD_FOLDER, date_folder)
        if os.path.isdir(folder_path):
            for f in os.listdir(folder_path):
                if not f.startswith('.'):
                    files.append({
                        "name": f,
                        "date_folder": date_folder,
                        "url": f"https://{request.host}/files/{date_folder}/{f}",
                        "delete_url": f"/delete/{date_folder}/{f}?password={password}"
                    })

    html_template = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Файлы</title>
        <style>
            body { font-family: sans-serif; padding: 20px; }
            table { border-collapse: collapse; width: 100%; }
            th, td { padding: 8px; border: 1px solid #ddd; }
            th { background-color: #f2f2f2; }
            a.button { padding: 4px 10px; background: #f44336; color: white; text-decoration: none; border-radius: 4px; }
            a.delete-all { margin-top: 15px; display: inline-block; background: #e91e63; }
        </style>
    </head>
    <body>
        <h2>📁 Загруженные файлы</h2>
        {% if files %}
        <table>
            <tr>
                <th>Дата</th>
                <th>Имя</th>
                <th>Скачать</th>
                <th>Удалить</th>
            </tr>
            {% for file in files %}
            <tr>
                <td>{{ file.date_folder }}</td>
                <td>{{ file.name }}</td>
                <td><a href="{{ file.url }}" target="_blank">Скачать</a></td>
                <td><a class="button" href="{{ file.delete_url }}" onclick="return confirm('Удалить {{ file.name }}?')">Удалить</a></td>
            </tr>
            {% endfor %}
        </table>
        {% else %}
        <p>Нет файлов.</p>
        {% endif %}

        <a class="button delete-all" href="/delete_all?password={{ password }}" onclick="return confirm('Удалить все файлы?')">Удалить все</a>
    </body>
    </html>
    """
    return render_template_string(html_template, files=files, password=password)


@app.route('/delete/<date_folder>/<filename>')
def delete_file(date_folder, filename):
    password = request.args.get("password", "")
    if password != ADMIN_PASSWORD:
        return "🔒 Неверный пароль", 403

    filepath = os.path.join(UPLOAD_FOLDER, date_folder, filename)
    if os.path.exists(filepath):
        os.remove(filepath)
        print(f"[ADMIN] Удалён файл: {filename} из папки {date_folder}")
        return redirect(url_for('list_files', password=password))
    return "Файл не найден", 404


@app.route('/delete_all')
def delete_all_files():
    password = request.args.get("password", "")
    if password != ADMIN_PASSWORD:
        return "🔒 Неверный пароль", 403

    deleted = []
    for date_folder in os.listdir(UPLOAD_FOLDER):
        folder_path = os.path.join(UPLOAD_FOLDER, date_folder)
        if os.path.isdir(folder_path):
            for f in os.listdir(folder_path):
                path = os.path.join(folder_path, f)
                if os.path.isfile(path) and not f.startswith('.'):
                    os.remove(path)
                    deleted.append(f)

    print(f"[ADMIN] Удалены все файлы: {', '.join(deleted)}")
    return f"Удалено файлов: {len(deleted)}<br><a href='/list?password={password}'>Назад</a>"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
