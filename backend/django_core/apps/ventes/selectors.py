"""Sélecteurs LECTURE SEULE du domaine Ventes exposés aux AUTRES apps.

Point d'entrée cross-app : les autres apps lisent les devis à travers ces
fonctions plutôt qu'en important `apps.ventes.models` directement (voir
CLAUDE.md, règle de modularité). Comportement strictement identique aux requêtes
inline d'origine.
"""


def compter_devis(company):
    """SCA22 — nombre de devis d'une société (console fondateur). Point d'entrée
    cross-app en LECTURE : ``authentication`` lit ce compteur sans importer
    ``apps.ventes.models``."""
    from .models import Devis
    return Devis.objects.filter(company=company).count()


def compter_factures(company):
    """SCA22 — nombre de factures d'une société (console fondateur). Lecture
    seule cross-app (jamais un import direct des modèles ventes)."""
    from .models import Facture
    return Facture.objects.filter(company=company).count()


def factures_echues(company, *, today=None):
    """YEVNT3 — Factures en retard d'une société : échéance dépassée, non
    payées, non annulées. Point d'entrée cross-app sanctionné pour
    `apps.notifications` (jamais un import direct de `apps.ventes.models`).
    Lecture seule ; renvoie un QuerySet (peut être vide)."""
    from django.utils import timezone as _tz

    from .models import Facture
    today = today or _tz.localdate()
    return Facture.objects.filter(
        company=company, date_echeance__isnull=False,
        date_echeance__lt=today,
    ).exclude(
        statut__in=[Facture.Statut.PAYEE, Facture.Statut.ANNULEE],
    ).select_related('client', 'created_by')


def get_facture_scoped(company, facture_id):
    """XFAC14 — Facture (AR) scopée société par id, ou ``None``. Point
    d'entrée cross-app (compensation AR/AP) : lire une facture client sans
    importer ``apps.ventes.models``. Lecture seule."""
    from .models import Facture
    return (Facture.objects
            .select_related('client')
            .filter(id=facture_id, company=company).first())


def releve_client_portail(client):
    """XFAC26 — Relevé de compte self-service (portail client) : réutilise
    ``recouvrement._releve_data`` (même patron que l'écran interne, sans
    filtre de portée — le portail montre TOUT le compte du client, jamais un
    sous-ensemble par créateur) et ajoute une mini balance âgée
    (0-30/31-60/61-90/90+) + le solde courant, cohérents avec
    ``balance_agee``. Point d'entrée cross-app pour ``apps.compta``
    (jamais un import de ``apps.ventes.models``). Lecture seule."""
    from decimal import Decimal

    from .models import Facture
    from .recouvrement import _releve_data

    data = _releve_data(client, user=None)

    buckets = {
        'b0_30': Decimal('0'), 'b31_60': Decimal('0'),
        'b61_90': Decimal('0'), 'b90_plus': Decimal('0'),
    }
    qs = (Facture.objects
          .filter(client=client)
          .exclude(statut__in=[Facture.Statut.PAYEE, Facture.Statut.ANNULEE]))
    for facture in qs:
        du = facture.montant_du
        if not du:
            continue
        jr = facture.jours_retard
        if jr <= 30:
            buckets['b0_30'] += du
        elif jr <= 60:
            buckets['b31_60'] += du
        elif jr <= 90:
            buckets['b61_90'] += du
        else:
            buckets['b90_plus'] += du

    data['solde_courant'] = data['totaux']['du']
    data['balance_agee'] = {k: str(v) for k, v in buckets.items()}
    return data


def releve_client_pdf_bytes(client):
    """XFAC26 — PDF du relevé de compte (portail client), même rendu que
    l'écran interne (``client_releve_pdf``). Lecture seule, jamais un import
    hors de ce module côté ``apps.compta``."""
    from .recouvrement import _releve_data
    from .utils.pdf import generate_releve_pdf

    return generate_releve_pdf(client, _releve_data(client, user=None))


def devis_for_lead(lead, ids):
    """Devis d'un lead (dans la société du lead), pour les ids donnés, triés par
    id. Liste matérialisée — comportement identique au filtre inline d'origine."""
    from .models import Devis
    return list(
        Devis.objects.filter(id__in=ids, lead=lead, company=lead.company)
        .order_by('id'))


def get_devis_by_pk(pk):
    """Devis par pk (ou None). Lecture seule, non scopé — l'appelant vérifie la
    société comme avant."""
    from .models import Devis
    return Devis.objects.filter(pk=pk).first()


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


def conception_pour_lead(lead, company):
    """PV78 — la conception 3D la plus RÉCENTE d'un lead, en lecture seule.

    Rend TOUJOURS le même dict ``{kwc, image_url}`` — jamais une clé absente,
    jamais un ``None`` global : une fiche lead sans conception affiche deux
    valeurs vides, elle ne plante pas sur ``undefined``.

    * ``kwc`` — la puissance crête RÉELLEMENT calepinée, lue dans le layout du
      devis (``roof_layout['result']['kwc']``), à défaut la puissance de
      l'étude. C'est le chiffre de la TOITURE, pas une cible commerciale ;
    * ``image_url`` — URL PRÉ-SIGNÉE (lecture seule, expirante) du rendu 3D
      stocké, via le helper existant ``utils.pdf.roof_image_signed_url``.
      Jamais une URL de bucket publique.

    Company-scopée : seul un devis de ``company`` est regardé (un lead d'une
    autre société ne fait rien fuiter). Point d'entrée cross-app pour
    ``apps.crm`` — jamais un import des modèles ventes de son côté.
    """
    vide = {'kwc': None, 'image_url': None}
    lead_id = getattr(lead, 'pk', None) or getattr(lead, 'id', None)
    if not lead_id or company is None:
        return vide
    from .models import Devis
    devis = (Devis.objects
             .filter(lead_id=lead_id, company=company,
                     roof_layout__isnull=False)
             .order_by('-date_creation', '-id')
             .first())
    if devis is None:
        return vide

    layout = devis.roof_layout if isinstance(devis.roof_layout, dict) else {}
    resultat = layout.get('result') if isinstance(layout, dict) else None
    kwc = (resultat or {}).get('kwc') if isinstance(resultat, dict) else None
    if kwc in (None, ''):
        kwc = (devis.etude_params or {}).get('puissance_kwc')
    try:
        kwc = float(kwc) if kwc not in (None, '') else None
    except (TypeError, ValueError):
        kwc = None

    image_url = None
    if devis.roof_image:
        try:
            from .utils.pdf import roof_image_signed_url
            image_url = roof_image_signed_url(devis.roof_image)
        except Exception:  # noqa: BLE001 — un rendu absent ne casse pas la fiche
            image_url = None
    return {'kwc': kwc, 'image_url': image_url}


def is_devis_accepte(devis):
    """Vrai si le devis est au statut « Accepté » (sans exposer l'enum)."""
    from .models import Devis
    return devis.statut == Devis.Statut.ACCEPTE


def production_attendue_pour_devis(devis_id):
    """YSERV8 — production annuelle attendue (kWh) calculée au devis.

    Point d'entrée cross-app en LECTURE SEULE pour ``apps.monitoring`` (jamais
    un import direct de ``ventes.models``) : lit la production annuelle stockée
    dans ``Devis.etude_params['production_annuelle']`` (semée par le moteur
    solaire à la création). Renvoie un ``Decimal`` positif, ou ``None`` si le
    devis n'existe pas, n'a pas d'étude, ou porte une valeur non exploitable.
    """
    from decimal import Decimal, InvalidOperation

    from .models import Devis
    devis = Devis.objects.filter(pk=devis_id).only('etude_params').first()
    if devis is None:
        return None
    params = devis.etude_params or {}
    raw = params.get('production_annuelle')
    if raw is None:
        return None
    try:
        val = Decimal(str(raw))
    except (InvalidOperation, ValueError, TypeError):
        return None
    return val if val > 0 else None


def pr_initial_pour_chantier(installation_id):
    """YSERV8 — énergie annuelle attendue (kWh) du test de performance FG278.

    Point d'entrée cross-app en LECTURE SEULE pour ``apps.monitoring`` : renvoie
    l'``energie_attendue_kwh`` du dernier ``TestPerformanceReception`` (PR
    initial de recette, FG278) lié au chantier donné, ou ``None`` s'il n'y en a
    pas de valeur exploitable. Le PR de recette prime sur l'étude du devis quand
    il existe (mesure terrain > prévision).
    """
    from decimal import Decimal, InvalidOperation

    from .models import TestPerformanceReception
    raw = (TestPerformanceReception.objects
           .filter(chantier_id=installation_id,
                   energie_attendue_kwh__isnull=False,
                   energie_attendue_kwh__gt=0)
           .order_by('-date_mesure', '-created_at')
           .values_list('energie_attendue_kwh', flat=True)
           .first())
    if raw is None:
        return None
    try:
        val = Decimal(str(raw))
    except (InvalidOperation, ValueError, TypeError):
        return None
    return val if val > 0 else None


# ── XPRJ21 — devis accepté → projet (gestion_projet) ─────────────────────────
_MOTS_CLES_MO = (
    'pose', 'installation', 'main d’œuvre', "main d'œuvre",
    'main d’oeuvre', "main d'oeuvre", 'mo ', 'montage',
)


def devis_pour_projet(devis_id, company):
    """Devis ACCEPTÉ prêt pour création de projet (XPRJ21) — scopé société.

    Thin selector cross-app pour ``apps.gestion_projet`` (jamais un import de
    ``ventes.models``) : renvoie ``None`` si le devis n'existe pas, n'est pas
    de la société demandée, ou n'est pas ACCEPTÉ. Sinon un dict LECTURE SEULE
    avec les données nécessaires à la création du projet + du budget v1
    ventilé matériel/main-d'œuvre (classification par mots-clés de la
    désignation, alignée sur ``frontend/src/features/ventes/solar.js``).
    """
    from .models import Devis

    devis = (
        Devis.objects.filter(pk=devis_id, company=company)
        .select_related('client')
        .prefetch_related('lignes')
        .first())
    if devis is None or devis.statut != Devis.Statut.ACCEPTE:
        return None

    lignes_mo = []
    lignes_materiel = []
    for ligne in devis.lignes.all():
        cible = lignes_mo if _est_main_oeuvre(ligne.designation) \
            else lignes_materiel

        cible.append({
            'designation': ligne.designation,
            'total_ht': ligne.total_ht,
        })

    montant_mo = sum((ligne['total_ht'] for ligne in lignes_mo), 0)
    montant_materiel = sum(
        (ligne['total_ht'] for ligne in lignes_materiel), 0)

    return {
        'id': devis.id,
        'reference': devis.reference,
        'client_id': devis.client_id,
        'lead_id': devis.lead_id,
        'montant_materiel': montant_materiel,
        'montant_main_oeuvre': montant_mo,
        'nb_lignes_materiel': len(lignes_materiel),
        'nb_lignes_main_oeuvre': len(lignes_mo),
    }


def _est_main_oeuvre(designation):
    d = (designation or '').lower()
    return any(mot in d for mot in _MOTS_CLES_MO)


