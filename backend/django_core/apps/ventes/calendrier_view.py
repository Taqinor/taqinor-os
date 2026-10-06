"""FG273 — Calendrier réglementaire & alertes d'expiration de dossiers.

Agrégation LECTURE SEULE, scopée société. Rassemble les échéances réglementaires
issues des dossiers de raccordement (FG268-269) :

  * pièces de checklist datées (``DossierChecklistItem.date_echeance``) —
    date limite de dépôt / fourniture d'une pièce ;
  * dossiers déposés en attente de décision (``RegulatoryDossier.date_depot``) ;
  * CIQ619 — délais MAXIMAUX du décret 2.25.100 : paiement de l'étude
    (notification + 10 jours, art. 13) et limite des travaux (convention +
    2 ans pour un accord, art. 14 ; récépissé + 12 mois pour une
    déclaration, art. 8). Plus de validité d'accord supposée à 365 jours :
    ``?validite=<jours>`` reste une SURCHARGE explicite (date de décision +
    fenêtre) ;
  * CHT25 — prochaine action EXPLICITE posée par l'utilisateur sur le dossier
    (``RegulatoryDossier.prochaine_action``/``prochaine_action_date``), en
    PLUS des règles déduites ci-dessus — jamais un remplacement.

Chaque échéance porte un statut d'alerte calculé par rapport à aujourd'hui :
``expire`` (passée), ``imminent`` (≤ seuil de jours), ``a_venir`` (au-delà). Ne
change aucun statut de devis ; jamais de prix.
"""
from datetime import timedelta

from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from authentication.permissions import IsAnyRole
from .models import RegulatoryDossier, DossierChecklistItem

# Seuil par défaut « imminent » (jours).
DEFAULT_SEUIL_IMMINENT_JOURS = 30


def _echeances_decret(dossier, today, seuil):
    """CIQ619 — échéances DÉRIVÉES du décret 2.25.100 d'un dossier."""
    from .selectors_reglementaire import (
        DELAI_PAIEMENT_ETUDE_SOURCE, DELAI_TRAVAUX_ACCORD_SOURCE,
        DELAI_TRAVAUX_DECLARATION_SOURCE, paiement_etude_limite,
        travaux_limite)
    lignes = []
    paiement = paiement_etude_limite(dossier)
    if paiement and not dossier.etude_payee_le:
        lignes.append(('paiement_etude', paiement,
                       f"Paiement de l'étude du distributeur "
                       f"({DELAI_PAIEMENT_ETUDE_SOURCE}) — devis "
                       f"{dossier.devis_id}"))
    travaux = travaux_limite(dossier)
    if travaux and not dossier.demande_exploitation_le:
        source = (DELAI_TRAVAUX_DECLARATION_SOURCE
                  if dossier.regime_8221 == 'declaration_bt'
                  else DELAI_TRAVAUX_ACCORD_SOURCE)
        lignes.append(('travaux_limite', travaux,
                       f"Limite des travaux ({source}) — devis "
                       f"{dossier.devis_id}"))
    sortie = []
    for type_, date_limite, libelle in lignes:
        statut, jours = _alerte(date_limite, today, seuil)
        sortie.append({
            'type': type_,
            'sous_type': dossier.regime_8221,
            'dossier_id': dossier.id,
            'libelle': libelle,
            'date_echeance': date_limite.isoformat(),
            'statut_alerte': statut,
            'jours_restants': jours,
            'relance_due': False,
        })
    return sortie


def _alerte(date_echeance, today, seuil_jours):
    """Statut d'alerte d'une échéance : expire / imminent / a_venir."""
    if date_echeance is None:
        return 'sans_echeance', None
    delta = (date_echeance - today).days
    if delta < 0:
        return 'expire', delta
    if delta <= seuil_jours:
        return 'imminent', delta
    return 'a_venir', delta


