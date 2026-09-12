"""Sélecteurs LECTURE SEULE du domaine CRM exposés aux AUTRES apps.

Point d'entrée cross-app : les autres apps lisent les clients à travers ces
fonctions plutôt qu'en important `apps.crm.models` directement (voir CLAUDE.md,
règle de modularité). Comportement strictement identique aux requêtes inline
d'origine.
"""
import datetime


def client_base_qs(company=None):
    """Queryset Client, scopé société si fournie. Lecture seule."""
    from .models import Client
    qs = Client.objects.all()
    if company is not None:
        qs = qs.filter(company=company)
    return qs


def find_client_by_email(from_email, company=None):
    """Client dont l'email correspond (insensible à la casse), ou None. Scopé
    société si fournie."""
    if not from_email:
        return None
    return client_base_qs(company).filter(
        email__iexact=from_email.strip()).first()


def clients_pour_controle_ice(company):
    """ZACC14 — Clients ENTREPRISE de la société, pour le contrôle
    d'identifiants légaux (ICE/IF) côté compta. Point d'entrée cross-app
    (jamais un import de ``apps.crm.models`` en dehors de ce module) :
    seuls les clients de type ``entreprise`` sont pertinents (un particulier
    n'a pas d'ICE). Lecture seule ; renvoie une liste de dicts ``{'id',
    'nom', 'ice', 'if_fiscal'}``."""
    from .models import Client

    qs = (Client.objects
          .filter(company=company, type_client=Client.TypeClient.ENTREPRISE)
          .order_by('id'))
    return [
        {
            'id': client.id,
            'nom': f'{client.nom} {client.prenom or ""}'.strip(),
            'ice': client.ice or '',
            'if_fiscal': client.if_fiscal or '',
        }
        for client in qs
    ]


def find_client_by_ice_or_libelle(company, ice=None, libelle=None):
    """AUD121 — identifie le DONNEUR D'ORDRE d'une ligne de relevé bancaire.

    Point d'entrée cross-app pour ``ventes.paiement_import`` : l'import de
    relevé ne doit plus rapprocher une somme d'argent sur le seul MONTANT
    (un virement de 12 000 soldait la facture d'un autre client qui devait
    la même somme). Il lui faut un client IDENTIFIABLE ; ce sélecteur est
    la seule façon dont ``ventes`` lit ``crm.Client`` pour cela.

    Deux pistes, dans l'ordre de fiabilité :
      1. l'ICE exact (identifiant légal, jamais ambigu) ;
      2. le nom du client CONTENU dans le libellé bancaire libre — un nom
         de moins de 4 caractères est ignoré (trop de faux positifs), et
         une correspondance MULTIPLE renvoie None : mieux vaut envoyer la
         ligne en revue humaine que créditer le mauvais client.

    Lecture seule. Renvoie un ``Client`` ou None.
    """
    ice = (ice or '').strip()
    if ice:
        hits = list(client_base_qs(company).filter(ice__iexact=ice)[:2])
        if len(hits) == 1:
            return hits[0]
        return None

    libelle = (libelle or '').strip().lower()
    if len(libelle) < 4:
        return None
    trouves = []
    for client in client_base_qs(company).only('id', 'nom', 'prenom'):
        nom = (client.nom or '').strip().lower()
        if len(nom) < 4 or nom not in libelle:
            continue
        trouves.append(client)
        if len(trouves) > 1:
            return None
    return trouves[0] if len(trouves) == 1 else None


def find_client_by_phone(company, telephone):
    """XSAV26 — Client de `company` dont le téléphone correspond au numéro
    donné, normalisé via `normalize_phone_key` (clé QW10, `services.
    normalize_phone`) — 25/08/2026, LANE NUMÉROS INTERNATIONAUX : bascule
    depuis `apps.ventes.utils.phone.normalize_ma_phone`, qui forçait un
    préfixe '212' et corrompait un numéro étranger avant comparaison (deux
    numéros étrangers différents pouvaient donc se rapprocher à tort, ou un
    +33 ne jamais matcher lui-même selon la graphie tapée). `normalize_phone`
    ne force RIEN — chiffres + indicatif réduit seulement — donc rapproche
    aussi correctement un numéro étranger saisi sous deux graphies.

    Point d'entrée cross-app sanctionné pour `apps.notifications` (webhook
    BSP WhatsApp) : matching par numéro SANS jamais exposer les modèles crm.
    Renvoie le client le plus récemment créé en cas de doublon, ou None."""
    key = normalize_phone_key(telephone)
    if not key:
        return None
    candidates = [
        c for c in client_base_qs(company).order_by('-id')
        if normalize_phone_key(c.telephone) == key
    ]
    return candidates[0] if candidates else None


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
    from . import services as crm_services
    return crm_services.normalize_phone(value)


def normalize_email_key(value):
    """NTDATA17 — clé email normalisée EXPOSÉE aux autres apps.

    Même point d'entrée sanctionné que :func:`normalize_phone_key` : délègue à
    ``services.normalize_email`` pour qu'une autre app (la qualité de données,
    par exemple) rapproche EXACTEMENT comme le CRM, sans importer ni
    ``crm.services`` ni ``crm.models``. Lecture pure, aucun accès base."""
    from . import services as crm_services
    return crm_services.normalize_email(value)


def normalize_name_key(nom, prenom=None, societe=None):
    """NTDATA17 — clé de NOM normalisée EXPOSÉE aux autres apps.

    Délègue à ``services.normalize_name`` (accents retirés, minuscules, mots
    triés, ponctuation écrasée). Rend une chaîne VIDE quand le nom est trop
    court pour rapprocher quoi que ce soit — c'est la garde du CRM, et elle
    doit valoir pour tous ses lecteurs. Lecture pure, aucun accès base."""
    from . import services as crm_services
    return crm_services.normalize_name(nom, prenom, societe)


def find_lead_id_by_phone(company, phone):
    """ADSDEEP24 — id du lead vivant de ``company`` dont le téléphone (ou
    WhatsApp) correspond au numéro donné, normalisé via la MÊME clé QW10 que
    ``normalize_phone_key``, ou None.

    Point d'entrée cross-app LECTURE SEULE pour ``apps.adsengine`` (le webhook
    WhatsApp Cloud API CTWA rattache une conversation entrante au lead par
    téléphone) — jamais un import de ``apps.crm.models`` côté adsengine. Renvoie
    le lead le plus récemment créé en cas de doublon ; None si le numéro est
    vide ou introuvable."""
    from . import services as crm_services
    from .models import Lead

    key = crm_services.normalize_phone(phone)
    if not key:
        return None
    for lead in (Lead.objects
                 .filter(company=company, is_archived=False)
                 .only('id', 'telephone', 'whatsapp')
                 .order_by('-id')):
        if (crm_services.normalize_phone(lead.telephone) == key
                or crm_services.normalize_phone(lead.whatsapp) == key):
            return lead.id
    return None


def signed_lead_phone_keys(company):
    """ADSDEEP25 — ``set`` des clés téléphone NORMALISÉES (QW10) des leads au
    stade SIGNÉ de la société.

    Point d'entrée cross-app SANCTIONNÉ pour ``apps.adsengine`` (métrique
    conversations-par-ad CTWA : rapproche une conversation WhatsApp entrante
    d'une signature par téléphone) — jamais un import de ``apps.crm.models``
    côté adsengine, et le stade SIGNÉ vient de ``STAGES.py`` (jamais codé en
    dur, règle #2). Lecture seule, scopée société ; ignore les numéros vides.
    Renvoie un ``set`` de clés non vides."""
    from . import services as crm_services
    from . import stages as stage_mod
    from .models import Lead

    keys = set()
    for tel in (Lead.objects
                .filter(company=company, stage=stage_mod.SIGNED)
                .values_list('telephone', flat=True)):
        key = crm_services.normalize_phone(tel)
        if key:
            keys.add(key)
    return keys


def signed_leads_for_campaigns(company, utm_campaigns):
    """ENG10 — Leads SIGNÉS attribués par ``utm_campaign``, avec traçabilité.

    Point d'entrée cross-app SANCTIONNÉ pour ``apps.adsengine`` (métrique
    coût-par-signature) : lit le CRM UNIQUEMENT via ce sélecteur, jamais un
    import de ``apps.crm.models`` ni du stade « SIGNED » en dur — la clé de stade
    vient de la source de vérité ``STAGES.py`` (via ``apps.crm.stages``).

    Pour chaque valeur d'``utm_campaign`` demandée, renvoie le nombre de leads au
    stade SIGNÉ et la LISTE de leurs ids (chaque chiffre est donc cliquable
    jusqu'au lead réel — traçabilité Northbeam). Lecture seule, scopée société ;
    ne compte jamais un lead supprimé (``Lead.objects`` = vivants). Renvoie ::

        {utm_campaign: {'signed_count': int, 'signed_lead_ids': [int, ...]}}
    """
    from . import stages as stage_mod
    from .models import Lead

    result = {}
    for key in utm_campaigns:
        if key in result:
            continue
        ids = list(
            Lead.objects
            .filter(company=company, utm_campaign=key, stage=stage_mod.SIGNED)
            .order_by('id')
            .values_list('id', flat=True))
        result[key] = {'signed_count': len(ids), 'signed_lead_ids': ids}
    return result


def attribution_lead_rows(company, qualifying_stage=None):
    """ADSENG6 — Lignes d'attribution PAR LEAD pour la jointure par variante.

    Point d'entrée cross-app SANCTIONNÉ pour ``apps.adsengine`` (attribution par
    variante) : le CRM est lu UNIQUEMENT via ce sélecteur, jamais un import de
    ``apps.crm.models``. Le stade « SIGNÉ » et le rang de qualification viennent
    de ``STAGES.py`` (via ``apps.crm.stages``) — jamais codés en dur côté
    adsengine (règle #2).

    Pour chaque lead vivant de la société, renvoie un dict portant les CLÉS
    d'attribution (``meta_ad_id`` d'ADSENG1, ``utm_content``/``utm_campaign``) +
    le canal (sous forme booléenne ``is_meta_channel`` pour ne pas exposer la
    taxonomie de canal crm à adsengine) + des drapeaux dérivés du funnel :

      * ``signed``    — le lead est au stade SIGNÉ ;
      * ``qualified`` — le lead a atteint AU MOINS ``qualifying_stage``
        (défaut : CONTACTED), hors COLD et hors perdu ;
      * ``junk``       — PUB28 : le lead est perdu (``perdu=True``) avec un
        motif marqué ``MotifPerte.est_junk=True`` (numéro invalide, spam/bot,
        hors zone, jamais répondu) — DISTINCT d'un lead simplement « non
        qualifié » (qui peut encore être vivant dans le funnel) ou perdu pour
        une raison commerciale réelle (prix, concurrent…). ``junk`` et
        ``qualified`` sont mutuellement exclusifs (un lead junk est perdu,
        donc jamais qualifié) ;
      * ``stage``     — PUB36 : l'étape courante (clé STAGES.py) du lead, pour
        l'entonnoir de décrochage par variante ; ``perdu`` — booléen « perdu ».

    Lecture seule, scopée société. Renvoie une LISTE de dicts (jamais un
    queryset de modèles — le contrat cross-app reste des données pures)."""
    from . import stages as stage_mod
    from .models import Lead, MotifPerte

    order = list(stage_mod.STAGES)
    qual_key = qualifying_stage or stage_mod.CONTACTED

    def _rank(key):
        try:
            return order.index(key)
        except ValueError:
            return -1

    qual_rank = _rank(qual_key)
    meta_channels = {Lead.Canal.META_ADS, Lead.Canal.WHATSAPP_CTWA}
    # PUB28 — motifs marqués « junk » de la société, comparés en minuscule/
    # strippé (Lead.motif_perte reste un texte libre, pas une FK vers
    # MotifPerte — même patron de rapprochement que le reste du CRM).
    junk_motifs = {
        (nom or '').strip().lower()
        for nom in MotifPerte.objects.filter(
            company=company, est_junk=True).values_list('nom', flat=True)}

    rows = []
    qs = (Lead.objects
          .filter(company=company, is_archived=False)
          .only('id', 'meta_ad_id', 'utm_content', 'utm_campaign', 'canal',
                'stage', 'perdu', 'motif_perte'))
    for lead in qs:
        stage = lead.stage
        rank = _rank(stage)
        is_signed = (stage == stage_mod.SIGNED)
        is_qualified = (
            stage != stage_mod.COLD and not lead.perdu
            and rank >= qual_rank)
        is_junk = bool(lead.perdu) and (
            (lead.motif_perte or '').strip().lower() in junk_motifs)
        rows.append({
            'id': lead.id,
            'meta_ad_id': lead.meta_ad_id or '',
            'utm_content': lead.utm_content or '',
            'utm_campaign': lead.utm_campaign or '',
            'is_meta_channel': lead.canal in meta_channels,
            'signed': is_signed,
            'qualified': is_qualified,
            'junk': is_junk,
            # PUB36 — étape courante (clé STAGES.py) + perdu, pour l'entonnoir
            # de décrochage PAR VARIANTE (``adsengine.attribution
            # .variant_stage_funnel``). ``stage`` est une clé STAGES.py déjà
            # exposée à adsengine via ``pipeline_stage_order`` (règle #2) — pas
            # une nouvelle fuite de la taxonomie ; ``perdu`` est un booléen.
            'stage': stage,
            'perdu': bool(lead.perdu),
        })
    return rows


def lead_appointment_stats(company):
    """PUB37 — Statistiques de RDV (``crm.Appointment``) PAR LEAD, pour le
    signal qualité intermédiaire de l'attribution par variante (adsengine).

    Point d'entrée cross-app LECTURE SEULE (jamais un import de
    ``apps.crm.models`` côté adsengine) : une annonce qui génère des RDV
    fantômes (no-show) coûte cher avant que le coût-par-signature ne le
    montre. Renvoie ``{lead_id: {'total': int, 'no_show': int}}`` — un lead
    sans AUCUN rendez-vous est absent du dict (jamais une entrée 0/0
    fabriquée). Lecture seule, scopée société."""
    from .models import Appointment

    stats = {}
    qs = (Appointment.objects
          .filter(company=company)
          .values_list('lead_id', 'statut'))
    for lead_id, statut in qs:
        slot = stats.setdefault(lead_id, {'total': 0, 'no_show': 0})
        slot['total'] += 1
        if statut == Appointment.Statut.NO_SHOW:
            slot['no_show'] += 1
    return stats


def client_credit_warning(client, montant_ttc_nouveau=None):
    """FG41 — encours client + avertissement plafond.

    Calcule l'encours TTC total des factures ouvertes (émises + en_retard) de
    ce client, l'additionne avec un nouveau montant éventuel, et renvoie un dict :

    ::
        {
          'plafond': Decimal | None,   # plafond défini sur le client
          'encours': Decimal,          # encours actuel (TTC facturé non payé)
          'encours_avec_nouveau': Decimal | None,   # si montant_ttc_nouveau fourni
          'depasse': bool,             # encours actuel > plafond
          'depassera': bool | None,    # encours+nouveau > plafond (si applicable)
          'message': str | None,       # message d'avertissement prêt à l'affichage
        }

    ``depasse=False`` et ``depassera=False`` quand aucun plafond n'est défini.
    Lecture seule — jamais de blocage, uniquement utilisé pour les avertissements.
    """
    from decimal import Decimal
    # Import local pour éviter les cycles crm ↔ ventes au module scope.
    from apps.ventes.models import Facture
    STATUTS_OUVERTS = (
        Facture.Statut.EMISE.value, Facture.Statut.EN_RETARD.value,
    )
    # montant_du de chaque facture ouverte (TTC − payé − avoirs).
    factures_ouvertes = Facture.objects.filter(
        client=client, statut__in=STATUTS_OUVERTS,
    ).prefetch_related('paiements', 'avoirs')
    encours = sum(
        (f.montant_du for f in factures_ouvertes), Decimal('0'))

    plafond = getattr(client, 'plafond_credit', None)
    depasse = plafond is not None and encours > plafond

    encours_avec_nouveau = None
    depassera = None
    if montant_ttc_nouveau is not None:
        montant_ttc_nouveau = Decimal(str(montant_ttc_nouveau))
        encours_avec_nouveau = encours + montant_ttc_nouveau
        depassera = plafond is not None and encours_avec_nouveau > plafond

    # Message d'avertissement (français, prêt pour l'UI).
    message = None
    if plafond is not None:
        if depassera:
            message = (
                f"⚠ Plafond de crédit dépassé : encours actuel "
                f"{encours:.2f} MAD + {montant_ttc_nouveau:.2f} MAD = "
                f"{encours_avec_nouveau:.2f} MAD > plafond {plafond:.2f} MAD."
            )
        elif depasse:
            message = (
                f"⚠ Plafond de crédit dépassé : encours {encours:.2f} MAD "
                f"> plafond {plafond:.2f} MAD."
            )

    return {
        'plafond': plafond,
        'encours': encours,
        'encours_avec_nouveau': encours_avec_nouveau,
        'depasse': depasse,
        'depassera': depassera,
        'message': message,
    }


def credit_hold_check(client, *, retard_jours_seuil=0):
    """XFAC28 — blocage crédit DUR (étend FG41, qui reste un simple warning).

    Réutilise ``client_credit_warning`` pour le critère plafond (jamais de
    logique dupliquée) et ajoute le critère retard : au moins une facture
    ouverte (émise/en_retard, non annulée) en retard de plus de
    ``retard_jours_seuil`` jours (0 = ce critère est ignoré). Renvoie
    ``{'bloque': bool, 'motif': str, 'encours': Decimal, 'plafond': Decimal|
    None, 'jours_retard_max': int}``. Lecture seule ; ne bloque RIEN par
    elle-même — c'est l'appelant (ventes) qui décide de refuser l'action
    selon ``CompanyProfile.credit_hold_actif``."""
    from apps.ventes.models import Facture
    warning = client_credit_warning(client)

    jours_retard_max = 0
    if retard_jours_seuil and retard_jours_seuil > 0:
        ouvertes = Facture.objects.filter(
            client=client,
            statut__in=(Facture.Statut.EMISE, Facture.Statut.EN_RETARD),
        ).prefetch_related('paiements', 'avoirs')
        for f in ouvertes:
            if f.montant_du > 0:
                jours_retard_max = max(jours_retard_max, f.jours_retard)

    motifs = []
    if warning['depasse']:
        motifs.append(
            f"encours {warning['encours']:.2f} MAD > plafond "
            f"{warning['plafond']:.2f} MAD")
    if retard_jours_seuil and jours_retard_max > retard_jours_seuil:
        motifs.append(
            f'{jours_retard_max} jour(s) de retard '
            f'(seuil {retard_jours_seuil})')

    return {
        'bloque': bool(motifs),
        'motif': ' ; '.join(motifs),
        'encours': warning['encours'],
        'plafond': warning['plafond'],
        'jours_retard_max': jours_retard_max,
    }


def get_company_lead(company, lead_id):
    """B1 — Lead borné à la société, ou None. Point d'entrée cross-app pour que
    ventes résolve un lead par id sans importer ``apps.crm.models`` (un id d'une
    autre société renvoie None → l'appelant répond 404). Lecture seule."""
    if not lead_id:
        return None
    from .models import Lead
    return Lead.objects.filter(pk=lead_id, company=company).first()


def get_company_client(company, client_id):
    """B1 — Client borné à la société, ou None (cf. get_company_lead)."""
    if not client_id:
        return None
    return client_base_qs(company).filter(pk=client_id).first()


def client_label(company, client_id):
    """ZGED5 — Libellé lisible d'un client borné société, ou None.

    Point d'entrée cross-app LECTURE SEULE pour qu'une autre app (ex. `ged`
    « contact assigné » sur un document) affiche un nom sans jamais importer
    `apps.crm.models` ni faire de FK dure. Dégrade proprement (None) si le
    client n'existe pas ou appartient à une autre société."""
    client = get_company_client(company, client_id)
    if client is None:
        return None
    if client.prenom:
        return f'{client.prenom} {client.nom}'.strip()
    return client.nom


def get_latest_lead_for_client(company, client_id):
    """Lead le plus récent rattaché à un client (borné société), ou None.

    Point d'entrée cross-app LECTURE SEULE pour que ``ventes`` remonte au lead
    porteur du profil énergétique quand seul le client est connu (auto-devis du
    Copilote). Miroir du fallback de ``lead_bills_for_devis``. Un client d'une
    autre société → None (jamais d'accès cross-tenant)."""
    if not client_id:
        return None
    from .models import Lead
    return (Lead.objects
            .filter(client_id=client_id, company=company)
            .order_by('-date_creation')
            .first())


def lead_bills_for_devis(devis):
    """Factures électriques RÉELLES (MAD/mois) du lead d'un devis, ou None.

    Point d'entrée cross-app LECTURE SEULE pour que ``ventes`` lise le profil de
    facture sans importer ``apps.crm.models``. Résolution : le lead lié au devis
    en priorité, sinon le premier lead rattaché au client du devis. Renvoie un
    dict ``{'facture_hiver', 'facture_ete', 'ete_differente'}`` (floats/None +
    bool) quand une facture d'hiver existe, sinon None (la page masque alors le
    graphe de consommation). Aucune donnée fabriquée."""
    lead = getattr(devis, 'lead', None)
    if lead is None:
        client_id = getattr(devis, 'client_id', None)
        if client_id:
            from .models import Lead
            lead = (
                Lead.objects
                .filter(client_id=client_id,
                        company_id=getattr(devis, 'company_id', None))
                .order_by('-date_creation')
                .first()
            )
    if lead is None or lead.facture_hiver in (None, ''):
        return None
    return {
        'facture_hiver': float(lead.facture_hiver),
        'facture_ete': (float(lead.facture_ete)
                        if lead.facture_ete not in (None, '') else None),
        'ete_differente': bool(lead.ete_differente),
        # QX7d — distributeur (onee/lydec/redal) pour convertir MAD→kWh par le
        # barème réel progressif-puis-sélectif (mêmes tranches que le chemin ROI), pas un prix plat.
        'distributeur': (lead.distributeur or None),
    }