def paiements_totaux_par_mode(facture_ids):
    """Totaux + nombre de ``Paiement`` groupés par mode, pour un ensemble de
    factures (thin selector pour apps.pos — rapport Z de session XPOS4)."""
    from django.db.models import Count, Sum
    from .models import Paiement
    if not facture_ids:
        return []
    return list(
        Paiement.objects.filter(facture_id__in=facture_ids)
        .values('mode')
        .annotate(total=Sum('montant'), nb=Count('id')))


def devis_card(devis_id, company):
    """S8 — fiche-carte LECTURE SEULE d'un devis pour le partage dans la
    messagerie. Scopée société : None si le devis n'appartient pas à la société.
    Format {label, subtitle, url}. N'expose aucun prix d'achat/marge."""
    from .models import Devis
    devis = (Devis.objects.filter(pk=devis_id, company=company)
             .select_related('client').first())
    if devis is None:
        return None
    parts = []
    try:
        parts.append(devis.get_statut_display())
    except Exception:  # pragma: no cover - défensif
        pass
    client = getattr(devis, 'client', None)
    if client is not None:
        parts.append(str(client))
    return {
        'label': f'Devis {devis.reference}',
        'subtitle': ' · '.join(p for p in parts if p),
        'url': f'/devis/{devis.pk}',
    }


# ── DC23 — UN référentiel TVA + UN selector `tva_par_taux` ──────────────────
# La ventilation de la TVA par taux était copiée à l'identique dans trois
# propriétés (Devis/Facture/Avoir) ; FEC (exports.py) et DGI (dgi/) la
# reconsommaient. `tva_buckets` est désormais l'UNIQUE implémentation : un
# panier par taux effectif, réconcilié au centime. Les trois modèles et les
# exports DGI/FEC y délèguent → une seule logique de bucket, comportement
# strictement identique (mono-taux : formule d'origine HT×taux sans arrondi par
# panier → figures historiques inchangées ; taux mixtes : panier arrondi au
# centime dont la somme = total TVA).

# Référentiel des taux de TVA marocains (réforme 2024–2026). Source unique de
# vérité côté backend pour les contrôles/labels ; les taux EFFECTIFS d'un
# document restent portés par chaque ligne (taux_tva_effectif) ou le profil
# société (CompanyProfile.tva_standard / tva_panneaux). Ne fixe AUCUNE valeur
# en dur dans les calculs — sert de table de référence partagée.
TAUX_TVA_REFERENTIEL = {
    'standard': 20,     # équipements et prestations
    'panneaux': 10,     # panneaux photovoltaïques (réforme)
    'exonere': 0,       # opérations exonérées
}


def ligne_compte_dans_totaux(li):
    """XSAL5/XSAL14 — une ligne entre-t-elle dans les totaux d'un devis ?

    Est comptée UNIQUEMENT une ligne PRODUIT non optionnelle. Sont exclues des
    totaux (HT/TVA/TTC) : les lignes optionnelles non activées (XSAL5) et les
    lignes de section/note sans prix (XSAL14). Robuste par ``getattr`` : une
    ligne d'un autre modèle (LigneFacture/LigneAvoir, dépourvue de ces
    attributs) est TOUJOURS comptée → factures/avoirs strictement inchangés.
    """
    if getattr(li, 'optionnelle', False):
        return False
    return getattr(li, 'type_ligne', 'produit') == 'produit'


def tva_buckets(lignes, *, fallback_taux, frozen=None):
    """Ventilation TVA canonique (DC23). UNE seule implémentation partagée.

    Args:
        lignes: itérable de lignes exposant ``total_ht`` (Decimal-coercible) et
            ``taux_tva_effectif`` (taux %).
        fallback_taux: taux à utiliser quand il n'y a aucune ligne (mono-taux du
            document).
        frozen: tuple optionnel ``(taux, base_ht, montant)`` pour un montant figé
            (facture de tranche / acompte) — renvoyé tel quel en un seul panier.

    Returns: liste de paniers ``{'taux', 'base_ht', 'montant'}``. Mono-taux :
        formule d'origine (HT × taux, aucun arrondi par panier). Taux mixtes :
        un panier par taux, chaque TVA arrondie au centime.
    """
    from decimal import Decimal, ROUND_HALF_UP
    if frozen is not None:
        taux, base_ht, montant = frozen
        return [{'taux': taux, 'base_ht': base_ht, 'montant': montant}]

    # XSAL5/XSAL14 — exclut les lignes optionnelles non activées et section/note.
    lignes = [li for li in lignes if ligne_compte_dans_totaux(li)]
    buckets = {}
    for ligne in lignes:
        rate = Decimal(str(ligne.taux_tva_effectif))
        buckets[rate] = buckets.get(rate, Decimal('0')) + Decimal(ligne.total_ht)
    if len(buckets) <= 1:
        rate = next(iter(buckets), Decimal(str(fallback_taux)))
        base = sum((Decimal(li.total_ht) for li in lignes), Decimal('0'))
        return [{'taux': rate, 'base_ht': base,
                 'montant': base * rate / Decimal('100')}]

    def q(x):
        return x.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    return [
        {'taux': rate, 'base_ht': q(buckets[rate]),
         'montant': q(buckets[rate] * rate / Decimal('100'))}
        for rate in sorted(buckets)
    ]


# ── QJ29 — Multi-propriétés : totaux par villa + total général ───────────────
# Un seul document, jamais scindé. Deux modes, tous deux additifs :
#   (A) ×N villas identiques : multiplicateur ``etude_params['nombre_proprietes']``
#       (défaut 1) appliqué aux totaux HT/TVA/TTC et à la production/économies.
#   (B) villas différentes : les lignes portent ``groupe_index`` (0 = commun,
#       1..N = villa N) → sous-totaux par villa + total général.
# Quand rien n'est utilisé (pas de groupe, N=1), le chemin mono-système reste
# STRICTEMENT inchangé (aucune de ces fonctions n'est appelée sur ce chemin).


def _canonical_totaux(lignes, *, remise_globale_pct, fallback_taux):
    """QJ29 — chaîne HT → remise → TVA (par taux) → TTC pour un lot de lignes.

    ``lignes`` : itérable de LigneDevis (expose ``total_ht`` et
    ``taux_tva_effectif``). Renvoie un dict {ht_brut, remise, ht_net, tva,
    tva_par_taux, ttc}. La remise globale s'applique proportionnellement à chaque
    panier de taux (comme le builder), réconcilié au centime.
    """
    from decimal import Decimal as D, ROUND_HALF_UP as RH
    # XSAL5/XSAL14 — exclut les lignes optionnelles non activées et section/note.
    lignes = [li for li in lignes if ligne_compte_dans_totaux(li)]
    disc = D(str(remise_globale_pct or 0))

    def q(x):
        return x.quantize(D('0.01'), rounding=RH)

    ht_brut = sum((D(str(li.total_ht)) for li in lignes), D('0'))
    remise = q(ht_brut * disc / D('100')) if disc > 0 else D('0')
    ht_net = q(ht_brut - remise)

    buckets = {}
    for li in lignes:
        rate = D(str(li.taux_tva_effectif
                     if li.taux_tva_effectif is not None else fallback_taux))
        buckets[rate] = buckets.get(rate, D('0')) + D(str(li.total_ht))

    # Chaque panier expose ``ht_net`` ET ``base_ht`` (alias) : ``base_ht`` est la
    # clé qu'attendent les consommateurs de ``tva_buckets`` (UBL, PDF facture),
    # ``ht_net`` reste pour les appelants historiques — les deux valent la base
    # HT nette (après remise) du panier, pour un drop-in compatible (QX1/QX2).
    if len(buckets) <= 1:
        rate = next(iter(buckets), D(str(fallback_taux)))
        tva_amt = q(ht_net * rate / D('100'))
        tva_par_taux = [{'taux': rate, 'montant': tva_amt,
                         'ht_net': ht_net, 'base_ht': ht_net}]
    else:
        rates = sorted(buckets)
        nets = {r: q(buckets[r] * (D('1') - disc / D('100'))) for r in rates}
        residu = q(ht_net - sum(nets.values(), D('0')))
        nets[rates[-1]] = q(nets[rates[-1]] + residu)
        tva_par_taux = [
            {'taux': r, 'montant': q(nets[r] * r / D('100')),
             'ht_net': nets[r], 'base_ht': nets[r]}
            for r in rates
        ]
        tva_amt = q(sum((b['montant'] for b in tva_par_taux), D('0')))

    ttc = q(ht_net + tva_amt)
    return {
        'ht_brut': q(ht_brut), 'remise': remise, 'ht_net': ht_net,
        'tva': tva_amt, 'tva_par_taux': tva_par_taux, 'ttc': ttc,
    }


def multi_villa_totaux(devis):
    """QJ29 — totaux par villa + total général d'un devis multi-propriétés.

    Renvoie None quand le devis n'est PAS multi-villa (aucune ligne groupée) :
    le chemin mono-système reste inchangé. Sinon :
        {
          'groupes': [{'index', 'label', 'totaux': {...}}, ...],  # trié par index
          'grand_total': {...},   # chaîne canonique sur TOUTES les lignes
        }
    ``index`` 0 = équipement commun. Company scoping : on lit uniquement les
    lignes du devis fourni (déjà borné à sa société par l'appelant).
    """
    lignes = list(devis.lignes.all())
    grouped = [li for li in lignes if getattr(li, 'groupe_index', None) is not None]
    if not grouped:
        return None

    fallback = devis.taux_tva
    remise = devis.remise_globale
    by_index = {}
    labels = {}
    for li in lignes:
        idx = getattr(li, 'groupe_index', None)
        if idx is None:
            continue
        by_index.setdefault(idx, []).append(li)
        lbl = (getattr(li, 'groupe_label', '') or '').strip()
        if lbl and idx not in labels:
            labels[idx] = lbl

    groupes = []
    for idx in sorted(by_index):
        default_label = 'Équipement commun' if idx == 0 else f'Villa {idx}'
        groupes.append({
            'index': idx,
            'label': labels.get(idx, default_label),
            'totaux': _canonical_totaux(
                by_index[idx], remise_globale_pct=remise,
                fallback_taux=fallback),
        })

    grand_total = _canonical_totaux(
        [li for li in lignes if getattr(li, 'groupe_index', None) is not None],
        remise_globale_pct=remise, fallback_taux=fallback)
    return {'groupes': groupes, 'grand_total': grand_total}


def nombre_proprietes(devis) -> int:
    """QJ29 (A) — multiplicateur ×N villas identiques stocké dans
    ``etude_params['nombre_proprietes']`` (défaut 1, jamais < 1). N=1 = chemin
    mono-système inchangé."""
    try:
        n = int((devis.etude_params or {}).get('nombre_proprietes', 1) or 1)
    except (TypeError, ValueError):
        n = 1
    return max(1, n)


# ── XFAC15 — score comportement de paiement (agrège FG365) ────────────────

_SCORE_BANDS = (
    (0.20, 'A'), (0.40, 'B'), (0.60, 'C'), (0.80, 'D'),
)


def _score_to_letter(score):
    for threshold, letter in _SCORE_BANDS:
        if score < threshold:
            return letter
    return 'E'


