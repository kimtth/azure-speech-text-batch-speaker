import json
import os
import streamlit as st
import speech
from os import path
from dotenv import load_dotenv
from azure.storage.blob import BlobServiceClient


dotenv_path = path.join(path.dirname(__file__), '.env')
load_dotenv(dotenv_path, override=True)

speech_subscription_key = os.getenv('SPEECH_SUBSCRIPTION_KEY')
speech_endpoint = os.getenv('SPEECH_ENDPOINT')
connection_string = os.getenv("BLOB_CONNECTION_STRING")
container_name = os.getenv("BLOB_CONTAINER_NAME")
env_type = os.getenv('ENV_TYPE', 'dev')

st.set_page_config(page_title="Azure Speech to Text")
st.header("Azure Speech to Text (Batch)")

blob_service_client = BlobServiceClient.from_connection_string(
    connection_string)


def callback():
    st.success('Process completed')
    st.balloons()


def upload_audio_file(audio_data, filename):
    container_client = blob_service_client.get_container_client(container_name)
    blob_client = container_client.get_blob_client(filename)
    blob_client.upload_blob(audio_data, overwrite=True)


def transcribe_audio_file(blob_url):
    with st.spinner(text="In progress..."):
        contents = speech.transcribe(blob_url, callback)
    return contents


def extract_recognized_phrases(contents):
    results = json.loads(contents)
    if 'recognizedPhrases' not in results:
        return []
    else:
        return [msg['nBest'][0]['display'] for msg in results['recognizedPhrases'] if msg['recognitionStatus'] == 'Success']


def main():
    # upload file
    mp3file = st.file_uploader("Please specify voice data.", type=['mp3', 'wav'])

    # extract the text
    if mp3file is not None:
        filename = mp3file.name

        with mp3file as audio:
            audio_data = audio.read()
            upload_audio_file(audio_data, filename)

        primary_endpoint = f"https://{blob_service_client.account_name}.blob.core.windows.net"
        blob_url = f"{primary_endpoint}/{container_name}/{filename}"

        print(blob_url, filename)

        contents = transcribe_audio_file(blob_url)

        if contents:
            # debug
            with open(f'{filename}.json', 'w', encoding='utf8') as f:
                f.write(contents)

            msgs = extract_recognized_phrases(contents)

            # debug
            with open(f'{filename}.txt', 'w', encoding='utf8') as f:
                f.write(os.linesep.join(msgs))

            for msg in msgs:
                if msg:
                    st.write(msg)
                    st.write(os.linesep)
        else:
            st.warning('Something went wrong!', icon="⚠️")


if __name__ == '__main__':
    # streamlit run web_main.py
    main()
