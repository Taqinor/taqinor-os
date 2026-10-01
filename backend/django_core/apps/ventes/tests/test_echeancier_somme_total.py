"""ERR120 / QJR623 — l'échéancier imprimé est celui DU DEVIS, et les cases du
Devis final SOMMENT au Total TTC au CENTIME.

Avant : ``payment_terms`` = réglage société seul (l'échéancier négocié
``Devis.echeancier`` était ignoré par le PDF alors que factures et page
publique le suivaient) ; les cases valaient ``round(total × pct / 1000) ×
1000`` avec un reliquat sur un total arrondi au dirham (ERR120) — en direct,
l'acompte réel de 19 156,31 MAD s'imprimait arrondi au millier.

Désormais : ``builder.repartition_paiement`` calcule les cases au centime
(``utils.echeancier.montants_tranches`` : reliquat sur la dernière tranche) ;
le moteur legacy ne fait plus qu'imprimer. Règle #4 : rendu seul.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.ventes.tests.test_echeancier_somme_total"
"""
from decimal import Decimal

from django.test import SimpleTestCase, TestCase

#: Totaux à centimes ≥ 0,50 (rouges avant ERR120), plus des témoins.
TOTAUX = (152990.60, 51232.80, 63186.99, 99999.50, 100000.49, 48000.00,
          12345.50, 0.0)
TERMES = {'acompte': 30, 'materiel': 60, 'solde': 10}
#: QJR624 — un acompte en dirhams démesuré (borné au total, ERR76).
TRANCHES_ENORMES = [{'unite': 'montant', 'valeur': 10 ** 9},
                    {'unite': 'pct', 'valeur': 60},
                    {'unite': 'pct', 'valeur': 10}]


def _somme(*vals):
    return sum(Decimal(str(v)) for v in vals)


class MontantsTranchesTest(SimpleTestCase):
    def test_reliquat_sur_la_derniere_tranche(self):
        from apps.ventes.utils.echeancier import montants_tranches
        m = montants_tranches(Decimal('100.00'),
                              [('a', 33), ('b', 33), ('c', 34)])
        self.assertEqual(m, {'a': Decimal('33.00'), 'b': Decimal('33.00'),
                             'c': Decimal('34.00')})
        m = montants_tranches(Decimal('10.01'), [('a', 50), ('b', 50)])
        self.assertEqual(m['a'] + m['b'], Decimal('10.01'))

    def test_somme_exacte_au_centime(self):
        from apps.ventes.utils.echeancier import montants_tranches
        for total in TOTAUX:
            with self.subTest(total=total):
                m = montants_tranches(total, [('acompte', 40), ('materiel', 50),
                                              ('solde', 10)])
                self.assertEqual(sum(m.values()),
                                 Decimal(str(total)).quantize(Decimal('0.01')))


class RepartitionPaiementTest(SimpleTestCase):
    def test_trois_cases_somment_au_total_au_centime(self):
        from apps.ventes.quote_engine.builder import repartition_paiement
        for total in (51232.80, 152990.60, 99999.50) + TOTAUX:
            with self.subTest(total=total):
                rep = repartition_paiement(total, TERMES)
                if total:
                    self.assertFalse(rep['deux_cases'])
                self.assertEqual(
                    _somme(rep['acompte'], rep['materiel'], rep['solde']),
                    Decimal(str(total)).quantize(Decimal('0.01')))

    def test_plus_d_arrondi_au_millier(self):
        from apps.ventes.quote_engine.builder import repartition_paiement
        rep = repartition_paiement(63854.37, TERMES)
        self.assertEqual(rep['acompte'], 19156.31)   # 30 % au centime

    def test_chemin_deux_cases_somme_au_total(self):
        """Acompte en dirhams qui absorbe le matériel : Acompte + Solde."""
        from apps.ventes.quote_engine.builder import repartition_paiement
        for total in TOTAUX[:-1]:
            with self.subTest(total=total):
                rep = repartition_paiement(total, TERMES, TRANCHES_ENORMES)
                self.assertTrue(rep['deux_cases'])
                self.assertEqual(_somme(rep['acompte'], rep['solde2']),
                                 Decimal(str(total)).quantize(Decimal('0.01')))

    def test_pourcentages_somment_a_100(self):
        from apps.ventes.quote_engine.builder import repartition_paiement
        for total in TOTAUX[:-1]:
            with self.subTest(total=total):
                rep = repartition_paiement(total, TERMES)
                self.assertEqual(rep['pct_a'] + rep['pct_m'] + rep['pct_s'],
                                 100)

    def test_acompte_montant_borne_err76(self):
        from apps.ventes.quote_engine.builder import repartition_paiement
        rep = repartition_paiement(50000.0, TERMES, [
            {'unite': 'montant', 'valeur': -5}, {'unite': 'pct', 'valeur': 60},
            {'unite': 'pct', 'valeur': 10}])
        self.assertEqual(rep['acompte'], 0)
        rep = repartition_paiement(50000.0, TERMES, TRANCHES_ENORMES)
        self.assertEqual(rep['acompte'], 50000)
        self.assertEqual(rep['materiel'], 0)

    def test_acompte_montant_exact_et_reliquat(self):
        from apps.ventes.quote_engine.builder import repartition_paiement
        rep = repartition_paiement(87654.32, TERMES, [
            {'unite': 'montant', 'valeur': 20000},
            {'unite': 'pct', 'valeur': 67.18},
            {'unite': 'pct', 'valeur': 10}])
        self.assertEqual(rep['acompte'], 20000.0)
        self.assertEqual(rep['materiel'], 58886.17)
        self.assertEqual(_somme(rep['acompte'], rep['materiel'], rep['solde']),
                         Decimal('87654.32'))

    def test_le_moteur_legacy_n_arrondit_plus_rien(self):
        from apps.ventes.quote_engine import generate_devis_premium as G
        self.assertFalse(hasattr(G, '_repartir_paiement'))