def _retard_reel_jours(facture):
    """Jours émission → encaissement RÉELS pour une facture soldée par
    paiement (dernière date de paiement enregistrée moins émission). Renvoie
    ``None`` si la facture n'a aucun paiement (rien à mesurer)."""
    dernier = None
    for p in facture.paiements.all():
        if p.date_paiement and (dernier is None or p.date_paiement > dernier):
            dernier = p.date_paiement
    if dernier is None or not facture.date_emission:
        return None
    delta = (dernier - facture.date_emission).days
    return delta if delta > 0 else 0


def comportement_paiement(client):
    """XFAC15 — score de comportement de paiement agrégé d'un client.

    AGRÈGE les scores FG365 (``core.payment_delay.payment_delay_risk``, jamais
    ré-implémenté ici) de toutes les factures ouvertes du client + son retard
    moyen RÉEL (jours émission → encaissement, sur les factures déjà payées) →
    une lettre A (excellent payeur) à E (à risque). Un client sans historique
    exploitable (aucune facture payée, aucune facture ouverte) reçoit un score
    NEUTRE (``used_fallback=True`` du moteur pur).

    Renvoie un dict :
      ``{'score': float, 'lettre': 'A'..'E', 'retard_moyen_jours': float,
         'nb_factures_ouvertes': int, 'nb_factures_historique': int,
         'used_fallback': bool}``
    """
    from core.payment_delay import payment_delay_risk
    from .models import Facture

    factures = Facture.objects.filter(
        client=client).exclude(statut=Facture.Statut.ANNULEE).prefetch_related(
        'paiements', 'avoirs')

    retards_reels = []
    for f in factures:
        if f.statut == Facture.Statut.PAYEE:
            r = _retard_reel_jours(f)
            if r is not None:
                retards_reels.append(r)

    retard_moyen = (
        sum(retards_reels) / len(retards_reels) if retards_reels else None)

    ouvertes = [f for f in factures if f.montant_du > 0]
    prior_late = sum(1 for r in retards_reels if r > 0)

    if not ouvertes:
        # Aucune facture ouverte à scorer : le score client se base
        # uniquement sur l'historique (ou tombe au neutre si aucun non plus).
        features = {}
        if retard_moyen is not None:
            features['client_avg_delay_days'] = retard_moyen
            features['client_prior_late_count'] = prior_late
        result = payment_delay_risk(features)
    else:
        scores = []
        for f in ouvertes:
            feats = {
                'days_overdue': f.jours_retard,
                'montant_du': float(f.montant_du),
                'relance_count': f.relances.count(),
            }
            if retard_moyen is not None:
                feats['client_avg_delay_days'] = retard_moyen
                feats['client_prior_late_count'] = prior_late
            scores.append(payment_delay_risk(feats))
        avg_score = sum(r.score for r in scores) / len(scores)
        result = scores[0]
        result.score = avg_score
        result.band = (
            'faible' if avg_score < 0.34 else
            'moyen' if avg_score < 0.67 else 'élevé')

    return {
        'score': round(result.score, 4),
        'lettre': _score_to_letter(result.score),
        'retard_moyen_jours': (
            round(retard_moyen, 1) if retard_moyen is not None else None),
        'nb_factures_ouvertes': len(ouvertes),
        'nb_factures_historique': len(retards_reels),
        'used_fallback': result.used_fallback,
    }


def date_encaissement_prevue(facture, retard_moyen_jours=None):
    """XFAC15 — date d'encaissement PRÉVUE d'une facture ouverte.

    Échéance théorique + retard moyen RÉEL du client (comportemental) au lieu
    de la seule échéance théorique. Sans échéance ou sans retard moyen connu,
    renvoie l'échéance théorique inchangée (comportement neutre/dégradé)."""
    from datetime import timedelta
    if not facture.date_echeance:
        return None
    if not retard_moyen_jours:
        return facture.date_echeance
    return facture.date_echeance + timedelta(days=round(retard_moyen_jours))


# ── XACC29 — Références (pour rapport de continuité des séquences) ────────

def references_factures(company):
    """XACC29 — Références de toutes les ``Facture`` (hors annulées) d'une
    société, pour la détection de trous de séquence côté ``compta`` (jamais un
    import de ``ventes.models`` en dehors de ce module). Lecture seule."""
    from .models import Facture
    return list(
        Facture.objects
        .exclude(statut=Facture.Statut.ANNULEE)
        .filter(company=company)
        .exclude(reference='')
        .values_list('reference', flat=True)
    )


def references_avoirs(company):
    """XACC29 — Références de tous les ``Avoir`` d'une société. Lecture seule."""
    from .models import Avoir
    return list(
        Avoir.objects.filter(company=company)
        .exclude(reference='')
        .values_list('reference', flat=True)
    )


def encours_clients_par_tiers(company):
    """YLEDG13 — encours documentaire (reste dû) par client, factures NON
    annulées d'une société. Point d'entrée cross-app sanctionné pour
    ``apps.compta`` (rapprochement auxiliaire/GL, jamais un import direct de
    ``ventes.models``). Renvoie une liste de dicts ``{'tiers_id', 'nom',
    'encours', 'references'}`` (encours > 0 seulement, ``references`` = les
    factures ouvertes de ce client). Lecture seule."""
    from decimal import Decimal
    from .models import Facture

    par_client = {}
    qs = (Facture.objects
          .filter(company=company)
          .exclude(statut=Facture.Statut.ANNULEE)
          .select_related('client'))
    for facture in qs:
        du = facture.montant_du
        if not du:
            continue
        client = facture.client
        entry = par_client.setdefault(client.id, {
            'tiers_id': client.id,
            'nom': (f'{client.prenom} {client.nom}'.strip()
                    if hasattr(client, 'prenom') else str(client)),
            'encours': Decimal('0'),
            'references': [],
        })
        entry['encours'] += Decimal(du)
        entry['references'].append(facture.reference)
    return [v for v in par_client.values() if v['encours'] > 0]


def encours_ouvert_par_tiers(company):
    """NTCRD4 — encours documentaire OUVERT par client, filtré PAR STATUT :
    somme du reste dû des factures dont le statut n'est ni ``PAYEE`` ni
    ``ANNULEE``. Distinct de ``encours_clients_par_tiers`` (YLEDG13, montant-dû
    only, qui inclut une ``PAYEE`` sans règlement enregistré) : ici l'exclusion
    est portée par le STATUT du document, ce que le module crédit exige (une
    facture marquée soldée ne compte plus dans l'exposition, quel que soit son
    reste dû résiduel). Point d'entrée cross-app sanctionné pour ``apps.credit``
    (jamais un import direct de ``ventes.models``). Renvoie une liste de dicts
    ``{'tiers_id', 'nom', 'encours', 'references'}`` (encours > 0). Lecture
    seule."""
    from decimal import Decimal
    from .models import Facture

    par_client = {}
    qs = (Facture.objects
          .filter(company=company)
          .exclude(statut__in=[Facture.Statut.PAYEE, Facture.Statut.ANNULEE])
          .select_related('client'))
    for facture in qs:
        du = facture.montant_du
        if not du:
            continue
        client = facture.client
        entry = par_client.setdefault(client.id, {
            'tiers_id': client.id,
            'nom': (f'{client.prenom} {client.nom}'.strip()
                    if hasattr(client, 'prenom') else str(client)),
            'encours': Decimal('0'),
            'references': [],
        })
        entry['encours'] += Decimal(du)
        entry['references'].append(facture.reference)
    return [v for v in par_client.values() if v['encours'] > 0]


def reste_du_factures_brouillon(company, client_id):
    """WIR93 — reste dû des factures ``BROUILLON`` d'un client, borné société.

    C'est le SEUL écart d'assiette autorisé entre les deux moteurs de crédit :
    ``encours_ouvert_par_tiers`` (moteur ``apps.credit``, NTCRD4) inclut les
    brouillons, tandis que ``crm.selectors.client_credit_warning`` (moteur
    FG41/XFAC28) ne compte que ``emise``/``en_retard``. Point d'entrée
    cross-app sanctionné pour ``apps.credit.services.ecart_encours_moteurs``
    (jamais un import direct de ``ventes.models``). Lecture seule."""
    from decimal import Decimal
    from .models import Facture

    total = Decimal('0')
    qs = (Facture.objects
          .filter(company=company, client_id=client_id,
                  statut=Facture.Statut.BROUILLON)
          .prefetch_related('paiements', 'avoirs'))
    for facture in qs:
        du = facture.montant_du
        if du:
            total += Decimal(du)
    return total


def ca_devis_factures_par_clients(company, client_ids):
    """XSAL9 — CA (devis + factures) agrégé, PAR client, pour une liste
    d'ids clients d'une même société. Point d'entrée cross-app sanctionné
    pour ``apps.crm`` (consolidation groupe — ``crm.selectors.
    consolidation_client``), jamais un import direct de ``ventes.models``.

    Renvoie un dict ``{client_id: {'ca_devis': Decimal, 'ca_factures':
    Decimal, 'nb_devis': int, 'nb_factures': int}}`` — un client sans devis/
    facture n'apparaît PAS dans le résultat (l'appelant fournit un défaut à
    zéro). Lecture seule ; jamais de fuite cross-société — filtré par
    ``company`` (le devis/facture) ET ``client__company=company`` (le client
    lui-même) EN PLUS de ``client_id__in`` : un ``client_id`` d'une AUTRE
    société ne doit jamais fuiter des chiffres même si (par bug amont ou
    appel API malveillant) un ``Devis``/``Facture`` avait été mal rattaché à
    un client d'une société différente de la sienne."""
    from decimal import Decimal

    from .models import Devis, Facture

    client_ids = list(client_ids or [])
    if not client_ids:
        return {}

    out = {}
    devis_qs = (Devis.objects
                .filter(company=company, client_id__in=client_ids,
                        client__company=company)
                .exclude(statut=Devis.Statut.REFUSE))
    for devis in devis_qs:
        entry = out.setdefault(devis.client_id, {
            'ca_devis': Decimal('0'), 'ca_factures': Decimal('0'),
            'nb_devis': 0, 'nb_factures': 0,
        })
        try:
            entry['ca_devis'] += Decimal(str(devis.total_ttc or 0))
        except Exception:  # noqa: BLE001 — jamais casser la consolidation
            pass
        entry['nb_devis'] += 1

    facture_qs = (Facture.objects
                  .filter(company=company, client_id__in=client_ids,
                          client__company=company)
                  .exclude(statut=Facture.Statut.ANNULEE))
    for facture in facture_qs:
        entry = out.setdefault(facture.client_id, {
            'ca_devis': Decimal('0'), 'ca_factures': Decimal('0'),
            'nb_devis': 0, 'nb_factures': 0,
        })
        try:
            entry['ca_factures'] += Decimal(str(facture.total_ttc or 0))
        except Exception:  # noqa: BLE001 — jamais casser la consolidation
            pass
        entry['nb_factures'] += 1

    return out


def acompte_paye_pour_devis(devis_id, company):
    """YSERV1 — vrai si le devis a au moins une ``Facture`` de
    ``type_facture='acompte'`` au statut ``payee`` — point d'entrée cross-app
    sanctionné pour ``apps.installations`` (jamais un import direct de
    ``apps.ventes.models``). Lecture seule ; ``devis_id`` sans facture
    d'acompte payée (ou inconnu/autre société) renvoie ``False``."""
    from .models import Facture
    if not devis_id:
        return False
    return Facture.objects.filter(
        devis_id=devis_id, company=company,
        type_facture=Facture.TypeFacture.ACOMPTE,
        statut=Facture.Statut.PAYEE,
    ).exists()


