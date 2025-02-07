import asyncio
from pathlib import Path
import logging
import os
from datetime import datetime
import json

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def get_session_files(session_dir: Path) -> dict:
    """Session qovluğundan lazımi faylları tap"""
    try:
        files = {
            "transcript": None,
            "metadata": None,
            "session_metadata": None,
            "transcription_report": None
        }
        
        # Full transcript
        transcript_path = session_dir / "transcripts" / "full_transcript.srt"
        if transcript_path.exists():
            files["transcript"] = transcript_path
        
        # Metadata
        metadata_dir = session_dir / "metadata" 
        if metadata_dir.exists():
            session_metadata = metadata_dir / "session_metadata.json"
            if session_metadata.exists():
                files["session_metadata"] = session_metadata
                
            # Segment metadata fayllarını birləşdir
            segment_metadata = list(metadata_dir.glob("segment_*_metadata.json"))
            if segment_metadata:
                files["metadata"] = segment_metadata
        
        # Transcription report
        report_path = session_dir / "transcripts" / "transcript_metadata.json"
        if report_path.exists():
            files["transcription_report"] = report_path
            
        if not any(files.values()):
            raise FileNotFoundError(f"Lazımi fayllar tapılmadı: {session_dir}")
            
        return files
        
    except Exception as e:
        logger.error(f"Session faylları oxuma xətası: {str(e)}")
        raise

async def process_video():
    try:
        from src.translation.translate import SubtitleTranslator
        from src.audio.ttsengine import AdvancedTTSEngine
        from src.video.video_processor import VideoProcessor
        from src.video.subtitle_burner import SubtitleBurner

        # Session qovluğunu birbaşa təyin et
        session_dir = Path(r"C:\Users\ramal\OneDrive\Desktop\az_dubbing\output_20250207_035158\session_20250206_235207")
        logger.info(f"Session qovluğu: {session_dir}")

        # Lazımi faylları tap
        files = get_session_files(session_dir)
        logger.info("Session faylları tapıldı")

        # Yeni çıxış qovluğunu yarat
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_base = Path(f"output_{timestamp}")
        output_base.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"İşləmə qovluğu: {output_base}")

        if not files["transcript"].exists():
            raise FileNotFoundError(f"Transkripsiya faylı tapılmadı: {files['transcript']}")
        
        logger.info(f"Mövcud transkripsiya faylı istifadə ediləcək: {files['transcript']}")

        # 1. Tərcümə
        logger.info("Tərcümə başladı...")
        translator = SubtitleTranslator()
        translated_path = output_base / "translated_subtitles.srt"
        translator.translate_subtitles(str(files["transcript"]), str(translated_path))
        logger.info(f"Tərcümə tamamlandı: {translated_path}")

        # 2. TTS
        logger.info("Səsləndirmə başladı...")
        tts_engine = AdvancedTTSEngine()
        
        # Session metadata-nı istifadə et
        if files["session_metadata"]:
            metadata_path = files["session_metadata"]
        elif files["metadata"]:
            # Segment metadata fayllarını birləşdir
            combined_metadata = {
                "segments": []
            }
            for segment_file in files["metadata"]:
                with open(segment_file, 'r', encoding='utf-8') as f:
                    segment_data = json.load(f)
                    combined_metadata["segments"].append(segment_data)
                    
            combined_metadata_path = output_base / "combined_metadata.json"
            with open(combined_metadata_path, 'w', encoding='utf-8') as f:
                json.dump(combined_metadata, f, ensure_ascii=False, indent=2)
            metadata_path = combined_metadata_path
        else:
            raise FileNotFoundError("Metadata faylı tapılmadı!")

        tts_output = await tts_engine.process_movie(
            srt_path=str(translated_path),
            metadata_path=str(metadata_path),
            output_dir=str(output_base / "audio")
        )
        logger.info("Səsləndirmə tamamlandı")

        # 3. Video prosesləmə
        video_processor = VideoProcessor()
        
        # 3.1 Altyazı əlavə et
        subtitle_burner = SubtitleBurner()
        subtitled_video = subtitle_burner.burn_subtitles(
            video_path="ss.mp4",
            subtitle_path=translated_path,
            output_path=output_base / "subtitled_video.mp4"
        )
        logger.info(f"Altyazı əlavə edildi: {subtitled_video}")

        # 3.2 Final video - səs və altyazı ilə
        logger.info("Final video hazırlanır...")
        final_video = video_processor.merge_audio_segments_with_video(
            video_path="ss.mp4",
            audio_segments=tts_output,
            output_path=output_base / "final_dubbed_video.mp4",
            keep_original_audio=True,
            original_audio_volume=0.1
        )
        logger.info(f"Final video hazır: {final_video}")

        return {
            "output_dir": str(output_base),
            "original_transcript": str(files["transcript"]),
            "translated_subtitles": str(translated_path),
            "subtitled_video": str(subtitled_video),
            "final_video": str(final_video)
        }

    except Exception as e:
        logger.error(f"Xəta baş verdi: {str(e)}")
        raise

if __name__ == "__main__":
    try:
        print("\nProsess başladı...")
        print(f"İşləmə tarixi: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"İstifadəçi: {os.getenv('USERNAME')}")
        print(f"İşləmə qovluğu: {os.getcwd()}")
        print("-" * 50)
        
        result = asyncio.run(process_video())
        
        print("\nProsess uğurla tamamlandı!")
        print("\nYaradılan fayllar:")
        print(f"1. İstifadə edilən transkripsiya: {result['original_transcript']}")
        print(f"2. Tərcümə edilmiş altyazılar: {result['translated_subtitles']}")
        print(f"3. Altyazılı video: {result['subtitled_video']}")
        print(f"4. Final dublyaj video: {result['final_video']}")
        
    except Exception as e:
        print(f"\nXəta: {str(e)}")
        logging.error("Detallı xəta:", exc_info=True)