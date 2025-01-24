import datetime
import os
import tempfile
from flask import Flask, jsonify, request, make_response
from json import JSONEncoder
from concurrent.futures import ThreadPoolExecutor
import socket
import jwt
import openai
import ffmpeg
import whisper
from pymongo import MongoClient
from bson import ObjectId
from flask_cors import CORS



app = Flask(__name__)
app.config['JWT_KEY'] = 'incredibly_secret_jwt_key'
app.config['MONGODB_CONNECTION_STRING'] = os.getenv('MONGODB_CONNECTION_STRING')
app.config['MAX_CONTENT_LENGTH'] = 1000 * 1024 * 1024 # 1000MB
openai.api_key = os.getenv('OPENAI_API_KEY')
executor = ThreadPoolExecutor(max_workers=5)
CORS(app, supports_credentials=True, origins="*")

class MongoJSONEncoder(JSONEncoder):
    def default(self, obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        return super().default(obj)
app.json_encoder = MongoJSONEncoder

task_status = {}

try:
    uri = app.config['MONGODB_CONNECTION_STRING']
    client = MongoClient(uri)
    database = client["lectify-mongo-db"]
    user_collection = database["user"]
    transcription_collection = database["transcription"]

except Exception as e:
    raise Exception("The following error occurred: ", e)

@app.route('/process', methods=['POST'])
def process():
    token = request.cookies.get('jwt')
    try:
        user_id = jwt.decode(token, app.config['JWT_KEY'], algorithms=['HS256'])['_id']
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3", dir='./temp') as temp_file:
            temp_file.write(request.data)
            temp_file_path = temp_file.name

            print("File saved to temporary file: ", temp_file_path)

            fileName = request.args.get('fileName')
            title = request.args.get('title')
            model = request.args.get('model')
            summaryType = request.args.get('summaryType')
            
            result = transcription_collection.insert_one({'user_id': user_id, 'title': title, 'fileName': fileName, 'duration': get_mp3_duration(temp_file_path), 'transcriptionQuality': model, 'summaryType': summaryType, 'createdAt': datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1), 'completed': False, 'summaryText': None, 'transcriptionText': None})
            print("Inserted transcription into database: ", result.inserted_id)
            print("starting threaded transcription and summarization")
            executor.submit(transcribe_and_summarize, user_id, result.inserted_id, temp_file_path, model, summaryType)
            
        return jsonify({'_id': str(result.inserted_id)}), 202
    except jwt.ExpiredSignatureError:
        return jsonify({'error': 'Token expired'}), 401
    except jwt.InvalidTokenError:
        return jsonify({'error': 'Invalid token'}), 401


def transcribe_and_summarize(user_id, transcription_id, temp_file_path, model, summaryType):
    print("starting transcription")
    transcripted_text = transcribe(temp_file_path, model)
    print("starting summarization")
    summary = summarize(transcripted_text, summaryType)

    update_operation = { '$set' : 
        { 'completed' : True, 'transcriptionText' : transcripted_text, 'summaryText' : summary }
    }
    transcription_collection.update_one({'_id': transcription_id, 'user_id': user_id}, update_operation)
    print("deleting temporary file:", temp_file_path)
    os.remove(temp_file_path)


def transcribe(path, model):
    model = whisper.load_model(model) # model has to be: tiny, base, small, medium, large
    result = model.transcribe(path)
    return result["text"]

def summarize(input, summaryType):
    completion = openai.chat.completions.create(
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
                           app.config['JWT_KEY'], algorithm='HS256')
        response = make_response(jsonify({'message': 'Login successful'}))
        response.set_cookie('jwt', token, max_age=60*60, httponly=True)

        return response
    
    return jsonify({'error': 'Invalid credentials'}), 401

@app.route('/logout', methods=['POST'])
def logout():
    token = request.cookies.get('jwt')
    if not token:
        return jsonify({'message': 'No token to invalidate'}), 400
    
    response = jsonify({'message': 'Logged out successfully'})
    response.set_cookie('jwt', '', max_age=0, httponly=True)
    return response

@app.route('/history', methods=['GET'])
def history():
    token = request.cookies.get('jwt')
    try:
        decoded = jwt.decode(token, app.config['JWT_KEY'], algorithms=['HS256'])
        entries = transcription_collection.find({'user_id': decoded['_id']})
        result = []
        for entry in entries:
            entry['_id'] = str(entry['_id'])
            result.append(entry)
        return jsonify(result)
    except jwt.ExpiredSignatureError:
        return jsonify({'error': 'Token expired'}), 401
    except jwt.InvalidTokenError:
        return jsonify({'error': 'Invalid token'}), 401

@app.route("/health", methods=['GET'])
def health():
    return "", 200

@app.route('/entry', methods=['GET'])
def entry():
    entry_id = request.args.get('_id')
    token = request.cookies.get('jwt')
   
    try:
        decoded = jwt.decode(token, app.config['JWT_KEY'], algorithms=['HS256'])
        try:
            entry = transcription_collection.find_one({'user_id': decoded['_id'], '_id': ObjectId(entry_id)})
            if entry:
                entry['_id'] = str(entry['_id'])  # Convert ObjectId to string
                return jsonify(entry)
            else:
                raise LookupError
        except:
            return jsonify({'error': 'Entry not found'}), 404
    except jwt.ExpiredSignatureError:
        return jsonify({'error': 'Token expired'}), 401
    except jwt.InvalidTokenError:
        return jsonify({'error': 'Invalid token'}), 401

if __name__ == '__main__':
    app.run("0.0.0.0", port=5001)
    
