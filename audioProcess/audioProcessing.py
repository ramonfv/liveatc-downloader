from scipy import signal
import librosa as lr
import numpy as np
import soundfile as sf
import webrtcvad
from pyrnnoise import RNNoise
import torch
import os
os.environ["SPEECHBRAIN_LOCAL_CACHE_STRATEGY"] = "copy"
from speechbrain.inference import SpectralMaskEnhancement
from denoiser import pretrained
from denoiser.dsp import convert_audio

global _sb_model_cache, _fb_model_cache
_sb_model_cache = {}
_fb_model_cache = {}

class AudioProcessor:
    def __init__(self, audio_file_path):

        self.input_audio, self.sample_audio_rate = lr.load(audio_file_path, sr=16000)
        self.eps = 1e-12

    def bandPassFilterIir(self, low_freq, high_freq, order=6, equalize=True):

        if high_freq >= self.sample_audio_rate / 2:
            high_freq = self.sample_audio_rate / 2 - 1.0

        sos = signal.iirfilter(order, [low_freq, high_freq], btype='bandpass', ftype='butter', output='sos', fs=self.sample_audio_rate)
        iir_filtered_audio = signal.sosfilt(sos, self.input_audio)

        if equalize:
            computedFrequencies, frequencyResponse = signal.freqz_sos(sos, worN=4096, fs=self.sample_audio_rate)
            passband = (computedFrequencies >= low_freq*1.1) & (computedFrequencies <= high_freq*0.9)
            gain = np.median(np.abs(frequencyResponse[passband])) if np.any(passband) else 1.0
            if gain > 1e-12:
                iir_filtered_audio = iir_filtered_audio / gain

        return iir_filtered_audio

    def bandPassFilterFir(self, low_freq, high_freq, numtaps=401, equalize=True):

        if high_freq >= self.sample_audio_rate / 2:
            high_freq = self.sample_audio_rate / 2 - 1.0

        fir_coeff = signal.firwin(numtaps, [low_freq, high_freq], window=('kaiser', 8.0), pass_zero=False, fs=self.sample_audio_rate)
        w, h = signal.freqz(fir_coeff, worN=4096, fs=self.sample_audio_rate)
        pb = (w >= 500) & (w <= 2500)
        g = np.mean(np.abs(h[pb])) + 1e-12
        fir_coeff /= g
        # fir_filtered_audio = signal.lfilter(fir_coeff, 1.0, self.input_audio)

        if equalize:
            computedFrequencies, frequencyResponse = signal.freqz(fir_coeff, worN=4096, fs=self.sample_audio_rate)
            passband = (computedFrequencies >= low_freq*1.1) & (computedFrequencies <= high_freq*0.9)
            gain = np.median(np.abs(frequencyResponse[passband])) if np.any(passband) else 1.0
            if gain > 1e-12:
                fir_coeff = fir_coeff / gain

        fir_filtered_audio = signal.filtfilt(fir_coeff, [1.0], self.input_audio)

        return fir_filtered_audio
    
    
    def rms(self, input_signal):
        return float(np.sqrt(np.mean(np.square(input_signal), dtype=np.float64)) + 1e-12)

    def loudnessNormalizeAdaptive(self, input_audio, sample_rate, target_dbfs = -20.0, top_db = 25.0):
        intervals = lr.effects.split(input_audio, top_db=top_db)
        if len(intervals) == 0:
            current_rms = self.rms(input_audio)
        else:
            pieces = [input_audio[s:e] for (s, e) in intervals]
            if len(pieces) == 0:
                current_rms = self.rms(input_audio)
            else:
                concat = np.concatenate(pieces)
                current_rms = self.rms(concat)

        target_linear = 10.0 ** (target_dbfs / 20.0)
        if current_rms < 1e-9:
            gain = 1.0
        else:
            gain = target_linear / current_rms

        y_out = input_audio * gain
        peak = np.max(np.abs(y_out)) + 1e-12
        if peak > 0.999:
            y_out = y_out * (0.999 / peak)
        return y_out, gain

    def resample_to_16k(self, input_audio, sample_rate_input, sample_rate_output=16000):
        if sample_rate_input == sample_rate_output:
            return input_audio
        y16 = lr.resample(input_audio, orig_sr=sample_rate_input, target_sr=sample_rate_output, res_type="kaiser_best")
        return y16


    def writeFilteredAudio(self, output_file_path, filtered_audio):
        sf.write(output_file_path, filtered_audio, self.sample_audio_rate)
        print(f"Filtered audio written to {output_file_path}")

    def vadGate(self, input_audio, sample_rate, frame_ms, mode, hang_ms, atten_db):

        assert frame_ms in (10, 20, 30) and sample_rate in (8000, 16000, 32000, 48000)
        
        frame_len = int(sample_rate * frame_ms / 1000)

        pad = (frame_len - (len(input_audio) % frame_len)) % frame_len
        output = np.pad(input_audio, (0, pad)) if pad else input_audio

        int16_output = (np.clip(output, -1.0, 1.0) * 32767).astype(np.int16)
        vad = webrtcvad.Vad(mode)

        num_frames = len(int16_output) // frame_len
        frame_flags = np.zeros((num_frames,), dtype=bool)
        for i in range(num_frames):
            frame = int16_output[i * frame_len:(i + 1) * frame_len].tobytes()
            frame_flags[i] = vad.is_speech(frame, sample_rate)

        
        hang = max(0, int(round(hang_ms / frame_ms)))
        if hang > 0:
            kernel = np.ones(2*hang + 1, dtype=int)
            smoothed = np.convolve(frame_flags.astype(int), kernel, mode='same') > 0
            frame_flags = smoothed

        mask = np.repeat(frame_flags, frame_len)[:len(int16_output)]

        att = 10 ** (-atten_db / 20.0)
        squelch_output = output.copy()
        squelch_output[~mask] *= att

        segments = []
        if frame_flags.any():
            i = 0
            while i < num_frames:
                if frame_flags[i]:
                    start = i 
                    while i < num_frames and frame_flags[i]:
                        i += 1
                    end = i
                    t0 = start * frame_ms / 1000.0
                    t1 = end * frame_ms / 1000.0
                    segments.append((t0, t1))
                else:
                    i += 1

        if pad:
            squelch_output = squelch_output[:-pad]

        return squelch_output, segments, frame_flags

    
    def wiener_minstat_denoise(self, inputAudio, sampleRate, noiseWindowS: float = 1.5 , alphaSpec: float = 0.8, alphaDd: float = 0.98, biasCorrection: float = 1.5, minGainDb: float = -15.0):
        
        nFft, winLength, hopLength, window, eps = AudioUtils._stft_params()

        stftComplex = lr.stft(inputAudio, n_fft=nFft, hop_length=hopLength, win_length=winLength, window=window, center=True)
        magnitude = np.abs(stftComplex)
        phase = np.angle(stftComplex)
        powerSpectrum = magnitude**2

        nBins, nFrames = powerSpectrum.shape

        smoothedPower = powerSpectrum[:, [0]].copy() 
        noiseWindowFrames = max(10, int(noiseWindowS * sampleRate / hopLength))
        noiseMinBuffer = np.tile(smoothedPower, (1, noiseWindowFrames)) 

        enhancedMagnitude = np.empty_like(magnitude)
        minGainLinear = 10.0 ** (minGainDb / 20.0)
        prevWienerGain = np.ones((nBins, 1))
        prevPosterioriSnr = np.ones((nBins, 1))

        for frame in range(nFrames):

            smoothedPower = alphaSpec * smoothedPower + (1.0 - alphaSpec) * powerSpectrum[:, [frame]]  
            noiseMinBuffer[:, frame % noiseWindowFrames] = smoothedPower[:, 0]                             
            noisePsd = np.min(noiseMinBuffer, axis=1, keepdims=True)             
            noisePsd = np.maximum(noisePsd * biasCorrection, self.eps)

            prevPosterioriSnr = powerSpectrum[:, [frame]] / noisePsd
            aPrioriSnr = (alphaDd * (prevWienerGain ** 2) * prevPosterioriSnr) + (1.0 - alphaDd) * np.maximum(prevPosterioriSnr - 1.0, 0.0)

            # Ganho de Wiener em magnitude: G = xi / (1 + xi)
            wienerGain = aPrioriSnr / (1.0 + aPrioriSnr) 
            wienerGain = np.maximum(wienerGain, minGainLinear)

            enhancedMagnitude[:, frame] = wienerGain[:, 0] * magnitude[:, frame]

            prevWienerGain = wienerGain
            prevPosterioriSnr = prevPosterioriSnr


        stftEnhanced = enhancedMagnitude * np.exp(1j * phase)
        audioOutput = lr.istft(stftEnhanced, hop_length=hopLength, win_length=winLength, window=window, center=True, length=len(inputAudio))

        return audioOutput
    

    @staticmethod
    def _enhance_rnnNoise(inputAudio, sampleRate, dry_wet=0.85):
        audio48 = lr.resample(inputAudio, orig_sr=sampleRate, target_sr=48000, res_type="polyphase").astype(np.float32, copy=False)
        frame_len = 480

        pad = (-len(audio48)) % frame_len
        if pad:
            audio48 = np.pad(audio48, (0, pad), mode="constant")

        denoiser = RNNoise(sample_rate=48000)
        if hasattr(denoiser, "set_channels"):
            denoiser.set_channels(1)
        elif hasattr(denoiser, "channels"):
            denoiser.channels = 1

        out48 = np.zeros_like(audio48, dtype=np.float32)

        for i in range(0, len(audio48), frame_len):
            frame_2d = audio48[i:i+frame_len].reshape(1, frame_len)

            den = denoiser.denoise_frame(frame_2d)

            if isinstance(den, tuple):
                den = den[0]

            den = np.asarray(den, dtype=np.float32)

            if den.ndim == 2 and den.shape[0] == 1:
                den = den[0]

            out48[i:i+frame_len] = den

        if pad:
            out48 = out48[:-pad]

        out = lr.resample(out48, orig_sr=48000, target_sr=sampleRate, res_type="polyphase").astype(np.float32, copy=False)

        return dry_wet * out + (1.0 - dry_wet) * inputAudio

    @staticmethod
    def _enhance_metricgan(inputAudio, sampleRate, dry_wet=0.9, device="cuda"):

        key = (sampleRate, device)
        if key not in _sb_model_cache:
            enhancer = SpectralMaskEnhancement.from_hparams(
                source="speechbrain/metricgan-plus-voicebank",
                savedir="./_sb_metricgan_cache",
                run_opts={"device": device}
            )
            _sb_model_cache[key] = enhancer
        enhancer = _sb_model_cache[key]

        wav = torch.from_numpy(inputAudio).float().unsqueeze(0).to(device).contiguous()

        lengths = torch.ones(1, device=device)

        prev = torch.backends.cudnn.enabled
        torch.backends.cudnn.enabled = False

        with torch.no_grad():
            enhanced = enhancer.enhance_batch(wav, lengths=lengths)
            torch.backends.cudnn.enabled = prev

        outputAudio = enhanced.squeeze(0).detach().cpu().numpy()

        return dry_wet * outputAudio + (1.0 - dry_wet) * inputAudio
    
    @staticmethod
    def _enhance_fb_denoiser(inputAudio, sampleRate, dry_wet=0.9, device="cuda", model_name="dns64"):

        key = (model_name, device)
        model = _fb_model_cache.get(key)
        if model is None:
            model = pretrained.dns64()
            model.to(device).eval()
            _fb_model_cache[key] = model

        audiofloat32 = np.asarray(inputAudio, dtype=np.float32, order='C')
        wav = torch.from_numpy(audiofloat32).unsqueeze(0)
        wav = convert_audio(wav, sampleRate, model.sample_rate, model.chin)
        wav = wav.unsqueeze(0).to(device).contiguous().float()  

        prev = torch.backends.cudnn.enabled
        torch.backends.cudnn.enabled = False   

        with torch.no_grad():
            enhanced = model(wav)
            if isinstance(enhanced, (tuple, list)):
                enhanced = enhanced[0]

        torch.backends.cudnn.enabled = prev
        outputAudio = enhanced.squeeze(0).squeeze(0).detach().cpu().numpy().astype(np.float32)

        if sampleRate != model.sample_rate:
            outputAudio = lr.resample(outputAudio, orig_sr=model.sample_rate, target_sr=sampleRate, res_type="polyphase").astype(np.float32, copy=False)

        return dry_wet * outputAudio + (1.0 - dry_wet) * inputAudio
    
    @staticmethod
    def _enhance_neural(inputAudio, sampleRate, strategy="offline", device="cuda"):

        inputAudio = AudioUtils._ensure_mono(AudioUtils._soft_limiter(inputAudio, ceiling_dbfs=-1.0))

        if strategy == "lite":
            return AudioProcessor._enhance_rnnNoise(inputAudio, sampleRate)

        elif strategy == "offline":
            return AudioProcessor._enhance_metricgan(inputAudio, sampleRate)

        elif strategy == "complex":
            return AudioProcessor._enhance_fb_denoiser(inputAudio, sampleRate)

    @staticmethod
    def _enhance_neural_chunked(inputAudio, sampleRate,
                                strategy="complex",
                                device="cuda",
                                chunk_seconds=20,
                                overlap_seconds=0.5):
        """
        Processa áudio neural em chunks com overlap-add (OLA) para evitar seams.
        overlap_seconds ~ 0.25 a 1.0s costuma ficar bom.
        """
        import torch

        x = AudioUtils._ensure_mono(AudioUtils._soft_limiter(inputAudio, ceiling_dbfs=-1.0))
        x = np.asarray(x, dtype=np.float32)

        chunk_size = int(chunk_seconds * sampleRate)
        ov = int(overlap_seconds * sampleRate)
        ov = min(max(0, ov), max(0, chunk_size // 2))

        if chunk_size <= 0 or chunk_size <= ov:
            raise ValueError("chunk_seconds muito pequeno ou overlap grande demais.")

        # janela de crossfade (Hann) só no overlap
        if ov > 0:
            win_in = np.sin(np.linspace(0, np.pi/2, ov, dtype=np.float32))**2
            win_out = win_in[::-1]
        else:
            win_in = win_out = None

        y = np.zeros_like(x, dtype=np.float32)
        wsum = np.zeros_like(x, dtype=np.float32)

        step = chunk_size - ov
        total = (len(x) + step - 1) // step

        print(f"🔄 Neural OLA: chunk={chunk_seconds}s overlap={overlap_seconds}s (total chunks ~ {total})")

        for k, start in enumerate(range(0, len(x), step), 1):
            end = min(start + chunk_size, len(x))
            chunk = x[start:end]

            # pad para chunk_size (melhora consistência)
            if len(chunk) < chunk_size:
                chunk = np.pad(chunk, (0, chunk_size - len(chunk)))

            if strategy == "lite":
                enh = AudioProcessor._enhance_rnnNoise(chunk, sampleRate)
            elif strategy == "offline":
                enh = AudioProcessor._enhance_metricgan(chunk, sampleRate, device=device)
            elif strategy == "complex":
                enh = AudioProcessor._enhance_fb_denoiser(chunk, sampleRate, device=device)
            else:
                raise ValueError(f"strategy inválida: {strategy}")

            enh = np.asarray(enh, dtype=np.float32)

            # recorta padding
            enh = enh[:(end - start)]

            # aplica janelas no overlap
            ww = np.ones_like(enh, dtype=np.float32)
            if ov > 0 and (end - start) > 1:
                # fade-in no começo (exceto no primeiro chunk)
                if start > 0:
                    L = min(ov, len(enh))
                    ww[:L] *= win_in[:L]
                # fade-out no fim (exceto se é o último)
                if end < len(x):
                    L = min(ov, len(enh))
                    ww[-L:] *= win_out[:L]

            y[start:end] += enh * ww
            wsum[start:end] += ww

            if torch.cuda.is_available():
                torch.cuda.empty_cache()

        wsum = np.maximum(wsum, 1e-6)
        out = (y / wsum).astype(np.float32, copy=False)
        print("✅ Processamento neural (OLA) concluído!")
        return out


    def lowPassFilterIir(self, cutoff_hz=3800.0, order=6):
        """Low-pass IIR Butterworth (causal). Útil para conter artefatos HF pós-denoise."""
        nyq = self.sample_audio_rate / 2.0
        cutoff_hz = min(float(cutoff_hz), nyq - 1.0)
        sos = signal.iirfilter(order, cutoff_hz, btype='lowpass', ftype='butter',
                               output='sos', fs=self.sample_audio_rate)
        y = signal.sosfilt(sos, self.input_audio)  # se quiser aplicar em outro sinal, use lowPassOn(...)
        return y

    @staticmethod
    def lowPassOn(x, sr, cutoff_hz=3800.0, order=6):
        nyq = sr / 2.0
        cutoff_hz = min(float(cutoff_hz), nyq - 1.0)
        sos = signal.iirfilter(order, cutoff_hz, btype='lowpass', ftype='butter',
                               output='sos', fs=sr)
        return signal.sosfilt(sos, x).astype(np.float32, copy=False)

    @staticmethod
    def _apply_fade_edges(y, mask, sr, fade_ms=10):
        """Aplica fade-in/out curto nos pontos de transição do mask para evitar clicks."""
        if fade_ms <= 0:
            return y
        fade_len = int(sr * fade_ms / 1000.0)
        if fade_len <= 1:
            return y

        mask_i = mask.astype(np.int32)
        # transições: 0->1 (rise) e 1->0 (fall)
        d = np.diff(mask_i, prepend=mask_i[0])
        rises = np.where(d == 1)[0]
        falls = np.where(d == -1)[0]

        y2 = y.copy()

        # fade in
        for r in rises:
            a = max(0, r - fade_len)
            b = min(len(y2), r + fade_len)
            L = b - a
            if L > 1:
                w = np.linspace(0.0, 1.0, L, dtype=np.float32)
                y2[a:b] *= w

        # fade out
        for f in falls:
            a = max(0, f - fade_len)
            b = min(len(y2), f + fade_len)
            L = b - a
            if L > 1:
                w = np.linspace(1.0, 0.0, L, dtype=np.float32)
                y2[a:b] *= w

        return y2




    def vadAttenuateSoft(self,
                         input_audio,
                         sample_rate,
                         frame_ms=20,
                         mode=2,
                         hang_ms=250,
                         atten_db=25.0,
                         floor_db=-60.0,
                         fade_ms=10):
        """
        Atenuação suave baseada em VAD:
        - Em não-fala: atenua atten_db (ex.: 20–35 dB), mas mantém um piso (floor_db).
        - Em fala: preserva.
        - Com fade nos edges para evitar clicks.
        Retorna: y, segments, frame_flags
        """
        assert frame_ms in (10, 20, 30) and sample_rate in (8000, 16000, 32000, 48000)
        frame_len = int(sample_rate * frame_ms / 1000)

        # pad para múltiplo de frames
        pad = (frame_len - (len(input_audio) % frame_len)) % frame_len
        x = np.pad(input_audio, (0, pad)) if pad else input_audio
        x = np.asarray(x, dtype=np.float32)

        # VAD usa int16
        x_i16 = (np.clip(x, -1.0, 1.0) * 32767).astype(np.int16)
        vad = webrtcvad.Vad(mode)

        num_frames = len(x_i16) // frame_len
        frame_flags = np.zeros((num_frames,), dtype=bool)
        for i in range(num_frames):
            fr = x_i16[i * frame_len:(i + 1) * frame_len].tobytes()
            frame_flags[i] = vad.is_speech(fr, sample_rate)

        # hang smoothing (dilatação temporal)
        hang = max(0, int(round(hang_ms / frame_ms)))
        if hang > 0:
            kernel = np.ones(2 * hang + 1, dtype=int)
            frame_flags = (np.convolve(frame_flags.astype(int), kernel, mode='same') > 0)

        # máscara por amostra
        mask = np.repeat(frame_flags, frame_len)[:len(x)]

        # Atenuação suave + piso
        att = 10 ** (-float(atten_db) / 20.0)

        # piso absoluto em amplitude (evita “silêncio digital” e melhora STT)
        floor_lin = 10 ** (float(floor_db) / 20.0)

        y = x.copy()
        y[~mask] *= att

        # aplica piso em não-fala (muito leve): mantém ruído baixo porém não zera
        # isso evita que o ASR trate transientes como tokenização esquisita
        if floor_lin > 0:
            ns = ~mask
            y[ns] = np.clip(y[ns], -floor_lin, floor_lin)

        # fades nos edges do mask (remove clicks)
        y = self._apply_fade_edges(y, mask, sample_rate, fade_ms=fade_ms)

        # segments (em segundos)
        segments = []
        if frame_flags.any():
            i = 0
            while i < num_frames:
                if frame_flags[i]:
                    s = i
                    while i < num_frames and frame_flags[i]:
                        i += 1
                    e = i
                    segments.append((s * frame_ms / 1000.0, e * frame_ms / 1000.0))
                else:
                    i += 1

        if pad:
            y = y[:-pad]

        return y.astype(np.float32, copy=False), segments, frame_flags



    def loudnessNormalizeSpeechAware(self, input_audio, sample_rate,
                                     speech_mask_samples,
                                     target_dbfs=-20.0,
                                     max_gain_db=12.0,
                                     min_gain_db=-12.0):
        """
        Normaliza com base SOMENTE na fala (speech_mask_samples=True),
        com limites de ganho para evitar amplificar ruído residual.
        """
        x = np.asarray(input_audio, dtype=np.float32)
        m = np.asarray(speech_mask_samples, dtype=bool)
        if len(m) != len(x):
            m = m[:len(x)] if len(m) >= len(x) else np.pad(m, (0, len(x)-len(m)), constant_values=False)

        # se não tem fala detectada, cai para RMS global
        ref = x[m] if np.any(m) else x

        rms = float(np.sqrt(np.mean(ref**2) + 1e-12))
        target_lin = 10.0 ** (target_dbfs / 20.0)

        gain = target_lin / max(rms, 1e-9)
        gain_db = 20.0 * np.log10(gain + 1e-12)

        gain_db = float(np.clip(gain_db, min_gain_db, max_gain_db))
        gain = 10.0 ** (gain_db / 20.0)

        y = x * gain

        # limiter suave anti-clip
        peak = float(np.max(np.abs(y)) + 1e-12)
        if peak > 0.999:
            y = y * (0.999 / peak)

        return y.astype(np.float32, copy=False), gain






class AudioUtils:

    @staticmethod
    def _stft_params():

        n_fft = 512
        win_length = 512
        hop_length = 160
        window = "hann"
        eps = 1e-12
        return n_fft, win_length, hop_length, window, eps

    @staticmethod
    def _ensure_mono(inputAudio):

        if inputAudio.ndim == 1:
            return inputAudio.astype(np.float32, copy=False)
        if inputAudio.ndim == 2:
            if inputAudio.shape[0] == 2 and inputAudio.shape[1] != 2:
                inputAudio = inputAudio.T

            return np.mean(inputAudio, axis=1).astype(np.float32, copy=False)

        return inputAudio.ravel().astype(np.float32, copy=False)
    
    @staticmethod
    def _soft_limiter(inputAudio, ceiling_dbfs = -1.0):

        n_fft, win_length, hop_length, window, eps = AudioUtils._stft_params()
        peak = np.max(np.abs(inputAudio)) + eps
        ceiling = 10 ** (ceiling_dbfs / 20.0)

        if peak <= ceiling:
            return inputAudio   
        
        return np.tanh(inputAudio / peak * 3.0) * ceiling
    
    @staticmethod
    def _band_energy(inputAudio, sampleRate, frequencyLow, frequencyHi, nFft=512, hop=160):
        stftComplex =  lr.stft(inputAudio, n_fft=nFft, hop_length=hop, win_length=nFft)
        frequencies = lr.fft_frequencies(sr=sampleRate, n_fft=nFft)
        magnitude = np.abs(stftComplex)
        idx = (frequencies >= frequencyLow) & (frequencies <= frequencyHi)

        if not np.any(idx):
            return 0.0

        return float(np.mean(magnitude[idx, :] ** 2))
    
    @staticmethod
    def _spectral_flatness(inputAudio, sampleRate, nFft=512, hop=160):
        n_fft, win_length, hop_length, window, eps = AudioUtils._stft_params()
        stftAbsolute =  np.abs(lr.stft(inputAudio, n_fft=nFft, hop_length=hop, win_length=nFft)) + eps
        geometricMean = np.exp(np.mean(np.log(stftAbsolute), axis=0))
        arithmeticMean = np.mean(stftAbsolute, axis=0) + eps
        flatness = geometricMean / arithmeticMean
        return float(np.mean(flatness))
    
    @staticmethod
    def _rough_snr(inputAudio, sampleRate, noiseWindowSample=1.5, nFFt=512, hop=160):

        n_fft, win_length, hop_length, window, eps = AudioUtils._stft_params()
        stftAbsolute = np.abs(lr.stft(inputAudio, n_fft=nFFt, hop_length=hop, win_length=nFFt))
        stftPower = stftAbsolute ** 2
        noiseWindowFrames = max(10, int(noiseWindowSample * sampleRate / hop))
        buffer = np.tile(stftPower[:, [0]], (1, noiseWindowFrames))
        snrList = []
        for frame in range(stftPower.shape[1]):
            buffer[:, frame % noiseWindowFrames] = 0.8 * buffer[:, frame % noiseWindowFrames] + 0.2 * stftPower[:, frame]
            noisePsd = np.min(buffer, axis=1) + self.eps
            signalPsd = np.mean(stftPower[:, frame]) + self.eps
            snrList.append(signalPsd / np.mean(noisePsd))

        snrLinear = float(np.mean(snrList))
        snrDb = 10.0 * np.log10(snrLinear + eps)
        return snrDb