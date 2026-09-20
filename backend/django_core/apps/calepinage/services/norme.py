"""CAL130 — QUELLE norme électrique s'applique, et ce qu'on omet sans elle.

LE CONSTAT
----------
``core/electrique`` cite des sources FRANÇAISES en dur : ampacité « IEC
60364-5-52 tableau B.52.4, reprise NF C 15-100 » (``cables.py``), chute DC
cible 1,5 % / maximum 3 % « UTE C 15-712-1 » (idem), parafoudre au-delà de
10 m et DDR 300 mA en régime TT (``protections.py``). Et le moteur le dit
lui-même : « aucun texte normatif marocain n'est présent dans ce dépôt »
(``docs/moteur-calepinage.md``).

LA RÈGLE D5 (fondateur)
-----------------------
Pour ``pays=ma``, AUCUNE norme n'est supposée. Tant que la société n'en a pas
choisi une, le calcul concerné est **OMIS** — avec sa mention — plutôt que
rendu sous une référence française imprimée sur un chantier casablancais. Le
jeu français ne s'applique que s'il est explicitement SÉLECTIONNÉ ; pour
``pays=fr``, c'est la sélection naturelle et elle vaut par défaut.

CE QUI EST PUBLIÉ AVEC CHAQUE VALEUR
-------------------------------------
Chaque coefficient porte sa RÉFÉRENCE TEXTE et sa SOURCE (``noyau`` quand il
vient du jeu français du moteur, ``societe`` quand la société l'a saisi). Un
coefficient sans référence est un coefficient que personne ne sait défendre
devant un bureau de contrôle.
"""
from __future__ import annotations

__all__ = [
    'NORME_FRANCAISE', 'PAYS_SANS_NORME_PAR_DEFAUT', 'COEFFICIENTS',
    'norme_applicable', 'coefficients_publies',
]

#: L'identifiant du jeu français — le SEUL que le dépôt sache citer.
NORME_FRANCAISE = 'nf_c_15_100'

#: Les pays pour lesquels AUCUNE norme n'est supposée à défaut de sélection.
#: Le Maroc y est par décision fondateur (règle D5) ; tout pays inconnu s'y
#: range aussi, par la même logique (on ne devine pas une juridiction).
PAYS_SANS_NORME_PAR_DEFAUT = ('ma',)

#: Les coefficients que le module publie, avec le NOM de la constante du
#: noyau qui les porte et la référence texte que le noyau cite déjà. Rien
#: n'est recopié en valeur ici : les valeurs sont LUES sur ``core.electrique``
#: au moment de la publication (une valeur recopiée serait une seconde vérité
#: le jour où le noyau change).
COEFFICIENTS = (
    ('chute_dc_cible_pct', 'CHUTE_CIBLE_DC_PCT',
     'UTE C 15-712-1 — chute de tension DC, cible'),
    ('chute_dc_max_pct', 'CHUTE_MAX_DC_PCT',
     'UTE C 15-712-1 — chute de tension DC, maximum'),
    ('chute_ac_cible_pct', 'CHUTE_CIBLE_AC_PCT',
     'UTE C 15-712-1 — chute de tension AC, cible'),
    ('chute_ac_max_pct', 'CHUTE_MAX_AC_PCT',
     'UTE C 15-712-1 — chute de tension AC, maximum ; NF C 15-100 §525 '
     'plafonne l\'installation entière à 3 %'),
    ('coeff_isc_dimensionnement', 'COEFF_ISC_DIMENSIONNEMENT',
     'IEC 62548 §7.3 — courant de dimensionnement des câbles DC'),
    ('section_min_dc_mm2', 'SECTION_MIN_DC_MM2',
     'décision fondateur 19/08/2026 — plancher commercial, jamais normatif'),
)


def _valeurs_du_noyau():
    """Les coefficients du jeu français, LUS sur le noyau (jamais recopiés)."""
    from core.electrique import cables

    valeurs = {}
    for cle, constante, reference in COEFFICIENTS:
        valeurs[cle] = {
            'valeur': getattr(cables, constante),
            'reference': reference,
            'source': 'noyau',
        }
    return valeurs


