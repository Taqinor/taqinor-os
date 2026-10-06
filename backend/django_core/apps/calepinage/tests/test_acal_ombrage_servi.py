"""ACAL143 — UN sélecteur ``ombrage_servi(devis_id, company)`` adossé à la
fraîcheur SERVIE, qui rend la perte d'ombrage PAR PAN.

Constats C-ACAL-075 / C-ACAL-078 : l'étude bancable du devis
(``apps/ventes/etude.py``) lisait la cascade STOCKÉE et la « validait » en
comparant son ``hash_entree`` à l'en-tête de la MÊME simulation — une
tautologie : une cascade calculée sur un autre toit passait toujours, et
seule la variante retenue était consultée.

Le sélecteur lit le résultat SERVI (``selectors.resultat_servi`` : verdict de
fraîcheur de GET resultat/, empreinte de simulation) et rend
``{perime, motif, par_pan, global}`` — ou ``None`` sans calepinage ou sans
simulation.

Calepinage RÉEL en base de test, simulé par la vraie chaîne (client rejoué),
aucun mock du sélecteur.

Run :
    python manage.py test apps.calepinage.tests.test_acal_ombrage_servi -v2
"""
from __future__ import annotations

import copy

from apps.calepinage.models import Calepinage
from apps.calepinage.selectors import ombrage_servi
from apps.calepinage.services.liens import lier_devis
from apps.calepinage.services.simulation import simuler_calepinage
from apps.ventes.models import Devis

from .acal_livrables_helpers import patch_materiel
from .test_acal_multi_pans import _ClientParOrientation, _layout, _zone
from .test_api_liste import BaseApiCalepinage
from .test_calx5_simulation import MATERIEL


class OmbrageServiTest(BaseApiCalepinage):

    def setUp(self):
        super().setUp()
        self.devis = Devis.objects.create(
            company=self.company, client=self.client_a, lead=self.lead,
            reference='DEV-202610-1431')
        layout = _layout(_zone(1, 16, 90.0), _zone(2, 8, 270.0))
        # Un accès solaire publié par le constructeur : l'étape « accès
        # module » s'applique, la perte d'ombrage est mesurée.
        layout['solarAccess'] = {'values': [0.9] * 24}
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Ombrage 143',
            roof_layout=layout)
        lier_devis(self.calepinage, self.devis.pk)
        with patch_materiel():
            simuler_calepinage(self.calepinage,
                               client=_ClientParOrientation(),
                               materiel=MATERIEL, enregistrer=True)
        self.calepinage.refresh_from_db()

    def test_frais_rend_la_perte_par_pan(self):
        with patch_materiel():
            servi = ombrage_servi(self.devis.pk, self.company)

        self.assertIsNotNone(servi)
        self.assertFalse(servi['perime'])
        self.assertEqual(sorted(servi['par_pan']), ['PAN-1', 'PAN-2'])
        attendu = {ligne['pan']: ligne['perte_ombrage_pct']
                   for ligne in self.calepinage.resultat['ombrage']
                   ['par_pan']}
        self.assertEqual(servi['par_pan'], attendu)
        self.assertIn('global', servi)

    def test_retouche_sans_resimuler_rend_perime(self):
        layout = copy.deepcopy(self.calepinage.roof_layout)
        layout['zones'][0]['geometry']['count'] = 3
        layout['zones'][0]['obstacles'] = [{'id': 'o1', 'heightM': 2.0}]
        self.calepinage.roof_layout = layout
        self.calepinage.save(update_fields=['roof_layout'])

        with patch_materiel():
            servi = ombrage_servi(self.devis.pk, self.company)

        self.assertTrue(servi['perime'])
        self.assertTrue(servi['motif'])
        self.assertEqual(servi['par_pan'], {})
        self.assertIsNone(servi['global'])

    def test_autre_societe_none(self):
        with patch_materiel():
            self.assertIsNone(ombrage_servi(self.devis.pk, self.autre))

    def test_jamais_simule_none(self):
        devis = Devis.objects.create(
            company=self.company, client=self.client_a, lead=self.lead,
            reference='DEV-202610-1432')
        calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead_2.pk,
            titre='Jamais simulé', roof_layout=_layout(_zone(1, 8)))
        lier_devis(calepinage, devis.pk)

        with patch_materiel():
            self.assertIsNone(ombrage_servi(devis.pk, self.company))
