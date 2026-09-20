"""CAL189 — `layout_stale` servi par l'API ERP (et pas seulement au public).

Ce qui est prouvé ici :

* l'API calepinage et le DÉTAIL devis rendent la MÊME valeur que la page
  publique pour le même devis (test croisé contre le moteur PDF) ;
* un calepinage SANS devis rend ``layout_stale: null`` — INCONNU, jamais
  ``false`` (l'écran affiche « — », CAL188) ;
* un devis dont les lignes ont bougé après la 3D est dit PÉRIMÉ ;
* un devis dont les lignes correspondent au calepinage ne l'est pas.

Run :
    python manage.py test apps.calepinage.tests.test_cal189_perime_api -v2
"""
from decimal import Decimal

from apps.calepinage.models import Calepinage
from apps.crm.models import Client, Lead
from apps.ventes.models import Devis, LigneDevis
from apps.ventes.selectors import peremption_layout_devis

from .test_api_liste import BaseApiCalepinage, url_detail

LAYOUT = {'schema_version': 2, 'result': {'panels': 12, 'kwc': 8.64}}


class PeremptionApiTest(BaseApiCalepinage):
    def setUp(self):
        super().setUp()
        self.client_lie = Client.objects.create(company=self.company,
                                                nom='Bâtiment Atlas 189')
        self.lead_lie = Lead.objects.create(company=self.company,
                                            nom='Toiture Anfa 189')
        self.devis = Devis.objects.create(
            company=self.company, client=self.client_lie, lead=self.lead_lie,
            reference='DEV-202609-1890', roof_layout=LAYOUT)
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead_lie.pk, devis=self.devis,
            titre='Villa Anfa', roof_layout=LAYOUT, layout_hash='f' * 64)
        self.nu = Calepinage.objects.create(
            company=self.company, client=self.client_lie, titre='Sans devis')

    def _ligne_panneaux(self, quantite):
        return LigneDevis.objects.create(
            devis=self.devis, designation='Panneau photovoltaïque 720 Wc',
            quantite=Decimal(quantite), prix_unitaire=Decimal('1000'))

    def _calepinage_api(self, calepinage):
        reponse = self.api.get(url_detail(calepinage.pk))
        self.assertEqual(reponse.status_code, 200, reponse.data)
        liste = self.api.get('/api/django/calepinage/calepinages/',
                             {'q': calepinage.titre})
        lignes = liste.data['results'] if isinstance(liste.data, dict) \
            else liste.data
        return next(ligne for ligne in lignes if ligne['id'] == calepinage.pk)

    def test_sans_devis_la_peremption_est_inconnue(self):
        ligne = self._calepinage_api(self.nu)
        self.assertIsNone(ligne['layout_stale'])
        self.assertIsNone(ligne['layout_nb_panneaux'])

    def test_lignes_alignees_le_calepinage_n_est_pas_perime(self):
        self._ligne_panneaux(12)
        ligne = self._calepinage_api(self.calepinage)
        self.assertFalse(ligne['layout_stale'])
        self.assertEqual(ligne['layout_nb_panneaux'], 12)

    def test_lignes_divergentes_le_calepinage_est_perime(self):
        self._ligne_panneaux(9)
        ligne = self._calepinage_api(self.calepinage)
        self.assertTrue(ligne['layout_stale'])
        self.assertEqual(ligne['layout_nb_panneaux'], 12)

    def test_meme_valeur_que_le_moteur_de_la_page_publique(self):
        """Test CROISÉ : le helper serveur et le moteur PDF s'accordent."""
        from apps.ventes.quote_engine.builder import _panneaux_du_layout

        self._ligne_panneaux(9)
        helper = peremption_layout_devis(self.devis)
        self.assertEqual(helper['layout_nb_panneaux'],
                         _panneaux_du_layout(self.devis.roof_layout))
        ligne = self._calepinage_api(self.calepinage)
        self.assertEqual(ligne['layout_stale'], helper['layout_stale'])
        self.assertEqual(ligne['layout_nb_panneaux'],
                         helper['layout_nb_panneaux'])

    def test_detail_devis_publie_les_deux_cles(self):
        self._ligne_panneaux(9)
        reponse = self.api.get(f'/api/django/ventes/devis/{self.devis.pk}/')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertIn('layout_stale', reponse.data)
        self.assertTrue(reponse.data['layout_stale'])
        self.assertEqual(reponse.data['layout_nb_panneaux'], 12)
