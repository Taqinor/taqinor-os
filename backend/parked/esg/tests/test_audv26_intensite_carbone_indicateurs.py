"""AUDV26 (NTESG9) — l'action `indicateurs` affiche enfin les 3 ratios carbone.

`selectors.intensite_carbone` calculait déjà les 3 ratios (par CA/kWc/ETP)
avec dégradation propre (jamais un 0 forfaitaire) mais
`PeriodeReportingESGViewSet.indicateurs` ne l'appelait jamais — ce fichier
prouve le câblage HTTP (aperçu LIVE d'une période brouillon ET snapshot gelé
d'une période figée), sans dupliquer la logique de dégradation déjà couverte
par `test_ntesg9_intensite_carbone.py`.

Run:
    python manage.py test apps.esg.tests.test_audv26_intensite_carbone_indicateurs -v 2
"""
from datetime import date

from testkit.base import TenantAPITestCase

from apps.esg import selectors
from apps.esg.models import PeriodeReportingESG


class IndicateursActionIntensiteCarboneTests(TenantAPITestCase):
    BASE = '/api/django/esg/periodes-esg/'

    def _create_periode(self, **kwargs):
        payload = dict(
            company=self.company, libelle='T1 2026',
            date_debut=date(2026, 1, 1), date_fin=date(2026, 3, 31))
        payload.update(kwargs)
        return PeriodeReportingESG.objects.create(**payload)

    def test_apercu_live_expose_les_3_ratios_degrades(self):
        periode = self._create_periode()
        r = self.client_as().get(f'{self.BASE}{periode.id}/indicateurs/')
        self.assertEqual(r.status_code, 200, r.content)
        carbone = r.data['intensite_carbone']
        self.assertIn('ratios', carbone)
        for cle in ('par_mad_ca', 'par_kwc_installe', 'par_etp'):
            ratio = carbone['ratios'][cle]
            # Aucun sélecteur qhse n'expose encore le bilan carbone (numérateur
            # toujours indisponible aujourd'hui) : les 3 ratios dégradent —
            # JAMAIS un 0 forfaitaire.
            self.assertFalse(ratio['disponible'])
            self.assertIsNone(ratio['valeur'])
            self.assertIsNotNone(ratio['raison'])

    def test_snapshot_fige_porte_aussi_les_ratios(self):
        periode = self._create_periode()
        self.client_as().post(f'{self.BASE}{periode.id}/figer/')
        r = self.client_as().get(f'{self.BASE}{periode.id}/indicateurs/')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertIn('intensite_carbone', r.data)
        self.assertIn('ratios', r.data['intensite_carbone'])

    def test_coherent_avec_le_selecteur_intensite_carbone(self):
        """L'action et l'appel direct du sélecteur NTESG9 s'accordent."""
        periode = self._create_periode()
        attendu = selectors.intensite_carbone(periode)
        r = self.client_as().get(f'{self.BASE}{periode.id}/indicateurs/')
        self.assertEqual(r.data['intensite_carbone']['ratios'], attendu['ratios'])
