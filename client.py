import requests

def start(audioPath):
    audioName = audioPath.split('/')[-1]
    file = {'file': (audioName, open(audioPath, 'rb'))}

    response = requests.post('http://localhost:5000/transcribe/start', files=file)
    return response.text

def stop():
    response = requests.post('http://localhost:5000/transcribe/stop')
    return(response.text)

def status():
    response = requests.get('http://localhost:5000/transcribe/status')
    return(response.text)

def download(destFolder, fileType):
    requestJson = {"fileType": fileType}
    response = requests.get('http://localhost:5000/downloadFiles', json=requestJson)
    if response.status_code != 200:
        return response.text

    responseJson = response.json()
    with open(f"{destFolder}/{responseJson['fileName']}", 'w') as f:
        f.write(responseJson["file"])

    return "Download successful"

def delete():
    response = requests.get('http://localhost:5000/deleteFiles')
    return response.text

def tokens(transcriptPath):
    requestJson = {"transcript": None}
    with open(transcriptPath, 'r') as f:
        requestJson["transcript"] = f.read()

    response = requests.post('http://localhost:5000/checkTokens', json=requestJson)
    return response.text

def notes(destFolder, transcriptPath):
    requestJson = {"transcript": None}
    with open(transcriptPath, 'r') as f:
        requestJson["transcript"] = f.read()

    response = requests.post('http://localhost:5000/generateNotes', json=requestJson)
    fileName = transcriptPath.split('/')[-1].split('.')[0]
    with open(f"{destFolder}/{fileName}_notes.json", 'w') as f:
        f.write(response.text)

    return "Notes sheet saved"

commands = {
    "start": [start, "Starts transcription process. \n\tParams: audio path"],
    "stop": [stop, "Stops transcription process. \n\tParams: none"],
    "status": [status, "Displays transcription status. \n\tParams: none"],
    "download": [download, "Downloads transcript. \n\tParams: destenation path, file type (txt, srt, json, tsv, vtt)"],
    "delete": [delete, "Deletes transcript files. \n\tParams: none"],
    "tokens": [tokens, "Counts tokens in transcript. \n\tParams: transcript path"],
    "notes": [notes, "Generages notes sheet. \n\tParams: destenation path, transcript path"]
}

while True:
    userInput = input("Enter command: ").split(' ')
    command = userInput[0]
    args = userInput[1:]

    if command not in commands:
        print("Invalid command")
        for c in commands:
            print(f"{c}: {commands[c][1]}")

        print()
        continue

    if len(args) < commands[command][0].__code__.co_argcount:
        print("Missing arguments")
        continue

    print(commands[command][0](*args), end="\n\n")