def etat_recouvrement_client(company, client_id):
    """YCASH4 — État de recouvrement d'UN client, pour le front du funnel.

    Agrège ce que le blueprint L2C appelle "l'état recouvrement remontant au
    commercial" : le retard maximum parmi ses factures ouvertes, le niveau de
    relance atteint (réutilise ``recouvrement._current_level`` — jamais une
    nouvelle échelle), et l'encours échu total (= somme des ``montant_du``
    des factures en retard, jamais un montant TTC non dû). Ne modifie AUCUN
    statut ; pur agrégat lecture seule pour l'avertissement FG41 enrichi.

    Renvoie :
      ``{'retard_max_jours': int, 'niveau_relance': dict|None,
         'encours_echu': Decimal, 'a_jour': bool}``
    Un client sans facture en retard renvoie ``a_jour=True`` et
    ``encours_echu=0`` — l'appelant n'affiche alors aucun avertissement."""
    from decimal import Decimal
    from .models import Facture
    from .recouvrement import _levels, _current_level

    factures = (
        Facture.objects
        .filter(company=company, client_id=client_id)
        .exclude(statut=Facture.Statut.ANNULEE)
        .prefetch_related('paiements', 'avoirs')
    )

    retard_max = 0
    encours_echu = Decimal('0')
    for f in factures:
        jr = f.jours_retard
        if jr > 0:
            retard_max = max(retard_max, jr)
            encours_echu += f.montant_du

    if retard_max <= 0:
        return {
            'retard_max_jours': 0, 'niveau_relance': None,
            'encours_echu': Decimal('0'), 'a_jour': True,
        }

    niveau = _current_level(retard_max, _levels(company))
    return {
        'retard_max_jours': retard_max,
        'niveau_relance': niveau,
        'encours_echu': encours_echu,
        'a_jour': False,
    }


def analyse_facturation(company, debut, fin):
    """ZFAC10 — Analyse de facturation : agrégat HT/TVA/TTC des factures
    scopées société, groupé par mois d'émission ET par client ET par statut,
    sur ``[debut, fin)``. Factures annulées EXCLUES du CA. Lecture pure —
    aucune écriture. Renvoie une liste de dicts triée par mois puis client :

    ``{'mois': 'YYYY-MM', 'client_id', 'client_nom', 'statut',
       'total_ht', 'total_tva', 'total_ttc', 'nb_factures'}``
    """
    from decimal import Decimal

    from .models import Facture

    factures = (
        Facture.objects
        .filter(company=company, date_emission__gte=debut,
                date_emission__lt=fin)
        .exclude(statut=Facture.Statut.ANNULEE)
        .select_related('client')
    )

    buckets = {}
    for f in factures:
        mois = f.date_emission.strftime('%Y-%m') if f.date_emission else ''
        client_nom = (
            f"{f.client.nom} {f.client.prenom or ''}".strip()
            if f.client_id else ''
        )
        key = (mois, f.client_id, f.statut)
        entry = buckets.setdefault(key, {
            'mois': mois, 'client_id': f.client_id, 'client_nom': client_nom,
            'statut': f.statut, 'total_ht': Decimal('0'),
            'total_tva': Decimal('0'), 'total_ttc': Decimal('0'),
            'nb_factures': 0,
        })
        entry['total_ht'] += f.total_ht
        entry['total_tva'] += f.total_tva
        entry['total_ttc'] += f.total_ttc
        entry['nb_factures'] += 1

    rows = list(buckets.values())
    rows.sort(key=lambda r: (r['mois'], r['client_nom'], r['statut']))
    return rows


def devis_a_facturer(company, *, jours=7, today=None):
    """ZFAC12 — ``Devis`` ``accepte`` d'une société, sans ``Facture`` liée
    depuis PLUS de ``jours`` jours (revenu bloqué en amont, backlog à
    facturer). Un devis déjà facturé (au moins une ``Facture`` via
    ``devis.factures``) est ignoré. Lecture seule."""
    from datetime import timedelta

    from django.utils import timezone

    from .models import Devis

    today = today or timezone.now().date()
    seuil = today - timedelta(days=jours)

    candidats = (
        Devis.objects
        .filter(company=company, statut=Devis.Statut.ACCEPTE,
                date_acceptation__isnull=False,
                date_acceptation__lte=seuil)
        .exclude(factures__isnull=False)
        .distinct()
    )
    return list(candidats)


def tranche_facturee(devis, type_facture):
    """YSERV7 — la facture d'échéancier ``type_facture`` (acompte/
    intermediaire/solde) existe-t-elle déjà pour ce devis ? Lecture seule,
    point d'entrée cross-app sanctionné pour ``apps.installations`` (jamais un
    import direct de ``apps.ventes.models``). Une facture ANNULÉE ne compte
    pas comme émise (la tranche reste due). Renvoie un booléen."""
    if devis is None or not type_facture:
        return False
    from .models import Facture
    return (
        Facture.objects
        .filter(devis=devis, type_facture=type_facture)
        .exclude(statut=Facture.Statut.ANNULEE)
        .exists()
    )


def jours_impaye_facture(facture_id, company):
    """ZCTR2 — Nombre de jours DEPUIS lesquels une facture est impayée.

    Point d'entrée cross-app en LECTURE SEULE pour ``apps.contrats``
    (clôture automatique des contrats impayés) — jamais un import direct de
    ``apps.ventes.models``. Renvoie ``0`` si la facture est introuvable (id
    NULL/inconnu, autre société), déjà payée, annulée, ou sans
    ``date_echeance`` (rien à mesurer) : dans tous ces cas rien n'est dû,
    cohérent avec ``Facture.jours_retard``. Sinon renvoie le nombre de jours
    entiers écoulés depuis ``date_echeance`` (0 si l'échéance n'est pas
    encore dépassée)."""
    from .models import Facture
    if not facture_id:
        return 0
    facture = Facture.objects.filter(
        pk=facture_id, company=company).first()
    if facture is None:
        return 0
    return facture.jours_retard


def lignes_louables_devis(devis, produit_ids_louables):
    """ZCTR6 — Lignes d'un devis dont le produit est LOUABLE.

    Point d'entrée cross-app en LECTURE SEULE pour ``apps.contrats``
    (rattachement d'ordres de location à un devis accepté) — jamais un
    import direct de ``apps.ventes.models`` depuis ``contrats``. L'appelant
    fournit ``produit_ids_louables`` (résolu via
    ``stock.selectors.produits_louables_qs`` — jamais réimporté ici, aucune
    dépendance directe à ``stock``). Renvoie une liste de dicts
    ``{'produit_id', 'quantite', 'ligne_id'}`` — une ligne dont le produit
    n'est PAS louable est simplement absente (ignorée par l'appelant)."""
    from .models import LigneDevis

    if not produit_ids_louables:
        return []
    lignes = (
        LigneDevis.objects
        .filter(devis=devis, produit_id__in=produit_ids_louables)
        .order_by('id')
    )
    return [
        {
            'ligne_id': ligne.id,
            'produit_id': ligne.produit_id,
            'quantite': ligne.quantite,
        }
        for ligne in lignes
    ]


def resoudre_plan_commission(company, owner):
    """XSAL6 — Point d'entrée cross-app (reporting/insights) pour résoudre le
    plan de commission d'un commercial.

    Ordre : plan actif dédié à ``owner`` → plan actif par défaut de la société
    (``owner=None``) → ``None`` (l'appelant retombe alors sur
    ``CompanyProfile.commission_mode``, comportement historique inchangé).
    Lecture seule ; ne consulte jamais ``prix_achat`` ici (la base
    ``marge_interne`` reste calculée et gardée ADMIN-ONLY côté appelant)."""
    from .models import PlanCommission

    if company is None:
        return None
    qs = PlanCommission.objects.filter(company=company, actif=True)
    if owner is not None:
        plan = qs.filter(owner=owner).first()
        if plan is not None:
            return plan
    return qs.filter(owner__isnull=True).first()


def devis_milestones(token):
    """QX34 — jalons post-signature d'un devis, résolus depuis un jeton
    ShareLink (lecture seule, public, tokenisé). Rien n'est muté.

    Dérive la timeline à partir des LIGNES EXISTANTES (aucun nouveau statut) :
    accepté → acompte reçu (Paiement) → matériel commandé (BonCommande) →
    installation (chantier via le sélecteur installations) → facturé.

    Renvoie ``None`` si le jeton est invalide/expiré/sans devis, sinon un dict
    ``{reference, milestones: [{key, label, done, date}]}``. Multi-tenant :
    le jeton borne un unique devis d'une seule société (aucune fuite d'une
    autre société), et jamais de prix d'achat/marge.
    """
    from django.utils import timezone
    from .models import ShareLink

    link = (ShareLink.objects
            .select_related('devis', 'devis__company')
            .filter(token=token).first())
    if link is None or not link.is_valid or not link.devis_id:
        return None
    devis = link.devis

    def _iso(d):
        return d.isoformat() if d is not None else None

    # 1) Accepté.
    accepte = devis.statut in ('accepte',) or devis.date_acceptation is not None
    date_accepte = getattr(devis, 'date_acceptation', None)

    # 2) Acompte reçu — un Paiement existe sur une facture liée au devis.
    from .models import Paiement
    paiement = (Paiement.objects
                .filter(facture__devis=devis)
                .order_by('date_paiement')
                .first())
    if paiement is None:
        # Chaîne BC → facture.
        paiement = (Paiement.objects
                    .filter(facture__bon_commande__devis=devis)
                    .order_by('date_paiement')
                    .first())
    acompte_recu = paiement is not None

    # 3) Matériel commandé — un BonCommande existe.
    bc = getattr(devis, 'bon_commande', None)
    materiel_commande = bc is not None
    date_bc = getattr(bc, 'date_creation', None) if bc else None

    # 4) Installation — chantier lié (via sélecteur installations, jamais
    #    d'import de son modèle).
    chantier = None
    try:
        from apps.installations.selectors import installation_for_devis
        chantier = installation_for_devis(devis)
    except Exception:  # noqa: BLE001 — best-effort
        chantier = None
    installation_faite = chantier is not None

    # 5) Facturé — au moins une facture liée.
    facture_emise = devis.factures.exists() or (
        bc is not None and bc.factures.exists() if bc else False)

    milestones = [
        {'key': 'accepte', 'label': 'Proposition acceptée',
         'done': bool(accepte), 'date': _iso(date_accepte)},
        {'key': 'acompte', 'label': 'Acompte reçu',
         'done': bool(acompte_recu),
         'date': _iso(getattr(paiement, 'date_paiement', None))},
        {'key': 'materiel', 'label': 'Matériel commandé',
         'done': bool(materiel_commande),
         'date': (date_bc.date().isoformat()
                  if hasattr(date_bc, 'date') else _iso(date_bc))},
        {'key': 'installation', 'label': 'Installation',
         'done': bool(installation_faite),
         'date': (getattr(chantier, 'statut', None)
                  if chantier is not None else None)},
        {'key': 'facture', 'label': 'Facturé',
         'done': bool(facture_emise), 'date': None},
    ]
    return {
        'reference': devis.reference,
        'generated_at': timezone.now().isoformat(),
        'milestones': milestones,
    }


