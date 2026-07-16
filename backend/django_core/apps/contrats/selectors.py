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
    ContratActivity,
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


def echeanciers_contrat(contrat):
    """Échéanciers de paiement d'un contrat (QuerySet scopé société) — CONTRAT30.

    Lecture seule. Ordre par ``id`` décroissant (cohérent avec ``Meta.ordering``).
    La société est portée par le contrat ; on filtre aussi sur ``contrat.company``
    par sécurité même si le FK ``contrat`` la garantit.
    """
    from .models import EcheancierContrat

    return EcheancierContrat.objects.filter(
        contrat=contrat, company=contrat.company).order_by('-id')


def lignes_echeancier(echeancier):
    """Lignes (échéances) d'un échéancier (QuerySet scopé société) — CONTRAT30.

    Lecture seule. Ordre par ``numero`` (cohérent avec ``Meta.ordering``). La
    société est portée par l'échéancier.
    """
    from .models import LigneEcheance

    return LigneEcheance.objects.filter(
        echeancier=echeancier, company=echeancier.company).order_by(
            'numero', 'id')


def indexations_contrat(contrat):
    """Indexations de prix d'un contrat (QuerySet scopé société) — CONTRAT32.

    Lecture seule. Ordre par ``id`` décroissant (cohérent avec ``Meta.ordering``).
    La société est portée par le contrat ; on filtre aussi sur ``contrat.company``
    par sécurité même si le FK ``contrat`` la garantit.
    """
    from .models import IndexationPrix

    return IndexationPrix.objects.filter(
        contrat=contrat, company=contrat.company).order_by('-id')


def pieces_conformite_contrat(contrat):
    """Pièces de conformité d'un contrat (QuerySet scopé société) — CONTRAT34.

    Lecture seule. Ordre par ``id`` (cohérent avec ``Meta.ordering``). La société
    est portée par le contrat ; on filtre aussi sur ``contrat.company`` par
    sécurité même si le FK ``contrat`` la garantit.
    """
    from .models import PieceConformite

    return PieceConformite.objects.filter(
        contrat=contrat, company=contrat.company).order_by('id')


def pieces_obligatoires_manquantes(contrat):
    """Pièces OBLIGATOIRES non encore fournies/validées d'un contrat — CONTRAT34.

    Lecture seule. Sous-ensemble des pièces ``obligatoire=True`` dont le statut
    n'est ni ``fournie`` ni ``validee`` (donc manquante/expirée/refusée) — la
    liste des pièces à réclamer. Scopée société.
    """
    from .models import PieceConformite

    return (
        PieceConformite.objects
        .filter(contrat=contrat, company=contrat.company, obligatoire=True)
        .exclude(statut__in=[
            PieceConformite.Statut.FOURNIE,
            PieceConformite.Statut.VALIDEE])
        .order_by('id')
    )


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


def etapes_approbation_en_attente(company):
    """XKB1 — étapes d'approbation EN ATTENTE de toute la société (QuerySet).

    Sélecteur company-wide (distinct de ``etapes_approbation(contrat)``, borné
    à un seul contrat) utilisé par l'agrégateur d'approbations cross-app
    (``apps/reporting``). Lecture seule, scopée société."""
    return (EtapeApprobation.objects
            .filter(company=company, statut=EtapeApprobation.Statut.EN_ATTENTE)
            .select_related('contrat', 'approbateur')
            .order_by('niveau', 'id'))


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


# ---------------------------------------------------------------------------
# CONTRAT33 — Tableau de bord contrats (actifs/à renouveler/en risque/valeur·MRR)
# ---------------------------------------------------------------------------

# Diviseur mensuel par périodicité d'échéancier : combien de mois couvre UNE
# période (sert à ramener un montant total d'échéancier en MRR mensuel). Une
# périodicité « unique »/« personnalisée » n'entre PAS dans le MRR (None).
_MOIS_PAR_PERIODE = {
    'mensuelle': 1,
    'trimestrielle': 3,
    'semestrielle': 6,
    'annuelle': 12,
}


def mrr_contrats(company):
    """MRR (revenu mensuel récurrent) des échéanciers actifs — CONTRAT33.

    Somme, sur les ``EcheancierContrat`` dont la facturation récurrente est
    active (``facturation_active=True``) et le statut ``actif``, du
    ``montant_total`` ramené au MOIS selon la périodicité (mensuelle = ÷1,
    trimestrielle = ÷3, semestrielle = ÷6, annuelle = ÷12). Les périodicités
    ``unique``/``personnalisée`` n'entrent pas dans le MRR. Lecture seule, scopée
    société. Renvoie un ``Decimal`` (arrondi 2 décimales).
    """
    from decimal import Decimal

    from .models import EcheancierContrat

    qs = EcheancierContrat.objects.filter(
        company=company,
        facturation_active=True,
        statut=EcheancierContrat.Statut.ACTIF,
    )
    total = Decimal('0')
    for ech in qs.only('montant_total', 'periodicite'):
        mois = _MOIS_PAR_PERIODE.get(ech.periodicite)
        if not mois:
            continue
        total += (ech.montant_total or Decimal('0')) / Decimal(mois)
    return total.quantize(Decimal('0.01'))


# Diviseur mensuel par périodicité ``sav.ContratMaintenance`` (mêmes maths que
# l'insight ``recurring_revenue`` du reporting — mensuel/trimestriel/
# semestriel/annuel, valeurs différentes de l'enum contrats ci-dessus).
_MOIS_PAR_PERIODICITE_SAV = {
    'mensuel': 1,
    'trimestriel': 3,
    'semestriel': 6,
    'annuel': 12,
}


