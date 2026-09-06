"""AUD189 — la chaîne MONO-TAUX de ventes/selectors rend les mêmes totaux
quantifiés que la chaîne canonique.

Deux chaînes d'arrondi coexistaient sur la MÊME facture : la branche mono-taux
de ``tva_buckets`` rendait ``base × taux`` NON quantifié (« la quantification
finale étant déléguée à l'affichage »), face à la chaîne canonique
``_canonical_totaux`` qui, elle, quantifie en ROUND_HALF_UP à chaque étage.
La branche MULTI-taux de ``tva_buckets`` quantifiait déjà : seul le mono-taux
ne le faisait pas.
"""
from decimal import Decimal

from django.test import SimpleTestCase

from apps.ventes.selectors import _canonical_totaux, tva_buckets


class _Ligne:
    """Ligne minimale au contrat lu par les deux chaînes."""

    def __init__(self, total_ht, taux):
        self.total_ht = Decimal(total_ht)
        self.taux_tva_effectif = Decimal(taux)
        self.type_ligne = 'produit'
        self.optionnelle = False
        self.quantite = Decimal('1')
        self.prix_unitaire = self.total_ht
        self.remise = Decimal('0')

    @property
    def est_ligne_produit(self):
        return True

    @property
    def compte_dans_totaux(self):
        return True


class TestPariteMonoTauxEtCanonique(SimpleTestCase):
    #: HT choisis pour que HT × taux tombe sur une bascule au demi-centime :
    #: 125.05 × 10 % = 12.505 → 12.51 (et non 12.50 en arrondi bancaire).
    LIGNES = [_Ligne('125.05', '10')]

    def test_tva_monotaux_est_quantifiee_half_up(self):
        """ROUGE avant le correctif : montant = 12.505 (non quantifié)."""
        panier = tva_buckets(self.LIGNES, fallback_taux=Decimal('10'))
        self.assertEqual(len(panier), 1)
        self.assertEqual(panier[0]['montant'], Decimal('12.51'))
        self.assertEqual(panier[0]['base_ht'], Decimal('125.05'))

    def test_meme_resultat_que_la_chaine_canonique(self):
        canonique = _canonical_totaux(
            self.LIGNES, remise_globale_pct=0, fallback_taux=Decimal('10'))
        panier = tva_buckets(self.LIGNES, fallback_taux=Decimal('10'))
        self.assertEqual(panier[0]['montant'],
                         canonique['tva_par_taux'][0]['montant'])
        self.assertEqual(panier[0]['base_ht'],
                         canonique['tva_par_taux'][0]['base_ht'])
        self.assertEqual(
            sum((p['montant'] for p in panier), Decimal('0')),
            canonique['tva'])

    def test_multitaux_inchange(self):
        """La branche multi-taux quantifiait déjà : rien ne bouge."""
        lignes = [_Ligne('125.05', '10'), _Ligne('200.00', '20')]
        panier = tva_buckets(lignes, fallback_taux=Decimal('20'))
        self.assertEqual(len(panier), 2)
        par_taux = {p['taux']: p['montant'] for p in panier}
        self.assertEqual(par_taux[Decimal('10')], Decimal('12.51'))
        self.assertEqual(par_taux[Decimal('20')], Decimal('40.00'))

    def test_cas_courant_sans_bascule_inchange(self):
        """Un montant rond rend exactement ce qu'il rendait hier."""
        lignes = [_Ligne('10000', '20')]
        panier = tva_buckets(lignes, fallback_taux=Decimal('20'))
        self.assertEqual(panier[0]['montant'], Decimal('2000.00'))
