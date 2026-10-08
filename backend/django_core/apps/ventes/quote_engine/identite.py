"""APDF2 (C-APDF-001) — LA règle de la ligne « Virement bancaire » des PDF
devis, une seule fonction et un seul littéral pour les deux moteurs (legacy
``generate_devis_premium`` et résidentiel v2 ``residential/trust``).

* RIB ou banque au profil société → SA ligne (bénéficiaire = raison sociale,
  sinon « Virement »), textes échappés ;
* société IDENTIFIÉE sans RIB ni banque → AUCUNE ligne (jamais le RIB d'un
  autre tenant) ;
* aucun profil du tout → la ligne historique TAQINOR (repli DC1
  byte-identique).

Rendu seul : aucun accès base, aucun statut (règle #4).
"""
from html import escape as _e

#: Les champs qui font qu'une société est IDENTIFIÉE (hors RIB/banque).
CHAMPS_IDENTITE = ("nom", "adresse", "email", "telephone", "ice", "rc",
                   "identifiant_fiscal", "patente")

#: Le SEUL littéral du RIB historique Taqinor (bénéficiaire, puis la suite).
RIB_TAQINOR_BENEFICIAIRE = "TAQINOR SOLUTION"
RIB_TAQINOR_SUITE = ("Saham Bank · RIB 022\u2009780\u20090002720029379418\u200974 "
                     "· BIC SGMBMAMCXXX")


def _gras_defaut(texte):
    return f"<b>{texte}</b>"


def ligne_rib(entreprise, *, gras=_gras_defaut) -> str:
    """La ligne de virement à imprimer, ou ``""`` quand il n'y en a pas.

    ``gras`` met en forme le bénéficiaire (chaque moteur garde sa balise)."""
    ent = entreprise if isinstance(entreprise, dict) else {}
    nom = (ent.get("nom") or "").strip()
    rib = (ent.get("rib") or "").strip()
    banque = (ent.get("banque") or "").strip()
    if rib or banque:
        bits = [gras(_e(nom) if nom else "Virement")]
        if banque:
            bits.append(_e(banque))
        if rib:
            bits.append("RIB " + _e(rib))
        return " · ".join(bits)
    identifiee = any((ent.get(k) or "").strip() for k in CHAMPS_IDENTITE)
    if identifiee:
        return ""
    return gras(RIB_TAQINOR_BENEFICIAIRE) + " · " + RIB_TAQINOR_SUITE
