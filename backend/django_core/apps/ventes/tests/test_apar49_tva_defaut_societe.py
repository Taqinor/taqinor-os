"""APAR49 (C-APAR-012) — toute entrée serveur de création de devis sans
``taux_tva`` prend le taux STANDARD de la société (``tva_standard``), plus
``Decimal('20')`` codé : pour une société à 14 %, le devis et les lignes sans
taux propre sont à 14 % ; un taux explicite (y compris 0) est respecté.

Sources réelles : ``composer_devis_residentiel``, ``build_devis_from_layout``,
``POST /ventes/devis/composition/`` (catalogue QJR80, produits sans TVA).

Test-du-test : remettre ``Decimal('20')`` comme défaut ⇒
``test_composition_sans_taux_prend_le_taux_societe`` échoue.
"""
from decimal import Decimal

from rest_framework.test import APIClient

from apps.parametres.models import CompanyProfile
from apps.ventes.domain import creation_auto, creation_calepinage
from apps.ventes.tests import test_qjr_pipeline_composer as qjr80


class TvaDefautSocieteTests(qjr80._Base):
    slug = 'apar49-tva'

    def setUp(self):
        super().setUp()
        profil = CompanyProfile.get(company=self.company)
        CompanyProfile.objects.filter(pk=profil.pk).update(
            tva_standard=Decimal('14'))

    def _taux_composition(self, **kwargs):
        charge = creation_auto.composer_devis_residentiel(
            company=self.company, nb_panneaux=qjr80.NB_PANNEAUX,
            panel_watt=qjr80.PANEL_WATT, scenario='sans', **kwargs)
        return {ligne['taux_tva'] for ligne in charge['lignes']}

    def test_composition_sans_taux_prend_le_taux_societe(self):
        self.assertEqual(self._taux_composition(), {'14'})

    def test_taux_explicite_respecte(self):
        self.assertEqual(self._taux_composition(taux_tva=Decimal('0')), {'0'})

    def test_from_layout_sans_taux(self):
        devis = creation_calepinage.build_devis_from_layout(
            layout=self._layout(), user=self.user, company=self.company,
            lead=self.lead)
        devis.refresh_from_db()
        self.assertEqual(devis.taux_tva, Decimal('14'))

    def test_endpoint_composition_sans_taux(self):
        api = APIClient()
        api.force_authenticate(self.user)
        resp = api.post('/api/django/ventes/devis/composition/',
                        {'nb_panneaux': qjr80.NB_PANNEAUX,
                         'panel_watt': qjr80.PANEL_WATT, 'scenario': 'sans'},
                        format='json')
        self.assertEqual(resp.status_code, 200, resp.content[:300])
        self.assertEqual({li['taux_tva'] for li in resp.json()['lignes']},
                         {'14'})
