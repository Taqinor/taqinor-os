"""Sélecteurs LECTURE SEULE des audiences de croissance et des faits publicitaires
(valeur d'un devis pour un lead, segments de suivi/relance/cross-sell, totaux
signés, vélocité de signature, faits de témoignage) — sortis de
``apps/ventes/selectors.py`` par SPL146 (déplacement pur, corps inchangés ;
propriétaire : acquisition).

Les autres apps continuent de lire ces fonctions par la FAÇADE
``apps.ventes.selectors`` (ré-export en fin de fichier) ; ce module est PLAT :
aucun import de ``.selectors`` en tête (cycle).
"""


def devis_value_for_lead(lead_id, company):
    """PUB31 — montant TTC + devise du devis le plus RÉCENT lié à un lead.

    Point d'entrée cross-app LECTURE SEULE, fonction FINE, pour
    ``apps.adsengine.capi_crm`` (enrichissement OPTIONNEL, flag-gaté, de
    l'événement CAPI CRM-stage QUOTE_SENT avec ``custom_data.value/currency`` —
    jamais un import de ``apps.ventes.models`` côté adsengine, jamais touché le
    chemin ``signed_contract``/``capi_odoo``, distinct et intact). Renvoie
    ``{'value': float, 'currency': str}`` ou ``None`` si aucun devis lié."""
    if not lead_id:
        return None
    from .models import Devis
    devis = (Devis.objects
             .filter(lead_id=lead_id, company=company)
             .order_by('-date_creation', '-id')
             .first())
    if devis is None:
        return None
    return {'value': float(devis.total_ttc), 'currency': devis.devise or 'MAD'}


# ── PUB58/59/60 — Contacts pour les audiences de croissance (ADSDEEP57) ──────
# Lecture directe des FK Devis→crm.Client/Lead déjà déclarées sur le modèle
# (même pattern que `analyse_facturation`/`revenu_attribue_campagne`) — jamais
# un import d'``apps.crm.models``.

def _client_contact(client):
    """Contact ``{'email', 'telephone'}`` d'un ``crm.Client`` (ou ``None`` si
    aucun identifiant exploitable). Même contrat que
    ``apps.crm.selectors.clients_contact_identifiers``."""
    if client is None:
        return None
    email = client.email or ''
    telephone = client.telephone or ''
    if not email and not telephone:
        return None
    return {'email': email, 'telephone': telephone}


def _devis_contact(devis):
    """Contact ``{'email', 'telephone'}`` résolu depuis le LEAD d'origine du
    devis si présent, sinon le client. ``None`` si aucun identifiant."""
    if devis.lead_id and devis.lead:
        email = devis.lead.email or ''
        telephone = devis.lead.telephone or devis.lead.whatsapp or ''
        if email or telephone:
            return {'email': email, 'telephone': telephone}
    return _client_contact(devis.client)


def devis_view_tracking_segments(company):
    """PUB58 — Segmente les devis ENVOYÉS non encore ACCEPTÉS/REFUSÉS/EXPIRÉS
    de la société en deux paniers de contacts, depuis le view-tracking
    ``ShareLink`` (QJ1) qui dort en base :

      * ``jamais_ouvert`` — devis envoyé, AUCUN ``ShareLink`` consulté
        (``view_count`` nul sur tous ses liens, ou aucun lien du tout) ;
      * ``ouvert_non_signe`` — devis envoyé et consulté (au moins un
        ``ShareLink`` avec ``view_count`` > 0), toujours pas accepté
        (objection prix probable).

    Chaque panier appelle un angle de relance différent (PUB58). Renvoie
    ``{'jamais_ouvert': [...], 'ouvert_non_signe': [...]}`` (dicts
    ``{'email', 'telephone'}``, même contrat que
    ``apps.crm.selectors.lead_contact_identifiers``)."""
    from .models import Devis

    qs = (Devis.objects
          .filter(company=company, statut=Devis.Statut.ENVOYE)
          .select_related('client', 'lead')
          .prefetch_related('share_links'))

    jamais_ouvert, ouvert_non_signe = [], []
    for devis in qs:
        contact = _devis_contact(devis)
        if not contact:
            continue
        views = [sl.view_count for sl in devis.share_links.all()]
        if views and max(views) > 0:
            ouvert_non_signe.append(contact)
        else:
            jamais_ouvert.append(contact)
    return {'jamais_ouvert': jamais_ouvert, 'ouvert_non_signe': ouvert_non_signe}


