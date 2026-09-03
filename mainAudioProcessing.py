# from audioProcess.audioProcessing import AudioProcessor
# from audioProcess.metrics import AudioMetrics, VADConfig, STFTConfig, PSDConfig
# import numpy as np

# atcVoiceMp3Path = "downloads\\sbrf\\ACC\\LiveATC-20260208T125151Z-1-001\\LiveATC\\SBRF-ACC-Feb-04-2026-1600Z.mp3"
# ap = AudioProcessor(atcVoiceMp3Path)

# x0 = ap.input_audio
# sr = ap.sample_audio_rate

# # 1) Bandpass (mantém)
# x1 = ap.bandPassFilterFir(250, 3400)

# # 2) Wiener (mantém, mas considere testar parâmetros depois)
# x2 = ap.wiener_minstat_denoise(x1, sr)

# # 3) Neural com OLA (troca o chunked simples pelo OLA)
# x3 = ap._enhance_neural_chunked(x2, sr, strategy="complex",
#                                 chunk_seconds=20, overlap_seconds=0.5)

# # 4) Low-pass pós-neural p/ conter HF artefato (NOVO)
# x3_lp = AudioProcessor.lowPassOn(x3, sr, cutoff_hz=3800.0, order=6)

# # 5) VAD soft attenuation (NOVO, substitui atten_db=80)
# x4, segments, frame_flags = ap.vadAttenuateSoft(
#     x3_lp, sr,
#     frame_ms=20, mode=2, hang_ms=250,
#     atten_db=25.0, floor_db=-60.0, fade_ms=10
# )

# # cria máscara por amostra para normalização speech-aware
# frame_len = int(sr * 20 / 1000)
# mask_samples = np.repeat(frame_flags, frame_len)[:len(x4)]

# # 6) Normalização baseada na fala (NOVO)
# x5_norm, gain = ap.loudnessNormalizeSpeechAware(
#     x4, sr, speech_mask_samples=mask_samples,
#     target_dbfs=-20.0, max_gain_db=12.0, min_gain_db=-12.0
# )

# # Final para STT (16k)
# x5 = ap.resample_to_16k(x5_norm, sr)

# ap.writeFilteredAudio(
#     "downloads/sbrf/ACC/LiveATC-20260208T125151Z-1-001/LiveATC/SBRF-ACC-Feb-04-2026-1600Z_stt_ready.wav",
#     x5
# )

# # padroniza comprimento p/ ablation (opcional)
# N = len(x0)
# def fit_len(x):
#     x = np.asarray(x, dtype=np.float32)
#     return x[:N] if len(x) >= N else np.pad(x, (0, N - len(x)))

# # escolha de estágios (inclui x3_lp)
# x0, x1, x2, x3, x3_lp, x4, x5 = map(fit_len, [x0, x1, x2, x3, x3_lp, x4, x5])

# m = AudioMetrics(
#     sample_rate=16000,
#     vad_cfg=VADConfig(frame_ms=20, mode=2, hang_ms=250),
#     stft_cfg=STFTConfig(n_fft=512, hop=160, win=512),
#     psd_cfg=PSDConfig(nperseg=1024),
# )

# stages = [
#     ("raw", x0),
#     ("bandpass", x1),
#     ("wiener", x2),
#     ("neural_ola", x3),
#     ("neural_lp", x3_lp),
#     ("vad_soft", x4),
#     ("final", x5),
# ]

# df = m.evaluate_stages(stages)
# m.save_table(df, out_csv="results/audio_metrics.csv", out_tex="results/audio_metrics.tex")

# m.plot_wave_vad(x0, x5, out_path="results/figs/example_wave.png", title_prefix="SBRF-ACC ")
# m.plot_spectrograms(x0, x5, out_path="results/figs/example_spec.png", title_prefix="SBRF-ACC ")
# m.plot_noise_psd(x0, x5, out_path="results/figs/example_psd.png", title_prefix="SBRF-ACC ")

# AudioMetrics.plot_metrics_bar(
#     df,
#     out_path="results/figs/ablation.png",
#     metrics=["noiseBandReductionDb", "nsReductionDb", "snrProxyDeltaDb",
#              "speechLevelDeltaDb", "hfEnergyRatioOutIn", "speechBandFocusDelta"],
#     title="Ablation (raw -> stage)"
# )


from audioProcess.audioProcessing import AudioProcessor
from audioProcess.metrics import AudioMetrics
import librosa as lr
import os

atcVoiceMp3Path = "C:\\ReposGithub\\liveatc-downloader\\downloads\\sbrf\\ACC\\LiveATC-20260208T125151Z-1-001\\LiveATC\\SBRF-Twr-Feb-02-2026-1130Z.mp3"
audio_processor = AudioProcessor(atcVoiceMp3Path)

fir_filtered_audio = audio_processor.bandPassFilterFir(250, 3400)

wienerDenoised = audio_processor.wiener_minstat_denoise(fir_filtered_audio, audio_processor.sample_audio_rate)

neuralNoiseReduction = audio_processor._enhance_neural(wienerDenoised, audio_processor.sample_audio_rate, strategy="complex")

output_gate_fir, segments_fir, flags_fir = audio_processor.vadGate(neuralNoiseReduction, audio_processor.sample_audio_rate, frame_ms=30, mode=3, hang_ms=150, atten_db=80)
fir_norm, gain_fir = audio_processor.loudnessNormalizeAdaptive(output_gate_fir, audio_processor.sample_audio_rate, target_dbfs=-20.0, top_db=25.0)


resampled_audio_fir = audio_processor.resample_to_16k(fir_norm, audio_processor.sample_audio_rate)
output_path = "downloads\\sbrf\\ACC\\LiveATC-20260208T125151Z-1-001\\LiveATC\\SBRF-Twr-Feb-02-2026-1130Z_fir_fb_denoiser.wav"
os.makedirs(os.path.dirname(output_path), exist_ok=True)
audio_processor.writeFilteredAudio(output_path, resampled_audio_fir)

# Gera figuras (wave + VAD, spectrogramas e PSD) com eixo em Hz
x_in_16k = audio_processor.resample_to_16k(audio_processor.input_audio, audio_processor.sample_audio_rate)
x_out_16k = resampled_audio_fir
m = AudioMetrics(sample_rate=16000)
m.plot_wave_vad(x_in_16k, x_out_16k, out_path="results/figs/example_wave_hz.png", title_prefix="SBRF-ACC ")
m.plot_spectrograms(x_in_16k, x_out_16k, out_path="results/figs/example_spec_hz.png", title_prefix="SBRF-ACC ")
m.plot_noise_psd(x_in_16k, x_out_16k, out_path="results/figs/example_psd_hz.png", title_prefix="SBRF-ACC ")