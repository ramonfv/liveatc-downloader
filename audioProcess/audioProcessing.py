from scipy import signal
import librosa as lr
import numpy as np
import soundfile as sf


class AudioProcessor:
    def __init__(self, audio_file_path):

        self.input_audio, self.sample_audio_rate = lr.load(audio_file_path, sr=16000)

    def bandPassFilterIir(self, low_freq, high_freq, order=6):

        if high_freq >= self.sample_audio_rate / 2:
            high_freq = self.sample_audio_rate / 2 - 1.0

        sos = signal.iirfilter(order, [low_freq, high_freq], btype='bandpass', ftype='butter', output='sos', fs=self.sample_audio_rate)
        iir_filtered_audio = signal.sosfilt(sos, self.input_audio)

        return iir_filtered_audio

    def bandPassFilterFir(self, low_freq, high_freq, numtaps=101):

        if high_freq >= self.sample_audio_rate / 2:
            high_freq = self.sample_audio_rate / 2 - 1.0

        fir_coeff = signal.firwin(numtaps, [low_freq, high_freq], window='hamming', pass_zero=False, fs=self.sample_audio_rate)
        fir_filtered_audio = signal.lfilter(fir_coeff, 1.0, self.input_audio)

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



