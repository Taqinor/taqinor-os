"""QJR669 (décision fondateur 01/10) — ``prix_par_kwc`` SUIT LE DEVIS.

Avant : ``Devis.save`` gelait la mesure BI une seule fois (« write-once ») ;
un envoyé corrigé sur place (D-QJR5-1) gardait le prix / kWc de son premier
brouillon. Désormais le propriétaire du kWc (``domain/scenario.py``) la
recalcule — Total TTC ÷ kWc — dès que le kWc ou le total change, par une
mise à jour ciblée de la colonne (jamais ``updated_at``). La pose d'une
surcharge (``domain/overrides.ecrire_colonne``) ne la touche toujours pas.

Run:
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.ventes.tests.test_prix_par_kwc_suit_devis"
"""
from decimal import Decimal, ROUND_HALF_UP

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis
from authentication.models import Company

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


def _attendu(devis):
    kwc = Decimal(str(devis.etude_params['puissance_kwc']))
    return (Decimal(str(devis.total_ttc)) / kwc).quantize(
        Decimal('0.01'), rounding=ROUND_HALF_UP)


class PrixParKwcSuitLeDevis(TestCase):

    def setUp(self):
        self.company = Company.objects.create(
            nom='QJR669 Co', slug='qjr669-co')
        self.user = User.objects.create_user(
            username='qjr669_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='QJR669',
            email='qjr669@example.test', telephone='+212600006690')
        self.panneau = Produit.objects.create(
            company=self.company, nom='Panneau Canadien Solar 710W',
            sku='QJR669-PV', prix_vente=Decimal('1000'),
            prix_achat=Decimal('700'), quantite_stock=100)
        self.onduleur = Produit.objects.create(
            company=self.company, nom='Onduleur réseau Huawei 5kW',
            sku='QJR669-OND', prix_vente=Decimal('3000'),
            prix_achat=Decimal('2000'), quantite_stock=100)

    def _devis(self, statut=Devis.Statut.BROUILLON):
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-6690',
            client=self.client_obj, statut=statut, taux_tva=Decimal('20'),
            mode_installation='residentiel', created_by=self.user)
        LigneDevis.objects.create(
            devis=devis, produit=self.panneau, designation=self.panneau.nom,
            quantite=Decimal('10'), prix_unitaire=Decimal('1000'),
            remise=Decimal('0'), ordre=0)
        LigneDevis.objects.create(
            devis=devis, produit=self.onduleur,
            designation=self.onduleur.nom, quantite=Decimal('1'),
            prix_unitaire=Decimal('3000'), remise=Decimal('0'), ordre=1)
        return devis

    def _replace(self, devis, prix_panneau):
        return self.api.post(
            f'/api/django/ventes/devis/{devis.id}/replace-lines/',
            {'lignes': [
                {'produit': self.panneau.id, 'quantite': '10',
                 'prix_unitaire': prix_panneau, 'ordre': 0,
                 'designation': self.panneau.nom},
                {'produit': self.onduleur.id, 'quantite': '1',
                 'prix_unitaire': '3000', 'ordre': 1,
                 'designation': self.onduleur.nom},
            ]}, format='json')

    def _poser_kwc(self, devis):
        from apps.ventes.domain.scenario import poser_puissance_kwc
        poser_puissance_kwc(Devis.objects.get(pk=devis.pk))
        devis.refresh_from_db()

    def test_le_proprietaire_du_kwc_pose_prix_par_kwc(self):
        devis = self._devis()
        self._poser_kwc(devis)
        self.assertTrue(devis.etude_params.get('puissance_kwc'))
        self.assertEqual(devis.prix_par_kwc, _attendu(devis))

    def test_replace_lines_recalcule_prix_par_kwc(self):
        devis = self._devis()
        self._poser_kwc(devis)
        avant = devis.prix_par_kwc
        r = self._replace(devis, '800')
        self.assertEqual(r.status_code, 200, r.content)
        devis.refresh_from_db()
        self.assertNotEqual(devis.prix_par_kwc, avant)
        self.assertEqual(devis.prix_par_kwc, _attendu(devis))

    def test_correction_sur_place_d_un_envoye_suit_aussi(self):
        devis = self._devis(statut=Devis.Statut.ENVOYE)
        self._poser_kwc(devis)
        r = self._replace(devis, '900')
        self.assertEqual(r.status_code, 200, r.content)
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.ENVOYE)
        self.assertEqual(devis.prix_par_kwc, _attendu(devis))

    def test_le_recalcul_n_avance_pas_updated_at(self):
        from apps.ventes.domain.scenario import poser_prix_par_kwc
        devis = self._devis()
        self._poser_kwc(devis)
        LigneDevis.objects.filter(devis=devis, ordre=0).update(
            prix_unitaire=Decimal('700'))
        maj = Devis.objects.get(pk=devis.pk).updated_at
        poser_prix_par_kwc(Devis.objects.get(pk=devis.pk))
        relu = Devis.objects.get(pk=devis.pk)
        self.assertEqual(relu.updated_at, maj)
        self.assertEqual(relu.prix_par_kwc, _attendu(relu))
