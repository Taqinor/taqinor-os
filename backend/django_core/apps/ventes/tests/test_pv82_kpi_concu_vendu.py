"""PV82 — KPI « conçu vs vendu » (kWc conçus / kWc signés / taux de conversion).

Miroir du test AO du même patron (``apps.ao.tests.test_kpis_ao``, AOF166) :
un provider KPI dotted (``apps.ventes.reports.kpi_ventes``) déclaré dans
``apps/ventes/platform.py`` et résolu par le hub fédéré ARC40
(``apps/reporting/reports.py::kpi_federes``).

Couvre :
  - un devis SANS layout 3D n'est ni conçu ni signé ;
  - un devis AVEC layout mais sans kWc résoluble (ni etude_params ni
    roof_layout.result.kwc) est ignoré, jamais compté à zéro ;
  - ``etude_params.puissance_kwc`` prime sur ``roof_layout.result.kwc`` quand
    les deux sont présents (même priorité que quote_engine/builder.py, Q5) ;
  - seul un devis ``statut='accepte'`` compte comme « signé » ;
  - le taux de conversion est CALCULÉ (signés / conçus), jamais saisi, et
    vaut 0 (jamais une division par zéro) sans aucun devis conçu ;
  - isolation société ;
  - forme de tuile conforme au hub fédéré (id/label/valeur) ;
  - aucune clé de prix/marge/prix_achat ne transite ;
  - le manifeste déclare un provider réellement résoluble (règle ARC41).

Run :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_pv82_kpi_concu_vendu -v 2
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from apps.crm.models import Client
from apps.ventes.models import Devis
from apps.ventes.platform import PLATFORM
from apps.ventes import reports as ventes_reports

User = get_user_model()


def _company(slug):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': slug})
    return company


class _Base(TestCase):
    def setUp(self):
        self.company = _company('pv82-co')
        self.autre = _company('pv82-autre')
        self.user = User.objects.create_user(
            username='pv82', password='x', role_legacy='responsable',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='PV82',
            email='pv82@example.com', telephone='+212622000000')

    def _devis(self, ref, *, statut='brouillon', roof_layout=None,
               etude_params=None, company=None):
        return Devis.objects.create(
            company=company or self.company, reference=ref,
            client=self.client_obj, statut=statut, created_by=self.user,
            roof_layout=roof_layout, etude_params=etude_params)


class UnDevisSansLayoutNEstNiConcuNiSigne(_Base):
    def test_devis_sans_roof_layout_est_ignore(self):
        self._devis('DEV-PV82-1', roof_layout=None,
                    etude_params={'puissance_kwc': 6.6})
        tuiles = {t['id']: t['valeur'] for t in ventes_reports.kpi_ventes(
            self.company)}
        self.assertEqual(tuiles['ventes_kwc_concus'], 0)
        self.assertEqual(tuiles['ventes_kwc_signes'], 0)


class UnDevisAvecLayoutMaisSansKwcResolubleEstIgnore(_Base):
    def test_layout_sans_result_ni_etude_params_ignore(self):
        self._devis('DEV-PV82-2', roof_layout={'zones': []},
                    etude_params=None)
        tuiles = {t['id']: t['valeur'] for t in ventes_reports.kpi_ventes(
            self.company)}
        self.assertEqual(tuiles['ventes_kwc_concus'], 0)

    def test_kwc_concu_devis_renvoie_none_si_irresoluble(self):
        devis = self._devis('DEV-PV82-3', roof_layout={'result': {}},
                            etude_params=None)
        self.assertIsNone(ventes_reports.kwc_concu_devis(devis))


class LeKwcPrivilegieEtudeParamsSurLeLayout(_Base):
    def test_etude_params_prime_sur_roof_layout(self):
        devis = self._devis(
            'DEV-PV82-4',
            roof_layout={'result': {'kwc': 3.3}},
            etude_params={'puissance_kwc': 9.9})
        self.assertAlmostEqual(
            ventes_reports.kwc_concu_devis(devis), 9.9, places=2)

    def test_repli_sur_roof_layout_result_kwc(self):
        devis = self._devis(
            'DEV-PV82-5', roof_layout={'result': {'kwc': 6.6}},
            etude_params=None)
        self.assertAlmostEqual(
            ventes_reports.kwc_concu_devis(devis), 6.6, places=2)


class SeulUnDevisAccepteCompteCommeSigne(_Base):
    def test_kwc_concus_et_signes_et_taux_conversion(self):
        self._devis('DEV-PV82-6', statut='accepte',
                    roof_layout={'result': {'kwc': 6.0}})
        self._devis('DEV-PV82-7', statut='envoye',
                    roof_layout={'result': {'kwc': 4.0}})
        tuiles = {t['id']: t['valeur'] for t in ventes_reports.kpi_ventes(
            self.company)}
        self.assertEqual(tuiles['ventes_kwc_concus'], 10.0)
        self.assertEqual(tuiles['ventes_kwc_signes'], 6.0)
        self.assertEqual(tuiles['ventes_taux_conversion_concus'], 50.0)

    def test_sans_aucun_devis_concu_le_taux_vaut_zero_et_pas_une_erreur(self):
        tuiles = {t['id']: t['valeur'] for t in ventes_reports.kpi_ventes(
            self.company)}
        self.assertEqual(tuiles['ventes_taux_conversion_concus'], 0.0)


class LeKpiEstBorneALaSociete(_Base):
    def test_un_devis_dune_autre_societe_nest_pas_compte(self):
        client_autre = Client.objects.create(
            company=self.autre, nom='Autre', prenom='Societe',
            email='autre-pv82@example.com', telephone='+212622000001')
        Devis.objects.create(
            company=self.autre, reference='DEV-PV82-AUTRE',
            client=client_autre, statut='accepte', created_by=self.user,
            roof_layout={'result': {'kwc': 12.0}})
        tuiles = {t['id']: t['valeur'] for t in ventes_reports.kpi_ventes(
            self.company)}
        self.assertEqual(tuiles['ventes_kwc_concus'], 0)


class LesTuilesKPISontConformesAuHubFedere(_Base):
    def test_chaque_tuile_porte_id_label_valeur(self):
        tuiles = ventes_reports.kpi_ventes(self.company)
        self.assertTrue(tuiles)
        for tuile in tuiles:
            for cle in ('id', 'label', 'valeur'):
                self.assertIn(cle, tuile, tuile)
            self.assertTrue(tuile['id'].startswith('ventes_'), tuile['id'])

    def test_aucun_kpi_ne_double_un_autre_module(self):
        """Deux tuiles de même ``id`` = un doublon dans le hub fédéré."""
        ids = [t['id'] for t in ventes_reports.kpi_ventes(self.company)]
        self.assertEqual(len(ids), len(set(ids)))


class AucunChiffreDePrixNeSortDesTuiles(_Base):
    def _cles(self, valeur, prefixe=''):
        cles = []
        if isinstance(valeur, dict):
            for k, v in valeur.items():
                cles.append('%s%s' % (prefixe, k))
                cles.extend(self._cles(v, prefixe))
        elif isinstance(valeur, (list, tuple)):
            for v in valeur:
                cles.extend(self._cles(v, prefixe))
        return cles

    def test_aucune_cle_de_prix_ou_marge_dans_les_tuiles(self):
        self._devis('DEV-PV82-8', statut='accepte',
                    roof_layout={'result': {'kwc': 5.0}})
        cles = [c.lower() for c in self._cles(
            ventes_reports.kpi_ventes(self.company))]
        for interdit in ('cout', 'coût', 'prix_achat', 'marge',
                         'benefice', 'bénéfice', 'revient'):
            for cle in cles:
                self.assertNotIn(interdit, cle,
                                 'clé interdite dans les tuiles : %s' % cle)


class LeProviderKPIEstReellementCable(SimpleTestCase):
    def test_le_manifeste_declare_le_provider(self):
        self.assertIn(
            'apps.ventes.reports.kpi_ventes', PLATFORM['kpi_providers'])

    def test_chaque_provider_declare_est_resoluble(self):
        """Règle d'honnêteté ARC41 : un dotted déclaré doit exister."""
        import importlib

        for dotted in PLATFORM['kpi_providers']:
            chemin, nom = dotted.rsplit('.', 1)
            self.assertTrue(
                callable(getattr(importlib.import_module(chemin), nom)),
                dotted)
