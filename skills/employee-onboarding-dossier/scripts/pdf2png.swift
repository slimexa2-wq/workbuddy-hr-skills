import Foundation
import PDFKit
import AppKit

let args = CommandLine.arguments
guard args.count >= 3 else {
    fputs("Usage: pdf2png <pdf_path> <out_dir> [scale]\n", stderr)
    exit(1)
}
let pdfPath = args[1]
let outDir = args[2]
let scale = args.count >= 4 ? (Double(args[3]) ?? 2.0) : 2.0

let url = URL(fileURLWithPath: pdfPath)
guard let doc = PDFDocument(url: url) else {
    fputs("Failed to open PDF: \(pdfPath)\n", stderr)
    exit(1)
}

try? FileManager.default.createDirectory(atPath: outDir, withIntermediateDirectories: true)

for i in 0..<doc.pageCount {
    guard let page = doc.page(at: i) else { continue }
    let bounds = page.bounds(for: .mediaBox)
    let w = Int(bounds.width * CGFloat(scale))
    let h = Int(bounds.height * CGFloat(scale))
    guard let rep = NSBitmapImageRep(
        bitmapDataPlanes: nil,
        pixelsWide: w,
        pixelsHigh: h,
        bitsPerSample: 8,
        samplesPerPixel: 4,
        hasAlpha: true,
        isPlanar: false,
        colorSpaceName: .calibratedRGB,
        bytesPerRow: 0,
        bitsPerPixel: 0
    ) else { continue }
    
    NSGraphicsContext.saveGraphicsState()
    if let ctx = NSGraphicsContext(bitmapImageRep: rep) {
        NSGraphicsContext.current = ctx
        NSColor.white.set()
        NSRect(x: 0, y: 0, width: w, height: h).fill()
        ctx.cgContext.scaleBy(x: CGFloat(scale), y: CGFloat(scale))
        page.draw(with: .mediaBox, to: ctx.cgContext)
    }
    NSGraphicsContext.restoreGraphicsState()
    
    if let data = rep.representation(using: .png, properties: [:]) {
        let outFile = String(format: "%@/page-%04d.png", outDir, i + 1)
        try? data.write(to: URL(fileURLWithPath: outFile))
        print(outFile)
    }
}
