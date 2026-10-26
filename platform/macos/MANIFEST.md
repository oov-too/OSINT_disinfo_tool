# macos: what the administrator stages

OCR backend: Apple Vision (tools/ocr_vision.swift compiled with swiftc at install); Tesseract as the fallback. The install script detects the OS and selects it; setup stage 0 reports the detection and a test render on each machine and asks only if something is missing.

| Item | Where it goes in the bundle | Why | How the install script and stage 0 detect it | SHA-256 (fill when staged) |
|---|---|---|---|---|
| Vision OCR | platform/macos/ocr_vision.swift (carried) | compiled at install with `swiftc -O` into <project>/.ledger/bin/ocr_vision (the Xcode command line tools provide swiftc) | swiftc on PATH |  |
| Tesseract (fallback) | platform/macos/tesseract/ (stage: binary, its libraries and tessdata/eng.traineddata) | only if Vision is unavailable | tesseract on PATH or $LEDGER_TESSERACT_CMD |  |
| ffmpeg | platform/macos/ffmpeg (stage: a static build) | audio and video decoding for transcription | ffmpeg on PATH |  |
| transcription engine | wheels/deps/ (stage: faster-whisper and its dependency wheels for macOS) | local transcription of recordings | `python3 -c 'import faster_whisper'` |  |
| whisper weights | platform/macos/whisper/ or a shared folder (stage: e.g. faster-whisper-small) | never downloaded at run time | ledger.toml [acquire] whisper_weights or $LEDGER_WHISPER_WEIGHTS |  |

Nothing here is fetched by the bundle or the install script. Stage each item from the institution's own mirror, then record its checksum here and re-run `python3 install/install.py --write-checksums` so the bundle's CHECKSUMS.sha256 covers it.
