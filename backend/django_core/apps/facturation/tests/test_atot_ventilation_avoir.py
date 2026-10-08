"""ATOT6 (C-ATOT-004) — `Avoir` et `NoteDebit` portent une `ventilation_tva`
recopiée au prorata de la facture d'origine (service unique
`totaux.ventilation_document_fige`) : un avoir d'une facture à taux mixtes
porte autant de paniers TVA que sa facture.

Rejoue la sonde V1 TFAC-4 : aujourd'hui l'avoir total d'un acompte 30 %
(1 200 @10 / 3 600 @20) a `tva_par_taux=[('16.00','4800.00')]`. Endpoints
réels, aucun mock.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.facturation.tests.test_atot_ventilation_avoir"
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

User = get_user_model()
_CTR = [0]
DEUX_PANIERS = [(Decimal('10.00'), Decimal('1200.00')),
                (Decimal('20.00'), Decimal('3600.00'))]


def _nxt():
    _CTR[0] += 1
    return _CTR[0]


def _paniers(doc):
    return [(Decimal(str(b['taux'])).quantize(Decimal('0.01')),
             Decimal(str(b['montant'])).quantize(Decimal('0.01')))
            for b in doc.tva_par_taux]


class VentilationServiceTests(SimpleTestCase):
    def test_meme_ttc_reprend_les_paniers(self):
        from apps.facturation.totaux import ventilation_document_fige
        src = [{'taux': '10', 'base_ht': '12000.00', 'montant': '1200.00'},
               {'taux': '20', 'base_ht': '18000.00', 'montant': '3600.00'}]
        v = ventilation_document_fige(src, Decimal('34800.00'))
        self.assertEqual([(b['base_ht'], b['montant']) for b in v],
                         [('12000.00', '1200.00'), ('18000.00', '3600.00')])

    def test_prorata_somme_exacte(self):
        from apps.facturation.totaux import ventilation_document_fige
        src = [{'taux': '10', 'base_ht': '12000.00', 'montant': '1200.00'},
               {'taux': '20', 'base_ht': '18000.00', 'montant': '3600.00'}]
        v = ventilation_document_fige(src, Decimal('1000.01'))
        total = sum(Decimal(b['base_ht']) + Decimal(b['montant']) for b in v)
        self.assertEqual(total, Decimal('1000.01'))

    def test_mono_taux_none(self):
        from apps.facturation.totaux import ventilation_document_fige
        self.assertIsNone(ventilation_document_fige(
            [{'taux': '20', 'base_ht': '100', 'montant': '20'}],
            Decimal('120')))


class VentilationAvoirTests(TestCase):
    def setUp(self):
        from apps.crm.models import Client
        from apps.stock.models import Produit
        from authentication.models import Company
        self.company = Company.objects.create(
            nom='ATOT6 Co', slug=f'atot6-co-{_nxt()}')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Ventile', prenom='ATOT6',
            email=f'atot6-{_nxt()}@example.invalid')
        self.admin = User.objects.create_user(
            username=f'atot6_admin_{_nxt()}', password='x',
            role_legacy='admin', company=self.company)
        self.produit = Produit.objects.create(
            company=self.company, nom='Geste commercial',
            sku=f'ATOT6-{_nxt()}', prix_vente=Decimal('0'),
            quantite_stock=0)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')

    def _acompte(self):
        """Devis 40 000 HT @10 % + 60 000 HT @20 % ; acompte 30 % émis :
        ventilation 12 000/1 200 @10 et 18 000/3 600 @20, TTC 34 800."""
        from apps.ventes.models import Devis, Facture, LigneDevis
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-ATOT6-{_nxt()}',
            client=self.client_obj, statut=Devis.Statut.ACCEPTE,
            taux_tva=Decimal('20.00'), mode_installation='residentiel')
        for designation, pu, taux in (('Pose', '40000', '10.00'),
                                      ('Matériel', '60000', '20.00')):
            LigneDevis.objects.create(
                devis=devis, designation=designation, quantite=Decimal('1'),
                prix_unitaire=Decimal(pu), remise=Decimal('0'),
                taux_tva=Decimal(taux))
        r = self.api.post(
            f'/api/django/ventes/devis/{devis.id}/generer-facture/',
            {}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        facture = Facture.objects.get(pk=r.data['id'])
        self.assertEqual(_paniers(facture), DEUX_PANIERS)
        return facture

    def test_avoir_total_tranche_deux_paniers(self):
        from apps.ventes.models import Avoir
        facture = self._acompte()
        r = self.api.post(
            f'/api/django/ventes/factures/{facture.id}/creer-avoir/', {},
            format='json')
        self.assertEqual(r.status_code, 201, r.data)
        avoir = Avoir.objects.get(pk=r.data['id'])  # relu en base
        self.assertEqual(_paniers(avoir), DEUX_PANIERS)
        self.assertEqual(Decimal(str(avoir.total_ttc)), Decimal('34800.00'))
        self.assertEqual(len(avoir.ventilation_tva), 2)

    def test_avoir_partiel_prorata(self):
        from apps.ventes.models import Avoir
        facture = self._acompte()
        r = self.api.post(
            f'/api/django/ventes/factures/{facture.id}/creer-avoir/',
            {'lignes': [{'designation': 'Geste', 'quantite': '1',
                         'prix_unitaire': '10000',
                         'produit': self.produit.id}]}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        avoir = Avoir.objects.get(pk=r.data['id'])
        paniers = _paniers(avoir)
        self.assertEqual([t for t, _ in paniers],
                         [Decimal('10.00'), Decimal('20.00')])
        self.assertEqual(paniers, [(Decimal('10.00'), Decimal('400.00')),
                                   (Decimal('20.00'), Decimal('1200.00'))])
        self.assertEqual(Decimal(str(avoir.total_ttc)), Decimal('11600.00'))
        self.assertEqual(
            Decimal(str(avoir.total_ht)) + Decimal(str(avoir.total_tva)),
            Decimal(str(avoir.total_ttc)))

    def test_note_debit_ventilee(self):
        from apps.ventes.models import NoteDebit
        facture = self._acompte()
        r = self.api.post(
            f'/api/django/ventes/factures/{facture.id}/creer-note-debit/',
            {}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        note = NoteDebit.objects.get(pk=r.data['id'])
        self.assertEqual(_paniers(note), DEUX_PANIERS)
