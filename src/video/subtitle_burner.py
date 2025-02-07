from pathlib import Path
import subprocess
import logging
from typing import Optional, Union, Dict, Literal, List
import json
from dataclasses import dataclass
import tempfile
import shutil
import os
import re
from datetime import datetime, timedelta

@dataclass
class SubtitleStyle:
    font: str = "Arial"
    font_size: int = 24
    primary_color: str = "white"
    outline_color: str = "black"
    outline_width: int = 2
    bold: bool = False
    italic: bool = False
    alignment: Literal[1, 2, 3, 4, 5, 6, 7, 8, 9] = 2  
    margin_v: int = 10
    margin_h: int = 10

class SubtitleBurner:
    def __init__(self, config: dict = None):
        self.logger = logging.getLogger('subtitle_burner')
        
        self.config = {
            'ffmpeg_path': 'ffmpeg',
            'font_name': 'Arial',
            'font_size': 24,
            'font_color': 'white',
            'outline_color': 'black',
            'outline_width': 2,
            'max_chars_per_line': 42,  # Netflix standard
            'min_duration': 0.833,    
            'max_duration': 7.0        # Maximum duration in seconds
        }
        
        if config:
            self.config.update(config)

    def _process_subtitle_text(self, text: str) -> List[str]:
        """Split long subtitle text into multiple parts."""
        max_chars = self.config.get('max_chars_per_line', 42)
        words = text.split()
        lines = []
        current_line = []
        current_length = 0
        
        for word in words:
            word_len = len(word)
            space_len = 1 if current_line else 0
            
            if current_length + word_len + space_len <= max_chars:
                if current_line:
                    current_line.append(' ')
                current_line.append(word)
                current_length += word_len + space_len
            else:
                if current_line:
                    lines.append(''.join(current_line))
                current_line = [word]
                current_length = word_len
        
        if current_line:
            lines.append(''.join(current_line))
        
        return lines

    def _parse_time(self, time_str: str) -> datetime:
        """Parse SRT timestamp to datetime."""
        time_parts = time_str.replace(',', ':').split(':')
        return datetime.strptime(f"{time_parts[0]}:{time_parts[1]}:{time_parts[2]}.{time_parts[3]}", 
                               "%H:%M:%S.%f")

    def _format_time(self, dt: datetime) -> str:
        """Format datetime to SRT timestamp."""
        return dt.strftime("%H:%M:%S,%f")[:-3]

    def _process_srt_file(self, srt_path: Path) -> Path:
        """Process SRT file to handle long subtitles."""
        temp_dir = Path(self.config.get('temp_dir', tempfile.gettempdir()))
        temp_srt = temp_dir / f"processed_{srt_path.name}"
        temp_srt.parent.mkdir(parents=True, exist_ok=True)
        
        with open(srt_path, 'r', encoding='utf-8') as f_in, \
             open(temp_srt, 'w', encoding='utf-8') as f_out:
            
            content = f_in.read().strip()
            blocks = re.split(r'\n\n+', content)
            new_blocks = []
            subtitle_index = 1
            
            for block in blocks:
                lines = block.strip().split('\n')
                if len(lines) >= 3:
                    timing = lines[1]
                    text = '\n'.join(lines[2:])
                    
                    start_time, end_time = timing.split(' --> ')
                    start_dt = self._parse_time(start_time)
                    end_dt = self._parse_time(end_time)
                    duration = (end_dt - start_dt).total_seconds()
                    
                    if len(text) > self.config['max_chars_per_line'] * 2:
                        lines = self._process_subtitle_text(text)
                        
                        time_per_part = duration / len(lines)
                        time_per_part = min(max(time_per_part, self.config['min_duration']), 
                                          self.config['max_duration'])
                        
                        current_start = start_dt
                        for i in range(0, len(lines), 2):
                            part_text = lines[i]
                            if i + 1 < len(lines):
                                part_text += f"\n{lines[i+1]}"
                            
                            part_end = current_start + timedelta(seconds=time_per_part)
                            if part_end > end_dt:
                                part_end = end_dt
                            
                            new_block = (f"{subtitle_index}\n"
                                       f"{self._format_time(current_start)} --> "
                                       f"{self._format_time(part_end)}\n"
                                       f"{part_text}")
                            new_blocks.append(new_block)
                            subtitle_index += 1
                            
                            current_start = part_end
                    else:
                        new_blocks.append(f"{subtitle_index}\n{timing}\n{text}")
                        subtitle_index += 1
            
            f_out.write('\n\n'.join(new_blocks))
        
        return temp_srt

    # [Previous methods remain unchanged: setup_config, _convert_srt_to_ass, _prepare_subtitle_filter]

    def burn_subtitles(self, 
                    video_path: Union[str, Path], 
                    subtitle_path: Union[str, Path], 
                    output_path: Union[str, Path],
                    style: Optional[SubtitleStyle] = None) -> str:
        """Altyazını video üzərinə yandır"""
        try:
            video_path = Path(video_path).absolute()
            subtitle_path = Path(subtitle_path).absolute()
            output_path = Path(output_path).absolute()
            
            if not video_path.exists():
                raise FileNotFoundError(f"Video fayl tapılmadı: {video_path}")
            if not subtitle_path.exists():
                raise FileNotFoundError(f"Altyazı faylı tapılmadı: {subtitle_path}")
            
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Process subtitles first
            processed_subs = self._process_srt_file(subtitle_path)
            
            subtitle_path_str = str(processed_subs).replace('\\', '/').replace(':', '\\:')
            subtitle_path_str = f"'{subtitle_path_str}'"
            
            if style:
                style_str = (f"force_style='FontName={style.font},"
                        f"FontSize={style.font_size},"
                        f"PrimaryColour=white,"  # Forced white color
                        f"OutlineColour=black,"  # Forced black outline
                        f"Outline=1,"           # Thin outline
                        f"Shadow=0,"            # No shadow
                        f"Bold=0,"              # No bold
                        f"Italic=0,"            # No italic
                        f"Alignment={style.alignment},"
                        f"MarginV={style.margin_v},"
                        f"MarginH={style.margin_h}'")
            else:
                style_str = (f"force_style='FontName=Arial,"
                        f"FontSize=28,"
                        f"PrimaryColour=white,"
                        f"OutlineColour=black,"
                        f"Outline=1,"
                        f"Shadow=0,"
                        f"Bold=0,"
                        f"Italic=0,"
                        f"Alignment=2,"
                        f"MarginV=20,"
                        f"MarginH=10'")
            subtitle_filter = f"subtitles={subtitle_path_str}:{style_str}"
            
            ffmpeg_cmd = [
                self.config['ffmpeg_path'],
                '-i', str(video_path),
                '-vf', subtitle_filter,
                '-c:a', 'copy',
                '-y', str(output_path)
            ]
            
            self.logger.info(f"FFmpeg əmri işə salınır: {' '.join(ffmpeg_cmd)}")
            result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                raise Exception(f"FFmpeg xətası: {result.stderr}")
            
            try:
                processed_subs.unlink()
            except:
                pass
            
            return str(output_path)
            
        except Exception as e:
            self.logger.error(f"Altyazı xətası: {str(e)}")
            raise