def mrr_maintenance_sav(company, *, exclure_ids=None):
    """MRR équivalent mensuel des ``sav.ContratMaintenance`` facturables — XCTR13.

    Lecture seule, scopée société. Frontière cross-app : lit UNIQUEMENT via
    ``sav.selectors.contrats_maintenance_facturables`` (jamais
    ``sav.models``). Même maths que ``mrr_contrats``/l'insight
    ``recurring_revenue`` du reporting (prix × équivalent mensuel de la
    périodicité). ``exclure_ids`` (itérable d'ids ``ContratMaintenance``,
    optionnel) permet d'exclure les contrats DÉJÀ comptés via un ``Contrat``
    lié (anti double-comptage — XCTR13).
    """
    from decimal import Decimal

    from apps.sav.selectors import contrats_maintenance_facturables

    exclure = set(exclure_ids or ())
    total = Decimal('0')
    for cm in contrats_maintenance_facturables(company):
        if cm['id'] in exclure:
            continue
        mois = _MOIS_PAR_PERIODICITE_SAV.get(cm['periodicite'])
        if not mois:
            continue
        total += (cm['prix'] or Decimal('0')) / Decimal(mois)
    return total.quantize(Decimal('0.01'))


def mrr_combine(company):
    """MRR combiné contrats + maintenance SAV, SANS double-comptage — XCTR13.

    Somme ``mrr_contrats`` (échéanciers CONTRAT31) et ``mrr_maintenance_sav``
    (``sav.ContratMaintenance`` facturables) — un ``ContratMaintenance``
    RATTACHÉ à un ``Contrat`` (via ``Contrat.sav_contrat_maintenance_id``) est
    EXCLU de la part maintenance SAV (compté une seule fois, côté contrat, où
    son échéancier CONTRAT31 porte déjà le MRR — le lien ne duplique jamais
    la facturation, XCTR13 valide seulement l'existence de l'id). Lecture
    seule, scopée société.
    """
    from .models import Contrat

    ids_lies = set(
        Contrat.objects.filter(
            company=company, sav_contrat_maintenance_id__isnull=False)
        .values_list('sav_contrat_maintenance_id', flat=True))

    return (
        mrr_contrats(company)
        + mrr_maintenance_sav(company, exclure_ids=ids_lies)
    )


def contrats_en_risque(company, within_days=30, today=None):
    """Contrats « EN RISQUE » : suspendus, en préavis dû, ou en résiliation active.

    CONTRAT33. Renvoie un QuerySet DISTINCT scopé société des contrats à risque :
    - statut ``suspendu`` ;
    - OU une résiliation ACTIVE (``demande``/``effective``) ouverte ;
    - OU une échéance de préavis dans la fenêtre ``[today, today+within_days]``
      non encore traitée (réutilise ``contrats_a_preavis``).
    Les contrats résiliés/expirés (terminaux) sont exclus. Lecture seule.
    """
    if today is None:
        today = timezone.localdate()
    preavis_ids = list(
        contrats_a_preavis(company, within_days=within_days, today=today)
        .values_list('id', flat=True))
    from django.db.models import Q

    from .models import Resiliation

    resil_ids = list(
        Resiliation.objects.filter(company=company)
        .exclude(statut=Resiliation.Statut.ANNULEE)
        .values_list('contrat_id', flat=True))
    return (
        Contrat.objects.filter(company=company)
        .exclude(statut__in=[Contrat.Statut.RESILIE, Contrat.Statut.EXPIRE])
        .filter(
            Q(statut=Contrat.Statut.SUSPENDU)
            | Q(id__in=preavis_ids)
            | Q(id__in=resil_ids))
        .distinct()
        .order_by('-id')
    )


def tableau_de_bord_contrats(company, within_days=30, today=None):
    """Agrégats du tableau de bord des contrats — CONTRAT33.

    Renvoie un dict d'indicateurs scopés société (lecture seule, aucune écriture) :

    - ``total`` : nombre total de contrats ;
    - ``par_statut`` : répartition {statut: count} ;
    - ``par_type`` : répartition {type_contrat: count} ;
    - ``actifs`` : nombre de contrats ``actif`` ;
    - ``a_renouveler`` : nombre de contrats dont la fin approche (CONTRAT21) ;
    - ``en_risque`` : nombre de contrats à risque (``contrats_en_risque``) ;
    - ``valeur_active`` : somme des ``montant`` des contrats ``actif`` ;
    - ``valeur_totale`` : somme des ``montant`` de tous les contrats ;
    - ``mrr`` : revenu mensuel récurrent des échéanciers contrats seuls
      (``mrr_contrats`` — inchangé, rétrocompatible) ;
    - ``mrr_combine`` : MRR contrats + ``sav.ContratMaintenance`` facturables,
      SANS double-comptage (``mrr_combine`` — XCTR13) ;
    - ``mrr_par_responsable`` : ventilation du MRR par responsable (XCTR10,
      clé ``id`` du responsable, ``'sans_responsable'`` si non renseigné).
    """
    from decimal import Decimal

    from django.db.models import Count, Sum

    base = Contrat.objects.filter(company=company)
    par_statut = {
        row['statut']: row['n']
        for row in base.values('statut').annotate(n=Count('id'))
    }
    par_type = {
        row['type_contrat']: row['n']
        for row in base.values('type_contrat').annotate(n=Count('id'))
    }
    valeur_active = base.filter(
        statut=Contrat.Statut.ACTIF).aggregate(s=Sum('montant'))['s'] \
        or Decimal('0')
    valeur_totale = base.aggregate(s=Sum('montant'))['s'] or Decimal('0')
    return {
        'total': base.count(),
        'par_statut': par_statut,
        'par_type': par_type,
        'actifs': par_statut.get(Contrat.Statut.ACTIF, 0),
        'a_renouveler': contrats_a_renouveler(
            company, within_days=within_days, today=today).count(),
        'en_risque': contrats_en_risque(
            company, within_days=within_days, today=today).count(),
        'valeur_active': valeur_active,
        'valeur_totale': valeur_totale,
        'mrr': mrr_contrats(company),
        'mrr_combine': mrr_combine(company),
        'exceptions_facturation': exceptions_facturation_count(company),
        'mrr_par_responsable': mrr_par_responsable(company),
    }


