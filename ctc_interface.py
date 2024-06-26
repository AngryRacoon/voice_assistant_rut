import wave
import torch
import torchaudio
import pyaudio
import numpy as np
from nemo.collections.asr.models import EncDecCTCModel
from preprocessors import AudioToMelSpectrogramPreprocessor

class SpeechRecognizer:
    def __init__(self):
        self.chunk = 2048
        self.format = pyaudio.paInt16
        self.channels = 1
        self.rate = 16000
        self.audio = pyaudio.PyAudio()
        self.stream = None
        self.threshold = 100
        self.gigaAM = "data/ctc_model_weights.ckpt"
        self.config = "data/ctc_model_config.yaml"
        self.device = "cpu"
        self.model = EncDecCTCModel.from_config_file(self.config)
        self.ckpt = torch.load(self.gigaAM, map_location="cpu")
        self.model.load_state_dict(self.ckpt, strict=False)
        self.model = self.model.to(self.device)
        self.model.eval()

    def calibrate_microphone(self):
        self.stream = self.audio.open(format=self.format, channels=self.channels, rate=self.rate, input=True, frames_per_buffer=self.chunk)
        print("Calibrating... Be quiet!")
        frames = [self.stream.read(self.chunk) for _ in range(0, int(self.rate / self.chunk * 2))]
        data_int = np.frombuffer(b''.join(frames), dtype=np.int16)
        new_threshold = np.max(data_int)
        print(f"Calibration complete. New threshold is {new_threshold}")
        self.threshold = new_threshold
        self.stream.stop_stream()

    def record_audio(self, frames):
        filename = "speech.wav"
        with wave.open(filename, 'wb') as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(self.audio.get_sample_size(self.format))
            wf.setframerate(self.rate)
            wf.writeframes(b''.join(frames))
        return filename

    def listen_and_transcribe(self):
        self.stream = self.audio.open(format=self.format, channels=self.channels, rate=self.rate, input=True, frames_per_buffer=self.chunk)
        print("Listening...")
        frames = []
        while True:
            data = self.stream.read(self.chunk)
            data_int = np.frombuffer(data, dtype=np.int16)
            if np.max(data_int) > self.threshold:
                frames.append(data)
            elif frames:
                print("Processing audio...")
                filename = self.record_audio(frames)
                transcription = self.model.transcribe([filename])[0]
                print("Recognized by GigaAM:", transcription)
                frames = []
                return transcription

    def close(self):
        self.stream.stop_stream()
        self.stream.close()