def compute_attainment(objectif):
    """FG39 — Calcule le réalisé pour un ObjectifCommercial.

    Retourne un dict::

        {
          'cible': Decimal,
          'realise': Decimal,
          'taux': float,          # 0.0–100.0+ (peut dépasser 100 %)
          'period_start': date,   # premier jour de la période
          'period_end': date,     # dernier jour de la période (inclus)
        }

    Métriques CRM-only calculées ici :
      - nb_leads    : leads crm.Lead créés dans la période
      - nb_contacts : leads avec first_contacted_at dans la période
      - nb_rdv      : Appointment.statut=EFFECTUE avec scheduled_at dans la période

    Métriques ventes (nb_devis / ca_signe) : retourne 0 ; un futur hook
    d'un sélecteur ventes branchera la valeur sans importer ventes.models.
    """
    import datetime
    from decimal import Decimal

    year = objectif.period_year
    pt = objectif.period_type
    company = objectif.company
    owner = objectif.owner  # None = équipe complète

    # ── Bornes de la période ──────────────────────────────────────────────────
    if pt == 'month':
        month = objectif.period_month or 1
        period_start = datetime.date(year, month, 1)
        import calendar
        last_day = calendar.monthrange(year, month)[1]
        period_end = datetime.date(year, month, last_day)
    elif pt == 'quarter':
        q = objectif.period_quarter or 1
        month_start = (q - 1) * 3 + 1
        period_start = datetime.date(year, month_start, 1)
        import calendar
        month_end = month_start + 2
        last_day = calendar.monthrange(year, month_end)[1]
        period_end = datetime.date(year, month_end, last_day)
    else:  # year
        period_start = datetime.date(year, 1, 1)
        period_end = datetime.date(year, 12, 31)

    # Convertir en datetimes UTC-aware pour filtrer sur des DateTimeFields.
    import datetime as _dt
    from django.utils import timezone as _tz

    def _to_aware(d):
        return _tz.make_aware(
            _dt.datetime.combine(d, _dt.time.min), _tz.get_current_timezone())

    start_dt = _to_aware(period_start)
    end_dt = _to_aware(period_end) + _dt.timedelta(days=1)  # exclusif

    # ── Calcul réalisé ────────────────────────────────────────────────────────
    realise = Decimal('0')
    metric = objectif.metric

    if metric == 'nb_leads':
        from .models import Lead
        qs = Lead.objects.filter(
            company=company,
            date_creation__gte=start_dt,
            date_creation__lt=end_dt,
        )
        if owner is not None:
            qs = qs.filter(owner=owner)
        realise = Decimal(qs.count())

    elif metric == 'nb_contacts':
        from .models import Lead
        qs = Lead.objects.filter(
            company=company,
            first_contacted_at__isnull=False,
            first_contacted_at__gte=start_dt,
            first_contacted_at__lt=end_dt,
        )
        if owner is not None:
            qs = qs.filter(owner=owner)
        realise = Decimal(qs.count())

    elif metric == 'nb_rdv':
        from .models import Appointment
        qs = Appointment.objects.filter(
            company=company,
            statut=Appointment.Statut.EFFECTUE,
            scheduled_at__gte=start_dt,
            scheduled_at__lt=end_dt,
        )
        if owner is not None:
            qs = qs.filter(created_by=owner)
        realise = Decimal(qs.count())

    # else: nb_devis / ca_signe → réalisé = 0 (hook ventes futur)

    cible = objectif.cible or Decimal('0')
    taux = float(realise / cible * 100) if cible else 0.0

    return {
        'cible': cible,
        'realise': realise,
        'taux': round(taux, 1),
        'period_start': period_start,
        'period_end': period_end,
    }


def lead_touchpoints_attribution(lead, company=None):
    """FG204 — journal multi-touch ordonné + résumé d'attribution d'un lead.

    Renvoie la timeline des points de contact (PointContact) du lead, ordonnée
    (``ordre`` puis ``date_contact``), plus un résumé d'attribution simple :
    first-touch vs last-touch (canal + libellé), nombre de points et coût total
    des canaux payants. Lecture seule.

    Scopé société si ``company`` est fournie (jamais d'accès cross-tenant). Si le
    lead n'a aucun point de contact, ``timeline`` est vide et les champs
    first/last sont ``None`` (l'UI peut alors retomber sur ``Lead.canal``).

    Format::

        {
          'lead_id': int,
          'count': int,
          'timeline': [PointContact, ...],   # ordonné
          'first_touch': {'canal': str, 'canal_libelle': str} | None,
          'last_touch':  {'canal': str, 'canal_libelle': str} | None,
          'cout_total': Decimal,             # somme des coûts (canaux payants)
        }
    """
    from decimal import Decimal
    from .models import PointContact

    qs = PointContact.objects.filter(lead=lead)
    if company is not None:
        qs = qs.filter(company=company)
    # ordering du modèle (ordre, date_contact, id) → timeline chronologique.
    points = list(qs)

    def _touch(pc):
        if pc is None:
            return None
        return {
            'canal': pc.canal,
            'canal_libelle': pc.get_canal_display(),
        }

    cout_total = sum(
        (p.cout for p in points if p.cout is not None), Decimal('0'))

    return {
        'lead_id': lead.pk,
        'count': len(points),
        'timeline': points,
        'first_touch': _touch(points[0]) if points else None,
        'last_touch': _touch(points[-1]) if points else None,
        'cout_total': cout_total,
    }


def lead_card(lead_id, company):
    """S8 — fiche-carte LECTURE SEULE d'un lead pour le partage dans la
    messagerie. Scopée société : renvoie None si le lead n'appartient pas à la
    société (jamais d'accès cross-tenant). Format {label, subtitle, url}."""
    from .models import Lead
    lead = Lead.objects.filter(pk=lead_id, company=company).first()
    if lead is None:
        return None
    nom = ' '.join(p for p in [lead.nom, (lead.prenom or '')] if p).strip()
    label = nom or f'Lead #{lead.pk}'
    parts = []
    try:
        parts.append(lead.get_stage_display())
    except Exception:  # pragma: no cover - défensif
        pass
    if lead.ville:
        parts.append(lead.ville)
    return {
        'label': label,
        'subtitle': ' · '.join(parts),
        'url': f'/leads/{lead.pk}',
    }


def conception_3d_du_lead(lead):
    """PV78 — la conception 3D du lead ``{kwc, image_url}``, lecture seule.

    Passe-plat vers ``apps.ventes.selectors.conception_pour_lead`` (import
    FONCTION-LOCAL : la lecture cross-app passe exclusivement par le sélecteur
    de l'app cible, et l'import différé évite tout cycle au chargement).
    ``crm`` n'importe donc JAMAIS les modèles ventes.

    Rend toujours les deux clés — un lead sans devis calepiné vaut
    ``{'kwc': None, 'image_url': None}``, jamais une clé absente.
    """
    vide = {'kwc': None, 'image_url': None}
    if lead is None:
        return vide
    from apps.ventes.selectors import conception_pour_lead
    return conception_pour_lead(lead, getattr(lead, 'company', None)) or vide


# DC12 — profil site/énergie réutilisable par client ─────────────────────────

# Champs du profil que le générateur peut pré-remplir (source unique).
#
# QJR107 / DÉCISION FONDATEUR D7 (29/08/2026) — `orientation`,
# `inclinaison_deg` et `ombrage` (+ `ombrage_notes`) NE SONT PAS DU CODE MORT.
# Une passe de nettoyage les prend facilement pour tels : AUCUN calcul du
# moteur ne les lit — ni le dimensionnement, ni l'étude horaire, ni le PDF.
# C'est VOULU et c'est TRANCHÉ : ils sont CRM-SEULEMENT (score du lead +
# complétude du questionnaire d'appel), et ils ne seront JAMAIS branchés au
# calcul tant que le fondateur n'aura pas fourni les COEFFICIENTS réels
# (perte par orientation, par inclinaison, par ombrage). Les brancher sans
# ces coefficients reviendrait à inventer un facteur de perte — c'est-à-dire
# à inventer un chiffre montré au client, ce que la règle fondateur interdit
# sans exception. NE PAS LES SUPPRIMER, NE PAS LES CÂBLER : les laisser ici.
SITE_PROFILE_FIELDS = (
    'facture_hiver', 'facture_ete', 'ete_differente', 'conso_mensuelle_kwh',
    'tranche_onee', 'raccordement', 'regularisation_8221', 'type_installation',
    'pompe_cv', 'pompe_hmt_m', 'pompe_debit_m3h',
    'type_toiture', 'surface_toiture_m2', 'orientation', 'inclinaison_deg',
    'ombrage', 'ombrage_notes', 'gps_lat', 'gps_lng',
)


def _lignes_pipeline_ouvertes(company, membre_ids=None):
    """Leads ouverts (hors SIGNED/COLD/perdu) de la société, optionnellement
    restreints à un sous-ensemble de owners. Toujours les étapes de
    STAGES.py — jamais une liste inventée (règle #2)."""
    from . import stages as stage_mod
    from .models import Lead
    ouvertes = [
        k for k in stage_mod.STAGES if k not in (stage_mod.SIGNED, stage_mod.COLD)
    ]
    qs = Lead.objects.filter(
        company=company, is_archived=False, perdu=False, stage__in=ouvertes,
    ).prefetch_related('devis')
    if membre_ids is not None:
        qs = qs.filter(owner_id__in=membre_ids)
    return qs


def _valeur_ponderee_leads(leads):
    """Valeur pipeline pondérée (FG362/XSAL15) : réutilise le même calcul que
    `apps.reporting.pipeline` (valeur du devis le plus récent × probabilité de
    gain du lead), sans dupliquer la logique."""
    from decimal import Decimal
    from apps.reporting.pipeline import _lead_value, _lead_win_weight
    valeur = Decimal('0')
    ponderee = Decimal('0')
    for lead in leads:
        v = _lead_value(lead)
        valeur += v
        ponderee += v * _lead_win_weight(lead)
    return valeur, ponderee


def _activites_en_retard(company, membre_ids, today=None):
    """Nombre d'activités (records.Activity) en retard, assignées à l'un des
    membres. Scopé société. Lecture seule."""
    import datetime
    from apps.records.models import Activity
    today = today or datetime.date.today()
    if not membre_ids:
        return 0
    return Activity.objects.filter(
        company=company, assigned_to_id__in=membre_ids, done=False,
        due_date__isnull=False, due_date__lt=today,
    ).count()


def _ca_signe_mois(company, membre_ids, today=None):
    """CA TTC signé (Devis acceptés) ce mois-ci, par owner du lead source,
    pour les membres donnés. Lecture seule — traverse Lead.devis (reverse FK
    ventes → crm), jamais un import de apps.ventes.models."""
    import datetime
    from decimal import Decimal
    today = today or datetime.date.today()
    debut_mois = today.replace(day=1)
    if not membre_ids:
        return Decimal('0')
    from .models import Lead
    leads = (Lead.objects
             .filter(company=company, owner_id__in=membre_ids)
             .prefetch_related('devis'))
    total = Decimal('0')
    for lead in leads:
        for devis in lead.devis.all():
            if devis.statut != 'accepte':
                continue
            d = devis.date_acceptation
            if d is None or d < debut_mois or d > today:
                continue
            try:
                total += Decimal(str(devis.total_ttc or 0))
            except Exception:
                continue
    return total


def stats_equipe(company):
    """ZSAL3 — Tableau de bord « Mes équipes » : pour chaque
    ``crm.EquipeCommerciale`` actives de la société, agrège pipeline ouvert
    (count + valeur), valeur pondérée (FG362/XSAL15), activités en retard
    (assignées aux membres), et CA signé du mois vs cible ``ObjectifCommercial``
    (métrique ``ca_signe``) rattachée aux membres.

    Un commercial sans équipe n'apparaît dans AUCUNE carte (comportement
    voulu — pas un dashboard global). Lecture seule, scopée société.
    """
    from decimal import Decimal
    from django.db.models import Sum
    from .models import EquipeCommerciale, ObjectifCommercial
    import datetime

    today = datetime.date.today()
    equipes = (EquipeCommerciale.objects
               .filter(company=company, actif=True)
               .prefetch_related('membres'))

    result = []
    for equipe in equipes:
        membre_ids = list(equipe.membres.values_list('id', flat=True))
        leads = list(_lignes_pipeline_ouvertes(company, membre_ids))
        valeur, ponderee = _valeur_ponderee_leads(leads)
        activites_retard = _activites_en_retard(company, membre_ids, today)
        ca_signe = _ca_signe_mois(company, membre_ids, today)

        cible = (ObjectifCommercial.objects
                 .filter(company=company, owner_id__in=membre_ids,
                         metric=ObjectifCommercial.Metric.CA_SIGNE,
                         period_type='month',
                         period_year=today.year, period_month=today.month)
                 .aggregate(total=Sum('cible'))['total'] or Decimal('0'))
        avancement_pct = (
            round(float(ca_signe) / float(cible) * 100, 1) if cible else None
        )

        result.append({
            'id': equipe.id,
            'nom': equipe.nom,
            'responsable': getattr(equipe.responsable, 'username', None),
            'nb_membres': len(membre_ids),
            'pipeline_ouvert_count': len(leads),
            'pipeline_ouvert_valeur': str(valeur),
            'pipeline_pondere': str(ponderee),
            'activites_en_retard': activites_retard,
            'ca_signe_mois': str(ca_signe),
            'cible_ca_signe_mois': str(cible),
            'avancement_pct': avancement_pct,
        })
    return result


def attribution_leads(company, debut=None, fin=None):
    """ZSAL6 — Rapport d'attribution des leads : par COMMERCIAL et par
    CANAL/SOURCE, croisés avec le résultat (conversion en SIGNED, CA signé).

    Croise ce que win/loss-par-source (QJ19) et le leaderboard commercial
    (FG93) exposent séparément. Lecture seule, aucune migration, jamais de
    ``prix_achat``. ``debut``/``fin`` (date, inclus) filtrent
    ``Lead.date_creation`` ; ``None`` = pas de borne sur ce côté.

    Renvoie ``{'par_commercial': [...], 'par_source': [...]}`` :
      - par_commercial: {commercial, nb_leads, par_canal: {canal: count},
        nb_signes, taux_conversion_pct, ca_signe}
      - par_source: {canal, canal_label, nb_leads, nb_signes,
        taux_conversion_pct, ca_signe}

    Toujours des gardes division-par-zéro (0.0, jamais une exception). Scopé
    société — jamais d'accès cross-tenant.
    """
    from decimal import Decimal
    from . import stages as stage_mod
    from .models import Lead

    qs = Lead.objects.filter(company=company, is_archived=False)
    if debut is not None:
        qs = qs.filter(date_creation__date__gte=debut)
    if fin is not None:
        qs = qs.filter(date_creation__date__lte=fin)
    leads = list(qs.prefetch_related('devis').select_related('owner'))

    # Lead.Canal (TextChoices statique) : labels français prêts pour l'UI.
    # Un canal libre non listé (ex. valeur legacy) retombe sur sa propre clé.
    canal_labels = dict(Lead.Canal.choices)

    def _ca_signe_lead(lead):
        total = Decimal('0')
        for devis in lead.devis.all():
            if devis.statut == 'accepte':
                try:
                    total += Decimal(str(devis.total_ttc or 0))
                except Exception:
                    continue
        return total

    par_commercial = {}
    par_source = {}

    for lead in leads:
        commercial_key = lead.owner_id or 0
        commercial_nom = getattr(lead.owner, 'username', None) or 'Non assigné'
        slot_com = par_commercial.setdefault(commercial_key, {
            'commercial': commercial_nom,
            'nb_leads': 0,
            'par_canal': {},
            'nb_signes': 0,
            'ca_signe': Decimal('0'),
        })
        slot_com['nb_leads'] += 1
        canal_key = lead.canal or 'inconnu'
        slot_com['par_canal'][canal_key] = slot_com['par_canal'].get(canal_key, 0) + 1

        slot_src = par_source.setdefault(canal_key, {
            'canal': canal_key,
            'canal_label': canal_labels.get(canal_key, canal_key),
            'nb_leads': 0,
            'nb_signes': 0,
            'ca_signe': Decimal('0'),
        })
        slot_src['nb_leads'] += 1

        est_signe = lead.stage == stage_mod.SIGNED and not lead.perdu
        if est_signe:
            ca = _ca_signe_lead(lead)
            slot_com['nb_signes'] += 1
            slot_com['ca_signe'] += ca
            slot_src['nb_signes'] += 1
            slot_src['ca_signe'] += ca

    def _finalize_commercial(slot):
        taux = (
            round(slot['nb_signes'] / slot['nb_leads'] * 100, 1)
            if slot['nb_leads'] else 0.0
        )
        return {
            'commercial': slot['commercial'],
            'nb_leads': slot['nb_leads'],
            'par_canal': slot['par_canal'],
            'nb_signes': slot['nb_signes'],
            'taux_conversion_pct': taux,
            'ca_signe': str(slot['ca_signe']),
        }

    def _finalize_source(slot):
        taux = (
            round(slot['nb_signes'] / slot['nb_leads'] * 100, 1)
            if slot['nb_leads'] else 0.0
        )
        return {
            'canal': slot['canal'],
            'canal_label': slot['canal_label'],
            'nb_leads': slot['nb_leads'],
            'nb_signes': slot['nb_signes'],
            'taux_conversion_pct': taux,
            'ca_signe': str(slot['ca_signe']),
        }

    return {
        'par_commercial': sorted(
            (_finalize_commercial(s) for s in par_commercial.values()),
            key=lambda r: r['commercial']),
        'par_source': sorted(
            (_finalize_source(s) for s in par_source.values()),
            key=lambda r: r['canal']),
    }


def delai_paiement_client(client):
    """XFAC23 — conditions de paiement négociées d'un client, en dict.

    Renvoie ``{'delai_jours': int | None, 'fin_de_mois': bool}``. ``client``
    peut être ``None`` (devis/facture sans client résolu) — renvoie alors le
    réglage par défaut (aucun délai négocié). Point d'entrée cross-app LECTURE
    SEULE pour que ``ventes`` dérive la date d'échéance sans importer
    ``apps.crm.models``.
    """
    if client is None:
        return {'delai_jours': None, 'fin_de_mois': False}
    return {
        'delai_jours': getattr(client, 'delai_paiement_jours', None),
        'fin_de_mois': bool(getattr(client, 'fin_de_mois', False)),
    }


def site_profile_for_client(client_id, company=None):
    """DC12 — profil site/énergie réutilisable d'un client, en dict.

    Renvoie les valeurs à pré-remplir dans le générateur (clés =
    ``SITE_PROFILE_FIELDS``), ou None si aucun profil n'existe. Scopé société
    si fournie : un profil d'une autre société n'est jamais renvoyé. Lecture
    seule — utilisé par le générateur de devis (y compris devis SANS lead) pour
    ne plus re-saisir le profil à chaque fois.
    """
    if not client_id:
        return None
    from .models import SiteProfile
    qs = SiteProfile.objects.filter(client_id=client_id)
    if company is not None:
        qs = qs.filter(company=company)
    profile = qs.first()
    if profile is None:
        return None
    return {f: getattr(profile, f) for f in SITE_PROFILE_FIELDS}


# DC11 — provenance des valeurs énergie/toiture reprises du lead ──────────────

# Valeurs énergie + toiture du lead recopiées dans le devis. Une divergence sur
# l'une de ces clés (lead modifié APRÈS capture) déclenche la bannière
# « valeurs du lead modifiées depuis » côté générateur. Source unique pour que
# ``ventes`` n'ait pas à connaître la liste des champs du lead.
LEAD_PROVENANCE_FIELDS = (
    'facture_hiver', 'facture_ete', 'ete_differente', 'bill_kwh',
    'type_toiture', 'surface_toiture_m2', 'orientation', 'inclinaison_deg',
    'gps_lat', 'gps_lng',
)


# ── QJR234 — LA GARDE : plus une seule omission SILENCIEUSE ──────────────────
#
# LE DÉFAUT. ``LEAD_PROVENANCE_FIELDS`` est une liste écrite à la main. Une
# valeur énergie/toiture ajoutée au modèle ``crm.Lead`` et oubliée ici sort de
# la bannière « valeurs du lead modifiées depuis » SANS QUE RIEN NE LE DISE :
# le commercial ne verra jamais que cette valeur a bougé depuis la capture. Ni
# test ni garde ne signalaient l'omission.
#
# LA RÈGLE. Tout champ concret de ``crm.Lead`` dont le NOM porte un marqueur
# énergie/toiture ci-dessous doit être, au choix : dans
# ``LEAD_PROVENANCE_FIELDS``, ou dans ``LEAD_PROVENANCE_EXCLUSIONS`` AVEC SA
# RAISON. Jamais par omission. Les marqueurs sont volontairement larges : un
# faux positif se règle en écrivant une ligne d'exclusion (trente secondes),
# un faux négatif se paye en chiffres périmés montrés à un client.
_LEAD_PROVENANCE_MARQUEURS = (
    'facture', 'ete_differente', 'conso_', 'kwh', 'bill_', 'tranche_onee',
    'raccordement', 'regularisation_', 'equip_', 'occupation_jour', 'pompe_',
    'toiture', 'roof_', 'orientation', 'inclinaison', 'ombrage', 'gps_',
    'nb_etages', 'structure_pref', 'kwc', 'batterie', 'distributeur',
)

# Les raisons, mutualisées par famille : une seule phrase à relire, et un champ
# ajouté à une famille reste malgré tout un ROUGE tant qu'il n'est pas nommé
# ci-dessous (l'exclusion est par CHAMP, jamais par préfixe).
_RAISON_LU_EN_DIRECT = (
    "lu EN DIRECT sur le lead au moment du rendu, jamais recopié dans "
    "`Devis.etude_params` : une valeur qui n'a pas de copie ne peut pas "
    "diverger de sa copie. L'ajouter ferait clignoter la bannière sur un "
    "champ que le devis n'a jamais repris."
)
_RAISON_PROFIL_APPEL = (
    "profil d'équipements du script d'appel (L-BACK / L-WEBT2) : le devis ne "
    "le RECOPIE pas — il est lu sur le lead quand l'étude en a besoin. "
    "À déclarer le jour où l'écran générateur le re-saisit."
)
_RAISON_POMPAGE = (
    "questionnaire de pompage agricole : hors du bloc énergie/toiture "
    "RÉSIDENTIEL que le devis recopie (les valeurs de "
    "`LEAD_PROVENANCE_FIELDS`). À déclarer le jour où l'écran agricole "
    "re-saisit ces valeurs depuis le lead."
)
_RAISON_QUALIFICATION = (
    "donnée de QUALIFICATION du lead (ce que le prospect a déclaré au "
    "premier contact), pas une valeur d'étude re-saisie dans le devis : elle "
    "vit sa vie côté CRM et n'a pas de copie dans `etude_params`."
)
_RAISON_TRANCHE = (
    "valeur RE-DÉRIVÉE par l'étude à chaque rendu depuis la facture et la "
    "consommation (elles, sont estampillées) : l'estampiller en plus ferait "
    "signaler deux fois la même dérive."
)

