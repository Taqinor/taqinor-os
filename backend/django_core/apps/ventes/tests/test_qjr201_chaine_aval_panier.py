"""QJR201 — TOUTE la chaîne aval lit le panier corrigé par QJR200.

QJR200 a déclaré la règle QF9 (« un panier dont l'onduleur n'est pas Huawei
perd son Smart Meter et sa clé Wi-Fi ») UNE SEULE FOIS, dans le noyau monnaie.
Ce module prouve que les CINQ consommateurs qui produisaient l'écart client la
reçoivent bien — échéancier, solde avant acceptation, pro-forma, commission
(base = ``Devis.total_ht``) et ``Devis.total_ttc`` — et que les DEUX chemins de
PDF jamais exercés par la contre-visite (la tâche Celery ``generer-pdf`` et le
PDF joint à l'email) bâtissent le MÊME document que le chemin synchrone.

TEST ROUGE D'ABORD : avant QJR200, la somme des tranches de l'échéancier
(bâtie sur ``option_totaux``) dépassait le total imprimé de 3 000 TTC — les
deux accessoires Huawei orphelins que le PDF ne montre pas.

Run:
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_qjr201_chaine_aval_panier -v 2
"""
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.ventes.models import Devis
from apps.ventes.tests._quote_engine_common import (
    DEUX_OPTIONS, make_client, make_company, make_devis, make_user,
)
from apps.ventes.tests.test_qjr200_panier_accessoires_noyau import (
    LIGNES_HUAWEI_DEYE,
)
from apps.ventes.utils.echeancier import (
    creer_facture_tranche, next_tranche, solde_devis,
)
from apps.ventes.utils.options import AVEC_BATTERIE, option_lines, option_totaux
from apps.ventes.utils.references import create_with_reference


def _q(x):
    return Decimal(str(x)).quantize(Decimal('0.01'))


class _BaseHuaweiDeye(TestCase):
    """Le devis résidentiel COURANT : réseau Huawei + hybride Deye, et les deux
    accessoires Huawei en lignes communes."""

    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        self.devis = make_devis(
            self.company, self.user, self.client_obj, LIGNES_HUAWEI_DEYE,
            reference='DEV-QJR201-0001', etude_params=dict(DEUX_OPTIONS))

    def total_imprime(self):
        """Le TTC que le document porte pour l'option mise en avant."""
        from apps.ventes.quote_engine.builder import build_quote_data
        return Decimal(str(build_quote_data(self.devis)['total_avec']))

    def accepter_avec(self):
        self.devis.statut = Devis.Statut.ACCEPTE
        self.devis.option_acceptee = AVEC_BATTERIE
        self.devis.save(update_fields=['statut', 'option_acceptee'])
        return self.devis


class EcheancierEtSolde(_BaseHuaweiDeye):
    """(1) échéancier · (2) solde avant acceptation."""

    def test_somme_des_tranches_egale_le_total_imprime(self):
        """LE ROUGE : Σ des factures de tranche == total imprimé, au dirham."""
        devis = self.accepter_avec()
        imprime = self.total_imprime()
        somme = Decimal('0')
        while next_tranche(devis) is not None:
            facture = creer_facture_tranche(
                devis, self.user, self.company, create_with_reference)
            somme += Decimal(str(facture.total_ttc))
        self.assertLessEqual(
            abs(somme - imprime), Decimal('1'),
            f'Σ tranches {somme} != total imprimé {imprime}')

    def test_solde_avant_acceptation_egale_le_total_imprime(self):
        """Aucune acceptation : le solde suit déjà le panier corrigé."""
        self.assertLessEqual(
            abs(solde_devis(self.devis)['total_ttc'] - self.total_imprime()),
            Decimal('1'))

    def test_acompte_est_30pct_du_panier_corrige(self):
        tranche = next_tranche(self.devis)
        attendu = _q(option_totaux(self.devis, AVEC_BATTERIE)['ttc']
                     * Decimal('0.30'))
        self.assertEqual(tranche['key'], 'acompte')
        self.assertEqual(tranche['ttc'], attendu)


