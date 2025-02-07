from pathlib import Path
import subprocess
import logging
from typing import Optional, Union, Dict, Literal
import json
from dataclasses import dataclass
import tempfile
import shutil
import os

@dataclass
class SubtitleStyle:
    font: str = "Arial"
    font_size: int = 32  # Daha böyük font ölçüsü
    primary_color: str = "&HFFFFFF"  # Ağ rəng (hex format)
    outline_color: str = "&H000000"  # Qara rəng (hex format)
    outline_width: int = 3  # Daha qalın kontur
    bold: bool = True  # Qalın mətn
    italic: bool = False
    alignment: Literal[1, 2, 3, 4, 5, 6, 7, 8, 9] = 2  # 2=aşağı mərkəz
    margin_v: int = 25  # Daha çox vertikal boşluq
    margin_h: int = 20  # Daha çox horizontal boşluq
    shadow_color: str = "&H000000"  # Kölgə rəngi
    shadow_depth: int = 2  # Kölgə dərinliyi
    spacing: int = 1  # Hərflər arası məsafə
    border_style: int = 4  # 1=outline, 3=opaq arxa fon, 4=rəngli kölgə
    scale_x: int = 100  # Horizontal miqyas
    scale_y: int = 100  # Vertikal miqyas
    wrap_style: int = 1  # Ağıllı sətir kəsmə