def devis_events_for_lead(lead_id, company):
    """QX32be — événements de cycle de vie des devis d'un LEAD (lecture seule).

    Point d'entrée cross-app UNIQUE pour que ``crm`` fusionne les jalons devis
    (envoyé/ouvert/signé/refusé) + un résumé d'engagement dans son historique
    lead, SANS importer ``apps.ventes.models``. Multi-tenant : borné à la
    société fournie (jamais de fuite d'une autre société). Jamais de
    ``prix_achat``/marge.

    Renvoie une liste d'événements triés (plus récents d'abord) :
    ``[{devis_id, reference, kind, label, at, engagement}]`` où ``kind`` ∈
    {sent, opened, signed, refused}. ``engagement`` (résumé par section) n'est
    posé que sur l'événement ``opened``.
    """
    from .models import Devis, ShareLink

    if not lead_id:
        return []
    devis_qs = (Devis.objects
                .filter(lead_id=lead_id, company=company)
                .order_by('-date_creation'))

    # Résumé d'engagement par devis (dernier ShareLink vu).
    links = (ShareLink.objects
             .filter(devis__lead_id=lead_id, devis__company=company)
             .order_by('devis_id', '-created_at'))
    eng_by_devis = {}
    first_view_by_devis = {}
    for lk in links:
        if lk.devis_id not in eng_by_devis:
            eng_by_devis[lk.devis_id] = lk.engagement_summary
            first_view_by_devis[lk.devis_id] = lk.first_viewed_at

    def _iso(d):
        return d.isoformat() if d is not None else None

    events = []
    for devis in devis_qs:
        ref = devis.reference
        if devis.date_envoi is not None:
            events.append({
                'devis_id': devis.id, 'reference': ref, 'kind': 'sent',
                'label': 'Devis envoyé', 'at': _iso(devis.date_envoi),
                'engagement': None,
            })
        fv = first_view_by_devis.get(devis.id)
        if fv is not None:
            events.append({
                'devis_id': devis.id, 'reference': ref, 'kind': 'opened',
                'label': 'Proposition ouverte', 'at': _iso(fv),
                'engagement': eng_by_devis.get(devis.id) or {},
            })
        if devis.statut == 'accepte' and devis.date_acceptation is not None:
            events.append({
                'devis_id': devis.id, 'reference': ref, 'kind': 'signed',
                'label': 'Devis signé', 'at': _iso(devis.date_acceptation),
                'engagement': None,
            })
        if devis.statut == 'refuse' and devis.date_refus is not None:
            events.append({
                'devis_id': devis.id, 'reference': ref, 'kind': 'refused',
                'label': 'Devis refusé', 'at': _iso(devis.date_refus),
                'engagement': None,
            })
    events.sort(key=lambda e: (e['at'] or ''), reverse=True)
    return events


def carnet_commande_par_mois(company, mois_debut, mois_fin):
    """NTFPA12 — revenu ENGAGÉ (carnet de commandes) par mois de facturation
    prévue, pour ``apps.fpa`` (driver revenu engagé).

    Agrège les ``Devis`` ``accepte`` NON encore facturés (aucune ``Facture``
    liée) dont la date de référence (``date_acceptation``) tombe dans
    ``[mois_debut, mois_fin]``. C'est du signé (100 % pondéré), distinct du
    pipeline probabiliste NTFPA11 — un devis accepté sort automatiquement du
    pipeline (son lead passe SIGNED), donc pas de double-compte. Lecture seule ;
    renvoie ``{'YYYY-MM': Decimal}``.
    """
    from decimal import Decimal

    from .models import Devis

    candidats = (
        Devis.objects
        .filter(company=company, statut=Devis.Statut.ACCEPTE,
                date_acceptation__isnull=False,
                date_acceptation__gte=mois_debut,
                date_acceptation__lte=mois_fin)
        .exclude(factures__isnull=False)
        .distinct()
        .prefetch_related('lignes')
    )
    par_mois = {}
    for devis in candidats:
        d = devis.date_acceptation
        cle = f'{d.year:04d}-{d.month:02d}'
        try:
            montant = Decimal(str(devis.total_ttc or 0))
        except Exception:
            montant = Decimal('0')
        par_mois[cle] = par_mois.get(cle, Decimal('0')) + montant
    return par_mois


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


# ── NTPRT10/NTPRT11 — Lectures self-service du PORTAIL CLIENT ───────────────
#
# Point d'entrée cross-app UNIQUE de ``apps.portail`` sur les documents
# ``ventes`` (jamais un import de ``apps.ventes.models`` depuis portail).
# Lecture SEULE et volontairement PAUVRE : uniquement ce qu'un client peut voir
# de SON dossier. Aucun champ de coût/marge n'y figure (``prix_achat``,
# ``marge``… ne sortent JAMAIS vers un écran client — registre
# ``core.permissions.SENSITIVE_FIELDS``), ni aucune donnée interne
# (propriétaire, notes, portée de visibilité).
#
# Les fonctions exigent ``company`` ET ``client_id`` : un ``client_id`` absent
# renvoie VIDE, jamais tous les documents de la société.

def devis_du_client_portail(company, client_id, *, limit=200):
    """NTPRT10 — Devis visibles par le client ``client_id`` sur son portail.

    Les BROUILLONS internes sont EXCLUS : un devis non envoyé n'a jamais été
    montré au client, l'exposer serait une fuite de travail en cours.
    """
    from .models import Devis

    if company is None or not client_id:
        return []
    qs = (Devis.objects
          .filter(company=company, client_id=client_id)
          .exclude(statut=Devis.Statut.BROUILLON)
          .order_by('-date_creation')[:limit])
    return [{
        'id': d.id,
        'reference': d.reference,
        'statut': d.statut,
        'statut_display': d.get_statut_display(),
        'date_creation': d.date_creation,
        'date_validite': d.date_validite,
        'total_ttc': str(d.total_ttc),
        'accepte': d.statut == Devis.Statut.ACCEPTE,
    } for d in qs]


def devis_du_client_portail_obj(company, client_id, devis_id):
    """NTPRT10 — UN devis du client (objet ORM), ou ``None``.

    Le triplet (société, client, id) est exigé : un devis d'un autre client —
    ou d'une autre société — est INTROUVABLE, jamais « trouvé puis refusé ».
    """
    from .models import Devis

    if company is None or not client_id or not devis_id:
        return None
    return (Devis.objects
            .filter(company=company, client_id=client_id, pk=devis_id)
            .exclude(statut=Devis.Statut.BROUILLON)
            .first())


def factures_du_client_portail(company, client_id, *, limit=200):
    """NTPRT11 — Factures visibles par le client ``client_id`` sur son portail.

    Mêmes règles : brouillons internes exclus, aucun champ de coût.
    ``montant_du`` est le reste à payer déjà calculé par le modèle (source
    unique — jamais un recalcul local qui divergerait de l'écran interne).
    """
    from .models import Facture

    if company is None or not client_id:
        return []
    qs = (Facture.objects
          .filter(company=company, client_id=client_id)
          .exclude(statut=Facture.Statut.BROUILLON)
          .order_by('-date_emission', '-id')[:limit])
    return [{
        'id': f.id,
        'reference': f.reference,
        'statut': f.statut,
        'statut_display': f.get_statut_display(),
        'date_emission': f.date_emission,
        'date_echeance': f.date_echeance,
        'montant_ttc': str(f.total_ttc),
        'montant_du': str(f.montant_du),
        'payee': f.statut == Facture.Statut.PAYEE,
    } for f in qs]


def facture_du_client_portail(company, client_id, facture_id):
    """NTPRT11 — UNE facture du client (objet ORM), ou ``None``. Voir ci-dessus."""
    from .models import Facture

    if company is None or not client_id or not facture_id:
        return None
    return (Facture.objects
            .filter(company=company, client_id=client_id, pk=facture_id)
            .exclude(statut=Facture.Statut.BROUILLON)
            .first())


# ── AOF164 — comparaison A/B du calepinage d'un devis (LECTURE SEULE) ───────
#
# C'est le SEUL endroit qui confronte le compte d'un devis EXISTANT au compte
# du moteur. Il ne récrit rien : ni les lignes, ni ``etude_params``, ni
# ``layout_hash``. **Un devis déjà émis ne doit jamais voir son compte bouger
# rétroactivement** — un client qui a reçu « 24 panneaux » a reçu 24 panneaux,
# quelle que soit l'opinion ultérieure du moteur. La fonction refuse donc
# explicitement tout devis hors ``brouillon``, avec un motif en français.

#: Le seul statut dont le compte est encore malléable.
STATUT_RECALCULABLE = 'brouillon'


def comparaison_calepinage_devis(devis):
    """Compare le compte STOCKÉ du devis au compte du moteur — sans rien écrire.

    Rend un dict ``{'recalculable', 'motif', 'compte_stocke', 'compte_moteur',
    'ecart'}``. ``recalculable`` est ``False`` dès que le devis a quitté le
    brouillon : la comparaison reste LISIBLE (elle informe l'arbitrage), mais
    aucun appelant n'a le droit de l'appliquer.
    """
    from .services import _is_panel, compte_moteur_du_layout

    if devis is None:
        return None
    statut = getattr(devis, 'statut', '')
    stocke = 0
    for ligne in devis.lignes.all():
        if _is_panel(ligne.designation):
            stocke += int(ligne.quantite or 0)

    if statut != STATUT_RECALCULABLE:
        return {
            'recalculable': False,
            'motif': ("Devis %s au statut « %s » : un devis déjà émis n'est "
                      'jamais recalculé.'
                      % (devis.reference, devis.get_statut_display())),
            'compte_stocke': stocke,
            'compte_moteur': None,
            'ecart': None,
        }

    # PV42 — le moteur calepine sur le PANNEAU du devis (kit-produit, PV12) :
    # sans lui, cette comparaison opposerait un compte posé sur le module vendu
    # à un compte posé sur le kit générique — un écart inventé de toutes pièces.
    mesure = compte_moteur_du_layout(
        devis.roof_layout, company=getattr(devis, 'company', None),
        devis=devis)
    if mesure is None:
        return {
            'recalculable': True,
            'motif': ('Aucune géométrie exploitable : le moteur ne se '
                      'prononce pas sur ce devis.'),
            'compte_stocke': stocke,
            'compte_moteur': None,
            'ecart': None,
        }
    return {
        'recalculable': True,
        'motif': '',
        'compte_stocke': stocke,
        'compte_moteur': int(mesure['modules']),
        'ecart': int(mesure['modules']) - stocke,
    }


