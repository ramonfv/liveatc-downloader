# 🎙️ Audio Processing Configuration Guide

## Descrição Geral

Este projeto foi refatorado para usar gerenciamento centralizado de configuração, permitindo ajustar todo o pipeline de processamento de áudio sem modificar o código.

Existem **3 formas** para configurar o processamento:

1. **JSON** (`config.json`) - Recomendado para ambientes de produção
2. **.env** (`.env`) - Recomendado para desenvolvimento local
3. **Programaticamente** - Para integração em outros scripts

---

## 🚀 Quick Start

### Opção 1: Usar config.json (Recomendado)

1. **Copie o arquivo de configuração padrão:**
   ```bash
   copy config.json config_my_project.json
   ```

2. **Edite os paths no arquivo:**
   ```json
   {
     "audio_paths": {
       "input_audio": "seu/caminho/audio_entrada.wav",
       "output_audio": "seu/caminho/audio_saida_limpo.wav",
       "reference_audio": null
     },
     ...
   }
   ```

3. **Execute o processamento:**
   ```bash
   python mainAudioProcessing.py
   ```

### Opção 2: Usar .env (Ambiente Local)

1. **Crie um arquivo `.env` na raiz do projeto:**
   ```bash
   copy .env.example .env
   ```

2. **Configure as variáveis de ambiente:**
   ```bash
   INPUT_AUDIO_PATH=C:\caminho\audio_entrada.wav
   OUTPUT_AUDIO_PATH=C:\caminho\audio_saida_limpo.wav
   
   # Customize configurações de processamento
   NEURAL_STRATEGY=complex
   VAD_MODE=3
   LOUDNESS_TARGET_DBFS=-20.0
   ```

3. **Execute com .env:**
   ```python
   from mainAudioProcessing import process_audio_with_config
   process_audio_with_config(".env")
   ```

### Opção 3: Uso Programático

```python
from config_manager import ConfigManager
from audioProcess.audioProcessing import AudioProcessor

# Carregar configuração
config = ConfigManager.from_json("config.json")

# Validar
if not config.validate():
    raise ValueError("Config inválida!")

# Usar valores
input_path = config.get_input_audio_path()
fir_settings = config.get_fir_filter_settings()

# Processar
processor = AudioProcessor(input_path)
filtered = processor.bandPassFilterFir(
    fir_settings['low_freq'],
    fir_settings['high_freq']
)
```

---

## 📋 Estrutura de config.json

### Seção: audio_paths
```json
{
  "audio_paths": {
    "input_audio": "C:\\path\\to\\audio.wav",      // OBRIGATÓRIO
    "output_audio": "C:\\path\\to\\output.wav",    // OBRIGATÓRIO
    "reference_audio": null                         // Opcional (para métricas)
  }
}
```

### Seção: audio_processing

#### FIR Filter
```json
{
  "fir_filter": {
    "enabled": true,              // Ativa/desativa filtro
    "low_freq": 250,              // Frequência mínima (Hz)
    "high_freq": 3400,            // Frequência máxima (Hz)
    "numtaps": 401,               // Número de coeficientes
    "equalize": true              // Normalizar resposta
  }
}
```

**Recomendações:**
- Para **ATC (Controle de Tráfego Aéreo)**: 250-3400 Hz
- Para **Fala em geral**: 300-3500 Hz
- Para **Comunicação telefônica**: 300-3400 Hz

#### Wiener Denoise
```json
{
  "wiener_denoise": {
    "enabled": true,
    "noise_window_s": 1.5,        // Janela de análise de ruído (segundos)
    "alpha_spec": 0.8,            // Suavização espectral (0-1)
    "alpha_dd": 0.98,             // Suavização decisão (0-1)
    "bias_correction": 1.5,       // Fator de correção de viés
    "min_gain_db": -15.0          // Ganho mínimo permitido (dB)
  }
}
```

**Dicas:**
- `alpha_spec` mais alto = menos suavização, mais detalhes
- `alpha_dd` mais alto = suavização no tempo mais conservadora
- `min_gain_db` mais negativo = permite ganho maior (menos proteção)

#### Neural Enhancement
```json
{
  "neural_enhancement": {
    "enabled": true,
    "strategy": "complex",        // "lite", "offline", ou "complex"
    "dry_wet": 0.9,               // 0.9 = 90% processado, 10% original
    "device": "cuda",             // "cuda" (GPU) ou "cpu"
    "model_name": "dns64"         // Nome do modelo
  }
}
```

