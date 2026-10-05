"""AGR310 — renderer AGRICOLE de 3 pages (D-AGR-2) : P1 eau et argent, P2
comment ça marche, P3 équipement, prix, garanties — rendu SEUL (règle #4 :
aucun statut touché, aucun calcul).

Même contrat que les autres renderers du registre (``industriel``,
``commercial``, ``residential``) : ``is_agricole(devis, options)`` dit s'il
sert ce devis dans ce format, ``render_pdf_bytes(data)`` rend les octets ou
lève :class:`Unsupported` (le builder journalise alors un repli NOMMÉ vers le
moteur legacy). Toutes les valeurs viennent de ``synthese_agricole(data)``
(AGR304-AGR309) et de la chaîne de totaux canonique du builder.

``data`` est ``data_rendu`` (textes client échappés UNE fois, QJR30) : rien
n'est ré-échappé ici.

Interdits (ce7e9f01^, DV1) : ni ``economics.py``, ni ``economics_page.py``,
ni ``constants.py``, ni ``cover.py`` ne sont ressuscités.
"""
from __future__ import annotations

from pathlib import Path


class Unsupported(Exception):
    """Le devis ou les options sont hors du périmètre du renderer agricole."""


#: Formats servis : le document complet. Le une-page (``onepage``) reste au
#: moteur legacy (version courte, D-AGR-2).
FORMATS_SERVIS = ("full", "premium")


def is_agricole(devis, options=None) -> bool:
    """Vrai pour un devis AGRICOLE demandé au format complet. ``options``
    porte le ``pdf_mode`` NORMALISÉ par le builder (QJR32)."""
    mode = (getattr(devis, "mode_installation", None) or "").strip().lower()
    if mode != "agricole":
        return False
    return ((options or {}).get("pdf_mode") or "full") in FORMATS_SERVIS


def _augment(data: dict) -> dict:
    """La charge utile du gabarit : ``data`` + ``synthese`` (la MÊME fonction
    que /proposition, AGR308). Lève :class:`Unsupported` sans ligne chiffrée
    ou sans totaux canoniques — jamais un document à zéros."""
    from .synthese import synthese_agricole

    items = data.get("all_items") or []
    if not any((it or {}).get("quantite") for it in items
               if isinstance(it, dict)):
        raise Unsupported("devis agricole sans ligne chiffrée")
    totaux = data.get("totaux_all")
    if not isinstance(totaux, dict) or not totaux:
        raise Unsupported("devis agricole sans totaux canoniques (totaux_all)")
    d = dict(data)
    d["synthese"] = synthese_agricole(data)
    d.setdefault("valid_until", None)
    return d


#: Bande de pied fixe (mm), marge esthétique et garde de sécurité (mm) — les
#: valeurs du canon v6 (``residential.renderer._measure_page_slack``).
PIED_MM, MARGE_MM, GARDE_MM = 13.0, 6.0, 4.0
#: Vide maximal redistribué sur une page (mm) : au-delà, la page reste aérée
#: en bas plutôt que d'écarteler ses blocs.
VIDE_MAX_MM = 95.0


def mesurer_talon(pdf_bytes: bytes) -> dict:
    """Vide exploitable par page (mm), MESURÉ sur le PDF rendu (PyMuPDF) :
    distance entre le bas du contenu et la bande de pied, moins la marge et
    la garde. ``{}`` si PyMuPDF manque ou sur toute erreur (le premier rendu
    est alors servi tel quel)."""
    try:
        import fitz
    except Exception:  # noqa: BLE001
        return {}
    sortie = {}
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        for i, page in enumerate(doc):
            mm = page.rect.height / 297.0
            haut_pied = page.rect.height - PIED_MM * mm
            bas = 0.0
            for b in page.get_text("blocks"):
                if b[3] < haut_pied - 0.5 * mm:
                    bas = max(bas, b[3])
            for dessin in page.get_drawings():
                if dessin["rect"].y1 < haut_pied - 0.5 * mm:
                    bas = max(bas, dessin["rect"].y1)
            if bas <= 0:
                continue
            vide = (haut_pied - bas) / mm - MARGE_MM - GARDE_MM
            if vide >= 4.0:
                sortie[i + 1] = round(min(vide, VIDE_MAX_MM), 1)
        doc.close()
    except Exception:  # noqa: BLE001
        return {}
    return sortie


def render_pdf_bytes(data: dict) -> bytes:
    """Le document agricole de 3 pages en octets PDF, ou :class:`Unsupported`.

    Deux passages (QRES62, comme le canon v6) : le premier rend les pages et
    MESURE leur vide ; le second répartit ce vide sur les joints élastiques —
    jamais au prix d'une page de plus (sinon le premier rendu est servi)."""
    from weasyprint import HTML

    from . import pages
    d = _augment(data)
    base = str(Path(pages.__file__).resolve().parent)
    doc1 = HTML(string=pages.build_html(d),
                base_url=f"file://{base}/").render()
    pdf_bytes = doc1.write_pdf()
    vide = mesurer_talon(pdf_bytes)
    if vide:
        doc2 = HTML(string=pages.build_html(d, elastic=vide),
                    base_url=f"file://{base}/").render()
        if len(doc2.pages) == len(doc1.pages):
            pdf_bytes = doc2.write_pdf()
    return pdf_bytes