LEAD_PROVENANCE_EXCLUSIONS = dict(
    [(champ, _RAISON_PROFIL_APPEL) for champ in (
        'equip_piscine', 'equip_piscine_pompe_kw', 'equip_piscine_heures_jour',
        'equip_piscine_creneau', 'equip_voiture_electrique',
        'equip_ve_km_semaine', 'equip_ve_chargeur_kw', 'equip_ve_creneau',
        'equip_clim', 'equip_clim_pieces', 'equip_clim_kw',
        'equip_clim_creneau', 'equip_chauffe_eau_electrique',
        'equip_chauffe_eau_kw', 'equip_chauffe_eau_creneau',
    )]
    + [(champ, _RAISON_POMPAGE) for champ in (
        'pompe_cv', 'pompe_hmt_m', 'pompe_debit_m3h',
    )]
    + [(champ, _RAISON_QUALIFICATION) for champ in (
        'bill_range_bucket', 'roof_type', 'roof_age', 'distributeur',
        'raccordement', 'batterie_souhaitee', 'taille_souhaitee_kwc',
        'structure_pref', 'nb_etages', 'regularisation_8221',
    )]
    + [
        ('occupation_jour', _RAISON_LU_EN_DIRECT),
        ('roof_point', _RAISON_LU_EN_DIRECT),
        ('roof_outline', _RAISON_LU_EN_DIRECT),
        ('ombrage', _RAISON_LU_EN_DIRECT),
        ('ombrage_notes',
         "note de terrain en TEXTE LIBRE : aucun chiffre d'étude n'en "
         "dérive, il n'y a rien à comparer."),
        ('conso_mensuelle_kwh', _RAISON_TRANCHE),
        ('tranche_onee', _RAISON_TRANCHE),
    ]
)


def _lead_champs_concrets():
    """Les noms des champs CONCRETS de ``crm.Lead`` (sans les relations inverses)."""
    from .models import Lead
    return [f.name for f in Lead._meta.get_fields()
            if getattr(f, 'concrete', False)]


def lead_provenance_champs_energie_toit(champs=None):
    """Les champs de ``crm.Lead`` que les marqueurs désignent énergie/toiture."""
    noms = _lead_champs_concrets() if champs is None else list(champs)
    return [nom for nom in noms
            if any(marqueur in nom for marqueur in _LEAD_PROVENANCE_MARQUEURS)]


def lead_provenance_omissions(champs=None):
    """QJR234 — [(champ, motif FR)] : tout ce qui rompt la règle ci-dessus.

    ``champs`` (facultatif) remplace la lecture du modèle : c'est ce qui permet
    de PROUVER la garde en simulant l'ajout d'un champ énergie au lead, sans
    migration et sans base de données. Liste vide = rien à signaler.
    """
    noms = _lead_champs_concrets() if champs is None else list(champs)
    connus = set(noms)
    energie_toit = lead_provenance_champs_energie_toit(noms)
    constats = []
    for champ in energie_toit:
        if champ in LEAD_PROVENANCE_FIELDS:
            continue
        raison = LEAD_PROVENANCE_EXCLUSIONS.get(champ)
        if raison:
            continue
        constats.append((
            champ,
            f"« {champ} » est un champ énergie/toiture de `crm.Lead` que "
            "`LEAD_PROVENANCE_FIELDS` ne déclare PAS : s'il change après la "
            "capture, la bannière « valeurs du lead modifiées depuis » ne le "
            "dira jamais. L'ajouter à `LEAD_PROVENANCE_FIELDS`, ou l'inscrire "
            "dans `LEAD_PROVENANCE_EXCLUSIONS` AVEC SA RAISON — jamais par "
            "omission."))
    for champ in LEAD_PROVENANCE_FIELDS:
        if champ not in connus:
            constats.append((
                champ,
                f"« {champ} » est déclaré dans `LEAD_PROVENANCE_FIELDS` mais "
                "n'existe plus sur `crm.Lead` : l'estampille porterait un "
                "champ fantôme (toujours None des deux côtés, donc une dérive "
                "invisible)."))
    for champ in LEAD_PROVENANCE_EXCLUSIONS:
        if champ not in connus:
            constats.append((
                champ,
                f"« {champ} » est exclu de la provenance alors qu'il n'existe "
                "plus sur `crm.Lead` : exclusion périmée, à retirer."))
    return constats


def _lead_provenance_valeurs(lead):
    """Snapshot {champ: valeur} des valeurs énergie/toiture d'un lead.

    Les Decimal sont rendus en str (JSON-safe + comparaison stable), les autres
    valeurs telles quelles. Lecture seule.
    """
    from decimal import Decimal
    valeurs = {}
    for f in LEAD_PROVENANCE_FIELDS:
        v = getattr(lead, f, None)
        valeurs[f] = str(v) if isinstance(v, Decimal) else v
    return valeurs


def lead_provenance_stamp(lead, captured_at=None):
    """DC11 — estampille de provenance pour ``Devis.etude_params``.

    Renvoie ``{'source_lead_id', 'captured_at', 'valeurs'}`` ou None si pas de
    lead. ``captured_at`` (ISO) par défaut = maintenant. ``ventes`` appelle
    ceci à la création/maj du devis pour tracer d'où viennent les valeurs
    énergie/toiture re-saisies, sans importer ``apps.crm.models``.
    """
    if lead is None:
        return None
    from django.utils import timezone
    ts = captured_at or timezone.now().isoformat()
    return {
        'source_lead_id': lead.pk,
        'captured_at': ts,
        'valeurs': _lead_provenance_valeurs(lead),
    }


def lead_values_changed_since(stamp, company=None):
    """DC11 — le lead source a-t-il changé depuis la capture ?

    ``stamp`` = dict produit par :func:`lead_provenance_stamp` (typiquement
    ``devis.etude_params['provenance']``). Renvoie la liste des champs dont la
    valeur courante du lead diffère de la valeur estampillée (liste vide = rien
    n'a bougé). Renvoie ``[]`` si le stamp est absent/incomplet ou le lead
    introuvable (pas de fausse alerte). Scopé société si fournie. Lecture seule
    — alimente la bannière « valeurs du lead modifiées depuis ».
    """
    if not stamp:
        return []
    lead_id = stamp.get('source_lead_id')
    valeurs = stamp.get('valeurs') or {}
    if not lead_id or not valeurs:
        return []
    from .models import Lead
    qs = Lead.objects.filter(pk=lead_id)
    if company is not None:
        qs = qs.filter(company=company)
    lead = qs.first()
    if lead is None:
        return []
    courant = _lead_provenance_valeurs(lead)

    def _norm(x):
        # Compare les nombres par VALEUR : '800' (capture en mémoire) et
        # '800.00' (relu de la base, decimal_places appliqués) sont ÉGAUX,
        # sinon chaque champ décimal non modifié lèverait une fausse alerte.
        from decimal import Decimal, InvalidOperation
        if x is None or isinstance(x, bool):
            return x
        try:
            return Decimal(str(x))
        except (InvalidOperation, ValueError):
            return x

    return [f for f in LEAD_PROVENANCE_FIELDS
            if f in valeurs and _norm(courant.get(f)) != _norm(valeurs.get(f))]


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
    from .services import lead_sla_hours as _get_sla_hours

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
    apparaissait instantanément « SLA rompu » (mesuré depuis sa création)."""
    from django.db.models.functions import Coalesce
    from django.db.models import F
    from django.utils import timezone as _timezone
    import datetime as _dt

    from .models import Lead
    from .services import callback_sla_hours as _get_callback_sla_hours

    now = now or _timezone.now()
    if seuil_heures is None:
        seuil_heures = _get_callback_sla_hours(company)
    if not seuil_heures:
        return Lead.objects.none()

    cutoff = now - _dt.timedelta(hours=seuil_heures)
    return Lead.objects.filter(
        company=company,
        is_archived=False,
        contact_preference=Lead.ContactPreference.PHONE_OK,
        first_contacted_at__isnull=True,
    ).annotate(
        _sla_clock=Coalesce(F('contact_preference_set_at'), F('date_creation')),
    ).filter(
        _sla_clock__lte=cutoff,
    ).order_by('date_creation')


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
      heures. Un KPI en minutes calendaires serait faux à charge et
      ininterprétable ;
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
             .only('id', 'date_creation', 'first_contacted_at'))

    minutes = []
    nb_leads = 0
    nb_nuit = 0
    nb_nuit_rappeles = 0
    for lead in leads:
        nb_leads += 1
        de_nuit = not horaires.est_dans_fenetre(lead.date_creation, company)
        if de_nuit:
            nb_nuit += 1
        if lead.first_contacted_at is None:
            continue
        minutes.append(horaires.minutes_ouvrees_entre(
            lead.date_creation, lead.first_contacted_at, company))
        if de_nuit and lead.first_contacted_at <= _limite_rappel_du_matin(
                lead.date_creation, company):
            nb_nuit_rappeles += 1

    if not nb_leads:
        return {
            'objectif_minutes': objectif_min,
            'nb_leads': 0,
            'nb_sous_objectif': None,
            'pct_sous_objectif': None,
            'mediane_minutes_ouvrees': None,
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
        'nb_nuit_rappeles_avant_930': nb_nuit_rappeles,
        'nb_nuit': nb_nuit,
    }


#: MRY21 — la promesse mesurée : joindre le prospect dans les 5 jours OUVRÉS.
JOURS_OUVRES_JOINDRE = 5


def _minutes_ouvrees_de_5_jours(creation, company):
    """Le seuil « 5 jours ouvrés », EXPRIMÉ en minutes ouvrées.

    Comparer des minutes ouvrées à ``5 * 24 * 60`` mélangeait deux unités :
    7 200 minutes de calendrier valent ~10 jours ouvrés de 11 h 30, soit le
    DOUBLE de la promesse — le KPI se donnait deux fois plus de temps qu'il
    n'en annonçait. On mesure donc la même chose des deux côtés : les minutes
    ouvrées séparant la création de la FERMETURE du 5ᵉ jour ouvré suivant."""
    from apps.notifications.calendar_utils import ajouter_jours_ouvres

    from . import horaires

    local = creation.astimezone(horaires.CASABLANCA)
    jour_fin = ajouter_jours_ouvres(
        local.date(), JOURS_OUVRES_JOINDRE, company)
    fenetre = horaires.fenetre_du_jour(jour_fin, company)
    fermeture = fenetre[1] if fenetre else datetime.time(20, 0)
    fin = datetime.datetime.combine(
        jour_fin, fermeture, tzinfo=horaires.CASABLANCA)
    return horaires.minutes_ouvrees_entre(creation, fin, company)


def kpi_cadences(company, *, jours=30):
    """MRY21 — Les sept chiffres du bilan de cadence (forme `kpi_cadences`).

    Lus à la fois par le panneau du Cockpit et par le bilan hebdomadaire du
    lundi. Trois règles les rendent honnêtes :

    * ``null`` dès que le DÉNOMINATEUR est 0 — jamais un 0 % qui se lirait
      comme un échec là où il n'y a simplement rien à mesurer ;
    * les devis sont comptés via ``apps.ventes.selectors``, JAMAIS un import
      de ``ventes.models`` (frontière M3) ;
    * les tentatives comptées sont HUMAINES (MRY20) — une moyenne gonflée par
      les lignes système ne dirait rien de l'effort réel.
    """
    from django.db.models import Count, Q
    from django.utils import timezone

    from . import horaires, stages
    from .models import Lead, LeadActivity, RelanceEtape

    depuis = timezone.now() - datetime.timedelta(days=int(jours))
    leads = Lead.objects.filter(company=company, date_creation__gte=depuis)
    nb_leads = leads.count()

    # « Joint » = une issue d'appel joint/intéressé dans les 5 jours OUVRÉS
    # suivant la création. Le délai est OUVRÉ pour la même raison que le KPI
    # de premier contact : un week-end n'est pas du temps perdu. Le SEUIL doit
    # l'être aussi : comparer des minutes OUVRÉES à `5 * 24 * 60` (7 200
    # minutes de calendrier) revenait à accorder ~10 jours ouvrés de 11 h 30 —
    # deux fois la promesse. Le seuil est donc lui-même compté en minutes
    # ouvrées, jusqu'à la fermeture du 5ᵉ jour ouvré.
    joints = 0
    for lead in leads.only('id', 'date_creation'):
        premiere = (LeadActivity.objects
                    .filter(lead=lead, outcome__in=('joint', 'interesse'),
                            user__isnull=False)
                    .order_by('created_at').first())
        if premiere is None:
            continue
        minutes = horaires.minutes_ouvrees_entre(
            lead.date_creation, premiere.created_at, company)
        if minutes <= _minutes_ouvrees_de_5_jours(lead.date_creation, company):
            joints += 1

    touches = RelanceEtape.objects.filter(company=company,
                                          traite_le__gte=depuis)
    # « Cadence menée à son terme » = ce lead a des touches `contact`
    # TRAITÉES sur la période et plus AUCUNE ouverte. Écrit en deux requêtes
    # simples plutôt qu'en une agrégation à double traversée : le chiffre
    # doit être lisible par qui le relit, sinon personne ne peut le vérifier.
    traites = set(
        touches.filter(cadence='contact', statut=RelanceEtape.Statut.FAIT)
        .values_list('lead_id', flat=True))
    encore_ouverts = set(
        RelanceEtape.objects.filter(
            company=company, cadence='contact',
            statut=RelanceEtape.Statut.A_FAIRE,
            lead_id__in=traites).values_list('lead_id', flat=True))
    cadences_completes = len(traites - encore_ouverts)
    # CKP1 — le proxy s'appuie désormais sur le STATUT structuré : seule une
    # touche ANNULÉE (moteur) peut venir d'un arrêt de cadence. Avant, un
    # commercial qui sautait une touche à la main en notant « pas joint »
    # gonflait ce chiffre ; et la note reste filtrée parce que le moteur
    # annule aussi pour « lead signé », « reprise : déjà passée », etc.
    cadences_arretees_joint = touches.filter(
        statut=RelanceEtape.Statut.ANNULEE, note__icontains='joint').count()

    perdus = leads.filter(perdu=True)
    nb_perdus = perdus.count()
    perdus_avec_motif = perdus.exclude(
        Q(motif_perte__isnull=True) | Q(motif_perte='')).count()

    signatures = LeadActivity.objects.filter(
        company=company, field='stage', created_at__gte=depuis,
        new_value=stages.STAGE_LABELS[stages.SIGNED]).count()

    try:
        from apps.ventes.selectors import devis_envoyes_periode
        devis_envoyes = devis_envoyes_periode(
            company, date_debut=depuis.date()).count()
    except Exception:  # noqa: BLE001 — un KPI ne casse jamais sur ce point
        devis_envoyes = 0

    # Moyenne de tentatives des leads passés au FROID sur la période — la
    # seule population où « avant abandon » veut dire quelque chose.
    refroidis = list(
        leads.filter(stage=stages.COLD)
        .annotate(tentatives=Count(
            'activites',
            filter=Q(activites__kind__in=[
                LeadActivity.Kind.APPEL, LeadActivity.Kind.WHATSAPP,
                LeadActivity.Kind.EMAIL],
                activites__user__isnull=False),
            distinct=True))
        .values_list('tentatives', flat=True))

    return {
        'joints_sous_5j_pct': (round(100.0 * joints / nb_leads, 1)
                               if nb_leads else None),
        'cadences_completes': cadences_completes,
        'cadences_arretees_joint': cadences_arretees_joint,
        'perdus_avec_motif_pct': (
            round(100.0 * perdus_avec_motif / nb_perdus, 1)
            if nb_perdus else None),
        'signatures': signatures,
        'devis_envoyes': devis_envoyes,
        'tentatives_moy_avant_abandon': (
            round(sum(refroidis) / len(refroidis), 1) if refroidis else None),
    }


# ── CKP3 — ADHÉRENCE AU PROTOCOLE (cockpit CRM « suivre les étapes ») ────────
#
# Fondateur 2026-09-10 : « moi et Meryem on ne voit pas assez ce qu'elle fait
# et si elle le fait bien — je parle du suivi des étapes ». TRANSPARENCE
# TOTALE (décision actée) : les deux agrégats ci-dessous sont lisibles par
# TOUS les rôles, seule la mise en page diffère à l'écran.
#
# Trois règles les rendent honnêtes, et aucune n'est négociable :
#   * une ANNULATION MOTEUR (statut `annulee`, CKP1) n'est JAMAIS comptée
#     comme un saut humain, ni au dénominateur de l'adhérence : une cadence
#     arrêtée parce que le client a répondu n'est pas un manquement ;
#   * dénominateur 0 → `null`, jamais un 0 % qui se lirait comme un échec là
#     où il n'y a rien à mesurer ;
#   * AUCUN seuil rouge/vert côté serveur : des valeurs et des tendances, le
#     jugement reste humain (et le couple « à-l'heure % + conversion » est
#     servi ensemble, anti-Goodhart).

#: Le grain de l'« à-l'heure » est le JOUR, pas la minute : une touche due à
#: 09:00 et faite à 17:00 le même jour A ÉTÉ FAITE. Mesurer à la minute
#: transformerait un KPI de suivi en chronomètre de surveillance — exactement
#: ce que la recherche (HBR) dit de ne pas faire.
#: Le DÉNOMINATEUR de l'adhérence = les touches closes PAR UN HUMAIN sur la
#: période (faites + sautées). Les annulations moteur en sont exclues.
_STATUTS_CLOS_HUMAIN = ('fait', 'sautee')

#: Plafond de la liste actionnable `leads_sans_touche` : au-delà, ce n'est
#: plus une file de travail mais un export — et la page mettrait dix secondes.
LEADS_SANS_TOUCHE_MAX = 100


def _lundi(jour):
    """Le lundi de la semaine de ``jour`` — la clé des tendances hebdo."""
    return jour - datetime.timedelta(days=jour.weekday())


def _pct(numerateur, denominateur):
    """``null`` dès que le dénominateur est 0 — jamais un 0 % inventé."""
    if not denominateur:
        return None
    return round(100.0 * numerateur / denominateur, 1)


def _mediane_decimale(valeurs):
    """Médiane DÉCIMALE — distincte du ``_mediane`` entier défini plus bas,
    qui arrondit des minutes : la vitesse de premier contact se lit en heures
    avec une décimale (3,4 h), et un arrondi à l'entier effacerait justement
    l'écart que la tendance hebdo cherche à montrer."""
    valeurs = sorted(valeurs)
    if not valeurs:
        return None
    milieu = len(valeurs) // 2
    if len(valeurs) % 2:
        return valeurs[milieu]
    return (valeurs[milieu - 1] + valeurs[milieu]) / 2.0


def _a_lheure(etape):
    """Une touche FAITE le jour où elle était due (heure locale Casablanca)."""
    from . import horaires

    if etape.statut != 'fait' or etape.traite_le is None:
        return False
    return (etape.traite_le.astimezone(horaires.CASABLANCA).date()
            == etape.due_date)


def kpi_adherence(company, user, jours=30):
    """CKP3 — la vue ADHÉRENCE du cockpit CRM (forme `kpi_adherence`).

    Les étapes du protocole sont-elles suivies, à l'heure, et OÙ décrochent-
    elles ? Toutes les mesures portent sur ``RelanceEtape`` — la seule table
    qui sache ce qui DEVAIT être fait et quand.

    ``user`` sert la PORTÉE DE VISIBILITÉ (``scope_queryset`` via le lead),
    jamais un filtre de rôle : la décision fondateur est la transparence
    totale — Meryem voit exactement ce que Reda voit.
    """
    from django.utils import timezone

    from authentication.scoping import scope_queryset

    from core.dates import aujourd_hui_local

    from . import horaires, stages
    from .models import Lead, RelanceEtape

    jours = max(1, int(jours))
    maintenant = timezone.now()
    depuis = maintenant - datetime.timedelta(days=jours)
    today = aujourd_hui_local()

    leads_visibles = scope_queryset(
        Lead.objects.filter(company=company, is_archived=False), user,
        ['owner'])

    touches = list(
        RelanceEtape.objects
        .filter(company=company, traite_le__gte=depuis,
                lead_id__in=leads_visibles.values('id'))
        .only('statut', 'due_date', 'traite_le', 'ordre', 'canal', 'libelle'))

    faites = [e for e in touches if e.statut == 'fait']
    sautees = [e for e in touches if e.statut == 'sautee']
    annulees = [e for e in touches if e.statut == 'annulee']
    closes_humain = faites + sautees
    a_lheure = [e for e in faites if _a_lheure(e)]

    # ── Drop-off par touche : LE signal de coaching. On groupe sur (ordre,
    # canal, libellé) — le libellé porte le sens pour un humain, l'ordre porte
    # la place dans le protocole.
    par_etape = {}
    for etape in touches:
        cle = (etape.ordre, etape.canal, (etape.libelle or '').strip())
        ligne = par_etape.setdefault(cle, {
            'ordre': etape.ordre, 'canal': etape.canal,
            'libelle': (etape.libelle or '').strip(),
            'faites': 0, '_a_lheure': 0, '_closes': 0,
            'sautees_humaines': 0, 'annulees_moteur': 0})
        if etape.statut == 'fait':
            ligne['faites'] += 1
            ligne['_closes'] += 1
            if _a_lheure(etape):
                ligne['_a_lheure'] += 1
        elif etape.statut == 'sautee':
            ligne['sautees_humaines'] += 1
            ligne['_closes'] += 1
        elif etape.statut == 'annulee':
            ligne['annulees_moteur'] += 1
    lignes_etape = []
    for ligne in sorted(par_etape.values(),
                        key=lambda x: (x['ordre'], x['canal'])):
        lignes_etape.append({
            'ordre': ligne['ordre'], 'canal': ligne['canal'],
            'libelle': ligne['libelle'], 'faites': ligne['faites'],
            'a_lheure_pct': _pct(ligne['_a_lheure'], ligne['_closes']),
            'sautees_humaines': ligne['sautees_humaines'],
            'annulees_moteur': ligne['annulees_moteur'],
        })

    # ── Tendance hebdo de l'à-l'heure : la comparaison est à SA PROPRE base,
    # jamais à un seuil inventé.
    semaines = {}
    for etape in closes_humain:
        cle = _lundi(etape.traite_le.astimezone(horaires.CASABLANCA).date())
        bloc = semaines.setdefault(cle, [0, 0])
        bloc[1] += 1
        if _a_lheure(etape):
            bloc[0] += 1
    tendance_a_lheure = [
        {'semaine': cle.isoformat(), 'a_lheure_pct': _pct(bloc[0], bloc[1])}
        for cle, bloc in sorted(semaines.items())
    ]

    # ── Vitesse de premier contact : minutes OUVRÉES (un week-end n'est pas
    # du temps perdu — même doctrine que `kpi_premier_contact`, MRY19), rendue
    # en heures. Seuls les leads NATIFS comptent : le miroir Odoo n'est pas
    # une file que Meryem doit rappeler.
    delais = []
    par_semaine = {}
    for lead in leads_visibles.filter(
            source=Lead.Source.OS_NATIVE, date_creation__gte=depuis,
            first_contacted_at__isnull=False,
    ).only('id', 'date_creation', 'first_contacted_at'):
        heures = horaires.minutes_ouvrees_entre(
            lead.date_creation, lead.first_contacted_at, company) / 60.0
        delais.append(heures)
        par_semaine.setdefault(
            _lundi(lead.date_creation.astimezone(horaires.CASABLANCA).date()),
            []).append(heures)
    mediane = _mediane_decimale(delais)
    vitesse = {
        'mediane_heures': None if mediane is None else round(mediane, 1),
        'tendance_hebdo': [
            {'semaine': cle.isoformat(),
             'mediane_heures': round(_mediane_decimale(valeurs), 1)}
            for cle, valeurs in sorted(par_semaine.items())
        ],
    }

    # ── Les dossiers qui décrochent MAINTENANT : une LISTE actionnable, pas
    # un compte. Deux cas, tous deux « la touche due n'a pas été faite » :
    # la touche ouverte est EN RETARD, ou il n'y a plus aucune touche ouverte
    # sur un lead pourtant vivant (le dossier est tombé du protocole).
    actifs = leads_visibles.exclude(
        stage__in=[stages.SIGNED, stages.COLD]).filter(
        perdu=False, ne_plus_contacter=False)
    ouvertes = {}
    for etape in RelanceEtape.objects.filter(
            company=company, statut='a_faire',
            lead_id__in=actifs.values('id')).order_by('due_date', 'ordre'):
        ouvertes.setdefault(etape.lead_id, etape)
    sans_touche = []
    for lead in actifs.only('id', 'nom', 'prenom', 'ville')[:1000]:
        etape = ouvertes.get(lead.pk)
        if etape is not None and etape.due_date >= today:
            continue                      # la prochaine touche est à venir
        if etape is None:
            retard = None
            libelle = None
        else:
            reference = etape.due_at or datetime.datetime.combine(
                etape.due_date, datetime.time(0, 0),
                tzinfo=horaires.CASABLANCA)
            retard = round(
                (maintenant - reference).total_seconds() / 3600.0, 1)
            libelle = (etape.libelle or '').strip() or etape.canal
        sans_touche.append({
            'lead_id': lead.pk,
            'nom': f'{lead.nom} {lead.prenom or ""}'.strip(),
            'ville': lead.ville or '',
            'en_retard_depuis_heures': retard,
            'prochaine_touche': libelle,
        })
    sans_touche.sort(key=lambda r: (r['en_retard_depuis_heures'] is None,
                                    -(r['en_retard_depuis_heures'] or 0)))
    sans_touche = sans_touche[:LEADS_SANS_TOUCHE_MAX]

    return {
        'periode_jours': jours,
        'a_lheure_pct': _pct(len(a_lheure), len(closes_humain)),
        'touches_faites': len(faites),
        'touches_en_retard_ouvertes': RelanceEtape.objects.filter(
            company=company, statut='a_faire', due_date__lt=today,
            lead__is_archived=False,
            lead_id__in=leads_visibles.values('id')).count(),
        'sautees_humaines': len(sautees),
        'annulees_moteur': len(annulees),
        'vitesse_premier_contact': vitesse,
        'tendance_a_lheure': tendance_a_lheure,
        'par_etape': lignes_etape,
        'leads_sans_touche': sans_touche,
        'conversion_par_stage': _conversion_par_stage(
            company, leads_visibles, depuis),
    }


