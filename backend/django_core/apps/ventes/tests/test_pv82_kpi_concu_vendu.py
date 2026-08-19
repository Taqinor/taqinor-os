"""PV82 — KPI « conçu vs vendu » (kWc conçus / kWc signés / taux de conversion).

Miroir du test AO du même patron (``apps.ao.tests.test_kpis_ao``, AOF166) :
un provider KPI dotted (``apps.ventes.reports.kpi_ventes``) déclaré dans
``apps/ventes/platform.py`` et résolu par le hub fédéré ARC40
(``apps/reporting/reports.py::kpi_federes``).

Couvre :
  - un devis SANS layout 3D n'est ni conçu ni signé ;
  - un devis AVEC layout mais sans kWc résoluble (ni lignes, ni etude_params,
    ni roof_layout.result.kwc) est ignoré, jamais compté à zéro ;
  - PVUNI (18/08/2026) — les LIGNES du devis priment TOUJOURS sur le kWc du
    calepinage (``puissance_panneaux_lignes``, la même fonction que le
    PDF/la page — jamais une seconde dérivation) ;
  - ``roof_layout.result.kwc`` prime sur ``etude_params.puissance_kwc`` quand
    le devis ne porte AUCUNE ligne panneau (même priorité que
    quote_engine/builder.py, PVUNI) — l'ordre INVERSE d'avant PVUNI, où cette
    tuile lisait encore la valeur potentiellement périmée (base 720 W)
    recopiée depuis le calepinage dans ``etude_params.puissance_kwc`` ;
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

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from apps.crm.models import Client
from apps.stock.models import Produit
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

    def _ligne_panneau(self, devis, *, quantite, watt=600, prix_unitaire='1000'):
        """PVUNI — une ligne PANNEAU réelle (produit + LigneDevis), pour les
        tests qui prouvent que les LIGNES priment sur le calepinage."""
        produit = Produit.objects.create(
            company=devis.company, nom=f'Panneau Solar {watt}W',
            sku=f'PV82-PAN-{watt}-{devis.pk}',
            prix_vente=Decimal(prix_unitaire), prix_achat=Decimal('1'),
            quantite_stock=500)
        devis.lignes.create(
            produit=produit, designation=f'Panneau Solar {watt}W',
            quantite=Decimal(str(quantite)),
            prix_unitaire=Decimal(prix_unitaire))
        return produit


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


class LesLignesDuDevisPrimentSurLeCalepinage(_Base):
    """PVUNI (18/08/2026) — le résidu exact de l'incident DEV-202608-0007,
    reproduit côté KPI : un devis avec des lignes panneau RÉELLES (600 W) et
    un calepinage dimensionné sur une autre base (720 W, 10 panneaux) doit
    compter le kWc des LIGNES (6.0), jamais celui du calepinage (7.2)."""

    def test_les_lignes_priment_sur_le_kwc_du_calepinage(self):
        devis = self._devis(
            'DEV-PV82-LIGNES',
            # 10 panneaux x 720 W (base roofPro) — ce que le calepinage annonce.
            roof_layout={'result': {'panels': 10, 'kwc': 7.2}},
            etude_params={'puissance_kwc': 7.2})
        # 10 panneaux x 600 W (ligne réellement vendue) — ce que les lignes disent.
        self._ligne_panneau(devis, quantite=10, watt=600)
        self.assertAlmostEqual(
            ventes_reports.kwc_concu_devis(devis), 6.0, places=2)

    def test_le_kpi_agrege_le_kwc_des_lignes_pas_celui_du_calepinage(self):
        devis = self._devis(
            'DEV-PV82-LIGNES-2', statut='accepte',
            roof_layout={'result': {'panels': 10, 'kwc': 7.2}},
            etude_params={'puissance_kwc': 7.2})
        self._ligne_panneau(devis, quantite=10, watt=600)
        tuiles = {t['id']: t['valeur'] for t in ventes_reports.kpi_ventes(
            self.company)}
        self.assertEqual(tuiles['ventes_kwc_concus'], 6.0)
        self.assertEqual(tuiles['ventes_kwc_signes'], 6.0)


class LeKwcPrivilegieLeCalepinageSurEtudeParams(_Base):
    """PVUNI — SANS AUCUNE ligne panneau, le kWc du calepinage prime sur
    ``etude_params.puissance_kwc`` (l'ordre INVERSE d'avant PVUNI — cette
    valeur est exactement celle qu'une création depuis calepinage y recopie,
    donc potentiellement périmée elle aussi)."""

    def test_roof_layout_prime_sur_etude_params_sans_ligne(self):
        devis = self._devis(
            'DEV-PV82-4',
            roof_layout={'result': {'kwc': 3.3}},
            etude_params={'puissance_kwc': 9.9})
        self.assertAlmostEqual(
            ventes_reports.kwc_concu_devis(devis), 3.3, places=2)

    def test_repli_sur_etude_params_si_le_layout_ne_porte_aucun_kwc(self):
        devis = self._devis(
            'DEV-PV82-4B', roof_layout={'zones': []},
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
