"""NTAI19 — Lire un contrat : dates, montant, préavis, clauses clés.

Ce qui coûte cher sur un contrat, ce n'est pas de le lire : c'est de RATER son
préavis. Ce service lit la pièce (OCR existant + ``CONTRAT_SCHEMA``), en tire
les échéances, et PROPOSE une alerte de préavis.

PROPOSE — pas plus. Le premier appel ne fait qu'analyser (``applique:
false``) ; l'alerte n'est créée que si l'utilisateur REVIENT avec
``confirmer: true``, et elle est alors posée par le ``services.py`` de
``contrats`` (jamais par une écriture directe d'ici : la frontière inter-apps
veut que chaque app reste maîtresse de ses écritures).

Aucune date n'est inventée : si la date de fin est illisible et que le contrat
n'en porte pas, aucune alerte n'est proposée — on le dit, plutôt que de
suggérer une échéance fausse.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta

from core.ai.registry import is_capability_configured

from .services import AiCopiloteUnavailable, exiger_feature

#: Champs rendus à l'appelant (sous-ensemble « échéances » du gabarit contrat).
CONTRAT_CHAMPS_CLES = (
    'reference', 'date_debut', 'date_fin', 'duree', 'preavis',
    'montant_total', 'reconduction', 'clauses', 'parties', 'objet',
)

#: Formats de date acceptés à la lecture (le reste est refusé, jamais deviné).
_FORMATS_DATE = ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%d.%m.%Y')

#: « 3 mois », « 90 jours », « 2 ans » → un nombre de jours. Un mois vaut 30
#: jours et une année 365 : c'est une CONVENTION, annoncée comme telle dans la
#: proposition, pas une date contractuelle.
_JOURS_PAR_UNITE = {'jour': 1, 'jours': 1, 'mois': 30, 'an': 365, 'ans': 365,
                    'annee': 365, 'année': 365, 'annees': 365, 'années': 365}

_RE_DUREE = re.compile(
    r'(\d+)\s*(jours?|mois|ans?|ann[ée]es?)', re.IGNORECASE)


def lire_date(valeur):
    """Date lue depuis un texte, ou ``None`` si le format n'est pas reconnu."""
    if isinstance(valeur, date) and not isinstance(valeur, datetime):
        return valeur
    if isinstance(valeur, datetime):
        return valeur.date()
    texte = str(valeur or '').strip()[:32]
    if not texte:
        return None
    for fmt in _FORMATS_DATE:
        try:
            return datetime.strptime(texte, fmt).date()
        except ValueError:
            continue
    return None


def lire_preavis_jours(valeur):
    """Préavis en JOURS depuis « 3 mois » / « 90 jours » / ``90``.

    ``None`` si rien d'exploitable — aucune valeur par défaut n'est inventée.
    """
    if valeur in (None, ''):
        return None
    if isinstance(valeur, (int, float)) and not isinstance(valeur, bool):
        return int(valeur)
    texte = str(valeur).strip()
    if texte.isdigit():
        return int(texte)
    trouve = _RE_DUREE.search(texte)
    if not trouve:
        return None
    nombre = int(trouve.group(1))
    unite = trouve.group(2).lower().rstrip('s')
    facteur = _JOURS_PAR_UNITE.get(unite) or _JOURS_PAR_UNITE.get(
        unite + 's') or _JOURS_PAR_UNITE.get(trouve.group(2).lower())
    return nombre * facteur if facteur else None


def _document_scoped(company, document_id):
    """Pièce GED de la société — même résolution que l'extraction (NTAI15).

    Une seule porte vers la GED dans cette app : ``documents_for_company``,
    son SELECTOR (jamais ses modèles)."""
    from .extraction import _document_scoped as resoudre

    return resoudre(company, document_id)


