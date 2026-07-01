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
