import numpy as np
from pydub import AudioSegment
import soundfile as sf
from pathlib import Path
import logging
from typing import Optional, Union, Tuple

class AudioUtils:
    def __init__(self):
        self.logger = logging.getLogger('audio_utils')

    @staticmethod
    def normalize_audio(audio_path: str, target_db: float = -20) -> AudioSegment:
        """Səs səviyyəsini normallaşdır"""
        try:
            audio = AudioSegment.from_file(audio_path)
            change_in_db = target_db - audio.dBFS
            return audio.apply_gain(change_in_db)
        except Exception as e:
            logging.error(f"Səs normallaşdırma xətası: {str(e)}")
            raise

    @staticmethod
    def adjust_speed(audio: AudioSegment, speed_factor: float) -> AudioSegment:
        """Səs sürətini tənzimlə"""
        if not 0.5 <= speed_factor <= 2.0:
            raise ValueError("Sürət faktoru 0.5 və 2.0 arasında olmalıdır")
            
        return audio._spawn(audio.raw_data, overrides={
            "frame_rate": int(audio.frame_rate * speed_factor)
        })

    @staticmethod
    def mix_audios(audio1_path: str, audio2_path: str, 
                   volume1: float = 1.0, volume2: float = 1.0) -> AudioSegment:
        """İki səs faylını qarışdır"""
        try:
            audio1 = AudioSegment.from_file(audio1_path)
            audio2 = AudioSegment.from_file(audio2_path)
            
            # Səs səviyyələrini tənzimlə
            audio1 = audio1 + (20 * np.log10(volume1))
            audio2 = audio2 + (20 * np.log10(volume2))
            
            # Səsləri qarışdır
            return audio1.overlay(audio2)
        except Exception as e:
            logging.error(f"Səs qarışdırma xətası: {str(e)}")
            raise

    @staticmethod
    def split_audio(audio_path: str, chunk_duration: int = 30000) -> list:
        """Səs faylını hissələrə böl"""
        try:
            audio = AudioSegment.from_file(audio_path)
            chunks = []
            
            for i in range(0, len(audio), chunk_duration):
                chunk = audio[i:i + chunk_duration]
                chunks.append(chunk)
                
            return chunks
        except Exception as e:
            logging.error(f"Səs bölmə xətası: {str(e)}")
            raise

    @staticmethod
    def detect_silence(audio_path: str, 
                      min_silence_len: int = 500, 
                      silence_thresh: int = -40) -> list:
        """Səsdəki səssiz hissələri aşkarla"""
        try:
            audio = AudioSegment.from_file(audio_path)
            silence_ranges = detect_silence(
                audio,
                min_silence_len=min_silence_len,
                silence_thresh=silence_thresh
            )
            return [(start/1000, end/1000) for start, end in silence_ranges]
        except Exception as e:
            logging.error(f"Səssizlik aşkarlama xətası: {str(e)}")
            raise

    @staticmethod
    def add_fade(audio: AudioSegment, 
                fade_in_ms: int = 100, 
                fade_out_ms: int = 100) -> AudioSegment:
        """Səsə fade effekti əlavə et"""
        try:
            return audio.fade_in(fade_in_ms).fade_out(fade_out_ms)
        except Exception as e:
            logging.error(f"Fade əlavə etmə xətası: {str(e)}")
            raise

    @staticmethod
    def convert_audio(input_path: str, 
                     output_path: str,
                     sample_rate: int = 16000,
                     channels: int = 1) -> str:
        """Səs faylını konvert et"""
        try:
            audio = AudioSegment.from_file(input_path)
            
            # Sample rate və kanal sayını tənzimlə
            if audio.frame_rate != sample_rate:
                audio = audio.set_frame_rate(sample_rate)
            if audio.channels != channels:
                audio = audio.set_channels(channels)
            
            # Yeni faylı saxla
            audio.export(output_path, format=Path(output_path).suffix[1:])
            return output_path
        except Exception as e:
            logging.error(f"Səs konvertasiya xətası: {str(e)}")
            raise

    @staticmethod
    def get_audio_info(audio_path: str) -> dict:
        """Səs faylı haqqında məlumat al"""
        try:
            audio = AudioSegment.from_file(audio_path)
            return {
                "duration": len(audio) / 1000.0,  # seconds
                "sample_rate": audio.frame_rate,
                "channels": audio.channels,
                "sample_width": audio.sample_width,
                "max_dBFS": audio.max_dBFS,
                "rms": audio.rms
            }
        except Exception as e:
            logging.error(f"Səs məlumatı alma xətası: {str(e)}")
            raise