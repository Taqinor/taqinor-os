# -*- coding: utf-8 -*-
"""CIQ119 — rafraîchisseur d'étude C&I : l'étude suit les LIGNES facturées.

``rafraichir_etude_ci_devis`` (appelé par ``rafraichir_etudes_du_devis``)
relit les panneaux et onduleurs réellement au devis, appelle ``etudier_ci``
en « taille donnée » et n'écrit que ``etude_ci`` / ``production_figee``.
PVGIS est simulé (table vendorisée de Casablanca) : aucun accès réseau.

Chemins de copie (grep ``etude_params_pour_copie``) — ils purgent déjà
``etude_ci``/``production_figee`` (CIQ117) puis appellent
``rafraichir_etudes_du_devis(force=True)``, qui recalcule donc l'étude C&I :
``domain/creation.py`` (dupliquer), ``domain/cycle_vie.py`` (renouveler),
``domain/gammes.py`` (gamme sœur), ``views/devis.dupliquer_variante``.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.ventes.tests.test_ciq119_rafraichir_ci"
"""
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.stock.models import FicheTechnique, Produit
from apps.ventes.domain import etude_ci
from apps.ventes.domain.etudes import rafraichir_etudes_du_devis
from apps.ventes.models import Devis, LigneDevis
from apps.ventes.tests.test_ciq118_etude_ci_preview import _production_casablanca
from authentication.models import Company

User = get_user_model()

ENTREES = {
    'mode': 'industriel', 'tension': 'bt', 'phases': 'tri',
    'site': {'ville': 'Casablanca', 'lat': None, 'lon': None},
    'consommation': {'kwh_mensuels': [20000] * 12},
    'rythme': {'jours_ouverts': [True] * 6 + [False],
               'plages': {'ouvre': [[7, 19]], 'samedi': [[7, 13]]},
               'talon': {'kw': 5}},
    'tarif_declare': {'contrat': 'bt_patente'},
}


class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.co = Company.objects.get_or_create(
            slug='ciq119-co', defaults={'nom': 'CIQ119 Co'})[0]
        cls.client_obj = Client.objects.create(company=cls.co, nom='Usine CIQ119')
        cls.panneau = Produit.objects.create(
            company=cls.co, nom='Panneau 710W', prix_vente=Decimal('1272.73'),
            prix_achat=Decimal('800'))
        FicheTechnique.objects.create(
            company=cls.co, produit=cls.panneau, type_fiche='module',
            pmax_wc=Decimal('710'), vmp_v=Decimal('40'), voc_v=Decimal('48'),
            isc_a=Decimal('18'), imp_a=Decimal('17'))
        cls.ond50 = cls._onduleur('Onduleur réseau Huawei 50kW Triphasé', 50)
        cls.ond30 = cls._onduleur('Onduleur réseau Huawei 30kW Triphasé', 30)

    @classmethod
    def _onduleur(cls, nom, kw):
        produit = Produit.objects.create(
            company=cls.co, nom=nom, prix_vente=Decimal('40000'),
            prix_achat=Decimal('30000'), role_devis='onduleur_reseau', garantie='10 ans constructeur')
        FicheTechnique.objects.create(
            company=cls.co, produit=produit, type_fiche='onduleur',
            ond_ac_kw=Decimal(kw), ond_phases=3, ond_n_mppt=4,
            ond_mppt_v_min=Decimal('200'), ond_mppt_v_max=Decimal('1000'),
            ond_v_max_abs=Decimal('1100'), ond_i_max_mppt_a=Decimal('30'),
            ond_rendement_euro_pct=Decimal('98.4'))
        return produit

    def setUp(self):
        patcher = mock.patch.object(etude_ci, 'lire_production',
                                    side_effect=_production_casablanca)
        self.production = patcher.start()
        self.addCleanup(patcher.stop)
        self.user = User.objects.create_user(
            username='ciq119_user', password='x', role_legacy='responsable',
            company=self.co)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def _devis(self, mode='industriel', ref='DEV-CIQ119-01'):
        devis = Devis.objects.create(
            company=self.co, reference=ref, client=self.client_obj,
            statut='brouillon', taux_tva=Decimal('20'), mode_installation=mode,
            etude_params=dict(ENTREES, mode=mode) if mode in ('commercial', 'industriel')
            else {})
        LigneDevis.objects.create(
            devis=devis, produit=self.panneau, designation='Panneau 710W',
            quantite=Decimal('70'), prix_unitaire=Decimal('1272.73'), remise=Decimal('0'))
        LigneDevis.objects.create(
            devis=devis, produit=self.ond50, designation='Onduleur 50 kW',
            quantite=Decimal('1'), prix_unitaire=Decimal('40000'), remise=Decimal('0'))
        return devis


