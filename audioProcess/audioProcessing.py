from scipy import signal
import librosa as lr
import numpy as np
import soundfile as sf
import webrtcvad
from pyrnnoise import RNNoise
import torch
from speechbrain.inference.enhancement import SpectralMaskEnhancement

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
                target="./_sb_metricgan_cache",
                run_opts={"device": device}
            )
            _sb_model_cache[key] = enhancer
        enhancer = _sb_model_cache[key]

        wav = torch.from_numpy(inputAudio).float().unsqueeze(0)

        with torch.no_grad():
            enhanced = enhancer.enhance_batch(wav, lengths=torch.tensor([1.0]))

        outputAudio = enhanced.squeeze().cuda().numpy()

        return dry_wet * outputAudio + (1.0 - dry_wet) * inputAudio
    @staticmethod
    def _enhance_fb_denoiser(inputAudio, sampleRate, dry_wet=0.9, device="cuda", model_name="dns64"):
        key = (model_name, device)
        model = _fb_model_cache[key]
        sampleRateProvided = sampleRate

        with torch.no_grad():
            wav = torch.from_numpy(inputAudio).float().unsqueeze(0).to(model.device)
            enhanced = model(wav)[0].cuda().numpy()

        outputAudio = enhanced.squeeze(0)

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