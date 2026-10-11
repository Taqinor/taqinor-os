"""Lectures clients (SPL85, scission de `selectors.py`) : fiche client, crédit,
pilotage, forecast, partenaires, salle de vente, défis, adaptateurs de métrique.

Déplacement pur ; `apps.crm.selectors` ré-exporte chaque nom (frontière
inter-apps). N'importe jamais `.selectors` au niveau module.

Note : `client_label` appelle `get_company_client` de CE module ; un
`mock.patch('apps.crm.selectors.get_company_client')` ne l'intercepte plus
(grep : aucun test n'attend cet effet).
"""
from .leads_selectors import (
    normalize_phone_key,
)


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

    ACRM27 — métriques ventes calculées elles aussi (jamais un réalisé
    constant à 0) :
      - nb_devis : devis ENVOYÉS dans la période (``date_envoi``) ;
      - ca_signe : ``ca_signe_periode`` — le MÊME chiffre que « Mes équipes ».
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

    elif metric == 'nb_devis':
        realise = nb_devis_envoyes_periode(
            company, None if owner is None else [owner.pk], start_dt, end_dt)

    elif metric == 'ca_signe':
        realise = ca_signe_periode(
            company, None if owner is None else [owner.pk],
            period_start, period_end)

    cible = objectif.cible or Decimal('0')
    taux = float(realise / cible * 100) if cible else 0.0

    return {
        'cible': cible,
        'realise': realise,
        'taux': round(taux, 1),
        'period_start': period_start,
        'period_end': period_end,
    }


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
    gain du lead), sans dupliquer la logique.

    ACRM34 — la valeur PONDÉRÉE est celle du forecast (XSAL7) :
    ``_lead_forecast_value`` × ``_lead_win_weight`` (un devis refusé/expiré
    ne pèse pas ; un lead sans devis actif pèse son ``montant_estime``), pour
    que la carte « Mes équipes » affiche le même pondéré que le forecast."""
    from decimal import Decimal
    from apps.reporting.pipeline import (
        _lead_forecast_value, _lead_value, _lead_win_weight)
    valeur = Decimal('0')
    ponderee = Decimal('0')
    for lead in leads:
        valeur += _lead_value(lead)
        ponderee += _lead_forecast_value(lead) * _lead_win_weight(lead)
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


def _devis_compte_comme_signe(devis):
    """ACRM10 (C-ACRM-006) — LE prédicat local du CA « signé » côté crm :
    ``statut='accepte'`` ET ``is_active=True`` — aligné sur
    ``reporting.pipeline._devis_signes`` (AANA19 / D-AANA-5). Réviser un devis
    accepté laisse la V1 acceptée mais INACTIVE : la compter en plus de la V2
    doublait le CA (53 500 + 72 500 au lieu de 72 500). Lit l'instance (la
    relation ``lead.devis`` préchargée) — jamais un import de
    ``apps.ventes.models``."""
    return (getattr(devis, 'statut', None) == 'accepte'
            and getattr(devis, 'is_active', True))


def _ca_signe_mois(company, membre_ids, today=None):
    """CA TTC signé (Devis acceptés) ce mois-ci, par owner du lead source,
    pour les membres donnés. Lecture seule — traverse Lead.devis (reverse FK
    ventes → crm), jamais un import de apps.ventes.models."""
    import datetime
    from decimal import Decimal
    today = today or datetime.date.today()
    if not membre_ids:
        return Decimal('0')
    return ca_signe_periode(company, membre_ids, today.replace(day=1), today)


def ca_signe_periode(company, membre_ids, debut, fin):
    """ACRM27 — LA lecture du CA TTC signé d'une période (bornes DATES
    incluses, ``date_acceptation``), par owner du lead source : la carte
    « Mes équipes » (``_ca_signe_mois``), le réalisé des objectifs ``ca_signe``
    et les défis la partagent — jamais deux chiffres. ``membre_ids`` ``None``
    = toute la société. Seule la version en vigueur compte
    (``_devis_compte_comme_signe``, ACRM10). Lecture via ``lead.devis`` —
    jamais un import de ``apps.ventes.models``."""
    from decimal import Decimal

    from .models import Lead
    leads = Lead.objects.filter(company=company)
    if membre_ids is not None:
        leads = leads.filter(owner_id__in=membre_ids)
    total = Decimal('0')
    for lead in leads.prefetch_related('devis'):
        for devis in lead.devis.all():
            if not _devis_compte_comme_signe(devis):  # ACRM10
                continue
            d = devis.date_acceptation
            if d is None or d < debut or d > fin:
                continue
            try:
                total += Decimal(str(devis.total_ttc or 0))
            except Exception:
                continue
    return total


def nb_devis_envoyes_periode(company, membre_ids, start_dt, end_dt):
    """ACRM27 — le nombre de devis ENVOYÉS dans la fenêtre
    ``[start_dt, end_dt[`` (``date_envoi``), par owner du lead source
    (``membre_ids`` ``None`` = toute la société) : le réalisé des objectifs
    et défis ``nb_devis``. Lecture via ``lead.devis``."""
    from decimal import Decimal

    from .models import Lead
    leads = Lead.objects.filter(company=company)
    if membre_ids is not None:
        leads = leads.filter(owner_id__in=membre_ids)
    nombre = 0
    for lead in leads.prefetch_related('devis'):
        for devis in lead.devis.all():
            envoye = getattr(devis, 'date_envoi', None)
            if envoye is not None and start_dt <= envoye < end_dt:
                nombre += 1
    return Decimal(nombre)


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


def clients_contact_identifiers(company):
    """XMKT36 — email/téléphone des CLIENTS signés de la société (liste
    d'exclusion publicitaire : on n'achète pas d'impression pour un client
    déjà converti). Même contrat lecture seule que ``lead_contact_identifiers``."""
    from .models import Client
    # ACRM56 (D-ACRM-5 (1)=(a)) — un client rattaché à un lead « ne plus
    # contacter » n'est exporté dans aucune audience.
    rows = (Client.objects.filter(company=company)
            .exclude(leads__ne_plus_contacter=True)
            .values('email', 'telephone'))
    return [
        {'email': r['email'] or '', 'telephone': r['telephone'] or ''}
        for r in rows
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


def soumissions_partenaire_portail(company, partenaire_id):
    """NTPRT28 — SES soumissions de leads, telles que le portail les montre.

    Point d'entrée cross-app LECTURE SEULE de ``apps.portail`` (jamais un
    import de ``apps.crm.models`` depuis portail). Borné au couple (société,
    partenaire) : un ``partenaire_id`` absent — ou d'une autre société —
    renvoie une liste VIDE, jamais les soumissions d'un autre partenaire.

    Charge utile volontairement pauvre : ce que LE PARTENAIRE a saisi, plus
    l'avancement de sa soumission. Aucune donnée interne (propriétaire du
    lead, notes commerciales, montants) ne transite ici.
    """
    if company is None or not partenaire_id:
        return []

    from .models import Partenaire, SoumissionLeadPartenaire

    if not Partenaire.objects.filter(
            company=company, pk=partenaire_id).exists():
        return []

    return [{
        'id': s.id,
        'nom_prospect': s.nom_prospect,
        'telephone_prospect': s.telephone_prospect,
        'email_prospect': s.email_prospect,
        'ville': s.ville,
        'note': s.note,
        'statut': s.statut,
        'statut_display': s.get_statut_display(),
        # Le partenaire voit que SON prospect est devenu un dossier réel
        # (traçabilité de sa commission) — jamais le contenu de ce dossier.
        'converti': bool(s.lead_id),
        'date_soumission': (s.date_soumission.isoformat()
                            if s.date_soumission else None),
    } for s in SoumissionLeadPartenaire.objects.filter(
        company=company, partenaire_id=partenaire_id)]


def partenaire_peut_soumettre(company, partenaire_id):
    """NTPRT32 — le partenaire est-il AGRÉÉ pour enregistrer une affaire ?

    Renvoie ``(autorise, motif)`` :

    * ``(False, None)`` — aucun partenaire de cet id dans CETTE société.
      L'appelant répond « introuvable » : on ne dit jamais qu'il existe
      ailleurs ;
    * ``(False, '<message français>')`` — le partenaire existe mais son
      agrément ne l'autorise pas : le message lui EXPLIQUE pourquoi ;
    * ``(True, '')`` — nominal.

    Le statut d'agrément (FG237, ``Partenaire.statut_onboarding``) est la
    SEULE autorité, avec le drapeau ``actif`` qui ferme la porte de la même
    façon : c'est exactement ce que le critère d'acceptation NTPRT32 demande
    de faire respecter par NTPRT28. Un partenaire encore ``prospect`` ou
    ``en_cours`` d'agrément — comme un partenaire ``suspendu`` — n'enregistre
    aucune affaire ; les soumissions DÉJÀ déposées restent consultables (on
    ne ferme jamais rétroactivement l'historique du partenaire).
    """
    if company is None or not partenaire_id:
        return False, None

    from .models import Partenaire

    partenaire = (Partenaire.objects
                  .filter(company=company, pk=partenaire_id).first())
    if partenaire is None:
        return False, None
    if not partenaire.actif:
        return False, ('Votre compte partenaire est désactivé. Contactez '
                       'votre interlocuteur commercial.')
    if partenaire.statut_onboarding == 'suspendu':
        return False, ('Votre agrément est suspendu : vous ne pouvez pas '
                       'enregistrer de nouvelle affaire pour le moment.')
    if partenaire.statut_onboarding != 'agree':
        return False, ("Votre agrément n'est pas encore finalisé : vous "
                       "pourrez enregistrer vos affaires dès l'activation "
                       'de votre partenariat.')
    return True, ''


def releve_commissions_partenaire(company, partenaire_id, debut=None,
                                  fin=None):
    """NTPRT30 — relevé des commissions DU partenaire, sur une période.

    Point d'entrée cross-app LECTURE SEULE de ``apps.portail`` (jamais un
    import de ``apps.crm.models`` depuis portail). Borné au couple (société,
    partenaire) : un partenaire absent de CETTE société renvoie un relevé VIDE,
    jamais les commissions d'un autre.

    ``debut``/``fin`` sont des ``date`` INCLUSIVES appliquées à la date de
    création de la commission ; omises, le relevé couvre tout l'historique.

    Le TOTAL est, par construction, la somme des montants des lignes RENDUES —
    jamais un agrégat calculé sur un autre périmètre que celui affiché (c'est
    exactement le critère d'acceptation NTPRT30). ``due``/``payee``/``annulee``
    en sont les trois sous-sommes : elles s'additionnent au total, à l'unité
    près.
    """
    from decimal import Decimal

    vide = {
        'partenaire_nom': '',
        'debut': debut.isoformat() if debut else None,
        'fin': fin.isoformat() if fin else None,
        'lignes': [],
        'totaux': {'due': '0', 'payee': '0', 'annulee': '0', 'total': '0'},
    }
    if company is None or not partenaire_id:
        return vide

    from .models import CommissionPartenaire, Partenaire

    partenaire = (Partenaire.objects
                  .filter(company=company, pk=partenaire_id).first())
    if partenaire is None:
        return vide

    qs = CommissionPartenaire.objects.filter(
        company=company, partenaire=partenaire)
    if debut is not None:
        qs = qs.filter(date_creation__date__gte=debut)
    if fin is not None:
        qs = qs.filter(date_creation__date__lte=fin)

    lignes = []
    sous_totaux = {
        CommissionPartenaire.Statut.DUE: Decimal('0'),
        CommissionPartenaire.Statut.PAYEE: Decimal('0'),
        CommissionPartenaire.Statut.ANNULEE: Decimal('0'),
    }
    total = Decimal('0')
    for c in qs.order_by('-date_creation', '-id'):
        montant = c.montant or Decimal('0')
        total += montant
        if c.statut in sous_totaux:
            sous_totaux[c.statut] += montant
        lignes.append({
            'id': c.id,
            'date_creation': (c.date_creation.isoformat()
                              if c.date_creation else None),
            # Références opaques : le partenaire sait SUR QUOI porte sa
            # commission, jamais le contenu du devis ni celui du lead.
            'devis_id': c.devis_id,
            'lead_id': c.lead_id,
            'base_ht': str(c.base_ht or Decimal('0')),
            'taux': str(c.taux or Decimal('0')),
            'montant': str(montant),
            'statut': c.statut,
            'statut_display': c.get_statut_display(),
            'paye_le': c.paye_le.isoformat() if c.paye_le else None,
        })

    return {
        'partenaire_nom': partenaire.nom,
        'debut': debut.isoformat() if debut else None,
        'fin': fin.isoformat() if fin else None,
        'lignes': lignes,
        'totaux': {
            'due': str(sous_totaux[CommissionPartenaire.Statut.DUE]),
            'payee': str(sous_totaux[CommissionPartenaire.Statut.PAYEE]),
            'annulee': str(sous_totaux[CommissionPartenaire.Statut.ANNULEE]),
            'total': str(total),
        },
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
    from .engagement import engagement_label, engagement_pour_clients
    from .models import Client, Lead

    if company is None or user is None:
        return []
    client_ids = (
        Lead.objects.filter(company=company, owner=user, client__isnull=False)
        .values_list('client_id', flat=True).distinct()
    )
    # APRF22 — plan de compte chargé avec le client, scores EN LOT.
    clients = list(Client.objects.filter(company=company, id__in=client_ids)
                   .select_related('plan_compte'))
    scores = engagement_pour_clients(clients, now=now)
    out = []
    for client in clients:
        score = scores.get(client.pk, 0)
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


def comptes_dormants(company, seuil_jours=90, now=None, *, clients=None):
    """NTCRM14 — Clients avec au moins un devis/facture passé mais AUCUNE
    activité (dernier devis créé, dernière facture émise, dernier
    `LeadActivity`, dernier `PointContact` sur un lead lié) depuis plus de
    `seuil_jours`.

    Réutilise `apps.ventes.selectors` via import function-local (frontière
    cross-app respectée — jamais `apps.ventes.models`). Un client sans AUCUN
    devis/facture n'est jamais considéré dormant (rien à réactiver). Renvoie
    une liste de dicts `{'client', 'derniere_activite', 'jours_inactivite'}`
    triée par inactivité décroissante. Lecture seule.

    ALEA27 — ``clients`` (queryset BORNÉ, optionnel) : l'action HTTP
    ``clients/dormants/`` transmet ``ClientViewSet.get_queryset()`` (société +
    portée équipe) pour que rien de hors portée ne soit rendu. ``None`` = la
    société entière, voulu pour la commande système
    ``detecter_comptes_dormants`` (balayage sans utilisateur)."""
    from django.db.models import Max, OuterRef, Q, Subquery
    from django.utils import timezone

    from .models import Client, LeadActivity, PointContact

    if company is None:
        return []
    now = now or timezone.now()
    today = now.date() if hasattr(now, 'date') else now

    base = clients if clients is not None else Client.objects.all()
    # APRF22 — dates EN LOT (annotations SQL) : dernier devis (actif, non
    # brouillon — mêmes populations que ``devis_du_client_portail``),
    # dernière facture (non brouillon — ``factures_du_client_portail``) par
    # relations inverses en chaînes ; dernière activité et dernier point de
    # contact des leads de la société par sous-requête. Un client sans
    # devis/facture est écarté EN BASE. Requêtes constantes.
    brouillon = 'brouillon'  # statut de DOCUMENT (couche séparée, règle #4)
    derniere_activite = (
        LeadActivity.objects
        .filter(lead__client=OuterRef('pk'), lead__company=company)
        .order_by('-created_at').values('created_at')[:1])
    dernier_contact = (
        PointContact.objects
        .filter(lead__client=OuterRef('pk'), lead__company=company)
        .order_by('-date_contact').values('date_contact')[:1])
    annotes = (
        base.filter(company=company)
        .prefetch_related(None)  # le viewset précharge pour sa liste
        .annotate(
            _dernier_devis=Max('devis__date_creation', filter=Q(
                devis__company=company, devis__is_active=True)
                & ~Q(devis__statut=brouillon)),
            _derniere_facture=Max('factures__date_emission', filter=Q(
                factures__company=company) & ~Q(
                    factures__statut=brouillon)),
            _derniere_activite=Subquery(derniere_activite),
            _dernier_contact=Subquery(dernier_contact))
        .filter(Q(_dernier_devis__isnull=False)
                | Q(_derniere_facture__isnull=False)))
    out = []
    for client in annotes:
        dates = [_as_date(client._dernier_devis),
                 _as_date(client._derniere_facture),
                 _as_date(client._derniere_activite),
                 _as_date(client._dernier_contact)]
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
    # ACRM27 — les métriques ventes sont calculées (même lecture que
    # ``compute_attainment``), jamais un 0 constant.
    if metric == 'nb_devis':
        return nb_devis_envoyes_periode(company, [owner.pk], start_dt, end_dt)
    if metric == 'ca_signe':
        import datetime

        from core.dates import aujourd_hui_local
        # Fenêtre [start_dt, end_dt[ ramenée aux jours locaux, bornes incluses.
        return ca_signe_periode(
            company, [owner.pk], aujourd_hui_local(start_dt),
            aujourd_hui_local(end_dt - datetime.timedelta(microseconds=1)))
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


def client_ids_par_identifiant(company, identifiant):
    """NTGRC1 — ids des ``Client`` de la société correspondant à une PERSONNE.

    Fonction fine ajoutée pour le fournisseur DSR des Ventes (loi 09-08) : une
    autre app doit pouvoir retrouver les clients d'une personne concernée SANS
    importer ``apps.crm.models``. ``identifiant`` = un email OU un téléphone,
    exactement comme ``core.DataSubjectRequest.subject_identifier``.

    Renvoie une liste d'ids (jamais d'instances, jamais de PII) bornée à
    ``company`` — aucune lecture cross-société.
    """
    from .models import Client
    from .leads_doublons import normalize_email, normalize_phone

    if company is None or not (identifiant or '').strip():
        return []

    email = normalize_email(identifiant)
    phone = normalize_phone(identifiant)
    qs = Client.objects.filter(company=company)

    ids = set()
    if email:
        ids.update(qs.filter(email__iexact=email).values_list('id', flat=True))
    if phone:
        ids.update(
            pk for pk, tel in qs.values_list('id', 'telephone')
            if normalize_phone(tel) == phone)
    return sorted(ids)