def expired_devis_contacts(company):
    """PUB59 — Contacts des devis EXPIRÉS (``Devis.statut='expire'``) de la
    société — angle de relance « votre prix était valable 30 j, nouvelle
    offre ». Un devis expiré est un statut DOCUMENT (rule #4), distinct du
    stade funnel COLD du lead (rule #2) : les deux ne se mélangent jamais
    ici (aucune lecture de ``stage``).

    EXCLUSION signée : un client qui a, PAR AILLEURS, au moins un devis
    ACCEPTÉ est retiré du segment — on ne relance jamais quelqu'un qui a
    déjà acheté. Renvoie une liste de dicts ``{'email', 'telephone'}``."""
    from .models import Devis

    expired = list(
        Devis.objects
        .filter(company=company, statut=Devis.Statut.EXPIRE)
        .select_related('client'))
    if not expired:
        return []

    client_ids = {d.client_id for d in expired if d.client_id}
    signed_client_ids = set(
        Devis.objects.filter(
            company=company, statut=Devis.Statut.ACCEPTE,
            client_id__in=client_ids)
        .values_list('client_id', flat=True)) if client_ids else set()

    seen, contacts = set(), []
    for devis in expired:
        if not devis.client_id:
            continue
        if devis.client_id in signed_client_ids or devis.client_id in seen:
            continue
        contact = _client_contact(devis.client)
        if not contact:
            continue
        seen.add(devis.client_id)
        contacts.append(contact)
    return contacts


def signed_clients_cross_sell_segments(company):
    """PUB60 — Segmente les clients SIGNÉS (≥1 devis ACCEPTÉ) en deux paniers
    d'upsell base installée :

      * ``sans_contrat`` — aucun ``sav.ContratMaintenance`` actif, lu via
        ``apps.sav.selectors.clients_sans_contrat_actif`` (version bulk de
        YSERV10 ``client_a_contrat_actif`` — RÉUTILISÉE, jamais
        réimplémentée) ;
      * ``sans_batterie`` — le devis d'ORIGINE (le premier ACCEPTÉ,
        chronologiquement) ne portait PAS l'option ``avec_batterie``.

    Renvoie ``{'sans_contrat': [...], 'sans_batterie': [...]}`` (dicts
    ``{'email', 'telephone'}``)."""
    from .models import Devis

    accepted = (Devis.objects
                .filter(company=company, statut=Devis.Statut.ACCEPTE)
                .select_related('client')
                .order_by('client_id', 'date_creation'))

    origin_by_client = {}
    for devis in accepted:
        if devis.client_id and devis.client_id not in origin_by_client:
            origin_by_client[devis.client_id] = devis  # 1er vu = le + ancien

    if not origin_by_client:
        return {'sans_contrat': [], 'sans_batterie': []}

    from apps.sav.selectors import clients_sans_contrat_actif
    sans_contrat_ids = clients_sans_contrat_actif(
        company, list(origin_by_client.keys()))

    sans_contrat, sans_batterie = [], []
    for client_id, devis in origin_by_client.items():
        contact = _client_contact(devis.client)
        if not contact:
            continue
        if client_id in sans_contrat_ids:
            sans_contrat.append(contact)
        if devis.option_acceptee != Devis.OptionAcceptee.AVEC_BATTERIE:
            sans_batterie.append(contact)
    return {'sans_contrat': sans_contrat, 'sans_batterie': sans_batterie}


