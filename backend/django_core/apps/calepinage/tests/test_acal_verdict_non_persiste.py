"""ACAL325 (C-ACAL-145) — l'enregistrement d'un plan n'écrit plus
``resultat['verdict_electrique']`` (instantané lu par personne, recopié
périmé dans chaque version) ; le verdict reste CALCULÉ (rendu par
``rejouer_apres_layout``) et SERVI À LA DEMANDE par ``evaluation_electrique``
; la réconciliation de longueur (CAL170) est toujours journalisée.

Calepinage simulé par les VRAIS écrivains, enregistré en base ; le matériel
est le seam documenté (``patch_materiel``). La réconciliation hors tolérance
est provoquée par son ENTRÉE (``longueur_chaine_retenue``), jamais par un
double de ``journaliser_ecart_longueur`` (la fonction prouvée).

Run :
    python manage.py test apps.calepinage.tests.test_acal_verdict_non_persiste -v2
"""
import copy
from unittest import mock

from apps.calepinage.models import Calepinage
from apps.calepinage.services.electrique import (
    CLE_FIL_ECARTS, evaluation_electrique, rejouer_apres_layout,
)
from apps.calepinage.services.layout import enregistrer_layout

from .acal_livrables_helpers import calepinage_simule_reel, patch_materiel
from .test_api_liste import BaseApiCalepinage, url_detail

HORS_TOLERANCE = {'longueur': 12, 'origine': 'calcul', 'detail': 'essai',
                  'longueur_dossier': 16, 'ecart': -4,
                  'hors_tolerance': True, 'par_pan': {}}


class VerdictNonPersisteTest(BaseApiCalepinage):
    def setUp(self):
        super().setUp()
        pivot = calepinage_simule_reel()
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='ACAL325',
            roof_layout=copy.deepcopy(pivot.roof_layout),
            resultat=copy.deepcopy(pivot.resultat),
            layout_hash=pivot.layout_hash or '')

    def _document_modifie(self):
        document = copy.deepcopy(self.calepinage.roof_layout)
        document['zones'][0]['geometry']['count'] += 1
        return document

    def test_enregistrer_layout_n_ecrit_pas_verdict_electrique(self):
        with patch_materiel():
            enregistrer_layout(self.calepinage, self._document_modifie(),
                               user=self.user)
        relu = Calepinage.objects.get(pk=self.calepinage.pk)
        self.assertNotIn('verdict_electrique', relu.resultat)
        # La version déposée ne porte aucun verdict périmé non plus.
        version = relu.versions.order_by('-id').first()
        self.assertTrue(version.resultat is None
                        or 'verdict_electrique' not in version.resultat)

    def test_la_reconciliation_de_longueur_est_toujours_journalisee(self):
        with patch_materiel(), mock.patch(
                'apps.calepinage.services.electrique.longueur_chaine_retenue',
                return_value=dict(HORS_TOLERANCE)):
            enregistrer_layout(self.calepinage, self._document_modifie(),
                               user=self.user)
        relu = Calepinage.objects.get(pk=self.calepinage.pk)
        self.assertIn(CLE_FIL_ECARTS, relu.resultat)
        self.assertTrue(relu.resultat[CLE_FIL_ECARTS])
        self.assertNotIn('verdict_electrique', relu.resultat)

    def test_verdict_servi_a_la_demande_inchange(self):
        with patch_materiel():
            enregistrer_layout(self.calepinage, self._document_modifie(),
                               user=self.user)
            relu = Calepinage.objects.get(pk=self.calepinage.pk)
            rendu = rejouer_apres_layout(relu, user=self.user)
            a_la_demande = evaluation_electrique(
                Calepinage.objects.get(pk=self.calepinage.pk))
            servi = self.api.get(f'{url_detail(self.calepinage.pk)}resultat/')
        self.assertIsNotNone(rendu)
        self.assertEqual(rendu, a_la_demande)
        self.assertEqual(servi.status_code, 200, servi.data)
        # Rejouer n'a toujours rien écrit.
        self.assertNotIn('verdict_electrique', Calepinage.objects.get(
            pk=self.calepinage.pk).resultat)
