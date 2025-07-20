# Используем официальный образ Python
FROM python:3.13-slim

# Устанавливаем системные пакеты, включая build-essential для компиляции
RUN apt-get update && apt-get install -y build-essential

# Устанавливаем зависимости Python
COPY requirements.txt .
RUN pip install -r requirements.txt

# Копируем весь проект в контейнер
COPY . /app

# Указываем команду для запуска приложения
CMD ["python", "app.py"]
