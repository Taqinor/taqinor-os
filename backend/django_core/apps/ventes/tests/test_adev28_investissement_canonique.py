"""ADEV28 (C-ADEV-037) — l'investissement des études commercial/industriel et
pompage est le TTC CANONIQUE du devis (``Devis.total_ttc``, palier
``PAS_ARRONDI_DEVIS`` compris), jamais une somme de lignes recalculée en float.

Tirages déterministes (taux 10/20, remises de ligne, remise globale 0 / 3,5 /
7,5 / 12,25) — rejoue la sonde VB p9 (40/40 écarts, ex. 66 200,00 vs
66 246,87). Décision fondateur 08/10/2026 : un devis aux règles d'origine
(envoyé avant les corrections) garde la somme des lignes d'hier.

Test-du-test : remettre ``investissement_ttc(lignes)`` inconditionnel dans
``economie_pompage`` ⇒ ``test_pompage_egal_total_ttc`` échoue.
"""
import itertools
from decimal import Decimal

from django.test import SimpleTestCase, TestCase

from apps.ventes import economie_pompage as E
from apps.ventes.economie_ci import economie_ci_pour_devis
from apps.ventes.models import LigneDevis
from apps.ventes.tests._quote_engine_common import (
    make_client, make_company, make_devis, make_produit, make_user)
from apps.ventes.tests.test_agr_economie_pompage import (
    CHARGES, ETUDE_COUVERTE, lignes_reference, saisies_12000)

REMISES_GLOBALES = ('0', '3.5', '7.5', '12.25')
TAUX = ('10', '20')
REMISES_LIGNE = ('0', '2.5', '5')
PRIX = ('13333.33', '24871.17', '8150.45', '41999.99', '17654.32')


def _tirages():
    """40 tirages déterministes (remise globale × taux × remise ligne × prix)."""
    combos = itertools.product(REMISES_GLOBALES, TAUX, REMISES_LIGNE, PRIX)
    return list(itertools.islice(combos, 0, 120, 3))[:40]


class InvestissementPompagePurTests(SimpleTestCase):
    def test_canonique_transmis_prime_sur_la_somme_des_lignes(self):
        bloc = E.economie_pompage(
            saisies_12000(), sortie_etude=ETUDE_COUVERTE,
            lignes=lignes_reference(), reglages=CHARGES,
            investissement_ttc_canonique=49900.0)
        self.assertEqual(bloc['economie']['flux'][0]['flux_mad'], -49900.0)

    def test_sans_canonique_somme_des_lignes_d_hier(self):
        bloc = E.economie_pompage(
            saisies_12000(), sortie_etude=ETUDE_COUVERTE,
            lignes=lignes_reference(), reglages=CHARGES)
        self.assertEqual(bloc['economie']['flux'][0]['flux_mad'], -50000.0)


class InvestissementCanoniqueTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_ = make_client(self.company)

    def _devis(self, n, remise_globale, taux, remise_ligne, prix):
        devis = make_devis(self.company, self.user, self.client_, [],
                           remise_globale=remise_globale,
                           reference=f'DEV-A28-{n:04d}')
        for k, (desig, qte) in enumerate((('Pompe immergée', '1'),
                                          ('Panneau 550W', '12'))):
            LigneDevis.objects.create(
                devis=devis,
                produit=make_produit(self.company, desig, f'A28-{n}-{k}', prix),
                designation=desig, quantite=Decimal(qte),
                prix_unitaire=Decimal(prix), remise=Decimal(remise_ligne),
                taux_tva=Decimal(taux))
        return devis

    def test_pompage_egal_total_ttc(self):
        ecarts = []
        for n, (rg, taux, rl, prix) in enumerate(_tirages()):
            devis = self._devis(n, rg, taux, rl, prix)
            attendu = float(devis.total_ttc)
            inv = E.investissement_canonique_du_devis(devis)
            somme = E.investissement_ttc(E.lignes_pour_economie(devis))
            if inv is None or abs(inv - attendu) >= 0.01:
                ecarts.append((n, inv, attendu, somme))
        self.assertEqual(ecarts, [], 'investissement pompage ≠ Devis.total_ttc')

    def test_pompage_regles_d_origine_garde_la_somme(self):
        devis = self._devis(99, '7.5', '20', '2.5', '13333.33')
        devis.regles_calcul = 1
        self.assertIsNone(E.investissement_canonique_du_devis(devis))

    def test_ci_egal_total_ttc(self):
        """C&I : l'investissement passé à ``base_economique`` est
        ``option_totaux`` (chaîne canonique, palier compris) — le TTC du devis
        pour un devis à une option, sur 40 tirages."""
        from apps.ventes.utils.options import option_totaux
        for n, (rg, taux, rl, prix) in enumerate(_tirages()):
            devis = self._devis(200 + n, rg, taux, rl, prix)
            self.assertEqual(Decimal(str(option_totaux(devis)['ttc'])),
                             Decimal(str(devis.total_ttc)), n)
        # Sans étude C&I stockée le bloc est omis, mais le chemin reste
        # appelable sans lever (aucune écriture).
        economie_ci_pour_devis(devis, self.company)