**Estratégias disponíveis:**
| Estratégia | Modelo | Velocidade | Qualidade | Uso |
|-----------|--------|-----------|-----------|-----|
| **lite** | RNNoise | Muito rápida | Boa | CPU, tempo real |
| **offline** | MetricGAN | Moderada | Excelente | Produção |
| **complex** | FB Denoiser | Lenta | Melhor | Batch processing |

#### VAD Gate
```json
{
  "vad_gate": {
    "enabled": true,
    "frame_ms": 30,               // Tamanho do frame (10, 20, 30 ms)
    "mode": 3,                    // 0=relaxado, 3=agressivo
    "hang_ms": 150,               // Suavização temporal (ms)
    "atten_db": 80                // Atenuação de silêncio (dB)
  }
}
```

**Modos VAD:**
- **Mode 0**: Relaxado - Perde pouca fala real
- **Mode 1**: Moderado
- **Mode 2**: Agressivo
- **Mode 3**: Muito agressivo - Remove mais ruído

#### Loudness Normalize
```json
{
  "loudness_normalize": {
    "enabled": true,
    "target_dbfs": -20.0,         // Nível alvo em dBFS
    "top_db": 25.0                // Limiar de silêncio (dB)
  }
}
```

**Padrões:**
- `-20 dBFS`: Podcast, áudio geral
- `-14 dBFS`: Vídeo, streaming
- `-23 dBFS`: Broadcast

#### Resampling
```json
{
  "resampling": {
    "enabled": true,
    "target_sr": 16000,           // Taxa de amostragem destino (Hz)
    "res_type": "kaiser_best"     // Qualidade: "kaiser_best" é superior
  }
}
```

---

## 📄 Variáveis de Ambiente (.env)

Complete lista de variáveis suportadas:

```bash
# Paths
INPUT_AUDIO_PATH=
OUTPUT_AUDIO_PATH=
REFERENCE_AUDIO_PATH=

# FIR Filter
FIR_FILTER_ENABLED=true
FIR_LOW_FREQ=250
FIR_HIGH_FREQ=3400
FIR_NUMTAPS=401
FIR_EQUALIZE=true

# Wiener Denoise
WIENER_DENOISE_ENABLED=true
WIENER_NOISE_WINDOW_S=1.5
WIENER_ALPHA_SPEC=0.8
WIENER_ALPHA_DD=0.98
WIENER_BIAS_CORRECTION=1.5
WIENER_MIN_GAIN_DB=-15.0

# Neural Enhancement
NEURAL_ENHANCEMENT_ENABLED=true
NEURAL_STRATEGY=complex
NEURAL_DRY_WET=0.9
NEURAL_DEVICE=cuda
NEURAL_MODEL_NAME=dns64

# VAD Gate
VAD_GATE_ENABLED=true
VAD_FRAME_MS=30
VAD_MODE=3
VAD_HANG_MS=150
VAD_ATTEN_DB=80

# Loudness Normalization
LOUDNESS_NORMALIZE_ENABLED=true
LOUDNESS_TARGET_DBFS=-20.0
LOUDNESS_TOP_DB=25.0

# Resampling
RESAMPLING_ENABLED=true
RESAMPLING_TARGET_SR=16000
RESAMPLING_RES_TYPE=kaiser_best

# Output Settings
SAVE_FILTERED_AUDIO=true
SAVE_VAD_SEGMENTS=false
SAVE_METRICS=false
LOG_PROCESSING=true

# Metrics
COMPUTE_LSD=false
COMPUTE_MFCC=false
COMPUTE_SNR=false
METRICS_N_FFT=512
METRICS_HOP_LENGTH=160
```

---

## 🔧 Exemplos Práticos

### Exemplo 1: Processamento Mínimo (Apenas Filtro)

**config.json:**
```json
{
  "audio_paths": {
    "input_audio": "input.wav",
    "output_audio": "output.wav"
  },
  "audio_processing": {
    "fir_filter": {"enabled": true, "low_freq": 250, "high_freq": 3400},
    "wiener_denoise": {"enabled": false},
    "neural_enhancement": {"enabled": false},
    "vad_gate": {"enabled": false},
    "loudness_normalize": {"enabled": false},
    "resampling": {"enabled": false}
  }
}
```