def ca_par_entite(company, entite_ids):
    """NTADM25 — CA (devis retenus + factures) agrégé PAR ENTITÉ (NTADM2).

    Point d'entrée cross-app sanctionné pour ``apps.entites`` (vue consolidée
    « Groupe »), jamais un import direct de ``ventes.models``. MÊME règle de
    calcul que ``ca_devis_factures_par_clients`` — aucune logique dupliquée :
    devis REFUSÉS et factures ANNULÉES exclus, ``total_ttc`` sommé tel quel.

    Renvoie ``{entite_id: {'ca_devis': Decimal, 'ca_factures': Decimal,
    'nb_devis': int, 'nb_factures': int}}`` ; une entité sans document
    n'apparaît PAS (l'appelant fournit un défaut à zéro). Lecture seule,
    bornée à ``company`` — jamais de fuite cross-société.
    """
    from decimal import Decimal

    from .models import Devis, Facture

    ids = [i for i in (entite_ids or []) if i is not None]
    if not ids:
        return {}

    def _vide():
        return {
            'ca_devis': Decimal('0'), 'ca_factures': Decimal('0'),
            'nb_devis': 0, 'nb_factures': 0,
        }

    out = {}
    devis_qs = (Devis.objects
                .filter(company=company, entite_id__in=ids)
                .exclude(statut=Devis.Statut.REFUSE))
    for devis in devis_qs:
        entry = out.setdefault(devis.entite_id, _vide())
        try:
            entry['ca_devis'] += Decimal(str(devis.total_ttc or 0))
        except Exception:  # noqa: BLE001 — jamais casser la consolidation
            pass
        entry['nb_devis'] += 1

    facture_qs = (Facture.objects
                  .filter(company=company, entite_id__in=ids)
                  .exclude(statut=Facture.Statut.ANNULEE))
    for facture in facture_qs:
        entry = out.setdefault(facture.entite_id, _vide())
        try:
            entry['ca_factures'] += Decimal(str(facture.total_ttc or 0))
        except Exception:  # noqa: BLE001 — jamais casser la consolidation
            pass
        entry['nb_factures'] += 1
    return out


# ── QX29/QX30/PACT17 — « Relances du jour » : file d'action des devis ────────

def devis_action_requise(company, *, today=None, jours_sans_reponse=3,
                         jours_avant_expiration=7, jours_non_facture=7):
    """PACT17 — Regroupe les devis d'une société par ACTION ATTENDUE, miroir
    exact de ``apps.sav.selectors.file_action`` (ZSAV6, parité Odoo « Activity
    view »). C'est l'agrégat que ``DevisActionBoardPage`` consomme : il
    n'avait jamais été construit côté serveur, donc l'écran — pourtant publié
    au menu des rôles responsable/admin — était mort.

    Chaque devis tombe dans EXACTEMENT UN panier (le premier qui matche, dans
    l'ordre ci-dessous), pour qu'un même devis ne soit jamais compté deux
    fois :

      * ``acceptes_non_factures`` — accepté depuis plus de
        ``jours_non_facture`` jours sans aucune ``Facture`` liée (réutilise
        ``devis_a_facturer``, ZFAC12 — aucune logique dupliquée) ;
      * ``refuses_sans_motif``    — refusé sans ``motif_refus`` (QX26 : un
        refus sans motif est une information perdue pour toujours) ;
      * ``engagement_relance``    — envoyé et le moteur d'engagement (QX30be,
        ``ShareLink.engagement_triggers_fired``) a déjà tiré au moins un
        déclencheur (non ouvert 24 h / ouvert non signé 48 h / rouvert 3×) ;
      * ``expirant_bientot``      — envoyé, ``date_validite`` dans les
        ``jours_avant_expiration`` jours (échéance non encore dépassée) ;
      * ``envoyes_sans_reponse``  — envoyé depuis plus de
        ``jours_sans_reponse`` jours sans aucun des signaux ci-dessus (palier
        de cadence).

    Les devis ``brouillon`` et ``expire`` ne sont JAMAIS dans un panier : le
    premier n'est pas encore parti, le second n'appelle plus de relance.

    Renvoie ``{'buckets': {clé: {'count': int, 'ids': [int, …]}, …},
    'wa_drafts': {devis_id: 'message'}, 'devis': {devis_id: {…}}}``.

      * ``wa_drafts`` ne porte QUE la file ``engagement_relance`` (le seul cas
        où le serveur sait quoi dire) ; l'écran retombe sur le lien wa.me nu
        partout ailleurs.
      * ``devis`` porte de quoi RENDRE chaque ligne (référence, client,
        téléphone, WhatsApp, total) pour les ids cités. Sans lui l'écran
        devait re-télécharger la liste des devis et n'y trouvait ni
        ``client_telephone`` ni ``client_whatsapp`` (``DevisSerializer`` ne
        les publie pas) : les raccourcis « Appeler » / WhatsApp ne
        s'affichaient JAMAIS, et une référence au-delà de la première page de
        50 tombait sur « #42 ». Le serveur sert donc ce dont l'écran a besoin,
        en un seul appel.

    Lecture seule, bornée à ``company`` — jamais de fuite cross-société.
    Aucun prix d'achat ni marge n'est exposé (règle #4) : seul le total TTC,
    déjà visible du client, accompagne la ligne.
    """
    from datetime import timedelta

    from django.utils import timezone

    from .models import Devis

    today = today or timezone.localdate()
    now = timezone.now()

    envoyes_sans_reponse = []
    acceptes_non_factures = []
    refuses_sans_motif = []
    expirant_bientot = []
    engagement_relance = []
    wa_drafts = {}

    # ── Acceptés non facturés : ZFAC12 tel quel (jamais recodé ici) ──
    for devis in devis_a_facturer(company, jours=jours_non_facture,
                                  today=today):
        acceptes_non_factures.append(devis.id)

    # ── Refusés sans motif (QX26) ──
    refuses_sans_motif.extend(
        Devis.objects
        .filter(company=company, statut=Devis.Statut.REFUSE)
        .exclude(motif_refus__gt='')
        .order_by('id')
        .values_list('id', flat=True)
    )

    # ── Devis ENVOYÉS : un seul panier par devis, priorité au signal le plus
    # fort (engagement mesuré > échéance qui approche > simple cadence).
    envoyes = (Devis.objects
               .filter(company=company, statut=Devis.Statut.ENVOYE)
               .select_related('client')
               .prefetch_related('share_links')
               .order_by('id'))
    limite_expiration = today + timedelta(days=jours_avant_expiration)

    for devis in envoyes:
        declencheurs = set()
        for link in devis.share_links.all():
            declencheurs.update(link.engagement_triggers_fired or [])
        if declencheurs:
            engagement_relance.append(devis.id)
            wa_drafts[devis.id] = _brouillon_relance_engagement(
                devis, declencheurs)
            continue
        if (devis.date_validite is not None
                and today <= devis.date_validite <= limite_expiration):
            expirant_bientot.append(devis.id)
            continue
        envoye_le = devis.date_envoi
        if (envoye_le is not None
                and (now - envoye_le) >= timedelta(days=jours_sans_reponse)):
            envoyes_sans_reponse.append(devis.id)

    paniers = {
        'envoyes_sans_reponse': envoyes_sans_reponse,
        'acceptes_non_factures': acceptes_non_factures,
        'refuses_sans_motif': refuses_sans_motif,
        'expirant_bientot': expirant_bientot,
        'engagement_relance': engagement_relance,
    }
    cites = {i for ids in paniers.values() for i in ids}
    # `prefetch_related('lignes')` : `Devis.total_ttc` itère les lignes — sans
    # ce préchargement, une requête PAR devis affiché (N+1).
    lignes = (Devis.objects
              .filter(company=company, pk__in=cites)
              .select_related('client', 'lead')
              .prefetch_related('lignes'))
    return {
        'buckets': {
            cle: {'count': len(ids), 'ids': list(ids)}
            for cle, ids in paniers.items()
        },
        'wa_drafts': wa_drafts,
        'devis': {d.id: _ligne_action_requise(d) for d in lignes},
    }


def _ligne_action_requise(devis):
    """PACT17 — de quoi RENDRE une ligne de « Relances du jour », rien de plus.

    Le WhatsApp vient du lead lié quand il existe (``crm.Lead.whatsapp``, lu
    par la relation string-FK déjà déclarée — jamais un import de
    ``apps.crm.models``, même motif que ``DevisSerializer.get_lead_nom``),
    sinon le téléphone du client fait office de numéro joignable. Le total est
    rendu en TEXTE décimal (jamais un flottant) — ``formatMAD`` le lit tel
    quel côté écran.
    """
    client = getattr(devis, 'client', None)
    telephone = (getattr(client, 'telephone', '') or '') if client else ''
    whatsapp = ''
    if devis.lead_id:
        whatsapp = getattr(devis.lead, 'whatsapp', '') or ''
    total = devis.total_ttc
    return {
        'id': devis.id,
        'reference': devis.reference or '',
        'client_nom': (getattr(client, 'nom', '') or '') if client else '',
        'client_telephone': telephone,
        'client_whatsapp': whatsapp,
        'total_ttc': str(total) if total is not None else None,
    }


def _brouillon_relance_engagement(devis, declencheurs):
    """PACT17/QX30 — message WhatsApp pré-rempli pour la file d'engagement.

    Le texte suit le déclencheur le plus parlant (jamais un message générique
    quand le serveur sait quoi dire) et ne cite AUCUN prix : un brouillon part
    tel quel dans WhatsApp, il doit rester une relance, pas une offre.
    """
    client = getattr(devis, 'client', None)
    # Prénom + nom, comme partout ailleurs dans ce fichier : « Bonjour Benali »
    # (le patronyme seul) ne se dit pas en français — on salue quelqu'un par
    # son prénom, ou par son nom complet. Un brouillon part TEL QUEL dans
    # WhatsApp : la salutation est la première chose que le client lit.
    prenom = (getattr(client, 'prenom', '') or '').strip() if client else ''
    patronyme = (getattr(client, 'nom', '') or '').strip() if client else ''
    nom = f'{prenom} {patronyme}'.strip()
    salutation = f'Bonjour {nom}' if nom else 'Bonjour'
    reference = getattr(devis, 'reference', '') or ''
    suffixe = f' (réf. {reference})' if reference else ''

    if 'reopened_3x' in declencheurs:
        corps = ('vous avez consulté votre proposition plusieurs fois'
                 f'{suffixe} — puis-je répondre à une question ?')
    elif 'opened_not_signed_48h' in declencheurs:
        corps = (f'avez-vous pu parcourir votre proposition{suffixe} ? '
                 'Je reste disponible pour en discuter.')
    else:
        corps = (f'votre proposition{suffixe} vous attend toujours — '
                 'souhaitez-vous que je vous la présente ?')
    return f'{salutation}, {corps}'


def devis_envoyes_periode(company, *, date_debut=None, date_fin=None,
                          commercial_id=None):
    """NTCPQ24 — Devis ENVOYÉS (ou au-delà) d'une société sur une période.

    Point d'entrée cross-app en LECTURE (``apps.cpq`` bâtit son rapport de
    conformité dessus sans importer ``apps.ventes.models``). La période porte
    sur ``date_envoi`` ; bornes optionnelles (ouvertes si absentes). Précharge
    les lignes/produits (le calcul de conformité les parcourt)."""
    from .models import Devis
    qs = Devis.objects.filter(
        company=company, date_envoi__isnull=False,
    ).select_related('client', 'created_by').prefetch_related(
        'lignes__produit__categorie')
    if date_debut:
        qs = qs.filter(date_envoi__date__gte=date_debut)
    if date_fin:
        qs = qs.filter(date_envoi__date__lte=date_fin)
    if commercial_id:
        qs = qs.filter(created_by_id=commercial_id)
    return qs.order_by('date_envoi', 'id')


