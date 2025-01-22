FROM python:3.10

EXPOSE 5000
COPY app app
COPY requirements.txt requirements.txt
RUN apt-get update && apt-get install -y curl ffmpeg
RUN python -m pip install --upgrade pip
RUN pip install torch==2.4.1 --index-url https://download.pytorch.org/whl/cpu --no-input
RUN pip install -r requirements.txt
RUN chown -R 1000:1000 /app
RUN chmod -R 700 /app
WORKDIR /app

ENTRYPOINT ["python", "./app.py"]