"""ATOT21 (C-ATOT-013) — bornes d'argent validées au sérialiseur ET à
l'écrivain unique (``remise_globale``, ``remise`` de ligne 0-100, quantité /
prix positifs à 2 décimales au plus), par la garde unique
``views/devis_gardes._pourcentage_saisi`` (+ son jumeau ``_montant_saisi``) :
un 400 NOMMÉ en français, jamais 500 ni texte SQL. Le devis relu est inchangé
après chaque refus ; le témoin « 5 » passe.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.ventes.tests.test_atot_bornes_argent"
"""
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.ventes.domain.lignes import remplacer_lignes
from testkit.factories import (
    CompanyFactory, DevisFactory, ProduitFactory, UserFactory,
)

SQL = ('violates check constraint', 'Failing row', 'IntegrityError', 'ck_')


class BornesArgentTests(TestCase):

    def setUp(self):
        self.company = CompanyFactory()
        self.user = UserFactory(company=self.company, role_legacy='admin')
        self.api = APIClient()
        self.api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.devis = DevisFactory(company=self.company, taux_tva=Decimal('20.00'),
                                  remise_globale=Decimal('0'))
        self.produit = ProduitFactory(company=self.company, nom='Onduleur réseau Huawei 5kW',
                                      prix_vente=Decimal('9000'), tva=Decimal('20.00'))
        remplacer_lignes(self.devis, [
            {'produit': self.produit.id, 'quantite': '1', 'prix_unitaire': '9000'},
        ], self.company)
        self.url = f'/api/django/ventes/devis/{self.devis.id}/'

    def _sans_sql(self, reponse):
        texte = reponse.content.decode('utf-8')
        for motif in SQL:
            self.assertNotIn(motif, texte)

    def _etat(self):
        self.devis.refresh_from_db()
        return (self.devis.remise_globale,
                list(self.devis.lignes.values_list('quantite', 'prix_unitaire', 'remise')))

    def test_patch_remise_globale_150_400_nomme(self):
        avant = self._etat()
        r = self.api.patch(self.url, {'remise_globale': '150'}, format='json')
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn('remise_globale', r.json())
        self.assertIn('doit être compris entre 0 et 100', str(r.json()['remise_globale']))
        self._sans_sql(r)
        self.assertEqual(self._etat(), avant)

    def test_patch_remise_globale_temoin_5(self):
        r = self.api.patch(self.url, {'remise_globale': '5'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.remise_globale, Decimal('5.00'))

    def test_post_ligne_remise_150_400_nomme(self):
        r = self.api.post('/api/django/ventes/devis-lignes/', {
            'devis': self.devis.id, 'produit': self.produit.id, 'designation': 'X',
            'quantite': '1', 'prix_unitaire': '100', 'remise': '150',
        }, format='json')
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn('remise', r.json())
        self._sans_sql(r)

    def test_replace_lines_entete_remise_negative_400(self):
        avant = self._etat()
        r = self.api.post(f'{self.url}replace-lines/', {
            'lignes': [{'produit': self.produit.id, 'quantite': '1', 'prix_unitaire': '9000'}],
            'entete': {'remise_globale': '-5'},
        }, format='json')
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn('remise_globale', r.json())
        self._sans_sql(r)
        self.assertEqual(self._etat(), avant)

    def test_replace_lines_quantite_trois_decimales_400(self):
        avant = self._etat()
        r = self.api.post(f'{self.url}replace-lines/', {
            'lignes': [{'produit': self.produit.id, 'quantite': '1.255', 'prix_unitaire': '9000'}],
        }, format='json')
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn('quantite', r.json())
        self.assertIn('au plus 2 décimales', str(r.json()['quantite']))
        self._sans_sql(r)
        self.assertEqual(self._etat(), avant)

    def test_replace_lines_remise_ligne_hors_bornes_400(self):
        r = self.api.post(f'{self.url}replace-lines/', {
            'lignes': [{'produit': self.produit.id, 'quantite': '1', 'prix_unitaire': '9000',
                        'remise': '150'}],
        }, format='json')
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn('remise', r.json())
        self._sans_sql(r)
