"""QJR554 — enregistrer en Édition complète remet à jour les CACHES du devis.

Avant : ``MODE_RAFRAICHIR`` = ``('rafraichir_etudes',)`` ; ``finaliser``
(``poser_puissance_kwc`` + ``refresh_marge_snapshot`` + conception électrique)
ne tournait qu'en ``composer``. ``replace-lines``, ``perform_update`` et
``LigneDevisViewSet`` laissaient ``etude_params['puissance_kwc']`` et
``marge_snapshot`` périmés.

Après : ``MODE_RAFRAICHIR`` = ``('rafraichir_etudes', 'finaliser_caches')`` —
le kWc et la marge interne suivent les lignes réellement écrites. La marge
reste interne (jamais au PDF) ; le statut n'est jamais écrit (règle #4).
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.domain import pipeline
from apps.ventes.models import Devis

User = get_user_model()
WATT = 550


class ModeRafraichirPoseLesCaches(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='qjr554-co', defaults={'nom': 'QJR554 Co'})
        self.user = User.objects.create_user(
            username='qjr554_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='QJR554',
            telephone='+212600005540')
        self.panneau = Produit.objects.create(
            company=self.company, nom=f'Panneau solaire {WATT}W',
            sku='QJR554-PV', prix_vente=Decimal('1200'),
            prix_achat=Decimal('700'), quantite_stock=500)

    def _creer(self, n=10, prix='1200'):
        resp = self.api.post('/api/django/ventes/devis/atomic/', {
            'client': self.client_obj.id, 'statut': 'brouillon',
            'taux_tva': '20',
            'lignes': [{'produit': self.panneau.id,
                        'designation': f'Panneau solaire {WATT}W',
                        'quantite': str(n), 'prix_unitaire': prix}],
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        return Devis.objects.get(pk=resp.data['id'])

    def test_le_mode_rafraichir_declare_finaliser_caches(self):
        self.assertEqual(
            pipeline.ETAPES_PAR_MODE[pipeline.MODE_RAFRAICHIR],
            ('rafraichir_etudes', 'finaliser_caches'))

    def test_atomic_pose_le_kwc_des_la_creation(self):
        devis = self._creer(10)
        self.assertEqual(
            (devis.etude_params or {}).get('puissance_kwc'),
            round(10 * WATT / 1000, 2))
        self.assertIsNotNone(devis.marge_snapshot)

    def test_replace_lines_remet_kwc_et_marge_a_jour(self):
        devis = self._creer(10)
        marge_avant = devis.marge_snapshot
        resp = self.api.post(
            f'/api/django/ventes/devis/{devis.pk}/replace-lines/', {
                'lignes': [{'produit': self.panneau.id,
                            'designation': f'Panneau solaire {WATT}W',
                            'quantite': '14', 'prix_unitaire': '900'}],
            }, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        devis.refresh_from_db()
        self.assertEqual(devis.etude_params.get('puissance_kwc'),
                         round(14 * WATT / 1000, 2))
        self.assertNotEqual(devis.marge_snapshot, marge_avant)
        # 14 × (900 − 700) = 2800
        self.assertEqual(Decimal(str(devis.marge_snapshot)),
                         Decimal('2800'))

    def test_patch_de_ligne_remet_kwc_et_marge_a_jour(self):
        devis = self._creer(10)
        ligne = devis.lignes.get()
        resp = self.api.patch(
            f'/api/django/ventes/devis-lignes/{ligne.pk}/',
            {'quantite': '14', 'prix_unitaire': '900'}, format='json')
        self.assertIn(resp.status_code, (200, 201), resp.content)
        devis.refresh_from_db()
        self.assertEqual(devis.etude_params.get('puissance_kwc'),
                         round(14 * WATT / 1000, 2))
        self.assertEqual(Decimal(str(devis.marge_snapshot)),
                         Decimal('2800'))

    def test_statut_d_un_envoye_inchange(self):
        devis = self._creer(10)
        Devis.objects.filter(pk=devis.pk).update(statut=Devis.Statut.ENVOYE)
        resp = self.api.post(
            f'/api/django/ventes/devis/{devis.pk}/replace-lines/', {
                'lignes': [{'produit': self.panneau.id,
                            'designation': f'Panneau solaire {WATT}W',
                            'quantite': '12', 'prix_unitaire': '1100'}],
            }, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.ENVOYE)
        self.assertEqual(devis.etude_params.get('puissance_kwc'),
                         round(12 * WATT / 1000, 2))
