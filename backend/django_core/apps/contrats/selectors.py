"""Sélecteurs LECTURE SEULE de la Gestion des contrats.

Point d'entrée cross-app : enrichissent les liens d'un contrat
(``ContratLien``) en appelant le sélecteur de l'app CIBLE quand elle en expose
un — jamais en important ses ``models``/``views`` (voir CLAUDE.md, frontière
cross-app). Tous les imports cross-app sont fonction-locaux pour éviter les
cycles. Quand une app cible n'a pas de sélecteur exploitable, on DÉGRADE
proprement : on renvoie le ``libelle`` mis en cache et les ids stockés, sans
rien importer.
"""
from datetime import timedelta

from django.db.models import ExpressionWrapper, F, fields
from django.utils import timezone

from .models import (
    Avenant,
    Contrat,
    ContratLien,
    EtapeApprobation,
    JalonContrat,
    Obligation,
    RegleApprobation,
    Resiliation,
    SignatureContrat,
    VersionContrat,
)


def contrats_a_preavis(company, within_days=30, today=None):
    """Contrats dont l'échéance de préavis approche (CONTRAT20).

    Renvoie un QuerySet scopé société des contrats dont la date limite de
    préavis (``date_fin − preavis_jours``) tombe dans la fenêtre
    ``[today, today + within_days]`` ET dont le préavis n'a pas encore été
    traité (``preavis_traite=False``) — ceux sur lesquels il faut agir AVANT
    une éventuelle tacite reconduction.

    Sont exclus : les contrats sans ``date_fin`` ou sans ``preavis_jours`` (rien
    à calculer), et les contrats déjà résiliés/expirés (plus d'enjeu de préavis).
    Ordonné par urgence : l'échéance de préavis la plus proche d'abord.

    ``within_days`` < 0 est ramené à 0 (fenêtre vide vers le futur). ``today``
    est injectable pour les tests.
    """
    if today is None:
        today = timezone.localdate()
    if within_days < 0:
        within_days = 0
    limite = today + timedelta(days=within_days)
    # Échéance de préavis calculée en base : date_fin − preavis_jours (jours).
    echeance = ExpressionWrapper(
        F('date_fin') - F('preavis_jours') * timedelta(days=1),
        output_field=fields.DateField(),
    )
    return (
        Contrat.objects.filter(company=company)
        .exclude(date_fin__isnull=True)
        .exclude(preavis_jours__isnull=True)
        .exclude(preavis_traite=True)
        .exclude(statut__in=[
            Contrat.Statut.RESILIE, Contrat.Statut.EXPIRE])
        .annotate(echeance_preavis_calc=echeance)
        .filter(echeance_preavis_calc__gte=today,
                echeance_preavis_calc__lte=limite)
        .order_by('echeance_preavis_calc', 'id')
    )


def contrats_a_renouveler(company, within_days=30, today=None):
    """Contrats dont l'ÉCHÉANCE (``date_fin``) approche (CONTRAT21).

    Renvoie un QuerySet scopé société des contrats dont la date de fin
    (``date_fin``) tombe dans la fenêtre ``[today, today + within_days]`` — ceux
    qu'il faut bientôt RENOUVELER ou clôturer. Complémentaire de
    ``contrats_a_preavis`` (CONTRAT20) : ce sélecteur regarde la FIN du contrat
    elle-même, pas la date limite de préavis (``date_fin − preavis_jours``).

    Sont exclus : les contrats sans ``date_fin`` (rien à échéancer) et les
    contrats déjà résiliés/expirés (plus d'enjeu de renouvellement). Le drapeau
    ``tacite_reconduction`` n'exclut PAS un contrat — il reste exposé par le
    sérialiseur pour que l'UI sache qu'il se reconduit tout seul. Ordonné par
    échéance la plus proche d'abord.

    ``within_days`` < 0 est ramené à 0 (fenêtre vide vers le futur). ``today``
    est injectable pour les tests.
    """
    if today is None:
        today = timezone.localdate()
    if within_days < 0:
        within_days = 0
    limite = today + timedelta(days=within_days)
    return (
        Contrat.objects.filter(company=company)
        .exclude(date_fin__isnull=True)
        .exclude(statut__in=[
            Contrat.Statut.RESILIE, Contrat.Statut.EXPIRE])
        .filter(date_fin__gte=today, date_fin__lte=limite)
        .order_by('date_fin', 'id')
    )


