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
    unique_suffix = uuid.uuid4().hex[:6]
    return f"{name}_{unique_suffix}{ext}"

@app.route('/')
def home():
    return '''
    <div style="display:flex; height:100vh; justify-content:center; align-items:center; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color:#eee; font-family:sans-serif; flex-direction:column;">
        <h1>Ты на главной!</h1>
        <p>Ничего лишнего.</p>
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
        # Страница, когда файл удалён или не найден — с таким же фоном, как на главной
        return render_template_string('''
            <div style="font-family:sans-serif; text-align:center; padding:50px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; height: 100vh; display: flex; flex-direction: column; justify-content: center; align-items: center;">
                <h2>Файл удалён или не найден</h2>
                <p>Этот файл был скачан и удалён, или не существует.</p>
                <a href="/" style="color:#fff; text-decoration: underline; font-weight: bold;">Вернуться на главную</a>
            </div>
        '''), 404

    if is_expired(filepath):
        os.remove(filepath)
        return render_template_string('''
            <div style="font-family:sans-serif; text-align:center; padding:50px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; height: 100vh; display: flex; flex-direction: column; justify-content: center; align-items: center;">
                <h2>Файл удалён или не найден</h2>
                <p>Срок хранения файла истёк, и он был удалён.</p>
                <a href="/" style="color:#fff; text-decoration: underline; font-weight: bold;">Вернуться на главную</a>
            </div>
        '''), 404

    html_template = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Файл для скачивания</title>
        <style>
            body {
                font-family: sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                text-align: center;
                padding: 50px;
                height: 100vh;
                display: flex;
                justify-content: center;
                align-items: center;
                margin: 0;
            }
            .container {
                background: rgba(255, 255, 255, 0.15);
                padding: 30px;
                border-radius: 12px;
                box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.37);
                backdrop-filter: blur(8.5px);
                -webkit-backdrop-filter: blur(8.5px);
                border: 1px solid rgba(255, 255, 255, 0.18);
                width: 300px;
            }
            button {
                padding: 12px 25px;
                margin: 10px;
                font-size: 16px;
                border: none;
                border-radius: 5px;
                cursor: pointer;
                transition: background-color 0.3s ease;
            }
            .download-btn {
                background-color: #4CAF50;
                color: white;
            }
            .download-btn:hover {
                background-color: #45a049;
            }
            .decline-btn {
                background-color: #f44336;
                color: white;
            }
            .decline-btn:hover {
                background-color: #da190b;
            }
            .note {
                margin-top: 15px;
                color: #ddd;
                font-style: italic;
                font-size: 14px;
            }
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
            <button class="decline-btn" onclick="decline()">Отмена</button>
            <p class="note">Автоудаление файла после загрузки.</p>
        </div>
    </body>
    </html>
    '''

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
        return "Доступ запрещён", 403

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
        <h2>Загруженные файлы</h2>
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
        return "Неверный пароль", 403

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
        return "Неверный пароль", 403

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
