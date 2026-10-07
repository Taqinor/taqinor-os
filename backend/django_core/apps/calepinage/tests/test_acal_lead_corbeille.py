"""ACAL178 — un lead à la corbeille n'est PAS « jamais rattaché ».

Constat C-ACAL-001 : un calepinage dont le lead est dans la corbeille
(données d'avant la garde D06-T05) perdait nom, ville, pin et adresse, et
« Générer le devis » répondait « ni à un lead ni à un client ». Ici, avec
``Lead.soft_delete`` réel et les routes HTTP réelles :
  * les lectures retrouvent le lead (``avec_corbeille``) et publient
    ``supprime: true`` ; restauré, la même fiche rend ``supprime: false`` ;
  * ``generer_devis`` NOMME le lead à la corbeille ;
  * les écritures (création) refusent toujours un lead supprimé.

Run :
    python manage.py test apps.calepinage.tests.test_acal_lead_corbeille -v2
"""
from __future__ import annotations

from apps.calepinage import selectors
from apps.calepinage.models import Calepinage
from apps.crm.models import Lead

from .test_api_generer_devis import LAYOUT, url_generer
from .test_api_liste import URL, BaseApiCalepinage, url_detail


class LeadCorbeilleTest(BaseApiCalepinage):
    def setUp(self):
        super().setUp()
        self.lead = Lead.objects.create(
            company=self.company, nom='Toiture Anfa', ville='Casablanca',
            adresse='12 rue des Fleurs')
        self.c = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Villa Anfa',
            roof_layout=LAYOUT, layout_hash='d' * 64)

    def _corbeille(self):
        Lead.objects.get(pk=self.lead.pk).soft_delete(self.user)

    def test_generer_devis_nomme_le_lead_a_la_corbeille(self):
        self._corbeille()
        reponse = self.api.post(url_generer(self.c.pk), {}, format='json')
        self.assertEqual(reponse.status_code, 400, reponse.data)
        texte = str(reponse.data)
        self.assertIn('corbeille', texte)
        self.assertIn(f'#{self.lead.pk}', texte)
        self.assertIn('Toiture Anfa', texte)
        self.assertNotIn('ni à un lead ni à un client', texte)

    def test_contexte_geographique_garde_pin_et_adresse(self):
        self._corbeille()
        self.c.refresh_from_db()
        geo = selectors.contexte_geographique(self.c)
        self.assertEqual(geo['adresse'], '12 rue des Fleurs')
        self.assertEqual(geo['ville'], 'Casablanca')

    def test_liste_publie_supprime_true(self):
        avant = self.api.get(URL)
        self.assertFalse(avant.data['results'][0]['lead']['supprime'])
        self._corbeille()
        liste = self.api.get(URL)
        self.assertEqual(liste.status_code, 200, liste.data)
        lead = liste.data['results'][0]['lead']
        self.assertEqual(lead['nom'], 'Toiture Anfa')
        self.assertTrue(lead['supprime'])
        detail = self.api.get(url_detail(self.c.pk))
        self.assertTrue(detail.data['lead']['supprime'])
        # Restaurer : la même fiche rend supprime:false, sans autre geste.
        Lead.all_objects.get(pk=self.lead.pk).restore()
        detail = self.api.get(url_detail(self.c.pk))
        self.assertFalse(detail.data['lead']['supprime'])

    def test_creation_sur_lead_supprime_reste_refusee(self):
        self._corbeille()
        reponse = self.api.post(
            URL, {'lead': self.lead.pk, 'titre': 'Neuf'}, format='json')
        self.assertIn(reponse.status_code, (400, 404), reponse.data)
        self.assertEqual(
            Calepinage.objects.filter(titre='Neuf').count(), 0)
