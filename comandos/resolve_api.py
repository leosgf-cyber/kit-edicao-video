"""Ligação com o DaVinci Resolve Studio (macOS) com as armadilhas de 15/09 codificadas. Só Python 3.12 do venv."""
import sys, time

MODULOS = "/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Modules"
CORES = ["Teal", "Green", "Lime", "Blue", "Purple", "Pink", "Navy", "Olive", "Violet", "Tan", "Brown", "Yellow"]

class ResolveErro(RuntimeError):
    """Mensagem pronta pra imprimir."""

def cor(i):
    return CORES[i % len(CORES)]

def conectar():
    """(resolve, pm, projeto, timeline, media_pool). Exige o Resolve aberto no projeto e na timeline certos."""
    if MODULOS not in sys.path:
        sys.path.append(MODULOS)
    try:
        import DaVinciResolveScript as dvr
    except ImportError:
        raise ResolveErro("módulo da API do Resolve não encontrado: o Resolve Studio está instalado?")
    r = None
    for _ in range(3):
        r = dvr.scriptapp("Resolve")
        if r:
            break
        time.sleep(5)
    if not r:
        raise ResolveErro("Resolve não respondeu: abra o Resolve no projeto certo e rode de novo")
    if r.GetCurrentPage() is None:
        raise ResolveErro("interface do Resolve travada: feche o diálogo aberto e rode de novo")
    pm = r.GetProjectManager(); proj = pm.GetCurrentProject()
    if not proj:
        raise ResolveErro("nenhum projeto aberto no Resolve")
    tl = proj.GetCurrentTimeline()
    if not tl:
        raise ResolveErro("nenhuma timeline aberta: abra a timeline e rode de novo")
    r.OpenPage("edit"); time.sleep(1)
    print(f"Resolve: projeto '{proj.GetName()}', timeline '{tl.GetName()}' (não mexa no Resolve até terminar)")
    return r, pm, proj, tl, proj.GetMediaPool()

def sub_bin(mp, pai, nome):
    """Acha (o primeiro com esse nome) ou cria um bin dentro de `pai`."""
    for f in pai.GetSubFolderList() or []:
        if f.GetName() == nome:
            return f
    f = mp.AddSubFolder(pai, nome)
    if not f:
        raise ResolveErro(f"não consegui criar o bin '{nome}'")
    return f

def clipes_por_caminho(bin_):
    return {c.GetClipProperty("File Path"): c for c in (bin_.GetClipList() or [])}

def importar(mp, bin_, caminhos):
    """Importa em `bin_` só o que ainda não está lá (por caminho). Devolve dict caminho -> item."""
    tem = clipes_por_caminho(bin_); faltam = [c for c in dict.fromkeys(caminhos) if c not in tem]
    if faltam:
        mp.SetCurrentFolder(bin_); mp.ImportMedia(faltam); tem = clipes_por_caminho(bin_)
    ainda = [c for c in caminhos if c not in tem]
    if ainda:
        raise ResolveErro(f"não entraram no bin '{bin_.GetName()}': {ainda[:3]}")
    return tem

def trilha_video(tl, nome):
    """Índice da trilha de vídeo `nome`: acha e esvazia (ligando-a pra receber clipes), ou cria no topo."""
    for i in range(1, tl.GetTrackCount("video") + 1):
        if tl.GetTrackName("video", i) == nome:
            if getattr(tl, "GetIsTrackLocked", lambda t, j: False)("video", i):
                raise ResolveErro(f"destranque a trilha '{nome}' e rode de novo")
            itens = tl.GetItemListInTrack("video", i) or []
            if itens and not tl.DeleteClips(itens):
                raise ResolveErro(f"não consegui esvaziar a trilha '{nome}'")
            tl.SetTrackEnable("video", i, True)
            return i
    if not tl.AddTrack("video"):
        raise ResolveErro("AddTrack falhou")
    i = tl.GetTrackCount("video"); tl.SetTrackName("video", i, nome)
    return i

def colocar(mp, item, sin, sout, trilha, quadro_abs):
    """Só vídeo, na trilha e no quadro pedidos (independe da seleção da interface; provado 64× em 15/09). Item ou None."""
    got = mp.AppendToTimeline([{"mediaPoolItem": item, "startFrame": sin, "endFrame": sout, "mediaType": 1,
                                "trackIndex": trilha, "recordFrame": quadro_abs}]) or []
    g = got[0] if got else None
    if not g or g.GetStart() != quadro_abs or g.GetTrackTypeAndIndex()[1] != trilha:
        return None
    return g

def desligar_trilha(resolve, tl, idx):
    """Na página Deliver o SetTrackEnable responde True sem desligar: sempre volta pra Edit, insiste e confere."""
    resolve.OpenPage("edit")
    for _ in range(5):
        tl.SetTrackEnable("video", idx, False)
        if tl.GetIsTrackEnabled("video", idx) is False:
            return True
        time.sleep(1)
    return False

def salvar(pm):
    """No 21.1 Project.SaveProject vem None; salvar é pelo ProjectManager."""
    return bool(pm.SaveProject())
