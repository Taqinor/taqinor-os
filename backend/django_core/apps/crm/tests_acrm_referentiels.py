"""ACRM25 (C-ACRM-018) — étiquettes et motifs de perte : amorcés UNE fois,
renommages propagés.

Sonde V_VA LVIEW2-5 : renommer le motif standard « Prix » puis relire la
liste le faisait RESSUSCITER (amorçage à chaque GET) ; une étiquette standard
supprimée revenait de même ; renommer une étiquette EN USAGE laissait les
leads sur l'ancien libellé (``en_usage`` [0]). Désormais : l'amorçage ne
recrée jamais un libellé standard déjà proposé, le renommage suit dans
``Lead.tags`` / ``Lead.motif_perte`` (une ligne « en masse » au chatter), et
la suppression d'un libellé en usage reste refusée (garde L779/L780,
réponse 409 historique conservée).

API réelle ; aucun mock.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.crm.models import Lead, LeadActivity, LeadTag, MotifPerte

User = get_user_model()
TAGS = '/api/django/crm/tags/'
MOTIFS = '/api/django/crm/motifs-perte/'


def _lignes(resp):
    return resp.data['results'] if isinstance(resp.data, dict) else resp.data


class ReferentielsTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(
            nom='ACRM25 Solaire', slug='acrm25-referentiels')
        self.admin = User.objects.create_user(
            username='acrm25-admin', password='x', company=self.company,
            role_legacy='admin')
        self.api = APIClient()
        self.api.credentials(HTTP_AUTHORIZATION=(
            f'Bearer {AccessToken.for_user(self.admin)}'))
        # Premier chargement : amorçage des deux listes.
        self.assertEqual(self.api.get(TAGS).status_code, 200)
        self.assertEqual(self.api.get(MOTIFS).status_code, 200)

    def _noms(self, url):
        return sorted(r['nom'] for r in _lignes(self.api.get(url)))

    def test_renommage_ne_ressuscite_pas(self):
        prix = MotifPerte.objects.get(company=self.company, nom='Prix')
        resp = self.api.patch(f'{MOTIFS}{prix.pk}/',
                              {'nom': 'Prix trop élevé'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        premiere = self._noms(MOTIFS)
        self.assertNotIn('Prix', premiere)
        self.assertIn('Prix trop élevé', premiere)
        self.assertEqual(self._noms(MOTIFS), premiere)

    def test_suppression_ne_ressuscite_pas(self):
        tag = LeadTag.objects.get(company=self.company,
                                  nom='Compare les devis')
        resp = self.api.delete(f'{TAGS}{tag.pk}/')
        self.assertEqual(resp.status_code, 204, resp.content)
        premiere = self._noms(TAGS)
        self.assertNotIn('Compare les devis', premiere)
        self.assertEqual(self._noms(TAGS), premiere)

    def test_renommage_propage(self):
        tag = LeadTag.objects.get(company=self.company,
                                  nom='Facilité de paiement')
        lead = Lead.objects.create(
            company=self.company, nom='Porteur',
            tags='Facilité de paiement, VIP')
        resp = self.api.patch(f'{TAGS}{tag.pk}/',
                              {'nom': 'Paiement échelonné'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        lead.refresh_from_db()
        self.assertEqual(lead.tags, 'Paiement échelonné, VIP')
        ligne = next(r for r in _lignes(self.api.get(TAGS))
                     if r['nom'] == 'Paiement échelonné')
        self.assertEqual(ligne['en_usage'], 1)
        self.assertTrue(LeadActivity.objects.filter(
            lead=lead, field='tags', bulk=True).exists())
        motif = MotifPerte.objects.get(company=self.company,
                                       nom='Concurrent')
        perdu = Lead.objects.create(company=self.company, nom='Perdu',
                                    motif_perte='Concurrent')
        self.api.patch(f'{MOTIFS}{motif.pk}/',
                       {'nom': 'Concurrent moins cher'}, format='json')
        perdu.refresh_from_db()
        self.assertEqual(perdu.motif_perte, 'Concurrent moins cher')

    def test_suppression_en_usage_refusee(self):
        tag = LeadTag.objects.get(company=self.company, nom='En construction')
        Lead.objects.create(company=self.company, nom='Porteur',
                            tags='En construction')
        resp = self.api.delete(f'{TAGS}{tag.pk}/')
        self.assertIn(resp.status_code, (400, 409))
        self.assertTrue(LeadTag.objects.filter(pk=tag.pk).exists())
