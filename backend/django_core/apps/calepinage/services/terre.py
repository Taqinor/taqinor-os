"""CAL134 — la check-list de MISE À LA TERRE, et la justification qui manquait.

LE DÉFAUT CORRIGÉ
-----------------
``core/electrique/protections.py`` traite déjà la prise de terre comme un
service EN SUS (décision fondateur 19/08/2026 : le client est réputé équipé,
la fournir sans le dire la facturerait en silence) et exige, à défaut, une
JUSTIFICATION de continuité (NF C 15-100 §542). Mais RIEN ne collecte cette
justification : elle n'existe nulle part en base. Un dossier sans prise de
terre vendue se lit donc aujourd'hui comme un dossier sans terre du tout.

CE QUE CE SERVICE AJOUTE
------------------------
Une check-list à quatre lignes, chacune citant SA référence :

* liaison équipotentielle des masses (toujours) ;
* section du conducteur de terre ;
* piquet + barrette de coupure (fournis, ou justifiés comme déjà en place) ;
* mesure de continuité / résistance de terre.

Deux règles dures :

1. **Aucune valeur de résistance inventée.** La résistance est MESURÉE et
   saisie, ou elle vaut ``null`` avec sa mention. Un « ≤ 100 Ω » imprimé sans
   mesure serait un procès-verbal falsifié.
2. **Sans prise de terre vendue, la justification cochée est EXIGÉE avant
   publication.** C'est la moitié manquante de la décision du 19/08/2026 :
   le service en sus ne se retire du bordereau qu'à condition d'avoir vérifié
   la terre existante.

La pièce jointe (procès-verbal de mesure) est OPTIONNELLE et passe par la GED
existante — lecture par ``apps.ged.selectors``, bornée société, jamais un
import des modèles de la GED.
"""
from __future__ import annotations

import datetime

__all__ = [
    'TerreInvalide', 'checklist_terre', 'garde_terre', 'LIGNES_MESUREES',
]

#: Les références citées par chaque ligne (celles que le noyau cite déjà).
REFERENCE_EQUIPOTENTIELLE = ('UTE C 15-712-1 / NF C 15-100 §542.4 — toutes '
                             'les masses métalliques du champ sont reliées à '
                             'la même barrette de terre')
REFERENCE_PRISE = ('NF C 15-100 §542 — valeur de prise de terre compatible '
                   'avec le différentiel du régime TT')

# ═══════════════════════════════════════════════════════════════════════════
# CALX245 — LA CONTINUITÉ MESURÉE DE L'EXISTANT
# ═══════════════════════════════════════════════════════════════════════════
#
# La check-list de CAL134 se contentait d'UNE résistance en ohms. Or une
# résistance de prise ne dit rien de la CONTINUITÉ des liaisons : un champ
# peut afficher 12 Ω à la barrette pendant que la structure n'y est reliée
# par rien. Et une mesure sans POINT ni DATE n'est pas une mesure — c'est un
# souvenir : un procès-verbal de mise en service en exige les trois.
#
# Trois lignes SAISIES de plus, chacune citant la référence que le noyau
# cite DÉJÀ (``core/electrique/protections.py`` : NF C 15-100 §542 pour la
# prise, §542.4 pour l'équipotentialité). AUCUNE valeur cible n'est ajoutée
# ici : ce module publie ce qui a été mesuré, il ne juge pas le chiffre —
# les seuils restent ceux que le noyau cite. Et aucune valeur n'est jamais
# inventée : sans saisie, la ligne dit « non mesurée ».
#
# UNE MESURE SANS SA DATE EST REFUSÉE EN NOMMANT LE CHAMP. C'est la règle
# fondateur « erreur → champ fautif » : l'écran doit pointer la date à
# saisir, pas afficher un « non enregistré » générique.

#: ``(code, libellé, champ de valeur, champ de date, unité, référence)``.
#: ``unite`` à ``None`` = la valeur est un TEXTE (le point de mesure).
LIGNES_MESUREES = (
    ('point_date_mesure_prise',
     'Point et date de mesure de la prise de terre',
     'point_mesure_prise', 'date_mesure_prise', None, REFERENCE_PRISE),
    ('continuite_structure_barrette',
     'Continuité mesurée structure ↔ barrette de terre',
     'continuite_structure_barrette_ohm',
     'date_continuite_structure_barrette', 'Ω', REFERENCE_EQUIPOTENTIELLE),
    ('continuite_barrette_coffrets',
     'Continuité mesurée barrette ↔ masses des coffrets',
     'continuite_barrette_coffrets_ohm', 'date_continuite_barrette_coffrets',
     'Ω', REFERENCE_EQUIPOTENTIELLE),
)


class TerreInvalide(ValueError):
    """Refus métier sur la check-list de terre — champ fautif NOMMÉ."""

    def __init__(self, message, *, champ=''):
        super().__init__(message)
        self.champ = champ