def devis_accepted_totals_by_lead(company, lead_ids):
    """PUB62 — Total TTC des devis ACCEPTÉS par ``lead_id`` (somme si un lead
    a plusieurs devis signés) — le « ticket moyen » de la carte chaleur
    ville. Lecture directe de la FK ``Devis.lead``. Renvoie
    ``{lead_id: Decimal}`` — un ``lead_id`` sans devis accepté est ABSENT
    (jamais un 0 fabriqué)."""
    from decimal import Decimal

    from .models import Devis

    lead_ids = list(lead_ids or [])
    if not lead_ids:
        return {}
    totals = {}
    for devis in (Devis.objects
                  .filter(company=company, statut=Devis.Statut.ACCEPTE,
                          lead_id__in=lead_ids)):
        try:
            amount = Decimal(str(devis.total_ttc or 0))
        except Exception:
            amount = Decimal('0')
        totals[devis.lead_id] = totals.get(devis.lead_id, Decimal('0')) + amount
    return totals


def signature_velocity_by_month_and_mode(company):
    """PUB67 — Nombre de devis ACCEPTÉS (signatures), par MOIS CALENDAIRE
    (1-12, toutes années confondues — la SAISONNALITÉ récurrente, pas une
    série temporelle) et par ``mode_installation``. Référence temporelle =
    ``date_acceptation`` (posée à l'acceptation), repli sur ``date_creation``
    pour les rares devis acceptés sans cette date.

    Renvoie ``{'par_mode': {mode: {1..12: count}}, 'mois_couverts': int}`` —
    ``mois_couverts`` = nombre de MOIS-CALENDAIRES (année, mois) DISTINCTS
    couverts par au moins un devis accepté, tous modes confondus (le signal
    de fiabilité — l'appelant exige ≥12 pour parler d'un cycle annuel
    complet, règle checked-facts)."""
    from collections import defaultdict

    from .models import Devis

    counts = defaultdict(lambda: defaultdict(int))
    covered_year_months = set()
    qs = (Devis.objects
          .filter(company=company, statut=Devis.Statut.ACCEPTE)
          .values_list('mode_installation', 'date_acceptation',
                       'date_creation'))
    for mode, date_acceptation, date_creation in qs:
        ref = date_acceptation or (
            date_creation.date() if date_creation else None)
        if ref is None:
            continue
        key = mode or '(non renseigné)'
        counts[key][ref.month] += 1
        covered_year_months.add((ref.year, ref.month))
    return {
        'par_mode': {mode: dict(months) for mode, months in counts.items()},
        'mois_couverts': len(covered_year_months),
    }


def faits_temoignage_devis(company, devis_id):
    """PUB63 — Faits VÉRIFIÉS d'un devis pour un brief témoignage créatif.

    Point d'entrée cross-app LECTURE SEULE pour ``apps.adsengine`` (jamais un
    import de ``ventes.models`` côté adsengine). Renvoie ``None`` si le devis
    n'existe pas / n'appartient pas à la société. Sinon un dict :
    ``{signed, client_id, client_nom, puissance_kwc, production_kwh,
    economie_annuelle, ville}`` — chiffres tirés de l'ÉTUDE du devis (faits du
    projet réel, jamais inventés ; ``None`` par champ absent). ``signed`` reflète
    le statut « Accepté » (un deal signé)."""
    from .models import Devis

    devis = (Devis.objects.filter(pk=devis_id, company=company)
             .select_related('client').first())
    if devis is None:
        return None
    etude = devis.etude_params or {}
    client = getattr(devis, 'client', None)

    def _num(*keys):
        for key in keys:
            val = etude.get(key)
            if val not in (None, ''):
                try:
                    return float(val)
                except (TypeError, ValueError):
                    return None
        return None

    return {
        'signed': devis.statut == Devis.Statut.ACCEPTE,
        'client_id': getattr(client, 'id', None),
        'client_nom': str(client) if client is not None else '',
        'puissance_kwc': _num('puissance_kwc', 'kwc', 'champ_kwc'),
        'production_kwh': _num('annualKwh', 'production_annuelle_kwh'),
        'economie_annuelle': _num('economies_annuelles', 'savings'),
        'ville': (etude.get('ville') or '').strip() or None,
        'reference': devis.reference,
    }
