import asyncio
import sys
from pathlib import Path
import argparse
from datetime import datetime

sys.path.append(str(Path(__file__).parent.parent))

from src.audio.transcriber import AdvancedTranscriber
from src.audio.ttsengine import AdvancedTTSEngine
from src.translation.translate import SubtitleTranslator
from src.video.video_processor import VideoProcessor
from src.video.subtitle_burner import SubtitleBurner, SubtitleStyle
from src.utils.logger import CustomLogger

def parse_args():
    parser = argparse.ArgumentParser(description="Video dublyaj sistemi")
    
    parser.add_argument(
        "video_path",
        type=str,
        help="Video faylının yolu"
    )
    
    parser.add_argument(
        "-o", "--output",
        type=str,
        default="output",
        help="Çıxış qovluğu"
    )
    
    parser.add_argument(
        "-c", "--config",
        type=str,
        help="Konfiqurasiya faylı"
    )
    
    parser.add_argument(
        "--gpu",
        action="store_true",
        help="GPU istifadə et"
    )
    
    parser.add_argument(
        "--subtitle-style",
        type=str,
        choices=["default", "modern", "classic"],
        default="modern",
        help="Altyazı stili"
    )
    
    return parser.parse_args()

def get_subtitle_style(style_name: str) -> SubtitleStyle:
    styles = {
        "default": SubtitleStyle(),
        "modern": SubtitleStyle(
            font="Arial",
            font_size=28,
            primary_color="white",
            outline_color="black",
            outline_width=1,
            bold=False,
            margin_v=20,
            margin_h=10
        ),
        "classic": SubtitleStyle(
            font="Arial",  # Changed to Arial for better readability
            font_size=26,
            primary_color="white",
            outline_color="black",
            outline_width=1,
            italic=False,
            margin_v=20,
            margin_h=10
        )
    }
    return styles.get(style_name, SubtitleStyle())
async def main():
    args = parse_args()
    
    logger = CustomLogger(
        name="video_dubbing",
        log_dir="logs"
    ).get_logger()

    try:
        logger.info("Dublyaj prosesi başladı...")
        logger.info(f"Video: {args.video_path}")
        logger.info(f"Çıxış qovluğu: {args.output}")

        video_path = Path(args.video_path)
        output_dir = Path(args.output)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Komponentləri inisializasiya et
        transcriber = AdvancedTranscriber(args.config)
        translator = SubtitleTranslator()
        tts_engine = AdvancedTTSEngine()
        video_processor = VideoProcessor()
        subtitle_burner = SubtitleBurner()

        # 1. Transkripsiya
        logger.info("Transkripsiya başladı...")
        transcript_result = transcriber.process_audio(
            str(video_path),
            str(output_dir)
        )
        
        # Session qovluğunu tap
        session_dir = list(output_dir.glob("session_*"))[0]
        transcript_path = session_dir / "transcripts" / "full_transcript.srt"
        
        # 2. Tərcümə
        logger.info("Tərcümə başladı...")
        translated_path = session_dir / "output" / "translated_subtitles.srt"
        translated_path.parent.mkdir(parents=True, exist_ok=True)
        
        translator.translate_subtitles(
            str(transcript_path),
            str(translated_path)
        )

        # 3. Səsləndirmə
        logger.info("Səsləndirmə başladı...")
        audio_dir = session_dir / "output" / "audio"
        audio_dir.mkdir(parents=True, exist_ok=True)
        
        audio_segments = await tts_engine.process_movie(
            srt_path=str(translated_path),
            metadata_path=str(session_dir / "metadata" / "session_metadata.json"),
            output_dir=str(audio_dir)
        )

        # 4. Video prosesləmə
        logger.info("Video prosesləmə başladı...")
        
        # 4.1 Altyazı əlavə et
        subtitle_style = get_subtitle_style(args.subtitle_style)
        subtitled_video = subtitle_burner.burn_subtitles(
            video_path=str(video_path),
            subtitle_path=str(translated_path),
            output_path=str(session_dir / "output" / "subtitled_video.mp4"),
            style=subtitle_style
        )

        # 4.2 Final video
        final_video = video_processor.merge_audio_segments_with_video(
            video_path=str(video_path),
            audio_segments=audio_segments,
            output_path=str(session_dir / "output" / "final_dubbed_video.mp4"),
            keep_original_audio=True,
            original_audio_volume=0.1
        )

        logger.info("\nProsess uğurla tamamlandı!")
        logger.info("\nYaradılan fayllar:")
        logger.info(f"1. Transkripsiya: {transcript_path}")
        logger.info(f"2. Tərcümə edilmiş altyazı: {translated_path}")
        logger.info(f"3. Altyazılı video: {subtitled_video}")
        logger.info(f"4. Final dublyaj video: {final_video}")

    except Exception as e:
        logger.error(f"Xəta baş verdi: {str(e)}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())