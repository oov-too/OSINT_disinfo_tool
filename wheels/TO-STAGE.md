# Wheels to stage

The administrator places these in wheels/deps/ from the institution's mirror (`pip download --only-binary=:all: --platform <tag> --python-version <3.11|3.12> -d wheels/deps <names>` on a machine that may reach it), then re-runs `python3 install/install.py --write-checksums`.

| Platform | Wheel | Why | Reason it is not here |
|---|---|---|---|
| macos | faster-whisper | local transcription (with ctranslate2, tokenizers, av, onnxruntime); or openai-whisper with torch | large and platform-specific: always staged by the administrator |
| macos | whisper weights | the model weights (e.g. small), placed where ledger.toml [acquire] whisper_weights points | large and platform-specific: always staged by the administrator |
| linux | faster-whisper | local transcription (with ctranslate2, tokenizers, av, onnxruntime); or openai-whisper with torch | large and platform-specific: always staged by the administrator |
| linux | whisper weights | the model weights (e.g. small), placed where ledger.toml [acquire] whisper_weights points | large and platform-specific: always staged by the administrator |
| windows | faster-whisper | local transcription (with ctranslate2, tokenizers, av, onnxruntime); or openai-whisper with torch | large and platform-specific: always staged by the administrator |
| windows | whisper weights | the model weights (e.g. small), placed where ledger.toml [acquire] whisper_weights points | large and platform-specific: always staged by the administrator |
