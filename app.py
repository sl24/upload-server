from flask import Flask, request, send_from_directory, jsonify, render_template_string, redirect, url_for, after_this_request
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

COMMON_BG_STYLE = "background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; font-family: sans-serif; height: 100vh; display: flex; flex-direction: column; justify-content: center; align-items: center; margin: 0; padding: 20px;"

@app.route('/')
def home():
    return '''
    <div style="display:flex; height:100vh; justify-content:center; align-items:center; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color:#eee; font-family:sans-serif; flex-direction:column;">
        <h1>Main page</h1>
        <p>nothing extra</p>
        <p><a href="/upload_form" style="color:#eee; text-decoration: underline;">Upload file via browser</a></p>
    </div>
    '''

# --- API для загрузки файла (бот и другие клиенты) ---
@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return jsonify({"error": "File not found"}), 400

    file = request.files['file']
    original_filename = file.filename

    if not original_filename or not allowed_file(original_filename):
        return jsonify({"error": "Invalid file type"}), 400

    filename = generate_unique_filename(original_filename)
    filepath = os.path.join(UPLOAD_FOLDER, filename)

    try:
        file.save(filepath)
        print(f"[UPLOAD] File saved: {filename}")
    except Exception as e:
        print(f"[ERROR] Error while saving: {e}")
        return jsonify({"error": f"Error saving file: {str(e)}"}), 500

    base_url = request.url_root.rstrip('/')
    file_url = f"{base_url}/files/{filename}"

    # ВСЕГДА возвращаем JSON с url для скачивания
    return jsonify({"url": file_url})

# --- Веб-форма загрузки для браузера ---
@app.route('/upload_form', methods=['GET', 'POST'])
def upload_form():
    if request.method == 'POST':
        if 'file' not in request.files:
            return render_template_string(FORM_HTML, error="File not found")

        file = request.files['file']
        original_filename = file.filename

        if not original_filename or not allowed_file(original_filename):
            return render_template_string(FORM_HTML, error="Invalid file type")

        filename = generate_unique_filename(original_filename)
        filepath = os.path.join(UPLOAD_FOLDER, filename)

        try:
            file.save(filepath)
            print(f"[UPLOAD FORM] File saved: {filename}")
            base_url = request.url_root.rstrip('/')
            file_url = f"{base_url}/files/{filename}"
            return render_template_string(FORM_HTML, success=True, file_url=file_url)
        except Exception as e:
            print(f"[ERROR] Error while saving: {e}")
            return render_template_string(FORM_HTML, error=f"Error saving file: {str(e)}")

    return render_template_string(FORM_HTML)


FORM_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>Upload file</title>
    <style>
        body {
            {{ common_bg_style }}
            flex-direction: column;
            justify-content: flex-start;
            padding-top: 40px;
        }
        .container {
            background: rgba(255, 255, 255, 0.15);
            padding: 30px;
            border-radius: 12px;
            max-width: 40vw;
            width: 100%;
            box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.37);
            overflow: hidden;
            text-align: center;
            margin: 0 auto;
            color: white;
        }
        input[type="file"] {
            margin: 15px 0;
        }
        input[type="submit"] {
            padding: 12px 25px;
            font-size: 16px;
            border: none;
            border-radius: 5px;
            background-color: #4CAF50;
            color: white;
            cursor: pointer;
            transition: background-color 0.3s ease;
        }
        input[type="submit"]:hover {
            background-color: #45a049;
        }
        .message {
            margin-top: 20px;
            font-weight: bold;
        }
        a.link {
            color: #ffd700;
            text-decoration: underline;
            word-break: break-all;
        }
    </style>
</head>
<body>
    <div class="container">
        <h2>Upload file</h2>
        <form method="POST" enctype="multipart/form-data">
            <input type="file" name="file" required>
            <br>
            <input type="submit" value="Upload">
        </form>
        {% if error %}
        <p class="message" style="color: #f44336;">{{ error }}</p>
        {% endif %}
        {% if success %}
        <p class="message">File uploaded successfully!</p>
        <p>Download link:<br><a class="link" href="{{ file_url }}" target="_blank">{{ file_url }}</a></p>
        {% endif %}
        <p><a href="/" style="color:#fff; text-decoration: underline;">Back to home</a></p>
    </div>
