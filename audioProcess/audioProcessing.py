from scipy import signal
import librosa as lr
import numpy as np
import soundfile as sf
import webrtcvad


class AudioProcessor:
    def __init__(self, audio_file_path):

        self.input_audio, self.sample_audio_rate = lr.load(audio_file_path, sr=16000)

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
