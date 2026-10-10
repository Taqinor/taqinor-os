"""APDF2 (C-APDF-001) — LA règle de la ligne « Virement bancaire » des PDF
devis, une seule fonction et un seul littéral pour les deux moteurs (legacy
``generate_devis_premium`` et résidentiel v2 ``residential/trust``).

* RIB ou banque au profil société → SA ligne (bénéficiaire = raison sociale,
  sinon « Virement »), textes échappés ;
* société IDENTIFIÉE sans RIB ni banque → AUCUNE ligne (jamais le RIB d'un
  autre tenant) ;
* aucun profil du tout → la ligne historique TAQINOR (repli DC1
  byte-identique).

APDF3 (C-APDF-001, D-APDF-1) — LES mentions légales du vendeur (bande légale
des gabarits premium et ligne légale du legacy) : ``mentions_legales``, lue du
SEUL profil société quel que soit son nom ; les littéraux RC/ICE/capital/
gérant de TAQINOR ne vivent plus qu'ici, comme repli « aucun profil ».

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

#: APDF3 — tout champ dont la présence prouve qu'un PROFIL société existe ;
#: sans aucun, le document imprime le repli historique « aucun profil ».
CHAMPS_PROFIL = CHAMPS_IDENTITE + ("capital_social", "forme_juridique", "rib",
                                   "banque", "site_web")

#: APDF3 — repli « aucun profil » des gabarits premium (bande légale), suivi
#: du contact résolu par l'appelant. SEUL littéral légal TAQINOR premium.
LEGALE_TAQINOR_PREMIUM = (
    '<b>TAQINOR Solutions SARLAU</b> au capital de 100 000,00 MAD'
    ' &middot; RC 691213 — Tribunal de Commerce de Casablanca'
    ' &middot; ICE 003799642000067 &middot; G\u00e9rant\u00a0: M. Reda Kasri')
#: APDF3 — repli « aucun profil » de la ligne légale du moteur legacy.
LEGALE_TAQINOR_LEGACY = (
    "Taqinor Solutions SARLAU &middot; RC 691213 &middot; "
    "ICE 003799642000067 &middot; Capital 100&#8239;000 MAD "
    "&middot; Si\u00e8ge\u00a0: 5 Rue Ennoussour RDC, Casablanca")


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


def profil_renseigne(entreprise) -> bool:
    """APDF3 — un profil société existe-t-il (au moins un champ rempli) ?"""
    ent = entreprise if isinstance(entreprise, dict) else {}
    return any((ent.get(k) or "").strip() for k in CHAMPS_PROFIL)


def mentions_legales(entreprise, *, gras=_gras_defaut, fiscales=False):
    """APDF3 (D-APDF-1) — mentions légales du vendeur, lues du SEUL profil.

    ``None`` quand aucun profil n'existe (l'appelant imprime son repli
    historique) ; sinon la liste échappée, champs vides omis : raison sociale
    (``gras``, ``None`` = texte nu) suivie de la forme juridique et du
    capital, « RC … », « ICE … », puis « IF … » et « Patente … » quand
    ``fiscales``. Aucun gérant n'est imprimé (D-APDF-1)."""
    ent = entreprise if isinstance(entreprise, dict) else {}
    if not profil_renseigne(ent):
        return None

    def val(cle):
        return (ent.get(cle) or "").strip()

    tete = []
    if val("nom"):
        tete.append(gras(_e(val("nom"))) if gras else _e(val("nom")))
    if val("forme_juridique"):
        tete.append(_e(val("forme_juridique")))
    if val("capital_social"):
        tete.append("au capital de " + _e(val("capital_social")))
    out = [" ".join(tete)] if tete else []
    champs = [("RC", "rc"), ("ICE", "ice")]
    if fiscales:
        champs += [("IF", "identifiant_fiscal"), ("Patente", "patente")]
    out += [f"{libelle} {_e(val(cle))}" for libelle, cle in champs if val(cle)]
    return out
