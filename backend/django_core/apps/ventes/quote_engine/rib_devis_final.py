"""T4-U1-009 / T4-X7-020 — le RIB du « Devis final » sous l'échéancier des
documents commercial, industriel et agricole (nouveaux rendus seulement).

Le Premium résidentiel imprime déjà la ligne de virement de son « Devis
final » (``residential/trust._bloc_paiement``, règle unique
``identite.ligne_rib``). Les documents commercial / industriel
(``ci.blocs.bloc_echeancier``) et agricole (``agricole.pages._echeancier``)
imprimaient leur échéancier sans jamais le RIB de la société, même renseigné.

Règle : document COMPLET (jamais le une-page, qui n'a pas d'échéancier),
« Devis final » (option de rendu ou case enregistrée), RIB ou banque au
profil de la société imprimé (identité figée à l'envoi pour un devis envoyé,
ASOC96) — jamais le RIB historique d'un autre tenant, jamais une mention
« RIB à communiquer ». Sans RIB au profil : rien n'est imprimé.

Nouveaux rendus seulement : la clé de rendu :data:`CLE` n'est posée que pour
un devis ouvert aux corrections du PDF du 26/11/2026
(``regles_calcul.phrases_pdf_2611_ouvertes``, même coupure datée) ; un devis
envoyé avant garde une charge utile SANS la clé (absente, jamais ``False``)
et un document octet pour octet identique. Rendu seul (règle #4).
"""

#: Clé de rendu posée par le builder (cas OUVERT seulement).
CLE = "rib_sous_echeancier"
#: Marchés dont le document imprime un échéancier sans ligne de virement.
MARCHES = ("commercial", "industriel", "agricole")


def _rib_au_profil(entreprise) -> bool:
    ent = entreprise if isinstance(entreprise, dict) else {}
    return any(str(ent.get(k) or "").strip() for k in ("rib", "banque"))


def drapeau_rib(devis, data) -> dict:
    """``{CLE: True}`` quand le document de ce devis imprime le RIB sous son
    échéancier, ``{}`` sinon (la charge utile ne bouge pas)."""
    from apps.ventes.domain.regles_calcul import phrases_pdf_2611_ouvertes
    marche = (getattr(devis, "mode_installation", None) or "").strip().lower()
    if (marche in MARCHES and data.get("devis_final")
            and data.get("pdf_mode") != "onepage"
            and _rib_au_profil(data.get("entreprise"))
            and phrases_pdf_2611_ouvertes(devis)):
        return {CLE: True}
    return {}


def drapeaux_rendu(devis, data) -> dict:
    """Les drapeaux « nouveaux rendus » du builder
    (``regles_calcul.drapeaux_nouveaux_rendus``) et celui du RIB."""
    from apps.ventes.domain.regles_calcul import drapeaux_nouveaux_rendus
    return {**drapeaux_nouveaux_rendus(devis), **drapeau_rib(devis, data)}


def ligne_rib(d) -> str:
    """La ligne de virement à imprimer sous l'échéancier, ou ``""`` : clé
    :data:`CLE` absente, ou profil sans RIB ni banque."""
    d = d if isinstance(d, dict) else {}
    if not d.get(CLE) or not _rib_au_profil(d.get("entreprise")):
        return ""
    from .identite import ligne_rib as _ligne
    return _ligne(d.get("entreprise"))


def bloc_ci(d, prefixe, couleur_titre) -> str:
    """Le ``<div>`` de virement du bloc échéancier C&I, ou ``""``."""
    rib = ligne_rib(d)
    if not rib:
        return ""
    from .ci.blocs import libelle
    return (f'<div class="{prefixe}-ech-rib" style="margin-top:4px;'
            f'font-size:7.2pt;">{libelle(d, "res_virement", "Virement bancaire&nbsp;:")}'
            f' <span style="color:{couleur_titre};">{rib}</span></div>')


def bloc_agricole(d, libelle_virement) -> str:
    """Le ``<div>`` de virement sous l'échéancier agricole, ou ``""``."""
    rib = ligne_rib(d)
    if not rib:
        return ""
    return (f'<div class="ag-sig-h ag-ech-rib" style="margin:-2px 0 3px;">'
            f'{libelle_virement} {rib}</div>')
