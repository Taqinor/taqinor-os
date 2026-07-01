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
