# import numpy as np
# import librosa as lr
# import webrtcvad


# class AudioMetrics:
#     def __init__(self, audio_data, sample_rate=16000):
#         self.audio_data = audio_data
#         self.sample_rate = sample_rate
#         self.EPS = 1e-12

#     def compute_rms(self, inputAudio):
#         return 20*np.log10(np.sqrt(np.mean(inputAudio**2) + self.EPS))


#     def _stft_mag2(self, inputAudio, n_fft=512, hop=128, win='hann'):
#         stft = lr.stft(inputAudio, n_fft=n_fft, hop_length=hop, window=win)
#         mag2 = np.abs(stft)**2
#         return mag2, stft
    
#     def _vad_flags(self, inputAudio, frame_ms=30, top_db=25):

#         frame_length = int(np.round(self.sample_rate * frame_ms / 1000))
#         num_frames = int(np.ceil(len(inputAudio) / frame_length))
#         flags = np.zeros(num_frames, dtype=bool)

#         vad = webrtcvad.Vad(2)
#         audio_int16 = (np.clip(inputAudio, -1.0, 1.0) * 32767).astype(np.int16)
#         for i in range(num_frames):
#             start = i * frame_length
#             stop = min((i + 1) * frame_length, len(audio_int16))
#             frame = np.zeros(frame_length, dtype=np.int16)
#             frame[:stop-start] = audio_int16[start:stop]
#             is_speech = vad.is_speech(frame.tobytes(), sample_rate=self.sample_rate)
#             flags[i] = is_speech
#         return flags, frame_length
    

#     def log_spectral_distance(self, audioReference, audioTarget, nFft=512, hop=128):

#         refStft = lr.stft(audioReference, n_fft=nFft, hop_length=hop)
#         targetStft = lr.stft(audioTarget, n_fft=nFft, hop_length=hop)

#         minLength = min(refStft.shape[1], targetStft.shape[1])
#         refStft = refStft[:, :minLength]
#         targetStft = targetStft[:, :minLength]

#         refStftMaximun = np.maximum(np.abs(refStft), self.EPS)
#         targetStftMaximun = np.maximum(np.abs(targetStft), self.EPS)

#         diffDb = 20*np.log10(refStftMaximun) - 20*np.log10(targetStftMaximun)

#         lsdT = np.sqrt(np.mean(diffDb**2, axis=0))

#         return float(np.mean(lsdT)), float(np.median(lsdT) )


#     def mfcc_dist(self, audioReference, audioTarget, nMfcc=13, hop=256):

#         mfccRef = lr.feature.mfcc(y=audioReference, sr=self.sample_rate, n_mfcc=nMfcc, hop_length=hop)
#         mfccTarget = lr.feature.mfcc(y=audioTarget, sr=self.sample_rate, n_mfcc=nMfcc, hop_length=hop)

#         minLength = min(mfccRef.shape[1], mfccTarget.shape[1])
#         mfccRef = mfccRef[:, :minLength]
#         mfccTarget = mfccTarget[:, :minLength]

#         distance = np.linalg.norm(mfccRef - mfccTarget, axis=0)

#         return float(np.mean(distance)), float(np.median(distance))
    

#     def snr_estimate_from_nonspeech(self, audioNonspeech, audioSpeech, frameMs=30, nFFT=512, hop=128):

#         flags, frameLength = self._vad_flags(audioNonspeech, frameMs)
#         mask = np.repeat(flags, frameLength)[:len(audioNonspeech)]

#         pninput, _ = self._stft_mag2(audioNonspeech, n_fft=nFFT, hop=hop)
#         psoutput, _ = self._stft_mag2(audioSpeech,    n_fft=nFFT, hop=hop)

#         frameLength = min(pninput.shape[1], psoutput.shape[1], int(np.ceil(len(mask)/hop)))
#         frameMsStft = 1000.0 * hop / self.sample_rate
#         speechFrames = []

#         for frame in range(frameLength):
#             idx = int(round((frame * frameMsStft) / frameMs))
#             idx = min(idx, len(flags) - 1)
#             if flags[idx]:
#                 speechFrames.append(frame)

