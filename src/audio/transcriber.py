import stable_whisper
import torch
import logging
from pathlib import Path
from pydub import AudioSegment, silence
import numpy as np
from tqdm import tqdm
import librosa
import soundfile as sf
from transformers import pipeline
import json
import wave
import contextlib
import os
from datetime import datetime

class AdvancedTranscriber:
    def __init__(self, config_path: str = None):
        self.logger = logging.getLogger('transcriber')
        self.setup_config(config_path)
        self.setup_models()
        self.session_id = datetime.utcnow().strftime('%Y%m%d_%H%M%S')

    def setup_config(self, config_path: str):
        if config_path and Path(config_path).exists():
            with open(config_path, 'r') as f:
                self.config = json.load(f)
        else:
            self.config = {
                'whisper_model': 'base',
                'sample_rate': 16000,
                'chunk_duration': 30,
                'overlap_duration': 1,
                'silence_threshold': -35,
                'min_silence_duration': 500,
                'export_formats': ['wav', 'mp3'],
                'vad': {
                    'threshold': 0.5,
                    'min_speech_duration_ms': 250,
                    'min_silence_duration_ms': 100
                },
                'speaker_detection': {
                    'pitch_threshold': 0.1,
                    'min_confidence': 0.6,
                    'features': {
                        'use_pitch': True,
                        'use_energy': True,
                        'use_spectral': True
                    }
                }
            }

    def setup_models(self):
        """Initialize all required models"""
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.logger.info(f"Using device: {self.device}")
        
        # Whisper model
        try:
            self.whisper_model = stable_whisper.load_faster_whisper(
                self.config['whisper_model']
            )
            self.logger.info("Whisper model loaded successfully")
        except Exception as e:
            self.logger.error(f"Error loading Whisper model: {str(e)}")
            raise

        try:
            self.speaker_detector = pipeline(
                "audio-classification",
                model="alefiury/wav2vec2-large-xlsr-53-gender-recognition-librispeech",
                device=self.device
            )
            self.logger.info("model ugurla add olundu")
        except Exception as e:
            self.logger.error(f"Error spiker modeli: {str(e)}")
            raise

    def detect_speaker_characteristics(self, audio_path: str) -> dict:
        try:
            gender_result = self.speaker_detector(audio_path)
            gender = gender_result[0]["label"]
            gender_confidence = gender_result[0]["score"]
            
            y, sr = librosa.load(audio_path, sr=self.config['sample_rate'])
            
            pitches, magnitudes = librosa.piptrack(y=y, sr=sr)
            significant_pitches = pitches[magnitudes > np.max(magnitudes)*0.1]
            pitch_mean = np.mean(significant_pitches) if len(significant_pitches) > 0 else 0
            
            voice_profile = {
                "gender": gender,
                "gender_confidence": float(gender_confidence),
                "pitch": float(pitch_mean),
                "energy": float(np.mean(librosa.feature.rms(y=y))),
                "voice_features": {
                    "zero_crossing_rate": float(np.mean(librosa.feature.zero_crossing_rate(y))),
                    "spectral_centroid": float(np.mean(librosa.feature.spectral_centroid(y=y, sr=sr))),
                    "spectral_rolloff": float(np.mean(librosa.feature.spectral_rolloff(y=y, sr=sr)))
                }
            }
            
            # Speaker classification
            if gender == "male":
                if pitch_mean < 120:
                    voice_profile["voice_type"] = "bass"
                elif pitch_mean < 150:
                    voice_profile["voice_type"] = "baritone"
                else:
                    voice_profile["voice_type"] = "tenor"
            else:  # female
                if pitch_mean < 200:
                    voice_profile["voice_type"] = "contralto"
                elif pitch_mean < 250:
                    voice_profile["voice_type"] = "mezzo-soprano"
                else:
                    voice_profile["voice_type"] = "soprano"
            
            self.logger.info(
                f"Speaker detected: {gender} ({voice_profile['voice_type']}) "
                f"with {gender_confidence:.2f} confidence"
            )
            return voice_profile
            
        except Exception as e:
            self.logger.error(f"Error in speaker detection: {str(e)}")
            return {
                "gender": "unknown",
                "gender_confidence": 0.0,
                "voice_type": "unknown",
                "pitch": 0.0,
                "energy": 0.0,
                "voice_features": {
                    "zero_crossing_rate": 0.0,
                    "spectral_centroid": 0.0,
                    "spectral_rolloff": 0.0
                }
            }
    def process_audio(self, audio_path: str, output_dir: str) -> dict:
        self.logger.info(f"Starting audio processing: {audio_path}")
        
        output_paths = self.create_output_structure(output_dir)
        
        audio = AudioSegment.from_file(audio_path)
        
        chunks = self.split_on_silence(audio)
        
        processed_segments = []
        current_time = 0
        
        for i, chunk in enumerate(tqdm(chunks, desc="Processing segments")):
            if len(chunk) < 500:  # qisalar i kec
                current_time += len(chunk) / 1000
                continue
                
            segment_info = self.process_audio_segment(
                chunk, current_time, output_paths, i
            )
            processed_segments.append(segment_info)
            
            current_time += len(chunk) / 1000
            
        patterns = self.analyze_speech_patterns(processed_segments)
        
        session_metadata = {
            "session_id": self.session_id,
            "processed_date": datetime.utcnow().isoformat(),
            "input_file": str(audio_path),
            "total_segments": len(processed_segments),
            "total_duration": sum(s["duration"] for s in processed_segments),
            "speech_patterns": patterns,
            "segments": processed_segments
        }
        
        metadata_path = output_paths['metadata'] / "session_metadata.json"
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(session_metadata, f, ensure_ascii=False, indent=2)
            
        self.generate_transcripts(processed_segments, output_paths['transcripts'])
        
        self.logger.info(f"Processing completed. {len(processed_segments)} segments processed.")
        return session_metadata

    def create_output_structure(self, base_dir: str) -> dict:
        """Create organized output directory structure"""
        paths = {
            'base': Path(base_dir) / f"session_{self.session_id}",
            'audio': Path(base_dir) / f"session_{self.session_id}" / "audio_segments",
            'metadata': Path(base_dir) / f"session_{self.session_id}" / "metadata",
            'transcripts': Path(base_dir) / f"session_{self.session_id}" / "transcripts",
            'analysis': Path(base_dir) / f"session_{self.session_id}" / "analysis"
        }
        
        for path in paths.values():
            path.mkdir(parents=True, exist_ok=True)
            
        paths['male_speakers'] = paths['audio'] / "male_speakers"
        paths['female_speakers'] = paths['audio'] / "female_speakers"
        paths['unknown_speakers'] = paths['audio'] / "unknown_speakers"
        
        for path in [paths['male_speakers'], paths['female_speakers'], paths['unknown_speakers']]:
            path.mkdir(parents=True, exist_ok=True)
            
        return paths

    def split_on_silence(self, audio_segment: AudioSegment) -> list:
        """Split audio on silence more intelligently"""
        try:
            self.logger.info(f"Splitting audio of length {len(audio_segment)}ms")
            
            normalized_audio = audio_segment.normalize(headroom=0.1)
            
            min_silence_len = 500  # 500ms
            silence_thresh = -40  # dB
            keep_silence = 300  # 300ms
            
            chunks = silence.split_on_silence(
                normalized_audio,
                min_silence_len=min_silence_len,
                silence_thresh=silence_thresh,
                keep_silence=keep_silence
            )
            
            if not chunks:
                self.logger.warning("No silence detected, splitting into fixed-length chunks")
                chunk_length = 30 * 1000  # 30 saniyə
                chunks = [
                    normalized_audio[i:i + chunk_length] 
                    for i in range(0, len(normalized_audio), chunk_length)
                ]
            
            self.logger.info(f"Split audio into {len(chunks)} chunks")
            
            filtered_chunks = [chunk for chunk in chunks if len(chunk) > 1000]  # 1 saniyədən uzun
            
            if not filtered_chunks:
                self.logger.warning("chunks after flitering")
                return [normalized_audio]
                
            self.logger.info(f"Final chunk count: {len(filtered_chunks)}")
            return filtered_chunks
            
        except Exception as e:
            self.logger.error(f"Error splitting audio: {str(e)}")
            return [audio_segment]
    def process_audio_segment(self, segment: AudioSegment, 
                            start_time: int,
                            output_paths: dict,
                            segment_index: int) -> dict:
        """Process and export a single audio segment"""
        temp_path = Path("temp_segment.wav")
        segment.export(str(temp_path), format="wav")
        
        try:
            result = self.whisper_model.transcribe_stable(str(temp_path))
            
            speaker_info = self.detect_speaker_characteristics(str(temp_path))
            
            if speaker_info['gender'] == 'male':
                output_dir = output_paths['male_speakers']
            elif speaker_info['gender'] == 'female':
                output_dir = output_paths['female_speakers']
            else:
                output_dir = output_paths['unknown_speakers']
                
            base_filename = f"segment_{segment_index:04d}"
            segment_path = output_dir / base_filename
            
            exported_files = {}
            for fmt in self.config['export_formats']:
                output_file = segment_path.with_suffix(f".{fmt}")
                segment.export(str(output_file), format=fmt)
                exported_files[fmt] = str(output_file)
            
            duration = len(segment) / 1000.0
            end_time = start_time + duration
            
            segment_info = {
                "segment_id": segment_index,
                "start_time": start_time,
                "end_time": end_time,
                "duration": duration,
                "text": result.text.strip() if hasattr(result, 'text') else "",
                "speaker": speaker_info,
                "confidence": getattr(result, 'confidence', 1.0),
                "files": exported_files,
                "words": getattr(result, 'word_timestamps', None)
            }
            
            metadata_path = output_paths['metadata'] / f"{base_filename}_metadata.json"
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(segment_info, f, ensure_ascii=False, indent=2)
                
            return segment_info
            
        finally:
            if temp_path.exists():
                temp_path.unlink()

    def analyze_speech_patterns(self, segments: list) -> dict:
        try:
            total_duration = 0
            gender_counts = {"male": 0, "female": 0, "unknown": 0}
            gender_durations = {"male": 0, "female": 0, "unknown": 0}
            pitch_data = []
            energy_data = []
            speech_rate_data = []
            segment_durations = []
            
            for segment in segments:
                duration = segment["duration"]
                total_duration += duration
                segment_durations.append(duration)
                
                gender = segment["speaker"]["gender"]
                gender_counts[gender] += 1
                gender_durations[gender] += duration
                
                if "pitch" in segment["speaker"]:
                    pitch_data.append(segment["speaker"]["pitch"])
                if "energy" in segment["speaker"]:
                    energy_data.append(segment["speaker"]["energy"])
                if "speech_rate" in segment["speaker"]:
                    speech_rate_data.append(segment["speaker"]["speech_rate"])
            
            patterns = {
                "total_duration": total_duration,
                "total_segments": len(segments),
                "gender_distribution": {
                    "counts": gender_counts,
                    "durations": gender_durations,
                    "percentages": {
                        gender: (count / len(segments) * 100) 
                        for gender, count in gender_counts.items()
                    }
                },
                "segment_statistics": {
                    "average_duration": float(np.mean(segment_durations)),
                    "min_duration": float(np.min(segment_durations)),
                    "max_duration": float(np.max(segment_durations)),
                    "std_duration": float(np.std(segment_durations))
                }
            }
            
            if pitch_data:
                patterns["voice_characteristics"] = {
                    "pitch": {
                        "mean": float(np.mean(pitch_data)),
                        "std": float(np.std(pitch_data)),
                        "min": float(np.min(pitch_data)),
                        "max": float(np.max(pitch_data))
                    }
                }
            
            if energy_data:
                if "voice_characteristics" not in patterns:
                    patterns["voice_characteristics"] = {}
                patterns["voice_characteristics"]["energy"] = {
                    "mean": float(np.mean(energy_data)),
                    "std": float(np.std(energy_data)),
                    "min": float(np.min(energy_data)),
                    "max": float(np.max(energy_data))
                }
            
            if speech_rate_data:
                if "voice_characteristics" not in patterns:
                    patterns["voice_characteristics"] = {}
                patterns["voice_characteristics"]["speech_rate"] = {
                    "mean": float(np.mean(speech_rate_data)),
                    "std": float(np.std(speech_rate_data)),
                    "min": float(np.min(speech_rate_data)),
                    "max": float(np.max(speech_rate_data))
                }
            
            return patterns
            
        except Exception as e:
            self.logger.error(f"Error in speech pattern analysis: {str(e)}")
            return {
                "error": str(e),
                "total_segments": len(segments),
                "status": "failed"
            }

    def generate_transcripts(self, segments: list, transcript_dir: Path):
        """
        Hər danışan üçün ayrı transkript yaradır və ətraflı metadata əlavə edir.
        """
        try:
            transcript_dir = Path(transcript_dir)
            transcript_dir.mkdir(parents=True, exist_ok=True)
            
            if not segments:
                self.logger.warning("No segments to transcribe!")
                return

            # Metadata hazırla
            metadata = {
                "creation_date": datetime.utcnow().isoformat(),
                "user": os.getenv('USERNAME', 'unknown'),
                "total_duration": sum(s['duration'] for s in segments),
                "total_segments": len(segments),
                "speakers": {}
            }

            speakers_segments = {}
            for segment in segments:
                speaker_info = segment['speaker']
                speaker_id = f"speaker_{speaker_info['gender']}_{len(speakers_segments) + 1}"
                
                if speaker_id not in speakers_segments:
                    speakers_segments[speaker_id] = {
                        "segments": [],
                        "voice_type": speaker_info.get('voice_type', 'unknown'),
                        "gender": speaker_info['gender'],
                        "gender_confidence": speaker_info['gender_confidence'],
                        "total_duration": 0,
                        "pitch_mean": speaker_info.get('pitch', 0)
                    }
                
                speakers_segments[speaker_id]["segments"].append(segment)
                speakers_segments[speaker_id]["total_duration"] += segment['duration']

            for speaker_id, speaker_data in speakers_segments.items():
                speaker_dir = transcript_dir / speaker_id
                speaker_dir.mkdir(exist_ok=True)
                
                text_path = speaker_dir / f"{speaker_id}_transcript.txt"
                with open(text_path, 'w', encoding='utf-8') as f:
                    f.write(f"Speaker Information:\n")
                    f.write(f"Gender: {speaker_data['gender']}\n")
                    f.write(f"Voice Type: {speaker_data['voice_type']}\n")
                    f.write(f"Confidence: {speaker_data['gender_confidence']:.2f}\n")
                    f.write(f"Total Duration: {speaker_data['total_duration']:.2f} seconds\n")
                    f.write("-" * 50 + "\n\n")
                    
                    for segment in speaker_data["segments"]:
                        timestamp = f"[{self._format_timecode(segment['start_time'])} --> {self._format_timecode(segment['end_time'])}]"
                        f.write(f"{timestamp}\n{segment['text']}\n\n")

                # transkripsia to srt
                srt_path = speaker_dir / f"{speaker_id}_transcript.srt"
                with open(srt_path, 'w', encoding='utf-8') as f:
                    for i, segment in enumerate(speaker_data["segments"], 1):
                        start = self._format_timecode(segment['start_time'])
                        end = self._format_timecode(segment['end_time'])
                        f.write(f"{i}\n{start} --> {end}\n{segment['text']}\n\n")

                # Speakerin metadatasi
                metadata["speakers"][speaker_id] = {
                    "voice_type": speaker_data["voice_type"],
                    "gender": speaker_data["gender"],
                    "gender_confidence": speaker_data["gender_confidence"],
                    "total_duration": speaker_data["total_duration"],
                    "segments_count": len(speaker_data["segments"]),
                    "pitch_mean": speaker_data["pitch_mean"]
                }

            #all srt fayli
            full_srt_path = transcript_dir / "full_transcript.srt"
            with open(full_srt_path, 'w', encoding='utf-8') as f: 
                all_segments = []
                for speaker_data in speakers_segments.values():
                    all_segments.extend(speaker_data["segments"])
                
                all_segments.sort(key=lambda x: x['start_time'])
                
                for i, segment in enumerate(all_segments, 1):
                    start = self._format_timecode(segment['start_time'])
                    end = self._format_timecode(segment['end_time'])
                    speaker_info = f"[{segment['speaker']['gender']} - {segment['speaker'].get('voice_type', 'unknown')}]"
                    f.write(f"{i}\n{start} --> {end}\n{speaker_info} {segment['text']}\n\n")

            metadata_path = transcript_dir / "transcript_metadata.json"
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump({
                    "project_info": {
                        "creation_date": datetime.utcnow().isoformat(),
                        "user": os.getenv('USERNAME', 'unknown'),
                        "processing_time": datetime.utcnow().isoformat(),
                        "whisper_model": self.config['whisper_model'],
                        "sample_rate": self.config['sample_rate']
                    },
                    "audio_stats": {
                        "total_duration": metadata["total_duration"],
                        "total_segments": metadata["total_segments"],
                        "speakers_count": len(speakers_segments)
                    },
                    "speakers": metadata["speakers"],
                    "files": {
                        "full_transcript": str(full_srt_path),
                        "speaker_transcripts": {
                            speaker_id: {
                                "srt": str(transcript_dir / speaker_id / f"{speaker_id}_transcript.srt"),
                                "txt": str(transcript_dir / speaker_id / f"{speaker_id}_transcript.txt")
                            }
                            for speaker_id in speakers_segments.keys()
                        }
                    }
                }, f, ensure_ascii=False, indent=2)

            report_path = transcript_dir / "transcription_report.txt"
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write("Transcription Report\n")
                f.write("===================\n\n")
                f.write(f"Created: {datetime.utcnow().isoformat()}\n")
                f.write(f"User: {os.getenv('USERNAME', 'unknown')}\n")
                f.write(f"Total Duration: {metadata['total_duration']:.2f} seconds\n")
                f.write(f"Total Segments: {metadata['total_segments']}\n")
                f.write(f"Number of Speakers: {len(speakers_segments)}\n\n")
                
                f.write("Speaker Information:\n")
                f.write("-" * 50 + "\n")
                for speaker_id, data in metadata["speakers"].items():
                    f.write(f"\n{speaker_id}:\n")
                    f.write(f"  Gender: {data['gender']}\n")
                    f.write(f"  Voice Type: {data['voice_type']}\n")
                    f.write(f"  Confidence: {data['gender_confidence']:.2f}\n")
                    f.write(f"  Duration: {data['total_duration']:.2f} seconds\n")
                    f.write(f"  Segments: {data['segments_count']}\n")

            self.logger.info(f"Generated transcripts for {len(speakers_segments)} speakers")
            self.logger.info(f"Full report saved to: {report_path}")
            
            return {
                "metadata": metadata_path,
                "full_transcript": full_srt_path,
                "report": report_path,
                "speakers": speakers_segments
            }
            
        except Exception as e:
            self.logger.error(f"Error generating transcripts: {str(e)}")
            raise
    
    def _format_timecode(self, seconds: float) -> str:
        """srt timecode ye converte"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        seconds = seconds % 60
        milliseconds = int((seconds % 1) * 1000)
        seconds = int(seconds)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"

    def _detect_language(self, audio_path: str) -> str:
        """Auto dil askarlamaq"""
        try:
            result = self.whisper_model.transcribe_stable(
                audio_path,
                language=None  # Auto detect
            )
            detected_language = getattr(result, 'language', 'en')
            self.logger.info(f"Detected language: {detected_language}")
            return detected_language
        except Exception as e:
            self.logger.error(f"Language detection error: {str(e)}")
            return 'en'  # Default to English

    def cleanup(self):
        try:
           
            temp_files = Path('.').glob('temp_segment*.wav')
            for temp_file in temp_files:
                try:
                    temp_file.unlink()
                except Exception as e:
                    self.logger.warning(f"{temp_file}: {str(e)}")
                    
            self.logger.info("temizleme bittdi")
        except Exception as e:
            self.logger.error(f"xeta: {str(e)}")