def devis_en_cours(company):
    """NTCPQ23 — Devis NON encore acceptés d'une société (brouillon/envoyé).

    Point d'entrée cross-app en LECTURE (``apps.cpq`` s'en sert pour son
    tableau de bord de marge interne, sans importer ``apps.ventes.models``).
    Précharge les lignes et leurs produits (le calcul de marge les parcourt)."""
    from .models import Devis
    return Devis.objects.filter(
        company=company,
        statut__in=(Devis.Statut.BROUILLON, Devis.Statut.ENVOYE),
    ).select_related('client', 'created_by').prefetch_related(
        'lignes__produit__categorie').order_by('-date_creation')


def frequence_co_achat(company, produit_id, *, limite=10):
    """NTCPQ19 — Fréquence de CO-ACHAT d'un produit dans les devis ACCEPTÉS.

    Point d'entrée cross-app en LECTURE (``apps.cpq`` l'appelle sans importer
    ``apps.ventes.models``) : renvoie ``[(produit_id, nb_devis), ...]`` trié par
    fréquence décroissante — les produits apparaissant dans les mêmes devis
    acceptés de la SOCIÉTÉ que ``produit_id``, hors lui-même. Lecture pure,
    jamais de prix d'achat ni de marge."""
    from collections import Counter
    from .models import Devis, LigneDevis

    devis_ids = LigneDevis.objects.filter(
        devis__company=company, devis__statut=Devis.Statut.ACCEPTE,
        produit_id=produit_id).values_list('devis_id', flat=True)
    devis_ids = set(devis_ids)
    if not devis_ids:
        return []
    paires = list(LigneDevis.objects.filter(
        devis_id__in=devis_ids).exclude(
            produit_id=produit_id).exclude(
                produit_id=None).values_list('devis_id', 'produit_id'))
    compteur = Counter({pid: 0 for _, pid in paires})
    vus = set()
    for devis_id, pid in paires:
        if (devis_id, pid) in vus:
            continue  # une même paire ne compte qu'une fois par devis
        vus.add((devis_id, pid))
        compteur[pid] += 1
    return compteur.most_common(limite)


def lots_totaux(devis):
    """NTCPQ18 — Sous-total PAR LOT + total consolidé d'un devis multi-sites.

    Renvoie ``None`` quand le devis ne porte AUCUN lot (chemin mono-site
    strictement inchangé). Sinon ::

        {
          'lots': [{'id', 'nom_lot', 'adresse_site', 'totaux': {...}}, ...],
          'hors_lot': {...} | None,      # lignes non rattachées à un lot
          'total_consolide': {...},      # TOUTES les lignes du devis
        }

    Chaque bloc de totaux passe par la MÊME chaîne canonique
    (``_canonical_totaux`` : HT brut → remise → TVA par taux → TTC) que les
    totaux du devis, donc la somme des lots + hors-lot recolle au total
    consolidé au centime. Company scoping : seules les lignes du devis fourni
    (déjà borné à sa société par l'appelant) sont lues."""
    lots = list(devis.lots.all())
    if not lots:
        return None

    lignes = list(devis.lignes.all())
    fallback = devis.taux_tva
    remise = devis.remise_globale
    par_lot = {}
    for ligne in lignes:
        par_lot.setdefault(ligne.lot_id, []).append(ligne)

    blocs = [{
        'id': lot.id,
        'nom_lot': lot.nom_lot,
        'adresse_site': lot.adresse_site,
        'totaux': _canonical_totaux(
            par_lot.get(lot.id, []), remise_globale_pct=remise,
            fallback_taux=fallback),
    } for lot in lots]

    orphelines = par_lot.get(None, [])
    hors_lot = _canonical_totaux(
        orphelines, remise_globale_pct=remise,
        fallback_taux=fallback) if orphelines else None

    return {
        'lots': blocs,
        'hors_lot': hors_lot,
        'total_consolide': _canonical_totaux(
            lignes, remise_globale_pct=remise, fallback_taux=fallback),
    }


# ── NTCPQ17 — Remises automatiques par palier de VOLUME, en cascade ──────────

def _paliers_volume_actifs(company):
    from .models import PalierRemiseVolume
    return list(PalierRemiseVolume.objects.filter(
        company=company, actif=True))


def _meilleur_palier(paliers, produit, quantite):
    """Palier le plus fort satisfait par ``quantite`` pour ce produit.

    Ordre de préférence : ``priorite`` décroissante, puis ``quantite_min``
    la plus élevée atteinte, puis la remise la plus forte."""
    from decimal import Decimal
    quantite = Decimal(str(quantite or 0))
    candidats = [
        p for p in paliers
        if p.matches_produit(produit) and quantite >= p.quantite_min]
    if not candidats:
        return None
    candidats.sort(
        key=lambda p: (p.priorite, p.quantite_min, p.remise_pct),
        reverse=True)
    return candidats[0]


def _categories_ayant_atteint_leur_seuil(paliers, lignes):
    """Noms de catégories dont le VOLUME cumulé atteint un palier dédié.

    ``lignes`` : itérable de ``{produit, quantite}``. Seuls les paliers portant
    une catégorie comptent ici (un palier « tout le catalogue » n'identifie
    aucune catégorie)."""
    from collections import defaultdict
    from decimal import Decimal
    volumes = defaultdict(Decimal)
    for ligne in lignes:
        produit = ligne.get('produit')
        cat = getattr(getattr(produit, 'categorie', None), 'nom', None)
        if cat:
            volumes[cat] += Decimal(str(ligne.get('quantite') or 0))
    atteintes = set()
    for palier in paliers:
        nom = palier.categorie_nom
        if not nom:
            continue
        if volumes.get(nom, Decimal('0')) >= palier.quantite_min:
            atteintes.add(nom)
    return atteintes


def decomposition_remise_volume(*, company, produit, quantite, lignes=None):
    """NTCPQ17 — DÉCOMPOSITION de la remise volume (remise ligne + cascade).

    * **Remise de ligne** : le meilleur palier satisfait par la quantité de
      CETTE ligne (comportement palier simple, comme XSAL2).
    * **Cascade globale** : quand au moins DEUX catégories du panier atteignent
      chacune leur seuil, les paliers marqués ``cumulable`` dont la
      ``quantite_min`` est couverte par le volume TOTAL du panier s'ajoutent,
      dans l'ordre de ``priorite`` décroissante.

    ``lignes`` : le panier complet (``[{produit, quantite}, ...]``) ; absent, la
    cascade ne se déclenche pas (une seule ligne ne peut pas couvrir deux
    catégories). Renvoie ``{remise_ligne_pct, cascade, remise_totale_pct}`` —
    les remises se COMPOSENT (jamais une addition naïve qui dépasserait 100 %).
    Aucune donnée de marge / ``prix_achat`` n'entre dans ce calcul."""
    from decimal import Decimal, ROUND_HALF_UP

    cent = Decimal('0.01')
    paliers = _paliers_volume_actifs(company)
    vide = {'remise_ligne_pct': '0.00', 'cascade': [],
            'remise_totale_pct': '0.00'}
    if not paliers:
        return vide

    ligne_palier = _meilleur_palier(paliers, produit, quantite)
    remise_ligne = (
        Decimal(str(ligne_palier.remise_pct)) if ligne_palier
        else Decimal('0'))

    cascade = []
    lignes = list(lignes or [])
    if len(lignes) > 1:
        atteintes = _categories_ayant_atteint_leur_seuil(paliers, lignes)
        if len(atteintes) >= 2:
            volume_total = sum(
                (Decimal(str(li.get('quantite') or 0)) for li in lignes),
                Decimal('0'))
            cumulables = [
                p for p in paliers
                if p.cumulable and volume_total >= p.quantite_min
                and (ligne_palier is None or p.id != ligne_palier.id)]
            cumulables.sort(
                key=lambda p: (p.priorite, p.quantite_min), reverse=True)
            cascade = [{
                'palier_id': p.id,
                'categorie_nom': p.categorie_nom,
                'quantite_min': str(p.quantite_min),
                'remise_pct': str(p.remise_pct),
                'portee': 'global',
            } for p in cumulables]

    reste = Decimal('1') - remise_ligne / Decimal('100')
    for entree in cascade:
        reste *= Decimal('1') - Decimal(entree['remise_pct']) / Decimal('100')
    totale = ((Decimal('1') - reste) * Decimal('100')).quantize(
        cent, ROUND_HALF_UP)

    return {
        'remise_ligne_pct': str(remise_ligne.quantize(cent, ROUND_HALF_UP)),
        'remise_ligne_palier_id': ligne_palier.id if ligne_palier else None,
        'cascade': cascade,
        'remise_totale_pct': str(totale),
    }


# ── NTEXT6 — source de liste whitelistée pour les boucles d'automatisation ──

def lignes_devis_pour_automatisation(devis_id, company, *, limite=200):
    """Lignes d'un devis, en LECTURE SEULE, pour une boucle d'automatisation.

    Thin selector cross-app (``apps.automation`` n'importe JAMAIS
    ``ventes.models``) : renvoie une liste de dicts bornée à ``limite``, scopée
    société, n'exposant AUCUN prix d'achat ni marge — uniquement ce qu'une
    sous-action a besoin de connaître d'une ligne. Les décimales sont rendues
    en CHAÎNES : le contexte d'une boucle peut être gelé en JSON (NTEXT7).
    Liste vide si le devis n'existe pas ou appartient à une autre société.
    """
    from .models import Devis

    devis = (Devis.objects.filter(pk=devis_id, company=company)
             .prefetch_related('lignes').first())
    if devis is None:
        return []
    lignes = []
    for ligne in list(devis.lignes.all())[:max(0, int(limite))]:
        lignes.append({
            'id': ligne.pk,
            'designation': ligne.designation,
            'quantite': ('' if ligne.quantite is None
                         else str(ligne.quantite)),
            'produit_id': ligne.produit_id,
            'total_ht': str(ligne.total_ht),
        })
    return lignes


# ── PV17 — contexte COMPLET de l'écran de conception 3D d'un devis ──────────
#
# UN SEUL appel, UN SEUL dict, TOUTES les clés TOUJOURS présentes (contrat
# ``apps/ventes/contract_samples/devis_design_context.json``). L'écran ne doit
# jamais avoir à deviner : une clé absente, c'est un ``.map()`` sur
# ``undefined`` en production — l'incident exact que ``check_api_shapes.py``
# garde. Un panier vide vaut ``[]``, une valeur inconnue vaut ``None`` ou
# ``''``, jamais une clé manquante.
#
# LECTURE PURE : aucun statut, aucune ligne, aucun layout n'est écrit ici.


def _config_carte():
    """Clés carte du builder 3D — MIROIR de ``views/roof_config.py``.

    Mêmes variables d'environnement (``PUBLIC_MAPTILER_KEY`` /
    ``PUBLIC_MAPBOX_TOKEN``), même forme ``{available, maptilerKey,
    mapboxToken}`` : l'écran de conception lit la carte DANS le contexte plutôt
    que d'enchaîner un second appel. Aucune donnée société, aucune écriture.
    """
    import os

    maptiler = os.environ.get('PUBLIC_MAPTILER_KEY', '') or ''
    mapbox = os.environ.get('PUBLIC_MAPBOX_TOKEN', '') or ''
    return {
        'available': bool(maptiler),
        'maptilerKey': maptiler,
        'mapboxToken': mapbox or None,
    }


