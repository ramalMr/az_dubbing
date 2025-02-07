import edge_tts
import asyncio
import logging
from pathlib import Path
import json
import numpy as np
import soundfile as sf
import torch
from transformers import pipeline
import tempfile
from pydub import AudioSegment
from tqdm import tqdm
from datetime import datetime, UTC
import os
import io
class AdvancedTTSEngine:
    def __init__(self, config_path: str = None):
        self.logger = logging.getLogger('tts_engine')
        self.setup_config(config_path)
        self.session_id = datetime.now(UTC).strftime('%Y%m%d_%H%M%S')
        self.logger.info("TTS Engine initialized")
        
    def setup_config(self, config_path: str):
        if config_path and Path(config_path).exists():
            with open(config_path, 'r') as f:
                self.config = json.load(f)
        else:
            self.config = {
                'voices': {
                    'male': {
                        'az': 'az-AZ-BabekNeural',
                        'en': 'en-US-GuyNeural',
                        'tr': 'tr-TR-AhmetNeural'
                    },
                    'female': {
                        'az': 'az-AZ-BanuNeural',
                        'en': 'en-US-JennyNeural',
                        'tr': 'tr-TR-EmelNeural'
                    }
                },
                'pitch_ranges': {
                    'male': {'min': 50, 'max': 180, 'base': 120},
                    'female': {'min': 150, 'max': 300, 'base': 210}
                },
                'voice_params': {
                    'rate': {'min': 0.8, 'max': 1.5, 'default': 1.0},
                    'volume': {'min': 0.5, 'max': 2.0, 'default': 1.0},
                    'gender_confidence_threshold': 0.7
                },
                'sample_rate': 16000,
                'silence_duration': 0.2
            }

    def read_srt(self, srt_path: str) -> list:
        """SRT faylını oxu və parse et"""
        with open(srt_path, 'r', encoding='utf-8') as f:
            content = f.read()

        blocks = content.strip().split('\n\n')
        parsed_subs = []
        
        for block in blocks:
            lines = block.split('\n')
            if len(lines) >= 3:
                try:
                    time_parts = lines[1].split(' --> ')
                    start_time = self._time_to_seconds(time_parts[0])
                    end_time = self._time_to_seconds(time_parts[1])
                    
                    sub = {
                        'index': int(lines[0]),
                        'start_time': start_time,
                        'end_time': end_time,
                        'duration': end_time - start_time,
                        'text': '\n'.join(lines[2:])
                    }
                    parsed_subs.append(sub)
                except Exception as e:
                    self.logger.warning(f"Blok parse edilə bilmədi: {str(e)}")
                    
        return parsed_subs

    def _time_to_seconds(self, time_str: str) -> float:
        """SRT vaxt formatını saniyələrə çevir"""
        time_parts = time_str.replace(',', ':').split(':')
        hours = int(time_parts[0])
        minutes = int(time_parts[1])
        seconds = int(time_parts[2])
        milliseconds = int(time_parts[3])
        
        return hours * 3600 + minutes * 60 + seconds + milliseconds / 1000

    def read_metadata(self, metadata_path: str) -> dict:
        """Metadata faylını oxu"""
        with open(metadata_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _normalize_speaker_params(self, speaker_info: dict) -> dict:
        """Səs parametrlərini normallaşdır"""
        normalized = speaker_info.copy()
        
        # Pitch (Hz)
        pitch = float(speaker_info.get('pitch', 0))
        if pitch > 300:  # Əgər pitch yuxaridirsa
            pitch = 210 if speaker_info.get('gender') == 'female' else 120
        
        normalized['pitch'] = max(50, min(300, pitch))
        
        energy = float(speaker_info.get('energy', 1.0))
        if energy < 0.01 or energy > 10:  # Əgər energy anormal dəyərdədirsə
            energy = 1.0
        normalized['energy'] = max(0.5, min(2.0, energy))
        
        speech_rate = float(speaker_info.get('speech_rate', 1.0))
        if speech_rate > 100:  # Əgər speech rate anormal yüksəkdirsə
            speech_rate = 1.0
        normalized['speech_rate'] = max(0.8, min(1.5, speech_rate))
        
        return normalized

    def _find_matching_segment(self, subtitle: dict, metadata_segments: list) -> dict:
        """Metadata-dan uyğun seqmenti tap və parametrləri normallaşdır"""
        try:
            closest_segment = None
            min_diff = float('inf')
            
            for segment in metadata_segments:
                if 'segment_id' in segment:  # Yeni metadata formatı
                    start_diff = abs(float(segment['start_time']) - subtitle['start_time'])
                    end_diff = abs(float(segment['end_time']) - subtitle['end_time'])
                    total_diff = start_diff + end_diff
                    
                    if total_diff < min_diff:
                        min_diff = total_diff
                        closest_segment = segment
            
            if closest_segment and 'speaker' in closest_segment:
                speaker_info = closest_segment['speaker']
                
                gender = speaker_info.get('gender', 'unknown').lower()
                confidence = speaker_info.get('gender_confidence', 0)
                
                if confidence > self.config['voice_params']['gender_confidence_threshold']:
                    normalized_speaker = self._normalize_speaker_params(speaker_info)
                else:
                    pitch = speaker_info.get('pitch', 0)
                    gender = 'female' if pitch > 165 else 'male'
                    normalized_speaker = self._normalize_speaker_params({
                        'gender': gender,
                        'gender_confidence': 0.8,
                        'pitch': pitch,
                        'energy': speaker_info.get('energy', 1.0),
                        'speech_rate': speaker_info.get('speech_rate', 1.0)
                    })
                
                return {
                    'segment_id': closest_segment.get('segment_id'),
                    'speaker': normalized_speaker,
                    'start_time': closest_segment['start_time'],
                    'end_time': closest_segment['end_time']
                }
                
        except Exception as e:
            self.logger.error(f"Seqment uyğunlaşdırma xətası: {str(e)}")
        
        return {
            'segment_id': 0,
            'speaker': {
                'gender': 'male',
                'gender_confidence': 1.0,
                'pitch': 120,
                'energy': 1.0,
                'speech_rate': 1.0
            }
        }

    async def generate_speech(self, text: str, speaker_info: dict, 
                            output_path: str, lang: str = 'az') -> str:
        try:
            if not text or text.isspace():
                self.logger.warning("Boş mətn verildi, səssizlik yaradılır")
                # Boş mətn üçün səssizlik yarat
                silence = AudioSegment.silent(duration=1000)  # 1 saniyə
                silence.export(output_path, format='wav')
                return output_path
                
            # gender ve voice
            gender = speaker_info.get('gender', 'male').lower()
            if gender not in ['male', 'female']:
                gender = 'male'
                
            voice = self.config['voices'][gender][lang]
            
            # Edge TTS params{}
            params = {
                "text": text,
                "voice": voice,
                "pitch": "+0Hz",
                "rate": "+0%",
                "volume": "+0%"
            }
            
            # Pitch settings
            if 'pitch' in speaker_info:
                base_pitch = self.config['pitch_ranges'][gender]['base']
                pitch = float(speaker_info['pitch'])
                if 50 <= pitch <= 300:
                    pitch_change = ((pitch - base_pitch) / base_pitch) * 50
                    params["pitch"] = f"{int(pitch_change):+d}Hz"
            
            # rate settings
            if 'speech_rate' in speaker_info:
                rate = float(speaker_info['speech_rate'])
                if 0.5 <= rate <= 2.0:
                    rate_change = (rate - 1.0) * 100
                    params["rate"] = f"{int(rate_change):+d}%"
            
            # voice A settings 
            if 'energy' in speaker_info:
                volume = float(speaker_info['energy'])
                if 0.1 <= volume <= 2.0:
                    volume_change = (volume - 1.0) * 100
                    params["volume"] = f"{int(volume_change):+d}%"
            
            self.logger.info(f"TTS parametrləri: {params}")
            
            communicate = edge_tts.Communicate(**params)
            await communicate.save(output_path)
            
            # Yoxlama
            if not Path(output_path).exists() or Path(output_path).stat().st_size < 100:
                raise Exception("Səs faylı yaradılmadı və ya boşdur")
            
            return output_path
            
        except Exception as e:
            self.logger.error(f"TTS xətası: {str(e)}")
            try:
                self.logger.info("Minimal parametrlərlə təkrar cəhd edilir...")
                communicate = edge_tts.Communicate(
                    text=text,
                    voice=self.config['voices']['male'][lang]
                )
                await communicate.save(output_path)
                return output_path
            except Exception as retry_error:
                self.logger.error(f"Təkrar cəhd xətası: {str(retry_error)}")
                raise

    async def process_segment(self, text: str, speaker_info: dict, 
                            target_duration: float, output_path: str) -> str:
        """Tam seqment emalı"""
        try:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            try:
                params = {
                    "text": text,
                    "voice": speaker_info.get('voice', self.config['voices']['male']['az']),
                    "pitch": f"{int(speaker_info.get('pitch_change', 0)):+d}Hz",
                    "rate": f"{int(speaker_info.get('rate_change', 0)):+d}%",
                    "volume": f"{int(speaker_info.get('volume_change', 0)):+d}%"
                }
                
                temp_mp3 = str(output_path) + '.temp.mp3'
                
                try:
                    communicate = edge_tts.Communicate(**params)
                    await communicate.save(temp_mp3)
                    
                    if not Path(temp_mp3).exists():
                        raise Exception("TTS səs faylı yarada bilmədi")
                    
                    audio = AudioSegment.from_mp3(temp_mp3)
                    
                    current_duration = len(audio) / 1000.0
                    if current_duration > 0 and abs(current_duration - target_duration) > 0.1:
                        speed_factor = current_duration / target_duration
                        if 0.5 <= speed_factor <= 2.0:
                            audio = audio._spawn(audio.raw_data, overrides={
                                "frame_rate": int(audio.frame_rate * speed_factor)
                            })
                            audio = audio.set_frame_rate(self.config['sample_rate'])
                    
                    silence_ms = int(self.config['silence_duration'] * 1000)
                    silence = AudioSegment.silent(duration=silence_ms)
                    audio = silence + audio + silence
                    
                    target_db = -20
                    change_in_db = target_db - audio.dBFS
                    normalized_audio = audio.apply_gain(change_in_db)
                    
                    normalized_audio.export(
                        str(output_path),
                        format='wav',
                        parameters=[
                            "-ar", str(self.config['sample_rate']),
                            "-ac", "1"  # Mono
                        ]
                    )
                    
                    Path(temp_mp3).unlink(missing_ok=True)
                    
                    if not output_path.exists():
                        raise Exception("Audio fayl yaradıla bilmədi")
                    
                    return str(output_path)
                    
                except Exception as e:
                    if Path(temp_mp3).exists():
                        Path(temp_mp3).unlink()
                    raise e
                    
            except Exception as audio_error:
                self.logger.error(f"Audio emalı xətası: {str(audio_error)}")
                raise
                
        except Exception as e:
            self.logger.error(f"Segment emalı xətası: {str(e)}")
            raise
    async def process_movie(self, srt_path: str, metadata_path: str, output_dir: str) -> list:
        """Filmin bütün seqmentlərini emal et və səs seqmentlərinin siyahısını qaytar"""
        try:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            audio_dir = output_dir / "audio_segments"
            audio_dir.mkdir(exist_ok=True)
            
            subtitles = self.read_srt(srt_path)
            metadata = self.read_metadata(metadata_path)
            
            audio_segments = []
            successful_count = 0
            
            for sub in tqdm(subtitles, desc="Seqmentlər emal edilir"):
                try:
                    segment_metadata = self._find_matching_segment(sub, metadata['segments'])
                    
                    if segment_metadata:
                        audio_path = audio_dir / f"segment_{sub['index']:04d}.wav"
                        
                        result_path = await self.process_segment(
                            text=sub['text'],
                            speaker_info=segment_metadata['speaker'],
                            target_duration=sub['duration'],
                            output_path=str(audio_path)
                        )
                        
                        if Path(result_path).exists():
                            audio_segments.append({
                                'path': result_path,
                                'start_time': sub['start_time'],
                                'end_time': sub['end_time'],
                                'duration': sub['duration'],
                                'text': sub['text'],
                                'speaker_info': segment_metadata['speaker']
                            })
                            successful_count += 1
                            
                except Exception as e:
                    self.logger.error(f"Seqment {sub['index']} emal edilərkən xəta: {str(e)}")
                    continue
            
            self.logger.info(f"Emal edilən seqmentlər: {successful_count}/{len(subtitles)}")
            
            if successful_count > 0:
                # Seqment melumatlarini saxla
                segments_info = {
                    "processing_date": datetime.now(UTC).isoformat(),
                    "user": os.getenv('USERNAME', 'unknown'),
                    "total_segments": len(audio_segments),
                    "successful_segments": successful_count,
                    "segments": audio_segments
                }
                
                segments_info_path = output_dir / "segments_info.json"
                with open(segments_info_path, 'w', encoding='utf-8') as f:
                    json.dump(segments_info, f, ensure_ascii=False, indent=2)
                
                return audio_segments
            else:
                raise Exception("Heç bir seqment uğurla emal edilmədi")
                
        except Exception as e:
            self.logger.error(f"Film emalı xətası: {str(e)}")
            raise

    def _combine_audio_segments(self, segments: list, output_path: str):
        """Audio seqmentləri birləşdir"""
        try:
            combined = AudioSegment.empty()
            successful_segments = []
            
            for segment in sorted(segments, key=lambda x: x['start_time']):
                try:
                    if Path(segment['path']).exists():
                        segment_audio = AudioSegment.from_wav(segment['path'])
                        combined += segment_audio
                        successful_segments.append(segment)
                    else:
                        self.logger.warning(f"Audio fayl tapılmadı: {segment['path']}")
                except Exception as e:
                    self.logger.warning(f"Seqment birləşdirilə bilmədi: {str(e)}")
                    continue
            
            if len(successful_segments) > 0:
                combined.export(str(output_path), format='wav')
                self.logger.info(f"Audio birləşdirildi: {len(successful_segments)} seqment")
            else:
                self.logger.error("Heç bir seqment birləşdirilə bilmədi")
                
        except Exception as e:
            self.logger.error(f"Audio birləşdirmə xətası: {str(e)}")
            raise