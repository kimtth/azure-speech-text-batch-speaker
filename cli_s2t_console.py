from azure.storage.blob import BlobServiceClient
import speech
from dotenv import load_dotenv
from os import path
import os
import json
import logging
import time

# Logging configuration
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("output3.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)


dotenv_path = path.join(path.dirname(__file__), '.env')
load_dotenv(dotenv_path, override=True)

speech_subscription_key = os.getenv('SPEECH_SUBSCRIPTION_KEY')
speech_endpoint = os.getenv('SPEECH_ENDPOINT')
connection_string = os.getenv("BLOB_CONNECTION_STRING")
container_name = os.getenv("BLOB_CONTAINER_NAME")
env_type = os.getenv('ENV_TYPE', 'dev')


blob_service_client = BlobServiceClient.from_connection_string(
    connection_string)


# Dictionary for speaker id management
emoji_list = ['😀', '😁', '😂', '🤣', '😃', '😄', '😅', '😆']


def callback():
    print('Process completed')


def upload_audio_file(audio_data, filename):
    container_client = blob_service_client.get_container_client(container_name)
    blob_client = container_client.get_blob_client(filename)
    blob_client.upload_blob(audio_data, overwrite=True)


def transcribe_audio_file(blob_url):
    contents = speech.transcribe(blob_url, callback)
    return contents


def extract_recognized_phrases(contents):
    results = json.loads(contents)
    if 'recognizedPhrases' not in results:
        return []
    else:
        return [(msg['speaker'], msg['nBest'][0]['display']) for msg in results['recognizedPhrases'] if msg['recognitionStatus'] == 'Success']


def main():
    # extract the text
    file_path = os.path.join('data', 'sample-kaigi.mp3')
    # file_path = os.path.join('data', 'short_64k.mp3')
    filename = os.path.basename(file_path)

    with open(file_path, 'rb') as audio_data:
        upload_audio_file(audio_data, filename)

    primary_endpoint = f"https://{blob_service_client.account_name}.blob.core.windows.net"
    blob_url = f"{primary_endpoint}/{container_name}/{filename}"

    print(blob_url, filename)
    contents = transcribe_audio_file(blob_url)

    if contents:
        # check if contents is a list
        if isinstance(contents, list):
            contents = os.linesep.join(contents)
        # debug
        with open(f'{filename}.json', 'w', encoding='utf8') as f:
            f.write(contents)

        msgs = extract_recognized_phrases(contents)

        # debug
        for speaker_id, msg in msgs:
            if msg:
                emoji = emoji_list[int(speaker_id) % len(emoji_list)]
                logging.info(
                    f'Speaker ID: {speaker_id}, Emoji: {emoji}: {msg}')
    else:
        logging.info('Something went wrong!')


if __name__ == '__main__':
    start_time = time.time()
    main()
    end_time = time.time()
    logging.info(f"S2T Time taken: {end_time - start_time} seconds")
