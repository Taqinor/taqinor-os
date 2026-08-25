"""XPLT23 — fournisseur DSR (loi 09-08) du CRM.

Enregistré auprès du registre générique ``core.dsr`` (frontière déjà en place :
``core`` orchestre sans importer le CRM ; le CRM lit ses PROPRES modèles). Deux
opérations :

* **export** — renvoie les données CRM (leads + clients) de la personne
  concernée, identifiée par email OU téléphone normalisé ;
* **effacement** — ANONYMISE (n'efface pas) : nom générique, contacts vidés,
  drapeau ``is_anonymized`` posé. Les activités/historique et l'intégrité
  comptable (devis/factures) sont CONSERVÉS. Les identifiants de TRAÇAGE
  partent aussi (``Lead.appareil_id`` et, sur les ``VisiteExterne`` du lead,
  IP / navigateur / appareil / suffixe de jeton) : sans eux, un lead
  « anonymisé » restait ré-identifiable — et une visite ultérieure du même
  navigateur le rattachait à sa fiche effacée.

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


def _anonymiser_traces_visiteur(company, lead):
    """Blanchit les identifiants de traçage rattachés à CE lead (T-TRACE).

    Revue critique du 25/08/2026, finding #13 — L'EFFACEMENT ÉTAIT TROUÉ. Un
    lead « anonymisé » gardait son ``appareil_id`` (l'identifiant PRIMAIRE du
    visiteur, un uuid que le site pose dans le navigateur) et TOUTES ses
    ``VisiteExterne`` avec leur IP, leur navigateur et le même
    ``appareil_id`` : la personne restait parfaitement ré-identifiable, et une
    nouvelle visite du même navigateur la rattachait à sa fiche « effacée ».

    DOCTRINE DU MODULE SUIVIE À LA LETTRE : on anonymise, on ne supprime pas.
    Les lignes de visite SURVIVENT (leur finalité anti-fraude — combien de
    passages, quand, sur quelle page — ne porte plus aucune PII une fois les
    trois identifiants vidés), exactement comme les activités et les documents
    comptables survivent à l'anonymisation d'un lead.

    Le ``token_suffixe`` part avec : c'est un fragment du lien nominatif envoyé
    à cette personne. Best-effort borné à ``company`` (multi-tenant)."""
    from .models import VisiteExterne
    return VisiteExterne.objects.filter(company=company, lead=lead).update(
        ip='', user_agent='', appareil_id='', token_suffixe='')


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
        # Finding #13 — l'identifiant d'appareil est une PII de traçage : sans
        # lui, une visite ultérieure du même navigateur re-rattacherait la
        # personne à sa fiche « effacée » (``visites.rattacher_visites_au_lead``
        # et l'alerte ``alerter_appareil_partage`` s'appuient dessus).
        le.appareil_id = None
        # QW10 — ``Lead.save()`` recalcule ``email_normalise``/``phone_normalise``
        # depuis les PII désormais vidées ; on les inclut dans ``update_fields``
        # pour que les clés de dédup normalisées soient AUSSI purgées (sinon un
        # lead « anonymisé » garderait un email/téléphone normalisé recherchable).
        le.save(update_fields=[
            'nom', 'prenom', 'email', 'telephone', 'whatsapp', 'adresse',
            'appareil_id', 'email_normalise', 'phone_normalise'])
        # Les traces de traçage du lead perdent leurs identifiants (IP,
        # navigateur, appareil, suffixe de jeton) — la ligne reste, la personne
        # n'est plus reconnaissable.
        _anonymiser_traces_visiteur(company, le)
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
