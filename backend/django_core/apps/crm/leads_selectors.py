"""Lectures d'intake (SPL84, scission de `selectors.py`) : normalisation et
dédoublonnage, premier contact et SLA, profilage progressif.

Déplacement pur ; `apps.crm.selectors` ré-exporte chaque nom (frontière
inter-apps). N'importe jamais `.selectors` au niveau module.
"""
import datetime

from .cadence_selectors import (
    _mediane,
)
from .portee_selectors import (
    cles_numeros_lead,
)


def normalize_phone_key(value):
    """ADSENG-ODOO — Clé téléphone normalisée EXPOSÉE aux autres apps.

    Point d'entrée cross-app SANCTIONNÉ (jamais un import de
    ``apps.crm.services`` ou ``apps.crm.models`` depuis une autre app) : délègue
    à la MÊME normalisation QW10 (``services.normalize_phone``) que celle
    utilisée par ``reconciliation_lead_rows`` (``phone_key``) et l'import Odoo.

    Sert au connecteur Odoo lecture-seule d'``apps.adsengine`` : un numéro de
    téléphone Odoo (``+212…``) passé ici produit EXACTEMENT la même clé que le
    ``phone_key`` d'un lead Meta capturé par l'ERP, donc les deux se rapprochent
    (matching signature ↔ campagne). Lecture pure, aucun accès base."""
    from . import leads_doublons
    return leads_doublons.normalize_phone(value)


def normalize_email_key(value):
    """NTDATA17 — clé email normalisée EXPOSÉE aux autres apps.

    Même point d'entrée sanctionné que :func:`normalize_phone_key` : délègue à
    ``services.normalize_email`` pour qu'une autre app (la qualité de données,
    par exemple) rapproche EXACTEMENT comme le CRM, sans importer ni
    ``crm.services`` ni ``crm.models``. Lecture pure, aucun accès base."""
    from . import leads_doublons
    return leads_doublons.normalize_email(value)


def normalize_name_key(nom, prenom=None, societe=None):
    """NTDATA17 — clé de NOM normalisée EXPOSÉE aux autres apps.

    Délègue à ``services.normalize_name`` (accents retirés, minuscules, mots
    triés, ponctuation écrasée). Rend une chaîne VIDE quand le nom est trop
    court pour rapprocher quoi que ce soit — c'est la garde du CRM, et elle
    doit valoir pour tous ses lecteurs. Lecture pure, aucun accès base."""
    from . import leads_doublons
    return leads_doublons.normalize_name(nom, prenom, societe)


def find_lead_id_by_phone(company, phone):
    """ADSDEEP24 — id du lead vivant de ``company`` dont le téléphone (ou
    WhatsApp) correspond au numéro donné, normalisé via la MÊME clé QW10 que
    ``normalize_phone_key``, ou None.

    Point d'entrée cross-app LECTURE SEULE pour ``apps.adsengine`` (le webhook
    WhatsApp Cloud API CTWA rattache une conversation entrante au lead par
    téléphone) — jamais un import de ``apps.crm.models`` côté adsengine. Renvoie
    le lead le plus récemment créé en cas de doublon ; None si le numéro est
    vide ou introuvable."""
    from . import leads_doublons
    from .models import Lead

    key = leads_doublons.normalize_phone(phone)
    if not key:
        return None
    for lead in (Lead.objects
                 .filter(company=company, is_archived=False)
                 .only('id', 'telephone', 'whatsapp')
                 .order_by('-id')):
        if key in cles_numeros_lead(lead):  # ACRM33 — helper unique
            return lead.id
    return None


# DC13 — localisation chantier : lead d'abord, sinon repli sur le client ──────

# YLEAD14 — Recyclage des leads non travaillés (SLA speed-to-lead) ───────────

