"""ATOT13 (C-ATOT-021) — ORACLE RÉUTILISABLE de la chaîne d'argent.

Vérificateurs (jamais l'objet en mémoire : chaque vérification relit la
facture en base) et stratégies Hypothesis, importés par ATOT14, ATOT15,
ATOT16 et par les audits J5 / J1b / J3. Il ne recalcule RIEN avec une
formule de production : le reste attendu est rebâti depuis les lignes
persistées (paiements, affectations, retenues, avoirs, notes de débit,
abandon), puis comparé à `Facture.montant_du` (D-ATOT-4).

Complémentaire de `_FakeDocumentTotaux` (`apps/ventes/tests/
test_invariants_money.py`) qui garde, lui, le mixin pur sans base.
"""
from decimal import Decimal

from hypothesis import strategies as st

ZERO = Decimal('0')
CENT = Decimal('0.01')

#: Taux de TVA marocains utilisés par les générateurs.
TAUX = (Decimal('0'), Decimal('10'), Decimal('20'))

#: Gestes appliqués au hasard par les propriétés « reste à payer ».
GESTES = ('paiement', 'rejet', 'avoir', 'annulation_avoir')


def _dec(valeur):
    return Decimal(str(valeur if valeur is not None else 0))


def relire(facture):
    """La facture relue en base (jamais l'instance de l'appelant)."""
    from apps.ventes.models import Facture
    return Facture.objects.get(pk=facture.pk)


def reste_brut(facture):
    """Reste à payer NON borné, rebâti depuis les lignes persistées :
    TTC + notes de débit actives − paiements valides (montant + escompte)
    − avances ventilées valides − retenues subies − avoirs actifs −
    abandon."""
    from apps.ventes.models import Paiement
    f = relire(facture)
    valides = [p for p in f.paiements.all()
               if p.statut != Paiement.Statut.REJETE]
    payes = sum((_dec(p.montant) + _dec(p.escompte_montant)
                 for p in valides), ZERO)
    ventile = sum((_dec(a.montant)
                   for a in f.affectations_paiement.select_related('paiement')
                   if a.paiement.statut != Paiement.Statut.REJETE), ZERO)
    retenues = sum((_dec(r.montant) for r in f.retenues_subies.all()), ZERO)
    avoirs = sum((_dec(a.total_ttc) for a in f.avoirs.all()
                  if a.statut != 'annulee'), ZERO)
    notes = sum((_dec(n.total_ttc) for n in f.notes_debit.all()
                 if n.statut == 'emise'), ZERO)
    return (_dec(f.total_ttc) + notes - payes - ventile - retenues - avoirs
            - _dec(f.abandon_montant))


def verifier_reste_a_payer(facture):
    """Invariants « reste à payer » d'une facture persistée :
    `montant_du == max(0, reste_brut)`, `0 ≤ montant_du ≤ TTC + notes`,
    et — hors brouillon/annulée — « payée » ⇔ dû ≤ 0. Lève AssertionError
    (message en français) ; renvoie le dû relu."""
    from apps.ventes.models import Facture
    f = relire(facture)
    brut = reste_brut(f)
    attendu = brut if brut > 0 else ZERO
    du = _dec(f.montant_du)
    plafond = _dec(f.total_ttc) + sum(
        (_dec(n.total_ttc) for n in f.notes_debit.all()
         if n.statut == 'emise'), ZERO)
    assert abs(du - attendu) <= ZERO, (
        f'{f.reference} : montant_du {du} ≠ reste attendu {attendu} '
        f'(brut {brut}).')
    assert ZERO <= du <= plafond, (
        f'{f.reference} : montant_du {du} hors de [0, {plafond}].')
    if f.statut not in (Facture.Statut.BROUILLON, Facture.Statut.ANNULEE):
        payee = f.statut == Facture.Statut.PAYEE
        assert payee == (du <= CENT), (
            f'{f.reference} : statut {f.statut} avec un dû de {du} '
            '(« payée » si et seulement si dû ≤ 0).')
    return du


def verifier_chaine_document(document, *, figures=None):
    """Arithmétique intra-document (D-ATOT-1) : `ht_brut − remise − arrondi
    = ht_net` et `ht_net + Σ tva_par_taux = ttc`, au centime.

    `figures` (facultatif) — dict `{ht_brut, remise, arrondi, ht_net,
    tva_par_taux|tva, ttc}` de nombres LUS (PDF, API) à vérifier à la place
    de `document.totaux_affichage`."""
    t = figures if figures is not None else document.totaux_affichage
    ht_brut, remise = _dec(t['ht_brut']), _dec(t.get('remise'))
    arrondi, ht_net = _dec(t.get('arrondi')), _dec(t['ht_net'])
    if 'tva_par_taux' in t:
        tva = sum((_dec(b['montant']) for b in t['tva_par_taux']), ZERO)
    else:
        tva = _dec(t['tva'])
    ttc = _dec(t['ttc'])
    assert ht_brut - remise - arrondi == ht_net, (
        f'Sous-total {ht_brut} − remise {remise} − arrondi {arrondi} '
        f'≠ Total HT {ht_net}.')
    assert ht_net + tva == ttc, (
        f'Total HT {ht_net} + TVA {tva} ≠ TTC {ttc}.')
    return True


# ── Stratégies Hypothesis ──────────────────────────────────────────────────

montants = st.decimals(min_value=Decimal('50'), max_value=Decimal('50000'),
                       places=2, allow_nan=False, allow_infinity=False)

ligne_strategie = st.fixed_dictionaries({
    'prix_unitaire': montants,
    'quantite': st.integers(min_value=1, max_value=12).map(Decimal),
    'remise': st.sampled_from([Decimal('0'), Decimal('5'), Decimal('12.5')]),
    'taux_tva': st.sampled_from(TAUX),
})

facture_strategie = st.fixed_dictionaries({
    'lignes': st.lists(ligne_strategie, min_size=1, max_size=4),
    'remise_globale': st.sampled_from(
        [Decimal('0'), Decimal('3'), Decimal('10')]),
})

#: Fraction (en %) d'un montant appliquée par un geste (paiement, avoir).
fraction_strategie = st.integers(min_value=5, max_value=100)

geste_strategie = st.tuples(st.sampled_from(GESTES), fraction_strategie)

gestes_strategie = st.lists(geste_strategie, min_size=1, max_size=6)
