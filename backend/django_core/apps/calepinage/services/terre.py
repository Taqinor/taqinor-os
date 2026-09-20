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

La pièce jointe (procès-verbal de mesure) est OPTIONNELLE et désigne une pièce
jointe ``records`` du module (SOLMVP15 — elle désignait un document du
référentiel documentaire, qui sort du produit ; ``records`` est le référentiel
où vivent déjà les photos de site et les fichiers de gabarit). La vérification
reste bornée SOCIÉTÉ : un identifiant qui ne correspond à aucune pièce de la
société est REFUSÉ, jamais accepté « au cas où ».
"""
from __future__ import annotations

__all__ = [
    'TerreInvalide', 'checklist_terre', 'garde_terre',
]

#: Les références citées par chaque ligne (celles que le noyau cite déjà).
REFERENCE_EQUIPOTENTIELLE = ('UTE C 15-712-1 / NF C 15-100 §542.4 — toutes '
                             'les masses métalliques du champ sont reliées à '
                             'la même barrette de terre')
REFERENCE_PRISE = ('NF C 15-100 §542 — valeur de prise de terre compatible '
                   'avec le différentiel du régime TT')


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
    """La pièce jointe, VÉRIFIÉE et bornée société, ou ``None``.

    C'est une pièce jointe ``records`` (SOLMVP15). Un identifiant qui ne
    correspond à aucune pièce de la société est REFUSÉ : une pièce jointe
    fantôme ferait croire à un procès-verbal qui n'existe pas.
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
    from apps.records.models import Attachment

    if not Attachment.objects.filter(company=company,
                                     pk=identifiant).exists():
        raise TerreInvalide(
            "Pièce jointe introuvable dans les documents de la société "
            "(document %d)." % identifiant, champ='terre.document_id')
    return {'document_id': identifiant, 'verifie': True}


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
        piece_jointe, omissions}``.

    Raises:
        TerreInvalide: pièce jointe illisible ou introuvable, mesure
            illisible.
    """
    decisions = decisions if isinstance(decisions, dict) else {}
    if norme is not None and not norme.get('applicable', False):
        return {'lignes': [], 'justification_requise': False,
                'justification_fournie': False, 'mesure': None,
                'piece_jointe': None,
                'omissions': [norme.get('motif') or
                              "aucune norme électrique sélectionnée : "
                              "check-list de terre OMISE"]}
    if conception.fiche_incomplete or conception.resultat is None \
            or not conception.chaines:
        return {'lignes': [], 'justification_requise': False,
                'justification_fournie': False, 'mesure': None,
                'piece_jointe': None,
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

    return {
        'lignes': lignes,
        # Sans prise de terre vendue, la continuité de la terre EXISTANTE doit
        # être justifiée avant publication (la moitié manquante de la décision
        # fondateur du 19/08/2026).
        'justification_requise': not prise_vendue,
        'justification_fournie': justification,
        'mesure': mesure,
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