def versions_contrat(contrat):
    """Versions IMMUABLES d'un contrat (QuerySet scopé société, ordonné).

    Lecture seule (CONTRAT18). Ordre par numéro de ``version`` DÉCROISSANT (la
    dernière version en tête), cohérent avec ``Meta.ordering`` du modèle. La
    société est portée par le contrat ; on filtre aussi sur ``contrat.company``
    par sécurité même si le FK ``contrat`` la garantit.
    """
    return VersionContrat.objects.filter(
        contrat=contrat, company=contrat.company).order_by('-version', '-id')


def avenants_contrat(contrat):
    """Avenants (amendements) d'un contrat (QuerySet scopé société, ordonné).

    Lecture seule (CONTRAT24). Ordre par numéro d'avenant DÉCROISSANT (le dernier
    avenant en tête), cohérent avec ``Meta.ordering`` du modèle. La société est
    portée par le contrat ; on filtre aussi sur ``contrat.company`` par sécurité
    même si le FK ``contrat`` la garantit.
    """
    return Avenant.objects.filter(
        contrat=contrat, company=contrat.company).order_by('-numero', '-id')


def resiliations_contrat(contrat):
    """Résiliations d'un contrat (QuerySet scopé société, ordonné).

    Lecture seule (CONTRAT25). Ordre par ``id`` DÉCROISSANT (la dernière
    résiliation en tête), cohérent avec ``Meta.ordering`` du modèle. La société
    est portée par le contrat ; on filtre aussi sur ``contrat.company`` par
    sécurité même si le FK ``contrat`` la garantit.
    """
    return Resiliation.objects.filter(
        contrat=contrat, company=contrat.company).order_by('-id')


def jalons_contrat(contrat):
    """Jalons d'un contrat (QuerySet scopé société, ordonné) — CONTRAT26.

    Lecture seule. Ordre par ``numero`` (cohérent avec ``Meta.ordering``). La
    société est portée par le contrat ; on filtre aussi sur ``contrat.company``
    par sécurité même si le FK ``contrat`` la garantit.
    """
    return JalonContrat.objects.filter(
        contrat=contrat, company=contrat.company).order_by('numero', 'id')


def obligations_contrat(contrat):
    """Obligations (livrables) d'un contrat (QuerySet scopé société, ordonné) — CONTRAT26.

    Lecture seule. Ordre par ``ordre`` puis ``date_echeance`` (cohérent avec
    ``Meta.ordering``). La société est portée par le contrat ; on filtre aussi
    sur ``contrat.company`` par sécurité même si le FK ``contrat`` la garantit.
    """
    return Obligation.objects.filter(
        contrat=contrat, company=contrat.company).order_by(
            'ordre', 'date_echeance', 'id')


def engagements_sla_contrat(contrat):
    """Engagements SLA d'un contrat (QuerySet scopé société, ordonné) — CONTRAT27.

    Lecture seule. Ordre par ``id`` (cohérent avec ``Meta.ordering``). La
    société est portée par le contrat ; on filtre aussi sur ``contrat.company``
    par sécurité même si le FK ``contrat`` la garantit.
    """
    from .models import EngagementSLA

    return EngagementSLA.objects.filter(
        contrat=contrat, company=contrat.company).order_by('id')