def mrr_par_responsable(company):
    """Ventilation du MRR par responsable (owner) — XCTR10.

    Lecture seule, scopée société. Somme le MRR de chaque contrat (via
    ``mrr_contrat_actif``) ventilé par ``responsable_id`` — clé ``'sans_
    responsable'`` (string) pour les contrats sans responsable renseigné
    (comportement inchangé : ils existaient déjà, ils sont juste regroupés).
    Renvoie un dict ``{responsable_id_ou_'sans_responsable': Decimal}``.
    """
    from decimal import Decimal

    ventilation = {}
    qs = (
        Contrat.objects.filter(company=company)
        .exclude(statut__in=[Contrat.Statut.RESILIE, Contrat.Statut.EXPIRE])
        .prefetch_related('echeanciers')
    )
    for contrat in qs:
        mrr = mrr_contrat_actif(contrat)
        if mrr <= 0:
            continue
        cle = contrat.responsable_id or 'sans_responsable'
        ventilation[cle] = ventilation.get(cle, Decimal('0')) + mrr
    return {k: v.quantize(Decimal('0.01')) for k, v in ventilation.items()}


def exceptions_facturation_count(company):
    """Nombre de cycles de facturation en échec — carte du tableau de bord (XCTR5).

    Lecture seule, scopée société. Alimente la carte « Exceptions de
    facturation » sans dupliquer la liste (voir ``services.exceptions_facturation``
    pour le détail des entrées).
    """
    from .models import CycleFacturationLog

    return CycleFacturationLog.objects.filter(
        company=company, statut=CycleFacturationLog.Statut.ECHEC).count()


# ---------------------------------------------------------------------------
# CONTRAT35 — Reporting valeur contractuelle & taux de renouvellement
# ---------------------------------------------------------------------------


def reporting_contrats(company):
    """Reporting valeur contractuelle & taux de renouvellement — CONTRAT35.

    Lecture seule, scopée société. Renvoie un dict :

    - ``valeur_totale`` : somme des ``montant`` de tous les contrats ;
    - ``valeur_active`` : somme des ``montant`` des contrats ``actif`` ;
    - ``valeur_par_type`` : {type_contrat: somme des montants} ;
    - ``nb_renouvellements`` : total des renouvellements effectifs (somme de
      ``nb_renouvellements`` — CONTRAT23) ;
    - ``nb_contrats_renouveles`` : nombre de contrats ayant été renouvelés au
      moins une fois ;
    - ``nb_echus`` : nombre de contrats arrivés à échéance (résiliés/expirés OU
      ``date_fin`` passée) — base du taux de renouvellement ;
    - ``taux_renouvellement`` : ``nb_contrats_renouveles / nb_echus`` en %
      (0 si aucun échu), arrondi 2 décimales.
    """
    from decimal import Decimal

    from django.db.models import Q, Sum
    from django.utils import timezone as _tz

    today = _tz.localdate()
    base = Contrat.objects.filter(company=company)

    valeur_totale = base.aggregate(s=Sum('montant'))['s'] or Decimal('0')
    valeur_active = base.filter(
        statut=Contrat.Statut.ACTIF).aggregate(s=Sum('montant'))['s'] \
        or Decimal('0')
    valeur_par_type = {
        row['type_contrat']: (row['s'] or Decimal('0'))
        for row in base.values('type_contrat').annotate(s=Sum('montant'))
    }

    nb_renouvellements = base.aggregate(
        s=Sum('nb_renouvellements'))['s'] or 0
    nb_contrats_renouveles = base.filter(
        nb_renouvellements__gt=0).count()
    nb_echus = base.filter(
        Q(statut__in=[Contrat.Statut.RESILIE, Contrat.Statut.EXPIRE])
        | Q(date_fin__lt=today)).distinct().count()
    taux = (
        (Decimal(nb_contrats_renouveles) / Decimal(nb_echus) * Decimal('100'))
        .quantize(Decimal('0.01'))
        if nb_echus else Decimal('0.00')
    )
    return {
        'valeur_totale': valeur_totale,
        'valeur_active': valeur_active,
        'valeur_par_type': valeur_par_type,
        'nb_renouvellements': nb_renouvellements,
        'nb_contrats_renouveles': nb_contrats_renouveles,
        'nb_echus': nb_echus,
        'taux_renouvellement': taux,
    }


# ---------------------------------------------------------------------------
# XCTR7 — Cascade MRR (new / expansion / contraction / churn / net) + motif
# ---------------------------------------------------------------------------


def _mrr_equivalent_mensuel(montant, periodicite):
    """Convertit un montant de PÉRIODE en équivalent MENSUEL selon la
    périodicité (même table que ``mrr_contrats``). ``None`` si la périodicité
    n'est pas prorata-able (unique/personnalisée) — le montant est alors ignoré
    du calcul MRR."""
    from decimal import Decimal

    mois = _MOIS_PAR_PERIODE.get(periodicite)
    if not mois:
        return None
    return montant / Decimal(mois)


def mrr_contrat_actif(contrat):
    """MRR mensuel d'UN contrat (somme de ses échéanciers actifs facturables).

    Réutilise la même conversion que ``mrr_contrats`` (CONTRAT33) mais bornée à
    UN contrat — sert de brique à ``mouvements_mrr`` (new/expansion/churn).
    """
    from decimal import Decimal

    from .models import EcheancierContrat

    total = Decimal('0')
    qs = contrat.echeanciers.filter(
        facturation_active=True, statut=EcheancierContrat.Statut.ACTIF)
    for ech in qs.only('montant_total', 'periodicite'):
        equiv = _mrr_equivalent_mensuel(
            ech.montant_total or Decimal('0'), ech.periodicite)
        if equiv is not None:
            total += equiv
    return total.quantize(Decimal('0.01'))