class RafraichisseurTests(_Base):
    def test_ligne_onduleur_remplacee_recalcule_etude(self):
        devis = self._devis()
        rafraichir_etudes_du_devis(devis)
        devis.refresh_from_db()
        avant = devis.etude_params['etude_ci']
        self.assertIsNotNone(avant['bilan'])
        self.assertIn('production_figee', devis.etude_params)
        self.assertEqual(avant['taille']['retenue_kwc'], 49.7)

        ligne = devis.lignes.get(produit=self.ond50)
        rep = self.api.patch(f'/api/django/ventes/devis-lignes/{ligne.id}/',
                             {'produit': self.ond30.id}, format='json')
        self.assertEqual(rep.status_code, 200, rep.content)
        devis.refresh_from_db()
        apres = devis.etude_params['etude_ci']
        self.assertNotEqual(avant['empreinte'], apres['empreinte'])
        self.assertIsNotNone(apres['bilan'])
        ids = [o['produit'] for o in apres['composition']['onduleurs']['combinaison']]
        self.assertEqual(ids, [self.ond30.id])

    def test_panneaux_modifies_bilan_recalcule(self):
        devis = self._devis()
        rafraichir_etudes_du_devis(devis)
        devis.refresh_from_db()
        avant = devis.etude_params['etude_ci']['bilan']['production_kwh']
        ligne = devis.lignes.get(produit=self.panneau)
        rep = self.api.patch(f'/api/django/ventes/devis-lignes/{ligne.id}/',
                             {'quantite': '100'}, format='json')
        self.assertEqual(rep.status_code, 200, rep.content)
        devis.refresh_from_db()
        self.assertGreater(devis.etude_params['etude_ci']['bilan']['production_kwh'], avant)

    def test_second_appel_sans_changement_zero_ecriture(self):
        devis = self._devis()
        rafraichir_etudes_du_devis(devis)
        devis.refresh_from_db()
        with CaptureQueriesContext(connection) as requetes:
            etude_ci.rafraichir_etude_ci_devis(devis)
        ecritures = [q['sql'] for q in requetes.captured_queries
                     if q['sql'].lstrip().upper().startswith(('INSERT', 'UPDATE', 'DELETE'))]
        self.assertEqual(ecritures, [])

    def test_plus_aucun_panneau_derivees_retirees(self):
        devis = self._devis()
        rafraichir_etudes_du_devis(devis)
        devis.lignes.filter(produit=self.panneau).delete()
        devis.refresh_from_db()
        etude_ci.rafraichir_etude_ci_devis(devis)
        devis.refresh_from_db()
        self.assertNotIn('etude_ci', devis.etude_params)
        self.assertNotIn('production_figee', devis.etude_params)

    def test_residentiel_et_agricole_inchanges(self):
        for mode, ref in (('residentiel', 'DEV-CIQ119-R'), ('agricole', 'DEV-CIQ119-A')):
            devis = self._devis(mode=mode, ref=ref)
            avant = dict(devis.etude_params or {})
            self.assertIsNone(etude_ci.rafraichir_etude_ci_devis(devis))
            devis.refresh_from_db()
            self.assertEqual(dict(devis.etude_params or {}), avant)
            self.production.assert_not_called()

    def test_statut_jamais_touche(self):
        devis = self._devis()
        rafraichir_etudes_du_devis(devis)
        devis.refresh_from_db()
        self.assertEqual(devis.statut, 'brouillon')
