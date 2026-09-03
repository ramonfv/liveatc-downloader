# Workflow de Processamento de Áudio - LiveATC Downloader

## 📊 Visão Geral do Pipeline

O sistema realiza uma série de transformações no áudio para melhorar sua qualidade, removendo ruído e normalizando o volume. O fluxo é sequencial e cada etapa prepara o áudio para a próxima.

---

## 🔄 Fluxo Completo do Processamento

```
┌─────────────────────────────────────────────────────────────────┐
│ ENTRADA: Arquivo de Áudio WAV/MP3                              │
│ Exemplo: voo_flymov1234_controleParaCopiloto1.wav              │
│ Taxa de Amostragem: Carregado como 16 kHz                       │
└─────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│ ETAPA 1: Band-Pass Filter (FIR)                                 │
│ ─────────────────────────────────────────────────────────────────│
│ Função: bandPassFilterFir(250, 3400)                             │
│                                                                  │
│ O que faz:                                                       │
│ • Aplica filtro FIR (Finite Impulse Response) passa-faixa       │
│ • Mantém frequências entre 250 Hz e 3400 Hz                     │
│ • Remove ruído fora desta faixa de frequência                   │
│ • Simula a faixa típica de comunicação ATC (voz humana)        │
│ • Compensação de ganho para manter nível de amplitude           │
│                                                                  │
│ Parâmetros:                                                      │
│ - low_freq: 250 Hz                                               │
│ - high_freq: 3400 Hz                                             │
│ - numtaps: 401 (comprimento do filtro)                           │
│ - window: Kaiser                                                 │
│ - equalize: True (normaliza resposta em frequência)             │
└─────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│ ETAPA 2: Wiener Denoise (Filtro Estatístico Mínimo)            │
│ ─────────────────────────────────────────────────────────────────│
│ Função: wiener_minstat_denoise(fir_filtered_audio, ...)         │
│                                                                  │
│ O que faz:                                                       │
│ • Reduz ruído usando filtro de Wiener adaptativo                │
│ • Estima o ruído nos frames silenciosos                         │
│ • Aplica ganho de Wiener no domínio espectral                   │
│ • Mantém componentes do sinal com maior SNR                     │
│ • Processamento em tempo curto de Fourier (STFT)                │
│                                                                  │
│ Parâmetros:                                                      │
│ - noiseWindowS: 1.5 segundos (janela de ruído)                 │
│ - alphaSpec: 0.8 (suavização espectral)                         │
│ - alphaDd: 0.98 (suavização decisão)                            │
│ - biasCorrection: 1.5                                            │
│ - minGainDb: -15.0 dB (ganho mínimo permitido)                 │
│ - Parâmetros STFT: n_fft=512, hop=160, window='hann'           │
└─────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│ ETAPA 3: Neural Network Enhancement (FB Denoiser)              │
│ ─────────────────────────────────────────────────────────────────│
│ Função: _enhance_neural(..., strategy="complex")                │
│         ↳ _enhance_fb_denoiser(...)                             │
│                                                                  │
│ O que faz:                                                       │
│ • Usa rede neural pré-treinada (DNS64 - Deep Noise Suppression) │
│ • Processamento com modelo Facebook Denoiser                    │
│ • Redução avançada de ruído usando deep learning                │
│ • Resampling para taxa do modelo (normalmente 16 kHz)          │
│ • Combinação (dry/wet) do sinal processado: 90% processado     │
│                                                                  │
│ Parâmetros:                                                      │
│ - strategy: "complex" (usa FB Denoiser, outras opções:         │
│             "lite" = RNNoise, "offline" = MetricGAN)           │
│ - dry_wet: 0.9 (90% sinal processado, 10% original)            │
│ - device: "cuda" (GPU, mais rápido que CPU)                    │
│ - model_name: "dns64"                                            │
│                                                                  │
│ Modelos disponíveis:                                            │
│ • lite: RNNoise (rápido, leve)                                 │
│ • offline: MetricGAN (qualidade média)                         │
│ • complex: FB Denoiser (melhor qualidade)                      │
└─────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│ ETAPA 4: Voice Activity Detection Gate (VAD Gate)               │
│ ─────────────────────────────────────────────────────────────────│
│ Função: vadGate(neuralNoiseReduction, ...)                      │
│                                                                  │
│ O que faz:                                                       │
│ • Detecta atividade de voz usando WebRTC VAD                    │
│ • Silencia (atenuação) frames sem fala                          │
│ • Suavização com janela temporal (hang_ms)                      │
│ • Gera segmentos com timestamps de fala detectada              │
│                                                                  │
│ Parâmetros:                                                      │
│ - frame_ms: 30 ms (tamanho do frame de análise)                │
│ - mode: 3 (agressividade: 0=relaxado, 3=agressivo)            │
│ - hang_ms: 150 ms (janela de suavização)                       │
│ - atten_db: 80 dB (atenuação de não-fala)                      │
│                                                                  │
│ Saídas:                                                          │
│ - output_gate_fir: áudio com gating aplicado                   │
│ - segments: lista de (tempo_inicio, tempo_fim) com fala        │
│ - flags: booleano por frame indicando fala detectada           │
└─────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│ ETAPA 5: Loudness Normalization (Normalização Adaptativa)      │
│ ─────────────────────────────────────────────────────────────────│
│ Função: loudnessNormalizeAdaptive(output_gate_fir, ...)        │
│                                                                  │
│ O que faz:                                                       │
│ • Calcula RMS (Root Mean Square) do áudio                       │
│ • Normaliza para um nível alvo de -20 dBFS                      │
│ • Identifica segmentos de áudio relevantes                      │
│ • Aplica ganho uniforme mantendo dinâmica                       │
│ • Limita picos para evitar clipping (saturação)                 │
│                                                                  │
│ Parâmetros:                                                      │
│ - target_dbfs: -20.0 dB (nível alvo)                           │
│ - top_db: 25.0 dB (limiar para detectar silêncio)              │
│                                                                  │
│ Retorna:                                                         │
│ - fir_norm: áudio normalizado                                   │
│ - gain_fir: ganho aplicado                                      │
└─────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│ ETAPA 6: Resampling para 16 kHz                                │
│ ─────────────────────────────────────────────────────────────────│
│ Função: resample_to_16k(fir_norm, ...)                          │
│                                                                  │
│ O que faz:                                                       │
│ • Resampling com qualidade Kaiser (best)                        │
│ • Taxa de saída: 16 kHz (padrão para aplicações de voz)        │
│ • Preserva qualidade de áudio durante resampling               │
│                                                                  │
│ Parâmetros:                                                      │
│ - target_sr: 16000 Hz                                            │
│ - res_type: "kaiser_best" (alta qualidade)                     │
└─────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│ SAÍDA: Arquivo de Áudio Processado                              │
│ ─────────────────────────────────────────────────────────────────│
│ Arquivo: voo_flymov1234_controleParaCopiloto1Cleaned.wav       │
│ Taxa de Amostragem: 16 kHz                                      │
│ Formato: WAV (PCM)                                              │
│ Características:                                                 │
│ • Ruído significativamente reduzido                             │
│ • Frequências de fala preservadas (250-3400 Hz)                │
│ • Normalização de volume consistente                            │
│ • Silêncios atenuados                                           │
│ • Pronto para reconhecimento de voz ou análise                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📈 Resumo das Transformações

| Etapa | Tipo | Entrada | Saída | Objetivo |
|-------|------|---------|-------|----------|
| 1 | **FIR Filter** | Áudio bruto | Áudio filtrado (250-3400 Hz) | Remover ruído fora da banda de voz |
| 2 | **Wiener Denoise** | Áudio filtrado | Áudio denoizado (Wiener) | Redução estatística de ruído |
| 3 | **Neural Enhancement** | Áudio denoizado | Áudio melhorado (NN) | Redução avançada com deep learning |
| 4 | **VAD Gate** | Áudio melhorado | Áudio com gating + timestamps | Silenciar não-fala, marcar segmentos |
| 5 | **Normalization** | Áudio com gating | Áudio normalizado | Equalizar volume (-20 dBFS) |
| 6 | **Resampling** | Áudio normalizado | Áudio 16 kHz | Padronizar taxa de amostragem |

---

## 🎛️ Parâmetros de Qualidade

### Configurações de Filtro (Etapas 1-2)
- **Banda de Frequência**: 250-3400 Hz (Fala ATC)
- **Tipo de Filtro FIR**: Kaiser, 401 taps
- **Wiener - Janela de Ruído**: 1.5 segundos

### Configurações de Detecção (Etapa 4)
- **VAD Mode**: 3 (Agressivo - remove mais ruído)
- **Frame Duration**: 30 ms
- **Suavização (hang)**: 150 ms
- **Atenuação**: 80 dB

### Configurações de Normalização (Etapa 5)
- **Nível Alvo**: -20 dBFS
- **Proteção contra clipping**: Limita a 0.999

---

## 💾 Fluxo de Dados

```
Input Audio File
    ↓