def _nombre(valeur):
    if valeur is None or isinstance(valeur, bool):
        return None
    try:
        return float(valeur)
    except (TypeError, ValueError):
        return None


def _piece_jointe(decisions, company):
    """La pièce jointe GED, VÉRIFIÉE et bornée société, ou ``None``.

    Lecture cross-app par ``apps.ged.selectors`` uniquement. Un identifiant
    qui ne correspond à aucun document de la société est REFUSÉ : une pièce
    jointe fantôme ferait croire à un procès-verbal qui n'existe pas.
    """
    identifiant = (decisions or {}).get('document_id')
    if identifiant in (None, ''):
        return None
    try:
        identifiant = int(identifiant)
    except (TypeError, ValueError):
        raise TerreInvalide(
            "Pièce jointe : identifiant de document illisible.",
            champ='terre.document_id')
    if company is None:
        # Hors base (calcul à chaud, test) : on conserve la référence telle
        # quelle sans prétendre l'avoir vérifiée.
        return {'document_id': identifiant, 'verifie': False}
    from apps.ged.selectors import documents_for_company

    if not documents_for_company(company).filter(pk=identifiant).exists():
        raise TerreInvalide(
            "Pièce jointe introuvable dans la GED de la société "
            "(document %d)." % identifiant, champ='terre.document_id')
    return {'document_id': identifiant, 'verifie': True}


def _date_saisie(brut, champ):
    """La date ISO d'une mesure, ou ``None`` — illisible = REFUS nommé.

    Une date de mesure se saisit ``AAAA-MM-JJ`` ; un texte libre en ferait
    une date qu'aucun procès-verbal ne peut opposer.
    """
    if brut in (None, ''):
        return None
    if isinstance(brut, datetime.date):
        return brut.isoformat()
    try:
        return datetime.date.fromisoformat(str(brut).strip()).isoformat()
    except (TypeError, ValueError):
        raise TerreInvalide(
            "Date de mesure illisible : saisissez-la au format AAAA-MM-JJ.",
            champ='terre.%s' % champ)


def _valeur_mesuree(brut, unite, champ):
    """La valeur mesurée d'une ligne — nombre en ohms, ou texte libre."""
    if brut is None or (isinstance(brut, str) and not brut.strip()):
        return None
    if unite is None:
        return str(brut).strip()
    nombre = _nombre(brut)
    if nombre is None:
        raise TerreInvalide(
            "Continuité mesurée illisible : saisissez la valeur MESURÉE en "
            "ohms, ou laissez le champ vide.", champ='terre.%s' % champ)
    return nombre


def _lignes_mesurees(decisions):
    """CALX245 — ``(lignes, mesures)`` des trois mesures de l'EXISTANT.

    Chaque ligne est TOUJOURS publiée : présente et non faite quand rien
    n'est saisi (un écran qui reçoit parfois sept lignes et parfois quatre
    finit par tester l'absence de ligne au lieu de l'absence de mesure).

    Raises:
        TerreInvalide: valeur illisible, date illisible, ou mesure saisie
            SANS sa date — le champ fautif est NOMMÉ dans les trois cas.
    """
    lignes = []
    mesures = {}
    for code, libelle, champ_valeur, champ_date, unite, reference in \
            LIGNES_MESUREES:
        valeur = _valeur_mesuree(decisions.get(champ_valeur), unite,
                                 champ_valeur)
        date = _date_saisie(decisions.get(champ_date), champ_date)
        if valeur is not None and date is None:
            raise TerreInvalide(
                "« %s » est saisi sans sa date de mesure : une mesure sans "
                "date n'est opposable à personne. Saisissez « %s » "
                "(AAAA-MM-JJ)." % (libelle, champ_date),
                champ='terre.%s' % champ_date)
        if valeur is None:
            # AUCUNE valeur inventée : la case reste vide et le DIT.
            affichee = 'non mesurée — aucune valeur supposée'
        elif unite is None:
            affichee = '%s, mesuré le %s' % (valeur, date)
        else:
            affichee = '%s %s mesurés le %s' % (
                ('%.2f' % valeur).replace('.', ','), unite, date)
        lignes.append({'code': code, 'libelle': libelle,
                       'fait': valeur is not None, 'valeur': affichee,
                       'reference': reference})
        mesures[code] = {'valeur': valeur, 'date': date}
    return (lignes, mesures)


def _section_de_terre(conception):
    """La section du conducteur de terre, LUE sur l'organe du noyau.

    Le calibre (« 6 mm² Cu minimum ») est celui que ``core.electrique``
    publie sur la liaison équipotentielle : le recopier ici en ferait une
    seconde vérité.
    """
    from core.electrique.protections import concevoir_protections

    from .chaines import evaluer_onduleurs

    resultat = concevoir_protections(conception.entree, conception.resultat,
                                     evaluer_onduleurs(conception))
    for protection in resultat.protections:
        if protection.repere == 'T2':
            return (protection.calibre, protection.regle_source)
    return ('', REFERENCE_EQUIPOTENTIELLE)


