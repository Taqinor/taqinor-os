"""CAL145 — comparer les variantes sur la PRODUCTION, à la LECTURE.

LE CONSTAT
----------
``CalepinageVariante`` (CAL9) compare des COMPTAGES de modules, et
``compare_scenarios`` (``apps/ventes/solar_design.py``) compare des scénarios
de DEVIS : aucun des deux ne confronte deux plans de pose sur leur production
simulée. Le contrat committé ``contract_samples/variantes_comparer.json``
porte pourtant déjà les colonnes de production (PACT10 : elles ont été
écrites AVANT, pour que le comparatif ne dérive pas du contrat le jour où
elles arrivent) — elles restaient vides parce que rien ne savait les remplir.

LES TROIS DISCIPLINES TENUES ICI
--------------------------------
1. **Calculé À LA LECTURE, jamais stocké.** Ce module ne persiste RIEN et ne
   lance AUCUNE simulation : il LIT le résultat déposé par le moteur sur
   chaque variante et en extrait les colonnes. Même discipline que
   ``core/calepinage/etude.py`` — un comparatif figé en base serait faux le
   lendemain sans que personne ne le sache.
2. **L'empreinte d'entrée fait foi.** Si le résultat porte l'empreinte du
   layout qui l'a produit et qu'elle DIFFÈRE de celle de la variante
   d'aujourd'hui, la production est PÉRIMÉE : la variante est publiée « non
   simulée », avec son motif. Le comparatif suit donc l'empreinte sans qu'on
   ait besoin d'invalider quoi que ce soit à l'écriture.
3. **Non simulée ⇒ ``None`` partout, jamais ``0``.** Un zéro se lirait « zéro
   kWh » là où personne n'a lancé de simulation.

DEUX FORMES DE RÉSULTAT SONT LUES, ET C'EST VOULU
--------------------------------------------------
Le moteur de production du module (CAL138/CAL142) écrit un bloc IMBRIQUÉ
(``production.total.p50_kwh``) ; les résultats venus du parcours devis sont
PLATS (``production.p50_kwh``, forme d'``apps/ventes/etude._pr_block``). Les
deux sont acceptées et rendues dans la MÊME forme plate, celle du contrat :
le comparatif n'a pas à savoir quel chemin a produit le chiffre.

Module PUR : aucune base, aucun réseau, aucun prix.
"""
from __future__ import annotations

__all__ = ['CLES_PRODUCTION', 'MOTIF_NON_SIMULEE', 'MOTIF_PERIMEE',
           'NOMBRE_PERTES_DOMINANTES', 'colonnes_production']

#: Les colonnes de production du contrat ``variantes_comparer.json`` —
#: ``pertes_dominantes`` est traitée à part (c'est une liste, jamais ``None``).
CLES_PRODUCTION = ('p50_kwh', 'p75_kwh', 'p90_kwh', 'performance_ratio',
                   'specific_yield_kwh_kwc', 'self_consumption_rate')

#: Combien de postes de perte on met en avant. Trois : de quoi nommer ce qui
#: sépare deux variantes sans transformer une colonne en tableau.
NOMBRE_PERTES_DOMINANTES = 3

MOTIF_NON_SIMULEE = (
    "Cette variante n'a pas été simulée : aucune production n'est publiée "
    '(les colonnes restent vides, jamais à 0).')
MOTIF_PERIMEE = (
    'La conception a changé depuis la dernière simulation de cette variante : '
    'la production affichée serait celle d’un autre toit. Elle est donc '
    'traitée comme non simulée — relancez la simulation.')


def _dict(valeur):
    return valeur if isinstance(valeur, dict) else {}


def _nombre(valeur):
    if valeur is None or isinstance(valeur, bool):
        return None
    try:
        nombre = float(valeur)
    except (TypeError, ValueError):
        return None
    if nombre != nombre:
        return None
    return nombre


