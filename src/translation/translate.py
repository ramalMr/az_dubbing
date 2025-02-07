import logging
from pathlib import Path
from deep_translator import GoogleTranslator
from tqdm import tqdm
import time
import re

class SubtitleTranslator:
    def __init__(self):
        self.logger = logging.getLogger('subtitle_translator')
        self.translator = GoogleTranslator(source='en', target='az')
        
    def read_srt(self, srt_path: str) -> list:
        """SRT faylını oxu və parse et"""
        with open(srt_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # SRT bloklarını ayır
        blocks = content.strip().split('\n\n')
        parsed_subs = []
        
        for block in blocks:
            lines = block.split('\n')
            if len(lines) >= 3:  # Minimal valid block
                try:
                    sub = {
                        'index': int(lines[0]),
                        'time': lines[1],
                        'text': '\n'.join(lines[2:])
                    }
                    parsed_subs.append(sub)
                except ValueError as e:
                    self.logger.warning(f"Blok parse edilə bilmədi: {block}")
                    
        return parsed_subs
    
    def translate_text(self, text: str, retry_count: int = 3) -> str:
        """Mətni tərcümə et (təkrar cəhdlərlə)"""
        for attempt in range(retry_count):
            try:
                # Xüsusi simvolları qoru
                placeholders = {}
                text_to_translate = text
                
                # HTML teqləri və digər xüsusi simvolları qoru
                html_tags = re.findall(r'<[^>]+>', text)
                for i, tag in enumerate(html_tags):
                    placeholder = f'__TAG{i}__'
                    text_to_translate = text_to_translate.replace(tag, placeholder)
                    placeholders[placeholder] = tag
                
                # Tərcümə et
                translated = self.translator.translate(text_to_translate)
                
                # Xüsusi simvolları bərpa et
                for placeholder, original in placeholders.items():
                    translated = translated.replace(placeholder, original)
                
                return translated
                
            except Exception as e:
                if attempt == retry_count - 1:
                    self.logger.error(f"Tərcümə xətası: {str(e)}")
                    return text  # Xəta halında original mətni qaytar
                time.sleep(1)  # Növbəti cəhddən əvvəl gözlə
    
    def translate_subtitles(self, srt_path: str, output_path: str = None) -> None:
        """SRT faylını tərcümə et və yeni fayl yarat"""
        # Output path-i müəyyən et
        if output_path is None:
            output_path = str(Path(srt_path).with_suffix('')) + '_az.srt'
            
        # SRT faylını oxu
        subs = self.read_srt(srt_path)
        self.logger.info(f"Oxundu: {len(subs)} altyazı bloku")
        
        # Hər bloku tərcümə et
        translated_subs = []
        for sub in tqdm(subs, desc="Altyazılar tərcümə edilir"):
            translated_text = self.translate_text(sub['text'])
            translated_subs.append({
                'index': sub['index'],
                'time': sub['time'],
                'text': translated_text
            })
            time.sleep(0.5)  # Rate limiting-dən qaçmaq üçün
            
        # Tərcümə edilmiş altyazıları yaz
        with open(output_path, 'w', encoding='utf-8') as f:
            for sub in translated_subs:
                f.write(f"{sub['index']}\n")
                f.write(f"{sub['time']}\n")
                f.write(f"{sub['text']}\n\n")
                
        self.logger.info(f"Tərcümə tamamlandı. Nəticə faylı: {output_path}")