import datetime
import os
import tempfile
from flask import Flask, jsonify, request
from json import JSONEncoder
from concurrent.futures import ThreadPoolExecutor
import uuid
import socket
import jwt
import openai
import ffmpeg
import whisper
from pymongo import MongoClient
from bson import ObjectId
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.utils import secure_filename



app = Flask(__name__)
app.config['SECRET_KEY'] = 'incredibly_secret_jwt_key'
app.config['MAX_CONTENT_LENGTH'] = 1000 * 1024 * 1024 # 1000MB
openai.api_key = "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"

class MongoJSONEncoder(JSONEncoder):
    def default(self, obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        return super().default(obj)
app.json_encoder = MongoJSONEncoder

task_status = {}

try:
    uri = "mongodb://lectify-mongo-db:8ekyMVGjqKEZy5LIfvvmcBaEXJjS4cwSSxnX9zBOZquVk8dbt0v2JUZQTUoFh9Qjx1OnaQCoSSN0ACDbQ92lhw==@lectify-mongo-db.mongo.cosmos.azure.com:10255/?ssl=true&replicaSet=globaldb&retrywrites=false&maxIdleTimeMS=120000&appName=@lectify-mongo-db@"
    client = MongoClient(uri)
    database = client["lectify-mongo-db"]
    user_collection = database["user"]
    transcription_collection = database["transcription"]

except Exception as e:
    raise Exception("The following error occurred: ", e)

@app.route('/process', methods=['POST'])
def process():
    token = request.headers.get('Authorization').split(" ")[1]
    try:
        user_id = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])['_id']
        
        with tempfile.NamedTemporaryFile(delete=True, suffix=".mp3", dir='./temp') as temp_file:
            temp_file.write(request.data)
            temp_file_path = temp_file.name

            print("File saved to temporary file: ", temp_file_path)

            fileName = request.args.get('fileName')
            title = request.args.get('title')
            model = request.args.get('model')
            summaryType = request.args.get('summaryType')
            
            result = transcription_collection.insert_one({'user_id': user_id, 'title': title, 'fileName': fileName, 'duration': get_mp3_duration(temp_file_path), 'summaryType': summaryType, 'createdAt': datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1), 'completed': False, 'summaryText': None, 'transcriptionText': None})
            print("Inserted transcription into database: ", result.inserted_id)
            transcribe_and_summarize(user_id, result.inserted_id, temp_file_path, model, summaryType)
        
        return '', 202
    except jwt.ExpiredSignatureError:
        return jsonify({'error': 'Token expired'}), 401
    except jwt.InvalidTokenError:
        return jsonify({'error': 'Invalid token'}), 401


def transcribe_and_summarize(user_id, transcription_id, file_name, model, summaryType):
    transcripted_text = transcribe.transcribe(file_name, model)
    
    summary = summarize.summarize(transcripted_text, summaryType)

    update_operation = { '$set' : 
        { 'completed' : True, 'transcriptionText' : transcripted_text, 'summaryText' : summary }
    }
    transcription_collection.update_one({'_id': transcription_id, 'user_id': user_id}, update_operation)

def transcribe(path, model):
    model = whisper.load_model(model) # model has to be: tiny, base, small, medium, large
    result = model.transcribe(path)
    return result["text"]

def summarize(input, summaryType):
    completion = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "user", "content": f"Provide a {summaryType} summary of the following text: " + input}
        ]
    )

    return completion.choices[0].message.content

def get_mp3_duration(file_path):
    print("get_mp3_duration: ", file_path)
    try:
        probe = ffmpeg.probe(file_path)
        duration = float(probe['format']['duration'])
    except ffmpeg._run.Error as e:
        print("Error: ", e.stderr)
    
    return duration


@app.route('/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    user = user_collection.find_one({"username": username, "password": password})
    if user is not None:
        token = jwt.encode({'_id': str(user['_id']), 
                            'exp': datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)},
                           app.config['SECRET_KEY'], algorithm='HS256')
        return jsonify({'token': token})
    return jsonify({'error': 'Invalid credentials'}), 401

@app.route('/history', methods=['GET'])
def history():
    token = request.headers.get('Authorization').split(" ")[1]
    try:
        decoded = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        return jsonify({list(transcription_collection.find({'user_id': decoded['_id']}))})
    except jwt.ExpiredSignatureError:
        return jsonify({'error': 'Token expired'}), 401
    except jwt.InvalidTokenError:
        return jsonify({'error': 'Invalid token'}), 401

@app.route('/entry', methods=['GET'])
def entry():
    entry_id = request.args.get('_id')
    token = request.headers.get('Authorization').split(" ")[1]

    try:
        decoded = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        return jsonify({list(transcription_collection.find({'user_id': decoded['_id'], '_id': entry_id}))})
    except jwt.ExpiredSignatureError:
        return jsonify({'error': 'Token expired'}), 401
    except jwt.InvalidTokenError:
        return jsonify({'error': 'Invalid token'}), 401
    
@app.route('/filetest', methods=['POST', 'PUT'])
def filetest():
    # Create a temporary file and write the body to it
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3", mode='wb') as temp_file:
        temp_file.write(request.data)
        temp_file_path = temp_file.name

    return f"Request body saved to temporary file: {temp_file_path}", 200

if __name__ == '__main__':
    app.run(socket.gethostbyname(socket.gethostname()))
    