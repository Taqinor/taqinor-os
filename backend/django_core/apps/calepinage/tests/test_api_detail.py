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

from django.test import SimpleTestCase

from apps.calepinage.models import Calepinage, CalepinageVariante
from apps.calepinage.services.layout import enregistrer_layout
from apps.calepinage.tests._m0_en_attente import (
    EN_ATTENTE_DETAIL as EN_ATTENTE, affirmer_non_servies, sans,
)
from apps.crm.models import Client, Lead
from apps.ventes.models import Devis

from .test_api_liste import BaseApiCalepinage, url_detail

CONTRAT = json.loads(
    (pathlib.Path(__file__).resolve().parents[1] / 'contract_samples'
     / 'calepinage_detail.json').read_text(encoding='utf-8'))
#: L'exemple privé des clés posées par ACAL6 avant leur producteur.
EXEMPLE_SERVI = sans(CONTRAT['exemple'], EN_ATTENTE)

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
        attendues = set(EXEMPLE_SERVI)
        for calepinage in (self.rempli, self.neuf):
            detail = self._detail(calepinage)
            affirmer_non_servies(self, detail, EN_ATTENTE)
            self.assertEqual(set(detail), attendues)

    def test_sous_blocs_conformes_au_contrat(self):
        detail = self._detail(self.rempli)
        affirmer_non_servies(self, detail, EN_ATTENTE)
        for bloc in ('versions', 'variantes', 'image', 'contexte_geographique',
                     'permissions'):
            self.assertEqual(set(detail[bloc]),
                             set(EXEMPLE_SERVI[bloc]), bloc)
        for bloc in ('lead', 'devis'):
            self.assertEqual(set(detail[bloc]),
                             set(EXEMPLE_SERVI[bloc]), bloc)

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

    def test_acal915_surfaces_chiffrables_zone_et_champ_au_sol(self):
        """ACAL915 — zone 42 + champ au sol 176 ⇒ deux lignes, total 218 (le
        cumul toit + sol voulu, D-ACAL-5) ; un pan non pavé n'est pas chiffré ;
        un calepinage neuf ⇒ ``[]``. Mutant : ne pas servir la clé ⇒ rouge."""
        Calepinage.objects.filter(pk=self.rempli.pk).update(roof_layout={
            'schema_version': 2,
            'zones': [{'id': 'z1', 'label': 'Zone 1', 'geometry': {'count': 42}},
                      {'id': 'z2', 'label': 'Zone 2'}],
            'poseSurfaces': [{'id': 's1', 'kind': 'sol', 'label': 'Champ au sol 1',
                              'moduleWc': 550, 'engine': {'modules': 176}}]})
        surfaces = self._detail(self.rempli)['surfaces_chiffrables']
        self.assertEqual([(s['libelle'], s['modules']) for s in surfaces],
                         [('Zone 1', 42), ('Champ au sol 1', 176)])
        self.assertEqual(sum(s['modules'] for s in surfaces), 218)
        self.assertEqual(set(surfaces[0]), set(EXEMPLE_SERVI['surfaces_chiffrables'][0]))
        self.assertEqual(self._detail(self.neuf)['surfaces_chiffrables'], [])

    def test_acal1402_surfaces_chiffrables_disent_si_le_devis_les_chiffre(self):
        """ACAL1402 — le contrat porte ``chiffree`` (booléen avec un devis lié,
        ``null`` sans) et le détail réel a EXACTEMENT la forme de l'exemple.
        Mutant : retirer la clé de l'exemple ⇒ échec."""
        lignes = EXEMPLE_SERVI['surfaces_chiffrables']
        self.assertTrue(lignes)
        for ligne in lignes:
            self.assertIsInstance(ligne['chiffree'], bool, ligne)
        Calepinage.objects.filter(pk=self.rempli.pk).update(roof_layout={
            'schema_version': 2,
            'zones': [{'id': 'z1', 'label': 'Zone 1', 'geometry': {'count': 8}}],
            'poseSurfaces': [{'id': 's1', 'kind': 'sol', 'label': 'Champ au sol 1',
                              'moduleWc': 550, 'engine': {'modules': 4}}]})
        for ligne in self._detail(self.rempli)['surfaces_chiffrables']:
            self.assertEqual(set(ligne), set(lignes[0]))

    def test_acal1413_chiffree_lit_la_selection_du_devis_lie(self):
        """ACAL1413 — trois surfaces posées, un devis lié qui ne chiffre que
        « Champ au sol 1 » ⇒ ``chiffree`` vrai pour elle, faux pour les deux
        autres ; devis sans sélection écrite ou sans devis ⇒ ``null`` partout.
        Mutant : tout ``True`` ⇒ échec."""
        layout = {'schema_version': 2,
                  'zones': [{'id': 'z1', 'label': 'Zone 1', 'geometry': {'count': 42}},
                            {'id': 'z2', 'label': 'Zone 2', 'geometry': {'count': 14}}],
                  'poseSurfaces': [{'id': 's1', 'kind': 'sol', 'label': 'Champ au sol 1',
                                    'moduleWc': 550, 'engine': {'modules': 50}}]}
        Calepinage.objects.filter(pk=self.rempli.pk).update(roof_layout=layout)
        Calepinage.objects.filter(pk=self.neuf.pk).update(roof_layout=layout)

        def chiffrees():
            return {s['libelle']: s['chiffree']
                    for s in self._detail(self.rempli)['surfaces_chiffrables']}

        self.assertEqual(chiffrees(), {'Zone 1': None, 'Zone 2': None,
                                       'Champ au sol 1': None})  # devis sans sélection
        Devis.objects.filter(pk=self.devis.pk).update(roof_layout={
            'choixConception': {'surfacesChiffrees': ['s1']}})
        self.assertEqual(chiffrees(), {'Zone 1': False, 'Zone 2': False,
                                       'Champ au sol 1': True})
        for surface in self._detail(self.neuf)['surfaces_chiffrables']:  # sans devis lié
            self.assertIsNone(surface['chiffree'], surface)

    def test_autre_societe_introuvable(self):
        reponse = self.api_autre.get(url_detail(self.rempli.pk))
        self.assertEqual(reponse.status_code, 404)

    def test_sans_permission_403(self):
        reponse = self.api_sans.get(url_detail(self.rempli.pk))
        self.assertEqual(reponse.status_code, 403)


class SurfacesChiffrablesSansBaseTest(SimpleTestCase):
    def test_pan_existant_jamais_propose_au_chiffrage(self):
        """Critique D1 (suite) — un pan « existant » n'est pas une surface à
        cocher pour le devis : ni case, ni modules dans « Le devis chiffre »."""
        from apps.calepinage.serializers import surfaces_chiffrables

        def pan(cle, nombre, **extra):
            return dict({'id': cle, 'label': cle, 'geometry': {
                'panels': [{'cx': i, 'cy': 0} for i in range(nombre)]}}, **extra)
        document = {'zones': [pan('A', 10, existant=True), pan('B', 6)]}
        self.assertEqual([(s['cle'], s['modules']) for s in surfaces_chiffrables(document)],
                         [('B', 6)])
        document['zones'][0]['existant'] = False
        self.assertEqual([s['cle'] for s in surfaces_chiffrables(document)], ['A', 'B'])