def _conversion_par_stage(company, leads_visibles, depuis):
    """Le funnel APPARIÉ à l'adhérence (anti-Goodhart) — sur les clés de
    ``STAGES.py``, jamais une liste en dur.

    « Entré » dans une étape = le lead l'a ATTEINTE (son étape courante est à
    ce rang ou au-delà, ou son historique porte le passage). L'historique
    compte parce qu'un lead redescendu au Froid a bel et bien traversé le
    funnel : ne lire que l'étape courante ferait disparaître tous les dossiers
    parqués et gonflerait mécaniquement les taux.

    ``COLD`` est un PARKING (rang hors échelle) : il n'entre pas dans
    l'échelle de conversion — il n'y a pas de « suivant » après un parking.
    """
    from .models import LeadActivity
    from . import stages

    echelle = [s for s in stages.STAGES if s != stages.COLD]
    rang = {cle: i for i, cle in enumerate(echelle)}
    label_vers_cle = {stages.STAGE_LABELS[cle]: cle for cle in echelle}

    leads = list(leads_visibles.filter(date_creation__gte=depuis)
                 .values_list('id', 'stage'))
    atteint = {pk: rang.get(stage, -1) for pk, stage in leads}
    if atteint:
        for lead_id, valeur in LeadActivity.objects.filter(
                company=company, field='stage', lead_id__in=list(atteint),
        ).values_list('lead_id', 'new_value'):
            cle = label_vers_cle.get((valeur or '').strip())
            if cle is not None:
                atteint[lead_id] = max(atteint[lead_id], rang[cle])

    lignes = []
    for i, cle in enumerate(echelle):
        entres = sum(1 for r in atteint.values() if r >= i)
        passes = sum(1 for r in atteint.values() if r >= i + 1)
        lignes.append({
            'stage': cle,
            'entres': entres,
            'passes_au_suivant': passes,
            'taux_pct': _pct(passes, entres),
        })
    return lignes


def mes_stats_relance(company, user):
    """CKP3 — les tuiles PERSONNELLES du commercial (forme
    `mes_stats_relance`).

    Actionnables, JAMAIS comparatives : un rep voit SA file et SES chiffres,
    pas un classement (recherche CKP + doctrine anti-surveillance). Le manager
    voit les mêmes données — décision fondateur de transparence — mais elles
    ne sont jamais servies côte à côte comme un palmarès.

    Le périmètre est celui des leads dont ``user`` est le RESPONSABLE, dans sa
    portée de visibilité : ses tuiles parlent de son travail, pas de celui de
    l'équipe.
    """
    from django.utils import timezone

    from authentication.scoping import scope_queryset

    from core.dates import aujourd_hui_local

    from .models import Lead, RelanceEtape

    maintenant = timezone.now()
    today = aujourd_hui_local()
    mes_leads = scope_queryset(
        Lead.objects.filter(company=company, is_archived=False, owner=user),
        user, ['owner'])
    mes_touches = RelanceEtape.objects.filter(
        company=company, lead_id__in=mes_leads.values('id'))

    a_faire = mes_touches.filter(statut='a_faire', due_date__lte=today).count()
    en_retard = mes_touches.filter(
        statut='a_faire', due_date__lt=today).count()

    # Mon à-l'heure sur 7 jours — même définition que l'adhérence globale
    # (grain JOUR, annulations moteur exclues du dénominateur).
    depuis_7j = maintenant - datetime.timedelta(days=7)
    recentes = list(mes_touches.filter(
        traite_le__gte=depuis_7j,
        statut__in=_STATUTS_CLOS_HUMAIN,
    ).only('statut', 'due_date', 'traite_le'))
    a_lheure_7j = _pct(sum(1 for e in recentes if _a_lheure(e)),
                       len(recentes))

    # Cadences menées à leur terme sur 14 jours : des touches TRAITÉES sur la
    # période et plus AUCUNE ouverte sur la même cadence — deux requêtes
    # lisibles plutôt qu'une agrégation que personne ne peut vérifier.
    depuis_14j = maintenant - datetime.timedelta(days=14)
    traites = set(mes_touches.filter(
        traite_le__gte=depuis_14j, statut='fait',
    ).values_list('lead_id', 'cadence'))
    encore = set(mes_touches.filter(
        statut='a_faire').values_list('lead_id', 'cadence'))
    cadences_completees = len(traites - encore)

    return {
        'a_faire_maintenant': a_faire,
        'en_retard': en_retard,
        'a_lheure_7j_pct': a_lheure_7j,
        'cadences_completees_14j': cadences_completees,
        'serie_jours_sans_retard': _serie_jours_sans_retard(
            company, mes_touches, today),
    }


#: Profondeur maximale de la remontée de la série : au-delà, la « série » ne
#: dit plus rien d'actionnable et la requête coûterait plus qu'elle ne vaut.
SERIE_JOURS_MAX = 60


def _serie_jours_sans_retard(company, mes_touches, today):
    """Jours OUVRÉS consécutifs TERMINÉS sans laisser une touche en retard.

    Un jour est « propre » si chaque touche qui y était due a été close ce
    jour-là au plus tard. On repart du dernier jour ouvré TERMINÉ (jamais
    d'aujourd'hui : la journée n'est pas finie, compter ses touches encore
    ouvertes comme des retards serait faux) et on remonte.
    """
    from . import horaires

    dues = {}
    debut = today - datetime.timedelta(days=SERIE_JOURS_MAX)
    for etape in mes_touches.filter(
            due_date__gte=debut, due_date__lt=today,
    ).only('due_date', 'statut', 'traite_le'):
        propre = (etape.statut in ('fait', 'sautee', 'annulee')
                  and etape.traite_le is not None
                  and etape.traite_le.astimezone(horaires.CASABLANCA).date()
                  <= etape.due_date)
        dues.setdefault(etape.due_date, []).append(propre)

    serie = 0
    jour = today - datetime.timedelta(days=1)
    while jour >= debut:
        if horaires._jour_ouvre(jour, company):
            if not all(dues.get(jour, [])):
                break
            serie += 1
        jour -= datetime.timedelta(days=1)
    return serie


def _objectif_premier_contact(company):
    """Objectif de la société (défaut 5 minutes ouvrées, MRY8)."""
    try:
        from apps.parametres.models import CompanyProfile
        profil = CompanyProfile.objects.filter(company=company).first()
        valeur = getattr(profil, 'premier_contact_objectif_min', None)
        return int(valeur) if valeur is not None else 5
    except Exception:  # noqa: BLE001 — défaut assumé
        return 5


def _mediane(valeurs):
    """Médiane entière, ou ``None`` sur une liste vide (jamais un 0 inventé)."""
    if not valeurs:
        return None
    ordonnees = sorted(valeurs)
    milieu = len(ordonnees) // 2
    if len(ordonnees) % 2:
        return int(ordonnees[milieu])
    return int((ordonnees[milieu - 1] + ordonnees[milieu]) / 2)


def site_location_for_devis(devis):
    """DC13 — localisation du chantier à créer depuis un devis.

    Renvoie ``{'site_adresse', 'site_ville', 'gps_lat', 'gps_lng'}``. Quand le
    devis porte un lead, on reprend ses valeurs (comportement historique).
    Pour un devis SANS lead, ``site_adresse`` retombe sur ``client.adresse`` au
    lieu de rester vide (le client n'a ni ville ni GPS → restent None).
    Point d'entrée cross-app LECTURE SEULE pour que ``installations`` n'importe
    pas ``apps.crm.models`` ; ``create_installation_from_devis`` consomme ce
    seul accesseur. Aucune donnée fabriquée.
    """
    lead = getattr(devis, 'lead', None)
    if lead is not None:
        return {
            'site_adresse': lead.adresse,
            'site_ville': lead.ville,
            'gps_lat': lead.gps_lat,
            'gps_lng': lead.gps_lng,
        }
    client = getattr(devis, 'client', None)
    return {
        'site_adresse': getattr(client, 'adresse', None) if client else None,
        'site_ville': None,
        'gps_lat': None,
        'gps_lng': None,
    }


#: Valeurs admises pour le profil d'activité PRO, telles que le webhook web les
#: valide déjà à l'entrée (``apps/crm/webhooks.py`` — QW2). Toute autre valeur
#: est traitée comme absente : on ne devine jamais un profil d'occupation.
PROFILS_ACTIVITE = ('day', 'day_evening', 'continuous')


def profil_activite_pour_devis(devis):
    """Profil d'activité PRO du lead d'un devis, ou ``None``.

    Point d'entrée cross-app LECTURE SEULE (``apps.ventes`` n'importe jamais
    ``apps.crm.models``). Renvoie la valeur de
    ``Lead.web_questionnaire['activity_profile']`` — le SEUL signal
    d'occupation en journée réellement câblé aujourd'hui, et seulement en mode
    PRO — quand elle fait partie de :data:`PROFILS_ACTIVITE`. Aucun lead, pas
    de questionnaire, valeur inconnue ⇒ ``None`` : l'appelant applique alors
    son propre défaut, jamais une valeur inventée ici.
    """
    lead = getattr(devis, 'lead', None)
    if lead is None:
        return None
    questionnaire = getattr(lead, 'web_questionnaire', None)
    if not isinstance(questionnaire, dict):
        return None
    valeur = questionnaire.get('activity_profile')
    return valeur if valeur in PROFILS_ACTIVITE else None


def occupation_jour_pour_devis(devis):
    """L4 (extension fondateur, 21/08/2026) — présence en journée déclarée
    au téléphone (``crm.Lead.occupation_jour``), ou ``None``.

    Point d'entrée cross-app LECTURE SEULE : ``apps/ventes/courbes_journalieres.py
    _occupation`` la consulte AVANT son défaut fondateur habituel — quand le
    commercial a posé la question, la réponse RÉELLE du lead prime. ``None``
    (lead absent, ou question pas encore posée) laisse l'appelant retomber
    sur son comportement actuel, inchangé.
    """
    lead = getattr(devis, 'lead', None)
    if lead is None:
        return None
    valeur = getattr(lead, 'occupation_jour', None)
    return valeur if valeur in ('present', 'absent', 'partiel') else None


def equipements_pour_lead(lead):
    """QJR9 — équipements électriques d'un LEAD, ou ``{}`` (lead absent).

    Point d'entrée cross-app LECTURE SEULE, jumeau de
    :func:`equipements_pour_devis` pour les chemins qui n'ont PAS encore de
    devis persisté (devis automatique, tunnel) : jusqu'ici ces chemins
    recomposaient la couche équipement à la main sur SIX clés, et les huit
    grandeurs L-BACK/L-BACK2 (chauffe-eau kW/créneau, chargeur VE kW/créneau,
    clim kW/créneau, piscine heures/créneau) plus ``chauffe_eau_electrique``
    n'atteignaient jamais le moteur. Il n'y a donc plus qu'UNE liste de champs
    lue, ici, pour les deux chemins.

    Valeurs BRUTES du lead — script d'appel du commercial (piscine/VE/clim/
    chauffe-eau), DISTINCT de ``futures_charges`` (case du questionnaire web,
    sans paramètre). Chaque valeur est ``None`` quand la question n'a pas été
    posée : aucune valeur n'est devinée ici, l'appelant décide de son propre
    repli (généralement : omettre la couche).
    """
    if lead is None:
        return {}
    return {
        'piscine': lead.equip_piscine,
        'piscine_pompe_kw': lead.equip_piscine_pompe_kw,
        'voiture_electrique': lead.equip_voiture_electrique,
        've_km_semaine': lead.equip_ve_km_semaine,
        'clim': lead.equip_clim,
        'clim_pieces': lead.equip_clim_pieces,
        'chauffe_eau_electrique': lead.equip_chauffe_eau_electrique,
        # L-BACK (24/08/2026) — grandeurs complémentaires (voir models.py) :
        # kW/créneau chauffe-eau, kW/créneau chargeur VE, kW clim déclarée,
        # heures/jour piscine. Mêmes None-par-défaut ; l'appelant décide.
        'chauffe_eau_kw': lead.equip_chauffe_eau_kw,
        'chauffe_eau_creneau': lead.equip_chauffe_eau_creneau,
        've_chargeur_kw': lead.equip_ve_chargeur_kw,
        've_creneau': lead.equip_ve_creneau,
        'clim_kw': lead.equip_clim_kw,
        'piscine_heures_jour': lead.equip_piscine_heures_jour,
        # L-BACK2 (24/08/2026) — créneaux clim/piscine (enrichissement d'une
        # couche déjà active, jamais une paire requise). Mêmes None-par-défaut.
        'clim_creneau': lead.equip_clim_creneau,
        'piscine_creneau': lead.equip_piscine_creneau,
    }


def equipements_pour_devis(devis):
    """L4 (21/08/2026) — équipements électriques du lead d'un devis, ou ``{}``.

    Point d'entrée cross-app LECTURE SEULE (``apps.ventes`` n'importe jamais
    ``apps.crm.models``) : ``apps/ventes/courbes_journalieres.py`` compose ses
    couches d'équipement à partir de ce dict.

    QJR9 — sortie INCHANGÉE : simple application de
    :func:`equipements_pour_lead` au lead du devis, pour que le chemin « devis
    persisté » et le chemin « lead seul » (devis automatique / tunnel) lisent
    exactement les mêmes champs.
    """
    return equipements_pour_lead(getattr(devis, 'lead', None))


# Champs Lead autorisés dans les règles JSON d'un segment marketing (XMKT6,
# apps.compta). Whitelist stricte — toute clé inconnue est rejetée côté
# validation, jamais évaluée à l'aveugle.
LEAD_SEGMENT_FIELDS = (
    'ville', 'type_installation', 'tags', 'canal', 'score', 'facture_energie',
)


def leads_matching_regles(company, regles):
    """XMKT6 — Renvoie le queryset de ``Lead`` correspondant aux règles JSON
    d'un segment marketing. LECTURE SEULE, point d'entrée cross-app pour
    ``apps.compta`` (jamais d'import direct de ``apps.crm.models`` ailleurs).

    ``regles`` est un dict dont les clés viennent de ``LEAD_SEGMENT_FIELDS`` :

    * ``ville`` — égalité insensible à la casse ;
    * ``type_installation`` — égalité (valeur de choix) ;
    * ``tags`` — le tag apparaît dans la liste séparée par virgules ;
    * ``canal`` — égalité (valeur de choix) ;
    * ``score`` — dict ``{'gte': int, 'lte': int}`` (au moins une borne) ;
    * ``facture_energie`` — dict ``{'gte': num, 'lte': num}`` (sur
      ``facture_hiver``, la facture de référence du lead).

    Une clé absente de ``LEAD_SEGMENT_FIELDS`` lève ``ValueError`` — la
    validation stricte vit ici, appelée par ``apps.compta.services`` avant
    tout enregistrement/évaluation.
    """
    from .models import Lead

    inconnues = set(regles or {}) - set(LEAD_SEGMENT_FIELDS)
    if inconnues:
        raise ValueError(f"Règle(s) de segment inconnue(s) : {sorted(inconnues)}")

    qs = Lead.objects.filter(company=company, is_archived=False, perdu=False)
    if 'ville' in regles and regles['ville']:
        qs = qs.filter(ville__iexact=regles['ville'])
    if 'type_installation' in regles and regles['type_installation']:
        qs = qs.filter(type_installation=regles['type_installation'])
    if 'tags' in regles and regles['tags']:
        qs = qs.filter(tags__icontains=regles['tags'])
    if 'canal' in regles and regles['canal']:
        qs = qs.filter(canal=regles['canal'])
    if 'score' in regles and isinstance(regles['score'], dict):
        borne = regles['score']
        if borne.get('gte') is not None:
            qs = qs.filter(score__gte=borne['gte'])
        if borne.get('lte') is not None:
            qs = qs.filter(score__lte=borne['lte'])
    if 'facture_energie' in regles and isinstance(regles['facture_energie'], dict):
        borne = regles['facture_energie']
        if borne.get('gte') is not None:
            qs = qs.filter(facture_hiver__gte=borne['gte'])
        if borne.get('lte') is not None:
            qs = qs.filter(facture_hiver__lte=borne['lte'])
    return qs


def lead_merge_fields(company, lead_id):
    """XMKT8 — Champs LECTURE SEULE d'un lead pour la substitution de
    variables de fusion dans une campagne marketing (``apps.compta``, jamais
    d'import direct de ``apps.crm.models``). Renvoie ``None`` si le lead
    n'appartient pas à la société (jamais d'accès cross-tenant).

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
    hash SHA-256 côté serveur (``apps.compta``, jamais d'import direct de
    ``apps.crm.models``). Scopé société : un id hors société est ignoré.
    Ne renvoie JAMAIS aucune donnée interne (prix_achat/marge inexistants
    ici) — uniquement les identifiants de contact déjà publics de la fiche."""
    from .models import Lead
    if not lead_ids:
        return []
    rows = Lead.objects.filter(
        company=company, id__in=list(lead_ids),
    ).values('email', 'telephone', 'whatsapp')
    return [
        {'email': r['email'] or '', 'telephone': r['telephone'] or r['whatsapp'] or ''}
        for r in rows
    ]


def clients_contact_identifiers(company):
    """XMKT36 — email/téléphone des CLIENTS signés de la société (liste
    d'exclusion publicitaire : on n'achète pas d'impression pour un client
    déjà converti). Même contrat lecture seule que ``lead_contact_identifiers``."""
    from .models import Client
    rows = Client.objects.filter(company=company).values('email', 'telephone')
    return [
        {'email': r['email'] or '', 'telephone': r['telephone'] or ''}
        for r in rows
    ]


def leads_ville_rows(company):
    """PUB62 — Une ligne par lead PORTANT une ville renseignée : id, ville,
    signé (stade SIGNED, jamais perdu — STAGES.py, jamais codé en dur).
    Scopé société, leads vivants. Un lead SANS ville est simplement ABSENT
    (jamais une ville vide fabriquée — règle checked-facts). Point d'entrée
    cross-app pour la carte chaleur ville d'``apps.adsengine.reporting``
    (jamais un import d'``apps.crm.models`` côté adsengine)."""
    from . import stages as stage_mod
    from .models import Lead

    rows = []
    qs = (Lead.objects
          .filter(company=company, is_archived=False)
          .exclude(ville__isnull=True).exclude(ville__exact='')
          .only('id', 'ville', 'stage', 'perdu'))
    for lead in qs:
        rows.append({
            'id': lead.id,
            'ville': lead.ville.strip(),
            'signed': lead.stage == stage_mod.SIGNED and not lead.perdu,
        })
    return rows


# ── XMKT17 — Coût & ROI MAD par campagne (compta.Campagne) ─────────────────

def revenu_attribue_campagne(company, nom_campagne):
    """XMKT17 — Revenu attribué (dernier-touch) à une ``compta.Campagne`` :
    somme des devis ACCEPTÉS (TTC) des leads portant
    ``utm_campaign == nom_campagne``. Jamais d'import de ``apps.ventes``
    depuis ici — les devis sont lus via la relation ``lead.devis`` déjà
    dans le domaine crm (même pattern que ``attribution_leads``).

    Renvoie ``{'nb_leads': int, 'nb_signes': int, 'revenu_ttc': str}``.
    """
    from decimal import Decimal
    from .models import Lead

    if not nom_campagne:
        return {'nb_leads': 0, 'nb_signes': 0, 'revenu_ttc': '0'}

    leads = list(
        Lead.objects.filter(
            company=company, is_archived=False, utm_campaign=nom_campagne,
        ).prefetch_related('devis'))
    nb_signes = 0
    revenu = Decimal('0')
    for lead in leads:
        signe_pour_ce_lead = False
        for devis in lead.devis.all():
            if devis.statut == 'accepte':
                signe_pour_ce_lead = True
                try:
                    revenu += Decimal(str(devis.total_ttc or 0))
                except Exception:
                    continue
        if signe_pour_ce_lead:
            nb_signes += 1
    return {
        'nb_leads': len(leads),
        'nb_signes': nb_signes,
        'revenu_ttc': str(revenu),
    }


