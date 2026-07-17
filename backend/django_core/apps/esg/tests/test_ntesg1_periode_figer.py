"""NTESG1 — Périodes de reporting ESG : figeage (snapshot gelé), immutabilité,
isolation multi-tenant.

Critère d'acceptation : une période figée renvoie EXACTEMENT les mêmes
chiffres à J+30 même si les données sources QHSE ont changé depuis.
"""
from datetime import date

from testkit.base import TenantAPITestCase

from apps.esg.models import PeriodeReportingESG, SnapshotESG


def _rows(resp):
    data = resp.data
    return data['results'] if isinstance(data, dict) and 'results' in data \
        else data


class PeriodeReportingESGFigerTests(TenantAPITestCase):
    BASE = '/api/django/esg/periodes-esg/'

    def _create_periode(self, company=None, **kwargs):
        payload = dict(
            company=company or self.company,
            libelle='T1 2026',
            date_debut=date(2026, 1, 1),
            date_fin=date(2026, 3, 31),
        )
        payload.update(kwargs)
        return PeriodeReportingESG.objects.create(**payload)

    def _seed_indicateur(self, company, valeur):
        from apps.qhse.models import IndicateurESG

        return IndicateurESG.objects.create(
            company=company, code='E1', libelle='Énergie',
            pilier=IndicateurESG.Pilier.ENVIRONNEMENT,
            valeur=valeur, annee=2026)

    def test_create_forces_company_server_side(self):
        r = self.client_as().post(
            self.BASE,
            {'libelle': 'T2 2026', 'date_debut': '2026-04-01',
             'date_fin': '2026-06-30'},
            format='json')
        self.assertEqual(r.status_code, 201, r.content)
        periode = PeriodeReportingESG.objects.get(id=r.data['id'])
        self.assertEqual(periode.company_id, self.company.id)
        self.assertEqual(periode.statut, PeriodeReportingESG.Statut.BROUILLON)

    def test_figer_freezes_snapshot_and_locks_statut(self):
        self._seed_indicateur(self.company, 100)
        periode = self._create_periode()
        r = self.client_as().post(f'{self.BASE}{periode.id}/figer/')
        self.assertEqual(r.status_code, 200, r.content)
        periode.refresh_from_db()
        self.assertEqual(periode.statut, PeriodeReportingESG.Statut.FIGEE)
        self.assertIsNotNone(periode.figee_le)
        snapshot = SnapshotESG.objects.get(periode=periode)
        indic = snapshot.donnees['sources']['indicateurs_esg']
        self.assertTrue(indic['disponible'])

    def test_figer_is_immutable_after_source_data_changes(self):
        """Critère d'acceptation NTESG1 : les chiffres figés ne bougent
        jamais, même si la donnée source QHSE change après coup."""
        indicateur = self._seed_indicateur(self.company, 100)
        periode = self._create_periode()
        self.client_as().post(f'{self.BASE}{periode.id}/figer/')
        snapshot_before = SnapshotESG.objects.get(periode=periode)
        piliers_before = (
            snapshot_before.donnees['sources']['indicateurs_esg']['piliers'])
        valeur_before = piliers_before['environnement']['lignes'][0]['valeur']

        # La donnée source change APRÈS le figeage.
        indicateur.valeur = 9999
        indicateur.save(update_fields=['valeur'])

        r = self.client_as().get(f'{self.BASE}{periode.id}/indicateurs/')
        self.assertEqual(r.status_code, 200)
        piliers_after = r.data['sources']['indicateurs_esg']['piliers']
        valeur_after = piliers_after['environnement']['lignes'][0]['valeur']
        self.assertEqual(valeur_before, valeur_after)
        self.assertNotEqual(valeur_after, '9999')

    def test_figer_twice_is_refused(self):
        periode = self._create_periode()
        r1 = self.client_as().post(f'{self.BASE}{periode.id}/figer/')
        self.assertEqual(r1.status_code, 200, r1.content)
        r2 = self.client_as().post(f'{self.BASE}{periode.id}/figer/')
        self.assertEqual(r2.status_code, 400)
        self.assertEqual(SnapshotESG.objects.filter(periode=periode).count(), 1)

    def test_statut_not_patchable_directly(self):
        periode = self._create_periode()
        r = self.client_as().patch(
            f'{self.BASE}{periode.id}/', {'statut': 'figee'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        periode.refresh_from_db()
        self.assertEqual(periode.statut, PeriodeReportingESG.Statut.BROUILLON)

    def test_cross_tenant_cannot_see_or_figer(self):
        periode = self._create_periode(company=self.other_company)
        r_list = self.client_as().get(self.BASE)
        self.assertNotIn(
            periode.id, [row['id'] for row in _rows(r_list)])
        r_detail = self.client_as().get(f'{self.BASE}{periode.id}/')
        self.assertIn(r_detail.status_code, (403, 404))
        r_figer = self.client_as().post(f'{self.BASE}{periode.id}/figer/')
        self.assertIn(r_figer.status_code, (403, 404))
