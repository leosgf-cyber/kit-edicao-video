# Histórico: kit-edicao-video

## v1, 29/10/2026

Primeira versão pública. Junta num repositório só as ferramentas de edição de vídeo do autor que rodam
sem API paga: `aroll`, `transcreve`, `transcreve-playlist`, `trilha`, `compila`, `folha`,
`alinha-cameras`, `sobrepoe`, `decupa`, `acha-offline`, as LUTs Stadium Warm e Fuji X100VI e o manual
para o Claude Code (`skill/kit-edicao-video/SKILL.md`, com as receitas de ffmpeg já testadas).

Mudanças em relação às versões de uso pessoal:
- caminhos fixos da máquina do autor trocados por `KIT_VIDEO_MODELOS` (padrão `~/.kit-video/modelos`);
- `transcreve`, `compila` e `trilha` eram funções do `.zshrc` e viraram executáveis em `bin/`;
- `trilha` não sobe mais pro Google Drive, só baixa;
- a LUT S-Log3 da Sony não vai no repositório (é da Sony); o instalador copia da pasta do Resolve;
- `acha-offline` lê o fps do vídeo em vez de supor 23,976;
- saíram os testes de regressão que dependiam de mídia do autor.

Verificado: instalador rodado num HOME limpo; `pytest` 57 passaram; teste real de `transcreve`, `folha`,
`aroll` (com e sem `--so-audio`), `acha-offline`, `compila`, `decupa` (preparar, situacao, planilha) e
`trilha` (simulado). Não testados aqui: `alinha-cameras --resolve` e `sobrepoe` (precisam do Resolve
Studio aberto; a lógica está coberta pelos testes) e `transcreve-playlist` (só sintaxe).
