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


# ── VNT16 — plan_facturation sur le panier RÉEL du devis 388 ────────────────
#: Lignes reproduisant ``option_totaux(388)`` (prod 12/10/2026) : HT 41 553,33
#: / TVA 7 446,67 / TTC 49 000,00 ; 10 % base 8 640,00 / 864,00 ; 20 % base
#: 32 913,33 / 6 582,67 (remise 10 %, arrondi au 100 MAD inférieur).
LIGNES_388 = [('Panneau 600 W', '8', '1200', '10'),
              ('Onduleur + structure + pose', '1', '36643.50', '20')]
ECHEANCIER_LIBRE = [
    {'type': 'acompte', 'libelle': 'Acompte', 'unite': 'montant',
     'pct_or_montant': 15000},
    {'type': 'materiel', 'libelle': 'Livraison du matériel',
     'pct_or_montant': 60},
    {'type': 'solde', 'libelle': 'Solde', 'unite': 'montant',
     'pct_or_montant': 4600}]


def creer_devis_388(company, user, client, reference, echeancier=None,
                    statut='accepte', **champs):
    """Devis ACCEPTÉ au panier réel du 388 (partagé par les tests VNT)."""
    from apps.ventes.models import Devis
    from apps.ventes.tests._quote_engine_common import make_devis
    devis = make_devis(company, user, client, LIGNES_388,
                       remise_globale='10', reference=reference)
    Devis.objects.filter(pk=devis.pk).update(
        statut=statut, echeancier=echeancier, **champs)
    devis.refresh_from_db()
    return devis


def facture_tranche(devis, reference, cle, ttc, ht, tva, statut='emise',
                    type_facture='acompte', ventilation=None):
    from apps.ventes.models import Facture
    return Facture.objects.create(
        company=devis.company, reference=reference, devis=devis,
        client=devis.client, statut=statut, type_facture=type_facture,
        cle_tranche=cle, montant_ttc=Decimal(ttc), montant_ht=Decimal(ht),
        montant_tva=Decimal(tva), ventilation_tva=ventilation)


VENT_ACOMPTE_15000 = [{'taux': '10.00', 'base_ht': '2644.90', 'montant': '264.49'},
                      {'taux': '20.00', 'base_ht': '10075.51',
                       'montant': '2015.10'}]


