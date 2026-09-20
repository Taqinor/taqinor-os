"""CAL17 — le détail agrégé, CONFORME à l'échantillon committé (PACT10).

Ce qui est prouvé ici :

* les clés de premier niveau du détail sont EXACTEMENT celles de
  ``contract_samples/calepinage_detail.json`` — dans les DEUX états du serveur
  (calepinage rempli / calepinage NEUF). C'est le lien qui manquait le
  03/08/2026 : le test d'écran importe ce MÊME fichier ;
* les sous-blocs (``versions``, ``variantes``, ``image``, ``lead``,
  ``client``, ``devis``, ``contexte_geographique``, ``permissions``) gardent
  leurs clés dans les deux états ;
* un calepinage NEUF rend des ``null`` — jamais des ``0`` : « aucune version »
  et « rien de mesuré » ne se lisent pas de la même façon ;
* le devis lié est lu par ``apps.ventes.selectors`` (référence + statut) ;
* un calepinage d'une AUTRE société est introuvable (404).

Run :
    python manage.py test apps.calepinage.tests.test_api_detail -v2
"""
import json
import pathlib

from apps.calepinage.models import Calepinage, CalepinageVariante
from apps.calepinage.services.layout import enregistrer_layout
from apps.crm.models import Client, Lead
from apps.ventes.models import Devis

from .test_api_liste import BaseApiCalepinage, url_detail

CONTRAT = json.loads(
    (pathlib.Path(__file__).resolve().parents[1] / 'contract_samples'
     / 'calepinage_detail.json').read_text(encoding='utf-8'))

LAYOUT = {'schema_version': 2, 'result': {'panels': 12, 'kwc': 8.64},
          'zones': [{'id': 'z1'}]}


class DetailContratTest(BaseApiCalepinage):
    def setUp(self):
        super().setUp()
        self.client_lie = Client.objects.create(company=self.company,
                                                nom='Bâtiment Atlas 17')
        self.lead_lie = Lead.objects.create(company=self.company,
                                            nom='Toiture Anfa 17',
                                            ville='Casablanca')
        self.devis = Devis.objects.create(
            company=self.company, client=self.client_lie, lead=self.lead_lie,
            reference='DEV-202609-1717')
        self.rempli = Calepinage.objects.create(
            company=self.company, lead_id=self.lead_lie.pk,
            devis=self.devis, titre='Villa Anfa', cree_par=self.user)
        enregistrer_layout(self.rempli, LAYOUT, user=self.user)
        CalepinageVariante.objects.create(
            company=self.company, calepinage=self.rempli,
            nom='Portrait plein sud')
        self.neuf = Calepinage.objects.create(
            company=self.company, client=self.client_lie,
            titre='Calepinage sans titre')

    def _detail(self, calepinage):
        reponse = self.api.get(url_detail(calepinage.pk))
        self.assertEqual(reponse.status_code, 200, reponse.data)
        return reponse.data

    def test_cles_de_premier_niveau_conformes_au_contrat(self):
        attendues = set(CONTRAT['exemple'])
        self.assertEqual(set(self._detail(self.rempli)), attendues)
        self.assertEqual(set(self._detail(self.neuf)), attendues)

    def test_sous_blocs_conformes_au_contrat(self):
        detail = self._detail(self.rempli)
        for bloc in ('versions', 'variantes', 'image', 'contexte_geographique',
                     'permissions'):
            self.assertEqual(set(detail[bloc]),
                             set(CONTRAT['exemple'][bloc]), bloc)
        for bloc in ('lead', 'devis'):
            self.assertEqual(set(detail[bloc]),
                             set(CONTRAT['exemple'][bloc]), bloc)

    def test_calepinage_neuf_rend_des_null_jamais_des_zeros(self):
        detail = self._detail(self.neuf)
        self.assertIsNone(detail['versions']['total'])
        self.assertIsNone(detail['variantes']['total'])
        self.assertIsNone(detail['layout_hash'])
        self.assertIsNone(detail['layout_schema_version'])
        self.assertIsNone(detail['devis'])
        self.assertIsNone(detail['lead'])
        self.assertFalse(detail['layout_present'])
        self.assertIsNone(detail['image']['url'])

    def test_calepinage_rempli_compte_versions_et_variantes(self):
        detail = self._detail(self.rempli)
        self.assertTrue(detail['layout_present'])
        self.assertEqual(detail['layout_schema_version'], 2)
        self.assertEqual(detail['versions']['total'], 1)
        self.assertEqual(detail['variantes']['total'], 1)
        self.assertEqual(detail['variantes']['non_simulees'], 1)
        self.assertEqual(detail['devis']['reference'], 'DEV-202609-1717')
        self.assertEqual(detail['devis']['statut'], self.devis.statut)
        self.assertEqual(detail['lead']['ville'], 'Casablanca')

    def test_autre_societe_introuvable(self):
        reponse = self.api_autre.get(url_detail(self.rempli.pk))
        self.assertEqual(reponse.status_code, 404)

    def test_sans_permission_403(self):
        reponse = self.api_sans.get(url_detail(self.rempli.pk))
        self.assertEqual(reponse.status_code, 403)