#         monoSpeechFrames = list(set(range(frameLength)) - set(speechFrames))

#         if len(monoSpeechFrames) == 0 or len(speechFrames) == 0:
#             return None, None, None

#         noiseProfile = np.mean(pninput[:, monoSpeechFrames], axis=1, keepdims=True) + self.EPS
#         Npow = float(np.sum(noiseProfile))

#         snrInput = []
#         snrOutput = []
#         for frame in speechFrames:
#             psInput  = float(np.sum(pninput[:, frame]))
#             psOutput = float(np.sum(psoutput[:, frame]))
#             snrInput.append( 10 * np.log10((psInput  + self.EPS) / Npow) )
#             snrOutput.append(10 * np.log10((psOutput + self.EPS) / Npow) )

#         snrInput  = float(np.mean(snrInput))
#         snrOutput = float(np.mean(snrOutput))
#         return snrInput, snrOutput, (snrOutput - snrInput)


#     def audio_compare(self, referenceAudio, processedAudio):

#         numFrames = min(len(referenceAudio), len(processedAudio))
#         referenceAudioOutput = np.asarray(referenceAudio[:numFrames], dtype=float)
#         processedAudioOutput = np.asarray(processedAudio[:numFrames], dtype=float)

#         maxDiff = max(np.max(np.abs(referenceAudioOutput)), np.max(np.abs(processedAudioOutput)), 1.0)

#         referenceAudioOutput /= maxDiff
#         processedAudioOutput /= maxDiff

#         flags, frameLength = self._vad_flags(referenceAudio)
#         mask = np.repeat(flags, frameLength)[:len(referenceAudioOutput)]
#         nsInput = referenceAudioOutput[~mask] if np.any(~mask) else referenceAudioOutput[:0]
#         nsOutput = processedAudioOutput[~mask] if np.any(~mask) else processedAudioOutput[:0]
#         nsRmsInputDb = self.compute_rms(nsInput) if len(nsInput) > 0 else None
#         nsRmsOutputDb = self.compute_rms(nsOutput) if len(nsOutput) > 0 else None
#         nsReductionDb = (nsRmsInputDb - nsRmsOutputDb) if nsRmsInputDb is not None and nsRmsOutputDb is not None else None

#         spInput = referenceAudioOutput[mask] if np.any(mask) else referenceAudioOutput[:0]
#         spOutput = processedAudioOutput[mask] if np.any(mask) else processedAudioOutput[:0]
#         spRmsInputDb = self.compute_rms(spInput) if len(spInput) > 0 else None
#         spRmsOutputDb = self.compute_rms(spOutput) if len(spOutput) > 0 else None
#         speechLevelDeltaDb = (spRmsInputDb - spRmsOutputDb) if spRmsInputDb is not None and spRmsOutputDb is not None else None

#         snrInput, snrOutput, snrDelta = self.snr_estimate_from_nonspeech(referenceAudioOutput, processedAudioOutput)

#         lsdMeanDb, lsdMedDb = self.log_spectral_distance(referenceAudioOutput, processedAudioOutput)
#         mfccMean, mfccMed = self.mfcc_dist(referenceAudioOutput, processedAudioOutput)

#         return {
#             "nsRmsInputDb": nsRmsInputDb,
#             "nsRmsOutputDb": nsRmsOutputDb,
#             "nsReductionDb": nsReductionDb,
#             "spRmsInputDb": spRmsInputDb,
#             "spRmsOutputDb": spRmsOutputDb,
#             "speechLevelDeltaDb": speechLevelDeltaDb,
#             "snrInput": snrInput,
#             "snrOutput": snrOutput,
#             "snrDelta": snrDelta,
#             "lsdMeanDb": lsdMeanDb,
#             "lsdMedDb": lsdMedDb,
#             "mfccMean": mfccMean,
#             "mfccMed": mfccMed
#         }


# metrics.py
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np
import librosa as lr
import webrtcvad
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from scipy.signal import welch

EPS = 1e-12