def mouvements_mrr(company, debut, fin):
    """Cascade MRR new/expansion/contraction/churn/net sur ``[debut, fin]`` — XCTR7.

    Décompose les MOUVEMENTS de revenu mensuel récurrent survenus dans la
    fenêtre ``[debut, fin]`` (dates incluses), scopés société :

    - ``new`` : somme du MRR (à date d'aujourd'hui) des contrats dont
      ``date_creation`` tombe dans la fenêtre ET qui portent un MRR non nul
      (échéancier actif facturable) — un nouveau contrat sans facturation
      récurrente n'entre pas dans le MRR (cohérent avec ``mrr_contrats``) ;
    - ``expansion`` : somme des ``Avenant.montant_delta`` POSITIFS dont
      ``date_effet`` (repli ``date_creation``) tombe dans la fenêtre, convertis
      en équivalent mensuel via la périodicité du PREMIER échéancier actif du
      contrat (repli : montant brut si aucun échéancier — traité comme mensuel) ;
    - ``contraction`` : idem pour les deltas NÉGATIFS (valeur renvoyée négative) ;
    - ``churn`` : somme (négative) du MRR PERDU par les contrats RÉSILIÉS dans la
      fenêtre (``Resiliation.statut != annulee``, ``date_effet`` repli
      ``date_demande`` dans la fenêtre) — le MRR perdu est celui du contrat AU
      MOMENT de la résiliation (``mrr_contrat_actif`` avant résiliation n'étant
      plus recalculable après coup, on utilise le MRR courant du contrat comme
      meilleure approximation disponible — cohérent avec CONTRAT33) ;
    - ``churn_par_motif`` : ventilation de ``churn`` par motif — ZCTR3 : utilise
      ``Resiliation.motif_ref.libelle`` (normalisé) quand présent, sinon replie
      sur le texte libre ``Resiliation.motif`` (motif vide groupé sous ``''``)
      — rétrocompatible avec les résiliations sans motif référentiel ;
    - ``net`` : ``new + expansion + contraction + churn`` (contraction et churn
      étant déjà négatifs, ``net`` est une simple somme algébrique — la garde
      ``somme new+expansion−contraction−churn = variation du MRR`` du Done= se
      lit avec contraction/churn déjà signés négatifs, donc ``net`` EST la
      variation) ;
    - ``net_par_responsable`` : même cascade ``net``, ventilée par
      ``Contrat.responsable`` (XCTR10 ; clé ``'sans_responsable'`` si absent).

    Lecture seule, scopée société. Tous les montants sont des ``Decimal``
    arrondis 2 décimales.
    """
    from decimal import Decimal

    from .models import Avenant, Contrat, Resiliation

    def _cle_resp(contrat):
        return contrat.responsable_id or 'sans_responsable'

    net_par_resp = {}

    # Avenants D'ABORD : leur équivalent mensuel sert à la fois à la cascade
    # expansion/contraction ET à neutraliser le double-comptage avec ``new``
    # (un avenant appliqué à un contrat NÉ dans la même fenêtre modifie
    # ``Contrat.montant`` sans forcément re-synchroniser l'échéancier — voir
    # ``creer_avenant`` — donc ``mrr_contrat_actif`` calculé APRÈS l'avenant
    # peut déjà (ou pas) porter l'effet de l'avenant selon que l'échéancier a
    # été resynchronisé entre-temps ; dans les deux cas l'avenant est déjà
    # compté une fois dans expansion/contraction, donc il ne doit JAMAIS être
    # recompté dans ``new`` — cf. l'invariant
    # new+expansion-contraction-churn = variation du MRR observée).
    expansion = Decimal('0')
    contraction = Decimal('0')
    avenant_equiv_par_contrat = {}
    avenants = (
        Avenant.objects.filter(company=company, montant_delta__isnull=False)
        .exclude(montant_delta=Decimal('0'))
        .select_related('contrat')
    )
    for avenant in avenants:
        date_ref = avenant.date_effet or avenant.date_creation.date()
        if not (debut <= date_ref <= fin):
            continue
        premier_ech = (
            avenant.contrat.echeanciers
            .exclude(periodicite='unique')
            .exclude(periodicite='personnalisee')
            .order_by('id')
            .first()
        )
        if premier_ech is not None:
            equiv = _mrr_equivalent_mensuel(
                avenant.montant_delta, premier_ech.periodicite)
        else:
            equiv = avenant.montant_delta
        if equiv is None:
            continue
        if equiv > 0:
            expansion += equiv
        elif equiv < 0:
            contraction += equiv
        if equiv:
            cle = _cle_resp(avenant.contrat)
            net_par_resp[cle] = net_par_resp.get(cle, Decimal('0')) + equiv
            avenant_equiv_par_contrat[avenant.contrat_id] = (
                avenant_equiv_par_contrat.get(avenant.contrat_id, Decimal('0'))
                + equiv)

    new = Decimal('0')
    for contrat in Contrat.objects.filter(
            company=company, date_creation__date__gte=debut,
            date_creation__date__lte=fin):
        # Neutralise l'effet des avenants DÉJÀ compté ci-dessus pour ce même
        # contrat (même fenêtre) — sinon un avenant sur un contrat tout juste
        # créé serait compté à la fois dans ``new`` et dans
        # ``expansion``/``contraction``.
        montant = (
            mrr_contrat_actif(contrat)
            - avenant_equiv_par_contrat.get(contrat.id, Decimal('0')))
        new += montant
        if montant:
            cle = _cle_resp(contrat)
            net_par_resp[cle] = net_par_resp.get(cle, Decimal('0')) + montant

    churn = Decimal('0')
    churn_par_motif = {}
    resiliations = (
        Resiliation.objects.filter(company=company)
        .exclude(statut=Resiliation.Statut.ANNULEE)
        .select_related('contrat', 'motif_ref')
    )
    for resiliation in resiliations:
        date_ref = resiliation.date_effet or resiliation.date_demande
        if date_ref is None or not (debut <= date_ref <= fin):
            continue
        perte = mrr_contrat_actif(resiliation.contrat)
        if perte <= 0:
            continue
        # ZCTR3 — motif normalisé prioritaire (référentiel), repli texte libre.
        if resiliation.motif_ref_id:
            motif = resiliation.motif_ref.libelle
        else:
            motif = (resiliation.motif or '').strip()
        churn -= perte
        churn_par_motif[motif] = churn_par_motif.get(
            motif, Decimal('0')) - perte
        cle = _cle_resp(resiliation.contrat)
        net_par_resp[cle] = net_par_resp.get(cle, Decimal('0')) - perte

    net = (new + expansion + contraction + churn).quantize(Decimal('0.01'))

    return {
        'debut': debut,
        'fin': fin,
        'new': new.quantize(Decimal('0.01')),
        'expansion': expansion.quantize(Decimal('0.01')),
        'contraction': contraction.quantize(Decimal('0.01')),
        'churn': churn.quantize(Decimal('0.01')),
        'churn_par_motif': {
            k: v.quantize(Decimal('0.01')) for k, v in churn_par_motif.items()
        },
        'net': net,
        'net_par_responsable': {
            k: v.quantize(Decimal('0.01')) for k, v in net_par_resp.items()
        },
    }