def leads_sla_depasse(company, now=None, seuil_heures=None):
    """YLEAD14 — Leads NEW non contactés au-delà du SLA (réutilise FG28).

    Même logique que l'action LECTURE-SEULE ``LeadViewSet.sla_breach`` :
    ``stage=NEW``, ``first_contacted_at`` NULL, créés il y a plus de
    ``seuil_heures`` heures (le seuil configuré société, ``services.
    lead_sla_hours``, si non fourni). ``now`` est injectable (tests
    déterministes) ; ``seuil_heures=0`` (SLA désactivé) renvoie un queryset
    vide — comportement identique au filtre existant. Lecture seule.
    """
    from django.utils import timezone as _timezone
    import datetime as _dt

    from .models import Lead
    from .leads_premier_contact import lead_sla_hours as _get_sla_hours

    now = now or _timezone.now()
    if seuil_heures is None:
        seuil_heures = _get_sla_hours(company)
    if not seuil_heures:
        return Lead.objects.none()

    cutoff = now - _dt.timedelta(hours=seuil_heures)
    return Lead.objects.filter(
        company=company,
        is_archived=False,
        stage='NEW',
        first_contacted_at__isnull=True,
        date_creation__lte=cutoff,
    ).order_by('date_creation')


# QW4 — Rappels demandés (contact_preference=phone_ok) non actionnés ─────────

#: N2 — la fenêtre sur laquelle court le SLA d'un RAPPEL demandé : un rappel
#: est un appel téléphonique, il ne se rattrape qu'aux heures d'appel.
CANAL_RAPPEL_SLA = 'appel'


def leads_callback_sla_depasse(company, now=None, seuil_heures=None):
    """QW4 — Rappels demandés (``contact_preference=phone_ok``) non actionnés
    (``first_contacted_at`` NULL) au-delà du SLA rappel, plus serré que le SLA
    générique (``services.callback_sla_hours``). Même patron LECTURE SEULE que
    ``leads_sla_depasse`` — ``now``/``seuil_heures`` injectables (tests
    déterministes) ; ``seuil_heures=0`` (SLA désactivé) renvoie un queryset
    vide. N'exige PAS ``stage=NEW`` : un rappel peut être demandé à n'importe
    quelle étape (rule #2 — la préférence de contact n'est pas liée au
    funnel).

    QX15 — l'horloge SLA mesure depuis ``contact_preference_set_at`` (quand
    la préférence a été POSÉE), avec repli sur ``date_creation`` pour les
    leads dont la préférence a été posée avant l'ajout de ce champ (NULL).
    Sans ce correctif, un VIEUX lead dont le rappel est demandé MAINTENANT
    apparaissait instantanément « SLA rompu » (mesuré depuis sa création).

    N2 (décision fondateur du 25/09/2026) — le délai se compte en TEMPS OUVRÉ
    sur la fenêtre d'APPEL de la société (``horaires.echeance_en_temps_ouvre``,
    canal ``appel`` : un rappel est un coup de téléphone). Un rappel promis un
    vendredi à 18 h n'est plus « en retard » le samedi matin : ses heures ne
    courent qu'aux heures d'appel. Le filtre calendaire est gardé en
    PRÉ-FILTRE (une échéance ouvrée n'est jamais plus tôt que l'échéance
    calendaire), le temps ouvré tranche ensuite. Renvoie toujours un
    queryset."""
    from django.db.models.functions import Coalesce
    from django.db.models import F
    from django.utils import timezone as _timezone
    import datetime as _dt

    from . import horaires
    from .models import Lead
    from .leads_premier_contact import callback_sla_hours as _get_callback_sla_hours

    now = now or _timezone.now()
    if seuil_heures is None:
        seuil_heures = _get_callback_sla_hours(company)
    if not seuil_heures:
        return Lead.objects.none()

    delai = _dt.timedelta(hours=seuil_heures)
    cutoff = now - delai
    candidats = Lead.objects.filter(
        company=company,
        is_archived=False,
        contact_preference=Lead.ContactPreference.PHONE_OK,
        first_contacted_at__isnull=True,
    ).annotate(
        _sla_clock=Coalesce(F('contact_preference_set_at'), F('date_creation')),
    ).filter(
        _sla_clock__lte=cutoff,
    ).values_list('pk', '_sla_clock')
    en_retard = []
    with horaires.cache_local():
        for pk, horloge in candidats:
            try:
                echeance = horaires.echeance_en_temps_ouvre(
                    horloge, delai, company, canal=CANAL_RAPPEL_SLA)
            except Exception:  # noqa: BLE001 — repli calendaire, jamais muet
                echeance = horloge + delai
            if echeance <= now:
                en_retard.append(pk)
    return Lead.objects.filter(pk__in=en_retard).order_by('date_creation')