</body>
</html>
'''

@app.route('/files/<filename>')
def serve_file(filename):
    filepath = os.path.join(UPLOAD_FOLDER, filename)

    if not os.path.exists(filepath) or not allowed_file(filename):
        return render_template_string('''
            <div style="{{ common_bg_style }}">
                <h2>File deleted or not found</h2>
                <p>This file has been downloaded and deleted, or does not exist.</p>
                <a href="/" style="color:#fff; text-decoration: underline; font-weight: bold;">Return to home page</a>
            </div>
        ''', common_bg_style=COMMON_BG_STYLE), 404

    if is_expired(filepath):
        os.remove(filepath)
        return render_template_string('''
            <div style="{{ common_bg_style }}">
                <h2>File deleted or not found</h2>
                <p>The file has expired and has been deleted.</p>
                <a href="/" style="color:#fff; text-decoration: underline; font-weight: bold;">Return to home page</a>
            </div>
        ''', common_bg_style=COMMON_BG_STYLE), 404

    if request.args.get("show_downloaded") == "1":
        return render_template_string('''
            <div style="{{ common_bg_style }}">
                <h2>File downloaded and deleted</h2>
                <p>Thank you! The file was successfully downloaded.</p>
                <a href="/" style="color:#fff; text-decoration: underline; font-weight: bold;">Return to home page</a>
            </div>
        ''', common_bg_style=COMMON_BG_STYLE)

    html_template = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>File for download</title>
        <style>
            body {
                {{ common_bg_style }}
                padding-top: 40px;
                align-items: center;
                justify-content: flex-start;
            }
            .container {
                background: rgba(255, 255, 255, 0.15);
                padding: 30px;
                border-radius: 12px;
                max-width: 50vw;
                width: 100%;
                box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.37);
                overflow: hidden;
                text-align: center;
                margin: 0 auto;
            }
            .filename {
                overflow: hidden;
                text-overflow: ellipsis;
                white-space: nowrap;
                font-weight: bold;
                font-size: 18px;
                margin-bottom: 20px;
                display: block;
            }
            button {
                padding: 12px 25px;
                margin: 10px 10px 10px 0;
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
                var iframe = document.createElement('iframe');
                iframe.style.display = 'none';
                iframe.src = '/files/{{ filename }}?download=1';
                document.body.appendChild(iframe);

                setTimeout(function() {
                    window.location.href = '/files/{{ filename }}?show_downloaded=1';
                }, 3000);
            }
            function decline() {
                window.location.href = '/';
            }
        </script>
    </head>
    <body>
        <div class="container">
            <span class="filename" title="{{ filename }}">{{ filename }}</span>
            <button class="download-btn" onclick="downloadFile()">Download</button>
            <button class="decline-btn" onclick="decline()">Cancel</button>
            <p class="note">Auto delete file after download.</p>
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
                    print(f"[INFO] File deleted after downloading: {filename}")
            except Exception as e:
                print(f"[ERROR] Error deleting after downloading: {e}")
            return response

        return send_from_directory(
            UPLOAD_FOLDER,
            filename,
            as_attachment=True,
            download_name=filename
        )

    return render_template_string(html_template, filename=filename, common_bg_style=COMMON_BG_STYLE)


@app.route('/list', methods=['GET'])
def list_files():
    password = request.args.get("password", "")
    if password != ADMIN_PASSWORD:
        return "Access Denied", 403

    # Удаляем просроченные файлы
    for f in os.listdir(UPLOAD_FOLDER):
        path = os.path.join(UPLOAD_FOLDER, f)
        if os.path.isfile(path) and is_expired(path):
            os.remove(path)

    files = [f for f in os.listdir(UPLOAD_FOLDER)
             if os.path.isfile(os.path.join(UPLOAD_FOLDER, f)) and not f.startswith('.')]

    base_url = request.url_root.rstrip('/')
    file_data = [
        {
            "name": f,
            "url": f"{base_url}/files/{f}",
            "delete_url": f"/delete/{f}?password={password}"
        }
        for f in files
    ]

    html_template = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Files</title>
        <style>
            body { font-family: sans-serif; padding: 20px; }
            table { border-collapse: collapse; width: 100%; }
            th, td { padding: 8px; border: 1px solid #ddd; max-width: 300px; }
            th { background-color: #f2f2f2; }
            a.button { padding: 4px 10px; background: #f44336; color: white; text-decoration: none; border-radius: 4px; }
            a.delete-all { margin-top: 15px; display: inline-block; background: #e91e63; }
            td.filename-cell {
                max-width: 400px;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
            }
        </style>
    </head>
    <body>
        <h2>Uploaded files</h2>
        {% if files %}
        <table>
            <tr>
                <th>Name</th>
                <th>Download</th>
                <th>Delete</th>
            </tr>
            {% for file in files %}
            <tr>
                <td class="filename-cell" title="{{ file.name }}">{{ file.name }}</td>
                <td><a href="{{ file.url }}" target="_blank">Download</a></td>
                <td><a class="button" href="{{ file.delete_url }}" onclick="return confirm('Delete {{ file.name }}?')">Delete</a></td>
            </tr>
            {% endfor %}
        </table>
        {% else %}
        <p>No files.</p>
        {% endif %}

        <a class="button delete-all" href="/delete_all?password={{ password }}" onclick="return confirm('Delete all files?')">Delete all</a>
    </body>
    </html>
    '''
    return render_template_string(html_template, files=file_data, password=password)

@app.route('/delete/<filename>')
def delete_file(filename):
    password = request.args.get("password", "")
    if password != ADMIN_PASSWORD:
        return "Wrong password", 403

    filepath = os.path.join(UPLOAD_FOLDER, filename)
    if os.path.exists(filepath):
        os.remove(filepath)
        print(f"[ADMIN] File deleted: {filename}")
        return redirect(url_for('list_files', password=password))
    return render_template_string('''
        <div style="{{ common_bg_style }}">
            <h2>File not found</h2>
            <p>Unable to delete: file not found.</p>
            <a href="/list?password={{ password }}" style="color:#fff; text-decoration: underline; font-weight: bold;">Back to file list</a>
        </div>
    ''', common_bg_style=COMMON_BG_STYLE, password=password), 404

@app.route('/delete_all')
def delete_all_files():
    password = request.args.get("password", "")
    if password != ADMIN_PASSWORD:
        return "Wrong password", 403

    deleted = []
    for f in os.listdir(UPLOAD_FOLDER):
        path = os.path.join(UPLOAD_FOLDER, f)
        if os.path.isfile(path) and not f.startswith('.'):
            os.remove(path)
            deleted.append(f)

    print(f"[ADMIN] All files have been deleted: {', '.join(deleted)}")
    return render_template_string('''
        <div style="{{ common_bg_style }}">
            <h2>Files removed: {{ count }}</h2>
            <a href="/list?password={{ password }}" style="color:#fff; text-decoration: underline; font-weight: bold;">Back to file list</a>
        </div>
    ''', common_bg_style=COMMON_BG_STYLE, count=len(deleted), password=password)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
