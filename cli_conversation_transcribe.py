# https://github.com/Azure-Samples/cognitive-services-speech-sdk
# https://github.com/Azure-Samples/cognitive-services-speech-sdk/blob/master/samples/python/console/transcription_sample.py
# https://learn.microsoft.com/en-us/azure/ai-services/speech-service/how-to-use-codec-compressed-audio-input-streams
# https://learn.microsoft.com/en-us/azure/ai-services/speech-service/get-started-stt-diarization?tabs=windows&pivots=programming-language-python

#!/usr/bin/env python
# coding: utf-8

# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE.md file in the project root for full license information.
"""
Conversation transcription samples for the Microsoft Cognitive Services Speech SDK
"""

from dotenv import load_dotenv
import time
import os
from os import path
import logging
# Logging configuration
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("output2.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)


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

    # Subscribe to the events fired by the conversation transcriber
    transcriber.transcribed.connect(conversation_transcriber_transcribed_cb)
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

        result = evt.result.text
        if result:
            logging.info(
                f'Speaker ID: {speaker_id}, Emoji: {emoji}: {evt.result.text}')

    elif evt.result.reason == speechsdk.ResultReason.NoMatch:
        logging.info('NOMATCH: Speech could not be TRANSCRIBED: {}'.format(
            evt.result.no_match_details))


if __name__ == '__main__':
    dotenv_path = path.join(path.dirname(__file__), '.env')
    load_dotenv(dotenv_path, override=True)

    speech_subscription_key = os.getenv('SPEECH_SUBSCRIPTION_KEY')
    speech_key, service_region = speech_subscription_key, "eastus"

    default_speech_auth = {
        "subscription": speech_key,
        "region": service_region
    }

    start_time = time.time()

    # Set your mp3 file path
    conversationfilename = os.path.join('data', 'short_64k.mp3')
    pull_audio_input_stream_compressed_mp3(conversationfilename,
                                           default_speech_auth)
    end_time = time.time()
    logging.info(f"S2T Time taken: {end_time - start_time} seconds")
