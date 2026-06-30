"""FG273 — Calendrier réglementaire & alertes d'expiration de dossiers.

Agrégation LECTURE SEULE, scopée société. Rassemble les échéances réglementaires
issues des dossiers de raccordement (FG268-269) :

  * pièces de checklist datées (``DossierChecklistItem.date_echeance``) —
    date limite de dépôt / fourniture d'une pièce ;
  * dossiers déposés en attente de décision (``RegulatoryDossier.date_depot``) ;
  * validité d'un accord (``RegulatoryDossier.date_decision`` + fenêtre de
    validité paramétrable, défaut 12 mois) — date limite de mise en service.

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

# Fenêtre de validité par défaut d'un accord de raccordement (jours).
DEFAULT_VALIDITE_ACCORD_JOURS = 365
# Seuil par défaut « imminent » (jours).
DEFAULT_SEUIL_IMMINENT_JOURS = 30


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
    ``?validite=<jours>`` règle la validité d'accord (défaut 365).
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
    try:
        validite = int(request.query_params.get(
            'validite', DEFAULT_VALIDITE_ACCORD_JOURS))
    except (TypeError, ValueError):
        validite = DEFAULT_VALIDITE_ACCORD_JOURS
    if validite < 0:
        validite = DEFAULT_VALIDITE_ACCORD_JOURS

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
        # Validité d'accord → date limite de mise en service.
        if d.date_decision and d.statut in ('approuve', 'comptage_pose'):
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