# ── PUB68 — SLA première réponse (répondre <1 min ≈ ×4-5 conversion) ────────

def leads_meta_sla_depasse(company, now=None, seuil_heures=None):
    """PUB68 — Sous-ensemble META (``META_ADS``/``WHATSAPP_CTWA``) de
    ``leads_sla_depasse`` (YLEAD14, RÉUTILISÉ — même SLA configuré société
    ``services.lead_sla_hours``, jamais un seuil dupliqué) : leads Meta
    encore sans premier contact au-delà du SLA — le dénominateur de
    l'alerte PUB68 (« lead Meta sans premier contact »). Lecture seule."""
    from .models import Lead

    base = leads_sla_depasse(company, now=now, seuil_heures=seuil_heures)
    return base.filter(
        canal__in=[Lead.Canal.META_ADS, Lead.Canal.WHATSAPP_CTWA])


def leads_response_time_rows(company):
    """PUB68 — Temps de première réponse (minutes) par lead RÉELLEMENT
    contacté (``first_contacted_at`` non nul), avec les clés d'attribution
    déjà utilisées par ``attribution_lead_rows`` (ADSENG6 — ``meta_ad_id``/
    ``utm_content``) pour que l'appelant résolve l'ad. Un lead jamais
    contacté est ABSENT (jamais un temps de réponse infini/0 fabriqué).
    Lecture seule, scopée société, leads vivants."""
    from .models import Lead

    rows = []
    qs = (Lead.objects
          .filter(company=company, is_archived=False,
                  first_contacted_at__isnull=False)
          .only('id', 'meta_ad_id', 'utm_content', 'date_creation',
                'first_contacted_at'))
    for lead in qs:
        delta_minutes = (
            (lead.first_contacted_at - lead.date_creation).total_seconds()
            / 60.0)
        if delta_minutes < 0:
            continue
        rows.append({
            'id': lead.id,
            'meta_ad_id': lead.meta_ad_id or '',
            'utm_content': lead.utm_content or '',
            'response_minutes': delta_minutes,
        })
    return rows


#: MRY19 — l'heure que promet « rappelé le lendemain matin ».
HEURE_RAPPEL_DU_MATIN = datetime.time(9, 30)


def _limite_rappel_du_matin(creation, company):
    """L'instant limite pour qu'un lead de nuit compte comme rappelé le matin.

    9 h 30 du PROCHAIN JOUR OUVRÉ suivant l'arrivée — sauf pour un lead arrivé
    un jour ouvré AVANT l'ouverture (par exemple 07 h 00), auquel cas c'est
    9 h 30 le JOUR MÊME : il n'a pas de nuit à attendre. Les jours ouvrés et
    les fériés viennent de ``notifications.calendar_utils``, source unique.
    """
    from apps.notifications.calendar_utils import prochain_jour_ouvre

    from . import horaires

    local = creation.astimezone(horaires.CASABLANCA)
    fenetre = horaires.fenetre_du_jour(local.date(), company)
    if fenetre is not None and local.time() < fenetre[0]:
        jour = local.date()
    else:
        jour = prochain_jour_ouvre(
            local.date() + datetime.timedelta(days=1), company)
    return datetime.datetime.combine(
        jour, HEURE_RAPPEL_DU_MATIN, tzinfo=horaires.CASABLANCA)