class EcheancierReelDuDevisTest(TestCase):
    """Échéancier négocié 40 / 50 / 10 : le PDF le suit."""

    def setUp(self):
        from apps.ventes.tests._quote_engine_common import (
            make_client, make_company, make_user)
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)

    def test_payment_terms_et_page_3(self):
        from apps.ventes.quote_engine import generate_devis_premium as G
        from apps.ventes.quote_engine.builder import build_quote_data
        from apps.ventes.tests._quote_engine_common import make_devis
        from apps.ventes.models import Devis
        devis = make_devis(self.company, self.user, self.client_obj, [
            ('Panneau mono 450W', '10', '1500'),
            ('Onduleur réseau 5kW', '1', '9000'),
        ], reference='DEV-QJR623-A')
        Devis.objects.filter(pk=devis.pk).update(echeancier=[
            {'libelle': 'Acompte', 'type': 'acompte', 'pct_or_montant': 40},
            {'libelle': 'Matériel', 'type': 'materiel', 'pct_or_montant': 50},
            {'libelle': 'Solde', 'type': 'solde', 'pct_or_montant': 10},
        ])
        devis.refresh_from_db()
        data = build_quote_data(devis, {'devis_final': True})
        self.assertEqual(data['payment_terms']['acompte'], 40)
        self.assertEqual(data['payment_terms']['materiel'], 50)
        rep = data['montants_tranches']['sans']
        self.assertEqual(rep['pct_a'], 40)
        self.assertEqual(
            _somme(rep['acompte'], rep['materiel'], rep['solde']),
            Decimal(str(data['total_sans'])).quantize(Decimal('0.01')))
        cap = {}
        orig = G._render_pdf_weasyprint
        G._render_pdf_weasyprint = lambda html, out: cap.update(html=html)
        try:
            G.generate_premium_pdf(data, '/tmp/_qjr623_test.pdf')
        finally:
            G._render_pdf_weasyprint = orig
        html = cap['html']
        self.assertIn('>40%</div>', html)
        self.assertIn(G._fmt2_mad(rep['acompte']), html)


class AcompteImprimeEgalFactureTest(TestCase):
    """QJR624 (D-QJR5-10) — l'acompte imprimé du Devis final est EXACTEMENT
    celui que la facture d'acompte portera (``next_tranche``) pour un devis
    sans facture émise : en pourcentage comme en dirhams (l'acompte
    personnalisé du dialogue PDF est écrit dans ``Devis.echeancier``)."""

    def setUp(self):
        from apps.ventes.tests._quote_engine_common import (
            make_client, make_company, make_user)
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)

    def _verifier(self, reference, echeancier):
        from apps.ventes.models import Devis
        from apps.ventes.quote_engine.builder import build_quote_data
        from apps.ventes.tests._quote_engine_common import make_devis
        from apps.ventes.utils.echeancier import next_tranche
        devis = make_devis(self.company, self.user, self.client_obj, [
            ('Panneau mono 450W', '9', '1487.37'),
            ('Onduleur réseau 5kW', '1', '9013.41'),
        ], reference=reference)
        Devis.objects.filter(pk=devis.pk).update(echeancier=echeancier)
        devis.refresh_from_db()
        data = build_quote_data(devis, {'devis_final': True})
        rep = data['montants_tranches']['sans']
        attendu = next_tranche(devis)['ttc']
        self.assertEqual(Decimal(str(rep['acompte'])), attendu)
        return rep

    def test_acompte_en_pourcentage(self):
        self._verifier('DEV-QJR624-PCT', [
            {'libelle': 'Acompte', 'type': 'acompte', 'pct_or_montant': 30},
            {'libelle': 'Matériel', 'type': 'materiel', 'pct_or_montant': 60},
            {'libelle': 'Solde', 'type': 'solde', 'pct_or_montant': 10}])

    def test_acompte_en_dirhams(self):
        rep = self._verifier('DEV-QJR624-MAD', [
            {'libelle': 'Acompte', 'type': 'acompte', 'unite': 'montant',
             'pct_or_montant': 7000},
            {'libelle': 'Matériel', 'type': 'materiel', 'pct_or_montant': 60},
            {'libelle': 'Solde', 'type': 'solde', 'pct_or_montant': 10}])
        self.assertEqual(rep['acompte'], 7000.0)

    def test_les_options_de_rendu_ne_portent_plus_d_acompte(self):
        from apps.ventes.quote_engine import clean_pdf_options
        opts = clean_pdf_options({'payment_mode': 'custom',
                                  'custom_acompte': 12000})
        self.assertNotIn('payment_mode', opts)
        self.assertNotIn('custom_acompte', opts)
