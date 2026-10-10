"""Déduplication, normalisation et champs de fusion des leads (SPL5, extrait de crm/services.py : déplacement pur).

Module de type (a) de la scission : il n'importe ni ``.services`` ni un
module racine ; ``services`` réexporte ce qu'il faut (façade).
"""
import re as _re

from .models import Lead


# Champs scalaires recopiés sur le survivant SEULEMENT s'il les a vides
# (« on garde la valeur la plus complète », jamais d'écrasement).
_MERGE_FILL_FIELDS = [
    'prenom', 'civilite',  # CAD65 — la civilité saisie survit à la fusion
    'societe', 'email', 'telephone', 'whatsapp', 'adresse', 'ville',
    'langue_preferee', 'gps_lat', 'gps_lng',
    'facture_hiver', 'facture_ete', 'ete_differente',
    'conso_mensuelle_kwh', 'tranche_onee', 'raccordement', 'regularisation_8221',
    'type_installation', 'priorite', 'relance_date',
    'type_toiture', 'surface_toiture_m2', 'orientation', 'inclinaison_deg',
    'ombrage', 'ombrage_notes', 'nb_etages', 'structure_pref',
    'taille_souhaitee_kwc', 'batterie_souhaitee', 'pompe_actuelle_cv', 'pompe_hmt_m',
    'pompe_debit_m3h', 'canal', 'motif_perte', 'note', 'whatsapp_opt_in',
    # AGR400 — colonnes de pompage (contrat AGR1) : préservées à la fusion.
    'source_eau', 'niveau_statique_m', 'niveau_statique_source',
    'profondeur_forage_m', 'debit_forage_m3h', 'debit_forage_source',
    'besoin_eau_m3j', 'besoin_eau_source', 'culture', 'surface_irriguee_ha',
    'irrigation_methode', 'region_agricole', 'pompe_actuelle_type',
    'pompe_actuelle_debit_m3h', 'butane_bouteilles_jour',
    'carburant_prix_unitaire_mad', 'carburant_prix_declare_le',
    'depense_carburant_mad_mois', 'mois_irrigation',
    'distance_forage_champ_m', 'electricite_sur_place',
    'autorisation_prelevement', 'autorisation_numero',
    'autorisation_debit_l_s', 'autorisation_volume_m3_an', 'compteur_eau',
    'projet_pompage', 'deja_beneficiaire_fda', 'pompe_hmt_source',
    # CIQ401 — colonnes du lead pro (contrat CIQ1) : préservées à la fusion.
    'tension_raccordement', 'tension_source', 'compteur_puissance_kva',
    'contrat_electricite', 'option_tarifaire_bt',  # CIQ666
    'puissance_souscrite_source', 'categorie_commerciale',
    'reponses_categorie', 'secteur_industriel', 'export_ue_declare',
    'regime_equipes', 'jours_ouverture', 'heure_debut', 'heure_fin',
    'fermeture_mois', 'type_surface', 'surface_source', 'groupe_electrogene',
    'groupe_kva', 'groupe_litres_mois', 'groupe_depense_mad_mois',
    'pv_existant_kwc', 'cos_phi', 'cos_phi_source', 'releve_conso',
    'tva_recuperable', 'ice', 'rc', 'if_fiscal', 'adresse_siege',
    'fonction_contact', 'contact_secondaire_fonction',
    'contact_secondaire_email', 'facture_tranche_declaree',
    # Visite technique (légère) — préservée à la fusion.
    'visite_prevue_le', 'visite_effectuee', 'visite_notes',
    # Intake site web (taqinor.ma) — attribution + diagnostic préservés.
    'bill_range_bucket', 'roi_band', 'consent_timestamp', 'fbclid', 'gclid',
    'utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term',
]


def normalize_phone(value):
    """Téléphone normalisé pour comparaison : chiffres seuls, indicatif marocain
    réduit, zéro initial retiré. '+212 6 12-34' et '0612 34' → même clé."""
    digits = _re.sub(r'\D', '', str(value or ''))
    if not digits:
        return ''
    if digits.startswith('00'):
        digits = digits[2:]
    if digits.startswith('212'):
        digits = digits[3:]
    digits = digits.lstrip('0')
    return digits


def normalize_email(value):
    return str(value or '').strip().lower()


def _strip_accents(text):
    import unicodedata
    return ''.join(
        c for c in unicodedata.normalize('NFKD', text)
        if not unicodedata.combining(c))