def _empreinte_du_resultat(resultat):
    """L'empreinte du layout AYANT PRODUIT ce résultat, si elle est dite."""
    for cle in ('layout_hash', 'empreinte_layout'):
        valeur = resultat.get(cle)
        if isinstance(valeur, str) and valeur:
            return valeur
    production = _dict(resultat.get('production'))
    valeur = _dict(production.get('base')).get('layout_hash')
    return valeur if isinstance(valeur, str) and valeur else None


def _pertes_dominantes(resultat):
    """Les postes de perte les plus lourds, chacun AVEC SA SOURCE.

    Les pertes du module sont une LISTE de postes sourcés (CAL139) ; celles du
    parcours devis arrivent en ``loss_breakdown`` ``{poste: {pct}}`` sans
    source — dans ce cas la source est ``None`` (non sourcée), jamais
    inventée.
    """
    postes = resultat.get('pertes')
    lignes = []
    if isinstance(postes, list):
        for poste in postes:
            if not isinstance(poste, dict):
                continue
            pct = _nombre(poste.get('pct'))
            if pct is None:
                continue
            lignes.append({'poste': str(poste.get('poste') or ''),
                           'pct': pct, 'source': poste.get('source')})
    else:
        production = _dict(resultat.get('production'))
        detail = _dict(production.get('loss_breakdown')) \
            or _dict(_dict(production.get('total')).get('loss_breakdown'))
        for nom, valeur in detail.items():
            pct = _nombre(_dict(valeur).get('pct') if isinstance(valeur, dict)
                          else valeur)
            if pct is None:
                continue
            lignes.append({'poste': str(nom), 'pct': pct, 'source': None})
    lignes.sort(key=lambda ligne: (-ligne['pct'], ligne['poste']))
    return lignes[:NOMBRE_PERTES_DOMINANTES]


def colonnes_production(resultat, *, layout_hash=None):
    """Les colonnes de production d'UNE variante, à la forme du contrat.

    Args:
        resultat: le ``resultat`` DÉPOSÉ sur la variante par le moteur.
        layout_hash: l'empreinte du layout ACTUEL de la variante. Quand le
            résultat porte lui aussi son empreinte et qu'elles diffèrent, la
            production est déclarée PÉRIMÉE (donc non simulée).

    Returns:
        ``(simulee, production, motif)`` — ``production`` porte TOUJOURS les
        mêmes clés ; non simulée ⇒ toutes à ``None`` et
        ``pertes_dominantes: []``.
    """
    resultat = _dict(resultat)
    production = _dict(resultat.get('production'))
    vide = ({cle: None for cle in CLES_PRODUCTION}
            | {'pertes_dominantes': []})

    if not production:
        return False, vide, MOTIF_NON_SIMULEE

    empreinte = _empreinte_du_resultat(resultat)
    if layout_hash and empreinte and empreinte != layout_hash:
        return False, vide, MOTIF_PERIMEE

    # Forme imbriquée du module (CAL138/CAL142) ou forme plate du parcours
    # devis : on lit la première qui porte la clé, sans jamais additionner
    # les deux.
    total = _dict(production.get('total'))
    autoconso = (_dict(resultat.get('autoconsommation'))
                 | _dict(production.get('self_consumption')))

    def _lire(cle):
        for source in (total, production, autoconso):
            if cle in source:
                valeur = _nombre(source.get(cle))
                if valeur is not None:
                    return valeur
        return None

    colonnes = {cle: _lire(cle) for cle in CLES_PRODUCTION}
    if all(valeur is None for valeur in colonnes.values()):
        # Un bloc ``production`` présent mais entièrement vide n'est pas une
        # simulation : le dire vaut mieux que publier six ``null`` sous un
        # « simulée ».
        return False, vide, MOTIF_NON_SIMULEE

    colonnes['pertes_dominantes'] = _pertes_dominantes(resultat)
    return True, colonnes, ''
