"""ACAL116 (D-ACAL-24, C-ACAL-094) — « Approbation exigée » active : générer /
resynchroniser le devis et les pièces d'exécution exigent une approbation À
JOUR ; les livrables d'étude impriment « Conception non approuvée ».

Le réglage société est ÉCRIT EN BASE ; routes HTTP réelles ; la mention est
lue dans le TEXTE imprimé (pied de planche SVG, corps de la note), jamais
dans les octets d'un PDF.

Run :
    python manage.py test apps.calepinage.tests.test_acal_portee_approbation -v2
"""
import copy

from apps.calepinage.models import Calepinage
from apps.calepinage.services.approbation import decider
from apps.calepinage.services.feu_vert import PIECES_EXECUTION
from apps.calepinage.services.layout import (
    empreinte_document, enregistrer_layout,
)
from apps.calepinage.services.parametres import enregistrer_parametres
from apps.ventes.models import Devis

from .acal_livrables_helpers import LAYOUT_PLANCHE_SIMULABLE
from .test_api_liste import BaseApiCalepinage, url_detail
from .test_cal173_empreinte import MOMENT

#: Chaque pièce d'exécution → sa porte HTTP réelle.
ROUTES = {
    'plan_pose': ('get', 'plan-pose.pdf/'),
    'plan_cablage': ('get', 'plan-cablage.pdf/'),
    'plan_cablage_dxf': ('get', 'plan-cablage.dxf/'),
    'export_dxf': ('get', 'export.dxf/'),
    'export_xlsx': ('get', 'export.xlsx/'),
    'export_csv': ('get', 'export.csv/'),
    'pack_technique': ('post', 'pack-technique/'),
    'dossier_fin_chantier': ('post', 'dossier-fin-chantier/'),
}

TOIT = {
    'areas': [{'vertices': [[0, 0], [10, 0], [10, 6], [0, 6]],
               'obstacles': [], 'roofType': 'flat', 'pitch': 10,
               'azimuth': 180}],
    'zones': [{'id': 'z1', 'label': 'Pan Sud',
               'vertices': [[0, 0], [10, 0], [10, 6], [0, 6]]}],
    'scenario': 'reseau',
    'result': {'panels': 12, 'kwc': 6.6, 'annualKwh': 10800, 'savings': 9200},
}


class PorteeApprobationTest(BaseApiCalepinage):
    def setUp(self):
        super().setUp()
        from apps.ventes.tests.test_from_layout_endpoint import seed_catalogue
        seed_catalogue(self.company)
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='ACAL116')
        enregistrer_layout(self.calepinage, copy.deepcopy(TOIT),
                           user=self.user)
        self.base = url_detail(self.calepinage.pk)

    def _exiger(self, valeur=True):
        enregistrer_parametres(self.company,
                               {'presets': {'approbation_exigee': valeur}})

    def _generer(self):
        return self.api.post(f'{self.base}generer-devis/', {}, format='json')

    def test_generer_refuse_sans_approbation_a_jour(self):
        self._exiger()
        avant = Devis.objects.filter(company=self.company).count()
        reponse = self._generer()
        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertIn('Approbation à jour exigée', str(reponse.data))
        self.assertEqual(Devis.objects.filter(company=self.company).count(),
                         avant)

    def test_sync_refuse_approbation_perimee(self):
        self._exiger()
        self.calepinage.refresh_from_db()
        decider(self.calepinage, decision='approuve', user=self.user)
        reponse = self._generer()
        self.assertEqual(reponse.status_code, 201, reponse.data)
        # La conception change : l'approbation est périmée.
        self.calepinage.refresh_from_db()
        autre = copy.deepcopy(TOIT)
        autre['result']['panels'] = 14
        autre['zones'][0]['vertices'] = [[0, 0], [14, 0], [14, 6], [0, 6]]
        jeton = empreinte_document(self.calepinage.roof_layout)
        reponse = self.api.post(f'{self.base}layout/', autre, format='json',
                                HTTP_IF_MATCH=f'"{jeton}"')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        reponse = self.api.post(f'{self.base}sync-devis/', {},
                                format='json')
        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertIn('approbation', str(reponse.data))

    def test_pieces_execution_refusees(self):
        self._exiger()
        self.assertEqual(set(ROUTES), set(PIECES_EXECUTION))
        for piece in PIECES_EXECUTION:
            with self.subTest(piece=piece):
                methode, chemin = ROUTES[piece]
                appel = getattr(self.api, methode)
                reponse = (appel(f'{self.base}{chemin}', {}, format='json')
                           if methode == 'post'
                           else appel(f'{self.base}{chemin}'))
                self.assertEqual(reponse.status_code, 400,
                                 (piece, reponse.status_code))
                self.assertIn('approbation', str(reponse.data))

    def test_livrables_etude_portent_non_approuvee(self):
        from apps.calepinage.services.documents.gabarit_document import (
            MENTION_NON_APPROUVEE, etat_de_conception, mentions_d_etat,
        )
        from apps.calepinage.services.planche import rendre_planche_svg

        self._exiger()
        Calepinage.objects.filter(pk=self.calepinage.pk).update(
            roof_layout=copy.deepcopy(LAYOUT_PLANCHE_SIMULABLE))
        cal = Calepinage.objects.get(pk=self.calepinage.pk)
        self.assertIn(MENTION_NON_APPROUVEE,
                      mentions_d_etat(etat_de_conception(cal)))
        planche = rendre_planche_svg(cal, moment=MOMENT)
        self.assertIn(MENTION_NON_APPROUVEE, planche)

    def test_reglages_inactifs_rien_ne_change(self):
        from apps.calepinage.services.documents.gabarit_document import (
            etat_de_conception, mentions_d_etat,
        )

        reponse = self._generer()
        self.assertEqual(reponse.status_code, 201, reponse.data)
        self.calepinage.refresh_from_db()
        self.assertEqual(mentions_d_etat(etat_de_conception(self.calepinage)),
                         [])
