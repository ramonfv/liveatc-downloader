from audioProcess.audioProcessing import AudioProcessor

atcVoiceMp3Path = "downloads/sbrf/sbrf_12960/SBRF-App-12960-Jul-10-2025-0000Z.mp3"
audio_processor = AudioProcessor(atcVoiceMp3Path)

iir_filtered_audio = audio_processor.bandPassFilterFir(300, 3000)
iir_norm, gain_iir = audio_processor.loudnessNormalizeAdaptive(iir_filtered_audio, audio_processor.sample_audio_rate)
resampled_audio_iir = audio_processor.resample_to_16k(iir_norm, audio_processor.sample_audio_rate)
audio_processor.writeFilteredAudio("downloads/sbrf/sbrf_12960/SBRF-App-12960-Jul-10-2025-0000Z_iir.wav", resampled_audio_iir)


firFilteredAudio = audio_processor.bandPassFilterFir(300, 3000)
fir_norm, gainfir = audio_processor.loudnessNormalizeAdaptive(firFilteredAudio, audio_processor.sample_audio_rate)
resampled_audio_fir = audio_processor.resample_to_16k(fir_norm, audio_processor.sample_audio_rate)
audio_processor.writeFilteredAudio("downloads/sbrf/sbrf_12960/SBRF-App-12960-Jul-10-2025-0000Z_fir.wav", resampled_audio_fir)

