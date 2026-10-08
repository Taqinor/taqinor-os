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


#: AMOT37 — libellé de la ligne de REGROUPEMENT déclaré (page 3) quand la
#: nomenclature ne tient pas en 3 pages. Textes en/ar à relire par le
#: fondateur.
LIBELLE_REGROUPEMENT = {
    "fr": "Autres équipements ({n} lignes) — détail sur la proposition en ligne",
    "en": "Other equipment ({n} lines) — details in the online proposal",
    "ar": "معدات أخرى ({n} بنود) — التفاصيل في العرض عبر الإنترنت",
}


def pages_attendues(d) -> int:
    """D-AGR-2 — 3 pages ; +1 SEULEMENT sur ``include_note_calcul``."""
    return 4 if d.get("include_note_calcul") else 3


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def regrouper_lignes(d, garde):
    """AMOT37 — ``d`` dont les lignes d'équipement au-delà des ``garde``
    premières sont regroupées en UNE ligne déclarée par taux de TVA
    (quantité 1, P.U. = Σ des totaux HT regroupés) : Σ des lignes imprimées
    = Total HT, chaîne de totaux inchangée (lue sur ``totaux_all``)."""
    from . import pages
    items = [it for it in (d.get("all_items") or [])
             if isinstance(it, dict) and _num(it.get("quantite")) > 0]
    if garde >= len(items):
        return d
    gardes, reste = items[:garde], items[garde:]
    langue = pages._langue(d)
    gabarit = LIBELLE_REGROUPEMENT.get(langue) or LIBELLE_REGROUPEMENT["fr"]
    par_taux = {}
    for it in reste:
        taux = _num(it.get("taux_tva"))
        total = round(_num(it.get("prix_unit_ht")) * _num(it.get("quantite")), 2)
        cumul = par_taux.setdefault(taux, [0, 0.0])
        cumul[0] += 1
        cumul[1] = round(cumul[1] + total, 2)
    regroupees = [{
        "designation": gabarit.format(n=n), "marque": "", "quantite": 1,
        "prix_unit_ht": total,
        "prix_unit_ttc": round(total * (1 + taux / 100), 2),
        "taux_tva": taux, "regroupement": True,
    } for taux, (n, total) in sorted(par_taux.items())]
    return dict(d, all_items=gardes + regroupees)


def _tient(doc, d):
    return len(doc.pages) == pages_attendues(d)


def _document_qui_tient(d, rendre):
    """AMOT37 (C-AMOT-046, volet agricole) — ``(d, doc)`` au premier rendu qui
    tient ses pages : tel quel, puis densité SUPÉRIEURE (jusqu'à serrée),
    puis regroupement DÉCLARÉ des dernières lignes (le plus de lignes
    possible, recherche dichotomique, densité serrée). Jamais une 4ᵉ page qui
    coupe le bloc d'acceptation : au-delà, :class:`Unsupported` NOMMÉ."""
    from . import pages
    doc = rendre(d)
    if _tient(doc, d):
        return d, doc
    for densite in range(pages.densite_compacte(d) + 1, 3):
        essai = dict(d, _densite_min=densite)
        doc = rendre(essai)
        if _tient(doc, essai):
            return essai, doc
    serre = dict(d, _densite_min=2)
    items = [it for it in (d.get("all_items") or [])
             if isinstance(it, dict) and _num(it.get("quantite")) > 0]
    bas, haut, retenu = 1, len(items) - 1, None
    while bas <= haut:
        garde = (bas + haut) // 2
        essai = regrouper_lignes(serre, garde)
        doc = rendre(essai)
        if _tient(doc, essai):
            retenu, bas = (essai, doc), garde + 1
        else:
            haut = garde - 1
    if retenu is not None:
        return retenu
    raise Unsupported("document agricole : 3 pages intenables même avec "
                      "regroupement des lignes")


def render_pdf_bytes(data: dict) -> bytes:
    """Le document agricole de 3 pages en octets PDF, ou :class:`Unsupported`.

    Deux passages (QRES62, comme le canon v6) : le premier rend les pages et
    MESURE leur vide ; le second répartit ce vide sur les joints élastiques —
    jamais au prix d'une page de plus (sinon le premier rendu est servi)."""
    from weasyprint import HTML

    from . import pages
    d = _augment(data)
    base = str(Path(pages.__file__).resolve().parent)

    def rendre(donnees):
        return HTML(string=pages.build_html(donnees),
                    base_url=f"file://{base}/").render()

    d, doc1 = _document_qui_tient(d, rendre)
    pdf_bytes = doc1.write_pdf()
    vide = mesurer_talon(pdf_bytes)
    if vide:
        doc2 = HTML(string=pages.build_html(d, elastic=vide),
                    base_url=f"file://{base}/").render()
        if len(doc2.pages) == len(doc1.pages):
            pdf_bytes = doc2.write_pdf()
    return pdf_bytes