def coefficients_publies(section):
    """Les coefficients applicables : ceux du noyau, écrasés par les SAISIS.

    Une valeur saisie par la société l'emporte sur celle du noyau ET porte sa
    propre référence (``{valeur, reference}`` dans la section). Une valeur
    saisie SANS référence est refusée : un coefficient qu'on ne sait pas
    rattacher à un texte n'est pas publiable.
    """
    valeurs = _valeurs_du_noyau()
    saisis = (section or {}).get('coefficients')
    if not isinstance(saisis, dict):
        return (valeurs, ())
    refus = []
    for cle, brut in saisis.items():
        if cle not in valeurs:
            refus.append("coefficient inconnu « %s » — coefficients admis : "
                         "%s" % (cle, ', '.join(sorted(valeurs))))
            continue
        if not isinstance(brut, dict):
            refus.append("coefficient « %s » : attendu un objet "
                         "{valeur, reference}" % cle)
            continue
        reference = (brut.get('reference') or '').strip()
        if not reference:
            refus.append("coefficient « %s » sans référence de texte : un "
                         "coefficient qu'on ne sait pas rattacher à une règle "
                         "n'est pas publiable" % cle)
            continue
        try:
            valeur = float(brut.get('valeur'))
        except (TypeError, ValueError):
            refus.append("coefficient « %s » : valeur illisible" % cle)
            continue
        valeurs[cle] = {'valeur': valeur, 'reference': reference,
                        'source': 'societe'}
    return (valeurs, tuple(refus))


def norme_applicable(parametres=None):
    """La norme applicable pour CETTE société — ou l'omission, avec sa raison.

    Args:
        parametres: le dict rendu par ``selectors.parametres_de_societe`` (ou
            au minimum ``{'norme_electrique': …, 'imagerie': …}``).

    Returns:
        ``{applicable, norme, reference, pays, coefficients, motif,
        avertissements}``. ``applicable`` à ``False`` veut dire : les calculs
        qui dépendent d'une norme (sections de câble, chutes de tension,
        check-list de protections) sont OMIS et le disent — jamais rendus
        sous une référence que personne n'a choisie.
    """
    parametres = parametres or {}
    section = parametres.get('norme_electrique') or {}
    pays = ((parametres.get('imagerie') or {}).get('pays')
            or section.get('pays') or '').strip().lower()
    choisie = (section.get('norme') or '').strip().lower()

    if choisie:
        coefficients, refus = coefficients_publies(section)
        reference = (section.get('reference')
                     or ("NF C 15-100 / UTE C 15-712-1 / IEC 62548"
                         if choisie == NORME_FRANCAISE else ''))
        if not reference:
            return {
                'applicable': False, 'norme': choisie, 'reference': '',
                'pays': pays, 'coefficients': {},
                'motif': "norme « %s » sélectionnée sans référence de texte : "
                         "renseignez « Référence de la norme » pour que chaque "
                         "valeur publiée soit défendable." % choisie,
                'avertissements': tuple(refus),
            }
        return {
            'applicable': True, 'norme': choisie, 'reference': reference,
            'pays': pays, 'coefficients': coefficients,
            'motif': '', 'avertissements': tuple(refus),
        }

    if pays == 'fr':
        coefficients, refus = coefficients_publies(section)
        return {
            'applicable': True, 'norme': NORME_FRANCAISE,
            'reference': 'NF C 15-100 / UTE C 15-712-1 / IEC 62548',
            'pays': pays, 'coefficients': coefficients,
            'motif': "jeu français retenu par la juridiction du site "
                     "(pays = fr) — sélection naturelle, modifiable dans les "
                     "réglages",
            'avertissements': tuple(refus),
        }

    return {
        'applicable': False, 'norme': None, 'reference': '', 'pays': pays,
        'coefficients': {},
        'motif': "aucune norme électrique sélectionnée%s : les calculs qui en "
                 "dépendent (sections de câble, chutes de tension, check-list "
                 "de protections) sont OMIS. Aucun texte normatif marocain "
                 "n'est présent dans ce dépôt, et NF C 15-100 / UTE C 15-712-1 "
                 "ne sont pas imprimées sur un chantier qui ne les a pas "
                 "choisies — sélectionnez la norme applicable dans les "
                 "réglages du module."
                 % (" pour le pays « %s »" % pays if pays else ''),
        'avertissements': (),
    }