def leads_source_campagne(company, nom_campagne):
    """XMKT17 — Liste (drill-down) des leads portant l'utm_campaign de la
    campagne : id + nom + stage + signé (pour le drill-down ROI)."""
    from .models import Lead

    if not nom_campagne:
        return []
    leads = Lead.objects.filter(
        company=company, is_archived=False, utm_campaign=nom_campagne,
    ).only('id', 'nom', 'prenom', 'stage')
    return [
        {'id': lead.id, 'nom': f'{lead.nom} {lead.prenom or ""}'.strip(),
         'stage': lead.stage}
        for lead in leads
    ]


# ── XSAL9 — Hiérarchie de comptes (société mère / filiales) + consolidation ──

def _tous_descendants(client):
    """XSAL9 — Tous les descendants (filiales, petites-filiales…) d'un
    client, en profondeur, jamais infini (garde anti-cycle même si `clean()`
    est censé l'empêcher en amont — défense en profondeur). Lecture seule."""
    out = []
    frontier = list(client.filiales.all())
    seen = {client.pk}
    while frontier:
        current = frontier.pop()
        if current.pk in seen:
            continue
        seen.add(current.pk)
        out.append(current)
        frontier.extend(current.filiales.all())
    return out


def consolidation_client(client):
    """XSAL9 — Rollup CA groupe : agrège CE client + TOUS ses descendants
    (filiales, récursif) via les sélecteurs ventes existants (JAMAIS d'import
    de ``apps.ventes.models``). Renvoie un dict :

      ``{'filiales': [Client, ...], 'ca_devis_total': Decimal,
         'ca_factures_total': Decimal, 'nb_devis_total': int,
         'nb_factures_total': int, 'par_client': {client_id: {...}}}``

    Un client SANS filiale renvoie un rollup contenant uniquement ses
    propres chiffres (comportement dégradé, jamais une erreur). Lecture
    seule ; toujours borné à la société du client (les sélecteurs ventes
    filtrent déjà par company+client_ids)."""
    from decimal import Decimal

    from apps.ventes.selectors import ca_devis_factures_par_clients

    filiales = _tous_descendants(client)
    tous_ids = [client.pk] + [f.pk for f in filiales]
    par_client = ca_devis_factures_par_clients(client.company, tous_ids)

    ca_devis_total = Decimal('0')
    ca_factures_total = Decimal('0')
    nb_devis_total = 0
    nb_factures_total = 0
    for cid in tous_ids:
        entry = par_client.get(cid) or {
            'ca_devis': Decimal('0'), 'ca_factures': Decimal('0'),
            'nb_devis': 0, 'nb_factures': 0,
        }
        ca_devis_total += entry['ca_devis']
        ca_factures_total += entry['ca_factures']
        nb_devis_total += entry['nb_devis']
        nb_factures_total += entry['nb_factures']

    return {
        'filiales': filiales,
        'ca_devis_total': ca_devis_total,
        'ca_factures_total': ca_factures_total,
        'nb_devis_total': nb_devis_total,
        'nb_factures_total': nb_factures_total,
        'par_client': par_client,
    }


# ── VX83 — « Ma file » : items commerciaux pour la file de travail unique ────

def relances_du_jour(company, user, scope='today', today=None):
    """VX83 — File de relance d'un utilisateur, EXTRAITE de
    ``LeadViewSet.relances`` (FG31, ``apps/crm/views.py``) pour être consommée
    par la « Ma file » cross-module (``records`` ne fabrique jamais sa propre
    union — convention selectors, jamais forker/appeler une vue).

    Mêmes règles que l'action d'origine : leads non archivés portant une
    ``relance_date``, filtrés par ``scope`` (``overdue`` / ``today`` / ``week``),
    ordonnés par échéance puis nom. La PORTÉE DE VISIBILITÉ de l'utilisateur est
    respectée à l'identique (``scope_queryset(..., ['owner'])`` — Feature F : un
    rôle restreint ne voit que ses leads). Lecture seule, scopée société.
    """
    import datetime
    from core.dates import aujourd_hui_local
    from authentication.scoping import scope_queryset
    from .models import Lead

    today = today or aujourd_hui_local()
    qs = Lead.objects.filter(
        company=company, is_archived=False, relance_date__isnull=False)
    qs = scope_queryset(qs, user, ['owner'])
    if scope == 'overdue':
        qs = qs.filter(relance_date__lt=today)
    elif scope == 'week':
        # CRX28 — la borne BASSE manquait : sans ``__gte=today``, « cette
        # semaine » ramenait TOUT le passé (un retard de six mois s'affichait
        # comme une relance de la semaine) et doublonnait le scope ``overdue``,
        # qui existe précisément pour montrer les retards. La semaine, c'est
        # aujourd'hui → aujourd'hui + 6 jours, bornes incluses.
        week_end = today + datetime.timedelta(days=6)
        qs = qs.filter(relance_date__gte=today, relance_date__lte=week_end)
    else:  # today
        qs = qs.filter(relance_date=today)
    return qs.order_by('relance_date', 'nom')


# ── RELANCE FOUNDATION — file des étapes de cadence de relance dues ─────────

def relance_etapes_dues(company, user, *, scope='today', owner=None, today=None):
    """RELANCE FOUNDATION — étapes de relance (``RelanceEtape``) DUES, pour le
    panneau « Relances du jour ».

    Distinct de ``relances_du_jour`` ci-dessus (leads via ``relance_date``,
    granularité lead) : ici la granularité est l'ÉTAPE de plan structuré
    (canal + statut propres). ``scope`` = ``overdue`` (en retard, strictement
    avant aujourd'hui) / ``today`` (échéance aujourd'hui, défaut) / ``all``
    (aujourd'hui + en retard, l'union affichée par le panneau). Seules les
    étapes ``a_faire`` sont candidates — jamais une étape déjà traitée. La
    portée de visibilité de l'utilisateur est respectée (``scope_queryset``
    via le lead) ; ``owner`` filtre en plus sur le responsable du lead.

    MRY30 — deux scopes S'AJOUTENT, sans rien changer aux trois précédents :
    ``tomorrow`` (échéance DEMAIN, ce que la file du jour ne montre jamais —
    Meryem prépare sa journée la veille) et ``week`` (retard + les 7 prochains
    jours). ``week`` INCLUT le retard : une touche oubliée lundi doit rester
    sous les yeux toute la semaine, sinon elle disparaît exactement au moment
    où elle devient urgente.
    """
    import datetime as _dt

    from core.dates import aujourd_hui_local
    from authentication.scoping import scope_queryset
    from .models import Lead, RelanceEtape

    today = today or aujourd_hui_local()
    qs = RelanceEtape.objects.filter(
        company=company, statut=RelanceEtape.Statut.A_FAIRE,
        lead__is_archived=False,
    ).select_related('lead', 'lead__owner', 'devis')
    if scope == 'overdue':
        qs = qs.filter(due_date__lt=today)
    elif scope == 'all':
        qs = qs.filter(due_date__lte=today)
    elif scope == 'tomorrow':
        qs = qs.filter(due_date=today + _dt.timedelta(days=1))
    elif scope == 'week':
        qs = qs.filter(due_date__lte=today + _dt.timedelta(days=7))
    else:  # today
        qs = qs.filter(due_date=today)

    # Portée de visibilité : mêmes leads que scope_queryset(..., ['owner'])
    # appliqué à Lead, traduit ici en filtre sur `lead_id`.
    leads_visibles = scope_queryset(
        Lead.objects.filter(company=company), user, ['owner'])
    qs = qs.filter(lead_id__in=leads_visibles.values('id'))

    if owner:
        qs = qs.filter(lead__owner_id=owner)
    # MRY5 — tri à la MINUTE : `due_at` d'abord, les lignes d'avant MRY5 (sans
    # heure) EN DERNIER. Sans `nulls_last`, Postgres les remonterait en tête
    # de la file de Meryem alors qu'elles n'ont pas d'heure connue.
    from django.db.models import F
    return qs.order_by(F('due_at').asc(nulls_last=True), 'due_date', 'ordre')


#: MRY30 — le statut VIRTUEL du suivi : « en retard » n'existe pas en base
#: (c'est un ``a_faire`` dont l'échéance est passée), mais c'est l'onglet que
#: Meryem ouvre en premier. Le nommer ici évite qu'il soit recalculé — donc
#: défini autrement — dans la vue puis dans l'écran.
STATUT_EN_RETARD = 'en_retard'

#: Les quatre valeurs acceptées par ``?statut=`` de l'action « suivi ».
#: CKP1 — ``annulee`` s'AJOUTE (aucune valeur retirée : les écrans qui
#: envoient ``statut=sautee`` continuent de fonctionner à l'identique).
STATUTS_SUIVI = ('a_faire', 'fait', 'sautee', 'annulee', STATUT_EN_RETARD)

#: Écart MAXIMAL entre les deux bornes du suivi. Au-delà, la requête cesse
#: d'être une « période de travail » et devient un export : 400 plutôt qu'une
#: page qui met dix secondes à s'afficher.
SUIVI_JOURS_MAX = 62


def relance_etapes_periode(company, user, *, date_debut, date_fin, owner=None,
                           statut=None, today=None):
    """MRY30 — TOUTES les touches de relance dont ``due_date`` tombe dans
    ``[date_debut, date_fin]``, TOUS statuts confondus — l'écran « Suivi des
    relances ».

    Distinct de ``relance_etapes_dues`` ci-dessus, qui ne sert QUE la file du
    jour (statut ``a_faire``, échéance relative à aujourd'hui) : ici on
    regarde EN ARRIÈRE autant qu'en avant — ce qui a été fait, ce qui a été
    sauté, ce qui reste — jour par jour, sur une période choisie.

    Renvoie ``(etapes, resume)`` — un COUPLE, délibérément :

      * ``resume`` = ``{a_faire, en_retard, fait, sautee, annulee}`` compté sur la
        période et le filtre ``owner`` mais **AVANT** le filtre ``statut``.
        L'écran affiche les quatre chiffres quel que soit l'onglet ouvert ;
        les compter après le filtre donnerait « fait : 12, sauté : 0 » sur
        l'onglet « fait ». Rendre le couple d'un seul appel rend cet ordre
        STRUCTUREL : l'appelant ne peut plus l'inverser par inadvertance.
      * ``en_retard`` est un SOUS-ENSEMBLE de ``a_faire`` (échéance
        strictement avant aujourd'hui, date de Casablanca), jamais une
        cinquième colonne qui s'ajouterait aux trois autres.

    Portée identique à la file du jour : ``scope_queryset`` via le lead (un
    lead hors portée n'apparaît jamais, pas même en 403 qui confirmerait son
    existence), leads archivés exclus, ``owner`` en filtre supplémentaire.
    """
    from django.db.models import Count, F, Q

    from core.dates import aujourd_hui_local
    from authentication.scoping import scope_queryset
    from .models import Lead, RelanceEtape

    today = today or aujourd_hui_local()
    qs = RelanceEtape.objects.filter(
        company=company, lead__is_archived=False,
        due_date__gte=date_debut, due_date__lte=date_fin,
    ).select_related('lead', 'lead__owner', 'devis', 'traite_par')

    leads_visibles = scope_queryset(
        Lead.objects.filter(company=company), user, ['owner'])
    qs = qs.filter(lead_id__in=leads_visibles.values('id'))
    if owner:
        qs = qs.filter(lead__owner_id=owner)

    a_faire = Q(statut=RelanceEtape.Statut.A_FAIRE)
    resume = qs.aggregate(
        a_faire=Count('pk', filter=a_faire),
        en_retard=Count('pk', filter=a_faire & Q(due_date__lt=today)),
        fait=Count('pk', filter=Q(statut=RelanceEtape.Statut.FAIT)),
        sautee=Count('pk', filter=Q(statut=RelanceEtape.Statut.SAUTEE)),
        # CKP1 — colonne SÉPARÉE, ajoutée À CÔTÉ de `sautee` (jamais fondue
        # dedans) : une cadence arrêtée par le moteur parce que le client a
        # répondu n'est pas un manquement, et `sautee` reste ce qu'il était
        # (compat : aucune clé retirée).
        annulee=Count('pk', filter=Q(statut=RelanceEtape.Statut.ANNULEE)),
    )

    if statut == STATUT_EN_RETARD:
        qs = qs.filter(a_faire, due_date__lt=today)
    elif statut:
        qs = qs.filter(statut=statut)

    # Tri de LECTURE (le jour d'abord), et non le tri d'urgence de la file du
    # jour : l'écran groupe par journée. `due_at` départage à la minute, les
    # lignes d'avant MRY5 (sans heure) EN DERNIER de leur journée.
    etapes = qs.order_by(
        'due_date', F('due_at').asc(nulls_last=True), 'ordre')
    return etapes, resume


def prochaine_touche_par_lead(company, lead_ids):
    """MRY5 — ``{lead_id: (due_at, due_date, cadence, canal)}`` de la prochaine
    touche À FAIRE de chaque lead demandé.

    Une seule requête pour N leads (le badge « touche due » de la liste et du
    kanban ne peut pas coûter une requête par carte). Un lead sans touche
    ouverte est simplement ABSENT du dictionnaire — jamais une entrée vide."""
    from django.db.models import F

    from .models import RelanceEtape

    if not lead_ids:
        return {}
    lignes = (RelanceEtape.objects
              .filter(company=company, lead_id__in=list(lead_ids),
                      statut=RelanceEtape.Statut.A_FAIRE)
              .order_by('lead_id', F('due_at').asc(nulls_last=True),
                        'due_date', 'ordre')
              .values_list('lead_id', 'due_at', 'due_date', 'cadence',
                           'canal'))
    out = {}
    for lead_id, due_at, due_date, cadence, canal in lignes:
        # La première ligne rencontrée par lead est la plus proche (tri
        # ci-dessus) — les suivantes sont ignorées.
        out.setdefault(lead_id, (due_at, due_date, cadence, canal))
    return out


def devis_a_cadence_active(devis_id):
    """MRY7 — ce devis porte-t-il une cadence MRY encore À FAIRE ?

    Consommé par ``ventes.domain.recouvrement`` pour SUPPRIMER la relance
    vendeur QJ4 sur un devis déjà suivi par le moteur de Meryem : sans cette
    porte, le client recevrait deux relances pour le même devis, le même jour,
    de deux systèmes différents. Lecture seule ; ``ventes`` l'appelle par ce
    sélecteur, jamais en important ``crm.models``."""
    from .models import RelanceEtape

    if not devis_id:
        return False
    return RelanceEtape.objects.filter(
        devis_id=devis_id, statut=RelanceEtape.Statut.A_FAIRE).exists()


def leads_chauds_non_contactes(company, user, seuil_score=None):
    """VX83 — Leads « chauds » (score élevé) JAMAIS contactés, pour la file de
    travail. Un lead à fort potentiel dont ``first_contacted_at`` est NULL est
    une opportunité qui dort. Portée de visibilité de l'utilisateur respectée
    (``scope_queryset(..., ['owner'])``). Lecture seule, scopée société.

    ``seuil_score`` par défaut = 60 (« chaud » sur l'échelle 0-100 de QJ6). Un
    lead archivé/perdu/déjà signé est exclu (funnel via STAGES.py — règle #2).
    """
    from authentication.scoping import scope_queryset
    from . import stages as stage_mod
    from .models import Lead

    seuil = 60 if seuil_score is None else seuil_score
    qs = Lead.objects.filter(
        company=company, is_archived=False, perdu=False,
        first_contacted_at__isnull=True, score__gte=seuil,
    ).exclude(stage__in=(stage_mod.SIGNED, stage_mod.COLD))
    qs = scope_queryset(qs, user, ['owner'])
    return qs.order_by('-score', 'date_creation')


def devis_expirant_bientot(company, user, dans_jours=7, today=None):
    """VX83 — Devis au statut ``envoye`` dont la validité expire dans les
    ``dans_jours`` prochains jours (ou déjà expirés mais encore ``envoye``),
    pour la file de travail. Lu via la relation ``lead.devis`` déjà dans le
    domaine crm (JAMAIS un import de ``apps.ventes.models`` — même patron que
    ``attribution_leads``/``revenu_attribue_campagne``). Portée de visibilité
    respectée (le devis suit le ``owner`` de son lead). Lecture seule.

    Renvoie une liste de dicts ``{devis_id, reference, lead_id, lead_nom,
    date_expiration, total_ttc}``.
    """
    import datetime
    from core.dates import aujourd_hui_local
    from authentication.scoping import scope_queryset
    from .models import Lead

    today = today or aujourd_hui_local()
    limite = today + datetime.timedelta(days=dans_jours)
    leads = scope_queryset(
        Lead.objects.filter(company=company, is_archived=False),
        user, ['owner']).prefetch_related('devis')

    out = []
    for lead in leads:
        for devis in lead.devis.all():
            if getattr(devis, 'statut', None) != 'envoye':
                continue
            exp = getattr(devis, 'date_expiration', None) or getattr(
                devis, 'date_validite', None)
            if exp is None or exp > limite:
                continue
            out.append({
                'devis_id': devis.id,
                'reference': getattr(devis, 'reference', '') or f'#{devis.id}',
                'lead_id': lead.id,
                'lead_nom': f'{lead.nom} {lead.prenom or ""}'.strip(),
                'date_expiration': exp,
                'total_ttc': str(getattr(devis, 'total_ttc', None) or ''),
            })
    out.sort(key=lambda d: (d['date_expiration'], d['reference']))
    return out


def leads_rappel_demande(company, user):
    """VX223 — Leads ayant demandé un RAPPEL téléphonique
    (``contact_preference=='phone_ok'``), le signal le plus chaud du pipeline
    jusqu'ici réduit à un badge PASSIF sur ``LeadCard`` (aucune file ne
    l'alimentait). Exclut perdu/archivé (funnel via STAGES.py — règle #2).
    Portée de visibilité de l'utilisateur respectée (``scope_queryset(...,
    ['owner'])``, même convention que ``relances_du_jour``/
    ``leads_chauds_non_contactes``). Lecture seule, scopée société.
    """
    from authentication.scoping import scope_queryset
    from .models import Lead

    qs = Lead.objects.filter(
        company=company, is_archived=False, perdu=False,
        contact_preference='phone_ok',
    )
    qs = scope_queryset(qs, user, ['owner'])
    return qs.order_by('-date_creation')


def ma_file_commercial_items(company, user, today=None):
    """VX83 — Items COMMERCIAUX normalisés de la « Ma file » d'un utilisateur,
    prêts pour l'union cross-module de ``records`` (aucun agrégateur dupliqué
    côté records : il consomme CE point d'entrée). Chaque item est un dict
    ``{kind, title, due, link, urgency, montant?}`` — contrat commun à toutes
    les familles de la file. Lecture seule, scopée société + visibilité.

    Quatre familles réunies :
      * relances dues (FG31, ``relances_du_jour`` scope ``overdue`` — en retard
        seulement, l'urgence de la file) ;
      * leads chauds jamais contactés (``leads_chauds_non_contactes``) ;
      * devis ``envoye`` proches d'expiration (``devis_expirant_bientot``) ;
      * VX223 — rappels demandés (``leads_rappel_demande``), famille que VX83
        n'énumérait pas : ``kind='rappel'``, ``urgency='high'`` (ni
        ``overdue`` ni ``today`` — un rappel demandé n'a pas d'échéance
        propre ; le tri de ``records.views.ActivityViewSet.ma_file`` retombe
        sur son rang par défaut pour toute urgence inconnue — hors périmètre
        de cette tâche, cf. ``FilterBar.jsx`` qui expose le même signal en
        chip dédiée, cliquable indépendamment de « Ma file »).
    """
    from core.dates import aujourd_hui_local
    today = today or aujourd_hui_local()
    items = []

    for lead in relances_du_jour(company, user, scope='overdue', today=today):
        nom = f'{lead.nom} {lead.prenom or ""}'.strip() or f'Lead #{lead.id}'
        items.append({
            'kind': 'relance',
            'title': f'Relancer {nom}',
            'due': lead.relance_date,
            'link': f'/crm/leads?lead={lead.id}',
            'urgency': 'overdue',
        })

    for lead in leads_chauds_non_contactes(company, user):
        nom = f'{lead.nom} {lead.prenom or ""}'.strip() or f'Lead #{lead.id}'
        items.append({
            'kind': 'lead_chaud',
            'title': f'Contacter {nom} (chaud, jamais contacté)',
            'due': None,
            'link': f'/crm/leads?lead={lead.id}',
            'urgency': 'today',
        })

    for d in devis_expirant_bientot(company, user, today=today):
        expire = d['date_expiration'] < today
        items.append({
            'kind': 'devis_expire',
            'title': f'Devis {d["reference"]} — {d["lead_nom"]} '
                     f'{"expiré" if expire else "expire bientôt"}',
            'due': d['date_expiration'],
            'link': f'/crm/leads?lead={d["lead_id"]}',
            'urgency': 'overdue' if expire else 'today',
            'montant': d['total_ttc'] or None,
        })

    # VX223 — rappels demandés : signal le plus chaud du pipeline (un client a
    # explicitement demandé un rappel), jusqu'ici un badge passif jamais
    # remonté dans aucune file.
    for lead in leads_rappel_demande(company, user):
        nom = f'{lead.nom} {lead.prenom or ""}'.strip() or f'Lead #{lead.id}'
        items.append({
            'kind': 'rappel',
            'title': f'Rappeler {nom} (rappel demandé)',
            'due': None,
            'link': f'/crm/leads?lead={lead.id}',
            'urgency': 'high',
        })

    return items


def lead_chatter_envelope(lead, user=None):
    """ARC9 — timeline chatter du lead dans l'ENVELOPPE UNIFORME.

    Étape 1 (additive) de la convergence des chatters historiques : projette
    ``crm.LeadActivity`` vers le format commun consommé par
    ``records.serializers.UniformChatterSerializer`` (un seul contrat de
    lecture pour le frontend, quel que soit le modèle source). Lecture seule —
    AUCUNE table modifiée. Le queryset est déjà borné par le lead (lui-même
    borné société par l'appelant).

    CRX19 — ``user`` optionnel : quand il est fourni, ``old_value``/
    ``new_value`` d'une entrée portant sur une PII du lead sont masqués par la
    MÊME règle que le sérialiseur d'activité (source unique
    ``serializers.masquer_valeurs_chatter``) — sinon cette troisième surface
    resservait en clair ce que les deux autres masquent. ``user=None`` (appel
    interne, ex. ``records.services`` qui ne lit que ``created_at``) laisse le
    rendu HISTORIQUE strictement inchangé. TOUTE surface HTTP qui exposera
    cette enveloppe DOIT passer l'utilisateur de la requête.
    """
    from .serializers import masquer_valeurs_chatter

    rows = lead.activites.select_related('user').all()
    sortie = []
    for a in rows:
        old_value, new_value = masquer_valeurs_chatter(
            a.field or '', a.old_value or '', a.new_value or '', user)
        sortie.append({
            'id': a.id,
            'kind': a.kind,
            'field': a.field or '',
            'field_label': a.field_label or '',
            'old_value': old_value,
            'new_value': new_value,
            'body': a.body or '',
            'user_username': a.user.username if a.user_id else None,
            'created_at': a.created_at,
            'source': 'crm.leadactivity',
        })
    return sortie


