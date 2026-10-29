// Detector de pessoa em quadro, usando o Vision do proprio macOS.
// Companheiro do comando `aroll` — compilado em bin/aroll-pessoas.
//
// uso:    aroll-pessoas <imagem> [imagem...]
// saida:  caminho <TAB> area_da_maior_pessoa <TAB> altura_do_maior_rosto
//         as duas medidas sao fracao do quadro (0 a 1); -1 = nao consegui ler
//
// compilar:  swiftc -O -o bin/aroll-pessoas src/aroll-pessoas.swift (o install.sh faz)

import Foundation
import Vision
import AppKit

for caminho in CommandLine.arguments.dropFirst() {
    guard let img = NSImage(contentsOfFile: caminho),
          let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
        print("\(caminho)\t-1\t-1")
        continue
    }

    let handler = VNImageRequestHandler(cgImage: cg, options: [:])
    let pessoas = VNDetectHumanRectanglesRequest()
    if #available(macOS 12.0, *) {
        // tronco em vez de corpo inteiro: em plano medio a perna fica fora do quadro
        pessoas.upperBodyOnly = true
    }
    let rostos = VNDetectFaceRectanglesRequest()

    try? handler.perform([pessoas, rostos])

    var areaPessoa = 0.0
    for obs in (pessoas.results ?? []) {
        let r = obs.boundingBox
        areaPessoa = max(areaPessoa, Double(r.width * r.height))
    }
    var alturaRosto = 0.0
    for obs in (rostos.results ?? []) {
        alturaRosto = max(alturaRosto, Double(obs.boundingBox.height))
    }

    print(String(format: "%@\t%.4f\t%.4f", caminho, areaPessoa, alturaRosto))
}