def kpi_premier_contact(company, *, jours=30, objectif_min=None):
    """MRY19 — « rappelé en moins de N minutes OUVRÉES » — forme
    `kpi_premier_contact` (contrat MRY25).

    Trois décisions qui font que ce chiffre veut dire quelque chose :

    * les minutes sont OUVRÉES (``horaires.minutes_ouvrees_entre``) — un lead
      arrivé vendredi 21 h et rappelé lundi 08:32 vaut 2 minutes, pas 60
      heures. Un KPI d'objectif bâti sur les seules minutes calendaires
      serait faux à charge et ininterprétable — CAD88 les AJOUTE à côté
      (``mediane_minutes_calendaires``) sans toucher à celle-ci : l'ouvrée
      dit si la promesse est tenue, la calendaire ce que le client a vécu ;
    * seuls les leads ``OS_NATIVE`` comptent : les 930 leads du miroir Odoo ne
      sont pas des demandes que Meryem doit rappeler ;
    * ``null`` PARTOUT dès que ``nb_leads == 0`` — jamais un 0 %, jamais une
      médiane fabriquée sur zéro ligne.

    « Leads de nuit » = arrivés HORS fenêtre d'appel ; « rappelés avant 9 h 30 »
    = ceux d'entre eux rappelés avant 09:30 du PROCHAIN JOUR OUVRÉ suivant leur
    arrivée. La DATE compte autant que l'heure : un lead arrivé lundi 23 h et
    rappelé jeudi 08:00 passait pour « rappelé avant 9 h 30 » alors qu'il avait
    dormi deux jours — la promesse mesurée était « le lendemain matin », pas
    « un matin ».
    """
    from django.utils import timezone

    from . import horaires
    from .models import Lead

    if objectif_min is None:
        objectif_min = _objectif_premier_contact(company)
    depuis = timezone.now() - datetime.timedelta(days=int(jours))
    leads = (Lead.objects
             .filter(company=company, is_archived=False,
                     source=Lead.Source.OS_NATIVE,
                     date_creation__gte=depuis)
             # CAD119 — `date_creation_origine` est chargée pour que
             # `Lead.date_origine` réponde sans une requête par lead : un KPI
             # de délai se compte depuis la naissance du dossier, jamais
             # depuis l'heure d'une synchronisation.
             .only('id', 'date_creation', 'date_creation_origine',
                   'first_contacted_at'))

    minutes = []
    # CAD88 — la MÊME attente, comptée en calendrier : ce que le client a
    # vécu. L'objectif reste l'ouvré (colonne inchangée) ; cette seconde
    # colonne existe pour qu'un lead du vendredi soir traité lundi ne
    # s'affiche plus « conforme » et rien d'autre.
    minutes_calendaires = []
    nb_leads = 0
    nb_nuit = 0
    nb_nuit_rappeles = 0
    for lead in leads:
        nb_leads += 1
        # CAD119 — `date_origine` = la date du système d'origine si on la
        # connaît, sinon celle de l'insertion ici.
        naissance = lead.date_origine
        de_nuit = not horaires.est_dans_fenetre(naissance, company)
        if de_nuit:
            nb_nuit += 1
        if lead.first_contacted_at is None:
            continue
        minutes.append(horaires.minutes_ouvrees_entre(
            naissance, lead.first_contacted_at, company))
        minutes_calendaires.append(horaires.minutes_calendaires_entre(
            naissance, lead.first_contacted_at))
        if de_nuit and lead.first_contacted_at <= _limite_rappel_du_matin(
                naissance, company):
            nb_nuit_rappeles += 1

    if not nb_leads:
        return {
            'objectif_minutes': objectif_min,
            'nb_leads': 0,
            'nb_sous_objectif': None,
            'pct_sous_objectif': None,
            'mediane_minutes_ouvrees': None,
            # CAD88 — la colonne « vécue par le client », à côté de l'ouvrée.
            'mediane_minutes_calendaires': None,
            'nb_nuit_rappeles_avant_930': None,
            'nb_nuit': 0,
        }
    sous = sum(1 for m in minutes if m <= objectif_min)
    return {
        'objectif_minutes': objectif_min,
        'nb_leads': nb_leads,
        'nb_sous_objectif': sous,
        'pct_sous_objectif': round(100.0 * sous / nb_leads, 1),
        'mediane_minutes_ouvrees': _mediane(minutes),
        'mediane_minutes_calendaires': _mediane(minutes_calendaires),
        'nb_nuit_rappeles_avant_930': nb_nuit_rappeles,
        'nb_nuit': nb_nuit,
    }


