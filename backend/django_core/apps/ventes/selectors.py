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
