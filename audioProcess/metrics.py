import numpy as np
import librosa as lr
import webrtcvad


class AudioMetrics:
    def __init__(self, audio_data, sample_rate=16000):
        self.audio_data = audio_data
        self.sample_rate = sample_rate
        self.EPS = 1e-12

    def compute_rms(self, inputAudio):
        return 20*np.log10(np.sqrt(np.mean(inputAudio**2) + self.EPS))


    def _stft_mag2(self, inputAudio, n_fft=512, hop=128, win='hann'):
        stft = lr.stft(inputAudio, n_fft=n_fft, hop_length=hop, window=win)
        mag2 = np.abs(stft)**2
        return mag2, stft
    
    def _vad_flags(self, inputAudio, frame_ms=30, top_db=25):

        frame_length = int(np.round(self.sample_rate * frame_ms / 1000))
        num_frames = int(np.ceil(len(inputAudio) / frame_length))
        flags = np.zeros(num_frames, dtype=bool)

        vad = webrtcvad.Vad(2)
        audio_int16 = (np.clip(inputAudio, -1.0, 1.0) * 32767).astype(np.int16)
        for i in range(num_frames):
            start = i * frame_length
            stop = min((i + 1) * frame_length, len(audio_int16))
            frame = np.zeros(frame_length, dtype=np.int16)
            frame[:stop-start] = audio_int16[start:stop]
            is_speech = vad.is_speech(frame.tobytes(), sample_rate=self.sample_rate)
            flags[i] = is_speech
        return flags, frame_length
    

    def log_spectral_distance(self, audioReference, audioTarget, nFft=512, hop=128):

        refStft = lr.stft(audioReference, n_fft=nFft, hop_length=hop)
        targetStft = lr.stft(audioTarget, n_fft=nFft, hop_length=hop)

        minLength = min(refStft.shape[1], targetStft.shape[1])
        refStft = refStft[:, :minLength]
        targetStft = targetStft[:, :minLength]

        refStftMaximun = np.maximum(np.abs(refStft), self.EPS)
        targetStftMaximun = np.maximum(np.abs(targetStft), self.EPS)

        diffDb = 20*np.log10(refStftMaximun) - 20*np.log10(targetStftMaximun)

        lsdT = np.sqrt(np.mean(diffDb**2, axis=0))

        return float(np.mean(lsdT)), float(np.median(lsdT) )


    def mfcc_dist(self, audioReference, audioTarget, nMfcc=13, hop=256):

        mfccRef = lr.feature.mfcc(y=audioReference, sr=self.sample_rate, n_mfcc=nMfcc, hop_length=hop)
        mfccTarget = lr.feature.mfcc(y=audioTarget, sr=self.sample_rate, n_mfcc=nMfcc, hop_length=hop)

        minLength = min(mfccRef.shape[1], mfccTarget.shape[1])
        mfccRef = mfccRef[:, :minLength]
        mfccTarget = mfccTarget[:, :minLength]

        distance = np.linalg.norm(mfccRef - mfccTarget, axis=0)

        return float(np.mean(distance)), float(np.median(distance))
    

    def snr_estimate_from_nonspeech(self, audioNonspeech, audioSpeech, frameMs=30, nFFT=512, hop=128):

        flags, frameLength = self._vad_flags(audioNonspeech, frameMs)
        mask = np.repeat(flags, frameLength)[:len(audioNonspeech)]

        pninput, _ = self._stft_mag2(audioNonspeech, n_fft=nFFT, hop=hop)
        psoutput, _ = self._stft_mag2(audioSpeech,    n_fft=nFFT, hop=hop)

        frameLength = min(pninput.shape[1], psoutput.shape[1], int(np.ceil(len(mask)/hop)))
        frameMsStft = 1000.0 * hop / self.sample_rate
        speechFrames = []

        for frame in range(frameLength):
            idx = int(round((frame * frameMsStft) / frameMs))
            idx = min(idx, len(flags) - 1)
            if flags[idx]:
                speechFrames.append(frame)

        monoSpeechFrames = list(set(range(frameLength)) - set(speechFrames))

        if len(monoSpeechFrames) == 0 or len(speechFrames) == 0:
            return None, None, None

        noiseProfile = np.mean(pninput[:, monoSpeechFrames], axis=1, keepdims=True) + self.EPS
        Npow = float(np.sum(noiseProfile))

        snrInput = []
        snrOutput = []
        for frame in speechFrames:
            psInput  = float(np.sum(pninput[:, frame]))
            psOutput = float(np.sum(psoutput[:, frame]))
            snrInput.append( 10 * np.log10((psInput  + self.EPS) / Npow) )
            snrOutput.append(10 * np.log10((psOutput + self.EPS) / Npow) )

        snrInput  = float(np.mean(snrInput))
        snrOutput = float(np.mean(snrOutput))
        return snrInput, snrOutput, (snrOutput - snrInput)


    def audio_compare(self, referenceAudio, processedAudio):

        numFrames = min(len(referenceAudio), len(processedAudio))
        referenceAudioOutput = np.asarray(referenceAudio[:numFrames], dtype=float)
        processedAudioOutput = np.asarray(processedAudio[:numFrames], dtype=float)

        maxDiff = max(np.max(np.abs(referenceAudioOutput)), np.max(np.abs(processedAudioOutput)), 1.0)

        referenceAudioOutput /= maxDiff
        processedAudioOutput /= maxDiff

        flags, frameLength = self._vad_flags(referenceAudio)
        mask = np.repeat(flags, frameLength)[:len(referenceAudioOutput)]
        nsInput = referenceAudioOutput[~mask] if np.any(~mask) else referenceAudioOutput[:0]
        nsOutput = processedAudioOutput[~mask] if np.any(~mask) else processedAudioOutput[:0]
        nsRmsInputDb = self.compute_rms(nsInput) if len(nsInput) > 0 else None
        nsRmsOutputDb = self.compute_rms(nsOutput) if len(nsOutput) > 0 else None
        nsReductionDb = (nsRmsInputDb - nsRmsOutputDb) if nsRmsInputDb is not None and nsRmsOutputDb is not None else None

        spInput = referenceAudioOutput[mask] if np.any(mask) else referenceAudioOutput[:0]
        spOutput = processedAudioOutput[mask] if np.any(mask) else processedAudioOutput[:0]
        spRmsInputDb = self.compute_rms(spInput) if len(spInput) > 0 else None
        spRmsOutputDb = self.compute_rms(spOutput) if len(spOutput) > 0 else None
        speechLevelDeltaDb = (spRmsInputDb - spRmsOutputDb) if spRmsInputDb is not None and spRmsOutputDb is not None else None

        snrInput, snrOutput, snrDelta = self.snr_estimate_from_nonspeech(referenceAudioOutput, processedAudioOutput)

        lsdMeanDb, lsdMedDb = self.log_spectral_distance(referenceAudioOutput, processedAudioOutput)
        mfccMean, mfccMed = self.mfcc_dist(referenceAudioOutput, processedAudioOutput)

        return {
            "nsRmsInputDb": nsRmsInputDb,
            "nsRmsOutputDb": nsRmsOutputDb,
            "nsReductionDb": nsReductionDb,
            "spRmsInputDb": spRmsInputDb,
            "spRmsOutputDb": spRmsOutputDb,
            "speechLevelDeltaDb": speechLevelDeltaDb,
            "snrInput": snrInput,
            "snrOutput": snrOutput,
            "snrDelta": snrDelta,
            "lsdMeanDb": lsdMeanDb,
            "lsdMedDb": lsdMedDb,
            "mfccMean": mfccMean,
            "mfccMed": mfccMed
        }
