from audioProcess.audioProcessing import AudioProcessor
from audioProcess.metrics import AudioMetrics
import librosa as lr

atcVoiceMp3Path = "downloads/sbrf/sbrf_12960/SBRF-App-12960-Jul-10-2025-0230Z.mp3"
audio_processor = AudioProcessor(atcVoiceMp3Path)

iir_filtered_audio = audio_processor.bandPassFilterFir(250, 3400)

output_gate_fir, segments_fir, flags_fir = audio_processor.vadGate(iir_filtered_audio, audio_processor.sample_audio_rate, frame_ms=30, mode=3, hang_ms=150, atten_db=80)
fir_norm, gain_fir = audio_processor.loudnessNormalizeAdaptive(output_gate_fir, audio_processor.sample_audio_rate, target_dbfs=-20.0, top_db=25.0)


resampled_audio_fir = audio_processor.resample_to_16k(fir_norm, audio_processor.sample_audio_rate)
audio_processor.writeFilteredAudio("downloads/sbrf/sbrf_12960/SBRF-App-12960-Jul-10-2025-0230Z_fir.wav", resampled_audio_fir)


# iirFilteredAudio = audio_processor.bandPassFilterIir(250, 3400)

# output_gate_iir, segments_iir, flags_iir = audio_processor.vadGate(iirFilteredAudio, audio_processor.sample_audio_rate, frame_ms=30, mode=3, hang_ms=150, atten_db=80)

# iir_norm, gainIir = audio_processor.loudnessNormalizeAdaptive(output_gate_iir, audio_processor.sample_audio_rate, target_dbfs=-20.0, top_db=25.0)


# resampled_audio_iir = audio_processor.resample_to_16k(iir_norm, audio_processor.sample_audio_rate)
# audio_processor.writeFilteredAudio("downloads/sbrf/sbrf_12960/SBRF-App-12960-Jul-10-2025-0230Z_iir.wav", resampled_audio_iir)

referenceAudio, referenceSampleRate = lr.load(atcVoiceMp3Path, sr=16000)

metrics = AudioMetrics(referenceSampleRate).audio_compare(referenceAudio, resampled_audio_fir)


for k, v in metrics.items():
    print(f"{k}: {v}")