def normalize_name(nom, prenom=None, societe=None):
    """Clé de nom pour le rapprochement : accents retirés, minuscules, mots
    triés, ponctuation/espaces écrasés. « Société Bélkacem » et « belkacem
    societe » donnent la même clé. Vide si le nom est trop court (évite de
    rapprocher des leads sur un nom générique d'un seul caractère)."""
    parts = [p for p in (nom, prenom, societe) if p]
    raw = _strip_accents(' '.join(str(p) for p in parts)).lower()
    raw = _re.sub(r'[^a-z0-9 ]', ' ', raw)
    tokens = sorted(t for t in raw.split() if t)
    key = ' '.join(tokens)
    return key if len(key) >= 4 else ''


def _est_vide(instance, champ, valeur):
    """ACRM13 (C-ACRM-008) — LA règle « champ vide » de la fusion : ``None``
    et ``''`` seulement ; ``False`` uniquement pour un booléen NON nullable
    (son « non renseigné »). Un ``0`` saisi (toit plat, 0 étage) n'est JAMAIS
    vide — l'idiome ``in (None, '', False)`` le confondait avec l'absence
    (``0 == False``) et l'écrasait par la valeur de l'absorbé."""
    if valeur is None:
        return True
    if isinstance(valeur, str):
        return valeur == ''
    if valeur is False:
        try:
            from django.db import models as dj_models
            champ_modele = type(instance)._meta.get_field(champ)
        except Exception:  # noqa: BLE001 — champ inconnu : jamais « vide »
            return False
        return (isinstance(champ_modele, dj_models.BooleanField)
                and not champ_modele.null)
    return False


def _completeness(lead):
    """Score « complétude » d'un lead : nombre de champs de fond renseignés.
    Sert à proposer par défaut le survivant le plus riche lors d'une fusion.
    ACRM13 — « renseigné » = non vide au sens de ``_est_vide`` (un 0 compte)."""
    score = 0
    for field in _MERGE_FILL_FIELDS:
        val = getattr(lead, field, None)
        if not _est_vide(lead, field, val):
            score += 1
    return score


def find_duplicate_clusters(company, include_archived=False, *,
                            queryset=None):
    """Scanne TOUS les leads d'une société et regroupe les doublons probables
    par téléphone OU email OU nom normalisé OU adresse OU point GPS
    (union-find, CAD93 pour les deux derniers). Renvoie une liste de clusters
    (chacun une liste de Lead, ≥ 2 membres), triés par taille puis par membre
    le plus récent. Les leads archivés sont inclus seulement si demandé (ils
    restent visibles pour comprendre une fusion passée).

    SUGGESTION, jamais décision : rien n'est fusionné ici. La fusion reste un
    geste humain explicite (``merge_leads``, appelé par l'atelier doublons).

    ALEA27 — ``queryset`` (optionnel, BORNÉ) : l'atelier HTTP transmet
    ``LeadViewSet.get_queryset()`` (société + portée équipe) — un lead hors
    portée n'entre dans aucun cluster. ``None`` = la société entière, voulu
    pour les lectures système (KPI/foyers, sans utilisateur)."""
    base = queryset if queryset is not None else Lead.objects.all()
    qs = base.filter(company=company)
    if not include_archived:
        qs = qs.filter(is_archived=False)
    leads = list(qs)

    parent = {lead.pk: lead.pk for lead in leads}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    # Indexe par chaque clé ; union des leads partageant une clé non vide.
    for keyer in (
        lambda lead: ('p', normalize_phone(lead.telephone)),
        lambda lead: ('e', normalize_email(lead.email)),
        lambda lead: ('n', normalize_name(lead.nom, lead.prenom, lead.societe)),
        # CAD93 — « même foyer » : deux membres d'un même ménage n'ont ni le
        # même numéro ni le même nom, et recevaient donc chacun onze touches.
        # SUGGESTION seulement : ce scan alimente l'atelier doublons, qu'un
        # humain confirme ; aucune fusion n'est faite d'ici.
        lambda lead: ('a', cles_foyer(lead)['adresse']),
        lambda lead: ('g', cles_foyer(lead)['gps']),
    ):
        buckets = {}
        for lead in leads:
            tag, val = keyer(lead)
            if not val:
                continue
            buckets.setdefault((tag, val), []).append(lead.pk)
        for members in buckets.values():
            first = members[0]
            for other in members[1:]:
                union(first, other)

    groups = {}
    by_id = {lead.pk: lead for lead in leads}
    for lead in leads:
        groups.setdefault(find(lead.pk), []).append(lead)

    clusters = [g for g in groups.values() if len(g) >= 2]
    # Chaque cluster : membre le plus récent en tête ; tri global par taille.
    for g in clusters:
        g.sort(key=lambda lead_: lead_.date_creation, reverse=True)
    clusters.sort(
        key=lambda g: (len(g), max(le.date_creation for le in g)),
        reverse=True)
    return clusters, by_id