@dataclass
class VADConfig:
    frame_ms: int = 30          # 10,20,30
    mode: int = 2               # 0..3 (agressividade)
    hang_ms: int = 150          # suavização (closing)
    min_speech_ms: int = 0      # opcional (filtrar segmentos curtos)


@dataclass
class STFTConfig:
    n_fft: int = 512
    hop: int = 160
    win: int = 512
    window: str = "hann"


@dataclass
class PSDConfig:
    nperseg: int = 1024


class AudioMetrics:
    """
    Avaliação no-reference para melhoria de áudio em pipeline (ATC/RTF):
    - separação speech / non-speech via VAD (máscara fixa derivada do INPUT)
    - métricas de piso de ruído, SNR proxy, preservação de fala
    - proxies espectrais: band energies, spectral flatness, HF loss
    - visualizações e exportação de tabelas
    """

    def __init__(self, sample_rate: int = 16000,
                 vad_cfg: VADConfig = VADConfig(),
                 stft_cfg: STFTConfig = STFTConfig(),
                 psd_cfg: PSDConfig = PSDConfig()):
        self.sr = int(sample_rate)
        self.vad_cfg = vad_cfg
        self.stft_cfg = stft_cfg
        self.psd_cfg = psd_cfg

    # ---------------------------
    # Utilitários básicos
    # ---------------------------
    @staticmethod
    def _ensure_float_mono(x: np.ndarray) -> np.ndarray:
        x = np.asarray(x)
        if x.ndim == 2:
            x = np.mean(x, axis=0)
        return x.astype(np.float32, copy=False)

    @staticmethod
    def peak(x: np.ndarray) -> float:
        return float(np.max(np.abs(x)) + EPS)

    @staticmethod
    def rms(x: np.ndarray) -> float:
        return float(np.sqrt(np.mean(x * x, dtype=np.float64)) + EPS)

    @staticmethod
    def rms_dbfs(x: np.ndarray) -> Optional[float]:
        if x is None or len(x) == 0:
            return None
        return float(20.0 * np.log10(AudioMetrics.rms(x)))

    @staticmethod
    def crest_factor_db(x: np.ndarray) -> Optional[float]:
        if x is None or len(x) == 0:
            return None
        return float(20.0 * np.log10(AudioMetrics.peak(x) / AudioMetrics.rms(x)))

    @staticmethod
    def clip_rate(x: np.ndarray, thr: float = 0.999) -> float:
        if x is None or len(x) == 0:
            return 0.0
        return float(np.mean(np.abs(x) >= thr))

    # ---------------------------
    # VAD: máscara fixa do INPUT
    # ---------------------------
    def vad_mask_from_input(self, x_in: np.ndarray) -> Tuple[np.ndarray, np.ndarray, int]:
        """
        Retorna:
          mask_sample: bool array no nível de amostras (speech=True)
          flags_frame: bool array por frame VAD
          frame_len: samples
        """
        cfg = self.vad_cfg
        assert cfg.frame_ms in (10, 20, 30), "webrtcvad suporta 10/20/30ms"
        frame_len = int(round(self.sr * cfg.frame_ms / 1000))
        n_frames = int(np.ceil(len(x_in) / frame_len))

        vad = webrtcvad.Vad(cfg.mode)
        x16 = (np.clip(x_in, -1.0, 1.0) * 32767).astype(np.int16)

        flags = np.zeros(n_frames, dtype=bool)
        for i in range(n_frames):
            a = i * frame_len
            b = min((i + 1) * frame_len, len(x16))
            frame = np.zeros(frame_len, dtype=np.int16)
            frame[: b - a] = x16[a:b]
            flags[i] = vad.is_speech(frame.tobytes(), self.sr)

        # Hang/closing simples (suaviza buracos curtos)
        hang = max(0, int(round(cfg.hang_ms / cfg.frame_ms)))
        if hang > 0 and len(flags) > 0:
            kernel = np.ones(2 * hang + 1, dtype=int)
            smoothed = np.convolve(flags.astype(int), kernel, mode="same") > 0
            flags = smoothed

        mask = np.repeat(flags, frame_len)[: len(x_in)]
        return mask, flags, frame_len

    # ---------------------------
    # STFT / Band energies
    # ---------------------------
    def _stft_mag2(self, x: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        c = self.stft_cfg
        stft = lr.stft(x, n_fft=c.n_fft, hop_length=c.hop, win_length=c.win, window=c.window)
        mag2 = np.abs(stft) ** 2
        return mag2, stft

    def band_energy(self, x: np.ndarray, f_lo: float, f_hi: float) -> float:
        c = self.stft_cfg
        stft = lr.stft(x, n_fft=c.n_fft, hop_length=c.hop, win_length=c.win, window=c.window)
        freqs = lr.fft_frequencies(sr=self.sr, n_fft=c.n_fft)
        mag2 = np.abs(stft) ** 2
        idx = (freqs >= f_lo) & (freqs <= f_hi)
        if not np.any(idx):
            return 0.0
        return float(np.mean(mag2[idx, :]))

    def spectral_flatness(self, x: np.ndarray) -> Optional[float]:
        if x is None or len(x) < self.stft_cfg.n_fft:
            return None
        c = self.stft_cfg
        S = np.abs(lr.stft(x, n_fft=c.n_fft, hop_length=c.hop, win_length=c.win, window=c.window)) + EPS
        gmean = np.exp(np.mean(np.log(S), axis=0))
        amean = np.mean(S, axis=0) + EPS
        return float(np.mean(gmean / amean))

    # ---------------------------
    # PSD (Welch) do ruído non-speech
    # ---------------------------
    def noise_psd_welch(self, x: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        f, P = welch(x, fs=self.sr, nperseg=self.psd_cfg.nperseg)
        return f, P

    # ---------------------------
    # Métricas principais (NO-REFERENCE)
    # ---------------------------
    def evaluate_pair(self, x_in: np.ndarray, x_out: np.ndarray,
                      label: str = "pair") -> Dict[str, Optional[float]]:
        """
        Compara input vs output usando máscara VAD fixa do input.
        Retorna métricas prontas para tabela/CSV.
        """
        x_in = self._ensure_float_mono(x_in)
        x_out = self._ensure_float_mono(x_out)

        n = min(len(x_in), len(x_out))
        x_in = x_in[:n]
        x_out = x_out[:n]

        mask, _, _ = self.vad_mask_from_input(x_in)

        ns_in = x_in[~mask]
        ns_out = x_out[~mask]
        sp_in = x_in[mask]
        sp_out = x_out[mask]

        # --- Band-limited PSD improvement (noise / non-speech)
        # potência integrada do PSD do ruído na banda de radiotelefonia
        noise_band_in = self.band_limited_psd_power(ns_in, 300, 3400) if len(ns_in) else None
        noise_band_out = self.band_limited_psd_power(ns_out, 300, 3400) if len(ns_out) else None

        noise_band_in_db = self.power_to_db(noise_band_in)
        noise_band_out_db = self.power_to_db(noise_band_out)

        noise_band_reduction_db = None
        if noise_band_in_db is not None and noise_band_out_db is not None:
            noise_band_reduction_db = float(noise_band_in_db - noise_band_out_db)


        ns_in_db = self.rms_dbfs(ns_in)
        ns_out_db = self.rms_dbfs(ns_out)
        sp_in_db = self.rms_dbfs(sp_in)
        sp_out_db = self.rms_dbfs(sp_out)

        # Proxy SNR = nível fala - nível ruído
        snr_in = (sp_in_db - ns_in_db) if (sp_in_db is not None and ns_in_db is not None) else None
        snr_out = (sp_out_db - ns_out_db) if (sp_out_db is not None and ns_out_db is not None) else None

        # Energias por banda (para “abafamento” e foco em radiotelefonia)
        # Banda típica voz: ~300–3400 Hz (adaptável)
        e_sp_band_in = self.band_energy(sp_in, 300, 3400) if len(sp_in) else None
        e_sp_band_out = self.band_energy(sp_out, 300, 3400) if len(sp_out) else None

        e_hf_in = self.band_energy(sp_in, 4000, 8000) if len(sp_in) else None
        e_hf_out = self.band_energy(sp_out, 4000, 8000) if len(sp_out) else None

        # Flatness em fala e ruído (artefatos / musical noise proxy)
        flat_sp_in = self.spectral_flatness(sp_in)
        flat_sp_out = self.spectral_flatness(sp_out)
        flat_ns_in = self.spectral_flatness(ns_in)
        flat_ns_out = self.spectral_flatness(ns_out)

        # Dinâmica / clipping
        clip_in = self.clip_rate(x_in)
        clip_out = self.clip_rate(x_out)
        crest_in = self.crest_factor_db(x_in)
        crest_out = self.crest_factor_db(x_out)

        # “HF loss” (quanto caiu a energia HF relativa na fala)
        hf_ratio = None
        if e_hf_in is not None and e_hf_out is not None:
            hf_ratio = float(e_hf_out / (e_hf_in + EPS))

        # “Speech-band focus” (energia banda voz / total na fala)
        # útil para evidenciar que o bandpass + denoise concentram no que importa
        focus_in = None
        focus_out = None
        if len(sp_in):
            e_total_in = self.band_energy(sp_in, 0, self.sr / 2 - 1)
            focus_in = float((e_sp_band_in or 0.0) / (e_total_in + EPS))
        if len(sp_out):
            e_total_out = self.band_energy(sp_out, 0, self.sr / 2 - 1)
            focus_out = float((e_sp_band_out or 0.0) / (e_total_out + EPS))

        return {
            "label": label,

            # Noise floor / redução de ruído
            "nsRmsInDb": ns_in_db,
            "nsRmsOutDb": ns_out_db,
            "nsReductionDb": (ns_in_db - ns_out_db) if (ns_in_db is not None and ns_out_db is not None) else None,

            # Preservação de fala
            "spRmsInDb": sp_in_db,
            "spRmsOutDb": sp_out_db,
            "speechLevelDeltaDb": (sp_out_db - sp_in_db) if (sp_in_db is not None and sp_out_db is not None) else None,

            # SNR proxy
            "snrProxyInDb": snr_in,
            "snrProxyOutDb": snr_out,
            "snrProxyDeltaDb": (snr_out - snr_in) if (snr_in is not None and snr_out is not None) else None,

            # Banda de voz / abafamento
            "speechBandEnergyIn": e_sp_band_in,
            "speechBandEnergyOut": e_sp_band_out,
            "hfEnergyIn": e_hf_in,
            "hfEnergyOut": e_hf_out,
            "hfEnergyRatioOutIn": hf_ratio,
            "speechBandFocusIn": focus_in,
            "speechBandFocusOut": focus_out,
            "speechBandFocusDelta": (focus_out - focus_in) if (focus_in is not None and focus_out is not None) else None,

            # Artefatos
            "flatnessSpeechIn": flat_sp_in,
            "flatnessSpeechOut": flat_sp_out,
            "flatnessNoiseIn": flat_ns_in,
            "flatnessNoiseOut": flat_ns_out,

            # Dinâmica
            "clipRateIn": clip_in,
            "clipRateOut": clip_out,
            "crestFactorInDb": crest_in,
            "crestFactorOutDb": crest_out,


            # PSD band-limited (ruído non-speech)
            "noiseBandPowerIn": noise_band_in,
            "noiseBandPowerOut": noise_band_out,
            "noiseBandPowerInDb": noise_band_in_db,
            "noiseBandPowerOutDb": noise_band_out_db,
            "noiseBandReductionDb": noise_band_reduction_db,

        }

    # ---------------------------
    # Ablation: múltiplos estágios
    # ---------------------------
    def evaluate_stages(self, stages: List[Tuple[str, np.ndarray]], x_ref: Optional[np.ndarray] = None) -> pd.DataFrame:
        """
        stages: lista [(nome, audio)]
        x_ref: se None, usa o primeiro estágio como input fixo para máscara VAD e referência comparativa.
        Retorna DataFrame com métricas por estágio comparado ao input.
        """
        if len(stages) < 2:
            raise ValueError("Forneça pelo menos 2 estágios: input e output.")

        base_name, x0 = stages[0]
        x0 = self._ensure_float_mono(x0)

        if x_ref is None:
            x_ref = x0
        else:
            x_ref = self._ensure_float_mono(x_ref)

        rows = []
        for name, x in stages[1:]:
            rows.append(self.evaluate_pair(x_ref, x, label=f"{base_name} -> {name}"))

        df = pd.DataFrame(rows)
        return df

    # ---------------------------
    # Export tabelas (CSV + LaTeX)
    # ---------------------------
    @staticmethod
    def save_table(df: pd.DataFrame, out_csv: str, out_tex: Optional[str] = None, float_format: str = "%.3f"):
        os.makedirs(os.path.dirname(out_csv) or ".", exist_ok=True)
        df.to_csv(out_csv, index=False)

        if out_tex:
            os.makedirs(os.path.dirname(out_tex) or ".", exist_ok=True)
            tex = df.to_latex(index=False, float_format=lambda x: float_format % x)
            with open(out_tex, "w", encoding="utf-8") as f:
                f.write(tex)

    # ---------------------------
    # VISUAIS (evidências)
    # ---------------------------
    def plot_wave_vad(self, x_in: np.ndarray, x_out: np.ndarray, out_path: str,
                      title_prefix: str = "", max_seconds: Optional[float] = 20.0):
        """
        Figura 1: waveform input/output com máscara VAD (derivada do input).
        """
        x_in = self._ensure_float_mono(x_in)
        x_out = self._ensure_float_mono(x_out)
        n_full = min(len(x_in), len(x_out))
        x_in = x_in[:n_full]
        x_out = x_out[:n_full]

        mask_full, flags_full, frame_len = self.vad_mask_from_input(x_in)

        x_in_short = x_in
        x_out_short = x_out
        n_short = n_full
        flags_short = flags_full
        if max_seconds is not None:
            nmax = int(max_seconds * self.sr)
            x_in_short = x_in[:nmax]
            x_out_short = x_out[:nmax]
            n_short = min(len(x_in_short), len(x_out_short))
            frame_limit = int(np.ceil(n_short / frame_len))
            flags_short = flags_full[:frame_limit]

        t_short = np.arange(n_short) / self.sr

        def add_vad_spans(ax, flags_local: np.ndarray, frame_len_local: int) -> None:
            if flags_local is None or len(flags_local) == 0:
                return
            frame_times = np.arange(len(flags_local) + 1) * (frame_len_local / self.sr)
            in_seg = False
            start = 0
            for i, flag in enumerate(flags_local):
                if flag and not in_seg:
                    start = i
                    in_seg = True
                if in_seg and (not flag or i == len(flags_local) - 1):
                    end = i + 1 if flag else i
                    ax.axvspan(frame_times[start], frame_times[end], color="tab:green", alpha=0.15, lw=0)
                    in_seg = False

        plt.figure()
        ax = plt.gca()
        ax.plot(t_short, x_in_short, linewidth=0.8)
        add_vad_spans(ax, flags_short, frame_len)
        ax.legend(handles=[Patch(facecolor="tab:green", alpha=0.15, label="Speech (VAD)")], loc="upper right")
        plt.title(f"{title_prefix}Waveform (Input) + VAD mask")
        plt.xlabel("Time (s)")
        plt.ylabel("Amplitude")
        plt.tight_layout()
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        plt.savefig(out_path.replace(".png", "_wave_in.png"), dpi=200)
        plt.close()

        plt.figure()
        ax = plt.gca()
        ax.plot(t_short, x_out_short, linewidth=0.8)
        add_vad_spans(ax, flags_short, frame_len)
        ax.legend(handles=[Patch(facecolor="tab:green", alpha=0.15, label="Speech (VAD)")], loc="upper right")
        plt.title(f"{title_prefix}Waveform (Output) + VAD mask (from input)")
        plt.xlabel("Time (s)")
        plt.ylabel("Amplitude")
        plt.tight_layout()
        plt.savefig(out_path.replace(".png", "_wave_out.png"), dpi=200)
        plt.close()

        if flags_full is not None and len(flags_full) > 0:
            max_points = 200000
            step = max(1, int(np.ceil(n_full / max_points)))
            t_full = np.arange(n_full) / self.sr
            plt.figure(figsize=(10, 2.8))
            ax = plt.gca()
            ax.plot(t_full[::step], x_in[::step], linewidth=0.6)
            add_vad_spans(ax, flags_full, frame_len)
            ax.legend(handles=[Patch(facecolor="tab:green", alpha=0.15, label="Speech (VAD)")], loc="upper right")
            plt.title(f"{title_prefix}Waveform (Input) + VAD mask (Full)")
            plt.xlabel("Time (s)")
            plt.ylabel("Amplitude")
            plt.tight_layout()
            plt.savefig(out_path.replace(".png", "_wave_full.png"), dpi=200)
            plt.close()

        if flags_full is not None and len(flags_full) > 0:
            frame_times = np.arange(len(flags_full)) * (frame_len / self.sr)
            plt.figure(figsize=(10, 2.4))
            plt.step(frame_times, flags_full.astype(int), where="post", linewidth=1.0)
            plt.ylim(-0.1, 1.1)
            plt.yticks([0, 1], ["non-speech", "speech"])
            plt.title(f"{title_prefix}VAD Speech Activity (Full)")
            plt.xlabel("Time (s)")
            plt.ylabel("Class")
            plt.tight_layout()
            plt.savefig(out_path.replace(".png", "_vad_activity_full.png"), dpi=200)
            plt.close()

            if max_seconds is not None:
                frame_times_short = frame_times[:len(flags_short)]
                plt.figure(figsize=(10, 2.4))
                plt.step(frame_times_short, flags_short.astype(int), where="post", linewidth=1.0)
                plt.ylim(-0.1, 1.1)
                plt.yticks([0, 1], ["non-speech", "speech"])
                plt.title(f"{title_prefix}VAD Speech Activity")
                plt.xlabel("Time (s)")
                plt.ylabel("Class")
                plt.tight_layout()
                plt.savefig(out_path.replace(".png", "_vad_activity.png"), dpi=200)
                plt.close()

    def plot_spectrograms(self, x_in: np.ndarray, x_out: np.ndarray, out_path: str, title_prefix: str = ""):
        """
        Figura 2: espectrograma input, output e diferença (dB).
        """
        x_in = self._ensure_float_mono(x_in)
        x_out = self._ensure_float_mono(x_out)
        n = min(len(x_in), len(x_out))
        x_in = x_in[:n]
        x_out = x_out[:n]

        c = self.stft_cfg

        def spec_mag(x):
            S = lr.stft(x, n_fft=c.n_fft, hop_length=c.hop, win_length=c.win, window=c.window)
            return np.abs(S)

        S1_mag = spec_mag(x_in)
        S2_mag = spec_mag(x_out)
        ref = max(float(np.max(S1_mag)), float(np.max(S2_mag)), EPS)
        S1 = lr.amplitude_to_db(S1_mag + EPS, ref=ref)
        S2 = lr.amplitude_to_db(S2_mag + EPS, ref=ref)
        Sd = S2 - S1

        freqs = lr.fft_frequencies(sr=self.sr, n_fft=c.n_fft)
        times = lr.frames_to_time(np.arange(S1.shape[1]), sr=self.sr, hop_length=c.hop)
        extent = [float(times[0]), float(times[-1]), float(freqs[0]), float(freqs[-1])]

        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)

        plt.figure()
        im = plt.imshow(S1, origin="lower", aspect="auto", extent=extent)
        plt.title(f"{title_prefix}Spectrogram (Input) [dB]")
        plt.xlabel("Time (s)")
        plt.ylabel("Frequency (Hz)")
        plt.colorbar(im, label="Level (dB)")
        plt.tight_layout()
        plt.savefig(out_path.replace(".png", "_spec_in.png"), dpi=200)
        plt.close()

        plt.figure()
        im = plt.imshow(S2, origin="lower", aspect="auto", extent=extent)
        plt.title(f"{title_prefix}Spectrogram (Output) [dB]")
        plt.xlabel("Time (s)")
        plt.ylabel("Frequency (Hz)")
        plt.colorbar(im, label="Level (dB)")
        plt.tight_layout()
        plt.savefig(out_path.replace(".png", "_spec_out.png"), dpi=200)
        plt.close()

        plt.figure()
        max_abs = float(np.max(np.abs(Sd))) if Sd.size else 1.0
        im = plt.imshow(Sd, origin="lower", aspect="auto", extent=extent,
                cmap="coolwarm", vmin=-max_abs, vmax=max_abs)
        plt.title(f"{title_prefix}Spectrogram Difference (Out - In) [dB]")
        plt.xlabel("Time (s)")
        plt.ylabel("Frequency (Hz)")
        plt.colorbar(im, label="Delta (dB)")
        plt.tight_layout()
        plt.savefig(out_path.replace(".png", "_spec_diff.png"), dpi=200)
        plt.close()

    def plot_noise_psd(self, x_in: np.ndarray, x_out: np.ndarray, out_path: str, title_prefix: str = ""):
        """
        Figura 3: PSD do ruído (non-speech) via Welch.
        """
        x_in = self._ensure_float_mono(x_in)
        x_out = self._ensure_float_mono(x_out)
        n = min(len(x_in), len(x_out))
        x_in = x_in[:n]
        x_out = x_out[:n]

        mask, _, _ = self.vad_mask_from_input(x_in)
        ns_in = x_in[~mask]
        ns_out = x_out[~mask]

        # garante que tem material suficiente pra Welch
        if len(ns_in) < int(0.2 * self.sr) or len(ns_out) < int(0.2 * self.sr):
            return

        f1, P1 = self.noise_psd_welch(ns_in)
        f2, P2 = self.noise_psd_welch(ns_out)

        P1_db = 10 * np.log10(P1 + EPS)
        P2_db = 10 * np.log10(P2 + EPS)

        plt.figure()
        plt.plot(f1, P1_db, linewidth=1.0)
        plt.plot(f2, P2_db, linewidth=1.0)
        plt.title(f"{title_prefix}Noise PSD (non-speech) - Welch")
        plt.xlabel("Frequency (Hz)")
        plt.ylabel("PSD (dB/Hz)")
        plt.xlim(0, self.sr / 2)
        plt.legend(["Input noise", "Output noise"])
        plt.tight_layout()

        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        plt.savefig(out_path.replace(".png", "_noise_psd.png"), dpi=200)
        plt.close()

    @staticmethod
    def plot_metrics_bar(df: pd.DataFrame, out_path: str,
                         metrics: List[str],
                         title: str = "Metrics by stage"):
        """
        Figura 4: gráfico simples (barras) de métricas selecionadas por estágio.
        df: DataFrame retornado por evaluate_stages (uma linha por transição input->stage).
        """
        if df is None or df.empty:
            return

        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)

        for m in metrics:
            if m not in df.columns:
                continue

            plt.figure()
            plt.bar(np.arange(len(df)), df[m].values)
            plt.xticks(np.arange(len(df)), df["label"].values, rotation=30, ha="right")
            plt.title(f"{title}: {m}")
            plt.ylabel(m)
            plt.tight_layout()
            plt.savefig(out_path.replace(".png", f"_bar_{m}.png"), dpi=200)
            plt.close()

    def band_limited_psd_power(self, x: np.ndarray, f_lo: float, f_hi: float) -> Optional[float]:
        """
        Retorna a potência integrada (aprox.) do PSD na banda [f_lo, f_hi].
        Usado para medir ruído (non-speech) de forma band-limited.
        """
        x = self._ensure_float_mono(x)
        if x is None or len(x) < int(0.2 * self.sr):
            return None

        f, P = self.noise_psd_welch(x)  # P em unidades ~ (amplitude^2)/Hz
        idx = (f >= f_lo) & (f <= f_hi)
        if not np.any(idx):
            return None

        # Integra PSD ao longo da frequência (trapz) -> potência na banda
        band_power = float(np.trapz(P[idx], f[idx]))
        return band_power

    @staticmethod
    def power_to_db(power: Optional[float]) -> Optional[float]:
        if power is None:
            return None
        return float(10.0 * np.log10(power + EPS))