def retenues_garantie_contrat(contrat):
    """Retenues de garantie d'un contrat (QuerySet scopé société) — CONTRAT28.

    Lecture seule. Ordre par ``id`` décroissant (cohérent avec ``Meta.ordering``).
    La société est portée par le contrat ; on filtre aussi sur ``contrat.company``
    par sécurité même si le FK ``contrat`` la garantit.
    """
    from .models import RetenueGarantie

    return RetenueGarantie.objects.filter(
        contrat=contrat, company=contrat.company).order_by('-id')


def cautions_contrat(contrat):
    """Cautions/garanties liées à un contrat (QuerySet scopé société) — CONTRAT29.

    Lecture seule. Ordre par ``id`` décroissant (cohérent avec ``Meta.ordering``).
    La société est portée par le contrat ; on filtre aussi sur ``contrat.company``
    par sécurité même si le FK ``contrat`` la garantit.
    """
    from .models import Caution

    return Caution.objects.filter(
        contrat=contrat, company=contrat.company).order_by('-id')


def signatures_contrat(contrat):
    """Signatures électroniques d'un contrat (QuerySet scopé société, ordonné).

    Lecture seule (CONTRAT16). Ordre par ``id`` (cohérent avec ``Meta.ordering``
    du modèle). La société est portée par le contrat ; on filtre aussi sur
    ``contrat.company`` par sécurité même si le FK ``contrat`` la garantit.
    """
    return SignatureContrat.objects.filter(
        contrat=contrat, company=contrat.company).order_by('contrat_id', 'id')


def etapes_approbation(contrat):
    """Étapes d'approbation d'un contrat (QuerySet scopé société, ordonné).

    Lecture seule (CONTRAT14). Ordre par ``niveau`` puis ``id``, cohérent avec
    ``Meta.ordering``. La société est portée par le contrat ; on filtre aussi
    sur ``contrat.company`` par sécurité même si le FK ``contrat`` la garantit.
    """
    return EtapeApprobation.objects.filter(
        contrat=contrat, company=contrat.company).order_by('niveau', 'id')


def regles_approbation(company):
    """Règles d'approbation ACTIVES d'une société (QuerySet ordonné).

    Lecture seule, scopée société. Ordre par priorité décroissante puis id,
    cohérent avec ``Meta.ordering`` du modèle.
    """
    return RegleApprobation.objects.filter(
        company=company, actif=True).order_by('-priorite', 'id')


def resoudre_regle_approbation(company, montant, type_contrat=None):
    """Résout la règle d'approbation la plus SPÉCIFIQUE couvrant un cas.

    Parcourt les règles actives de ``company`` qui couvrent le couple
    (``montant``, ``type_contrat``) via ``RegleApprobation.couvre`` et renvoie la
    plus spécifique (voir docstring du modèle). Renvoie ``None`` si aucune règle
    active ne s'applique — l'appelant décide alors d'un comportement par défaut.

    Aucun seuil n'est codé en dur : tout vient des règles en base.
    """
    candidates = [
        r for r in regles_approbation(company)
        if r.couvre(montant, type_contrat)
    ]
    if not candidates:
        return None

    def _cle(regle):
        # Tri décroissant : la plus spécifique en tête.
        # 1) règle ciblant un type précis prime sur « tous types ».
        type_specifique = 1 if regle.type_contrat else 0
        # 2) intervalle borné plus étroit prime (ouvert = moins spécifique).
        largeur = regle.largeur_intervalle()
        intervalle_borne = 1 if largeur is not None else 0
        # Plus étroit d'abord → on trie sur -largeur ; on neutralise pour les
        # intervalles ouverts en les classant après les bornés.
        largeur_tri = -largeur if largeur is not None else None
        return (
            type_specifique,
            intervalle_borne,
            # Pour les bornés : intervalle le plus étroit gagne (largeur_tri le
            # plus grand car négatif). Les ouverts (None) restent derrière grâce
            # à intervalle_borne=0, donc largeur_tri n'est lu que pour les bornés.
            largeur_tri if largeur_tri is not None else 0,
            regle.priorite,
            regle.id,
        )

    candidates.sort(key=_cle, reverse=True)
    return candidates[0]


