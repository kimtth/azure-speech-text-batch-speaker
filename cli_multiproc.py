import io
import json
import os
import logging
import time
import speech
from pydub import AudioSegment
from pydub.silence import split_on_silence
from os import path
from dotenv import load_dotenv
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from azure.storage.blob import BlobServiceClient

# Logging configuration
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("output.log", encoding='utf-8'),
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
temp_directory = "temp"


def upload_audio_file(audio_data, filename):
    container_client = blob_service_client.get_container_client(container_name)
    blob_client = container_client.get_blob_client(filename)
    blob_client.upload_blob(audio_data, overwrite=True)


def transcribe_audio_file(blob_url):
    contents = speech.transcribe(blob_url)
    return contents


def extract_recognized_phrases(contents):
    if not contents:
        return []
    results = json.loads(contents)
    if 'recognizedPhrases' not in results:
        return []
    else:
        return [msg['nBest'][0]['display'] for msg in results['recognizedPhrases'] if msg['recognitionStatus'] == 'Success']


def transcribe_chunk(args):
    i, buffer = args
    upload_audio_file(buffer, f"chunk{i}.mp3")
    rtn = transcribe_audio_file(
        f"https://{blob_service_client.account_name}.blob.core.windows.net/{container_name}/chunk{i}.mp3")
    extract_transcribe = extract_recognized_phrases(rtn)
    return extract_transcribe


def remove_temp_files(folder):
    for filename in os.listdir(folder):
        file_path = os.path.join(folder, filename)
        try:
            if os.path.isfile(file_path):
                os.unlink(file_path)
        except Exception as e:
            print('Failed to delete %s. Reason: %s' % (file_path, e))


def process_chunk(args):  # chunk, to_file=False):
    i, chunk, to_file = args

    if to_file:
        chunk.export(f"{temp_directory}/chunk{i}.mp3", format="mp3")

    buffer = io.BytesIO()
    chunk.export(buffer, format="mp3")
    buffer_copy = io.BytesIO(buffer.getvalue())
    # initial position of read/write pointer at the beginning of the buffer
    buffer.seek(0)
    buffer.truncate(0)
    return buffer_copy


def proc():
    # Set the file path and blob name
    file_path = os.path.join(
        "data", "sample_64k.mp3")
    blob_name = os.path.basename(file_path)

    # remove_temp_files(temp_directory)

    start_time = time.time()
    # https://unix.stackexchange.com/questions/545946/trim-an-audio-file-into-multiple-segments-using-ffmpeg-with-a-single-command
    audio = AudioSegment.from_mp3(file_path, parameters=["-c", "copy"])
    print(f"Transcribing audio {len(audio)}")

    # 1s == 1000 ms
    chunks = split_on_silence(audio, min_silence_len=2000, silence_thresh=-32)

    # Create a ThreadPoolExecutor and process the chunks in parallel
    logging.getLogger().setLevel(logging.WARNING)

    with ProcessPoolExecutor(max_workers=4) as executor:
        args_list = [(i, chunk, True) for i, chunk in enumerate(chunks)]
        buffers = list(executor.map(process_chunk, args_list))

    end_time = time.time()

    logging.getLogger().setLevel(logging.INFO)
    logging.info(f"Chunks Time taken: {end_time - start_time} seconds")
    logging.getLogger().setLevel(logging.WARNING)

    start_time = time.time()
    # Create a ThreadPoolExecutor and process the chunks in parallel
    print(f"Transcribing {len(buffers)} chunks")
    with open(f"{blob_name}.txt", "w", encoding="utf8") as f:
        with ThreadPoolExecutor(max_workers=5) as executor:
            # executor.submit does not guarantee any specific order in which the results are returned.
            # tasks = [executor.submit(transcribe_chunk, i, bytes) for i, bytes in enumerate(buffers)]
            tasks = list(executor.map(transcribe_chunk, enumerate(buffers)))
            for result in tasks:
                if len(result) > 0:
                    f.write(result[0] + os.linesep)

    end_time = time.time()

    logging.getLogger().setLevel(logging.INFO)
    logging.info(f"S2T Time taken: {end_time - start_time} seconds")


if __name__ == '__main__':
    proc()