def cluster_match_keys(group):
    """Clés de rapprochement PARTAGÉES par au moins deux membres d'un cluster
    (pour expliquer dans l'UI POURQUOI ils sont regroupés) : 'telephone',
    'email' et/ou 'nom'. Renvoie une liste ordonnée et stable."""
    out = []
    checks = (
        ('telephone', lambda le: normalize_phone(le.telephone)),
        ('email', lambda le: normalize_email(le.email)),
        ('nom', lambda le: normalize_name(le.nom, le.prenom, le.societe)),
        # CAD93 — dire à l'écran POURQUOI deux fiches sont rapprochées : une
        # même adresse n'est pas la même preuve qu'un même numéro, et le
        # commercial doit pouvoir faire la différence avant de fusionner.
        ('adresse', lambda le: cles_foyer(le)['adresse']),
        ('gps', lambda le: cles_foyer(le)['gps']),
    )
    for label, keyer in checks:
        seen = {}
        shared = False
        for le in group:
            val = keyer(le)
            if not val:
                continue
            if val in seen:
                shared = True
                break
            seen[val] = True
        if shared:
            out.append(label)
    return out


def find_duplicate_leads(lead, *, queryset=None):
    """Leads probablement en double : même téléphone OU email normalisé, même
    société, hors le lead lui-même. Inclut les archivés (pour les retrouver).
    ALEA27 — ``queryset`` borne la recherche (voir
    ``find_duplicates_by_contact``)."""
    return find_duplicates_by_contact(
        lead.company, phone=lead.telephone, email=lead.email,
        exclude_pk=lead.pk, queryset=queryset)


def find_duplicates_by_contact(company, *, phone=None, email=None,
                               exclude_pk=None, queryset=None, whatsapp=None):
    """Leads d'une société partageant un téléphone OU un email normalisé avec
    les valeurs fournies (saisie libre acceptée — mêmes normaliseurs que la
    détection de doublons). Sert AUSSI au contrôle PRÉ-CRÉATION, où aucun Lead
    n'existe encore (d'où l'absence d'instance). Inclut les archivés.

    QW10 — requête INDEXÉE sur les colonnes normalisées maintenues par
    `Lead.save()` (`phone_normalise`/`email_normalise`, backfillées par la
    migration pour les lignes existantes) — jamais un scan Python complet de
    la société à chaque appel.

    ALEA27 — ``queryset`` (optionnel, BORNÉ) : les actions HTTP
    ``duplicates``/``check-duplicates`` transmettent
    ``LeadViewSet.get_queryset()`` (société + portée équipe) — un lead hors
    portée n'est jamais rendu (ni ses PII). ``None`` = la société entière,
    voulu pour les chemins SYSTÈME (webhooks, imports, WhatsApp entrant,
    DSR) qui doivent rapprocher sans utilisateur.

    ACRM32 — un numéro est cherché sur ``phone_normalise`` OU
    ``whatsapp_normalise`` (un lead connu seulement par son WhatsApp est
    retrouvé) ; ``whatsapp`` (optionnel) ajoute un second numéro à chercher
    de la même façon."""
    from django.db.models import Q

    numeros = {k for k in (normalize_phone(phone), normalize_phone(whatsapp))
               if k}
    email = normalize_email(email)
    if not numeros and not email:
        return []
    base = queryset if queryset is not None else Lead.objects.all()
    qs = base.filter(company=company)
    if exclude_pk is not None:
        qs = qs.exclude(pk=exclude_pk)

    q = Q()
    if numeros:
        q |= (Q(phone_normalise__in=numeros)
              | Q(whatsapp_normalise__in=numeros))
    if email:
        q |= Q(email_normalise=email)
    return list(qs.filter(q))