# ── CRX37 — Jalons devis dans l'historique du lead ───────────────────────────

#: CRX37 — ``kind`` renvoyé par ``ventes.selectors.devis_events_for_lead`` →
#: ``kind`` du chatter, celui que ``ChatterTimeline`` sait DÉJÀ rendre
#: (📤/👁️/✅/❌) et que ``matchesTimelineFilter`` range sous le filtre
#: « Devis ». Le rendu existait des deux côtés ; il ne manquait que la source.
_KIND_DEVIS_VERS_CHATTER = {
    'sent': 'devis_sent',
    'opened': 'devis_opened',
    'signed': 'devis_signed',
    'refused': 'devis_refused',
}


def lead_jalons_devis(lead):
    """CRX37 — jalons du cycle de vie des devis d'un lead, projetés dans la
    forme du chatter (contrat ``apps/crm/contract_samples/lead_jalons_devis.json``).

    Le sélecteur ``apps.ventes.selectors.devis_events_for_lead`` (QX32be) a été
    écrit pour ça et n'avait AUCUN appelant : le commercial ne voyait donc
    jamais « devis envoyé / proposition ouverte / signé / refusé » dans
    l'historique du lead, alors que ``ChatterTimeline`` sait rendre ces quatre
    ``kind`` depuis QX32 et que le filtre « Devis » de la timeline existe déjà.

    Lecture seule, cross-app par le SÉLECTEUR de l'app cible (jamais un import
    de ``apps.ventes.models``), bornée à la société du lead. Aucun montant :
    la timeline montre des JALONS, pas des prix (et jamais de ``prix_achat``).

    Chaque entrée porte la forme d'une ligne de chatter — ``id`` textuel et
    STABLE (aucune collision avec les ``id`` numériques de ``LeadActivity``,
    que le frontend fusionne dans la même liste), ``kind`` ``devis_*``,
    ``body`` lisible, ``created_at`` ISO.
    """
    from apps.ventes import selectors as ventes_selectors

    if lead is None or not getattr(lead, 'pk', None):
        return []
    evenements = ventes_selectors.devis_events_for_lead(lead.pk, lead.company)

    lignes = []
    for evenement in evenements:
        kind = _KIND_DEVIS_VERS_CHATTER.get(evenement.get('kind'))
        if kind is None:
            continue
        reference = evenement.get('reference') or ''
        lignes.append({
            'id': f"devis-{evenement.get('devis_id')}-{evenement.get('kind')}",
            'kind': kind,
            'body': reference,
            'created_at': evenement.get('at'),
            'devis_id': evenement.get('devis_id'),
            'reference': reference,
            'user_nom': None,
            'pinned': False,
        })
    return lignes


# ── ADSENG31 — Réconciliation Meta-vs-ERP : lignes de lead par mécanisme ──────

def reconciliation_lead_rows(company, *, date_start=None, date_end=None):
    """ADSENG31 — Lignes d'un lead pour la RÉCONCILIATION Meta-vs-ERP (dd-
    attribution part b). Point d'entrée cross-app SANCTIONNÉ pour
    ``apps.adsengine`` (le CRM est lu UNIQUEMENT via ce sélecteur, jamais un
    import de ``apps.crm.models``).

    Chaque ligne porte de quoi classer le lead par MÉCANISME DE CAPTURE (les deux
    dénominateurs que la réconciliation ne fusionne jamais) et de quoi le
    rapprocher d'une campagne + le dédupliquer :

      * ``is_meta_form``      — formulaire Meta Lead Ads (``source=meta_lead_ads``,
        appariable 1:1 via leadgen_id) ;
      * ``is_site``           — lead du site (``source=site_web``) — Meta-attribué
        seulement si son canal/utm indique Meta (l'appelant tranche) ;
      * ``is_ctwa``           — canal WhatsApp/CTWA (auto-déclaré, JAMAIS confirmé
        côté Meta — montré à part) ;
      * ``is_meta_ads_canal`` — canal « Publicité Meta » ;
      * ``phone_key``/``email_key`` — clés NORMALISÉES QW10 (réutilise
        ``services.normalize_phone``/``normalize_email``) pour dédupliquer sans
        recompter un payload webhook brut (dd-attribution §3.3) ;
      * ``utm_campaign``/``meta_campaign_id`` — clés de rapprochement de campagne.

    Lecture seule, scopée société ; ne compte jamais un lead archivé.
    ``date_start``/``date_end`` (date, inclus) bornent ``date_creation`` ;
    ``None`` = pas de borne. Renvoie une LISTE de dicts (données pures)."""
    from . import services as crm_services
    from .models import Lead

    qs = Lead.objects.filter(company=company, is_archived=False)
    if date_start is not None:
        qs = qs.filter(date_creation__date__gte=date_start)
    if date_end is not None:
        qs = qs.filter(date_creation__date__lte=date_end)

    meta_form = Lead.Source.META_LEAD_ADS
    site_source = Lead.Source.SITE_WEB
    ctwa_canal = Lead.Canal.WHATSAPP_CTWA
    meta_canal = Lead.Canal.META_ADS

    rows = []
    for lead in qs.only(
            'id', 'utm_campaign', 'utm_source', 'meta_campaign_id',
            'source', 'canal', 'telephone', 'email', 'date_creation'):
        rows.append({
            'id': lead.id,
            'utm_campaign': lead.utm_campaign or '',
            'utm_source': (lead.utm_source or '').strip().lower(),
            'meta_campaign_id': lead.meta_campaign_id or '',
            'source': lead.source or '',
            'is_meta_form': lead.source == meta_form,
            'is_site': lead.source == site_source,
            'is_ctwa': lead.canal == ctwa_canal,
            'is_meta_ads_canal': lead.canal == meta_canal,
            'phone_key': crm_services.normalize_phone(lead.telephone),
            'email_key': crm_services.normalize_email(lead.email),
            'date': lead.date_creation.date() if lead.date_creation else None,
        })
    return rows


# ── ADSENG32 — Émetteur CAPI CRM-stage : contexte lead borné société ──────────

# Valeur d'``external_system`` d'un lead issu d'un formulaire Meta Lead Ads : son
# ``external_id`` EST alors le leadgen_id Meta (clé de match préférée, cf.
# services._META_LEAD_ADS_SYSTEM). Constante locale pour éviter d'importer les
# services CRM sur ce chemin de lecture.
_META_LEAD_ADS_SYSTEM = 'meta_lead_ads'


def pipeline_stage_order():
    """ADSENG32 — Ordre canonique des étapes + repères SIGNED/COLD, depuis
    ``STAGES.py`` (jamais codés en dur côté adsengine — règle #2). Point d'entrée
    cross-app pour que ``apps.adsengine`` détecte une transition AVANT (rang qui
    augmente) sans importer ``apps.crm.models`` ni ``STAGES.py`` directement.

    Renvoie ``{'stages': [...], 'funnel': [...], 'signed': str, 'cold': str,
    'quote_sent': str}`` où ``funnel`` = les étapes AVANT-ordonnées hors COLD
    (« Perdu » n'est pas une étape). PUB31 ajoute ``quote_sent`` (additif) :
    permet à ``adsengine.capi_crm`` de détecter la transition QUOTE_SENT sans
    jamais importer ``apps.crm.stages`` directement (règle #2)."""
    from . import stages as stage_mod
    order = list(stage_mod.STAGES)
    return {
        'stages': order,
        'funnel': [k for k in order if k != stage_mod.COLD],
        'signed': stage_mod.SIGNED,
        'cold': stage_mod.COLD,
        'quote_sent': stage_mod.QUOTE_SENT,
    }


def lead_current_stage(company, lead_id):
    """ADSENG32 — Étape COURANTE (clé STAGES.py) d'un lead borné société, ou
    None. Point d'entrée cross-app LECTURE SEULE : appelé en ``pre_save`` par
    l'émetteur CAPI CRM-stage pour capturer l'ANCIENNE étape (la base porte
    encore l'ancienne valeur) et n'émettre que sur une VRAIE transition."""
    if not lead_id:
        return None
    from .models import Lead
    return (Lead.objects
            .filter(pk=lead_id, company=company)
            .values_list('stage', flat=True)
            .first())


def lead_capi_identifiers(company, lead_id):
    """ADSENG32 — Identifiants de MATCH d'un lead borné société pour le CAPI
    CRM-stage (Conversion Leads), ou None si hors société. Point d'entrée cross-
    app LECTURE SEULE (jamais un import de ``apps.crm.models`` côté adsengine).

    Renvoie ``{'lead_id', 'leadgen_id', 'phone', 'email', 'fbclid',
    'is_meta_origin'}`` : ``leadgen_id`` = ``external_id`` quand
    ``external_system == 'meta_lead_ads'`` (clé de match Meta préférée) ; sinon
    ''. ``phone``/``email`` sont bruts (le HACHAGE SHA-256 se fait côté émetteur,
    jamais ici — on n'expose pas de PII hachée en dur). ``is_meta_origin`` =
    lead issu d'un canal/source Meta (éligible à l'intégration). Ne renvoie
    JAMAIS de donnée interne (aucun prix_achat n'existe côté lead)."""
    if not lead_id:
        return None
    from .models import Lead
    lead = (Lead.objects
            .filter(pk=lead_id, company=company)
            .only('id', 'external_system', 'external_id', 'telephone', 'email',
                  'fbclid', 'canal', 'source')
            .first())
    if lead is None:
        return None
    leadgen_id = ''
    if lead.external_system == _META_LEAD_ADS_SYSTEM and lead.external_id:
        leadgen_id = str(lead.external_id)
    meta_canaux = {Lead.Canal.META_ADS, Lead.Canal.WHATSAPP_CTWA}
    is_meta_origin = (
        lead.canal in meta_canaux
        or lead.source == _META_LEAD_ADS_SYSTEM
        or bool(leadgen_id) or bool(lead.fbclid))
    return {
        'lead_id': lead.id,
        'leadgen_id': leadgen_id,
        'phone': lead.telephone or '',
        'email': lead.email or '',
        'fbclid': lead.fbclid or '',
        'is_meta_origin': is_meta_origin,
    }


def meta_lead_match_coverage(company):
    """ADSENG32 — Couverture de MATCH des leads Meta de la société (moniteur EMQ
    LOCAL, sans appel réseau). Point d'entrée cross-app LECTURE SEULE : donne au
    moniteur EMQ d'``apps.adsengine`` une estimation de la qualité de match
    ATTENDUE (quelle proportion des leads Meta porte un identifiant fort :
    leadgen_id ou téléphone) sans exposer les modèles crm.

    Le score EMQ réel (0-10) exige l'API Dataset Quality de Meta (séparée) ; ce
    proxy local rend « visible » la qualité de match côté ERP en attendant.
    Renvoie ``{'meta_leads', 'with_leadgen_id', 'with_phone', 'strong_match'}``."""
    from .models import Lead
    meta_canaux = {Lead.Canal.META_ADS, Lead.Canal.WHATSAPP_CTWA}
    qs = Lead.objects.filter(company=company, is_archived=False).only(
        'external_system', 'external_id', 'telephone', 'canal', 'source')
    meta_leads = with_leadgen = with_phone = strong = 0
    for lead in qs:
        is_meta = (lead.canal in meta_canaux
                   or lead.source == _META_LEAD_ADS_SYSTEM)
        if not is_meta:
            continue
        meta_leads += 1
        has_leadgen = (lead.external_system == _META_LEAD_ADS_SYSTEM
                       and bool(lead.external_id))
        has_phone = bool(lead.telephone)
        if has_leadgen:
            with_leadgen += 1
        if has_phone:
            with_phone += 1
        if has_leadgen or has_phone:
            strong += 1
    return {
        'meta_leads': meta_leads,
        'with_leadgen_id': with_leadgen,
        'with_phone': with_phone,
        'strong_match': strong,
    }


# ── ADSENG33 — Drill-down reporting : lignes de lead (entonnoir + cohortes) ────

def reporting_lead_rows(company, *, date_start=None, date_end=None):
    """ADSENG33 — Lignes de lead pour les drill-downs de reporting (entonnoir par
    campagne + cohortes de signature). Point d'entrée cross-app SANCTIONNÉ pour
    ``apps.adsengine`` (le CRM est lu UNIQUEMENT via ce sélecteur, jamais un
    import de ``apps.crm.models``).

    Chaque ligne porte l'étape courante (clé STAGES.py), le drapeau ``perdu``, la
    clé de campagne (``meta_campaign_id``/``utm_campaign``), la date de création,
    et — pour le lag de signature (dd-attribution §5.3) — la DATE de signature :
    la plus ANCIENNE ``date_acceptation`` parmi les devis ACCEPTÉS du lead (lus
    via la relation ``lead.devis`` déjà dans le domaine crm, JAMAIS un import de
    ``apps.ventes.models`` — même patron que ``attribution_leads``). None si le
    lead n'a pas de devis accepté (un lead au stade SIGNÉ sans devis n'a pas
    d'horodatage de signature → lag indéterminé, jamais fabriqué).

    PUB38 — ``ville`` (brute, non normalisée) est incluse pour le harnais
    d'incrémentalité geo-holdout d'``apps.adsengine`` (zone tenue vs zones
    actives) ; additif, ignoré des consommateurs existants (entonnoir/cohortes).

    Lecture seule, scopée société ; jamais un lead archivé. ``date_start``/
    ``date_end`` (date, inclus) bornent ``date_creation``. Renvoie une LISTE de
    dicts (données pures)."""
    from .models import Lead

    qs = Lead.objects.filter(company=company, is_archived=False)
    if date_start is not None:
        qs = qs.filter(date_creation__date__gte=date_start)
    if date_end is not None:
        qs = qs.filter(date_creation__date__lte=date_end)

    meta_canaux = {Lead.Canal.META_ADS, Lead.Canal.WHATSAPP_CTWA}
    rows = []
    for lead in qs.prefetch_related('devis'):
        accept_dates = [
            d.date_acceptation for d in lead.devis.all()
            if getattr(d, 'statut', None) == 'accepte' and d.date_acceptation]
        signature_date = min(accept_dates) if accept_dates else None
        rows.append({
            'id': lead.id,
            'utm_campaign': lead.utm_campaign or '',
            'meta_campaign_id': lead.meta_campaign_id or '',
            'stage': lead.stage,
            'perdu': bool(lead.perdu),
            'is_meta_channel': lead.canal in meta_canaux,
            'created_date': (lead.date_creation.date()
                             if lead.date_creation else None),
            'signature_date': signature_date,
            'ville': lead.ville or '',
        })
    return rows


# ── PUB72 — Mine d'objections (motif_perte + notes chatter) ──────────────────

def objection_mining_rows(company):
    """PUB72 — Lignes texte-libre PAR LEAD pour la mine d'objections
    (``apps.adsengine.comment_mining.mine_ad_objections``) : ``motif_perte`` +
    le corps des activités de chatter texte-libre (notes/appels/e-mails —
    JAMAIS les entrées structurées création/modification, qui ne portent pas
    d'objection), avec les MÊMES clés d'attribution que
    ``attribution_lead_rows`` (``meta_ad_id``/``utm_content``/
    ``utm_campaign``) pour permettre la résolution PAR VARIANTE d'annonce en
    aval. Point d'entrée cross-app SANCTIONNÉ pour ``apps.adsengine`` (le CRM
    est lu UNIQUEMENT via ce sélecteur, jamais un import de
    ``apps.crm.models``). Lecture seule, scopée société ; jamais un lead
    archivé. Renvoie une LISTE de dicts (jamais un queryset de modèles)."""
    from .models import Lead, LeadActivity

    qs = (Lead.objects
          .filter(company=company, is_archived=False)
          .only('id', 'meta_ad_id', 'utm_content', 'utm_campaign', 'canal',
                'motif_perte'))
    leads = list(qs)
    lead_ids = [lead.id for lead in leads]

    notes_by_lead = {}
    if lead_ids:
        text_kinds = (LeadActivity.Kind.NOTE, LeadActivity.Kind.APPEL,
                      LeadActivity.Kind.EMAIL)
        activities = (LeadActivity.objects
                      .filter(lead_id__in=lead_ids, kind__in=text_kinds)
                      .only('lead_id', 'body'))
        for act in activities:
            if act.body:
                notes_by_lead.setdefault(act.lead_id, []).append(act.body)

    meta_channels = {Lead.Canal.META_ADS, Lead.Canal.WHATSAPP_CTWA}
    rows = []
    for lead in leads:
        rows.append({
            'id': lead.id,
            'meta_ad_id': lead.meta_ad_id or '',
            'utm_content': lead.utm_content or '',
            'utm_campaign': lead.utm_campaign or '',
            'is_meta_channel': lead.canal in meta_channels,
            'motif_perte': lead.motif_perte or '',
            'notes': notes_by_lead.get(lead.id, []),
        })
    return rows


def organic_referral_lead_series(company, *, date_start=None, date_end=None):
    """PUB95 — Comptes QUOTIDIENS de leads par CATÉGORIE de canal, pour la
    détection de cannibalisation par ``apps.adsengine`` (« les pubs créent-elles
    des leads ou déplacent-elles l'organique ? »). Point d'entrée cross-app
    LECTURE SEULE (jamais un import de ``apps.crm.models`` côté adsengine).

    Ne renvoie que des COMPTES par catégorie — ``paid`` (Meta/CTWA, piloté par la
    dépense pub), ``referral`` (parrainage / référence), ``organic`` (tout le reste
    non payant) — jamais la taxonomie de canal crm brute (même discipline que
    ``attribution_lead_rows``). Scopé société ; jamais un lead archivé.
    ``date_start``/``date_end`` (date, inclus) bornent ``date_creation``. Renvoie
    ``{'YYYY-MM-DD': {'paid': int, 'organic': int, 'referral': int}}``."""
    from .models import Lead

    qs = Lead.objects.filter(company=company, is_archived=False)
    if date_start is not None:
        qs = qs.filter(date_creation__date__gte=date_start)
    if date_end is not None:
        qs = qs.filter(date_creation__date__lte=date_end)

    paid_canaux = {Lead.Canal.META_ADS, Lead.Canal.WHATSAPP_CTWA}
    referral_canaux = {Lead.Canal.REFERENCE}

    series = {}
    for lead in qs.only('canal', 'date_creation'):
        if not lead.date_creation:
            continue
        key = lead.date_creation.date().isoformat()
        slot = series.setdefault(key, {'paid': 0, 'organic': 0, 'referral': 0})
        if lead.canal in paid_canaux:
            slot['paid'] += 1
        elif lead.canal in referral_canaux:
            slot['referral'] += 1
        else:
            slot['organic'] += 1
    return series


def lead_criteria_for_territoire(company, lead_id):
    """NTCRM1 — Contexte plat de matching territoire pour un lead réel,
    exposé aux AUTRES apps (``apps.territoires.views``) au lieu d'un import
    direct de ``apps.crm.models`` — jamais cross-tenant : ``None`` si le lead
    n'existe pas ou appartient à une autre société."""
    from .models import Lead

    try:
        lead = Lead.objects.get(pk=lead_id, company=company)
    except (Lead.DoesNotExist, ValueError, TypeError):
        return None
    return {
        'ville': lead.ville,
        'type_installation': lead.type_installation,
        'montant_estime': lead.montant_estime,
        'canal': lead.canal,
    }


def leads_recents_pour_couverture(company, jours=30):
    """NTCRM25 — Leads récents (``jours`` derniers jours) de ``company``, avec
    leur contexte plat de matching territoire (même forme que
    ``lead_criteria_for_territoire``), exposés à ``apps.territoires`` pour le
    rapport de couverture — jamais un import direct de ``apps.crm.models``
    depuis l'appelant."""
    from django.utils import timezone

    from .models import Lead

    depuis = timezone.now() - timezone.timedelta(days=jours)
    leads = Lead.objects.filter(company=company, date_creation__gte=depuis)
    return [
        {
            'id': lead.id,
            'nom': getattr(lead, 'nom', '') or getattr(lead, 'prenom', '') or f'Lead #{lead.id}',
            'ville': lead.ville,
            'type_installation': lead.type_installation,
            'montant_estime': lead.montant_estime,
            'canal': lead.canal,
        }
        for lead in leads
    ]


def forecast_rollup(company, periode=None, manager=None):
    """NTCRM5 — Roll-up hiérarchique du forecast : par commercial → par
    équipe (``EquipeCommerciale`` existant, FG39 voisin) → total société.

    ``periode`` (optionnel) : ``{'period_type': 'month'|'quarter'|'year',
    'period_year': int, 'period_month': int|None, 'period_quarter': int|None}``
    — restreint aux leads dont ``date_cloture_prevue`` tombe dans cette
    fenêtre ; ``None`` = tous les leads (comportement par défaut). ``manager``
    (optionnel, un ``CustomUser``) : restreint aux équipes qu'il dirige
    (``EquipeCommerciale.responsable``) — sans lui, agrège TOUTES les équipes
    de la société (vue Directeur).

    AUCUNE duplication avec ``ObjectifCommercial`` (FG39) : le roll-up
    AGRÈGE les montants forecast des ``ForecastEntry`` (NTCRM4, repli sur le
    devis actif le plus récent puis ``Lead.montant_estime``) ; l'objectif
    reste la cible séparée, comparée en sortie via ``ecart_vs_objectif``
    (somme des cibles CA_SIGNE individuelles des membres de l'équipe pour la
    même période, si au moins une existe — sinon ``None``, jamais fabriqué).
    """
    from decimal import Decimal

    from .models import EquipeCommerciale, ForecastEntry, ObjectifCommercial

    def _in_periode(lead):
        if periode is None:
            return True
        d = lead.date_cloture_prevue
        if d is None:
            return False
        if d.year != periode.get('period_year'):
            return False
        ptype = periode.get('period_type', 'month')
        if ptype == 'month':
            return d.month == periode.get('period_month')
        if ptype == 'quarter':
            quarter = (d.month - 1) // 3 + 1
            return quarter == periode.get('period_quarter')
        return True  # 'year' — l'année a déjà matché ci-dessus

    entries = (
        ForecastEntry.objects.filter(company=company)
        .select_related('lead', 'lead__owner')
    )

    by_owner = {}  # owner_id -> {'nom': str, 'totals': {categorie: Decimal}}
    for entry in entries:
        lead = entry.lead
        owner = getattr(lead, 'owner', None)
        if owner is None or not _in_periode(lead):
            continue
        bucket = by_owner.setdefault(
            owner.id, {'owner_id': owner.id, 'nom': owner.username, 'totals': {}})
        bucket['totals'][entry.categorie] = (
            bucket['totals'].get(entry.categorie, Decimal('0'))
            + (entry.montant_effectif or Decimal('0')))

    equipes_qs = EquipeCommerciale.objects.filter(company=company, actif=True)
    if manager is not None:
        equipes_qs = equipes_qs.filter(responsable=manager)

    def _cible_equipe(membre_ids):
        """Somme des cibles CA_SIGNE individuelles des membres pour la
        période demandée (None si aucune n'existe — jamais fabriquée)."""
        qs = ObjectifCommercial.objects.filter(
            company=company, owner_id__in=membre_ids,
            metric=ObjectifCommercial.Metric.CA_SIGNE)
        if periode is not None:
            qs = qs.filter(
                period_type=periode.get('period_type', 'month'),
                period_year=periode.get('period_year'))
            if periode.get('period_type', 'month') == 'month':
                qs = qs.filter(period_month=periode.get('period_month'))
            elif periode.get('period_type') == 'quarter':
                qs = qs.filter(period_quarter=periode.get('period_quarter'))
        cibles = list(qs.values_list('cible', flat=True))
        return sum(cibles) if cibles else None

    equipes_out = []
    # Total société = TOUS les commerciaux avec un forecast, appartenant ou
    # non à une équipe (jamais restreint aux seules équipes retournées quand
    # `manager` filtre — le total société reste le total société).
    total_societe = {}
    for com in by_owner.values():
        for cat, amt in com['totals'].items():
            total_societe[cat] = total_societe.get(cat, Decimal('0')) + amt

    for equipe in equipes_qs.prefetch_related('membres'):
        membre_ids = list(equipe.membres.values_list('id', flat=True))
        commerciaux = [by_owner[uid] for uid in membre_ids if uid in by_owner]
        totals = {}
        for com in commerciaux:
            for cat, amt in com['totals'].items():
                totals[cat] = totals.get(cat, Decimal('0')) + amt
        cible = _cible_equipe(membre_ids)
        total_equipe = sum(totals.values()) if totals else Decimal('0')
        equipes_out.append({
            'equipe_id': equipe.id,
            'nom': equipe.nom,
            'commerciaux': commerciaux,
            'totals': totals,
            'total': total_equipe,
            'cible_objectif': cible,
            'ecart_vs_objectif': (total_equipe - cible) if cible is not None else None,
        })

    return {'equipes': equipes_out, 'total_societe': total_societe}


