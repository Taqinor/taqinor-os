"""AGR624 — relevés portail d'une pompe du CATALOGUE : les pompes OSP de
``seed_catalogue`` sont créées SANS ``role_pompage`` déclaré (leur rôle se lit
sur la catégorie ou le nom, ``stock.selectors.produits_pompage``). Le portail
lisait la seule colonne déclarée → aucun équipement n'admettait de relevé m³
(e2e ``agricole-chantier-recette.spec.js``). Le rôle EFFECTIF fait foi.

Run :
    python manage.py test apps.portail.tests.test_agr624_releves_role_effectif
"""
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.installations.models import Installation
from apps.portail.tests.test_ntprt14_mes_chantiers import (
    make_client, make_company, make_portal_user,
)
from apps.sav.models import Equipement, ReleveCompteurEquipement
from apps.stock.models import Produit
from authentication.models import CustomUser


class RelevesPompeCatalogueTests(TestCase):
    def setUp(self):
        self.company = make_company('agr624-co', 'AGR624 Société')
        self.client_a = make_client(self.company, 'Alpha')
        self.chantier = Installation.objects.create(
            company=self.company, reference='CH-AGR624-1',
            client=self.client_a, type_installation='agricole')
        # Comme seed_catalogue : nom OSP, AUCUN rôle déclaré.
        self.pompe = self._equipement(
            'Pompe immergée OSP 30/8 — 10 CV / 7.5 kW (3", 380V)')
        self.panneau = self._equipement('Panneau 710W')
        self.api = APIClient()
        self.api.force_authenticate(user=make_portal_user(
            self.company, 'agr624-portail-a',
            CustomUser.PORTEE_PORTAIL_CLIENT, self.client_a.id))
        self.url = f'/api/django/portail/mes-chantiers/{self.chantier.id}/releves/'

    def _equipement(self, nom):
        produit = Produit.objects.create(
            company=self.company, nom=nom, prix_vente=Decimal('0'),
            prix_achat=Decimal('0'))
        self.assertEqual(produit.role_pompage or '', '')
        return Equipement.objects.create(
            company=self.company, produit=produit, installation=self.chantier)

    def test_la_pompe_osp_sans_role_declare_admet_le_m3(self):
        r = self.api.get(self.url)
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual([(e['id'], e['types_admis']) for e in r.data['equipements']],
                         [(self.pompe.id, ['m3'])])

    def test_le_client_poste_son_releve_m3(self):
        r = self.api.post(self.url, {'equipement': self.pompe.id, 'type': 'm3',
                                     'valeur': '100', 'date': '2027-01-05'},
                          format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertTrue(ReleveCompteurEquipement.objects.filter(
            equipement=self.pompe).exists())
        # Un type non admis reste refusé (le kWh n'est jamais une saisie client).
        r = self.api.post(self.url, {'equipement': self.pompe.id, 'type': 'heures',
                                     'valeur': '5', 'date': '2027-01-06'},
                          format='json')
        self.assertEqual(r.status_code, 400)
        # Un équipement sans rôle pompage n'admet rien.
        r = self.api.post(self.url, {'equipement': self.panneau.id, 'type': 'm3',
                                     'valeur': '5', 'date': '2027-01-06'},
                          format='json')
        self.assertEqual(r.status_code, 400)