### Exemplo 2: Máxima Qualidade (Todos os Filtros)

**config.json:**
```json
{
  "audio_paths": {
    "input_audio": "input.wav",
    "output_audio": "output_hq.wav"
  },
  "audio_processing": {
    "fir_filter": {"enabled": true},
    "wiener_denoise": {"enabled": true},
    "neural_enhancement": {"enabled": true, "strategy": "complex", "device": "cuda"},
    "vad_gate": {"enabled": true, "mode": 3},
    "loudness_normalize": {"enabled": true},
    "resampling": {"enabled": true, "target_sr": 16000}
  }
}
```

### Exemplo 3: CPU-Friendly (Rápido)

**config.json:**
```json
{
  "audio_processing": {
    "fir_filter": {"enabled": true},
    "wiener_denoise": {"enabled": true},
    "neural_enhancement": {"enabled": true, "strategy": "lite", "device": "cpu"},
    "vad_gate": {"enabled": true, "mode": 1},
    "loudness_normalize": {"enabled": true},
    "resampling": {"enabled": false}
  }
}
```

### Exemplo 4: ATC Específico

**config.json:**
```json
{
  "audio_processing": {
    "fir_filter": {
      "enabled": true,
      "low_freq": 200,      // Um pouco mais baixo para ATC
      "high_freq": 3500     // Um pouco mais alto
    },
    "vad_gate": {"mode": 3, "atten_db": 90},
    "loudness_normalize": {"target_dbfs": -18.0}
  }
}
```

---

## 🐍 API ConfigManager

### Carregamento

```python
from config_manager import ConfigManager

# De JSON
config = ConfigManager.from_json("config.json")

# De .env
config = ConfigManager.from_env(".env")
```

### Getters

```python
# Paths
input_path = config.get_input_audio_path()
output_path = config.get_output_audio_path()

# Settings
fir = config.get_fir_filter_settings()
wiener = config.get_wiener_denoise_settings()
neural = config.get_neural_enhancement_settings()
vad = config.get_vad_gate_settings()
loudness = config.get_loudness_normalize_settings()
resample = config.get_resampling_settings()

# Check status
is_fir_enabled = config.is_enabled("fir_filter")
```

### Validação

```python
if config.validate():
    print("✓ Config válida!")
else:
    print("✗ Config inválida!")
```

### Export

```python
# Get as dict
config_dict = config.to_dict()

# Save to JSON
config.to_json("config_backup.json")
```

---

## 📊 Dependências de Python

```bash
pip install numpy librosa scipy soundfile webrtcvad pyrnnoise torch speechbrain denoiser python-dotenv
```

---

## ✅ Checklist de Uso

- [ ] Criar `config.json` ou `.env` com paths corretos
- [ ] Validar configuração com `config.validate()`
- [ ] Escolher strategy neural adequada (lite/offline/complex)
- [ ] Testar com arquivo pequeno primeiro
- [ ] Monitorar logs de processamento
- [ ] Validar qualidade do áudio de saída
- [ ] Documentar configuração final

---

## 🐛 Troubleshooting

### "Configuration file not found"
```
Solução: Certifique-se que config.json existe e está no mesmo diretório
```

### "CUDA not available, falling back to CPU"
```
Solução: Instale CUDA ou use strategy="lite" ou "offline"
```

### "Neural model not found"
```
Solução: Primeira execução baixa modelo automaticamente. Aguarde.
```

### Arquivo de saída silencioso
```
Solução: Verifique VAD_MODE (tente reduzir) ou desative VAD_GATE
```

### Audio distorcido
```
Solução: Reduza NEURAL_DRY_WET para 0.7, ou desative VAD_GATE
```

---

## 📝 Próximos Passos

1. **Batch Processing**: Processar múltiplos arquivos
2. **Logging Detalhado**: Salvar métricas por etapa
3. **Web API**: Expor via REST API
4. **GUI**: Interface gráfica para configuração
5. **Presets**: Configurações pré-definidas por caso de uso

---

## 📞 Suporte

Para mais informações, consulte:
- [AUDIO_PROCESSING_WORKFLOW.md](AUDIO_PROCESSING_WORKFLOW.md) - Detalhes técnicos do pipeline
- [config.json](config.json) - Configuração padrão
- [.env.example](.env.example) - Template de variáveis de ambiente