def contexte_conception_devis(devis, company):
    """PV17 — tout ce que l'écran de conception toiture doit savoir d'un devis.

    Rend ``None`` quand le devis appartient à une AUTRE société (l'appelant
    répond alors 404 — jamais d'oracle d'existence). Sinon un dict à la forme
    FIXE :

        {devis: {id, reference, statut, mode_installation, lead, client,
                 client_nom},
         geometrie: {source, roof_layout, pin, outline},
         cible: {panneaux, kwc, panel_watt, scenario, batterie,
                 avertissements, bill_kwh},
         carte: {available, maptilerKey, mapboxToken},
         modifiable, raison_lecture_seule, avertissements}

    ``geometrie.source`` vaut ``'devis'`` (le devis porte déjà un layout 3D),
    ``'lead'`` (repli sur l'épingle/le contour posés au diagnostic) ou
    ``'none'``. ``modifiable`` est faux — avec une raison FRANÇAISE dans
    ``raison_lecture_seule`` — pour un devis sorti du cycle d'édition
    (accepté/refusé/expiré), un devis agricole (pompage) et un devis
    multi-villa. ``raison_lecture_seule`` vaut ``''`` quand le devis est
    modifiable, jamais ``None``.
    """
    from .models import Devis
    from .services import cible_depuis_lignes

    if devis is None:
        return None
    # Garde société DÉFENSIVE (le queryset de l'appelant borne déjà) : un
    # superutilisateur sans société passe outre, comme partout ailleurs.
    company_id = getattr(company, 'id', None)
    if company_id is not None and devis.company_id != company_id:
        return None

    lead = getattr(devis, 'lead', None)

    # ── Cible : ce que le devis DIT aujourd'hui (PV16) + la conso du lead ──
    cible = cible_depuis_lignes(devis)
    bill_kwh = getattr(lead, 'bill_kwh', None) if lead is not None else None
    try:
        cible['bill_kwh'] = float(bill_kwh) if bill_kwh is not None else None
    except (TypeError, ValueError):
        cible['bill_kwh'] = None

    # ── Géométrie : le layout du devis PRIME sur le repère du lead ──
    layout = devis.roof_layout if isinstance(devis.roof_layout, dict) else None
    if layout:
        source = 'devis'
        roof_layout = layout
        pin_brut = layout.get('pin')
        contour = layout.get('outline')
        pin = pin_brut if isinstance(pin_brut, dict) else None
        outline = contour if isinstance(contour, list) else []
    else:
        roof_layout = None
        point_lead = getattr(lead, 'roof_point', None) if lead else None
        contour_lead = getattr(lead, 'roof_outline', None) if lead else None
        pin = point_lead if isinstance(point_lead, dict) else None
        outline = contour_lead if isinstance(contour_lead, list) else []
        source = 'lead' if (pin or outline) else 'none'

    # Correction fondateur 24/08 — sans épingle posée (ni sur le layout ni sur
    # `lead.roof_point`, tous deux alimentés par le pointeur PUBLIC du site),
    # la carte démarrait systématiquement au niveau Maroc alors que la FICHE
    # du lead porte souvent déjà des coordonnées GPS réelles (`Lead.gps_lat`/
    # `gps_lng`, saisies côté « Toiture & site » du CRM — bornées ±90/±180 en
    # base). Repli RÉEL, jamais une valeur inventée : n'écrit rien nulle part,
    # centre seulement la carte. `source` reste 'lead' (le repère vient bien
    # du lead, juste par un autre champ) ; un devis SANS lead ou dont le lead
    # ne porte aucune des deux coordonnées garde `pin = None` (vue Maroc).
    if pin is None and lead is not None:
        lat = getattr(lead, 'gps_lat', None)
        lng = getattr(lead, 'gps_lng', None)
        if lat is not None and lng is not None:
            pin = {'lat': float(lat), 'lng': float(lng)}
            if source == 'none':
                source = 'lead'

    # ── Modifiable ? Trois raisons de LECTURE SEULE, toutes en français ──
    raison = ''
    if devis.statut in (Devis.Statut.ACCEPTE, Devis.Statut.REFUSE,
                        Devis.Statut.EXPIRE):
        raison = (
            'Devis « %s » : le calepinage n\'est plus modifiable. Utilisez '
            '« Réviser » pour en créer une nouvelle version.'
            % devis.get_statut_display())
    elif devis.mode_installation == Devis.ModeInstallation.AGRICOLE:
        raison = ('Devis agricole (pompage) — le calepinage de toiture ne '
                  's\'applique pas.')
    elif devis.lignes.filter(groupe_index__gte=1).exists():
        raison = ('Devis multi-villa : chaque villa porte son propre '
                  'calepinage — cet écran ne peut pas en modifier une seule.')

    avertissements = list(cible['avertissements'])
    if source == 'none':
        avertissements.append(
            'Aucune géométrie de toiture connue pour ce devis : commencez par '
            'situer le bâtiment sur la carte.')

    client = getattr(devis, 'client', None)
    # PV23bis (fondateur 20/08/2026 : « link this 3D layouter to the quote »)
    # — l'outil 3D doit connaître le CLIENT du devis, pas seulement son nom :
    # téléphone, ville et adresse alimentent le formulaire du builder
    # (`hydrateFromDevis` sait déjà les lire) et le centrage de la carte quand
    # aucune géométrie n'existe. Client d'abord, repli sur le lead (même
    # priorité whatsapp > téléphone que le mode lead de l'écran) ; vide quand
    # personne ne le sait — jamais une valeur inventée.
    telephone = (getattr(client, 'telephone', '') or '').strip() if client else ''
    adresse = (getattr(client, 'adresse', '') or '').strip() if client else ''
    ville = ''  # crm.Client ne porte pas de ville — elle vient du lead.
    if lead is not None:
        telephone = telephone or (getattr(lead, 'whatsapp', '') or '').strip() \
            or (getattr(lead, 'telephone', '') or '').strip()
        adresse = adresse or (getattr(lead, 'adresse', '') or '').strip()
        ville = (getattr(lead, 'ville', '') or '').strip()
    return {
        'devis': {
            'id': devis.pk,
            'reference': devis.reference,
            'statut': devis.statut,
            'mode_installation': devis.mode_installation or '',
            'lead': devis.lead_id,
            'client': devis.client_id,
            'client_nom': (getattr(client, 'nom', '') or '') if client else '',
            'client_telephone': telephone,
            'client_ville': ville,
            'client_adresse': adresse,
        },
        'geometrie': {
            'source': source,
            'roof_layout': roof_layout,
            'pin': pin,
            'outline': outline,
        },
        'cible': cible,
        'carte': _config_carte(),
        'modifiable': not raison,
        'raison_lecture_seule': raison,
        'avertissements': avertissements,
    }


# ═══════════════════════════════════════════════════════════════════════════
# PVCOMPAT (fondateur 20/08/2026) — COMPATIBILITÉ DEUX À DEUX, point d'entrée
# cross-app.
#
# Le CALCUL vit dans ``apps.ventes.compatibilites`` (il tient au moteur
# électrique et au catalogue solaire, donc au domaine Ventes) ; l'ÉCRAN, lui,
# est la fiche produit du STOCK. Les trois fonctions ci-dessous sont la façade
# LICITE de ce calcul : `apps.stock` (et tout autre appelant) les appelle sans
# jamais importer `apps.ventes.compatibilites` ni, à plus forte raison, les
# modèles de ventes — exactement la règle cross-app de CLAUDE.md.
#
# Import FONCTION-LOCAL : ce module est chargé très tôt (les modèles y font des
# appels différés), et `compatibilites` tire `solar_design` + le noyau
# `core.electrique`. Le différer garde ce fichier sans dépendance au chargement.
# ═══════════════════════════════════════════════════════════════════════════
def compatibilites_du_produit(produit, company):
    """PVCOMPAT — la fiche « Compatibilités » d'un produit du stock.

    Forme CONTRACTUELLE committée dans
    ``apps/stock/contract_samples/produit_compatibilites.json`` :
    ``{produit, fiche_incomplete, installable, bilan, familles}``. Lecture
    seule, aucun prix (ni de vente, ni d'achat) ne traverse cette fonction.
    """
    from .compatibilites import compatibilites_du_produit as _impl
    return _impl(produit, company)


def verdict_panneau_onduleur(panneau, onduleur):
    """PVCOMPAT — ``{statut, raisons, …}`` pour un couple panneau/onduleur.

    ``statut`` ∈ ``compatible`` / ``reserve`` / ``incompatible`` / ``inconnu``,
    avec la TAXONOMIE du noyau ``core.electrique`` (bloquant → incompatible,
    alerte → réserve) et jamais un faux OK sur une fiche incomplète.
    """
    from .compatibilites import verdict_panneau_onduleur as _impl
    return _impl(panneau, onduleur)


def verdict_batterie_onduleur(batterie, onduleur):
    """PVCOMPAT — ``{statut, raisons, …}`` pour un couple batterie/onduleur.

    Délègue à la règle batterie UNIQUE du dépôt
    (``services._batterie_compatible``) : l'écran et la composition ne peuvent
    pas diverger.
    """
    from .compatibilites import verdict_batterie_onduleur as _impl
    return _impl(batterie, onduleur)


def share_link_niveau_map(devis_ids):
    """L-NIV-UI (24/08/2026) — ``niveau``/``otp_lecture`` des ``ShareLink``
    DÉJÀ EXISTANTS (jamais un mint) pour un lot de devis.

    Sert à ``apps.crm.serializers`` (fiche lead, onglet Devis) pour que le
    badge de niveau s'affiche dès le chargement de la fiche sans attendre un
    premier clic — le bug corrigé ici : avant, seul un POST ``share-link``
    (mint/re-mint explicite) alimentait l'état affiché côté écran, donc rien
    n'apparaissait après un simple rechargement tant que l'utilisateur n'avait
    pas ré-interagi. Lecture seule pure : ne crée jamais de lien, n'expose
    aucun token (aucun besoin pour le badge) — un devis sans lien encore minté
    est simplement absent du dict retourné."""
    from django.utils import timezone

    from .models import ShareLink
    ids = [i for i in (devis_ids or []) if i is not None]
    if not ids:
        return {}
    rows = (
        ShareLink.objects
        .filter(devis_id__in=ids, expires_at__gt=timezone.now())
        .order_by('devis_id', '-expires_at')
        .values('devis_id', 'niveau', 'otp_lecture', 'sections')
    )
    out = {}
    for row in rows:
        devis_id = row['devis_id']
        if devis_id in out:  # garde la plus récente (première rencontrée)
            continue
        out[devis_id] = {
            'niveau': row['niveau'],
            'otp_lecture': row['otp_lecture'],
            # L-SECT (24/08/2026) — sections déjà posées sur CE lien, pour que
            # le dialogue « Envoyer au client » rouvre sur les cases réellement
            # en vigueur plutôt que sur les défauts. Dict vide = aucune case
            # décochée (comportement par défaut).
            'sections': row['sections'] or {},
        }
    return out