def liens_for_contrat(contrat):
    """Liens d'un contrat (QuerySet scopé société, ordonné par id).

    Lecture seule. La société est portée par le contrat : on filtre aussi sur
    ``contrat.company`` par sécurité même si le FK ``contrat`` la garantit déjà.
    """
    return ContratLien.objects.filter(
        contrat=contrat, company=contrat.company).order_by('id')


def _label_devis(company, cible_id):
    """Libellé enrichi d'un devis via ``ventes.selectors`` (ou None).

    Import fonction-local : on ne touche JAMAIS ``ventes.models`` directement.
    Renvoie le ``label`` de la fiche-carte du devis, ou None si l'app ne peut
    pas l'enrichir (devis absent / hors société / sélecteur indisponible).
    """
    try:
        from apps.ventes import selectors as ventes_selectors
    except Exception:  # pragma: no cover - défensif (app absente)
        return None
    try:
        card = ventes_selectors.devis_card(cible_id, company)
    except Exception:  # pragma: no cover - défensif (cible introuvable)
        return None
    if not card:
        return None
    return card.get('label') or None


def _label_lead(company, cible_id):
    """Libellé enrichi d'un lead via ``crm.selectors`` (ou None).

    Import fonction-local : on ne touche JAMAIS ``crm.models`` directement.
    """
    try:
        from apps.crm import selectors as crm_selectors
    except Exception:  # pragma: no cover - défensif (app absente)
        return None
    try:
        card = crm_selectors.lead_card(cible_id, company)
    except Exception:  # pragma: no cover - défensif (cible introuvable)
        return None
    if not card:
        return None
    return card.get('label') or None


def _label_installation(company, cible_id):
    """Libellé enrichi d'un chantier via ``installations.selectors`` (ou None).

    Import fonction-local : on ne touche JAMAIS ``installations.models``
    directement.
    """
    try:
        from apps.installations import selectors as inst_selectors
    except Exception:  # pragma: no cover - défensif (app absente)
        return None
    try:
        card = inst_selectors.chantier_card(cible_id, company)
    except Exception:  # pragma: no cover - défensif (cible introuvable)
        return None
    if not card:
        return None
    return card.get('label') or None


# Enrichisseurs par type de cible. Une entrée n'existe QUE si l'app cible expose
# un sélecteur de lecture exploitable : `maintenance` → sav n'a pas de
# selectors.py aujourd'hui → ce type dégrade au libellé stocké, sans aucun
# import.
_ENRICHERS = {
    ContratLien.TypeCible.DEVIS: _label_devis,
    ContratLien.TypeCible.LEAD: _label_lead,
    ContratLien.TypeCible.INSTALLATION: _label_installation,
}


def liens_enrichis(contrat):
    """Liste de dicts {id, type_cible, cible_id, libelle, source} d'un contrat.

    Pour chaque lien : si l'app cible expose un enrichisseur, on s'en sert pour
    récupérer un libellé frais (``source='live'``) ; sinon — ou si
    l'enrichissement renvoie vide — on retombe sur le ``libelle`` stocké
    (``source='stored'``). Aucune exception ne remonte : un enrichisseur qui
    échoue dégrade au libellé stocké.
    """
    out = []
    for lien in liens_for_contrat(contrat):
        libelle = lien.libelle
        source = 'stored'
        enricher = _ENRICHERS.get(lien.type_cible)
        if enricher is not None:
            try:
                fresh = enricher(lien.company, lien.cible_id)
            except Exception:  # pragma: no cover - défensif
                fresh = None
            if fresh:
                libelle = fresh
                source = 'live'
        out.append({
            'id': lien.id,
            'type_cible': lien.type_cible,
            'cible_id': lien.cible_id,
            'libelle': libelle,
            'source': source,
        })
    return out
