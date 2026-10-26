// OCR with Apple Vision, the macOS backend of the ledger (tools/ocr_vision.swift). Build: swiftc -O -o <dest>/ocr_vision ocr_vision.swift
// Run: ocr_vision img1.png img2.png ...  Prints "=== <file>" then one recognised line per text line. (Header rewritten by tools/build_bundle.py.)
import Foundation
import Vision
import AppKit
let args = CommandLine.arguments.dropFirst()
for path in args {
    guard let img = NSImage(contentsOfFile: path), let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else { FileHandle.standardError.write("cannot load \(path)\n".data(using: .utf8)!); continue }
    let req = VNRecognizeTextRequest()
    req.recognitionLevel = .accurate
    req.usesLanguageCorrection = true
    req.recognitionLanguages = ["en-US"]
    let handler = VNImageRequestHandler(cgImage: cg, options: [:])
    do { try handler.perform([req]) } catch { FileHandle.standardError.write("fail \(path): \(error)\n".data(using: .utf8)!); continue }
    print("=== \(URL(fileURLWithPath: path).lastPathComponent)")
    for obs in req.results ?? [] { if let c = obs.topCandidates(1).first { print(c.string) } }
}
