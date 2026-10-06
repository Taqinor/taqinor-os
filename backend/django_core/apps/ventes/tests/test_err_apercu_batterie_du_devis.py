"""ERR-FIG-APERCU-BATTERIE — l'aperçu horaire de l'« Édition complète » calcule
la batterie comme le bloc ENREGISTRÉ du devis.

L'écran envoie la capacité NOMINALE lue sur le nom de ses lignes (« Dyness
5 kWh » → 5) ; l'aperçu tournait à 5 kWh × rendement de référence 0,90 pendant
que le bloc du devis tourne à la capacité UTILE de la fiche × le rendement
PUBLIÉ (QJR137). Même devis, deux paybacks (6,9 ans à l'écran contre 6,7 au
PDF — e2e figures-parite, PR #818).

Technique : espionner les kwargs reçus par ``calculer_etude_horaire`` (comme
``test_err_apercu_meme_conso_que_devis``).
"""
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client, Lead
from apps.stock.models import Produit
from apps.ventes.domain.lignes import creer_ligne
from apps.ventes.models import Devis
from authentication.models import Company

User = get_user_model()

URL = '/api/django/ventes/etude-horaire/preview/'
BL = 'apps.ventes.horaire.batterie_lignes'


class ApercuBatterieDuDevisTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(nom='ERR apercu bat',
                                              slug='err-apercu-bat')
        self.user = User.objects.create_user(
            username='err_apercu_bat', password='x',
            role_legacy='responsable', company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        client_obj = Client.objects.create(company=self.company, nom='C')
        lead = Lead.objects.create(
            company=self.company, nom='Lead', prenom='bat',
            telephone='+212600000003', ville='Casablanca',
            facture_hiver=900, ete_differente=False)
        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-ERR-APERCU-BAT',
            client=client_obj, lead=lead, statut='brouillon',
            taux_tva=Decimal('20'), mode_installation='residentiel')
        batterie = Produit.objects.create(
            company=self.company, nom='Batterie Dyness 5 kWh',
            prix_vente=Decimal('11666.67'), prix_achat=Decimal('1'),
            quantite_stock=10, tva=Decimal('20'))
        creer_ligne(self.devis, produit=batterie,
                    designation='Batterie Dyness 5 kWh',
                    quantite=Decimal('1'), prix_unitaire=Decimal('11666.67'),
                    remise=Decimal('0'), variante='avec')

    def _kwargs_vus(self, corps):
        vues = {}

        def _espion(**kwargs):
            vues.update(kwargs)
            return None

        with mock.patch('apps.ventes.etude_horaire.calculer_etude_horaire',
                        side_effect=_espion), \
                mock.patch(f'{BL}.capacite_batterie_du_devis',
                           return_value=4.6), \
                mock.patch(f'{BL}.rendement_batterie_du_devis',
                           return_value={'rendement': 0.98,
                                         'source': 'fiche:test'}):
            resp = self.api.post(URL, corps, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        return vues

    def test_meme_batterie_que_le_devis_prend_ses_grandeurs(self):
        vues = self._kwargs_vus({'devis': self.devis.pk, 'kwc': 4.26,
                                 'batterie_kwh': 5, 'facture_hiver': 900})
        self.assertEqual(vues['batterie_kwh_utile'], 4.6)
        self.assertEqual(vues['batterie_rendement'], 0.98)
        self.assertEqual(vues['batterie_rendement_source'], 'fiche:test')

    def test_autre_batterie_essayee_a_l_ecran_garde_le_corps(self):
        vues = self._kwargs_vus({'devis': self.devis.pk, 'kwc': 4.26,
                                 'batterie_kwh': 10, 'facture_hiver': 900})
        self.assertEqual(vues['batterie_kwh_utile'], 10)
        self.assertNotIn('batterie_rendement', vues)

    def test_sans_devis_garde_le_corps(self):
        vues = self._kwargs_vus({'kwc': 4.26, 'batterie_kwh': 5,
                                 'facture_hiver': 900, 'ville': 'Casablanca'})
        self.assertEqual(vues['batterie_kwh_utile'], 5)
        self.assertNotIn('batterie_rendement', vues)