Load with Librosa (16 kHz)
    ↓
numpy.ndarray (float32, 1D)
    ↓
[1] FIR Band-Pass Filter → numpy.ndarray
    ↓
[2] Wiener Denoise (STFT domain) → numpy.ndarray
    ↓
[3] Neural Enhancement (GPU/CPU) → numpy.ndarray
    ↓
[4] VAD Gate + Attenuation → numpy.ndarray + metadata
    ↓
[5] Loudness Normalize → numpy.ndarray
    ↓
[6] Resample to 16 kHz → numpy.ndarray
    ↓
Write to WAV File (soundfile)
    ↓
Output Audio File
```

---

## 🔌 Métodos Alternados Disponíveis

### Neural Enhancement Strategies
```python
# Estratégia 1: Lite (RNNoise)
_enhance_neural(audio, sr, strategy="lite")  # Rápido, CPU-friendly

# Estratégia 2: Offline (MetricGAN)
_enhance_neural(audio, sr, strategy="offline")  # Balanço qualidade/velocidade

# Estratégia 3: Complex (FB Denoiser) ← USADO NO WORKFLOW ATUAL
_enhance_neural(audio, sr, strategy="complex")  # Melhor qualidade
```

### Filtros Alternativos
```python
# Ao invés de FIR, pode usar IIR (Infinite Impulse Response)
bandPassFilterIir(250, 3400, order=6)  # Mais eficiente, menor latência
```

---

## 📊 Métricas Disponíveis (audioProcess/metrics.py)

Após processamento, é possível comparar com áudio de referência:

| Métrica | Descrição |
|---------|-----------|
| **Log Spectral Distance (LSD)** | Diferença espectral entre áudios |
| **MFCC Distance** | Distância em coeficientes cepstrais |
| **SNR Estimate** | Razão Sinal-Ruído estimada |
| **RMS** | Nível de energia (dB) |
| **VAD Flags** | Segmentos com fala detectada |

---

## 🔍 Exemplo de Uso Completo

```python
from audioProcess.audioProcessing import AudioProcessor

