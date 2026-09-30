"""ERR120 — l'échéancier du Devis Final SOMME au Total TTC AFFICHÉ.

Sur le PDF client ``?devis_final=1``, les cases Acompte / Matériel / Solde
sommaient à 1 MAD de MOINS que le Total TTC dès que ses centimes valaient
≥ 0,50 : le reliquat partait de ``int(total)`` (troncature) alors que le total
s'affiche par ``fmt`` (``int(round(total))``). 51 232,80 s'affichait
« 51 233 MAD » au-dessus de trois cases faisant 51 232.

``_repartir_paiement`` est une aide PURE (règle #4 : le moteur ne fait que
rendre) : ``SimpleTestCase``, aucune base.

Run :
    python manage.py test apps.ventes.tests.test_echeancier_somme_total -v2
"""
from django.test import SimpleTestCase

from apps.ventes.quote_engine.generate_devis_premium import (
    _repartir_paiement, fmt,
)

#: Totaux à centimes ≥ 0,50 (rouges avant ERR120), plus des témoins.
TOTAUX = (152990.60, 51232.80, 63186.99, 99999.50, 100000.49, 48000.00,
          12345.50, 0.0)


def _affiche(montant):
    """Le nombre que ``fmt`` imprime, relu en entier."""
    return int(fmt(montant).split(' ')[0].replace(' ', ''))


class EcheancierSommeTotalTest(SimpleTestCase):
    def test_trois_cases_somment_au_total_affiche(self):
        for total in TOTAUX:
            with self.subTest(total=total):
                rep = _repartir_paiement(total, 30, 10)
                somme = rep['acompte'] + rep['materiel'] + rep['solde']
                self.assertEqual(somme, _affiche(total))

    def test_chemin_deux_cases_somme_au_total_affiche(self):
        """Acompte custom qui absorbe le matériel : Acompte + Solde."""
        for total in TOTAUX[:-1]:
            with self.subTest(total=total):
                rep = _repartir_paiement(total, 30, 10,
                                         custom_acompte=10 ** 9)
                self.assertLessEqual(rep['materiel'], 0)
                self.assertEqual(rep['acompte'] + rep['solde2'],
                                 _affiche(total))

    def test_cas_du_constat_51232_80(self):
        rep = _repartir_paiement(51232.80, 30, 10)
        self.assertEqual(_affiche(51232.80), 51233)
        self.assertEqual(rep['total_mad'], 51233)
        self.assertEqual(rep['acompte'] + rep['materiel'] + rep['solde'],
                         51233)

    def test_arrondi_bancaire_identique_des_deux_cotes(self):
        """99 999,50 → 100 000 à l'affichage ET dans la répartition."""
        rep = _repartir_paiement(99999.50, 30, 10)
        self.assertEqual(rep['total_mad'], _affiche(99999.50))

    def test_pourcentages_somment_a_100(self):
        for total in TOTAUX[:-1]:
            with self.subTest(total=total):
                rep = _repartir_paiement(total, 30, 10)
                self.assertEqual(rep['pct_a'] + rep['pct_m'] + rep['pct_s'],
                                 100)

    def test_acompte_custom_borne_err76(self):
        rep = _repartir_paiement(50000.0, 30, 10, custom_acompte=-5)
        self.assertEqual(rep['acompte'], 0)
        rep = _repartir_paiement(50000.0, 30, 10, custom_acompte=10 ** 9)
        self.assertEqual(rep['acompte'], 50000 - rep['solde'])
