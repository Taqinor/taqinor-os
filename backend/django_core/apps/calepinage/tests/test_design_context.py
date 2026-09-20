"""CAL231 — le contexte de conception NEUTRE, conforme à son contrat.

Ce qui est prouvé ici :

* les sept clés de ``contract_samples/calepinage_design_context.json`` sont
  TOUJOURS présentes, dans les DEUX états du serveur (avec devis / sans rien) ;
* un calepinage SANS devis ni facture rend ``cible: null`` — jamais une
  puissance inventée — et le dit dans ``avertissements`` ;
* la cible d'un calepinage AVEC devis est celle de l'atelier devis (même
  sélecteur ``apps.ventes.selectors.contexte_conception_devis``), marquée
  ``source: "devis"`` ;
* ``geometrie.source`` vaut ``calepinage`` / ``lead`` / ``none`` selon ce qui
  a réellement été posé, et rien n'est deviné quand tout manque ;
* la raison de lecture seule du serveur VENTES est reprise MOT POUR MOT ;
* un calepinage d'une AUTRE société est introuvable (404).

Run :
    python manage.py test apps.calepinage.tests.test_design_context -v2
"""
import json
import pathlib
from unittest import mock

from apps.calepinage.models import Calepinage
from apps.crm.models import Client, Lead
from apps.ventes.models import Devis

from .test_api_liste import BaseApiCalepinage, url_detail

CONTRAT = json.loads(
    (pathlib.Path(__file__).resolve().parents[1] / 'contract_samples'
     / 'calepinage_design_context.json').read_text(encoding='utf-8'))

LAYOUT = {'schema_version': 2, 'result': {'panels': 12, 'kwc': 8.64},
          'pin': {'lat': 33.5731, 'lng': -7.5898},
          'outline': [[33.5731, -7.5898], [33.5732, -7.5898]]}


def url_contexte(pk):
    return f'{url_detail(pk)}design-context/'


class ContexteConceptionTest(BaseApiCalepinage):
    def setUp(self):
        super().setUp()
        self.client_lie = Client.objects.create(company=self.company,
                                                nom='Bâtiment Atlas 231')
        self.lead_lie = Lead.objects.create(
            company=self.company, nom='Toiture Anfa 231', ville='Casablanca',
            roof_point={'lat': 33.5731, 'lng': -7.5898})
        self.devis = Devis.objects.create(
            company=self.company, client=self.client_lie, lead=self.lead_lie,
            reference='DEV-202609-2311')
        self.avec_devis = Calepinage.objects.create(
            company=self.company, lead_id=self.lead_lie.pk, devis=self.devis,
            titre='Villa Anfa', roof_layout=LAYOUT, layout_hash='a' * 64)
        self.nu = Calepinage.objects.create(
            company=self.company, client=self.client_lie,
            titre='Calepinage sans titre')
        self.etranger = Calepinage.objects.create(
            company=self.autre, lead_id=5, titre='Chez la voisine')

    def _contexte(self, calepinage, api=None):
        reponse = (api or self.api).get(url_contexte(calepinage.pk))
        self.assertEqual(reponse.status_code, 200, reponse.data)
        return reponse.data

    def test_sept_cles_toujours_presentes(self):
        attendues = set(CONTRAT['exemple'])
        self.assertEqual(set(self._contexte(self.avec_devis)), attendues)
        self.assertEqual(set(self._contexte(self.nu)), attendues)

    def test_sous_blocs_conformes(self):
        contexte = self._contexte(self.avec_devis)
        for bloc in ('calepinage', 'geometrie', 'carte'):
            self.assertEqual(set(contexte[bloc]),
                             set(CONTRAT['exemple'][bloc]), bloc)

    def test_sans_devis_ni_facture_la_cible_est_nulle(self):
        contexte = self._contexte(self.nu)
        self.assertIsNone(contexte['cible'])
        self.assertTrue(any('cible' in m for m in contexte['avertissements']))

    def test_sans_geometrie_la_source_est_none(self):
        contexte = self._contexte(self.nu)
        self.assertEqual(contexte['geometrie']['source'], 'none')
        self.assertIsNone(contexte['geometrie']['pin'])
        self.assertEqual(contexte['geometrie']['outline'], [])

    def test_avec_layout_la_source_est_le_calepinage(self):
        contexte = self._contexte(self.avec_devis)
        self.assertEqual(contexte['geometrie']['source'], 'calepinage')
        self.assertEqual(contexte['geometrie']['roof_layout'], LAYOUT)

    def test_sans_layout_mais_avec_epingle_la_source_est_le_lead(self):
        calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead_lie.pk,
            titre='Repli lead')
        contexte = self._contexte(calepinage)
        self.assertEqual(contexte['geometrie']['source'], 'lead')
        self.assertEqual(contexte['geometrie']['pin'],
                         {'lat': 33.5731, 'lng': -7.5898})

    def test_cible_du_devis_marquee_a_sa_source(self):
        contexte = self._contexte(self.avec_devis)
        self.assertIsNotNone(contexte['cible'])
        self.assertEqual(contexte['cible']['source'], 'devis')

    def test_raison_lecture_seule_reprise_mot_pour_mot(self):
        phrase = 'Devis accepté : la conception ne se modifie plus.'
        faux_contexte = {
            'cible': None, 'geometrie': {'contour_client': []},
            'raison_lecture_seule': phrase, 'avertissements': [],
        }
        with mock.patch('apps.ventes.selectors.contexte_conception_devis',
                        return_value=faux_contexte):
            contexte = self._contexte(self.avec_devis)
        self.assertEqual(contexte['raison_lecture_seule'], phrase)
        self.assertFalse(contexte['modifiable'])

    def test_autre_societe_introuvable(self):
        reponse = self.api.get(url_contexte(self.etranger.pk))
        self.assertEqual(reponse.status_code, 404)

    def test_sans_permission_403(self):
        reponse = self.api_sans.get(url_contexte(self.avec_devis.pk))
        self.assertEqual(reponse.status_code, 403)
