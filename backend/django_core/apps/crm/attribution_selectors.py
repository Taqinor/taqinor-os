"""Lectures d'attribution publicitaire servies à adsengine (SPL88, scission de
`selectors.py`).

Déplacement pur ; `apps.crm.selectors` ré-exporte chaque nom (frontière
inter-apps). N'importe jamais `.selectors` au niveau module.
"""
from .clients_selectors import (
    _devis_compte_comme_signe,
)
from .portee_selectors import (
    lead_signe_q, est_lead_signe, cles_numeros_lead,
)


def signed_lead_phone_keys(company):
    """ADSDEEP25 — ``set`` des clés téléphone NORMALISÉES (QW10) des leads au
    stade SIGNÉ de la société.

    Point d'entrée cross-app SANCTIONNÉ pour ``apps.adsengine`` (métrique
    conversations-par-ad CTWA : rapproche une conversation WhatsApp entrante
    d'une signature par téléphone) — jamais un import de ``apps.crm.models``
    côté adsengine, et le stade SIGNÉ vient de ``STAGES.py`` (jamais codé en
    dur, règle #2). Lecture seule, scopée société ; ignore les numéros vides.
    Renvoie un ``set`` de clés non vides."""
    from .models import Lead

    keys = set()
    # ACRM33 — telephone ET whatsapp (helper partagé avec
    # ``find_lead_id_by_phone``).
    for lead in (Lead.objects
                 .filter(lead_signe_q(), company=company)
                 .only('id', 'telephone', 'whatsapp')):
        keys |= cles_numeros_lead(lead)
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
    from .models import Lead

    result = {}
    for key in utm_campaigns:
        if key in result:
            continue
        ids = list(
            Lead.objects
            .filter(lead_signe_q(), company=company, utm_campaign=key)
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
                'stage', 'perdu', 'motif_perte', 'is_archived'))
    for lead in qs:
        stage = lead.stage
        rank = _rank(stage)
        is_signed = est_lead_signe(lead)  # ACRM31
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
            if _devis_compte_comme_signe(devis):  # ACRM10
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

        est_signe = est_lead_signe(lead)  # ACRM31
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


def leads_ville_rows(company, canaux=None, date_start=None, date_end=None):
    """PUB62 — Une ligne par lead PORTANT une ville renseignée : id, ville,
    signé (stade SIGNED, jamais perdu — STAGES.py, jamais codé en dur).
    Scopé société, leads vivants. Un lead SANS ville est simplement ABSENT
    (jamais une ville vide fabriquée — règle checked-facts). Point d'entrée
    cross-app pour la carte chaleur ville d'``apps.adsengine.reporting``
    (jamais un import d'``apps.crm.models`` côté adsengine).

    AACQ10 — filtres OPTIONNELS (défaut = comportement d'avant) : ``canaux``
    (liste de clés ``Lead.Canal``) et ``date_start``/``date_end`` (dates
    incluses, sur la date de création du lead) — la carte chaleur peut ainsi
    ne demander que les leads Meta d'une fenêtre."""
    from .models import Lead

    rows = []
    qs = (Lead.objects
          .filter(company=company, is_archived=False)
          .exclude(ville__isnull=True).exclude(ville__exact='')
          .only('id', 'ville', 'stage', 'perdu', 'is_archived'))
    if canaux is not None:
        qs = qs.filter(canal__in=list(canaux))
    if date_start is not None:
        qs = qs.filter(date_creation__date__gte=date_start)
    if date_end is not None:
        qs = qs.filter(date_creation__date__lte=date_end)
    for lead in qs:
        rows.append({
            'id': lead.id,
            'ville': lead.ville.strip(),
            'signed': est_lead_signe(lead),  # ACRM31
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
        # ACRM31 — seul un lead signé (prédicat unique) porte du CA attribué.
        if not est_lead_signe(lead):
            continue
        for devis in lead.devis.all():
            if _devis_compte_comme_signe(devis):  # ACRM10
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
    from .dsr_provider import LEAD_NOM_ANONYMISE
    from .models import Lead
    lead = (Lead.objects
            .filter(pk=lead_id, company=company)
            .only('id', 'external_system', 'external_id', 'telephone', 'email',
                  'fbclid', 'canal', 'source', 'nom')
            .first())
    if lead is None:
        return None
    # AACQ20 — un lead EFFACÉ (DSR/rétention) ne fournit plus aucun
    # identifiant publicitaire : ``external_id`` est gardé en base pour la
    # dédup anti-résurrection, jamais renvoyé ici.
    is_erased = lead.nom == LEAD_NOM_ANONYMISE
    leadgen_id = ''
    if (not is_erased and lead.external_system == _META_LEAD_ADS_SYSTEM
            and lead.external_id):
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
        'fbclid': '' if is_erased else (lead.fbclid or ''),
        'is_meta_origin': is_meta_origin,
        'is_erased': is_erased,
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
    from .dsr_provider import LEAD_NOM_ANONYMISE
    from .models import Lead
    meta_canaux = {Lead.Canal.META_ADS, Lead.Canal.WHATSAPP_CTWA}
    # AACQ20 — un lead effacé ne compte plus dans la couverture de match.
    qs = (Lead.objects.filter(company=company, is_archived=False)
          .exclude(nom=LEAD_NOM_ANONYMISE)
          .only('external_system', 'external_id', 'telephone', 'canal',
                'source'))
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

    paid_canaux = {Lead.Canal.META_ADS, Lead.Canal.WHATSAPP_CTWA, Lead.Canal.GOOGLE_ADS}
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
