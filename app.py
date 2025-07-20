from flask import Flask, request, send_from_directory, jsonify, render_template_string, redirect, url_for, abort, after_this_request
import os
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import uuid

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

ADMIN_PASSWORD = "admin123"
DELETE_AFTER_DAYS = 7
DELETE_AFTER_DOWNLOAD = True

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'mp3', 'pdf', 'txt', 'zip', 'rar', 'docx'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def is_expired(file_path):
    file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
    return datetime.now() - file_mtime > timedelta(days=DELETE_AFTER_DAYS)

def generate_unique_filename(original_filename):
    name, ext = os.path.splitext(secure_filename(original_filename))
    unique_suffix = uuid.uuid4().hex[:6]  # короткий уникальный суффикс
    return f"{name}_{unique_suffix}{ext}"

@app.route('/')
def home():
    return '''
    <div style="display:flex; height:100vh; justify-content:center; align-items:center; background:#222; color:#eee; font-family:sans-serif; flex-direction:column;">
        <h1>🚀 Файлообменник на Render работает!</h1>
        <p>Загружай файлы и делись ссылками.</p>
    </div>
    '''

@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return jsonify({"error": "Файл не найден"}), 400

    file = request.files['file']
    original_filename = file.filename

    if not original_filename or not allowed_file(original_filename):
        return jsonify({"error": "Недопустимый тип файла"}), 400

    filename = generate_unique_filename(original_filename)
    filepath = os.path.join(UPLOAD_FOLDER, filename)

    try:
        file.save(filepath)
        print(f"[UPLOAD] Сохранён файл: {filename}")
    except Exception as e:
        print(f"[ERROR] Ошибка при сохранении: {e}")
        return jsonify({"error": f"Ошибка сохранения файла: {str(e)}"}), 500

    base_url = "https://" + request.host
    return jsonify({"url": f"{base_url}/files/{filename}"})


@app.route('/files/<filename>')
def serve_file(filename):
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    if not os.path.exists(filepath) or not allowed_file(filename):
        abort(404)

    if is_expired(filepath):
        os.remove(filepath)
        abort(404)

    html_template = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Файл для скачивания</title>
        <style>
            body { font-family: sans-serif; background: #f9f9f9; text-align: center; padding: 50px; }
            .container { background: white; padding: 30px; border-radius: 8px; box-shadow: 0 0 10px rgba(0,0,0,0.1); display: inline-block; }
            button { padding: 10px 20px; margin: 10px; font-size: 16px; border: none; border-radius: 5px; cursor: pointer; }
            .download-btn { background-color: #4CAF50; color: white; }
            .decline-btn { background-color: #f44336; color: white; }
        </style>
        <script>
            function downloadFile() {
                window.location.href = '/files/{{ filename }}?download=1';
            }
            function decline() {
                window.location.href = '/';
            }
        </script>
    </head>
    <body>
        <div class="container">
            <h2>Ваш файл готов к скачиванию:</h2>
            <p><strong>{{ filename }}</strong></p>
            <button class="download-btn" onclick="downloadFile()">Скачать</button>
            <button class="decline-btn" onclick="decline()">Отказаться</button>
        </div>
    </body>
    </html>
    '''

    # Если есть параметр download=1, сразу отдаем файл с заголовком скачивания
    if request.args.get("download") == "1":
        @after_this_request
        def remove_file(response):
            try:
                if DELETE_AFTER_DOWNLOAD and os.path.exists(filepath):
                    os.remove(filepath)
                    print(f"[INFO] Удалён файл после скачивания: {filename}")
            except Exception as e:
                print(f"[ERROR] Ошибка удаления после скачивания: {e}")
            return response

        return send_from_directory(
            UPLOAD_FOLDER,
            filename,
            as_attachment=True,
            download_name=filename
        )

    return render_template_string(html_template, filename=filename)


@app.route('/list', methods=['GET'])
def list_files():
    password = request.args.get("password", "")
    if password != ADMIN_PASSWORD:
        return "🔒 Доступ запрещён. Укажи параметр ?password=admin123", 403

    for f in os.listdir(UPLOAD_FOLDER):
        path = os.path.join(UPLOAD_FOLDER, f)
        if os.path.isfile(path) and is_expired(path):
            os.remove(path)

    files = [f for f in os.listdir(UPLOAD_FOLDER)
             if os.path.isfile(os.path.join(UPLOAD_FOLDER, f)) and not f.startswith('.')]

    base_url = "https://" + request.host
    file_data = [
        {
            "name": f,
            "url": f"{base_url}/files/{f}",
            "delete_url": f"/delete/{f}?password={password}"
        }
        for f in files
    ]

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
                <th>Имя</th>
                <th>Скачать</th>
                <th>Удалить</th>
            </tr>
            {% for file in files %}
            <tr>
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
    return render_template_string(html_template, files=file_data, password=password)


@app.route('/delete/<filename>')
def delete_file(filename):
    password = request.args.get("password", "")
    if password != ADMIN_PASSWORD:
        return "🔒 Неверный пароль", 403

    filepath = os.path.join(UPLOAD_FOLDER, filename)
    if os.path.exists(filepath):
        os.remove(filepath)
        print(f"[ADMIN] Удалён файл: {filename}")
        return redirect(url_for('list_files', password=password))
    return "Файл не найден", 404


@app.route('/delete_all')
def delete_all_files():
    password = request.args.get("password", "")
    if password != ADMIN_PASSWORD:
        return "🔒 Неверный пароль", 403

    deleted = []
    for f in os.listdir(UPLOAD_FOLDER):
        path = os.path.join(UPLOAD_FOLDER, f)
        if os.path.isfile(path) and not f.startswith('.'):
            os.remove(path)
            deleted.append(f)

    print(f"[ADMIN] Удалены все файлы: {', '.join(deleted)}")
    return f"Удалено файлов: {len(deleted)}<br><a href='/list?password={password}'>Назад</a>"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
