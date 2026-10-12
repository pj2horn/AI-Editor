#!/usr/bin/env swift
// vision.swift — Apple's built-in Vision framework from the command line.
// Free, local, no installs. macOS 12+.
//
//   swift mac/vision.swift ocr    <image>                 # on-screen text, one line per block
//   swift mac/vision.swift faces  <image>                 # face count + pixel boxes
//   swift mac/vision.swift cutout <image> <out.png> [--green]
//                                                        # person cutout (transparent, or on green)
//
// Compile once for faster startup:  swiftc -O mac/vision.swift -o ~/bin/vision
//
// NOTE: written on Linux without a Swift toolchain — not yet compiled or run.

import CoreImage
import Foundation
import Vision

func fail(_ msg: String) -> Never {
    FileHandle.standardError.write((msg + "\n").data(using: .utf8)!)
    exit(1)
}

let args = CommandLine.arguments
guard args.count >= 3 else {
    fail("usage: vision ocr|faces <image>  |  vision cutout <image> <out.png> [--green]")
}
let cmd = args[1]
guard let image = CIImage(contentsOf: URL(fileURLWithPath: args[2])) else {
    fail("can't read image: \(args[2])")
}
let handler = VNImageRequestHandler(ciImage: image, options: [:])
let W = image.extent.width
let H = image.extent.height

do {
    switch cmd {
    case "ocr":
        let req = VNRecognizeTextRequest()
        req.recognitionLevel = .accurate
        req.usesLanguageCorrection = true
        try handler.perform([req])
        for obs in req.results ?? [] {
            if let top = obs.topCandidates(1).first { print(top.string) }
        }

    case "faces":
        let req = VNDetectFaceRectanglesRequest()
        try handler.perform([req])
        let faces = req.results ?? []
        print("faces: \(faces.count)")
        for f in faces {
            // Vision boxes are normalized with a bottom-left origin; print top-left pixels.
            let b = f.boundingBox
            print("x=\(Int(b.minX * W)) y=\(Int((1 - b.maxY) * H)) w=\(Int(b.width * W)) h=\(Int(b.height * H))")
        }

    case "cutout":
        guard args.count >= 4 else { fail("usage: vision cutout <image> <out.png> [--green]") }
        let req = VNGeneratePersonSegmentationRequest()
        req.qualityLevel = .accurate
        req.outputPixelFormat = kCVPixelFormatType_OneComponent8
        try handler.perform([req])
        guard let buf = req.results?.first?.pixelBuffer else { fail("no person found") }
        var mask = CIImage(cvPixelBuffer: buf)
        mask = mask.transformed(by: CGAffineTransform(
            scaleX: W / mask.extent.width, y: H / mask.extent.height))
        let bg = args.contains("--green")
            ? CIImage(color: CIColor(red: 0, green: 1, blue: 0)).cropped(to: image.extent)
            : CIImage.empty()
        let out = image.applyingFilter("CIBlendWithMask", parameters: [
            kCIInputBackgroundImageKey: bg,
            kCIInputMaskImageKey: mask,
        ])
        try CIContext().writePNGRepresentation(
            of: out, to: URL(fileURLWithPath: args[3]),
            format: .RGBA8, colorSpace: CGColorSpace(name: CGColorSpace.sRGB)!)
        print(args[3])

    default:
        fail("unknown command: \(cmd)")
    }
} catch {
    fail("vision: \(error)")
}
