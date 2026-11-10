"""ASOC66 (C-ASOC-064) — fournisseur DSR (loi 09-08) du journal WhatsApp.

``WhatsAppMessageLog`` garde le NUMÉRO et le CORPS de chaque message envoyé à
une personne (« Bonjour <nom>, … ») : sans fournisseur, ``core.dsr.exporter``
ne les listait pas et ``core.dsr.effacer`` les laissait intacts.

* **export** — les messages dont le destinataire, normalisé
  (``crm.selectors.normalize_phone_key``), est un numéro de la personne :
  l'identifiant lui-même s'il est un téléphone, et les numéros de ses leads /
  clients résolus par ``crm.selectors`` (jamais ``apps.crm.models``) ;
* **effacement** — ``recipient`` et ``body`` vidés, date et statut gardés.

``erase_order = 50`` : la résolution passe par l'identité du CRM
(``erase_order = 100``), qui doit encore exister.
"""
from __future__ import annotations

PROVIDER_NAME = 'notifications'


def _cles_du_sujet(company, subject_identifier):
    from apps.crm.selectors import (
        client_ids_par_identifiant, lead_ids_par_identifiant, normalize_phone_key,
        telephones_cibles_activites)

    numeros = telephones_cibles_activites(
        company, lead_ids_par_identifiant(company, subject_identifier),
        client_ids_par_identifiant(company, subject_identifier)).values()
    sujet = '' if '@' in str(subject_identifier or '') else subject_identifier  # un e-mail n'est pas un numéro
    cles = {normalize_phone_key(n) for n in (sujet, *numeros)}
    cles.discard('')
    return cles


def messages_du_sujet(company, subject_identifier):
    """Les ``WhatsAppMessageLog`` de la société adressés à la personne."""
    from django.db.models import Q

    from apps.crm.selectors import normalize_phone_key

    from .models import WhatsAppMessageLog

    cles = _cles_du_sujet(company, subject_identifier) if company is not None else set()
    if not cles:
        return []
    filtre = Q()
    for cle in cles:
        filtre |= Q(recipient__endswith=cle)
    return [m for m in WhatsAppMessageLog.objects.filter(company=company).filter(filtre)
            .order_by('created_at', 'id') if normalize_phone_key(m.recipient) in cles]


def export_notifications(company, subject_identifier):
    return {'whatsapp': [
        {'date': m.created_at.isoformat(), 'statut': m.status, 'corps': m.body}
        for m in messages_du_sujet(company, subject_identifier)]}


def erase_notifications(company, subject_identifier):
    """Caviarde numéro et corps ; rend le nombre de lignes traitées."""
    from .models import WhatsAppMessageLog

    ids = [m.pk for m in messages_du_sujet(company, subject_identifier)]
    return WhatsAppMessageLog.objects.filter(pk__in=ids).update(recipient='', body='')


#: ASOC102 — nom de la politique au registre de rétention partagé (``core.retention``).
RETENTION_POLICY_WHATSAPP = 'notifications_whatsapp_journal'


def sweep_retention_whatsapp(now, apply_=False):
    """ASOC102 — caviarde (numéro et corps vidés, date et statut gardés) les messages
    journalisés au-delà de la durée DÉCLARÉE au registre (crm, « 3 ans après le
    dernier contact ») ; dry-run : le compte seul. Rend le nombre de lignes."""
    import datetime

    from apps.crm.dsr_provider import DUREE_CONSERVATION_PROSPECTS_JOURS

    from .models import WhatsAppMessageLog

    limite = now - datetime.timedelta(days=DUREE_CONSERVATION_PROSPECTS_JOURS)
    lignes = WhatsAppMessageLog.objects.filter(created_at__lt=limite).exclude(recipient='', body='')
    return lignes.update(recipient='', body='') if apply_ else lignes.count()


def register():
    """Enregistre le fournisseur DSR (idempotent). Appelé en ``ready()``."""
    from core import dsr

    dsr.register_dsr_provider(PROVIDER_NAME, export=export_notifications,
                              erase=erase_notifications, erase_order=50)