def _objectif_premier_contact(company):
    """Objectif de la société (défaut 5 minutes ouvrées, MRY8)."""
    try:
        from apps.parametres.models import CompanyProfile
        profil = CompanyProfile.objects.filter(company=company).first()
        valeur = getattr(profil, 'premier_contact_objectif_min', None)
        return int(valeur) if valeur is not None else 5
    except Exception:  # noqa: BLE001 — défaut assumé
        return 5


def lead_merge_fields(company, lead_id):
    """XMKT8 — Champs LECTURE SEULE d'un lead pour la substitution de
    variables de fusion dans une campagne marketing (module marketing de
    compta, jamais d'import direct de ``apps.crm.models``). Renvoie ``None``
    si le lead n'appartient pas à la société (jamais d'accès cross-tenant).

    Ne renvoie JAMAIS ``prix_achat`` ni aucune donnée interne — uniquement
    les champs de contact/adresse déjà publics dans la fiche lead.
    """
    from .models import Lead
    lead = Lead.objects.select_related('owner').filter(
        pk=lead_id, company=company).first()
    if lead is None:
        return None
    proprietaire = ''
    if lead.owner_id:
        proprietaire = lead.owner.get_full_name() or lead.owner.username
    return {
        'prenom': lead.prenom or '',
        'nom': lead.nom or '',
        'ville': lead.ville or '',
        'societe': lead.societe or '',
        'proprietaire_lead': proprietaire,
    }


# ── XMKT36 — Identifiants de contact pour l'export d'audience Meta ─────────

def lead_contact_identifiers(company, lead_ids):
    """XMKT36 — email/téléphone LECTURE SEULE des leads d'un segment, pour le
    hash SHA-256 côté serveur (module marketing de compta, jamais d'import
    direct de ``apps.crm.models``). Scopé société : un id hors société est
    ignoré.
    Ne renvoie JAMAIS aucune donnée interne (prix_achat/marge inexistants
    ici) — uniquement les identifiants de contact déjà publics de la fiche."""
    from .models import Lead
    if not lead_ids:
        return []
    # ACRM56 (D-ACRM-5 (1)=(a)) — jamais d'identifiant d'un lead opposé
    # (audience Meta, graine lookalike).
    rows = Lead.objects.filter(
        company=company, id__in=list(lead_ids), ne_plus_contacter=False,
    ).values('email', 'telephone', 'whatsapp')
    return [
        {'email': r['email'] or '', 'telephone': r['telephone'] or r['whatsapp'] or ''}
        for r in rows
    ]


def existing_lead_emails(company, emails):
    """NTAPI27 — sous-ensemble de ``emails`` déjà présent comme
    ``Lead.email`` pour ``company``. Sélecteur de LECTURE pour
    ``apps.publicapi`` (seed idempotent du bac à sable API) : jamais
    d'import direct de ``Lead`` hors de ``crm``."""
    from .models import Lead

    emails = [e for e in (emails or []) if e]
    if not emails:
        return set()
    return set(
        Lead.objects.filter(company=company, email__in=emails)
        .values_list('email', flat=True)
    )


# ── NTMKT17 — Progressive profiling (formulaire public d'intake) ───────────

_PROGRESSIVE_PROFILING_STANDARD_FIELDS = (
    'nom', 'prenom', 'societe', 'email', 'telephone', 'ville',
)


def lead_known_field_codes(company, *, phone=None, email=None):
    """NTMKT17 — codes de champs DÉJÀ CONNUS pour le lead le plus RÉCENT
    correspondant à ``phone`` OU ``email`` normalisés (dédup QJ8 existante,
    ``services.find_duplicates_by_contact``).

    Renvoie ``None`` si aucun lead ne correspond (visiteur inconnu — le
    formulaire public reste inchangé, comportement actuel). Sinon un
    ``set`` des codes déjà renseignés parmi les champs standards
    (nom/prenom/societe/email/telephone/ville, non vides) et les clés non
    vides de ``custom_data``. Lecture seule."""
    from .leads_doublons import find_duplicates_by_contact

    matches = find_duplicates_by_contact(company, phone=phone, email=email)
    if not matches:
        return None
    lead = matches[0]
    connus = {
        code for code in _PROGRESSIVE_PROFILING_STANDARD_FIELDS
        if getattr(lead, code, None)
    }
    for code, valeur in (lead.custom_data or {}).items():
        if valeur not in (None, '', False):
            connus.add(code)
    return connus


