from flask import Flask, request, send_from_directory, jsonify, render_template_string, redirect, url_for, abort, after_this_request, Response
import os
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import uuid
from functools import wraps

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Админ данные для Basic Auth
ADMIN_USERNAME = "admin"
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
    unique_id = uuid.uuid4().hex[:8]
    return f"{name}_{unique_id}{ext}"

# --- Basic Auth функции ---
def check_auth(username, password):
    return username == ADMIN_USERNAME and password == ADMIN_PASSWORD

def authenticate():
    return Response(
        'Требуется авторизация', 401,
        {'WWW-Authenticate': 'Basic realm="Login Required"'}
    )

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated
# ---------------------------

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

@app.route('/list', methods=['GET'])
@requires_auth
def list_files():
    # Удаляем устаревшие файлы
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
            "delete_url": f"/delete/{f}"
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

        <a class="button delete-all" href="/delete_all" onclick="return confirm('Удалить все файлы?')">Удалить все</a>
    </body>
    </html>
    """
    return render_template_string(html_template, files=file_data)

@app.route('/delete/<filename>')
@requires_auth
def delete_file(filename):
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    if os.path.exists(filepath):
        os.remove(filepath)
        print(f"[ADMIN] Удалён файл: {filename}")
        return redirect(url_for('list_files'))
    return "Файл не найден", 404

@app.route('/delete_all')
@requires_auth
def delete_all_files():
    deleted = []
    for f in os.listdir(UPLOAD_FOLDER):
        path = os.path.join(UPLOAD_FOLDER, f)
        if os.path.isfile(path) and not f.startswith('.'):
            os.remove(path)
            deleted.append(f)

    print(f"[ADMIN] Удалены все файлы: {', '.join(deleted)}")
    return f"Удалено файлов: {len(deleted)}<br><a href='/list'>Назад</a>"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