def is_strong_identity_match(other, *, phone=None, email=None):
    """« Identité forte » : `other` partage À LA FOIS l'e-mail normalisé exact
    ET le téléphone normalisé exact avec les valeurs fournies.

    Niveau DISTINCT du rapprochement ordinaire (même téléphone OU même
    e-mail) : le fondateur veut pouvoir dire « très probablement le même
    client » sans jamais fusionner à la place du commercial. Les deux clés
    doivent être non vides des DEUX côtés — un lead sans e-mail (ou sans
    téléphone) n'est jamais une identité forte, seulement un doublon possible.
    """
    phone = normalize_phone(phone)
    email = normalize_email(email)
    if not phone or not email:
        return False
    return (normalize_phone(other.telephone) == phone
            and normalize_email(other.email) == email)


# ── CAD-I ── CAD93 — « même foyer » : l'adresse et le point GPS ─────────────
#
# Trou signalé par le critique de l'audit L3 du 21/09/2026 (§3) : la garde
# `doublon` bloque bien la cadence automatique, mais le rapprochement ne
# compare que le téléphone, l'e-mail et le nom complet — jamais l'ADRESSE.
# Deux membres d'un même foyer (ou deux numéros du même client) passent donc
# au travers et reçoivent chacun onze touches.
#
# OÙ cet indice vit, et où il ne vit PAS. Adresse et GPS sont VIDES à la
# création d'un lead — c'est `valeur_j1` qui les demande à J1 : les mettre
# dans la garde de démarrage ne bloquerait donc rien au bon moment et ferait
# dérailler le démarrage plus tard. L'indice « même foyer » vit dans
# l'ATELIER DOUBLONS, où il est une SUGGESTION qu'un humain confirme —
# `find_duplicates_by_contact` (garde de démarrage, contrôle pré-création,
# rattachement Meta/WhatsApp) n'est pas touchée, et aucune fusion n'est
# jamais faite sans validation.
def normalize_adresse(adresse, ville=None):
    """Clé d'adresse pour le rapprochement — même fabrique que ``normalize_name``.

    Accents retirés, minuscules, ponctuation écrasée, mots TRIÉS : « Rés. Al
    Firdaous, Imm. 4, Bouskoura » et « imm 4 residence al firdaous bouskoura »
    donnent la même clé dès que les mots coïncident. La ville n'est ajoutée
    qu'en COMPLÉMENT d'une adresse déjà renseignée : une ville seule
    rapprocherait tous les leads de Casablanca.

    Vide en dessous de 8 caractères utiles : « lot 4 » n'est pas une adresse,
    et un rapprochement sur un fragment aussi court signalerait des foyers
    qui n'en sont pas — un faux signal coûte plus cher que pas de signal.
    """
    if not adresse or not str(adresse).strip():
        return ''
    parts = [p for p in (adresse, ville) if p]
    raw = _strip_accents(' '.join(str(p) for p in parts)).lower()
    raw = _re.sub(r'[^a-z0-9 ]', ' ', raw)
    tokens = sorted(t for t in raw.split() if t)
    cle = ' '.join(tokens)
    return cle if len(cle) >= 8 else ''


#: Décimales conservées sur les coordonnées GPS pour la clé « même point ».
#: 4 décimales de latitude ≈ 11 m (un degré de latitude ≈ 111 km, donc
#: 0,0001° ≈ 11,1 m) : la taille d'un toit, pas celle d'un quartier. Deux
#: relevés du même toit tombent dans la même case, deux maisons voisines non.
GPS_DECIMALES_FOYER = 4


def normalize_gps(lat, lng):
    """Clé « même point de toiture » : les deux coordonnées ARRONDIES.

    Vide dès qu'une des deux manque — un demi-point ne localise rien. Les
    valeurs arrivent en ``Decimal`` (champs du lead) ou en flottant : les
    deux sont acceptées, et une valeur illisible rend une clé vide plutôt
    qu'une exception dans un scan de doublons.
    """
    if lat is None or lng is None:
        return ''
    try:
        lat = round(float(lat), GPS_DECIMALES_FOYER)
        lng = round(float(lng), GPS_DECIMALES_FOYER)
    except (TypeError, ValueError):
        return ''
    return f'{lat:.{GPS_DECIMALES_FOYER}f},{lng:.{GPS_DECIMALES_FOYER}f}'


def cles_foyer(lead):
    """Les clés « même foyer » d'un lead : ``{'adresse': …, 'gps': …}``.

    Les valeurs vides signifient « rien à rapprocher », jamais « identiques ».
    """
    return {
        'adresse': normalize_adresse(
            getattr(lead, 'adresse', None), getattr(lead, 'ville', None)),
        'gps': normalize_gps(
            getattr(lead, 'gps_lat', None), getattr(lead, 'gps_lng', None)),
    }