# ---------------------------------------------------------------------------
# XCTR8 — Cohortes de rétention contrats (logo + revenu, NRR/GRR)
# ---------------------------------------------------------------------------


def _mois_ecoules(debut, fin):
    """Nombre de MOIS calendaires entiers écoulés entre ``debut`` et ``fin``.

    ``0`` le même mois, ``1`` un mois plus tard, etc. Jamais négatif (borné à
    0 si ``fin`` précède ``debut``).
    """
    delta = (fin.year - debut.year) * 12 + (fin.month - debut.month)
    return max(0, delta)


def _mrr_initial_contrat(contrat):
    """Montant D'ORIGINE (à la signature) d'un contrat — avant tout avenant.

    ``Contrat.montant`` est un champ mutable : ``services.creer_avenant``
    l'incrémente en place à chaque avenant (``montant_delta``), donc sa valeur
    COURANTE n'est PAS le montant initial de la cohorte dès qu'un avenant a été
    posé. On reconstruit le montant d'origine en retranchant la somme de tous
    les ``Avenant.montant_delta`` déjà appliqués — cf. XCTR8 (NRR/GRR doivent se
    mesurer contre le MRR DE DÉPART de la cohorte, pas contre le montant courant
    déjà gonflé par l'expansion elle-même, sinon ``revenu_pct`` reste bloqué à
    100 % quelle que soit l'expansion réelle).
    """
    from decimal import Decimal

    from .models import Avenant

    deltas = (
        Avenant.objects.filter(contrat=contrat, montant_delta__isnull=False)
        .values_list('montant_delta', flat=True))
    total_deltas = sum(deltas, Decimal('0'))
    return (contrat.montant or Decimal('0')) - total_deltas


def cohortes_retention(company, today=None):
    """Matrice de cohortes de rétention contrats (logo + revenu) — XCTR8.

    Regroupe les contrats par MOIS DE SIGNATURE (``date_debut``, repli
    ``date_creation`` si absent) — le « mois de cohorte ». Pour chaque cohorte,
    calcule à chaque « mois d'ancienneté » ``k`` (0, 1, 2… jusqu'au mois
    courant) :

    - ``logo`` : % de contrats de la cohorte encore ACTIFS au mois ``k`` (non
      résiliés/expirés à cette date, ou résiliés APRÈS avoir atteint ce mois
      d'ancienneté) ;
    - ``revenu`` (NRR — Net Revenue Retention) : % du MRR de cohorte initial
      encore généré au mois ``k``, EXPANSION INCLUSE (le MRR courant du contrat
      peut dépasser 100 % s'il a grossi via avenant) ;
    - ``revenu_grr`` (GRR — Gross Revenue Retention) : identique à ``revenu``
      mais PLAFONNÉ à 100 % par contrat (l'expansion n'y contribue jamais,
      seule la perte compte).

    Un contrat RÉSILIÉ AVANT d'atteindre le mois ``k`` sort du dénominateur ET
    du numérateur à partir de ce mois (perte définitive) — jamais de division
    par zéro : une cohorte/mois sans contrat éligible est simplement ABSENTE
    de la matrice (pas d'entrée à 0/0).

    Lecture seule, scopée société. ``today`` est injectable pour les tests.
    Renvoie ``{'cohortes': {mois_cohorte_iso: {age_mois: {...}}}, 'mois_max'}``.
    """
    from collections import defaultdict
    from decimal import Decimal

    from .models import Contrat

    if today is None:
        today = timezone.localdate()

    contrats = list(
        Contrat.objects.filter(company=company)
        .exclude(date_debut__isnull=True, date_creation__isnull=True))

    # Regroupe par mois de cohorte (année-mois du premier jour du mois).
    cohortes_contrats = defaultdict(list)
    for contrat in contrats:
        base = contrat.date_debut or contrat.date_creation.date()
        cohorte_mois = base.replace(day=1)
        cohortes_contrats[cohorte_mois].append(contrat)

    resultat = {}
    mois_max_global = 0

    for cohorte_mois, membres in cohortes_contrats.items():
        mois_max = _mois_ecoules(cohorte_mois, today)
        mois_max_global = max(mois_max_global, mois_max)
        matrice = {}

        for k in range(0, mois_max + 1):
            eligibles = []
            for contrat in membres:
                base = contrat.date_debut or contrat.date_creation.date()
                # Le contrat doit avoir ATTEINT ce mois d'ancienneté à ce jour.
                if _mois_ecoules(base, today) < k:
                    continue
                eligibles.append(contrat)
            if not eligibles:
                continue  # jamais de division par zéro — mois absent

            mrr_initial_total = Decimal('0')
            for contrat in eligibles:
                mrr_initial_total += _mrr_initial_contrat(contrat)

            actifs = 0
            mrr_courant_total = Decimal('0')
            mrr_courant_plafonne_total = Decimal('0')
            for contrat in eligibles:
                # Un contrat est PERDU pour la cohorte dès qu'il est dans un
                # état terminal (résilié/expiré) — même vérification que
                # ``contrats_en_risque``/CONTRAT33, sans dépendre de
                # ``services`` (selectors reste en amont de services).
                perdu = contrat.statut in (
                    Contrat.Statut.RESILIE, Contrat.Statut.EXPIRE)
                if not perdu:
                    actifs += 1
                mrr = Decimal('0') if perdu else mrr_contrat_actif(contrat)
                mrr_courant_total += mrr
                # Plafond GRR = montant D'ORIGINE de CE contrat (pas le montant
                # courant, déjà gonflé par l'expansion qu'on plafonne ici).
                plafond = _mrr_initial_contrat(contrat)
                mrr_courant_plafonne_total += min(mrr, plafond)

            logo_pct = (
                Decimal(actifs) / Decimal(len(eligibles)) * Decimal('100')
            ).quantize(Decimal('0.01'))

            if mrr_initial_total > 0:
                revenu_pct = (
                    mrr_courant_total / mrr_initial_total * Decimal('100')
                ).quantize(Decimal('0.01'))
                revenu_grr_pct = (
                    mrr_courant_plafonne_total / mrr_initial_total
                    * Decimal('100')
                ).quantize(Decimal('0.01'))
            else:
                revenu_pct = Decimal('0.00')
                revenu_grr_pct = Decimal('0.00')

            matrice[k] = {
                'nb_contrats': len(eligibles),
                'nb_actifs': actifs,
                'logo_pct': logo_pct,
                'revenu_pct': revenu_pct,
                'revenu_grr_pct': revenu_grr_pct,
            }

        resultat[cohorte_mois.isoformat()] = matrice

    return {'cohortes': resultat, 'mois_max': mois_max_global}