def lead_ids_by_contact(company, *, email=None, phone=None):
    """AUD620 — ids des leads d'une société joignables à cet e-mail OU ce
    téléphone (saisie libre acceptée, mêmes normaliseurs que la détection de
    doublons QJ8). Lecture seule, scopée société.

    Sert au chemin de DÉSINSCRIPTION marketing (loi 09-08/CNDP) : le
    destinataire qui clique « ne plus me contacter » n'est connu que par son
    adresse ou son numéro ; il faut le rattacher à ses leads pour le sortir de
    ses séquences/journeys actifs. Renvoie ``[]`` si rien ne correspond —
    l'appelant se contente alors de la liste de suppression.
    """
    from .leads_doublons import find_duplicates_by_contact

    if not email and not phone:
        return []
    return [
        lead.pk
        for lead in find_duplicates_by_contact(
            company, email=email, phone=phone)
    ]


def lead_ids_par_identifiant(company, identifiant):
    """NTGRC8 — ids des ``Lead`` de la société correspondant à une PERSONNE.

    Pendant de :func:`client_ids_par_identifiant` pour les leads, utilisé par
    la mise sous séquestre transverse (``grc``) : elle doit pouvoir désigner
    « tous les leads de cette personne » SANS importer ``apps.crm.models``.
    Le téléphone passe par la colonne NORMALISÉE indexée (QW10) — jamais un
    scan Python de toute la table des leads.
    """
    from .models import Lead
    from .leads_doublons import normalize_email, normalize_phone

    if company is None or not (identifiant or '').strip():
        return []

    email = normalize_email(identifiant)
    phone = normalize_phone(identifiant)
    qs = Lead.objects.filter(company=company)

    ids = set()
    if email:
        ids.update(qs.filter(email__iexact=email).values_list('id', flat=True))
    if phone:
        ids.update(
            qs.filter(phone_normalise=phone).values_list('id', flat=True))
    return sorted(ids)


# ── CAD-I ── CAD93 ──────────────────────────────────────────────────────────
def doublons_foyer_probables(company, *, include_archived=False):
    """Les clusters rapprochés par l'ADRESSE ou le POINT GPS, et rien d'autre.

    Deux fiches qui partagent un téléphone sont probablement la MÊME
    personne ; deux fiches qui ne partagent que l'adresse sont probablement
    deux personnes du MÊME FOYER — et c'est une décision différente pour le
    commercial : on ne fusionne pas un père et son fils, on choisit qui
    reçoit la cadence. Cette lecture isole donc le second cas.

    Lecture seule, bornée à ``company``. Chaque entrée porte l'indice qui
    l'explique ; rien n'est fusionné, jamais, sans le geste humain de
    l'atelier doublons.
    """
    from .leads_doublons import cluster_match_keys, find_duplicate_clusters

    #: Les seules clés qui parlent de LIEU. Un cluster qui partage aussi un
    #: téléphone, un e-mail ou un nom n'est pas un « même foyer » : c'est un
    #: doublon ordinaire, déjà rendu par l'atelier.
    cles_de_lieu = {'adresse', 'gps'}

    sorties = []
    clusters, _ = find_duplicate_clusters(
        company, include_archived=include_archived)
    for groupe in clusters:
        cles = set(cluster_match_keys(groupe))
        if not cles or not cles.issubset(cles_de_lieu):
            continue
        sorties.append({
            'indices': sorted(cles),
            'membres': [
                {'id': lead.id, 'nom': lead.nom or '',
                 'prenom': lead.prenom or '', 'ville': lead.ville or '',
                 'telephone': lead.telephone or ''}
                for lead in groupe
            ],
        })
    return sorties
