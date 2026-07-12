"""XPLT21 — Orchestration (écritures) du softphone VoIP.

Cross-app : la résolution numéro → lead/client passe EXCLUSIVEMENT par les
points d'entrée cross-app déjà sanctionnés de `apps.crm`
(`selectors.find_client_by_phone`, `services.find_lead_by_phone` — le MÊME
motif que le webhook BSP WhatsApp, `apps.notifications.views_whatsapp_bsp`),
jamais un import de `apps.crm.models`. Le journal automatique écrit dans
`apps.records` (app de FONDATION, import direct autorisé — voir CLAUDE.md).
"""
import logging

from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from apps.ventes.utils.phone import normalize_ma_phone

from . import providers
from .models import Appel, VoipParametres

logger = logging.getLogger(__name__)


def get_or_create_parametres(company):
    """Ligne `VoipParametres` de `company` — créée inerte (noop/actif=False)
    à la première consultation, comportement historique préservé."""
    parametres, _ = VoipParametres.objects.get_or_create(company=company)
    return parametres


def est_actif(company):
    """True si le softphone est UTILISABLE pour cette société (configuré ET
    actif) — sinon aucun appel n'est possible (sans config rien ne change)."""
    return get_or_create_parametres(company).est_configure


def _resolve_cible(company, numero):
    """Résout `numero` vers un (ContentType, object_id) de client OU lead,
    via les sélecteurs cross-app sanctionnés de `apps.crm` (client en
    priorité, puis lead). Best-effort : ne lève JAMAIS — un numéro qui ne
    matche rien renvoie (None, None), comme le webhook WhatsApp."""
    if not numero:
        return None, None
    try:
        from apps.crm.selectors import find_client_by_phone
        from apps.crm.services import find_lead_by_phone

        client = find_client_by_phone(company, numero)
        if client is not None:
            return ContentType.objects.get_for_model(client.__class__), client.id
        lead = find_lead_by_phone(company, numero)
        if lead is not None:
            return ContentType.objects.get_for_model(lead.__class__), lead.id
    except Exception:  # pragma: no cover - défensif, jamais bloquant
        logger.warning(
            'voip._resolve_cible a échoué pour %s (no-op).',
            company, exc_info=True)
    return None, None


def demarrer_appel_sortant(company, user, numero):
    """XPLT21 — Amorce un appel SORTANT et journalise l'`Appel`.

    Renvoie None (no-op) si le softphone n'est pas configuré/actif pour cette
    société — sans config rien ne change. Résout automatiquement le lead/
    client correspondant au numéro pour le rattachement chatter à la clôture.
    """
    parametres = get_or_create_parametres(company)
    if not parametres.est_configure:
        return None
    content_type, object_id = _resolve_cible(company, numero)
    provider = providers.get_provider(parametres.fournisseur)
    result = provider.start_outbound_call(numero, parametres) or {}
    return Appel.objects.create(
        company=company,
        direction=Appel.Direction.SORTANT,
        numero=numero,
        numero_normalise=normalize_ma_phone(numero) or '',
        content_type=content_type,
        object_id=object_id,
        utilisateur=user,
        statut=result.get('statut') or Appel.Statut.INITIE,
        fournisseur=parametres.fournisseur,
        external_call_id=result.get('external_call_id') or '',
    )


def recevoir_appel_entrant(company, numero, *, external_call_id=''):
    """XPLT21 — Enregistre un appel ENTRANT (webhook/notification fournisseur)
    et résout la fiche à ouvrir (« call-pop »).

    Renvoie None (no-op) si le softphone n'est pas configuré/actif — sans
    config rien ne change, aucun appel entrant n'est traité.
    """
    parametres = get_or_create_parametres(company)
    if not parametres.est_configure:
        return None
    content_type, object_id = _resolve_cible(company, numero)
    return Appel.objects.create(
        company=company,
        direction=Appel.Direction.ENTRANT,
        numero=numero,
        numero_normalise=normalize_ma_phone(numero) or '',
        content_type=content_type,
        object_id=object_id,
        statut=Appel.Statut.SONNANT,
        fournisseur=parametres.fournisseur,
        external_call_id=external_call_id or '',
    )


def _format_duree(duree_secondes):
    if not duree_secondes:
        return '0 s'
    minutes, secondes = divmod(int(duree_secondes), 60)
    if minutes:
        return f'{minutes} min {secondes:02d} s'
    return f'{secondes} s'


def _log_chatter(appel):
    """Journalise l'appel terminé sur le chatter de sa cible résolue
    (`apps.records.Activity`, app de FONDATION — import direct autorisé).
    No-op si aucune cible n'a été résolue (numéro sans correspondance)."""
    if not appel.content_type_id or not appel.object_id:
        return
    from apps.records.models import Activity, ActivityType

    atype, _ = ActivityType.objects.get_or_create(
        company=appel.company, nom='Appel',
        defaults={'icone': '📞', 'ordre': 10, 'est_systeme': True})
    direction_label = (
        'Appel sortant' if appel.direction == Appel.Direction.SORTANT
        else 'Appel entrant')
    summary = f'{direction_label} — {appel.numero} — {_format_duree(appel.duree_secondes)}'
    note = f'Issue : {appel.issue or "non renseignée"}.'
    Activity.objects.create(
        company=appel.company,
        content_type=appel.content_type,
        object_id=appel.object_id,
        activity_type=atype,
        summary=summary[:255],
        note=note,
        assigned_to=appel.utilisateur,
        done=True,
        done_at=appel.ended_at or timezone.now(),
        done_by=appel.utilisateur,
        created_by=appel.utilisateur,
    )


def terminer_appel(appel, *, duree_secondes=0, issue=''):
    """XPLT21 — Clôture un `Appel` : pose durée/issue, journalise le chatter
    de sa cible résolue (lead/client). Idempotent au sens métier — un appel
    déjà terminé peut être re-clôturé (met simplement à jour), mais chaque
    clôture écrit une nouvelle entrée de chatter (une par appel, comme une
    vraie fiche de journal d'appels)."""
    appel.ended_at = timezone.now()
    appel.duree_secondes = max(0, int(duree_secondes or 0))
    appel.issue = issue or ''
    appel.statut = Appel.Statut.TERMINE
    appel.save(update_fields=['ended_at', 'duree_secondes', 'issue', 'statut'])
    try:
        _log_chatter(appel)
    except Exception:  # pragma: no cover - défensif, jamais bloquant
        logger.warning(
            "voip.terminer_appel: journalisation chatter échouée "
            "pour l'appel %s.", appel.id, exc_info=True)
    return appel