# ---------------------------------------------------------------------------
# XCTR9 — CLV (valeur vie client) sur revenu récurrent
# ---------------------------------------------------------------------------


def mrr_client(company, client_id):
    """MRR mensuel d'UN client (somme du MRR de ses contrats actifs) — XCTR9.

    Lecture seule, scopée société. ``client_id`` est un lien LÂCHE
    (``Contrat.client_id``) — jamais un import de ``crm.models``. Renvoie un
    ``Decimal`` (0 si le client n'a aucun contrat facturable).
    """
    from decimal import Decimal

    from .models import Contrat

    total = Decimal('0')
    for contrat in Contrat.objects.filter(
            company=company, client_id=client_id).exclude(
                statut__in=[Contrat.Statut.RESILIE, Contrat.Statut.EXPIRE]):
        total += mrr_contrat_actif(contrat)
    return total.quantize(Decimal('0.01'))


def taux_churn_mensuel_company(company, within_days=90):
    """Taux de churn MENSUEL observé de la société (fraction ``[0, 1]``) — XCTR9.

    Approxime le taux de churn mensuel à partir des résiliations RÉCENTES
    (``within_days``, défaut 90 jours ≈ 3 mois) rapportées à la base de
    contrats actifs+résiliés sur la fenêtre, ramené à un taux MENSUEL (division
    par le nombre de mois de la fenêtre). Lecture seule, scopée société.

    Renvoie ``None`` si la base est vide (aucun contrat pour calculer un taux
    exploitable) — repli propre, jamais de division par zéro.
    """
    from decimal import Decimal

    from .models import Contrat, Resiliation

    today = timezone.localdate()
    debut = today - timedelta(days=within_days)

    base_count = Contrat.objects.filter(company=company).count()
    if base_count == 0:
        return None

    resilies = Resiliation.objects.filter(
        company=company,
    ).exclude(statut=Resiliation.Statut.ANNULEE).filter(
        date_demande__gte=debut, date_demande__lte=today).count()

    mois_fenetre = max(Decimal('1'), Decimal(within_days) / Decimal('30'))
    taux = (Decimal(resilies) / Decimal(base_count)) / mois_fenetre
    if taux <= 0:
        return None
    return taux


def clv_client(company, client_id, *, within_days=90):
    """CLV d'un client sur revenu récurrent (délègue à ``core.clv``) — XCTR9.

    Alimente le calculateur PUR ``core.clv.clv`` avec l'ARPC mensuel du client
    (``mrr_client``) et le taux de churn OBSERVÉ de la société
    (``taux_churn_mensuel_company``). Lecture seule, scopée société. Renvoie le
    ``core.clv.ClvResult`` (``clv=None`` si le churn est nul/inconnu — un client
    SANS contrat renvoie un ARPC à 0, donc une CLV à 0 si un taux de churn est
    disponible, ou ``None`` si aucun taux n'est calculable).
    """
    from core.clv import clv as _clv

    arpc = mrr_client(company, client_id)
    taux = taux_churn_mensuel_company(company, within_days=within_days)
    return _clv(arpc, taux)


# ---------------------------------------------------------------------------
# XCTR14 — Portail client : « Mes contrats & abonnements »
# ---------------------------------------------------------------------------


