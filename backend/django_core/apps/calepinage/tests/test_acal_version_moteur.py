"""ACAL121 (C-ACAL-092) — ``Calepinage.version_moteur`` est ÉCRIT à la fin
de chaque simulation, depuis la version PUBLIÉE dans
``resultat['simulation']['version_moteur']`` (une seule source :
``core.electrique.version.VERSION_MOTEUR``) ; le pied de planche l'imprime.

Le fournisseur PVGIS est injecté au niveau RÉSEAU seulement (client rejoué) ;
le reste (simulation, écriture, planche, détail HTTP) est réel.

Run :
    python manage.py test apps.calepinage.tests.test_acal_version_moteur -v2
"""
from apps.calepinage.models import Calepinage
from apps.calepinage.services.planche import (
    _empreinte_du_calepinage, pied_du_calepinage,
)
from apps.calepinage.services.simulation import simuler_calepinage
from core.electrique.version import VERSION_MOTEUR

from .acal_livrables_helpers import patch_materiel
from .test_acal_multi_pans import _ClientParOrientation, _layout, _zone
from .test_api_liste import BaseApiCalepinage, url_detail
from .test_calx5_simulation import MATERIEL


class VersionMoteurTest(BaseApiCalepinage):
    def setUp(self):
        super().setUp()
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='ACAL121',
            roof_layout=_layout(_zone(1, 16, 180.0)),
            layout_hash='b' * 64,
            resultat={'entree_electrique': {'dc_m': 30}})
        self.assertEqual(self.calepinage.version_moteur, '')

    def _simuler(self):
        with patch_materiel():
            simuler_calepinage(self.calepinage,
                               client=_ClientParOrientation(),
                               materiel=MATERIEL, enregistrer=True,
                               forcer=True)

    def test_simulation_ecrit_la_colonne(self):
        self._simuler()
        relu = Calepinage.objects.get(pk=self.calepinage.pk)
        publiee = relu.resultat['simulation']['version_moteur']
        self.assertEqual(publiee, VERSION_MOTEUR)
        self.assertEqual(relu.version_moteur, publiee)
        # Rouvrir : le détail relit la colonne de la base.
        with patch_materiel():
            detail = self.api.get(url_detail(self.calepinage.pk))
        self.assertEqual(detail.status_code, 200, detail.data)
        self.assertEqual(detail.data['version_moteur'], VERSION_MOTEUR)

    def test_pied_de_planche_porte_le_moteur(self):
        avant = Calepinage.objects.get(pk=self.calepinage.pk)
        self.assertNotIn('moteur ', _empreinte_du_calepinage(avant))
        self._simuler()
        relu = Calepinage.objects.get(pk=self.calepinage.pk)
        self.assertIn(f'moteur {VERSION_MOTEUR}',
                      _empreinte_du_calepinage(relu))
        self.assertIn(f'moteur {VERSION_MOTEUR}', pied_du_calepinage(relu))
