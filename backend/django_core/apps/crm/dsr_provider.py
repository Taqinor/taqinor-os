"""XPLT23 — fournisseur DSR (loi 09-08) du CRM.

Enregistré auprès du registre générique ``core.dsr`` (frontière déjà en place :
``core`` orchestre sans importer le CRM ; le CRM lit ses PROPRES modèles). Deux
opérations :

* **export** — renvoie les données CRM (leads + clients) de la personne
  concernée, identifiée par email OU téléphone normalisé ;
* **effacement** — ANONYMISE (n'efface pas) : nom générique, contacts vidés,
  drapeau ``is_anonymized`` posé. CRX32 — l'ensemble scrubé est désormais
  EXACTEMENT celui de l'action ``ClientViewSet.anonymize`` (FG26) : les
  identifiants fiscaux et administratifs du client (``cin``/``ice``/
  ``if_fiscal``/``rc``) et les champs personnalisés ``custom_data`` du client
  ET du lead partent avec le reste. Les activités/historique et l'intégrité
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

#: Nom porté par un lead anonymisé — écrit par ``anonymiser_lead`` ET lu par
#: le balayage de rétention (CAD92) pour ne jamais repasser sur une fiche
#: déjà scrubée. ``Lead`` n'a pas de drapeau ``is_anonymized`` (contrairement
#: à ``Client``) : c'est ce nom qui fait foi, une seule fois, à un seul
#: endroit.
LEAD_NOM_ANONYMISE = 'Anonymisé'

#: ACRM19 (C-ACRM-012) — ce qui remplace une copie brute d'intake effacée.
PAYLOAD_CAVIARDE = {'caviarde': True,
                    'motif': 'effacement des données personnelles (loi 09-08)'}

#: ACRM19 — TOUT modèle portant une clé vers ``crm.Lead`` est DÉCLARÉ ici :
#: soit TRAITÉ par ``anonymiser_lead`` (ses PII partent avec le lead), soit
#: EXEMPTÉ avec sa raison. Un modèle nouveau qui pointe un lead et n'est
#: déclaré nulle part fait échouer ``tests_acrm_dsr_copies_brutes`` : un
#: effacement ne peut plus oublier une copie en silence.
MODELES_LEAD_TRAITES = {
    'crm.WebsiteLeadPayload': 'payload brut caviardé, IP vidée',
    'crm.ChatSessionPublique': 'transcript vidé',
    'crm.VisiteExterne': 'IP, navigateur, appareil et suffixe de jeton vidés',
    'crm.Parrainage': 'nom du filleul vidé',
    'crm.LeadActivity': "lignes gardées, valeurs d'identité caviardées "
                        '(D-ASOC-3)',
}
MODELES_LEAD_EXEMPTES = {
    'crm.RelanceEtape': 'touches de cadence : libellés et échéances, aucune '
                        'copie de PII',
    'crm.Appointment': 'rendez-vous : date, statut et notes métier ; '
                       "l'identité est portée par le lead anonymisé",
    'crm.BookingLink': 'jeton de réservation sans PII',
    'crm.AttributionEnAttente': "attente d'attribution : équipe, membre "
                                'proposé, raison et échéance, sans PII',
    'crm.QuestionnaireLien': 'jeton de questionnaire sans PII',
    'crm.ConcurrentPerte': 'intelligence concurrentielle sans PII',
    'crm.DealEnregistre': "réservation d'antériorité d'un apporteur, sans PII",
    'crm.ForecastEntry': 'catégorie et montant prévisionnels, sans PII',
    'crm.LeadPlaybookProgress': 'progression de tâches, sans PII',
    'crm.PointContact': "journal d'attribution (canal, source), sans PII",
    'crm.SalleVente': 'espace de vente : documents commerciaux du dossier',
    'ventes.Devis': 'document commercial conservé (intégrité comptable)',
    'ventes.BonCommande': 'document comptable conservé (obligation légale)',
    'facturation.Facture': 'document comptable conservé (obligation légale)',
    'installations.Installation': 'chantier réalisé : obligation de garantie',
    'visites.VisiteTerrain': 'relevé technique du site, rattaché au lead '
                             'anonymisé',
    'portail.DocumentClientPortail': 'document remis au client, conservé',
}


def _matcher(company, subject_identifier):
    """Renvoie (leads_qs, clients_qs) correspondant à ``subject_identifier``.

    Match sur email exact (insensible à la casse) OU téléphone/WhatsApp
    normalisé. Toujours borné par ``company``.
    """
    from .models import Client, Lead
    from .leads_doublons import normalize_email, normalize_phone

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
        # CRX32 — LE TÉLÉPHONE DU LEAD PASSE PAR LA COLONNE INDEXÉE.
        # ``Lead.phone_normalise`` est maintenu à chaque ``save()`` (QW10) et
        # porte un index ``(company, phone_normalise)`` : la recherche devient
        # une requête indexée au lieu d'un scan Python de TOUTE la table des
        # leads de la société (le chemin DSR pouvait donc devenir illisible sur
        # un tenant chargé). L'ancien scan est SUPPRIMÉ, jamais gardé en repli.
        lead_q |= Q(phone_normalise=phone)
        # Le WhatsApp n'a PAS de colonne normalisée : on restreint d'abord en
        # BASE aux leads qui en portent un (une petite minorité), puis on
        # normalise ce seul sous-ensemble — la couverture est identique à
        # l'ancien scan, le coût ne l'est plus.
        whatsapp_ids = [
            pk for pk, whatsapp in Lead.objects
            .filter(company=company)
            .exclude(whatsapp__isnull=True).exclude(whatsapp='')
            .values_list('pk', 'whatsapp')
            if normalize_phone(whatsapp) == phone
        ]
        if whatsapp_ids:
            lead_q |= Q(pk__in=whatsapp_ids)
        # ``Client`` n'a pas de colonne normalisée : le filtrage reste côté
        # Python (hors périmètre de cette tâche — inchangé).
        client_ids = [
            cl.pk for cl in Client.objects.filter(company=company)
            if normalize_phone(cl.telephone) == phone
        ]
        client_q |= Q(pk__in=client_ids)

    return leads.filter(lead_q), clients.filter(client_q)


def export_crm(company, subject_identifier):
    """Export des données CRM de la personne (leads + clients)."""
    from apps.visites.selectors import visites_export_dsr
    from .models import LeadActivity
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
        'chatter': [  # ASOC67 — chatter des leads + visites terrain (selector visites)
            {'id': a.pk, 'lead': a.lead_id, 'kind': a.kind, 'body': a.body, 'champ': a.field_label,
             'le': a.created_at.isoformat()} for a in LeadActivity.objects.filter(company=company, lead__in=leads)],
        'visites': visites_export_dsr(company, leads.values_list('pk', flat=True)),
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


def _anonymiser_copies_brutes(company, lead, identifiants):
    """ACRM19 (C-ACRM-012) — caviarde les copies brutes de la personne :

    * ``WebsiteLeadPayload`` du lead, ou dont le corps brut porte l'un de
      ses identifiants (un payload EN ERREUR n'a souvent jamais été
      rattaché) : ``payload`` remplacé par ``PAYLOAD_CAVIARDE``,
      ``remote_addr`` vidé — la ligne survit (trace de réception) ;
    * ``ChatSessionPublique`` du lead : ``transcript`` vidé ;
    * ``Parrainage`` dont il est le filleul : ``filleul_nom`` vidé.
    Borné à ``company``."""
    from .models import ChatSessionPublique, Parrainage, WebsiteLeadPayload

    cible = Q(lead=lead)
    for identifiant in identifiants:
        cible |= Q(payload__icontains=identifiant)
    WebsiteLeadPayload.objects.filter(company=company).filter(cible).update(
        payload=PAYLOAD_CAVIARDE, remote_addr=None)
    ChatSessionPublique.objects.filter(company=company, lead=lead).update(
        transcript=[])
    Parrainage.objects.filter(company=company, filleul_lead=lead).update(
        filleul_nom='')


def _caviarder_historique(company, lead, identifiants, champs_effaces):
    """ASOC62 (D-ASOC-3) — caviarde le chatter du lead, archive comprise,
    lignes GARDÉES : ``old_value``/``new_value`` des champs suivis
    (``activity.TRACKED_FIELDS``) que le scrub vient de vider deviennent
    « Anonymisé », et les identifiants lus AVANT le scrub sortent des corps."""
    from django.db.models import Value
    from django.db.models.functions import Replace

    from .activity import TRACKED_FIELDS
    from .models import LeadActivity, LeadActivityArchive

    champs = [c for c in champs_effaces if c in TRACKED_FIELDS]
    for lignes in (
            LeadActivity.objects.filter(company=company, lead=lead),
            LeadActivityArchive.objects.filter(
                company_id=company.pk, lead_id=lead.pk)):
        lignes.filter(field__in=champs).update(
            old_value=LEAD_NOM_ANONYMISE, new_value=LEAD_NOM_ANONYMISE)
        for identifiant in identifiants:
            lignes.filter(body__contains=identifiant).update(body=Replace(
                'body', Value(identifiant), Value(LEAD_NOM_ANONYMISE)))


def anonymiser_lead(company, le, *, motif, demande_droit_ref=''):
    """Anonymise UN lead (jamais de suppression) + journalise la destruction.

    NTGRC4 — extrait de ``erase_crm`` SANS changer une ligne de son
    comportement, pour que la RÉTENTION (balayage par âge) et le DSR (demande
    d'une personne) partagent exactement le même scrub : deux chemins qui
    divergeraient, c'est un des deux qui oublierait un champ.

    ACAL301 — le point UNIQUE d'émission de ``core.events.lead_erased``
    (DSR ET rétention passent ici) : payload catalogué ``{company,
    crm_lead_id, phone_key}``, ``phone_key`` lu AVANT le scrub, émis APRÈS
    validation de la transaction. Les apps qui référencent le lead
    (adsengine, calepinage) s'y abonnent — le CRM n'en importe aucune.
    """
    phone_key = getattr(le, 'phone_normalise', '') or ''
    # ACVI39 — un lead effacé n'a plus aucune touche à faire (file, digest).
    from .cadence_plan import arreter_cadence
    arreter_cadence(le, user=None, motif='effacement')
    # ACRM19 — les identifiants sont lus AVANT le scrub : ils retrouvent les
    # copies brutes d'intake qui ne portent pas (encore) le lien au lead.
    identifiants = [v.strip() for v in (le.email, le.telephone, le.whatsapp)
                    if (v or '').strip()]
    # ACRM62 (D-ACRM-5 (2)=(a)) — l'opposition SURVIT à l'effacement, en
    # empreinte seule (aucune valeur en clair), lue AVANT le scrub.
    from .leads_doublons import poser_empreintes_opposition
    poser_empreintes_opposition(company, le)
    le.nom = LEAD_NOM_ANONYMISE
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
    # CRX32 — LES CHAMPS PERSONNALISÉS PARTENT AUSSI. ``custom_data``
    # (T11) est un JSON libre où une société range ce qu'elle veut : CIN,
    # numéro de compteur, notes nominatives. L'action ``anonymize`` du
    # ClientViewSet le purgeait déjà ; le chemin DSR — le seul qui réponde
    # à une demande LÉGALE d'effacement — l'oubliait des deux côtés.
    le.custom_data = None
    # AACQ20 — les identifiants de CLIC publicitaire partent aussi : un lead
    # effacé ne doit plus rien fournir au CAPI. ``external_id`` reste (dédup
    # anti-résurrection au rejeu webhook) — le sélecteur CAPI ne le renvoie
    # plus pour un lead effacé.
    le.fbclid = ''
    le.gclid = ''
    # ASOC61 — GPS, contact secondaire, notes libres et lien Maps aussi.
    le.gps_lat = le.gps_lng = le.note = le.visite_notes = None
    le.ombrage_notes = le.contact_secondaire_nom = None
    le.contact_secondaire_telephone = le.contact_secondaire_email = None
    le.contact_secondaire_fonction = None
    le.lien_maps = ''
    # QW10 — ``Lead.save()`` recalcule ``email_normalise``/``phone_normalise``
    # depuis les PII désormais vidées ; on les inclut dans ``update_fields``
    # pour que les clés de dédup normalisées soient AUSSI purgées (sinon un
    # lead « anonymisé » garderait un email/téléphone normalisé recherchable).
    champs_effaces = [
        'nom', 'prenom', 'email', 'telephone', 'whatsapp', 'adresse',
        'appareil_id', 'custom_data', 'fbclid', 'gclid',
        'email_normalise', 'phone_normalise', 'whatsapp_normalise',
        'gps_lat', 'gps_lng', 'note', 'visite_notes', 'ombrage_notes',
        'contact_secondaire_nom', 'contact_secondaire_telephone',
        'contact_secondaire_email', 'contact_secondaire_fonction',
        'lien_maps']
    le.save(update_fields=champs_effaces)
    # ASOC62 — le chatter garde ses lignes, plus les valeurs d'identité.
    _caviarder_historique(company, le, identifiants, champs_effaces)
    # Les traces de traçage du lead perdent leurs identifiants (IP,
    # navigateur, appareil, suffixe de jeton) — la ligne reste, la personne
    # n'est plus reconnaissable.
    _anonymiser_traces_visiteur(company, le)
    # ACRM19 — les COPIES BRUTES du lead : payloads d'intake (caviardés, IP
    # vidée — y compris ceux en erreur, jamais rattachés) et transcripts de
    # chat. Les purges par âge ne sont plus le seul rempart.
    _anonymiser_copies_brutes(company, le, identifiants)
    # Lot 3 critique #1 — émis APRÈS l'écriture du lead : sans transaction
    # englobante (autocommit), ``on_commit`` exécute tout de suite — un
    # abonné (scrub calepinage, suppression IRRÉVERSIBLE des photos) ne doit
    # jamais passer avant que le lead lui-même soit anonymisé.
    _emettre_lead_erased(company, le.pk, phone_key)
    return 1


def _emettre_lead_erased(company, lead_id, phone_key):
    """ACAL301 — ``lead_erased`` APRÈS validation (``on_commit``) : un
    effacement annulé ne propage rien ; les abonnés sont best-effort."""
    from django.db import transaction

    from core.events import lead_erased

    def emettre():
        lead_erased.send(sender=None, company=company,
                         crm_lead_id=lead_id, phone_key=phone_key)

    transaction.on_commit(emettre)


def anonymiser_client(company, cl, *, motif, demande_droit_ref='', now=None,
                      nom='Anonymisé'):
    """Anonymise UN client (jamais de suppression) + journalise (NTGRC4).

    Même scrub que l'action ``ClientViewSet.anonymize`` (FG26/CRX32), qui
    délègue ici (ASOC61) : identité, contacts, identifiants fiscaux/
    administratifs, champs personnalisés et GPS/notes d'ombrage du profil de
    site. Les documents comptables restent intacts.
    """
    now = now or timezone.now()
    site = getattr(cl, 'site_profile', None)  # reverse 1-1 : None si absent
    if site is not None:
        site.gps_lat = site.gps_lng = site.ombrage_notes = None
        site.save(update_fields=['gps_lat', 'gps_lng', 'ombrage_notes'])
    cl.nom = nom
    cl.prenom = None
    cl.email = None
    cl.telephone = None
    cl.adresse = None
    # CRX32 — PARITÉ AVEC L'ACTION ``anonymize`` DU ClientViewSet.
    # Elle purge depuis FG26 les identifiants fiscaux et administratifs
    # (CIN, ICE, IF, RC) et les champs personnalisés ; le chemin DSR, LUI,
    # les laissait intacts — un client « effacé » sur demande légale
    # gardait donc son numéro de carte d'identité nationale. Les deux
    # chemins scrubent désormais exactement le même ensemble.
    cl.cin = None
    cl.ice = None
    cl.if_fiscal = None
    cl.rc = None
    cl.custom_data = None
    cl.is_anonymized = True
    cl.anonymized_at = now
    cl.save(update_fields=[
        'nom', 'prenom', 'email', 'telephone', 'adresse',
        'cin', 'ice', 'if_fiscal', 'rc', 'custom_data',
        'is_anonymized', 'anonymized_at'])
    # ASOC100 — l'effacement traverse le Tiers miroir (porte ASOC60).
    from apps.tiers.services import CHAMPS_PERSONNE, anonymiser_tiers
    anonymiser_tiers(company, cl.tiers_id, CHAMPS_PERSONNE)
    return 1


def erase_crm(company, subject_identifier):
    """Anonymise leads + clients de la personne (activités conservées).

    Renvoie le nombre d'enregistrements anonymisés. N'efface JAMAIS les lignes
    (intégrité devis/factures/activités) : vide les PII et pose le drapeau.
    NTGRC1 — chaque anonymisation réelle laisse une ligne au journal de
    destruction (``grc.JournalDestruction``), best-effort : une journalisation
    impossible ne fait JAMAIS échouer l'effacement légal.
    """
    leads, clients = _matcher(company, subject_identifier)
    now = timezone.now()
    count = 0

    for le in leads:
        count += anonymiser_lead(
            company, le, motif='Effacement DSR (loi 09-08) — lead',
            demande_droit_ref=subject_identifier)

    for cl in clients:
        count += anonymiser_client(
            company, cl, motif='Effacement DSR (loi 09-08) — client',
            demande_droit_ref=subject_identifier, now=now)

    return count


# ── CAD-I ── CAD92 — la durée DÉCLARÉE est enfin celle qui est APPLIQUÉE ───
#
# Audit L3 du 21/09/2026. Le traitement seedé ``leads_clients`` déclare au
# registre CNDP « 3 ans après le dernier contact (prospects), durée légale
# comptable pour les clients » (`core/management/commands/
# seed_registre_traitements.py`), alors que `crm` n'enregistrait au registre
# de rétention partagé que la purge des `WebsiteLeadPayload`, celle des
# `ChatSessionPublique` et l'archivage du chatter (OFF par défaut) : AUCUNE
# anonymisation du Lead lui-même. Déclarer une durée qu'on n'applique nulle
# part est exactement ce qu'un contrôle compare — et c'est un écart de CODE,
# vérifiable, que `tests_cad92_retention.py` fait échouer s'il réapparaît.
#
# TROIS CHOSES QUE CE BALAYAGE NE FAIT PAS.
#   * Il ne SUPPRIME rien : il anonymise, par la MÊME fonction que le DSR
#     (`anonymiser_lead`) — deux chemins de scrub qui divergeraient, c'est un
#     des deux qui oublierait un champ.
#   * Il ne touche AUCUN lead devenu client FACTURÉ (son client porte une
#     facture, ou étape SIGNED) : la déclaration lui oppose la durée légale
#     COMPTABLE, pas trois ans, et une facture doit rester rattachable.
#     ASOC74 (D-ASOC-4) — un client SANS facture (posé au premier devis) reste
#     un prospect ; il est anonymisé quand tous ses leads sont hors durée.
#   * Il n'anonymise rien tant que le fondateur n'a pas armé l'interrupteur
#     `CRM_LEAD_RETENTION_ACTIF` : un réglage neuf garde le comportement
#     d'aujourd'hui, et supprimer des données clients par surprise au premier
#     déploiement serait irréparable. En attendant, chaque balayage COMPTE et
#     journalise le volume concerné (`core.RetentionRun`) — la déclaration
#     cesse d'être décorative même avant d'être armée.

#: La durée DÉCLARÉE au registre des traitements, en années, pour les
#: PROSPECTS : « 3 ans après le dernier contact (prospects) ». Source unique —
#: `tests_cad92_retention.py` relit la déclaration seedée et échoue si les
#: deux divergent.
DUREE_CONSERVATION_PROSPECTS_ANS = 3
DUREE_CONSERVATION_PROSPECTS_JOURS = DUREE_CONSERVATION_PROSPECTS_ANS * 365

#: Nom de la politique dans le registre de rétention partagé (YOPSB10).
RETENTION_POLICY_PROSPECTS = 'crm_prospects_anonymisation'

#: Réglage fondateur : tant qu'il est faux, le balayage COMPTE sans rien
#: écrire, même appelé avec ``apply_=True``.
RETENTION_ACTIF_SETTING = 'CRM_LEAD_RETENTION_ACTIF'


def _retention_armee():
    """Le fondateur a-t-il armé l'anonymisation des prospects ?"""
    from django.conf import settings
    valeur = getattr(settings, RETENTION_ACTIF_SETTING, False)
    if isinstance(valeur, str):
        return valeur.strip().lower() in ('1', 'true', 'oui', 'yes')
    return bool(valeur)


def prospects_hors_duree(now=None):
    """Les PROSPECTS dont le dernier contact dépasse la durée déclarée.

    « Dernier contact » = la plus récente ligne de chatter du lead, à défaut
    sa date de création — jamais ``date_modification``, qu'un simple passage
    de script suffirait à rafraîchir sans qu'aucun humain n'ait parlé à
    personne.
    """
    import datetime

    from django.db.models import Max
    from django.db.models.functions import Coalesce

    from . import stages
    from .models import Lead

    now = now or timezone.now()
    limite = now - datetime.timedelta(days=DUREE_CONSERVATION_PROSPECTS_JOURS)
    # ASOC74 (D-ASOC-4) — un client SANS facture reste un prospect (le
    # client est posé dès le premier devis) ; relation inverse à chaîne.
    return (Lead.objects
            .filter(Q(client__isnull=True) | Q(client__factures__isnull=True))
            .distinct()
            .exclude(stage=stages.SIGNED)
            .exclude(nom=LEAD_NOM_ANONYMISE)
            .annotate(dernier_contact=Coalesce(Max('activites__created_at'),
                                               'date_creation'))
            .filter(dernier_contact__lt=limite))


def sweep_retention_prospects(now, apply_=False):
    """Balayage de rétention des PROSPECTS (registre YOPSB10).

    Renvoie le nombre de leads concernés. N'anonymise que si ``apply_`` ET
    l'interrupteur fondateur sont vrais — sinon le compte est renvoyé tel
    quel, ce qui rend le volume visible dans ``core.RetentionRun`` sans rien
    détruire.
    """
    leads = list(prospects_hors_duree(now))
    if not leads:
        return 0
    if not apply_ or not _retention_armee():
        return len(leads)
    compte = 0
    motif = ('Rétention (loi 09-08) — prospect sans contact depuis '
             f'{DUREE_CONSERVATION_PROSPECTS_ANS} ans, durée déclarée '
             'au registre des traitements')
    for lead in leads:
        compte += anonymiser_lead(lead.company, lead, motif=motif)
    # ASOC74 — le client sans facture part quand TOUS ses leads sont hors durée.
    ids = [le.pk for le in leads]
    for cl in {le.client_id: le.client for le in leads if le.client_id}.values():
        if not cl.is_anonymized and not cl.leads.exclude(pk__in=ids).exclude(
                nom=LEAD_NOM_ANONYMISE).exists():
            anonymiser_client(cl.company, cl, motif=motif)
    return compte


def register():
    """Enregistre le fournisseur DSR CRM (idempotent). Appelé en ready().

    ``erase_order=100`` : le CRM porte l'IDENTITÉ de la personne (email,
    téléphone) — c'est la clé avec laquelle les AUTRES apps retrouvent leurs
    documents (``ventes`` passe par ``crm.selectors.client_ids_par_identifiant``).
    Anonymiser le CRM en premier (ordre alphabétique) effaçait cette clé sous
    les pieds des fournisseurs suivants : leur effacement ne trouvait plus rien
    et repartait à zéro, sans erreur. Le CRM s'efface donc EN DERNIER.
    """
    from core import dsr
    dsr.register_dsr_provider(
        PROVIDER_NAME, export=export_crm, erase=erase_crm, erase_order=100)