@api_view(['GET'])
@permission_classes([IsAnyRole])
def calendrier_reglementaire(request):
    """GET /ventes/calendrier-reglementaire/

    ``?seuil=<jours>`` règle la fenêtre « imminent » (défaut 30).
    ``?validite=<jours>`` : surcharge EXPLICITE de la validité d'accord
    (sinon : délais du décret 2.25.100, CIQ619).
    ``?statut=expire|imminent|a_venir`` filtre les lignes renvoyées.

    Renvoie ``{echeances: [...], resume: {expire, imminent, a_venir}}`` trié par
    date d'échéance croissante. Lecture seule, scopé société.
    """
    user = request.user
    today = timezone.now().date()

    try:
        seuil = int(request.query_params.get(
            'seuil', DEFAULT_SEUIL_IMMINENT_JOURS))
    except (TypeError, ValueError):
        seuil = DEFAULT_SEUIL_IMMINENT_JOURS
    if seuil < 0:
        seuil = DEFAULT_SEUIL_IMMINENT_JOURS
    # CIQ619 — aucune validité par défaut : sans surcharge, les délais du
    # décret s'appliquent.
    try:
        validite = int(request.query_params.get('validite'))
    except (TypeError, ValueError):
        validite = None
    if validite is not None and validite < 0:
        validite = None

    def _scope(qs):
        if getattr(user, 'company_id', None):
            return qs.filter(company=user.company)
        if user.is_superuser:
            return qs
        return qs.none()

    echeances = []

    # 1) Pièces de checklist datées (date limite de dépôt / fourniture).
    items = _scope(
        DossierChecklistItem.objects.select_related('dossier')).exclude(
        date_echeance__isnull=True).exclude(
        statut__in=['valide', 'fourni', 'na'])
    for item in items:
        statut, jours = _alerte(item.date_echeance, today, seuil)
        echeances.append({
            'type': 'piece',
            'sous_type': item.etape,
            'dossier_id': item.dossier_id,
            'libelle': item.libelle,
            'date_echeance': item.date_echeance.isoformat(),
            'statut_alerte': statut,
            'jours_restants': jours,
            'relance_due': item.relance_due,
        })

    # 2) Dossiers : décision en attente (depuis dépôt) + validité d'accord.
    dossiers = _scope(RegulatoryDossier.objects.select_related('devis'))
    for d in dossiers:
        # Dépôt en attente de décision.
        if d.date_depot and not d.date_decision and d.statut in (
                'depose', 'en_instruction', 'complement_demande'):
            statut, jours = _alerte(d.date_depot, today, seuil)
            echeances.append({
                'type': 'depot',
                'sous_type': d.regime_8221,
                'dossier_id': d.id,
                'libelle': f'Dépôt en instruction — devis {d.devis_id}',
                'date_echeance': d.date_depot.isoformat(),
                'statut_alerte': statut,
                'jours_restants': jours,
                'relance_due': False,
            })
        # CIQ619 — délais maximaux du décret 2.25.100.
        echeances.extend(_echeances_decret(d, today, seuil))
        # Surcharge explicite ``?validite=`` → date limite de mise en service.
        if (validite is not None and d.date_decision
                and d.statut in ('approuve', 'comptage_pose')):
            limite_mes = d.date_decision + timedelta(days=validite)
            statut, jours = _alerte(limite_mes, today, seuil)
            echeances.append({
                'type': 'validite_accord',
                'sous_type': d.regime_8221,
                'dossier_id': d.id,
                'libelle': (f"Date limite MES (validité accord) — "
                            f"devis {d.devis_id}"),
                'date_echeance': limite_mes.isoformat(),
                'statut_alerte': statut,
                'jours_restants': jours,
                'relance_due': False,
            })
        # CHT25 — prochaine action explicite : indépendante du statut du
        # dossier (l'utilisateur peut vouloir relancer même un dossier
        # approuvé), toujours en PLUS des deux règles déduites ci-dessus.
        if d.prochaine_action_date:
            statut, jours = _alerte(d.prochaine_action_date, today, seuil)
            echeances.append({
                'type': 'prochaine_action',
                'sous_type': d.regime_8221,
                'dossier_id': d.id,
                'libelle': d.prochaine_action or (
                    f'Prochaine action — devis {d.devis_id}'),
                'date_echeance': d.prochaine_action_date.isoformat(),
                'statut_alerte': statut,
                'jours_restants': jours,
                'relance_due': False,
            })

    # Filtre statut optionnel.
    filtre = request.query_params.get('statut')
    if filtre:
        echeances = [e for e in echeances if e['statut_alerte'] == filtre]

    echeances.sort(key=lambda e: e['date_echeance'])

    resume = {'expire': 0, 'imminent': 0, 'a_venir': 0, 'sans_echeance': 0}
    for e in echeances:
        resume[e['statut_alerte']] = resume.get(e['statut_alerte'], 0) + 1

    return Response({
        'today': today.isoformat(),
        'seuil_imminent_jours': seuil,
        'validite_accord_jours': validite,
        'echeances': echeances,
        'resume': resume,
    })
