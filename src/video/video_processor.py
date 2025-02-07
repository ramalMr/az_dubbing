from pathlib import Path
import subprocess
import logging
from typing import Optional, Union, List, Dict
import json
import os
from pydub import AudioSegment
import numpy as np
import tempfile
import shutil

class VideoProcessor:
    def __init__(self, config_path: Optional[str] = None):
        self.logger = logging.getLogger('video_processor')
        self.setup_config(config_path)

    def setup_config(self, config_path: Optional[str]):
        if config_path and Path(config_path).exists():
            with open(config_path, 'r') as f:
                self.config = json.load(f)
        else:
            self.config = {
                'ffmpeg_path': 'ffmpeg',
                'ffprobe_path': 'ffprobe',
                'temp_dir': 'temp',
                'output_dir': 'output',
                'video_settings': {
                    'codec': 'libx264',
                    'audio_codec': 'aac',
                    'audio_bitrate': '192k',
                    'video_bitrate': '2000k',
                    'preset': 'medium',
                    'crf': 23
                }
            }

    def merge_audio_segments_with_video(self,
                                      video_path: Union[str, Path],
                                      audio_segments: List[Dict],
                                      output_path: Union[str, Path],
                                      keep_original_audio: bool = False,
                                      original_audio_volume: float = 0.1) -> str:
        """Səs seqmentlərini video ilə birləşdir"""
        try:
            video_path = Path(video_path)
            output_path = Path(output_path)
            
            if not video_path.exists():
                raise FileNotFoundError(f"Video fayl tapılmadı: {video_path}")
            
            # Temp qovluq yarat
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_dir = Path(temp_dir)
                
                # Video müddətini al
                video_duration = self.get_video_duration(video_path)
                
                # Boş səs yaratmaq
                base_audio = AudioSegment.silent(duration=int(video_duration * 1000))
                
                # Hər seqmenti öz vaxtında yerləşdir
                for segment in audio_segments:
                    if Path(segment['path']).exists():
                        segment_audio = AudioSegment.from_wav(segment['path'])
                        position_ms = int(float(segment['start_time']) * 1000)
                        base_audio = base_audio.overlay(segment_audio, position=position_ms)
                
                # Birləşdirilmiş səsi müvəqqəti olaraq saxla
                temp_audio = temp_dir / "combined_audio.wav"
                base_audio.export(str(temp_audio), format='wav')
                
                # Video ilə birləşdir
                output_path.parent.mkdir(parents=True, exist_ok=True)
                
                if keep_original_audio:
                    # Original və dublyaj səslərini qarışdır
                    filter_complex = (
                        f"[0:a]volume={original_audio_volume}[original];"
                        "[1:a][original]amix=inputs=2:duration=first[final_audio]"
                    )
                    
                    ffmpeg_cmd = [
                        self.config['ffmpeg_path'],
                        '-i', str(video_path),
                        '-i', str(temp_audio),
                        '-filter_complex', filter_complex,
                        '-map', '0:v',
                        '-map', '[final_audio]',
                        '-c:v', self.config['video_settings']['codec'],
                        '-preset', self.config['video_settings']['preset'],
                        '-crf', str(self.config['video_settings']['crf']),
                        '-c:a', self.config['video_settings']['audio_codec'],
                        '-b:a', self.config['video_settings']['audio_bitrate'],
                        '-y', str(output_path)
                    ]
                else:
                    # Yalnız dublyaj səsini istifadə et
                    ffmpeg_cmd = [
                        self.config['ffmpeg_path'],
                        '-i', str(video_path),
                        '-i', str(temp_audio),
                        '-map', '0:v',
                        '-map', '1:a',
                        '-c:v', self.config['video_settings']['codec'],
                        '-preset', self.config['video_settings']['preset'],
                        '-crf', str(self.config['video_settings']['crf']),
                        '-c:a', self.config['video_settings']['audio_codec'],
                        '-b:a', self.config['video_settings']['audio_bitrate'],
                        '-y', str(output_path)
                    ]
                
                self.logger.info(f"FFmpeg əmri işə salınır: {' '.join(ffmpeg_cmd)}")
                result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
                
                if result.returncode != 0:
                    raise Exception(f"FFmpeg xətası: {result.stderr}")
                
                self.logger.info(f"Səs seqmentləri video ilə birləşdirildi: {output_path}")
                return str(output_path)
                
        except Exception as e:
            self.logger.error(f"Səs seqmentlərini video ilə birləşdirmə xətası: {str(e)}")
            raise

    def get_video_duration(self, video_path: Union[str, Path]) -> float:
        """Video müddətini saniyələrlə al"""
        try:
            cmd = [
                self.config['ffprobe_path'],
                '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                str(video_path)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                raise Exception(f"FFprobe xətası: {result.stderr}")
            
            return float(result.stdout.strip())
            
        except Exception as e:
            self.logger.error(f"Video müddətini alma xətası: {str(e)}")
            raise

    def extract_audio(self, video_path: Union[str, Path], output_path: Union[str, Path]) -> str:
        """Videodan səsi çıxart"""
        try:
            video_path = Path(video_path)
            output_path = Path(output_path)
            
            if not video_path.exists():
                raise FileNotFoundError(f"Video fayl tapılmadı: {video_path}")
            
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Windows üçün yolu düzəlt
            video_path_str = str(video_path).replace('\\', '/')
            output_path_str = str(output_path).replace('\\', '/')
            
            ffmpeg_cmd = [
                self.config['ffmpeg_path'],
                '-i', video_path_str,
                '-vn',  # Video stream-i ləğv et
                '-acodec', 'pcm_s16le',  # Audio codec
                '-ar', '16000',  # Sample rate
                '-ac', '1',  # Mono
                '-y',  # Mövcud faylın üzərinə yaz
                output_path_str
            ]
            
            self.logger.info(f"FFmpeg əmri işə salınır: {' '.join(ffmpeg_cmd)}")
            
            # Shell=True Windows-da daha yaxşı işləyir
            result = subprocess.run(
                ffmpeg_cmd,
                capture_output=True,
                text=True,
                shell=True if os.name == 'nt' else False
            )
            
            if result.returncode != 0:
                raise Exception(f"FFmpeg xətası: {result.stderr}")
            
            if not output_path.exists():
                raise FileNotFoundError(f"Səs faylı yaradıla bilmədi: {output_path}")
                
            self.logger.info(f"Səs çıxarıldı: {output_path}")
            return str(output_path)
            
        except Exception as e:
            self.logger.error(f"Səs çıxartma xətası: {str(e)}")
            raise
    def validate_audio_sync(self, video_path: str, segments: List[Dict]) -> bool:
        """Səs seqmentlərinin sinxronizasiyasını yoxla"""
        try:
            video_duration = self.get_video_duration(video_path)
            
            # Seqmentlərin video müddətini aşıb-aşmadığını yoxla
            for segment in segments:
                end_time = float(segment['end_time'])
                if end_time > video_duration:
                    self.logger.warning(
                        f"Seqment {end_time}s-də bitir, video müddətini ({video_duration}s) aşır"
                    )
                    return False
                
                # Üst-üstə düşən seqmentləri yoxla
                for other_segment in segments:
                    if segment != other_segment:
                        if (float(segment['start_time']) < float(other_segment['end_time']) and
                            float(segment['end_time']) > float(other_segment['start_time'])):
                            self.logger.warning(f"Üst-üstə düşən seqmentlər aşkar edildi")
                            return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Səs sinxronizasiyası yoxlanışı xətası: {str(e)}")
            return False

    def add_subtitle_to_video(self,
                            video_path: Union[str, Path],
                            subtitle_path: Union[str, Path],
                            output_path: Union[str, Path],
                            burn: bool = False) -> str:
        """Video-ya altyazı əlavə et"""
        try:
            video_path = Path(video_path)
            subtitle_path = Path(subtitle_path)
            output_path = Path(output_path)
            
            if not video_path.exists():
                raise FileNotFoundError(f"Video fayl tapılmadı: {video_path}")
            if not subtitle_path.exists():
                raise FileNotFoundError(f"Altyazı faylı tapılmadı: {subtitle_path}")
            
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            if burn:
                ffmpeg_cmd = [
                    self.config['ffmpeg_path'],
                    '-i', str(video_path),
                    '-vf', f"subtitles={subtitle_path}",
                    '-c:a', 'copy',
                    '-y', str(output_path)
                ]
            else:
                ffmpeg_cmd = [
                    self.config['ffmpeg_path'],
                    '-i', str(video_path),
                    '-i', str(subtitle_path),
                    '-c', 'copy',
                    '-c:s', 'mov_text',
                    '-y', str(output_path)
                ]
            
            result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                raise Exception(f"FFmpeg xətası: {result.stderr}")
            
            self.logger.info(f"Altyazı əlavə edildi: {output_path}")
            return str(output_path)
            
        except Exception as e:
            self.logger.error(f"Altyazı əlavə etmə xətası: {str(e)}")
            raise