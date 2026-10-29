# flake8: noqa
# D-ENF22 : exception de fichier entier signée — moteur de devis vendoré (règle #4 de CLAUDE.md), non réécrit pour le lint.
"""Aperçu des éditions commerciales (outil d'étude, 29/10/2026).

``rendre(edition, data) -> bytes`` rend une édition sur une charge utile
brute (la même que ``commercial.renderer.render_pdf_bytes`` reçoit) ; la
charge est augmentée par ``commercial.renderer._augment`` — la même
fonction que le dispatch — puis assemblée par l'édition. ``tient`` dit si
le document a ses pages exactes sans texte sous le pied.

Usage (dans l'image prod, WeasyPrint) :
    python -m apps.ventes.quote_engine.commercial_editions.apercu /sortie
"""
from __future__ import annotations

import importlib
import sys

EDITIONS = ("khatam",)


def _edition(nom: str):
    return importlib.import_module(f"{__package__}.{nom}.render")


def html(edition: str, data: dict) -> str:
    from ..commercial.renderer import _augment
    from ..montants import poser_regles_origine
    poser_regles_origine((data or {}).get("regles_calcul_origine"),
                         avant_2710=(data or {}).get("regles_avant_2710"))
    return _edition(edition).build_html(_augment(data))


def document(edition: str, data: dict):
    """``(html, document WeasyPrint rendu, tient)`` — au PREMIER essai
    ``(variante, palier)`` de l'édition qui tient (pages exactes, rien sous
    le pied, socle libre), sinon le dernier, ``tient=False`` (le dispatch
    réel refuserait : CIQ317)."""
    from . import harnais
    module = _edition(edition)
    essais = getattr(module, "ESSAIS", [("A", 0), ("A", 1), ("A", 2), ("A", 3)])
    h = doc = None
    for variante, palier in essais:
        donnees = dict(data, _variante_ed=variante, _palier_ed=palier)
        h = html(edition, donnees)
        doc = harnais.rendre(h)
        if harnais.tient(h, doc):
            return h, doc, True
    return h, doc, False


def rendre(edition: str, data: dict) -> bytes:
    return document(edition, data)[1].write_pdf()


def fixture_complexe():
    """La fixture CIQ331 (boulangerie) poussée sur les choix que l'ERP
    offre : deux options (réseau seul / avec batterie), options proposées
    hors total, sections et note intercalées, note client, interlocuteur
    nommé — pour voir les éditions sur un devis riche. Chiffres : ceux des
    fixtures de test (``deux_options``), aucun nouveau calcul."""
    from apps.ventes.tests.test_ciq331_pdf_commercial_complet import (
        _data, deux_options)
    data = deux_options(_data("boulangerie"))
    items = data["all_items"]
    for i, it in enumerate(items):
        it["ordre"] = (i + 1) * 10
    data["lignes_structure"] = [
        {"type": "section", "texte": "Champ solaire", "ordre": 5},
        {"type": "section", "texte": "Conversion et protection", "ordre": 15},
        {"type": "note", "texte": "Onduleur dimensionné pour l'extension "
                                  "future du fournil.", "ordre": 16},
        {"type": "section", "texte": "Pose et mise en service", "ordre": 25},
    ]
    data["options_proposees"] = [
        {"designation": "Supervision à distance (box 4G + portail)",
         "quantite": 1, "taux_tva": 20, "total_ht": 4500.0, "total_ttc": 5400.0},
        {"designation": "Extension de garantie onduleur, +5 ans",
         "quantite": 1, "taux_tva": 20, "total_ht": 8000.0, "total_ttc": 9600.0},
    ]
    data["note_client"] = ("Accès toiture par l'escalier de service ; "
                           "intervention en dehors des heures de fournée.")
    data["seller"] = {"nom": "Yassine Cherkaoui", "telephone": "0612345678",
                      "email": "y.cherkaoui@taqinor.ma"}
    return data


def main(dossier: str, editions=EDITIONS, categories=("hotel", "boulangerie", "cafe"),
         langues=("fr",)):
    """Rend chaque édition × catégorie × langue sur la fixture complète
    CIQ331 (étude C&I + économies + jalons) et sur la fixture dégradée."""
    import os
    from apps.ventes.tests.test_ciq331_pdf_commercial_complet import _data
    from ..commercial import sample_data
    os.makedirs(dossier, exist_ok=True)
    for edition in editions:
        for cat in categories:
            for langue in langues:
                data = _data(cat)
                if langue != "fr":
                    data["langue_sortie"] = langue
                h, doc, ok = document(edition, data)
                chemin = os.path.join(dossier, f"{edition}_{cat}_{langue}.pdf")
                doc.write_pdf(chemin)
                print(f"{'OK ' if ok else 'DEBORDE'} {edition} {cat} {langue} "
                      f"pages={len(doc.pages)}")
        h, doc, ok = document(edition, sample_data.build("restaurant"))
        doc.write_pdf(os.path.join(dossier, f"{edition}_degrade_fr.pdf"))
        print(f"{'OK ' if ok else 'DEBORDE'} {edition} degrade pages={len(doc.pages)}")
        h, doc, ok = document(edition, fixture_complexe())
        doc.write_pdf(os.path.join(dossier, f"{edition}_complexe_fr.pdf"))
        print(f"{'OK ' if ok else 'DEBORDE'} {edition} complexe pages={len(doc.pages)}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "/tmp/apercu")