def analyser_contrat(*, company, contrat_id, document_id=None,
                     confirmer=False, user=None) -> dict:
    """NTAI19 — Analyse un contrat et PROPOSE son alerte de préavis.

    Sans ``confirmer``, n'écrit rien. Avec ``confirmer=True``, crée l'alerte
    via ``apps.contrats.services.creer_alerte`` — et seulement si une date de
    déclenchement a pu être ÉTABLIE (jamais inventée).
    """
    exiger_feature(company, 'ai.analyser_contrat')

    from apps.records.serializers import resolve_target

    try:
        _ct, contrat = resolve_target('contrats.contrat', contrat_id, company)
    except ValueError as exc:
        raise AiCopiloteUnavailable(str(exc))

    champs = {}
    source = 'contrat'
    document = _document_scoped(company, document_id)
    if document is not None:
        champs = _extraire_du_document(document)
        source = 'ocr'

    # Les valeurs du CONTRAT priment sur l'OCR quand elles existent : la fiche
    # a été saisie/validée par un humain, la lecture automatique non.
    date_debut = getattr(contrat, 'date_debut', None) or lire_date(
        champs.get('date_debut'))
    date_fin = getattr(contrat, 'date_fin', None) or lire_date(
        champs.get('date_fin'))
    preavis_jours = (getattr(contrat, 'preavis_jours', None)
                     or lire_preavis_jours(champs.get('preavis')))
    montant = getattr(contrat, 'montant', None)

    proposition = _proposer_alerte(date_fin, preavis_jours)
    resultat = {
        'contrat_id': contrat.pk,
        'source': source,
        'date_debut': date_debut.isoformat() if date_debut else None,
        'date_fin': date_fin.isoformat() if date_fin else None,
        'preavis_jours': preavis_jours,
        'montant': str(montant) if montant is not None else None,
        'clauses': champs.get('clauses') or [],
        'champs_extraits': {cle: champs.get(cle)
                            for cle in CONTRAT_CHAMPS_CLES if champs.get(cle)},
        'proposition': proposition,
        'applique': False,
    }

    if confirmer:
        if proposition is None:
            raise AiCopiloteUnavailable(
                "Aucune échéance exploitable : impossible de proposer une "
                "alerte de préavis sans date de fin ni durée de préavis.")
        resultat.update(_appliquer_alerte(contrat, proposition, user=user))
    return resultat


def _extraire_du_document(document) -> dict:
    """Champs du gabarit ``contrat`` lus sur la pièce GED. ``{}`` si indispo.

    Sans clé OCR, renvoie ``{}`` SANS lever : l'analyse continue avec les seules
    données de la fiche contrat (dégradation utile plutôt qu'un échec)."""
    if not is_capability_configured('ocr'):
        return {}

    from core.ai.services import extract_document

    from .services import _octets_du_document

    contenu, mime = _octets_du_document(document)
    if not contenu:
        return {}
    resultat = extract_document(
        content=contenu, mime_type=mime or 'application/pdf', schema='contrat')
    if not (resultat.configured and resultat.ok):
        return {}
    return resultat.data or {}


def _proposer_alerte(date_fin, preavis_jours):
    """Proposition d'alerte, ou ``None`` si la date ne peut pas être ÉTABLIE."""
    if not date_fin or not preavis_jours:
        return None
    declenchement = date_fin - timedelta(days=int(preavis_jours))
    return {
        'type_alerte': 'preavis',
        'date_declenchement': declenchement.isoformat(),
        'message': (f'Préavis à donner avant le {date_fin.isoformat()} '
                    f'({int(preavis_jours)} jours de préavis).'),
        # Dit explicitement d'où sort la date : une soustraction, pas une
        # estimation.
        'calcul': 'date_fin - preavis_jours',
    }


def _appliquer_alerte(contrat, proposition, *, user=None) -> dict:
    """Crée l'alerte via le ``services.py`` de ``contrats`` (jamais d'écriture
    directe ici). Renvoie le fragment de réponse à fusionner."""
    from apps.contrats import services as contrats_services

    declenchement = lire_date(proposition.get('date_declenchement'))
    if declenchement is None:
        raise AiCopiloteUnavailable(
            "Date de déclenchement illisible — alerte non créée.")
    alerte = contrats_services.creer_alerte(
        contrat,
        # Valeur de la ``TextChoices`` de contrats passée EN CHAÎNE : lire son
        # énumération exigerait d'importer ``contrats.models``, ce que la
        # frontière inter-apps interdit.
        type_alerte=proposition.get('type_alerte') or 'preavis',
        date_declenchement=declenchement,
        message=proposition.get('message') or '',
        cree_par=user)
    return {'applique': True, 'alerte_id': alerte.pk}