class ProformaCommissionEtTotalTtc(_BaseHuaweiDeye):
    """(3) pro-forma · (4) commission · (5) ``Devis.total_ttc``."""

    def test_proforma_lit_le_panier_corrige(self):
        """L'argent ET les lignes de la pro-forma sortent du même panier que le
        PDF client — on teste la SOURCE, pas le rendu WeasyPrint."""
        from apps.ventes.utils.pdf import _proforma_option

        option = _proforma_option(self.devis)
        self.assertEqual(option, AVEC_BATTERIE)
        lignes = option_lines(self.devis, option)
        designations = [li.designation for li in lignes]
        self.assertNotIn('Smart Meter', designations)
        self.assertNotIn('Wifi Dongle', designations)
        totaux = option_totaux(self.devis, option, lignes=lignes)
        self.assertLessEqual(
            abs(Decimal(str(totaux['ttc'])) - self.total_imprime()),
            Decimal('1'))

    def test_base_de_commission_est_le_ht_du_panier_corrige(self):
        """La commission est un % du NET de l'option effective : sa base est
        ``Devis.total_ht``, qui passe par la vue NET du noyau."""
        self.assertEqual(
            Decimal(str(self.devis.total_ht)),
            Decimal(str(option_totaux(self.devis, AVEC_BATTERIE)['ht'])))

    def test_total_ttc_du_devis_egale_le_total_imprime(self):
        self.assertLessEqual(
            abs(Decimal(str(self.devis.total_ttc)) - self.total_imprime()),
            Decimal('1'))


class TroisCheminsDeRendu(_BaseHuaweiDeye):
    """Les trois chemins qui produisent le PDF client bâtissent le MÊME
    document : synchrone, tâche Celery ``generer-pdf``, et PDF joint à l'email.
    Les deux derniers n'avaient jamais été exercés."""

    def _espion(self):
        """Capture la charge utile BÂTIE par chaque chemin, sans payer le rendu
        WeasyPrint ni l'upload MinIO : ``build_quote_data`` est espionné (il
        rend la VRAIE donnée), le renderer et l'upload sont bouchonnés."""
        from unittest import mock
        from apps.ventes.quote_engine import builder as _builder

        vu = {}
        vrai = _builder.build_quote_data

        def _batir(devis, options=None, *a, **kw):
            data = vrai(devis, options, *a, **kw)
            vu['data'] = data
            return data

        correctifs = [
            mock.patch.object(_builder, 'build_quote_data', side_effect=_batir),
            mock.patch(
                'apps.ventes.quote_engine.residential.renderer'
                '.render_pdf_bytes', return_value=b'%PDF-1.4 test'),
            mock.patch('apps.ventes.utils.pdf._upload_pdf',
                       return_value='cle/test.pdf'),
        ]
        return vu, correctifs

    def _total_avec_rendu(self, action):
        vu, correctifs = self._espion()
        for c in correctifs:
            c.start()
        try:
            action()
        finally:
            for c in correctifs:
                c.stop()
        self.assertIn('data', vu, "le chemin n'a rendu aucun document")
        return Decimal(str(vu['data']['total_avec']))

    def test_chemin_synchrone(self):
        from apps.ventes.quote_engine import (
            clean_pdf_options, generate_premium_devis_pdf,
        )

        total = self._total_avec_rendu(lambda: generate_premium_devis_pdf(
            self.devis.id, clean_pdf_options({'pdf_mode': 'full'}),
            persist=False))
        self.assertLessEqual(
            abs(total - Decimal(str(
                option_totaux(self.devis, AVEC_BATTERIE)['ttc']))),
            Decimal('1'))

    def test_chemin_celery(self):
        from apps.ventes.tasks import task_generate_devis_pdf

        total = self._total_avec_rendu(
            lambda: task_generate_devis_pdf.apply(
                args=[self.devis.id, {'pdf_mode': 'full'}]).get())
        self.assertLessEqual(
            abs(total - Decimal(str(
                option_totaux(self.devis, AVEC_BATTERIE)['ttc']))),
            Decimal('1'))

    def test_chemin_email(self):
        """Le PDF JOINT à l'email : même panier, même total."""
        api = APIClient()
        api.force_authenticate(user=self.user)

        def _envoyer():
            resp = api.post(
                f'/api/django/ventes/devis/{self.devis.id}/envoyer-email/',
                {'pdf_mode': 'full'}, format='json')
            self.assertIn(resp.status_code, (200, 201), getattr(resp, 'data', resp))

        total = self._total_avec_rendu(_envoyer)
        self.assertLessEqual(
            abs(total - Decimal(str(
                option_totaux(self.devis, AVEC_BATTERIE)['ttc']))),
            Decimal('1'))