def checklist_terre(conception, *, decisions=None, norme=None, company=None):
    """CAL134 — la check-list de terre, chaque ligne citant sa référence.

    Returns:
        ``{lignes, justification_requise, justification_fournie, mesure,
        mesures_saisies, piece_jointe, omissions}``.

    Raises:
        TerreInvalide: pièce jointe illisible ou introuvable, mesure
            illisible, ou (CALX245) mesure saisie sans sa date.
    """
    decisions = decisions if isinstance(decisions, dict) else {}
    if norme is not None and not norme.get('applicable', False):
        return {'lignes': [], 'justification_requise': False,
                'justification_fournie': False, 'mesure': None,
                'mesures_saisies': {}, 'piece_jointe': None,
                'omissions': [norme.get('motif') or
                              "aucune norme électrique sélectionnée : "
                              "check-list de terre OMISE"]}
    if conception.fiche_incomplete or conception.resultat is None \
            or not conception.chaines:
        return {'lignes': [], 'justification_requise': False,
                'justification_fournie': False, 'mesure': None,
                'mesures_saisies': {}, 'piece_jointe': None,
                'omissions': ["aucune chaîne calculée : la check-list de "
                              "terre n'a pas d'objet"]}

    prise_vendue = bool(getattr(conception.entree, 'inclure_prise_terre',
                                False))
    justification = bool(decisions.get('justification_continuite'))
    mesure = _nombre(decisions.get('resistance_ohm'))
    if decisions.get('resistance_ohm') not in (None, '') and mesure is None:
        raise TerreInvalide(
            "Résistance de terre illisible : saisissez la valeur MESURÉE en "
            "ohms, ou laissez le champ vide.", champ='terre.resistance_ohm')
    piece = _piece_jointe(decisions, company)
    calibre, regle_equipotentielle = _section_de_terre(conception)

    lignes = [
        {'code': 'liaison_equipotentielle',
         'libelle': 'Liaison équipotentielle des masses (structure, cadres '
                    'modules, coffrets)',
         'fait': bool(decisions.get('liaison_equipotentielle', True)),
         'valeur': None,
         'reference': regle_equipotentielle},
        {'code': 'section_conducteur',
         'libelle': 'Section du conducteur de terre',
         'fait': bool(calibre),
         'valeur': calibre or None,
         'reference': regle_equipotentielle},
        {'code': 'piquet_barrette',
         'libelle': 'Piquet de terre + barrette de coupure',
         'fait': prise_vendue,
         'valeur': ('fournis au marché (service en sus)' if prise_vendue
                    else 'non fournis — terre existante réputée en place'),
         'reference': REFERENCE_PRISE},
        {'code': 'mesure_continuite',
         'libelle': 'Mesure de continuité / résistance de la prise de terre',
         'fait': mesure is not None,
         # AUCUNE valeur inventée : sans mesure, la case reste vide et le
         # dit. Un « ≤ 100 Ω » non mesuré serait un procès-verbal falsifié.
         'valeur': (('%s Ω mesurés' % ('%.1f' % mesure).replace('.', ','))
                    if mesure is not None
                    else 'non mesurée — aucune valeur supposée'),
         'reference': REFERENCE_PRISE},
    ]
    # CALX245 — la continuité MESURÉE de l'existant, en fin de check-list :
    # les quatre lignes historiques gardent leur ordre et leur rang.
    lignes_mesurees, mesures_saisies = _lignes_mesurees(decisions)
    lignes.extend(lignes_mesurees)

    return {
        'lignes': lignes,
        # Sans prise de terre vendue, la continuité de la terre EXISTANTE doit
        # être justifiée avant publication (la moitié manquante de la décision
        # fondateur du 19/08/2026).
        'justification_requise': not prise_vendue,
        'justification_fournie': justification,
        'mesure': mesure,
        # CALX245 — les trois mesures de l'existant, telles que SAISIES
        # (valeur + date), jamais une valeur reconstruite.
        'mesures_saisies': mesures_saisies,
        'piece_jointe': piece,
        'omissions': [],
    }


def garde_terre(checklist):
    """Refuse la publication tant que la justification exigée manque.

    Ne lève pas quand la check-list est OMISE (sans norme applicable, il n'y
    a rien à exiger) ni quand la prise de terre est vendue.
    """
    checklist = checklist or {}
    if not checklist.get('lignes'):
        return True
    if checklist.get('justification_requise') and not checklist.get(
            'justification_fournie'):
        raise TerreInvalide(
            "Prise de terre non fournie au marché : cochez la justification "
            "de continuité de la terre EXISTANTE (NF C 15-100 §542) avant de "
            "publier le calepinage — une pièce jointe (procès-verbal de "
            "mesure) peut y être rattachée depuis la GED.",
            champ='terre.justification_continuite')
    return True
