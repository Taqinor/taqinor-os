"""XPLT23 — fournisseur DSR (loi 09-08) du CRM.

Enregistré auprès du registre générique ``core.dsr`` (frontière déjà en place :
``core`` orchestre sans importer le CRM ; le CRM lit ses PROPRES modèles). Deux
opérations :

* **export** — renvoie les données CRM (leads + clients) de la personne
  concernée, identifiée par email OU téléphone normalisé ;
* **effacement** — ANONYMISE (n'efface pas) : nom générique, contacts vidés,
  drapeau ``is_anonymized`` posé. Les activités/historique et l'intégrité
  comptable (devis/factures) sont CONSERVÉS.

``subject_identifier`` = un email ou un téléphone. Tout est borné par
``company`` (multi-tenant).
"""
from __future__ import annotations

from django.db.models import Q
from django.utils import timezone

PROVIDER_NAME = 'crm'


def _matcher(company, subject_identifier):
    """Renvoie (leads_qs, clients_qs) correspondant à ``subject_identifier``.

    Match sur email exact (insensible à la casse) OU téléphone/WhatsApp
    normalisé. Toujours borné par ``company``.
    """
    from .models import Client, Lead
    from .services import normalize_email, normalize_phone

    email = normalize_email(subject_identifier)
    phone = normalize_phone(subject_identifier)

    leads = Lead.objects.filter(company=company)
    clients = Client.objects.filter(company=company)

    if email:
        lead_q = Q(email__iexact=email)
        client_q = Q(email__iexact=email)
    else:
        lead_q = Q(pk__in=[])
        client_q = Q(pk__in=[])

    if phone:
        # Filtrer côté Python sur le téléphone normalisé (les valeurs stockées
        # ne sont pas normalisées) ; l'email reste filtré en base.
        lead_ids = [
            le.pk for le in Lead.objects.filter(company=company)
            if normalize_phone(le.telephone) == phone
            or normalize_phone(le.whatsapp) == phone
        ]
        client_ids = [
            cl.pk for cl in Client.objects.filter(company=company)
            if normalize_phone(cl.telephone) == phone
        ]
        lead_q |= Q(pk__in=lead_ids)
        client_q |= Q(pk__in=client_ids)

    return leads.filter(lead_q), clients.filter(client_q)


def export_crm(company, subject_identifier):
    """Export des données CRM de la personne (leads + clients)."""
    leads, clients = _matcher(company, subject_identifier)
    return {
        'leads': [
            {
                'id': le.pk,
                'nom': le.nom,
                'prenom': le.prenom,
                'email': le.email,
                'telephone': le.telephone,
                'whatsapp': le.whatsapp,
                'ville': le.ville,
                'stage': le.stage,
                'source': le.source,
                'cree_le': le.date_creation.isoformat()
                if getattr(le, 'date_creation', None) else None,
            }
            for le in leads
        ],
        'clients': [
            {
                'id': cl.pk,
                'nom': cl.nom,
                'prenom': cl.prenom,
                'email': cl.email,
                'telephone': cl.telephone,
                'adresse': cl.adresse,
                'is_anonymized': cl.is_anonymized,
            }
            for cl in clients
        ],
    }


def erase_crm(company, subject_identifier):
    """Anonymise leads + clients de la personne (activités conservées).

    Renvoie le nombre d'enregistrements anonymisés. N'efface JAMAIS les lignes
    (intégrité devis/factures/activités) : vide les PII et pose le drapeau.
    """
    leads, clients = _matcher(company, subject_identifier)
    now = timezone.now()
    count = 0

    for le in leads:
        le.nom = 'Anonymisé'
        le.prenom = None
        le.email = None
        le.telephone = None
        le.whatsapp = None
        le.adresse = None
        le.save(update_fields=[
            'nom', 'prenom', 'email', 'telephone', 'whatsapp', 'adresse'])
        count += 1

    for cl in clients:
        cl.nom = 'Anonymisé'
        cl.prenom = None
        cl.email = None
        cl.telephone = None
        cl.adresse = None
        cl.is_anonymized = True
        cl.anonymized_at = now
        cl.save(update_fields=[
            'nom', 'prenom', 'email', 'telephone', 'adresse',
            'is_anonymized', 'anonymized_at'])
        count += 1

    return count


def register():
    """Enregistre le fournisseur DSR CRM (idempotent). Appelé en ready()."""
    from core import dsr
    dsr.register_dsr_provider(
        PROVIDER_NAME, export=export_crm, erase=erase_crm)
