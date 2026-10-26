# linux: what the administrator stages

OCR backend: Tesseract (the tesseract binary and tessdata). The install script detects the OS and selects it; setup stage 0 reports the detection and a test render on each machine and asks only if something is missing.

| Item | Where it goes in the bundle | Why | How the install script and stage 0 detect it | SHA-256 (fill when staged) |
|---|---|---|---|---|
| Tesseract | platform/linux/tesseract/ (stage: the binary and its libraries, or the distribution's package files, and tessdata/eng.traineddata) | OCR of scanned pages | tesseract on PATH or $LEDGER_TESSERACT_CMD |  |
| ffmpeg | platform/linux/ffmpeg (stage: a static build) | audio and video decoding for transcription | ffmpeg on PATH |  |
| transcription engine | wheels/deps/ (stage: faster-whisper and its dependency wheels for Linux) | local transcription | `python3 -c 'import faster_whisper'` |  |
| whisper weights | platform/linux/whisper/ or a shared folder | never downloaded at run time | ledger.toml [acquire] whisper_weights |  |

Nothing here is fetched by the bundle or the install script. Stage each item from the institution's own mirror, then record its checksum here and re-run `python3 install/install.py --write-checksums` so the bundle's CHECKSUMS.sha256 covers it.
