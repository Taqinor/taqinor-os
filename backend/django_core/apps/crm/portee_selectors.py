"""Portée et signature des leads (feuille de la scission de `selectors.py`, SPL309).

Contact autorisé, portée/visibilité des leads, prédicat « lead signé », clés de
numéros, responsable, identifiants anonymisés. Module FEUILLE : n'importe ni
`.selectors` ni aucun module frère. Déplacement pur ; `apps.crm.selectors`
ré-exporte chaque nom (frontière inter-apps).
"""


#: ACRM17 — le motif FR d'un envoi refusé à une personne opposée (loi 09-08).
MOTIF_CONTACT_REFUSE = ('Contact refusé : la personne a demandé à ne plus '
                        'être contactée')


def peut_contacter(instance, canal=None):
    """ACRM17 (C-ACRM-010) — peut-on CONTACTER la personne derrière
    ``instance`` par ``canal`` (e-mail, WhatsApp…) ?

    Faux quand ``instance`` est un ``crm.Lead`` — ou porte un ``lead`` —
    marqué ``ne_plus_contacter`` : aucun émetteur automatique (règles
    d'automatisation, réveils, envois en masse) ne lui écrit. Vrai sinon (une
    instance sans lead n'est pas concernée par ce drapeau). ``canal`` est
    accepté pour l'avenir (consentement par canal, ACRM59) ; le drapeau
    actuel couvre TOUS les canaux. Lecture pure."""
    from .models import Lead

    lead = instance if isinstance(instance, Lead) else getattr(
        instance, 'lead', None)
    if not isinstance(lead, Lead):
        return True
    return not getattr(lead, 'ne_plus_contacter', False)


def portee_leads(qs, user):
    """ACRM28 — restreint un queryset de LEADS à ce que ``user`` voit :
    portée de visibilité du rôle (``scope_queryset`` sur ``owner`` —
    Feature F) ET périmètre d'entités (``scope_entite_queryset``, NTADM3).
    Un rôle sans entités visibles → seule la portée propriétaire, comme
    avant."""
    from authentication.scoping import scope_queryset
    from core.entite_scoping import scope_entite_queryset

    return scope_entite_queryset(
        scope_queryset(qs, user, ['owner']), user, 'entite')


def leads_visibles(user, company=None):
    """ACRM28 — LES leads visibles de ``user`` : société (``company``, ou
    la société active par ``company_qs``), portée propriétaire et périmètre
    d'entités (``portee_leads``). Une seule définition, lue par toutes les
    files (relances, cockpit, « Ma file », clôture des cadences) et par les
    viewsets enfants d'un lead (ACRM8 — ``leads_en_portee`` en est l'alias) :
    un lead qui répond 404 à l'utilisateur n'apparaît nulle part."""
    from core.mixins import company_qs

    from .models import Lead

    qs = (Lead.objects.filter(company=company) if company is not None
          else company_qs(Lead.objects.all(), user))
    return portee_leads(qs, user)


def leads_en_portee(user):
    """ACRM8 — alias de ``leads_visibles`` (ACRM28) : la portée des
    viewsets ENFANTS d'un lead (rendez-vous, concurrents, points de contact,
    forecast, deals, playbook, aperçu de gabarit). Un lead hors portée y est
    traité comme ABSENT."""
    return leads_visibles(user)


def lead_signe_q():
    """ACRM31 — LE prédicat « lead signé » (filtre ORM) : étape SIGNED
    (clé lue de ``stages``/STAGES.py, jamais un littéral — règle #2), non
    perdu, non archivé. Toute lecture qui compte des « signés » passe par lui
    (ou par ``est_lead_signe`` pour un objet déjà chargé) afin que tous les
    rapports comptent pareil sur le même jeu."""
    from django.db.models import Q
    from . import stages as stage_mod
    return Q(stage=stage_mod.SIGNED, perdu=False, is_archived=False)


def est_lead_signe(lead):
    """ACRM31 — Jumeau Python de ``lead_signe_q`` pour un lead déjà chargé."""
    from . import stages as stage_mod
    return (getattr(lead, 'stage', None) == stage_mod.SIGNED
            and not getattr(lead, 'perdu', False)
            and not getattr(lead, 'is_archived', False))


def cles_numeros_lead(lead):
    """ACRM33 — Clés téléphone NORMALISÉES (QW10) d'un lead : son
    ``telephone`` ET son ``whatsapp`` (vides ignorés). Helper unique partagé
    par ``find_lead_id_by_phone`` et ``signed_lead_phone_keys`` — un lead
    joignable seulement sur WhatsApp est reconnu partout pareil."""
    from . import leads_doublons
    keys = set()
    for numero in (getattr(lead, 'telephone', None),
                   getattr(lead, 'whatsapp', None)):
        key = leads_doublons.normalize_phone(numero)
        if key:
            keys.add(key)
    return keys


def lead_ids_du_responsable(user):
    """Sous-requête des ids de leads dont ``user`` est le RESPONSABLE
    (``Lead.owner``), bornée à SA société. Lecture seule, cross-app : ventes
    l'utilise pour que le responsable d'un lead voie TOUS les devis de ce lead,
    quel qu'en soit l'auteur (règle fondateur 08/10/2026)."""
    from .models import Lead
    return Lead.objects.filter(
        company_id=user.company_id, owner_id=user.pk).values('pk')


def lead_ids_anonymises(company):
    """ACAL300 — ids des leads DÉJÀ anonymisés (DSR ou rétention) de la
    société : le scrub de ``crm.dsr_provider.anonymiser_lead`` pose
    ``LEAD_NOM_ANONYMISE`` et vide email / téléphone. Lecture bornée société,
    sans PII ; pour le rattrapage des calepinages (``manage.py
    anonymiser_calepinages_effaces``)."""
    from .dsr_provider import LEAD_NOM_ANONYMISE
    from .models import Lead

    if company is None:
        return []
    return sorted(Lead.objects.filter(
        company=company, nom=LEAD_NOM_ANONYMISE, email__isnull=True,
        telephone__isnull=True).values_list('id', flat=True))


def client_ids_anonymises(company):
    """ACAL300 — ids des clients anonymisés (``is_anonymized``) de la
    société, bornés société, sans PII."""
    from .models import Client

    if company is None:
        return []
    return sorted(Client.objects.filter(
        company=company, is_anonymized=True).values_list('id', flat=True))