def contrats_portail_client(company, client_id):
    """Contrats d'UN client, projetés pour le portail public (XCTR14).

    Lecture minimisée (loi 09-08) : seuls les champs nécessaires au client
    sont exposés (statut, dates, périodicité, montant, prochaine échéance) —
    jamais ``confidentialite``, ``responsable``, ni aucun champ interne. Le
    client ne voit QUE ses propres contrats (filtré par ``client_id`` ET
    ``company`` — jamais un contrat d'un autre client ou d'une autre société).
    Renvoie une liste de dicts triés par échéance la plus proche.
    """
    contrats = (
        Contrat.objects
        .filter(company=company, client_id=client_id)
        .prefetch_related('echeanciers__lignes')
        .order_by('-date_creation')
    )
    rows = []
    for contrat in contrats:
        prochaine = None
        factures_liees = []
        for echeancier in contrat.echeanciers.all():
            for ligne in echeancier.lignes.all():
                if ligne.statut in ('a_venir', 'en_retard') and (
                        prochaine is None or ligne.date_echeance < prochaine):
                    prochaine = ligne.date_echeance
                if ligne.facture_id:
                    factures_liees.append(ligne.facture_id)
        rows.append({
            'id': contrat.id,
            'reference': contrat.reference,
            'objet': contrat.objet,
            'type_contrat': contrat.type_contrat,
            'statut': contrat.statut,
            'statut_display': contrat.get_statut_display(),
            'date_debut': contrat.date_debut,
            'date_fin': contrat.date_fin,
            'montant': contrat.montant,
            'devise': contrat.devise,
            'prochaine_echeance': prochaine,
            'factures_ids': factures_liees,
        })
    return rows


# ---------------------------------------------------------------------------
# XCTR17 — Location de matériel SORTANTE : disponibilité
# ---------------------------------------------------------------------------


def disponibilite_produit(company, produit_id, *, numero_serie=None,
                          date_debut=None, date_fin=None):
    """Disponibilité d'un produit louable (XCTR17) — lecture seule.

    Sans fenêtre de dates (``date_debut``/``date_fin`` absents) : renvoie la
    liste des ordres ACTIFS (réservée/enlevée) du produit (occupé quand), en
    triant par date d'enlèvement prévue. Avec une fenêtre : renvoie en plus
    ``disponible`` (``True`` si AUCUN ordre actif — filtré éventuellement par
    ``numero_serie`` — ne chevauche la fenêtre demandée).
    """
    from .models import OrdreLocation

    qs = OrdreLocation.objects.filter(
        company=company, produit_id=produit_id,
        statut__in=OrdreLocation.STATUTS_ACTIFS,
    )
    if numero_serie is not None:
        qs = qs.filter(numero_serie=numero_serie)
    qs = qs.order_by('date_enlevement_prevue', 'id')

    occupations = [
        {
            'id': o.id,
            'numero_serie': o.numero_serie,
            'statut': o.statut,
            'date_enlevement_prevue': o.date_enlevement_prevue,
            'date_retour_prevue': o.date_retour_prevue,
        }
        for o in qs
    ]

    result = {'produit_id': produit_id, 'occupations': occupations}
    if date_debut is not None and date_fin is not None:
        result['disponible'] = not any(
            o.chevauche(date_debut, date_fin) for o in qs)
        result['date_debut'] = date_debut
        result['date_fin'] = date_fin
    return result


# ---------------------------------------------------------------------------
# XCTR19 — Retour de location : ordres en retard
# ---------------------------------------------------------------------------


def ordres_location_en_retard(company, today=None):
    """Ordres de location ENLEVÉS dont le retour prévu est dépassé sans
    retour effectif — XCTR19. Lecture seule, scopée société."""
    from .models import OrdreLocation

    if today is None:
        today = timezone.localdate()
    return (
        OrdreLocation.objects
        .filter(company=company, statut=OrdreLocation.Statut.ENLEVEE,
                date_retour_prevue__lt=today)
        .order_by('date_retour_prevue', 'id')
    )


# ---------------------------------------------------------------------------
# XCTR21 — Utilisation & ROI du parc de location
# ---------------------------------------------------------------------------


def _jours_loues_dans_periode(ordre, periode_debut, periode_fin):
    """Nombre de jours (bornes incluses) où ``ordre`` occupe le produit, BORNÉ
    à ``[periode_debut, periode_fin]`` — XCTR21. Utilise la fenêtre
    PRÉVUE (cohérent avec la détection de conflit XCTR17) ; un ordre hors
    fenêtre renvoie 0 (jamais négatif)."""
    debut = max(ordre.date_enlevement_prevue, periode_debut)
    fin = min(ordre.date_retour_prevue, periode_fin)
    if fin < debut:
        return 0
    return (fin - debut).days + 1