# Carregar áudio
audio_processor = AudioProcessor("input.wav")

# Pipeline completo
fir = audio_processor.bandPassFilterFir(250, 3400)
wiener = audio_processor.wiener_minstat_denoise(fir, 16000)
neural = audio_processor._enhance_neural(wiener, 16000, strategy="complex")
vad, segments, flags = audio_processor.vadGate(neural, 16000, 30, 3, 150, 80)
norm, gain = audio_processor.loudnessNormalizeAdaptive(vad, 16000, -20.0, 25.0)
final = audio_processor.resample_to_16k(norm, 16000)

# Salvar resultado
audio_processor.writeFilteredAudio("output_cleaned.wav", final)

# Segmentos com fala detectada
print(f"Detected speech segments: {segments}")
```

---

## ⚙️ Dependências

- **librosa**: Processamento de áudio e STFT
- **scipy.signal**: Filtros IIR/FIR
- **numpy**: Operações numéricas
- **soundfile**: I/O de arquivos WAV
- **webrtcvad**: Detecção de atividade de voz
- **pyrnnoise**: Denoiser RNNoise
- **torch**: Deep learning (neural enhancement)
- **speechbrain**: Modelos de enhancement (MetricGAN)
- **denoiser**: Facebook AI Denoiser

---

## 🎯 Saídas Principais

### Saída Primária
- **Arquivo WAV**: Áudio processado em 16 kHz, normalizado

### Saídas Secundárias (VAD)
- **Segmentos**: Lista de tuplas `[(start_time, end_time), ...]`
- **Flags**: Array booleano por frame

### Informações de Processamento
- **Gain Aplicado**: Fator de ganho de normalização
- **Taxa Original**: Taxa de amostragem carregada

---

## 🚀 Próximas Etapas Possíveis

1. **Análise de qualidade**: Usar métricas para validar processamento
2. **Reconhecimento de voz**: Passar para ASR (Speech-to-Text)
3. **Armazenamento**: Organizar outputs em estrutura de pastas
4. **Logging**: Documentar parâmetros e tempos de processamento
5. **Batch processing**: Processar múltiplos arquivos em paralelo
