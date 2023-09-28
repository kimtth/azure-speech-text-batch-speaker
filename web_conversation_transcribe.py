# https://github.com/Azure-Samples/cognitive-services-speech-sdk
# https://github.com/Azure-Samples/cognitive-services-speech-sdk/blob/master/samples/python/console/transcription_sample.py
# https://learn.microsoft.com/en-us/azure/ai-services/speech-service/how-to-use-codec-compressed-audio-input-streams
# https://learn.microsoft.com/en-us/azure/ai-services/speech-service/get-started-stt-diarization?tabs=windows&pivots=programming-language-python

#!/usr/bin/env python
# coding: utf-8

# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

"""
The code not working on Streamlit. Don't use the code.
"""

"""
Conversation transcription samples for the Microsoft Cognitive Services Speech SDK
"""

import logging
from os import path
import os
from tempfile import NamedTemporaryFile
import time
import streamlit as st

from dotenv import load_dotenv

try:
    import azure.cognitiveservices.speech as speechsdk
except ImportError:
    logging.info("""
    Importing the Speech SDK for Python failed.
    Refer to
    https://docs.microsoft.com/azure/cognitive-services/speech-service/quickstart-python for
    installation instructions.
    """)
    import sys
    sys.exit(1)

# Set up the subscription info for the Speech Service:
# Replace with your own subscription key and service region (e.g., "centralus").
# See the limitations in supported regions,
# https://docs.microsoft.com/azure/cognitive-services/speech-service/how-to-use-conversation-transcription

# This sample uses a wavfile which is captured using a supported Speech SDK devices (8 channel, 16kHz, 16-bit PCM)
# See https://docs.microsoft.com/azure/cognitive-services/speech-service/speech-devices-sdk-microphone

# Dictionary for speaker id management
speaker_ids = set()
emoji_list = ['😀', '😁', '😂', '🤣', '😃', '😄', '😅', '😆']

st.set_page_config(page_title="Azure Speech to Text")
st.header("Azure Speech to Text (Batch)")


class BinaryFileReaderCallback(speechsdk.audio.PullAudioInputStreamCallback):
    def __init__(self, filename: str):
        super().__init__()
        self._file_h = open(filename, "rb")

    def read(self, buffer: memoryview) -> int:
        try:
            size = buffer.nbytes
            frames = self._file_h.read(size)
            buffer[:len(frames)] = frames

            return len(frames)
        except Exception as ex:
            logging.info('Exception in `read`: {}'.format(ex))
            raise

    def close(self) -> None:
        logging.info('closing file')
        try:
            self._file_h.close()
        except Exception as ex:
            logging.info('Exception in `close`: {}'.format(ex))
            raise


def compressed_stream_helper(compressed_format,
                             mp3_file_path,
                             default_speech_auth):
    callback = BinaryFileReaderCallback(mp3_file_path)
    stream = speechsdk.audio.PullAudioInputStream(
        stream_format=compressed_format, pull_stream_callback=callback)

    speech_config = speechsdk.SpeechConfig(**default_speech_auth)
    speech_config.speech_recognition_language = "ja-JP"
    audio_config = speechsdk.audio.AudioConfig(stream=stream)

    transcriber = speechsdk.transcription.ConversationTranscriber(
        speech_config=speech_config, audio_config=audio_config)

    done = False

    def stop_cb(evt: speechsdk.SessionEventArgs):
        """callback that signals to stop continuous transcription upon receiving an event `evt`"""
        logging.info('CLOSING {}'.format(evt.session_id))
        nonlocal done
        done = True
        st.success('Process completed')
        st.balloons()

    st.info('In progress...', icon="ℹ️")
    # Subscribe to the events fired by the conversation transcriber
    transcriber.transcribed.connect(
        conversation_transcriber_transcribed_cb)
    transcriber.session_started.connect(
        lambda evt: logging.info('SESSION STARTED: {}'.format(evt.session_id)))
    transcriber.session_stopped.connect(
        lambda evt: logging.info('SESSION STOPPED {}'.format(evt.session_id)))
    transcriber.canceled.connect(lambda evt: logging.info(
        'CANCELED {}'.format(evt.session_id)))
    # stop continuous transcription on either session stopped or canceled events
    transcriber.session_stopped.connect(stop_cb)
    transcriber.canceled.connect(stop_cb)

    # Start continuous speech recognition
    transcriber.start_transcribing_async()
    while not done:
        time.sleep(.5)

    transcriber.stop_transcribing_async()


def pull_audio_input_stream_compressed_mp3(mp3_file_path: str,
                                           default_speech_auth):
    # Create a compressed format
    compressed_format = speechsdk.audio.AudioStreamFormat(
        compressed_stream_format=speechsdk.AudioStreamContainerFormat.MP3)
    compressed_stream_helper(
        compressed_format, mp3_file_path, default_speech_auth)


def conversation_transcriber_transcribed_cb(evt: speechsdk.SpeechRecognitionEventArgs):
    if evt.result.reason == speechsdk.ResultReason.RecognizedSpeech:
        # Speaker assignment
        speaker_id = evt.result.speaker_id
        if evt.result.speaker_id not in speaker_ids:
            speaker_ids.add(evt.result.speaker_id)

        speaker_ids_list = list(speaker_ids)
        index = speaker_ids_list.index(speaker_id)
        emoji = emoji_list[index % len(emoji_list)]

        # The result with Speaker id and emoji
        logging.info(
            f'Speaker ID: {speaker_id}, Emoji: {emoji}: {evt.result.text}')
        st.write(f'Speaker ID: {speaker_id}{emoji}: {evt.result.text}')
        st.write(os.linesep)

    elif evt.result.reason == speechsdk.ResultReason.NoMatch:
        logging.info('\tNOMATCH: Speech could not be TRANSCRIBED: {}'.format(
            evt.result.no_match_details))
        st.warning('Something went wrong!', icon="⚠️")


def main():

    # Logging configuration
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
        logging.basicConfig(filename='output2.log', level=logging.INFO)

    # Load environment variables
    dotenv_path = path.join(path.dirname(__file__), '.env')
    load_dotenv(dotenv_path, override=True)

    speech_subscription_key = os.getenv('SPEECH_SUBSCRIPTION_KEY')
    speech_key, service_region = speech_subscription_key, "eastus"

    # Set up the subscription info for the Speech Service:
    default_speech_auth = {
        "subscription": speech_key,
        "region": service_region
    }

    # Upload file
    mp3file = st.file_uploader("Please specify voice data.", type=['mp3'])

    # Extract the text
    if mp3file is not None:
        # Create Temporary file for file path
        # By default the temporary file is deleted as soon as it is closed. To fix this use delete=False.
        with NamedTemporaryFile(dir=os.path.abspath('.'), suffix='.mp3', delete=False) as f:
            f.write(mp3file.getbuffer())

            # The line for resolving the error "Thread 'Dummy-11': missing ScriptRunContext."
            # st.script_runner.add_script_run_ctx(pull_audio_input_stream_compressed_mp3)
            # Not able to solve the error "Thread 'Dummy-11': missing ScriptRunContext."
            st.runtime.scriptrunner.add_script_run_ctx(
                pull_audio_input_stream_compressed_mp3)

            conversationfilename = f.name
            print(conversationfilename)
            pull_audio_input_stream_compressed_mp3(
                conversationfilename, default_speech_auth)

            f.close()
            os.unlink(f.name)


if __name__ == '__main__':
    main()