def utilisation_parc_location(company, *, periode_debut, periode_fin,
                              admin=False):
    """Rapport d'utilisation/ROI du parc de location, PAR produit — XCTR21.

    Pour chaque produit louable ayant AU MOINS un ordre de location (actif ou
    non — un ordre annulé/clôturé compte pour l'historique), calcule sur la
    période ``[periode_debut, periode_fin]`` (bornes incluses) :

    - ``jours_disponibles`` : durée de la période (jours) ;
    - ``jours_loues`` : Σ des jours occupés par des ordres NON annulés,
      BORNÉE à la période (un ordre chevauchant partiellement ne compte que
      sa portion dans la fenêtre — jamais au-delà) ;
    - ``taux_utilisation`` : ``jours_loues / jours_disponibles`` (0..1) ;
    - ``revenu_locatif`` : Σ ``montant_estime`` des ordres NON annulés dont la
      fenêtre chevauche la période ;
    - ``dormant`` : ``True`` si ``jours_loues == 0`` sur la période (aucune
      location sur N jours).

    ``payback`` (revenu locatif cumulé ÷ ``prix_achat`` du produit) n'est
    inclus QUE si ``admin=True`` (ADMIN-ONLY — ``prix_achat`` ne doit JAMAIS
    apparaître pour un autre rôle ni dans un PDF/export client-facing).
    Lecture seule, scopée société.
    """
    from decimal import Decimal

    from .models import OrdreLocation

    nb_jours_periode = (periode_fin - periode_debut).days + 1
    if nb_jours_periode <= 0:
        return []

    ordres = (
        OrdreLocation.objects
        .filter(
            company=company,
            date_enlevement_prevue__lte=periode_fin,
            date_retour_prevue__gte=periode_debut,
        )
        .exclude(statut=OrdreLocation.Statut.ANNULEE)
        .select_related('produit')
    )

    par_produit = {}
    for ordre in ordres:
        entry = par_produit.setdefault(ordre.produit_id, {
            'produit_id': ordre.produit_id,
            'produit_nom': ordre.produit.nom,
            'prix_achat': ordre.produit.prix_achat,
            'jours_loues': 0,
            'revenu_locatif': Decimal('0'),
        })
        entry['jours_loues'] += _jours_loues_dans_periode(
            ordre, periode_debut, periode_fin)
        entry['revenu_locatif'] += (ordre.montant_estime or Decimal('0'))

    rows = []
    for entry in par_produit.values():
        taux = Decimal(entry['jours_loues']) / Decimal(nb_jours_periode)
        row = {
            'produit_id': entry['produit_id'],
            'produit_nom': entry['produit_nom'],
            'jours_disponibles': nb_jours_periode,
            'jours_loues': entry['jours_loues'],
            'taux_utilisation': taux,
            'revenu_locatif': entry['revenu_locatif'],
            'dormant': entry['jours_loues'] == 0,
        }
        if admin:
            prix_achat = entry['prix_achat'] or Decimal('0')
            row['prix_achat'] = prix_achat
            row['payback'] = (
                (entry['revenu_locatif'] / prix_achat)
                if prix_achat > 0 else None)
        rows.append(row)

    rows.sort(key=lambda r: r['produit_nom'])
    return rows


# ---------------------------------------------------------------------------
# YSUBS5 — Résiliation : résolution du ContratMaintenance SAV lié
# ---------------------------------------------------------------------------


def contrat_maintenance_lie_id(company, contrat_id):
    """ID du ``sav.ContratMaintenance`` lié à un ``Contrat``, ou ``None`` —
    YSUBS5. Point d'entrée LECTURE SEULE pour les apps consommatrices (ex.
    ``apps.sav.receivers`` sur l'événement ``contrat_resilie``) : jamais un
    import du modèle ``Contrat`` en dehors de ``contrats``.

    Résolution dans l'ORDRE : (1) ``Contrat.sav_contrat_maintenance_id``
    (lien direct, le plus courant) ; (2) à défaut, un ``ContratLien`` de
    type ``maintenance`` pour ce contrat (premier trouvé). ``None`` si le
    contrat n'existe pas dans la société ou n'a aucun lien maintenance."""
    from .models import Contrat, ContratLien

    contrat = Contrat.objects.filter(id=contrat_id, company=company).first()
    if contrat is None:
        return None
    if contrat.sav_contrat_maintenance_id:
        return contrat.sav_contrat_maintenance_id

    lien = (
        ContratLien.objects
        .filter(
            company=company, contrat=contrat,
            type_cible=ContratLien.TypeCible.MAINTENANCE,
        )
        .order_by('id')
        .first()
    )
    return lien.cible_id if lien is not None else None


# ---------------------------------------------------------------------------
# ZCTR1 — Plan de facturation récurrente réutilisable (RecurringPlan config)
# ---------------------------------------------------------------------------


def plans_recurrents_actifs(company):
    """Plans de facturation récurrente ACTIFS d'une société, scopés — ZCTR1."""
    from .models import PlanRecurrent

    return PlanRecurrent.objects.filter(company=company, actif=True)


def mois_par_cycle_contrat(contrat):
    """Nombre de mois d'un cycle de facturation pour un contrat — ZCTR1.

    Lit ``Contrat.plan_recurrent.mois_par_cycle()`` quand un plan ACTIF est
    rattaché ; sinon retombe sur le pas de périodicité de son
    ``EcheancierContrat`` le plus récent (même table que YSUBS8) ; ``None`` si
    ni l'un ni l'autre n'est déterminable (comportement actuel inchangé —
    aucune décision prise à la place de l'appelant)."""
    if contrat.plan_recurrent_id and contrat.plan_recurrent.actif:
        return contrat.plan_recurrent.mois_par_cycle()

    echeancier = contrat.echeanciers.order_by('-id').first()
    if echeancier is None:
        return None

    mois_par_periodicite = {
        'mensuelle': 1, 'trimestrielle': 3, 'semestrielle': 6, 'annuelle': 12,
    }
    return mois_par_periodicite.get(echeancier.periodicite)


def contrat_chatter_envelope(contrat):
    """ARC9 — timeline chatter du contrat dans l'ENVELOPPE UNIFORME.

    Projette ``contrats.ContratActivity`` vers le format commun consommé par
    ``records.serializers.UniformChatterSerializer``. Les noms de champs maison
    diffèrent des autres apps : on NORMALISE ici (``type``→``kind`` avec
    ``log``→``modification``, ``message``→``body``, ``auteur``→
    ``user_username``, ``date_creation``→``created_at``) — le frontend (VX23
    ChatterTimeline) ne voit qu'UN format. Lecture seule, aucune table
    modifiée. Le contrat est déjà borné société par l'appelant.
    """
    rows = contrat.activites.select_related('auteur').all()
    return [{
        'id': a.id,
        # Vocabulaire uniforme : une entrée d'audit (« log ») est une
        # modification au sens du chatter commun.
        'kind': ('modification' if a.type == ContratActivity.Kind.LOG
                 else a.type),
        'field': a.field or '',
        # ContratActivity n'a pas de libellé de champ dédié : on retombe sur
        # le nom technique (jamais None — enveloppe uniforme).
        'field_label': a.field or '',
        'old_value': a.old_value or '',
        'new_value': a.new_value or '',
        'body': a.message or '',
        'user_username': a.auteur.username if a.auteur_id else None,
        'created_at': a.date_creation,
        'source': 'contrats.contratactivity',
    } for a in rows]