class PlanFacturationVenteTest(TestCase):
    """VNT16 — ``vente_facturation.plan_facturation`` : cibles cumulatives
    bornées, chaîne de versions (``superseded_by``), brouillon = PRÉVU, TVA
    close au centime par taux. Goldens vérifiés sur le panier réel du 388."""

    def setUp(self):
        from apps.ventes.tests._quote_engine_common import (
            make_client, make_company, make_user)
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)

    def _devis(self, reference, echeancier=None, **champs):
        return creer_devis_388(self.company, self.user, self.client_obj,
                               reference, echeancier, **champs)

    def test_fixture_rend_les_bases_du_388(self):
        from apps.ventes.utils.options import option_totaux
        tot = option_totaux(self._devis('DEV-VNT16-FIX'))
        self.assertEqual((tot['ht'], tot['tva'], tot['ttc']),
                         (Decimal('41553.33'), Decimal('7446.67'),
                          Decimal('49000.00')))
        self.assertEqual(
            [(Decimal(str(b['base_ht'])), Decimal(str(b['montant'])))
             for b in tot['tva_par_taux']],
            [(Decimal('8640.00'), Decimal('864.00')),
             (Decimal('32913.33'), Decimal('6582.67'))])

    def test_facture_rattachee_depuis_la_v1_cible_cumulee(self):
        """[15 000 MAD, 60 %, reste] ; facture émise 16 350 rattachée depuis
        la V1 ⇒ matériel 28 050 (= 44 400 − 16 350), solde 4 600, Σ 49 000."""
        from apps.ventes.models import Devis
        from apps.ventes.vente_facturation import (
            chaine_vente, factures_de_la_vente, plan_facturation)
        v1 = self._devis('DEV-VNT16-V1', ECHEANCIER_LIBRE)
        v2 = self._devis('DEV-VNT16-V2', ECHEANCIER_LIBRE,
                         version=2, version_parent=v1)
        Devis.objects.filter(pk=v1.pk).update(is_active=False,
                                              superseded_by=v2)
        f1 = facture_tranche(v1, 'FAC-VNT16-1', 'acompte', '16350.00',
                             '13865.00', '2485.00')
        v2.refresh_from_db()
        self.assertEqual([d.pk for d in chaine_vente(v2)], [v1.pk, v2.pk])
        self.assertEqual([f.pk for f in factures_de_la_vente(v2)], [f1.pk])
        plan = plan_facturation(v2)
        tr = {t['cle']: t for t in plan['tranches']}
        self.assertEqual(tr['acompte']['statut'], 'emise')
        self.assertEqual(tr['materiel']['montant_ttc'], Decimal('28050.00'))
        self.assertEqual(tr['materiel']['cible_cumul_ttc'],
                         Decimal('44400.00'))
        self.assertEqual(tr['solde']['montant_ttc'], Decimal('4600.00'))
        self.assertEqual(sum(t['montant_ttc'] for t in plan['tranches']),
                         Decimal('49000.00'))
        for t in plan['tranches']:
            self.assertEqual(t['ht'] + t['tva'], t['montant_ttc'], t['cle'])
        self.assertEqual(plan['emis_net'], Decimal('16350.00'))
        self.assertEqual(plan['prochaine']['cle'], 'materiel')

    def test_golden_388_acompte_libre_et_solde(self):
        from apps.ventes.vente_facturation import plan_facturation
        devis = self._devis('DEV-VNT16-388', [
            {'type': 'acompte', 'libelle': 'Acompte', 'unite': 'montant',
             'pct_or_montant': 15000},
            {'type': 'solde', 'libelle': 'Solde', 'unite': 'montant',
             'pct_or_montant': 34000}])
        plan = plan_facturation(devis)
        acompte, solde = plan['tranches']
        self.assertEqual((acompte['montant_ttc'], acompte['ht'], acompte['tva']),
                         (Decimal('15000.00'), Decimal('12720.41'),
                          Decimal('2279.59')))
        self.assertEqual(acompte['ventilation_tva'], VENT_ACOMPTE_15000)
        self.assertEqual((solde['montant_ttc'], solde['ht'], solde['tva']),
                         (Decimal('34000.00'), Decimal('28832.92'),
                          Decimal('5167.08')))
        self.assertEqual(solde['ventilation_tva'], [
            {'taux': '10.00', 'base_ht': '5995.10', 'montant': '599.51'},
            {'taux': '20.00', 'base_ht': '22837.82', 'montant': '4567.57'}])
        for taux, base, tva in (('10.00', '8640.00', '864.00'),
                                ('20.00', '32913.33', '6582.67')):
            vents = [b for t in plan['tranches'] for b in t['ventilation_tva']
                     if b['taux'] == taux]
            self.assertEqual(sum(Decimal(b['base_ht']) for b in vents),
                             Decimal(base))
            self.assertEqual(sum(Decimal(b['montant']) for b in vents),
                             Decimal(tva))
        self.assertEqual(acompte['pourcentage'], Decimal('30.61'))

    def test_un_brouillon_est_prevu_jamais_emis(self):
        from apps.ventes.vente_facturation import plan_facturation
        devis = self._devis('DEV-VNT16-BR', ECHEANCIER_LIBRE)
        facture_tranche(devis, 'BROUILLON-VNT16', 'acompte', '15000.00',
                        '12720.41', '2279.59', statut='brouillon')
        plan = plan_facturation(devis)
        self.assertEqual(plan['emis_net'], Decimal('0.00'))
        self.assertEqual(plan['brouillons'], Decimal('15000.00'))
        self.assertEqual(plan['reste_a_facturer'], Decimal('34000.00'))
        self.assertEqual(plan['tranches'][0]['statut'], 'brouillon')
        self.assertEqual(plan['prochaine']['cle'], 'materiel')
        self.assertEqual(plan['prochaine']['montant_ttc'], Decimal('29400.00'))
