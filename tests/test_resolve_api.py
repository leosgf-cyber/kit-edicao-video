import pytest
from comandos import resolve_api as ra

class Trilha:
    def __init__(self, nome, itens=None, ligada=True, trancada=False):
        self.nome, self.itens, self.ligada, self.trancada = nome, itens or [], ligada, trancada

class TimelineFalsa:
    def __init__(self, trilhas, teimosa=0):
        self.t = trilhas; self.teimosa = teimosa          # teimosa = quantas vezes ignora o SetTrackEnable(False)
    def GetTrackCount(self, tipo): return len(self.t)
    def GetTrackName(self, tipo, i): return self.t[i - 1].nome
    def GetIsTrackLocked(self, tipo, i): return self.t[i - 1].trancada
    def GetItemListInTrack(self, tipo, i): return list(self.t[i - 1].itens)
    def DeleteClips(self, itens): self.t = [Trilha(x.nome, [y for y in x.itens if y not in itens], x.ligada) for x in self.t]; return True
    def AddTrack(self, tipo): self.t.append(Trilha("Video %d" % (len(self.t) + 1))); return True
    def SetTrackName(self, tipo, i, nome): self.t[i - 1].nome = nome; return True
    def SetTrackEnable(self, tipo, i, on):
        if not on and self.teimosa > 0: self.teimosa -= 1; return True
        self.t[i - 1].ligada = on; return True
    def GetIsTrackEnabled(self, tipo, i): return self.t[i - 1].ligada

class ResolveFalso:
    def __init__(self): self.paginas = []
    def OpenPage(self, p): self.paginas.append(p); return True

def test_trilha_video_cria_no_topo():
    tl = TimelineFalsa([Trilha("Video 1")])
    assert ra.trilha_video(tl, "SOBREPOSIÇÕES") == 2 and tl.GetTrackName("video", 2) == "SOBREPOSIÇÕES"

def test_trilha_video_esvazia_existente_e_recusa_trancada():
    tl = TimelineFalsa([Trilha("Video 1"), Trilha("X", itens=["a", "b"])])
    assert ra.trilha_video(tl, "X") == 2 and tl.GetItemListInTrack("video", 2) == []
    with pytest.raises(ra.ResolveErro, match="destranque"):
        ra.trilha_video(TimelineFalsa([Trilha("X", trancada=True)]), "X")

def test_desligar_insiste_e_abre_pagina_edit(monkeypatch):
    monkeypatch.setattr(ra.time, "sleep", lambda s: None)
    tl = TimelineFalsa([Trilha("V")], teimosa=2); r = ResolveFalso()
    assert ra.desligar_trilha(r, tl, 1) is True and tl.GetIsTrackEnabled("video", 1) is False and r.paginas == ["edit"]
    assert ra.desligar_trilha(r, TimelineFalsa([Trilha("V")], teimosa=99), 1) is False

def test_cor_por_indice_cicla():
    assert ra.cor(0) == "Teal" and ra.cor(len(ra.CORES)) == "Teal" and ra.cor(3) == "Blue"
