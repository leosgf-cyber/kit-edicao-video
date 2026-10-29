# Como descrever um clipe (passo 3 do decupa, o único com IA)

Para cada clipe do lote (em `_DECUPA/lotes.json`):

1. Olhe `_DECUPA/folhas/<clipe>.jpg`: os quadros do clipe com `nome mm:ss` embaixo de cada um.
2. Leia `_DECUPA/meta/<clipe>.json` (duração, orientação, fps, câmera) e, se existir,
   `_DECUPA/transcr/<clipe>.json` (fala automática: pista, não verdade; em ruído inventa palavras).
3. Só se a folha não bastar, tire um quadro extra:
   `ffmpeg -v error -ss T -i CLIPE -frames:v 1 -vf "scale=1280:-2" _DECUPA/frames_extra/<clipe>_T.jpg`
4. Grave `_DECUPA/descricoes/<clipe>.json` (UTF-8, tudo texto). Não reescreva descrição que já existe.

| campo | o que vai |
|---|---|
| `clipe` | o nome, igual ao arquivo |
| `grupo` | o assunto que junta vários clipes seguidos (ex.: "Burrata com atum"); mesmo nome em todos do grupo |
| `categoria` | tipo de cena (ex.: "Preparo / montagem", "Ambiente", "Mesa", "Detalhe", "Entrevista") |
| `assunto` | uma frase do que o clipe mostra |
| `itens` | o que aparece em cena, separado por `;` |
| `descricao` | 2 a 5 frases: lugar, o que acontece do começo ao fim |
| `acoes` | linha do tempo `00:00–00:03 o que acontece · 00:03–00:05 ...`, tempos tirados dos rótulos da folha |
| `enquadramento` | plano e ângulo (ex.: "Close, ângulo de 45°") |
| `movimento` | câmera parada, na mão, travelling, reenquadra no fim... |
| `pessoas` | quem aparece e se o rosto é reconhecível; "só mãos" quando for o caso |
| `texto_visivel` | marca, placa, rótulo legível; "nenhum legível" |
| `qualidade` | foco, tremida, obstrução da lente, com os tempos |
| `melhor_trecho` | os trechos que dá para usar, com os tempos |
| `aproveitamento` | exatamente um: `Alto`, `Médio`, `Baixo` ou `Descartar` |
| `incertezas` | o que não dá para afirmar só pela imagem, e por quê |
| `fala` | opcional: só se você ouviu/conferiu a fala e ela importa (substitui a transcrição automática na planilha) |

Regras:
- Descreva o que se vê. Nome de prato, pessoa, lugar ou marca só se estiver escrito na imagem ou no pedido;
  senão, "provável X" e o motivo em `incertezas`.
- Tempos em mm:ss, sempre a partir dos rótulos da folha.
- Português claro, sem jargão.

Depois de todos os lotes, se houver pontos de atenção (marca legível, rosto reconhecível, áudio sensível,
arquivo estranho, clipe que precisa girar), grave `_DECUPA/para_olhar.json`:
`[{"assunto": "...", "clipes": "C4873, C4892", "o_que_e": "..."}]`. Vira a aba "Para olhar" da planilha.