class SubtitleBurner:
    def __init__(self, config: dict = None):
        self.logger = logging.getLogger('subtitle_burner')
        
        # Default konfiqurasiya
        self.config = {
            'ffmpeg_path': 'ffmpeg',
            'ffprobe_path': 'ffprobe',
            'temp_dir': str(Path(tempfile.gettempdir()) / "subtitle_burner"),
            'subtitle_settings': {
                'font': 'Arial',
                'font_size': 32,
                'primary_color': '&HFFFFFF',
                'outline_color': '&H000000',
                'outline_width': 3,
                'bold': True,
                'alignment': 2,
                'margin_v': 25,
                'margin_h': 20,
                'shadow_depth': 2,
                'border_style': 4,
                'wrap_style': 1
            }
        }
        
        if config:
            self.config.update(config)

    def setup_config(self, config_path: Optional[str] = None) -> None:
        """Konfiqurasiya parametrlərini təyin et."""
        if config_path and Path(config_path).exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
        else:
            self.config = {
                'ffmpeg_path': 'ffmpeg',
                'ffprobe_path': 'ffprobe',
                'temp_dir': str(Path(tempfile.gettempdir()) / "subtitle_burner"),
                'subtitle_settings': {
                    'font': 'Arial',
                    'font_size': 32,
                    'primary_color': '&HFFFFFF',
                    'outline_color': '&H000000',
                    'outline_width': 3,
                    'bold': True,
                    'alignment': 2,
                    'margin_v': 25,
                    'margin_h': 20,
                    'shadow_depth': 2,
                    'border_style': 4,
                    'wrap_style': 1
                }
            }

    def _get_video_dimensions(self, video_path: Path) -> tuple[int, int]:
        """Video ölçülərini al"""
        try:
            cmd = [
                self.config['ffprobe_path'],
                '-v', 'error',
                '-select_streams', 'v:0',
                '-show_entries', 'stream=width,height',
                '-of', 'csv=p=0',
                str(video_path)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                width, height = map(int, result.stdout.strip().split(','))
                return width, height
        except Exception as e:
            self.logger.warning(f"Video ölçüləri alına bilmədi: {str(e)}")
        
        return 1280, 720  # Default ölçülər

    def _convert_srt_to_ass(self, srt_path: Path, style: Optional[SubtitleStyle] = None) -> Path:
        """SRT faylını ASS formatına çevir"""
        ass_path = Path(self.config['temp_dir']) / f"{srt_path.stem}.ass"
        ass_path.parent.mkdir(parents=True, exist_ok=True)

        if style is None:
            style = SubtitleStyle()

        cmd = [
            self.config['ffmpeg_path'],
            '-i', str(srt_path),
            '-y', str(ass_path)
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(f"SRT-ASS çevrilmə xətası: {result.stderr}")

        return ass_path

    def _prepare_subtitle_filter(self, subtitle_path: Path, style: SubtitleStyle) -> str:
        """Altyazı filterini hazırla"""
        # Windows yolunu düzəlt
        subtitle_path_str = str(subtitle_path).replace('\\', '/').replace(':', '\\:')
        subtitle_path_str = f"filename='{subtitle_path_str}'"
        
        # Stil parametrləri
        style_str = (
            f"FontName={style.font},"
            f"FontSize={style.font_size},"
            f"PrimaryColour={style.primary_color},"
            f"OutlineColour={style.outline_color},"
            f"BackColour={style.shadow_color},"
            f"Bold={1 if style.bold else 0},"
            f"Italic={1 if style.italic else 0},"
            f"BorderStyle={style.border_style},"
            f"Outline={style.outline_width},"
            f"Shadow={style.shadow_depth},"
            f"Alignment={style.alignment},"
            f"MarginL={style.margin_h},"
            f"MarginR={style.margin_h},"
            f"MarginV={style.margin_v},"
            f"Spacing={style.spacing},"
            f"ScaleX={style.scale_x},"
            f"ScaleY={style.scale_y},"
            f"WrapStyle={style.wrap_style}"
        )
        
        return f"subtitles={subtitle_path_str}:force_style='{style_str}'"
    def _split_srt_to_ass_files(self, srt_path: Path, style: Optional[SubtitleStyle] = None) -> list[Path]:
        """SRT faylını cümlələrə böl və hər cümlə üçün ayrı ASS faylı yarat."""
        ass_files = []
        if style is None:
            style = SubtitleStyle()

        with open(srt_path, 'r', encoding='utf-8') as f:
            srt_content = f.read()

        # SRT faylını cümlələrə böl
        subtitles = srt_content.strip().split('\n\n')
        for i, subtitle in enumerate(subtitles):
            lines = subtitle.split('\n')
            if len(lines) >= 3:
                # Zaman kodları və mətn
                timecodes = lines[1]
                text = ' '.join(lines[2:])
                # Yeni SRT məzmunu
                new_srt_content = f"1\n{timecodes}\n{text}\n"
                # Müvəqqəti SRT faylı yarat
                temp_srt_path = Path(self.config['temp_dir']) / f"temp_{i}.srt"
                with open(temp_srt_path, 'w', encoding='utf-8') as temp_srt_file:
                    temp_srt_file.write(new_srt_content)
                # SRT faylını ASS formatına çevir
                ass_path = self._convert_srt_to_ass(temp_srt_path, style)
                ass_files.append(ass_path)
                # Müvəqqəti SRT faylını sil
                temp_srt_path.unlink()

        return ass_files

    def burn_subtitles(self, 
                    video_path: Union[str, Path], 
                    subtitle_path: Union[str, Path], 
                    output_path: Union[str, Path],
                    style: Optional[SubtitleStyle] = None) -> str:
        """Altyazını video üzərinə cümlə-cümlə yandır."""
        try:
            video_path = Path(video_path).absolute()
            subtitle_path = Path(subtitle_path).absolute()
            output_path = Path(output_path).absolute()
            
            if not video_path.exists():
                raise FileNotFoundError(f"Video fayl tapılmadı: {video_path}")
            if not subtitle_path.exists():
                raise FileNotFoundError(f"Altyazı faylı tapılmadı: {subtitle_path}")
            
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # SRT faylını cümlələrə böl və hər biri üçün ASS faylı yarat
            ass_files = self._split_srt_to_ass_files(subtitle_path, style)
            
            # Müvəqqəti video faylı üçün yol
            temp_video_path = Path(self.config['temp_dir']) / f"temp_video.mp4"
            shutil.copy(video_path, temp_video_path)
            
            # Hər bir ASS faylını videoya əlavə et
            for ass_path in ass_files:
                # Subtitle filter hazırla
                subtitle_filter = self._prepare_subtitle_filter(ass_path, style)
                
                # FFmpeg əmri
                ffmpeg_cmd = [
                    self.config['ffmpeg_path'],
                    '-i', str(temp_video_path),
                    '-vf', subtitle_filter,
                    '-c:v', 'libx264',  # H.264 codec
                    '-preset', 'medium',  # Sürət/keyfiyyət balansı
                    '-crf', '23',  # Keyfiyyət (0-51, aşağı=yaxşı)
                    '-c:a', 'copy',  # Audio-nu kopyala
                    '-y', str(output_path)
                ]
                
                self.logger.info(f"FFmpeg əmri işə salınır: {' '.join(ffmpeg_cmd)}")
                result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
                
                if result.returncode != 0:
                    raise Exception(f"FFmpeg xətası: {result.stderr}")
                
                # Növbəti iterasiya üçün çıxış faylını müvəqqəti video faylı kimi istifadə et
                shutil.copy(output_path, temp_video_path)
            
            # Müvəqqəti video faylını sil
            temp_video_path.unlink()
            
            return str(output_path)
            
        except Exception as e:
            self.logger.error(f"Altyazı yandırma xətası: {str(e)}")
            raise


    def add_soft_subtitles(self,
                          video_path: Union[str, Path],
                          subtitle_path: Union[str, Path],
                          output_path: Union[str, Path],
                          language: str = 'aze') -> str:
        """Yumşaq altyazı əlavə et"""
        try:
            video_path = Path(video_path).absolute()
            subtitle_path = Path(subtitle_path).absolute()
            output_path = Path(output_path).absolute()
            
            if not video_path.exists():
                raise FileNotFoundError(f"Video fayl tapılmadı: {video_path}")
            if not subtitle_path.exists():
                raise FileNotFoundError(f"Altyazı faylı tapılmadı: {subtitle_path}")
            
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            ffmpeg_cmd = [
                self.config['ffmpeg_path'],
                '-i', str(video_path),
                '-i', str(subtitle_path),
                '-c', 'copy',
                '-c:s', 'mov_text',
                '-metadata:s:s:0', f'language={language}',
                '-y', str(output_path)
            ]
            
            self.logger.info(f"FFmpeg əmri işə salınır: {' '.join(ffmpeg_cmd)}")
            result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                raise Exception(f"FFmpeg xətası: {result.stderr}")
            
            return str(output_path)
            
        except Exception as e:
            self.logger.error(f"Yumşaq altyazı əlavə etmə xətası: {str(e)}")
            raise
# SubtitleBurner yaradılması
burner = SubtitleBurner()

# Xüsusi stil təyin etmək
style = SubtitleStyle(
    font="Arial",
    bold=True,
    outline_width=3,
    shadow_depth=2,
    margin_v=25,
    border_style=4,
    wrap_style=1
)

# Altyazı yandırma
result = burner.burn_subtitles(
    video_path=r"C:\Users\ramal\OneDrive\Desktop\az_dubbing\ss.mp4",
    subtitle_path=r"C:\Users\ramal\OneDrive\Desktop\az_dubbing\output\session_20250207_011535\output\translated_subtitles.srt",
    output_path="output_video.mp4",
    style=style
)