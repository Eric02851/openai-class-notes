from flask import Flask, request
from werkzeug.utils import secure_filename
import sys
import io
import threading
import os
import multiprocessing
import time
import tiktoken
import openai

sys.path.append('/Users/eric/Documents/GitHub/whisper/')
import whisper

app = Flask(__name__)
openai.api_key_path = "./apiKey.txt"

filePath = None
parentConn = None
childProcess = None

encoding = tiktoken.encoding_for_model("gpt-3.5-turbo-16k")
maxTokens = 16385
tmpDir = "./transcribeTmp/"

def transcribeThread(filePath, tqdmOut, parentConn):
    #Change file path name to audio path
    model = whisper.load_model("medium.en")
    result = model.transcribe(filePath, verbose=False, tqdmOut=tqdmOut)

    writer = whisper.utils.get_writer("all", tmpDir)
    writerArgs = {"highlight_words": False, "max_line_count": None, "max_line_width": None}
    writer(result, filePath, writerArgs)
    parentConn.send("transcriptionCompleted");

#filePath and parentConn have to be parameter even though it is global because child processes do not share memory space with parent.
def transcribeProcess(filePath, childConn, parentConn):
    tqdmOut = io.StringIO()
    thread = threading.Thread(target=transcribeThread, args=(filePath, tqdmOut, parentConn))
    thread.start()

    print("Waiting for parent process requests")
    while True:
        request = childConn.recv()

        if request == "transcriptionCompleted":
            #make sure audio file is deleted after completion UP HERE.
            thread.join()
            print("Transcription completed")
            childConn.close()
            return

        if request == "killProcess":
            #Sometimes thread stays running even after child process is killed. Add code to kill thread.
            #Delete audio file up here instead of the terminate function
            print("Value: " + str((not tqdmOut.getvalue())))
            if not tqdmOut.getvalue():
                print("Waiting for transcription to start before killing process")
                while not tqdmOut.getvalue():
                    time.sleep(0.1)

            print("Transcription killed")
            childConn.send("transcriptionKilled")
            childConn.close()
            return

        childConn.send(tqdmOut.getvalue())

@app.route('/transcribe/start', methods=['POST'])
def transcribeStart():
    #Add code to create tmp folder if it does not exist
    global filePath, childProcess, parentConn

    if childProcess and childProcess.is_alive():
        return "Transcribe already running", 200
    if os.listdir(tmpDir):
        return "Files waiting for download and deletion", 200

    file = request.files['file']
    filePath = f"{tmpDir}/{secure_filename(file.filename)}"
    file.save(filePath)

    parentConn, childConn = multiprocessing.Pipe()
    childProcess = multiprocessing.Process(target=transcribeProcess, args=(filePath, childConn, parentConn))
    childProcess.start()

    return "Transcribe started", 200

@app.route('/transcribe/stop', methods=['POST'])
def transcribeStop():
    if not childProcess or not childProcess.is_alive():
        return "No active transcribe", 200

    parentConn.send("killProcess");
    parentConn.recv()
    os.remove(filePath)
    return "Transcribe stopped", 200

@app.route('/transcribe/status', methods=['GET'])
def transcribeStatus():
    #Status still showing as starting after transcription has completed
    if len(os.listdir(tmpDir)) > 1:
        return "Files waiting for download and deletion", 200

    if not childProcess or not childProcess.is_alive():
        return "No active transcribe", 200

    parentConn.send("progressCheck")
    progress = parentConn.recv()
    if not progress:
        return "Transcribe starting", 200

    return progress, 200

@app.route('/downloadFiles', methods=['GET'])
def downloadFiles():
    if len(os.listdir(tmpDir)) <= 1:
        return "No files available for download", 200

    fileType = request.get_json()["fileType"]
    with open(f".{filePath.split('.')[1]}.{fileType}", 'r') as f:
        return f.read()

@app.route('/deleteFiles', methods=['GET'])
def deleteFiles():
    tmpFiles = os.listdir(tmpDir)
    if len(tmpFiles) <= 1:
        return "No files available for deletion", 200

    for fileName in tmpFiles:
        os.remove(tmpDir + fileName)

    return f"\"{tmpFiles[0].split('.')[0]}\" files deleted"

@app.route('/checkTokens', methods=['POST'])
def checkTokens():
    #Change to accept string instead of file
    transcript = request.get_json()["transcript"]
    tokenList = encoding.encode(str(transcript))
    return f"Tokens: {str(len(tokenList))}", 200

@app.route('/trimTranscript', methods=['POST'])
def trimTranscript():
    #Change to accept string instead of file
    #Add param to pass in system prompt. Subtract system prompt from max tokens to get real max tokens.
    transcript = str(request.files['file'].read())
    tokenCount = len(encoding.encode(transcript))

    if tokenCount <= maxTokens:
        return "Transcript already less than or equal too max tokens"

    splitTranscript = transcript.split(". ")
    while tokenCount > maxTokens:
        sentenceLen = len(splitTranscript.pop(0))
        transcript = transcript[sentenceLen + 2:]
        tokenCount = len(encoding.encode(transcript))

    return transcript

@app.route('/generateNotes', methods=['POST'])
def generateNotes():
    requestJson = request.get_json()
    transcript = requestJson["transcript"]
    systemPrompt = requestJson.get("systemPrompt")

    if not systemPrompt:
        systemPrompt = "You will be provided with a transcrtipt of a college class. Your task is to turn the transcript into a helpful notes sheet in mark down syntax. Your response should be long enough to cover all topics thoroughly."

    #Add code to check tokens here

    response = openai.ChatCompletion.create(
        model = "gpt-3.5-turbo-16k",
        messages = [
            {"role": "system", "content": systemPrompt},
            {"role": "user", "content": transcript}
        ]
    )

    return response

if __name__ == '__main__':
    try: filePath = tmpDir + os.listdir(tmpDir)[0].split('.')[0] + ".mp3"
    except: pass

    app.run(debug=True)