def revenu_pipeline_pondere_par_mois(company, mois_debut, mois_fin):
    """NTFPA11 — revenu prévisionnel PONDÉRÉ-PROBABILITÉ du pipeline CRM,
    agrégé par mois de clôture prévue (``Lead.date_cloture_prevue``).

    Sélecteur de LECTURE pour ``apps.fpa`` (driver revenu pipeline) : FP&A ne
    lit jamais ``crm.models`` directement. Pour chaque lead OUVERT (ni SIGNED,
    ni perdu) dont la clôture prévue tombe dans ``[mois_debut, mois_fin]``, la
    contribution du mois = Σ(valeur prévisionnelle × probabilité de gain), en
    réutilisant les scorers déjà en place dans ``apps.reporting.pipeline``
    (``_lead_forecast_value`` × ``_lead_win_weight``, core ``win_probability``)
    — jamais de logique dupliquée. Recalculé à la demande (aucun cache).

    Renvoie un dict ``{'YYYY-MM': Decimal}`` pour les seuls mois porteurs.
    """
    from decimal import Decimal

    from apps.reporting.pipeline import _lead_forecast_value, _lead_win_weight
    from . import stages as stage_mod
    from .models import Lead

    ouvertes = [
        k for k in stage_mod.STAGES if k not in (stage_mod.SIGNED, stage_mod.COLD)
    ]
    qs = (
        Lead.objects
        .filter(company=company, is_archived=False, perdu=False,
                stage__in=ouvertes,
                date_cloture_prevue__isnull=False,
                date_cloture_prevue__gte=mois_debut,
                date_cloture_prevue__lte=mois_fin)
        .prefetch_related('devis')
    )
    par_mois = {}
    for lead in qs:
        d = lead.date_cloture_prevue
        cle = f'{d.year:04d}-{d.month:02d}'
        contribution = _lead_forecast_value(lead) * _lead_win_weight(lead)
        par_mois[cle] = par_mois.get(cle, Decimal('0')) + contribution
    return par_mois


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


# ── PUB64 — Calculateur recyclage COLD (aide à la décision, pas une action) ──

# Buckets d'âge-au-COLD (jours). Le dernier segment est ouvert (180j+).
COLD_AGE_BUCKETS = (
    (0, 30, '0-30j'), (30, 90, '30-90j'), (90, 180, '90-180j'),
    (180, None, '180j+'),
)

# Jamais un taux de reconversion calculé sur un échantillon minuscule (bruit
# statistique) — sous ce seuil, ``rate`` reste ``None``.
MIN_SAMPLE_COLD_BUCKET = 3


def cold_reactivation_by_age_bucket(company):
    """PUB64 — Taux de reconversion RÉEL des leads passés COLD, par
    ÂGE-AU-COLD (date de création → PREMIÈRE entrée en COLD, lue dans le
    chatter ``LeadActivity`` field='stage' — les valeurs stockées sont les
    LIBELLÉS FR de ``STAGES.STAGE_LABELS``, jamais les clés brutes). Un lead
    sans trace d'entrée COLD explicite (créé directement COLD, activité non
    journalisée) est EXCLU — jamais un âge inventé. « Reconverti » = a
    quitté COLD au moins une fois ET est ACTUELLEMENT au stade SIGNED (non
    perdu).

    Un bucket avec <``MIN_SAMPLE_COLD_BUCKET`` leads renvoie ``rate=None``
    (bruit statistique, jamais un taux fabriqué). Renvoie une liste ordonnée
    ``[{'bucket', 'total', 'reconverted', 'rate'}, ...]``."""
    from . import stages as stage_mod
    from .models import Lead, LeadActivity

    cold_label = stage_mod.STAGE_LABELS[stage_mod.COLD]

    # Première entrée en COLD par lead (âge-au-COLD).
    first_cold_at = {}
    for row in (LeadActivity.objects
                .filter(lead__company=company,
                        kind=LeadActivity.Kind.MODIFICATION,
                        field='stage', new_value=cold_label)
                .order_by('lead_id', 'created_at')
                .values('lead_id', 'created_at')):
        first_cold_at.setdefault(row['lead_id'], row['created_at'])

    if not first_cold_at:
        return [{'bucket': label, 'total': 0, 'reconverted': 0, 'rate': None}
                for (_, _, label) in COLD_AGE_BUCKETS]

    # A quitté COLD au moins une fois (old_value=cold_label -> autre étape).
    left_cold_ids = set(
        LeadActivity.objects.filter(
            lead__company=company, kind=LeadActivity.Kind.MODIFICATION,
            field='stage', old_value=cold_label,
            lead_id__in=list(first_cold_at))
        .values_list('lead_id', flat=True))
    # Repli : certaines écritures historiques peuvent porter la clé brute
    # (jamais supposé, mais couvert honnêtement) — union, jamais un ET.
    left_cold_ids |= set(
        LeadActivity.objects.filter(
            lead__company=company, kind=LeadActivity.Kind.MODIFICATION,
            field='stage', old_value=stage_mod.COLD,
            lead_id__in=list(first_cold_at))
        .values_list('lead_id', flat=True))

    signed_now = set(
        Lead.objects.filter(
            id__in=list(first_cold_at), stage=stage_mod.SIGNED, perdu=False)
        .values_list('id', flat=True))
    reconverted_ids = left_cold_ids & signed_now

    creation_by_id = dict(
        Lead.objects.filter(id__in=list(first_cold_at))
        .values_list('id', 'date_creation'))

    buckets = {label: {'total': 0, 'reconverted': 0}
               for (_, _, label) in COLD_AGE_BUCKETS}
    for lead_id, cold_at in first_cold_at.items():
        created = creation_by_id.get(lead_id)
        if created is None or cold_at is None:
            continue
        age_days = (cold_at - created).days
        if age_days < 0:
            continue
        for lo, hi, label in COLD_AGE_BUCKETS:
            if age_days >= lo and (hi is None or age_days < hi):
                buckets[label]['total'] += 1
                if lead_id in reconverted_ids:
                    buckets[label]['reconverted'] += 1
                break

    result = []
    for (_, _, label) in COLD_AGE_BUCKETS:
        b = buckets[label]
        rate = (round(b['reconverted'] / b['total'], 4)
                if b['total'] >= MIN_SAMPLE_COLD_BUCKET else None)
        result.append({
            'bucket': label, 'total': b['total'],
            'reconverted': b['reconverted'], 'rate': rate,
        })
    return result


def new_leads_by_mode_meta(company, *, date_start, date_end):
    """PUB64 — Nombre de leads NOUVEAUX (créés sur ``[date_start, date_end]``)
    par ``type_installation``, restreint au canal Meta (META_ADS/
    WHATSAPP_CTWA) — le dénominateur du CAC-par-mode courant du calculateur
    de recyclage COLD. Un mode absent de la fenêtre est simplement absent du
    dict (jamais un 0 fabriqué). Renvoie ``{type_installation_ou_'': count}``."""
    from django.db.models import Count

    from .models import Lead

    meta_channels = [Lead.Canal.META_ADS, Lead.Canal.WHATSAPP_CTWA]
    rows = (Lead.objects
            .filter(company=company, canal__in=meta_channels,
                    date_creation__date__gte=date_start,
                    date_creation__date__lte=date_end)
            .values('type_installation')
            .annotate(n=Count('id')))
    return {(r['type_installation'] or ''): r['n'] for r in rows}


# ── NTPRT27 — Résumé self-service du PORTAIL PARTENAIRE ─────────────────────

def resume_portail_partenaire(company, partenaire_id):
    """NTPRT27 — Cartes résumé du tableau de bord partenaire.

    Point d'entrée cross-app UNIQUE de ``apps.portail`` (jamais un import de
    ``apps.crm.models`` depuis portail). Lecture SEULE, bornée au triplet
    (société, partenaire) : un ``partenaire_id`` absent renvoie des compteurs
    à zéro, JAMAIS ceux de la société entière.
    """
    from decimal import Decimal

    vide = {
        'partenaire_nom': '',
        'statut_onboarding': '',
        'soumissions_par_statut': {},
        'commissions_dues': '0',
        'commissions_payees': '0',
    }
    if company is None or not partenaire_id:
        return vide

    from .models import (
        CommissionPartenaire, Partenaire, SoumissionLeadPartenaire,
    )

    partenaire = (Partenaire.objects
                  .filter(company=company, pk=partenaire_id).first())
    if partenaire is None:
        return vide

    soumissions = {}
    for statut, _ in SoumissionLeadPartenaire.Statut.choices:
        soumissions[statut] = SoumissionLeadPartenaire.objects.filter(
            company=company, partenaire=partenaire, statut=statut).count()

    def _somme(statut):
        total = sum(
            (c.montant or Decimal('0') for c in CommissionPartenaire.objects
             .filter(company=company, partenaire=partenaire, statut=statut)),
            Decimal('0'))
        return str(total)

    # NB — « territoire assigné » (NTPRT27) n'est PAS servi ici :
    # ``TerritoireCommercial`` (FG236) porte un ``owner_user_id``, pas de
    # rattachement à un ``Partenaire``. Inventer ce lien serait un changement
    # de schéma que personne n'a demandé ; la carte reste absente tant que la
    # relation n'existe pas, plutôt que remplie d'un chiffre faux.
    return {
        'partenaire_nom': partenaire.nom,
        'statut_onboarding': partenaire.statut_onboarding or '',
        'soumissions_par_statut': soumissions,
        'commissions_dues': _somme(CommissionPartenaire.Statut.DUE),
        'commissions_payees': _somme(CommissionPartenaire.Statut.PAYEE),
    }


def pipeline_pondere_par_entite(company, entite_ids):
    """NTADM25 — pipeline PONDÉRÉ-PROBABILITÉ agrégé PAR ENTITÉ (NTADM2).

    Point d'entrée cross-app sanctionné pour ``apps.entites`` (vue consolidée
    « Groupe ») : FP&A/entités ne lisent jamais ``crm.models`` directement.
    RÉUTILISE les scorers déjà en place (``apps.reporting.pipeline.
    _lead_forecast_value`` × ``_lead_win_weight``, cf.
    ``revenu_pipeline_pondere_par_mois``) — aucune logique dupliquée.

    Renvoie ``{entite_id: {'pipeline': Decimal, 'nb_leads': int}}`` pour les
    seules entités porteuses de leads OUVERTS (ni signés, ni perdus, ni
    archivés).
    """
    from decimal import Decimal

    from apps.reporting.pipeline import _lead_forecast_value, _lead_win_weight

    from . import stages as stage_mod
    from .models import Lead

    ids = [i for i in (entite_ids or []) if i is not None]
    if not ids:
        return {}

    ouvertes = [
        k for k in stage_mod.STAGES
        if k not in (stage_mod.SIGNED, stage_mod.COLD)
    ]
    qs = (
        Lead.objects
        .filter(company=company, entite_id__in=ids, is_archived=False,
                perdu=False, stage__in=ouvertes)
        .prefetch_related('devis')
    )
    out = {}
    for lead in qs:
        entry = out.setdefault(
            lead.entite_id, {'pipeline': Decimal('0'), 'nb_leads': 0})
        entry['pipeline'] += _lead_forecast_value(lead) * _lead_win_weight(lead)
        entry['nb_leads'] += 1
    return out


# ── NTMIG26/27 — Fiches partenaires vues par la couche certification ────────
#
# Point d'entrée cross-app UNIQUE de ``apps.migration`` (jamais un import de
# ``apps.crm.models`` depuis migration). LECTURE SEULE : l'écriture de la fiche
# passe exclusivement par ``crm.services`` (cf. `poser_compteur_deploiements`).


def partenaire_pour_certification(company, partenaire_id):
    """Fiche partenaire d'une société, ou ``None`` — jamais cross-tenant."""
    if company is None or not partenaire_id:
        return None

    from .models import Partenaire

    return (Partenaire.objects
            .filter(company=company, pk=partenaire_id).first())


def partenaires_certifies_qs(company, *, niveau_min=None, specialite=None,
                             zone=None):
    """Queryset LECTURE SEULE des partenaires filtrés par la couche
    certification (annuaire interne NTMIG29).

    ``niveau_min`` — comme le tri — est évalué sur le RANG de l'échelle
    (``Partenaire.NIVEAUX_ORDONNES``), jamais alphabétiquement : en tri de
    chaînes « or » passerait AVANT « platine » et même avant « certifie ».
    """
    from django.db.models import Case, IntegerField, Value, When

    from .models import Partenaire

    if company is None:
        return Partenaire.objects.none()
    niveaux = list(Partenaire.NIVEAUX_ORDONNES)
    qs = Partenaire.objects.filter(company=company).annotate(
        rang_niveau=Case(
            *[When(niveau_certification=niveau, then=Value(rang))
              for rang, niveau in enumerate(niveaux)],
            default=Value(0), output_field=IntegerField()))
    if niveau_min:
        try:
            rang = niveaux.index(niveau_min)
        except ValueError:
            rang = 0
        qs = qs.filter(niveau_certification__in=niveaux[rang:])
    if specialite:
        # ``specialites`` est une liste JSON : le filtre porte sur
        # l'APPARTENANCE, jamais sur une égalité de chaîne.
        qs = qs.filter(specialites__contains=[specialite])
    if zone:
        qs = qs.filter(zone__iexact=zone)
    return qs.order_by('-rang_niveau', 'nom')


def specialites_partenaire_cles():
    """NTMIG31 — clés du référentiel FERMÉ des spécialités partenaire.

    Simple accès en lecture à la liste de clés déclarée par le modèle
    (``Partenaire.SPECIALITES_CLES``) — jamais un import de
    ``apps.crm.models`` depuis une autre app pour cette seule constante.
    """
    from .models import Partenaire

    return Partenaire.SPECIALITES_CLES


def certifications_expirantes(company, within_days=60):
    """NTMIG30 — partenaires dont la couche certification EXPIRE bientôt.

    Réutilise le PATTERN d'échéances RH (FG175/YHIRE8) — jamais son code : la
    fiche est ``crm.Partenaire``, une famille distincte de
    ``rh.selectors.certifications_expirantes`` (habilitations employés).
    Ne retient que les fiches avec un niveau de certification POSÉ (jamais
    ``aucun`` — rien à alerter pour un partenaire non certifié) ET une
    échéance renseignée tombant au plus tard dans ``within_days`` jours
    (aujourd'hui + ``within_days`` inclus), PAS ENCORE échue (une certification
    déjà expirée est visible directement sur l'annuaire NTMIG29 — cette alerte
    est un rappel PRÉVENTIF, pas un état). Toujours scopé société ; triée par
    échéance la plus proche.
    """
    from datetime import timedelta

    from core.dates import aujourd_hui_local

    from .models import Partenaire

    if company is None:
        return Partenaire.objects.none()
    try:
        within_days = int(within_days)
    except (TypeError, ValueError):
        within_days = 60
    if within_days < 0:
        within_days = 0
    today = aujourd_hui_local()
    limite = today + timedelta(days=within_days)
    return (Partenaire.objects
            .filter(company=company,
                    date_expiration_certification__isnull=False,
                    date_expiration_certification__gte=today,
                    date_expiration_certification__lte=limite)
            .exclude(niveau_certification=Partenaire.NiveauCertification.AUCUN)
            .order_by('date_expiration_certification', 'id'))


def _as_date(value):
    """Normalise un DateField/DateTimeField en `date` pour comparaison sûre."""
    if value is None:
        return None
    return value.date() if hasattr(value, 'date') else value


def portefeuille_commercial(company, user, now=None):
    """NTCRM29 — Comptes (``Client``) dont ``user`` est owner via AU MOINS un
    lead lié, triés par score d'engagement (NTCRM16) CROISSANT (les plus
    froids en premier — priorisation d'action). Chaque entrée porte
    ``plan_compte_id`` (``NTCRM10``, ``None`` si aucun plan de compte formel).
    Toujours scopé société + owner — jamais de fuite cross-tenant ni
    cross-commercial (aucun paramètre société/utilisateur accepté depuis la
    requête, seulement ``request.user``)."""
    from .engagement import compute_engagement_score, engagement_label
    from .models import Client, Lead

    if company is None or user is None:
        return []
    client_ids = (
        Lead.objects.filter(company=company, owner=user, client__isnull=False)
        .values_list('client_id', flat=True).distinct()
    )
    clients = Client.objects.filter(company=company, id__in=client_ids)
    out = []
    for client in clients:
        score = compute_engagement_score(client, now=now)
        plan_compte_id = client.plan_compte.id if hasattr(client, 'plan_compte') else None
        out.append({
            'client_id': client.id,
            'nom': str(client),
            'score': score,
            'label': engagement_label(score),
            'plan_compte_id': plan_compte_id,
        })
    out.sort(key=lambda r: r['score'])
    return out


def comptes_dormants(company, seuil_jours=90, now=None):
    """NTCRM14 — Clients avec au moins un devis/facture passé mais AUCUNE
    activité (dernier devis créé, dernière facture émise, dernier
    `LeadActivity`, dernier `PointContact` sur un lead lié) depuis plus de
    `seuil_jours`.

    Réutilise `apps.ventes.selectors` via import function-local (frontière
    cross-app respectée — jamais `apps.ventes.models`). Un client sans AUCUN
    devis/facture n'est jamais considéré dormant (rien à réactiver). Renvoie
    une liste de dicts `{'client', 'derniere_activite', 'jours_inactivite'}`
    triée par inactivité décroissante. Lecture seule."""
    from django.utils import timezone

    from apps.ventes.selectors import (
        devis_du_client_portail, factures_du_client_portail,
    )

    from .models import Client, Lead, LeadActivity, PointContact

    if company is None:
        return []
    now = now or timezone.now()
    today = now.date() if hasattr(now, 'date') else now

    out = []
    for client in Client.objects.filter(company=company):
        devis_list = devis_du_client_portail(company, client.id, limit=1)
        factures_list = factures_du_client_portail(company, client.id, limit=1)
        if not devis_list and not factures_list:
            continue  # jamais de devis/facture : hors périmètre de la dormance

        dates = []
        if devis_list:
            dates.append(_as_date(devis_list[0]['date_creation']))
        if factures_list:
            dates.append(_as_date(factures_list[0]['date_emission']))

        lead_ids = list(Lead.objects.filter(
            company=company, client=client).values_list('id', flat=True))
        if lead_ids:
            last_activity = (
                LeadActivity.objects
                .filter(lead_id__in=lead_ids)
                .order_by('-created_at')
                .values_list('created_at', flat=True).first())
            dates.append(_as_date(last_activity))
            last_contact = (
                PointContact.objects
                .filter(lead_id__in=lead_ids)
                .order_by('-date_contact')
                .values_list('date_contact', flat=True).first())
            dates.append(_as_date(last_contact))

        dates = [d for d in dates if d is not None]
        derniere = max(dates) if dates else None
        jours = (today - derniere).days if derniere is not None else None
        dormant = derniere is None or jours >= seuil_jours
        if dormant:
            out.append({
                'client': client,
                'derniere_activite': derniere,
                'jours_inactivite': jours,
            })

    out.sort(
        key=lambda r: (r['jours_inactivite'] is None, r['jours_inactivite'] or 0),
        reverse=True)
    return out


def salle_vente_analytics(salle):
    """NTCRM19 — analytics d'une salle de vente : nombre de vues, dernière
    vue, délai création → première vue (signal d'intérêt : plus court =
    prospect plus chaud). Lecture seule."""
    vues_qs = salle.vues.order_by('created_at')
    count = vues_qs.count()
    premiere = vues_qs.first()
    derniere = salle.vues.order_by('-created_at').first()
    delai_premiere_vue_heures = None
    if premiere is not None:
        delta = premiere.created_at - salle.created_at
        delai_premiere_vue_heures = round(delta.total_seconds() / 3600, 1)
    return {
        'salle_id': salle.id,
        'nb_vues': count,
        'derniere_vue': derniere.created_at if derniere else None,
        'premiere_vue': premiere.created_at if premiere else None,
        'delai_premiere_vue_heures': delai_premiere_vue_heures,
    }


def salle_vente_summary_for_lead(company, lead_id):
    """NTCRM19 — résumé consommé par la fiche lead : « le client a consulté
    N fois, dernière fois <date> » sur la salle de vente la plus récente du
    lead. `None` si le lead n'a aucune salle de vente."""
    from .models import SalleVente

    salle = (SalleVente.objects
             .filter(company=company, lead_id=lead_id)
             .order_by('-created_at').first())
    if salle is None:
        return None
    analytics = salle_vente_analytics(salle)
    analytics['salle_titre'] = salle.titre
    return analytics


