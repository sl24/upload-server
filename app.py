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
DELETE_AFTER_DOWNLOAD = True  # если True — файл удаляется сразу после скачивания

def is_expired(file_path):
    file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
    return datetime.now() - file_mtime > timedelta(days=DELETE_AFTER_DAYS)

def generate_unique_filename(original_filename):
    # Сохраняем расширение
    name, ext = os.path.splitext(secure_filename(original_filename))
    # Добавляем дату и уникальный UUID4 (короткий)
    unique_id = uuid.uuid4().hex[:8]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    new_name = f"{name}_{timestamp}_{unique_id}{ext}"
    return new_name

@app.route('/')
def home():
    return "Файлообменник на Render работает!"

@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return jsonify({"error": "Файл не найден"}), 400

    file = request.files['file']
    original_filename = file.filename

    if not original_filename:
        return jsonify({"error": "Некорректное имя файла"}), 400

    filename = generate_unique_filename(original_filename)
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    file.save(filepath)

    base_url = "https://" + request.host
    return jsonify({"url": f"{base_url}/files/{filename}"})


@app.route('/files/<filename>')
def serve_file(filename):
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    if not os.path.exists(filepath):
        abort(404)

    if is_expired(filepath):
        os.remove(filepath)
        abort(404)

    @after_this_request
    def remove_file(response):
        try:
            if DELETE_AFTER_DOWNLOAD and os.path.exists(filepath):
                os.remove(filepath)
        except Exception as e:
            print(f"Ошибка удаления файла: {e}")
        return response

    return send_from_directory(
        UPLOAD_FOLDER,
        filename,
        as_attachment=True,
        download_name=filename
    )


@app.route('/list', methods=['GET'])
def list_files():
    password = request.args.get("password", "")
    if password != ADMIN_PASSWORD:
        return "🔒 Доступ запрещён. Укажи параметр ?password=admin123", 403

    # Удаляем просроченные файлы при списке
    for f in os.listdir(UPLOAD_FOLDER):
        file_path = os.path.join(UPLOAD_FOLDER, f)
        if os.path.isfile(file_path) and f[0] != '.':
            if is_expired(file_path):
                os.remove(file_path)

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
        <title>Загруженные файлы</title>
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
                <th>Имя файла</th>
                <th>Ссылка</th>
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
        <p>Нет загруженных файлов.</p>
        {% endif %}

        <a class="button delete-all" href="/delete_all?password={{ password }}" onclick="return confirm('Удалить все файлы?')">Удалить все</a>
    </body>
    </html>
    """
    return render_template_string(html_template, files=file_data, password=password)


@app.route('/delete/<filename>', methods=['GET'])
def delete_file(filename):
    password = request.args.get("password", "")
    if password != ADMIN_PASSWORD:
        return "🔒 Неверный пароль", 403

    filepath = os.path.join(UPLOAD_FOLDER, filename)
    if os.path.exists(filepath):
        os.remove(filepath)
        return redirect(url_for('list_files', password=password))
    else:
        return f"Файл {filename} не найден", 404

@app.route('/delete_all', methods=['GET'])
def delete_all_files():
    password = request.args.get("password", "")
    if password != ADMIN_PASSWORD:
        return "🔒 Неверный пароль", 403

    deleted_files = []
    for f in os.listdir(UPLOAD_FOLDER):
        file_path = os.path.join(UPLOAD_FOLDER, f)
        if os.path.isfile(file_path) and not f.startswith('.'):
            os.remove(file_path)
            deleted_files.append(f)

    return f"Удалены файлы: {', '.join(deleted_files)}<br><a href='/list?password={password}'>Вернуться к списку файлов</a>"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
