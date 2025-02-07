import logging
from pathlib import Path
from datetime import datetime
import os
from typing import Optional
import json

class CustomLogger:
    def __init__(self, 
                 name: str, 
                 log_dir: str = "logs",
                 config: Optional[dict] = None):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Default konfiqurasiya
        self.config = {
            'log_level': logging.INFO,
            'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            'date_format': '%Y-%m-%d %H:%M:%S',
            'file_name_format': '%Y%m%d_%H%M%S',
            'max_file_size': 10 * 1024 * 1024,  # 10MB
            'backup_count': 5,
            'add_user_info': True,
            'add_process_info': True
        }
        
        if config:
            self.config.update(config)
        
        timestamp = datetime.utcnow().strftime(self.config['file_name_format'])
        self.log_file = self.log_dir / f"{name}_{timestamp}.log"
        
        self.logger = logging.getLogger(name)
        self.logger.setLevel(self.config['log_level'])
        
        self._setup_handlers()
        
        self._log_initial_info()

    def _setup_handlers(self):
        """Handler-ləri quraşdır"""
        file_handler = logging.FileHandler(self.log_file, encoding='utf-8')
        file_handler.setLevel(self.config['log_level'])
       
        console_handler = logging.StreamHandler()
        console_handler.setLevel(self.config['log_level'])
        
        formatter = logging.Formatter(
            self.config['format'],
            datefmt=self.config['date_format']
        )
        
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
    
        self.logger.handlers = []
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)

    def _log_initial_info(self):
        """İlkin sistem məlumatlarını loqla"""
        self.logger.info(f"Logger initialized: {self.log_file}")
        
        if self.config['add_user_info']:
            self.logger.info(f"User: {os.getenv('USERNAME', 'unknown')}")
        
        if self.config['add_process_info']:
            self.logger.info(f"Process ID: {os.getpid()}")
            self.logger.info(f"Working Directory: {os.getcwd()}")

    def get_logger(self):
        """Logger obyektini qaytar"""
        return self.logger

    def update_config(self, new_config: dict):
        """Konfiqurasiyanı yenilə"""
        self.config.update(new_config)
        self._setup_handlers()
        self.logger.setLevel(self.config['log_level'])

    def archive_logs(self, archive_dir: Optional[str] = None):
        """Köhnə log fayllarını arxivləşdir"""
        try:
            if archive_dir:
                archive_path = Path(archive_dir)
            else:
                archive_path = self.log_dir / "archive"
            
            archive_path.mkdir(parents=True, exist_ok=True)
        
            current_time = datetime.utcnow()
            for log_file in self.log_dir.glob("*.log"):
                try:
                    file_time = datetime.strptime(
                        log_file.stem.split('_')[-1],
                        self.config['file_name_format']
                    )
                    if (current_time - file_time).days > 30:
                        log_file.rename(archive_path / log_file.name)
                except ValueError:
                    continue
                    
        except Exception as e:
            self.logger.error(f"Log arxivləşdirmə xətası: {str(e)}")

    def get_recent_logs(self, n: int = 100) -> list:
        """Son N log yazısını qaytar"""
        try:
            with open(self.log_file, 'r', encoding='utf-8') as f:
                logs = f.readlines()
                return logs[-n:]
        except Exception as e:
            self.logger.error(f"Log oxuma xətası: {str(e)}")
            return []

    def export_logs_as_json(self, output_path: Optional[str] = None) -> str:
        """Log yazılarını JSON formatında export et"""
        try:
            if not output_path:
                output_path = self.log_file.with_suffix('.json')
            
            logs = []
            with open(self.log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        # Log formatını parse et
                        parts = line.split(' - ', 3)
                        if len(parts) >= 4:
                            logs.append({
                                'timestamp': parts[0],
                                'name': parts[1],
                                'level': parts[2],
                                'message': parts[3].strip()
                            })
                    except Exception:
                        continue
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(logs, f, ensure_ascii=False, indent=2)
            
            return str(output_path)
            
        except Exception as e:
            self.logger.error(f"Log export xətası: {str(e)}")
            raise