def _metric_count_for_owner(company, metric, owner, start_dt, end_dt):
    """NTCRM23 — même 3 métriques CRM-only que `compute_attainment` (FG39),
    mais paramétrées par une fenêtre de dates explicite (jamais le système
    année/mois/trimestre d'`ObjectifCommercial`) et TOUJOURS par commercial
    (jamais l'équipe entière — un classement compare des individus)."""
    from decimal import Decimal

    from .models import Appointment, Lead

    if metric == 'nb_leads':
        return Decimal(Lead.objects.filter(
            company=company, owner=owner,
            date_creation__gte=start_dt, date_creation__lt=end_dt).count())
    if metric == 'nb_contacts':
        return Decimal(Lead.objects.filter(
            company=company, owner=owner, first_contacted_at__isnull=False,
            first_contacted_at__gte=start_dt,
            first_contacted_at__lt=end_dt).count())
    if metric == 'nb_rdv':
        return Decimal(Appointment.objects.filter(
            company=company, created_by=owner,
            statut=Appointment.Statut.EFFECTUE,
            scheduled_at__gte=start_dt, scheduled_at__lt=end_dt).count())
    # nb_devis / ca_signe — hors périmètre crm-only (comme compute_attainment).
    return Decimal('0')


def classement_defi(defi):
    """NTCRM23 — Classement PAR COMMERCIAL sur la métrique/fenêtre du défi,
    trié décroissant. Ne considère que les commerciaux ayant AU MOINS une
    activité mesurée (jamais un classement pollué de zéros pour toute la
    société) — cohérent avec « le plus de RDV ce mois »."""
    import datetime as _dt

    from django.utils import timezone as _tz

    from authentication.models import CustomUser

    start_dt = _tz.make_aware(
        _dt.datetime.combine(defi.periode_debut, _dt.time.min),
        _tz.get_current_timezone())
    end_dt = _tz.make_aware(
        _dt.datetime.combine(defi.periode_fin, _dt.time.min),
        _tz.get_current_timezone()) + _dt.timedelta(days=1)

    classement = []
    for user in CustomUser.objects.filter(company=defi.company):
        realise = _metric_count_for_owner(
            defi.company, defi.metrique, user, start_dt, end_dt)
        if realise > 0:
            classement.append({
                'owner_id': user.id,
                'owner_nom': str(user),
                'realise': realise,
            })
    classement.sort(key=lambda r: r['realise'], reverse=True)
    for rang, entry in enumerate(classement, start=1):
        entry['rang'] = rang
    return classement


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
    from .services import find_duplicates_by_contact

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


def lead_devis_ids_by_id(company, lead_id):
    """NTMKT18 — ids (str) des devis liés à un lead, par id OPAQUE (lecture
    seule) — pour un appelant cross-app (``marketing``) qui ne peut importer
    ``Lead`` et ne dispose que d'un ``lead_id`` (jamais d'objet ``Lead``).
    Renvoie ``[]`` si le lead n'existe pas ou n'a aucun devis."""
    from .models import Lead

    lead = Lead.objects.filter(company=company, pk=lead_id).only('id').first()
    if lead is None:
        return []
    return [str(d.id) for d in lead.devis.all()]


def leads_export_rows(company, lead_ids):
    """NTMKT40 — lignes d'export (nom/prenom/email/telephone/ville) des leads
    d'un segment marketing, par ids OPAQUES. Lecture seule, scopé société (un
    id hors société est ignoré) — snapshot d'audit RGPD/CNDP, aucune donnée
    interne (score/notes)."""
    from .models import Lead

    if not lead_ids:
        return []
    rows = Lead.objects.filter(
        company=company, id__in=list(lead_ids),
    ).values('id', 'nom', 'prenom', 'email', 'telephone', 'ville')
    return list(rows)


def dernier_contact_lead(company, lead_id):
    """NTMKT34 — date/heure du dernier point de contact (``PointContact``,
    FG204) d'un lead, ou ``None``. Lecture seule, par id OPAQUE pour un
    appelant cross-app (``marketing``)."""
    from .models import PointContact

    pc = (PointContact.objects
          .filter(company=company, lead_id=lead_id)
          .order_by('-date_contact')
          .first())
    return pc.date_contact if pc else None


# ── NTMKT20 — Modèles d'attribution configurables sur PointContact (FG204) ──
# Complète ``revenu_attribue_campagne`` (XMKT17, implicitement dernier-touche
# par nom de campagne) SANS le modifier : ceci répartit le revenu d'UN devis
# signé entre les points de contact de son parcours, pour les 4 modèles
# standards — une aide à la décision, jamais un recalcul persistant.

ATTRIBUTION_MODELES = (
    'dernier_touche', 'premier_touche', 'lineaire', 'pondere_temporel',
)

# Demi-vie (jours) du modèle « pondéré temporel » — formule de dégradation
# temporelle standard (poids = 2^(-jours_avant_la_dernière_touche / demi_vie)).
_ATTRIBUTION_DEMI_VIE_JOURS = 7


def _attribution_part(point_contact, montant):
    return {
        'point_contact_id': point_contact.pk,
        'canal': point_contact.canal,
        'canal_libelle': point_contact.get_canal_display(),
        'date_contact': point_contact.date_contact,
        'revenu_attribue': str(montant),
    }


def _repartir_attribution(points, modele, total_revenu):
    """NTMKT20 — répartit ``total_revenu`` (Decimal) entre ``points``
    (``PointContact`` triés chronologiquement) selon ``modele``. Lecture
    pure : aucune écriture, aucun état modifié. La somme des montants
    répartis reste TOUJOURS égale à ``total_revenu`` au centime près."""
    from decimal import ROUND_HALF_UP, Decimal

    n = len(points)
    if n == 0 or not total_revenu:
        return []

    if modele == 'premier_touche':
        montants = [Decimal('0')] * n
        montants[0] = total_revenu
    elif modele == 'lineaire':
        part = (total_revenu / n).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        montants = [part] * n
        # Ajuste le DERNIER point pour que la somme reste exacte au centime
        # (l'arrondi par ligne peut sinon dériver de quelques centimes).
        montants[-1] = total_revenu - part * (n - 1)
    elif modele == 'pondere_temporel':
        derniere_date = points[-1].date_contact
        poids = [
            Decimal(str(2 ** (
                -max((derniere_date - p.date_contact).days, 0)
                / _ATTRIBUTION_DEMI_VIE_JOURS)))
            for p in points
        ]
        total_poids = sum(poids) or Decimal('1')
        montants = [
            (total_revenu * w / total_poids).quantize(Decimal('0.01'))
            for w in poids
        ]
        ecart = total_revenu - sum(montants)
        montants[-1] = montants[-1] + ecart
    else:  # 'dernier_touche' — défaut, comportement historique XMKT17.
        montants = [Decimal('0')] * n
        montants[-1] = total_revenu

    return [_attribution_part(p, m) for p, m in zip(points, montants)]


def attribution_comparaison_devis(devis):
    """NTMKT20 — pour un devis ACCEPTÉ, la répartition de son ``total_ttc``
    entre les points de contact (``PointContact``, FG204) du lead lié, pour
    les 4 modèles d'attribution côte à côte. ``None`` si le devis n'a pas de
    lead lié ou n'est pas accepté. Lecture seule, aide à la décision — ne
    modifie JAMAIS ``PointContact`` ni le devis."""
    from decimal import Decimal

    from .models import PointContact

    lead = getattr(devis, 'lead', None)
    if lead is None or getattr(devis, 'statut', None) != 'accepte':
        return None
    points = list(
        PointContact.objects.filter(company=lead.company_id, lead=lead))
    try:
        total_revenu = Decimal(str(devis.total_ttc or 0))
    except Exception:
        total_revenu = Decimal('0')
    return {
        'devis_id': devis.pk,
        'lead_id': lead.pk,
        'total_revenu': str(total_revenu),
        'nb_points_contact': len(points),
        'modeles': {
            modele: _repartir_attribution(points, modele, total_revenu)
            for modele in ATTRIBUTION_MODELES
        },
    }


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
    from .services import find_duplicates_by_contact

    if not email and not phone:
        return []
    return [
        lead.pk
        for lead in find_duplicates_by_contact(
            company, email=email, phone=phone)
    ]


# ── VT2 — L'AGRÉGAT DE LA VISITE TECHNIQUE TERRAIN ───────────────────────────
#
# ``contexte_visite_terrain`` est la SOURCE DE VÉRITÉ de la forme servie par
# ``GET /api/django/crm/visites/<pk>/`` (contrat PACT10
# ``apps/crm/contract_samples/visite_terrain.json``). Les deux écrans — wizard
# commercial mobile et revue bureau d'études — la lisent en UN appel.
#
# LA COMPLÉTUDE EST CALCULÉE ICI, JAMAIS DANS LE NAVIGATEUR : le front AFFICHE
# ``completude.manquants``, il ne la reconstitue pas. Et cet agrégat n'émet
# AUCUN verdict technique — il montre les mesures relevées ; c'est le bureau
# d'études qui juge au moment du feu vert.

def _visite_url_photo(attachment_id):
    """URL du proxy Django qui sert une pièce jointe (jamais MinIO direct)."""
    return f'/api/django/records/attachments/{attachment_id}/download/'


def _visite_decimal(valeur):
    """Un ``Decimal`` de coordonnée rendu en nombre JSON, ou ``None``."""
    return None if valeur is None else float(valeur)


def _visite_photo(media):
    attachment = media.attachment
    return {
        'id': media.id,
        'url': _visite_url_photo(media.attachment_id),
        'filename': getattr(attachment, 'filename', '') or '',
        'gps_lat': _visite_decimal(media.gps_lat),
        'gps_lng': _visite_decimal(media.gps_lng),
        'commentaire': media.commentaire or '',
        'a_refaire': bool(media.a_refaire),
        'motif_refaire': media.motif_refaire or '',
    }


def _visite_etat_slot(declaration, photos):
    """``manquant`` / ``ok`` / ``a_refaire`` pour UN slot photo.

    Une photo marquée à refaire prime : tant qu'elle n'est pas remplacée, le
    slot n'est pas servi (peu importe le compte brut de photos).
    """
    if any(photo['a_refaire'] for photo in photos):
        return 'a_refaire'
    servies = [photo for photo in photos if not photo['a_refaire']]
    if len(servies) >= declaration['min_photos']:
        return 'ok'
    return 'manquant'


def _visite_checklist(visite, medias):
    from . import visite_checklist as checklist

    par_slot = {}
    for media in medias:
        par_slot.setdefault(media.slot_code, []).append(_visite_photo(media))
    blocs = []
    for cat in checklist.categories():
        slots = []
        for declaration in cat['slots']:
            photos = par_slot.get(declaration['code'], [])
            slots.append({
                'code': declaration['code'],
                'libelle': declaration['libelle'],
                'guide': declaration['guide'],
                'requis': declaration['requis'],
                'min_photos': declaration['min_photos'],
                'etat': _visite_etat_slot(declaration, photos),
                'photos': photos,
            })
        blocs.append({
            'categorie': cat['categorie'],
            'libelle': cat['libelle'],
            'slots': slots,
        })
    return blocs


def _visite_mesures(visite):
    """Les mesures DÉCLARÉES, remplies des valeurs saisies (``None`` sinon).

    Rendre la structure complète — et non le seul JSON stocké — garantit que
    l'écran affiche toujours les mêmes champs, dans le même ordre, qu'ils
    soient renseignés ou pas.
    """
    from . import visite_checklist as checklist

    saisies = visite.mesures if isinstance(visite.mesures, dict) else {}
    rendu = {}
    for cat in checklist.categories():
        champs = cat['mesures']
        if not champs:
            continue
        valeurs = saisies.get(cat['categorie']) or {}
        rendu[cat['categorie']] = {
            champ['code']: valeurs.get(champ['code'], None)
            for champ in champs
        }
    return rendu


def _visite_manquants(blocs, mesures_rendues):
    from . import visite_checklist as checklist

    manquants = []
    for bloc in blocs:
        for slot in bloc['slots']:
            if slot['etat'] == 'a_refaire':
                manquants.append({
                    'type': checklist.MANQUE_PHOTO_A_REFAIRE,
                    'categorie': bloc['categorie'],
                    'code': slot['code'],
                    'libelle': slot['libelle'],
                })
            elif slot['requis'] and slot['etat'] == 'manquant':
                manquants.append({
                    'type': checklist.MANQUE_PHOTO,
                    'categorie': bloc['categorie'],
                    'code': slot['code'],
                    'libelle': slot['libelle'],
                })
    for cat in checklist.categories():
        valeurs = mesures_rendues.get(cat['categorie']) or {}
        for champ in cat['mesures']:
            if not checklist.mesure_requise(champ, valeurs):
                continue
            valeur = valeurs.get(champ['code'])
            if valeur is None or valeur == '':
                manquants.append({
                    'type': checklist.MANQUE_MESURE,
                    'categorie': cat['categorie'],
                    'code': champ['code'],
                    'libelle': champ['libelle'],
                })
    return manquants


def _visite_client_panel(lead):
    """Panneau LECTURE SEULE du client — coordonnées du lead uniquement."""
    nom = ' '.join(
        part for part in [(lead.prenom or '').strip(), (lead.nom or '').strip()]
        if part)
    return {
        'lead_nom': nom or (lead.nom or ''),
        'telephone': lead.telephone or '',
        'whatsapp': lead.whatsapp or '',
        'adresse': lead.adresse or '',
        'ville': lead.ville or '',
        'gps_lat': _visite_decimal(lead.gps_lat),
        'gps_lng': _visite_decimal(lead.gps_lng),
    }


def _visite_devis(lead):
    """Devis du lead pour le panneau lecture seule — VT3.

    Frontière M3 : la lecture passe par le SELECTOR de ``apps.ventes``, jamais
    par un import de ses modèles. Cette porte ne laisse sortir aucun
    ``prix_achat`` ni aucune donnée de marge (garde testée côté VT4).
    """
    from apps.ventes.selectors import devis_lecture_seule_pour_lead

    try:
        return devis_lecture_seule_pour_lead(lead)
    except Exception:  # pragma: no cover - défensif : un devis illisible ne
        # doit jamais empêcher le commercial d'ouvrir sa visite sur le terrain.
        return []


def visite_terrain_manquants(visite):
    """La liste SERVEUR des manquants d'une visite (gate de terminaison)."""
    medias = list(visite.medias.select_related('attachment').all())
    blocs = _visite_checklist(visite, medias)
    return _visite_manquants(blocs, _visite_mesures(visite))


def contexte_visite_terrain(visite):
    """L'agrégat COMPLET d'une visite technique terrain (contrat VT0)."""
    medias = list(visite.medias.select_related('attachment').all())
    blocs = _visite_checklist(visite, medias)
    mesures_rendues = _visite_mesures(visite)
    manquants = _visite_manquants(blocs, mesures_rendues)
    commercial = visite.commercial
    return {
        'id': visite.id,
        'lead': visite.lead_id,
        'commercial': None if commercial is None else {
            'id': commercial.id,
            'nom_affiche': (commercial.get_full_name()
                            or commercial.username),
        },
        'statut': visite.statut,
        'date_prevue': (visite.date_prevue.isoformat()
                        if visite.date_prevue else None),
        'date_realisee': (visite.date_realisee.isoformat()
                          if visite.date_realisee else None),
        'notes': visite.notes or '',
        'modifiable': visite.modifiable,
        'raison_lecture_seule': visite.raison_lecture_seule,
        'photo_toit': {
            'assemblage_etat': visite.assemblage_etat,
            'assemblage_erreur': visite.assemblage_erreur or '',
            'url': (f'/api/django/crm/visites/{visite.id}/photo-toit/'
                    if visite.photo_toit_key else None),
            'texture_calage': visite.texture_calage,
        },
        'checklist': blocs,
        'mesures': mesures_rendues,
        'completude': {
            'complet': not manquants,
            'manquants': manquants,
        },
        'client_panel': _visite_client_panel(visite.lead),
        'devis': _visite_devis(visite.lead),
    }


def texture_toit_pour_lead(lead):
    """VT12 — la texture de toit CALÉE d'un lead, ou des valeurs nulles.

    C'est la porte par laquelle le reste de l'ERP (atelier 3D/calepinage,
    carte de la fiche lead) lit le toit réaliste SANS rien connaître du module
    visite : il demande « la texture de ce lead », pas « la visite n° 7 ».

    Règles :

    * seule une visite **VALIDÉE** (feu vert du bureau d'études) compte — une
      visite encore en cours ou renvoyée ne doit jamais peindre un toit ;
    * la **dernière** validée gagne (``-id`` : déterministe, aucune horloge) ;
    * la société vient du LEAD, jamais de la requête — une visite d'une autre
      société ne peut structurellement pas sortir d'ici ;
    * sans visite validée, ou sans image assemblée, les MÊMES clés sortent à
      ``None`` — l'appelant n'a jamais à distinguer deux formes de réponse, et
      rien n'est inventé pour combler le vide.
    """
    from .models import VisiteTerrain

    vide = {'visite_id': None, 'url': None, 'texture_calage': None}
    if lead is None:
        return vide
    visite = (VisiteTerrain.objects
              .filter(lead=lead, company_id=lead.company_id,
                      statut=VisiteTerrain.Statut.VALIDEE)
              .exclude(photo_toit_key='')
              .order_by('-id')
              .first())
    if visite is None or not visite.photo_toit_key:
        return vide
    return {
        'visite_id': visite.id,
        'url': f'/api/django/crm/visites/{visite.id}/photo-toit/',
        'texture_calage': visite.texture_calage,
    }


def recap_visite_terrain(visite):
    """VT12 — le récap COURT (FR) écrit en retour sur ``Lead.visite_notes``.

    Ne contient QUE des valeurs réellement saisies : une mesure absente est
    OMISE de la phrase, jamais remplacée par un défaut forfaitaire (règle
    « zéro chiffre inventé »). Si rien n'a été relevé, seule la ligne de date
    sort — et si même la date manque, la phrase la tait aussi.
    """
    saisies = visite.mesures if isinstance(visite.mesures, dict) else {}

    def valeur(categorie, code):
        bloc = saisies.get(categorie) or {}
        brute = bloc.get(code)
        if brute is None or brute == '':
            return None
        return brute

    def nombre(categorie, code):
        brute = valeur(categorie, code)
        if brute is None:
            return None
        try:
            flottant = float(brute)
        except (TypeError, ValueError):
            return None
        entier = int(flottant)
        return str(entier) if flottant == entier else f'{flottant:g}'

    morceaux = []
    longueur = nombre('toiture', 'longueur_m')
    largeur = nombre('toiture', 'largeur_m')
    if longueur and largeur:
        morceaux.append(f'zone utile {longueur} × {largeur} m')
    if valeur('toiture', 'toit_plat') is True:
        morceaux.append('toit plat')
    else:
        pente = nombre('toiture', 'pente_deg')
        if pente:
            morceaux.append(f'pente {pente}°')
    orientation = valeur('toiture', 'orientation')
    if orientation:
        morceaux.append(f'orientation {orientation}')
    couverture = valeur('toiture', 'type_couverture')
    if couverture:
        morceaux.append(f'couverture {couverture}')
    calibre = nombre('tableau', 'calibre_disjoncteur_a')
    if calibre:
        morceaux.append(f'disjoncteur {calibre} A')
    alimentation = valeur('tableau', 'type_alimentation')
    if alimentation:
        morceaux.append(f'alimentation {alimentation}')

    moment = visite.date_realisee or visite.date_prevue
    entete = 'Visite technique validée'
    if moment is not None:
        entete += f' — réalisée le {moment.strftime("%d/%m/%Y")}'
    if not morceaux:
        return entete + '.'
    return entete + ' : ' + ', '.join(morceaux) + '.'


def ligne_visite_terrain(visite):
    """UNE ligne de la liste ``GET /crm/visites/`` (badge de complétude)."""
    manquants = visite_terrain_manquants(visite)
    lead = visite.lead
    nom = ' '.join(
        part for part in [(lead.prenom or '').strip(), (lead.nom or '').strip()]
        if part)
    return {
        'id': visite.id,
        'lead': visite.lead_id,
        'lead_nom': nom or (lead.nom or ''),
        'ville': lead.ville or '',
        'statut': visite.statut,
        'date_prevue': (visite.date_prevue.isoformat()
                        if visite.date_prevue else None),
        'complet': not manquants,
        'manquants_count': len(manquants),
    }


# ── NTDATA11 — ADAPTATEUR DE MÉTRIQUE (couche sémantique) ───────────────────
#
# Le pipeline PONDÉRÉ n'est pas un agrégat SQL : il passe lead par lead par
# ``apps.reporting.pipeline._lead_forecast_value`` × ``_lead_win_weight``
# (scorer ``core.win_probability``). Cette enveloppe MINCE réutilise
# exactement ces scorers — aucune seconde définition, aucun coefficient
# recopié — pour que la métrique nommée « valeur_pipeline_ponderee » rende le
# MÊME chiffre que l'écran Pipeline.


def metrique_pipeline_pondere(company, user=None, *, period=None,
                              filters=None):
    """NTDATA11 — valeur PONDÉRÉE du pipeline ouvert (MAD) d'une société.

    Population : leads non archivés, non perdus, dont l'étape n'est ni SIGNED
    ni COLD (les clés viennent de ``STAGES.py``, jamais écrites ici) — la
    MÊME population qu'``pipeline_pondere_par_entite``. ``period``
    (``{'debut','fin'}`` ou couple) borne la date de création ; ``filters``
    est ignoré (la population est celle du pipeline, par définition).
    """
    from decimal import Decimal

    from apps.reporting.pipeline import _lead_forecast_value, _lead_win_weight

    from . import stages as stage_mod
    from .models import Lead

    ouvertes = [
        k for k in stage_mod.STAGES
        if k not in (stage_mod.SIGNED, stage_mod.COLD)
    ]
    qs = (Lead.objects
          .filter(company=company, is_archived=False, perdu=False,
                  stage__in=ouvertes)
          .prefetch_related('devis'))
    if period:
        if isinstance(period, (tuple, list)):
            valeurs = list(period) + [None, None]
            debut, fin = valeurs[0], valeurs[1]
        else:
            debut, fin = period.get('debut'), period.get('fin')
        if debut is not None:
            qs = qs.filter(date_creation__gte=debut)
        if fin is not None:
            qs = qs.filter(date_creation__lte=fin)
    total = Decimal('0')
    for lead in qs:
        total += _lead_forecast_value(lead) * _lead_win_weight(lead)
    return total


def register_metric_adapters():
    """Enregistre les adaptateurs CRM dans ``apps.semantic`` (idempotent).

    Appelé depuis ``CrmConfig.ready()`` : c'est l'app PROPRIÉTAIRE du calcul
    qui vient s'enregistrer — ``semantic`` n'importe jamais ``crm``.
    """
    from apps.semantic.adapters import register_adapter
    register_adapter('crm.pipeline_pondere', metrique_pipeline_pondere)
