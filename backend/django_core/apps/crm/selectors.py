"""Sélecteurs LECTURE SEULE du domaine CRM exposés aux AUTRES apps.

Point d'entrée cross-app : les autres apps lisent les clients à travers ces
fonctions plutôt qu'en important `apps.crm.models` directement (voir CLAUDE.md,
règle de modularité). Comportement strictement identique aux requêtes inline
d'origine.
"""


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


def find_client_by_phone(company, telephone):
    """XSAV26 — Client de `company` dont le téléphone correspond au numéro
    donné, normalisé via `apps.ventes.utils.phone.normalize_ma_phone`.

    Point d'entrée cross-app sanctionné pour `apps.notifications` (webhook
    BSP WhatsApp) : matching par numéro SANS jamais exposer les modèles crm.
    Renvoie le client le plus récemment créé en cas de doublon, ou None."""
    from apps.ventes.utils.phone import normalize_ma_phone

    key = normalize_ma_phone(telephone)
    if not key:
        return None
    candidates = [
        c for c in client_base_qs(company).order_by('-id')
        if normalize_ma_phone(c.telephone) == key
    ]
    return candidates[0] if candidates else None


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
        # barème progressif (mêmes tranches que le chemin ROI), pas un prix plat.
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


# DC12 — profil site/énergie réutilisable par client ─────────────────────────

# Champs du profil que le générateur peut pré-remplir (source unique).
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
    from django.utils import timezone
    from authentication.scoping import scope_queryset
    from .models import Lead

    today = today or timezone.localdate()
    qs = Lead.objects.filter(
        company=company, is_archived=False, relance_date__isnull=False)
    qs = scope_queryset(qs, user, ['owner'])
    if scope == 'overdue':
        qs = qs.filter(relance_date__lt=today)
    elif scope == 'week':
        week_end = today + datetime.timedelta(days=6)
        qs = qs.filter(relance_date__lte=week_end)
    else:  # today
        qs = qs.filter(relance_date=today)
    return qs.order_by('relance_date', 'nom')


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
    from django.utils import timezone
    from authentication.scoping import scope_queryset
    from .models import Lead

    today = today or timezone.localdate()
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
    from django.utils import timezone
    today = today or timezone.localdate()
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


def lead_chatter_envelope(lead):
    """ARC9 — timeline chatter du lead dans l'ENVELOPPE UNIFORME.

    Étape 1 (additive) de la convergence des chatters historiques : projette
    ``crm.LeadActivity`` vers le format commun consommé par
    ``records.serializers.UniformChatterSerializer`` (un seul contrat de
    lecture pour le frontend, quel que soit le modèle source). Lecture seule —
    AUCUNE table modifiée. Le queryset est déjà borné par le lead (lui-même
    borné société par l'appelant).
    """
    rows = lead.activites.select_related('user').all()
    return [{
        'id': a.id,
        'kind': a.kind,
        'field': a.field or '',
        'field_label': a.field_label or '',
        'old_value': a.old_value or '',
        'new_value': a.new_value or '',
        'body': a.body or '',
        'user_username': a.user.username if a.user_id else None,
        'created_at': a.created_at,
        'source': 'crm.leadactivity',
    } for a in rows]
