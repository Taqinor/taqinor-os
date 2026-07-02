"""Sélecteurs LECTURE SEULE du domaine Ventes exposés aux AUTRES apps.

Point d'entrée cross-app : les autres apps lisent les devis à travers ces
fonctions plutôt qu'en important `apps.ventes.models` directement (voir
CLAUDE.md, règle de modularité). Comportement strictement identique aux requêtes
inline d'origine.
"""


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

    lignes = list(lignes)
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
    lignes = list(lignes)
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

    if len(buckets) <= 1:
        rate = next(iter(buckets), D(str(fallback_taux)))
        tva_amt = q(ht_net * rate / D('100'))
        tva_par_taux = [{'taux': rate, 'montant': tva_amt, 'ht_net': ht_net}]
    else:
        rates = sorted(buckets)
        nets = {r: q(buckets[r] * (D('1') - disc / D('100'))) for r in rates}
        residu = q(ht_net - sum(nets.values(), D('0')))
        nets[rates[-1]] = q(nets[rates[-1]] + residu)
        tva_par_taux = [
            {'taux': r, 'montant': q(nets[r] * r / D('100')), 'ht_net': nets[r]}
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
