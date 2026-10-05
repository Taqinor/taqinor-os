# -*- coding: utf-8 -*-
"""CIQ118 — aperçu serveur ``POST /ventes/etude-ci/preview/`` : un
orchestrateur ventes (``domain/etude_ci.etudier_ci``), le noyau ``moteur_ci``,
AUCUNE écriture.

Réseau : PVGIS est TOUJOURS simulé (``etude_ci.lire_production`` patché sur
la table vendorisée de Casablanca) — aucun test ne touche le réseau.

Appelants de ``etudier_ci`` (grep) : ``apps/ventes/etude_ci_view.py`` (cette
tâche) ; CIQ119 (rafraîchisseur) et CIQ120 (devis automatique) s'y branchent.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.ventes.tests.test_ciq118_etude_ci_preview"
"""
import json
from decimal import Decimal
from pathlib import Path
from unittest import mock

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.calepinage.models import ProfilTypeConsommation
from apps.crm.models import Lead
from apps.parametres.pvgis_profils import (
    SAISONS,
    productible_mensuel,
    profil_production_journalier,
    vers_heure_locale,
)
from apps.stock.models import FicheTechnique, Produit
from apps.ventes.domain import etude_ci
from authentication.models import Company

User = get_user_model()

CONTRAT = json.loads(
    (Path(__file__).resolve().parent.parent / 'contract_samples'
     / 'etude_ci_preview.json').read_text(encoding='utf-8'))
URL = '/api/django/ventes/etude-ci/preview/'


def _production_casablanca(_site=None):
    formes = {}
    for saison in SAISONS:
        resolu = profil_production_journalier(saison=saison, ville='Casablanca')
        if resolu:
            formes[saison] = vers_heure_locale(resolu[0])
    mensuel, source = productible_mensuel(ville='Casablanca')
    return mensuel, formes, source


def _cles(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from _cles(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _cles(v)


class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.co = Company.objects.get_or_create(
            slug='ciq118-co', defaults={'nom': 'CIQ118 Co'})[0]
        cls.autre = Company.objects.get_or_create(
            slug='ciq118-autre', defaults={'nom': 'CIQ118 Autre'})[0]
        cls.panneau = cls._produit(cls.co, 'Panneau 710W', prix_vente=Decimal('1272.73'))
        FicheTechnique.objects.create(
            company=cls.co, produit=cls.panneau, type_fiche='module',
            pmax_wc=Decimal('710'), vmp_v=Decimal('40'), voc_v=Decimal('48'),
            isc_a=Decimal('18'), imp_a=Decimal('17'))
        cls.onduleur = cls._onduleur(cls.co, 'Onduleur réseau Huawei 50kW Triphasé', 50)
        # Un onduleur d'une AUTRE société, moins cher : jamais lu.
        cls.onduleur_etranger = cls._onduleur(
            cls.autre, 'Onduleur réseau étranger 50kW Triphasé', 50,
            prix=Decimal('100'))

    @staticmethod
    def _produit(company, nom, **kw):
        kw.setdefault('prix_vente', Decimal('1000'))
        kw.setdefault('prix_achat', Decimal('600'))
        return Produit.objects.create(company=company, nom=nom, **kw)

    @classmethod
    def _onduleur(cls, company, nom, kw, prix=Decimal('45833.33')):
        produit = cls._produit(company, nom, prix_vente=prix,
                               role_devis='onduleur_reseau', garantie='10 ans constructeur')
        FicheTechnique.objects.create(
            company=company, produit=produit, type_fiche='onduleur',
            ond_ac_kw=Decimal(kw), ond_phases=3, ond_n_mppt=4,
            ond_mppt_v_min=Decimal('200'), ond_mppt_v_max=Decimal('1000'),
            ond_v_max_abs=Decimal('1100'), ond_i_max_mppt_a=Decimal('30'),
            ond_rendement_euro_pct=Decimal('98.4'))
        return produit

    def setUp(self):
        self.user = User.objects.create_user(
            username='ciq118_user', password='x', role_legacy='responsable',
            company=self.co)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        patcher = mock.patch.object(etude_ci, 'lire_production',
                                    side_effect=_production_casablanca)
        self.production = patcher.start()
        self.addCleanup(patcher.stop)

    def corps(self, **extra):
        corps = json.loads(json.dumps(CONTRAT['corps']))
        corps['lead'] = None
        corps['tarif'] = {'contrat': 'bt_patente'}
        corps['site'] = {'ville': 'Casablanca', 'lat': None, 'lon': None}
        # Longueurs non déclarées : câbles « à confirmer à la visite », la
        # taille reste calculable sur le catalogue minimal du test.
        corps['contraintes'] = {'revente_choisie': False, 'nb_points_raccordement': 1,
                                'longueur_dc_m': None, 'longueur_ac_m': None,
                                'besoin_cellule_mt': False}
        corps['toit'] = {'type_pose': None, 'surface_utile_m2': None}
        corps.update(extra)
        return corps

    def post(self, corps):
        rep = self.api.post(URL, corps, format='json')
        self.assertEqual(rep.status_code, 200, rep.content[:500])
        return rep.json()

    def _lead(self, **kw):
        kw.setdefault('type_installation', 'commercial')
        kw.setdefault('ville', 'Casablanca')
        return Lead.objects.create(company=self.co, nom='Pro CIQ118', **kw)


class ContratTests(_Base):
    def test_reponse_conforme_au_contrat(self):
        data = self.post(self.corps())
        exemple = CONTRAT['exemple']
        self.assertEqual(set(data), set(exemple))
        self.assertEqual(set(data['bilan']), set(exemple['bilan']))
        self.assertEqual(set(data['taille']), set(exemple['taille']))
        self.assertEqual(set(data['profil_charge']), set(exemple['profil_charge']))
        self.assertEqual(set(data['production']), set(exemple['production']))
        self.assertEqual(set(data['composition']), set(exemple['composition']))
        self.assertEqual(set(data['regime_8221_suggere']),
                         set(exemple['regime_8221_suggere']))
        for alerte in data['alertes']:
            self.assertEqual(set(alerte), set(exemple['alertes'][0]))
        for entree in data['entrees_resolues'].values():
            self.assertEqual(set(entree), {'valeur', 'provenance'})
            self.assertEqual(set(entree['provenance']), {'origine', 'detail', 'date'})
        self.assertIsNotNone(data['taille']['retenue_kwc'])

    def test_aucune_cle_prix_achat_ni_marge(self):
        data = self.post(self.corps())
        cles = set(_cles(data))
        self.assertNotIn('prix_achat', cles)
        self.assertNotIn('marge', cles)

    def test_produit_dune_autre_societe_jamais_lu(self):
        catalogue = etude_ci.lire_catalogue_ci(self.co)
        ids = {o['produit'] for o in catalogue['onduleurs']}
        self.assertIn(self.onduleur.id, ids)
        self.assertNotIn(self.onduleur_etranger.id, ids)
        data = self.post(self.corps())
        self.assertNotIn('étranger', json.dumps(data, ensure_ascii=False))

    def test_pvgis_indisponible_etude_null_et_avertissement(self):
        self.production.side_effect = None
        self.production.return_value = None
        data = self.post(self.corps())
        self.assertIsNone(data['production'])
        self.assertIsNone(data['taille'])
        self.assertIsNone(data['bilan'])
        self.assertIn('production_indisponible', [a['code'] for a in data['alertes']])

    def test_aucune_ecriture(self):
        lead = self._lead(conso_mensuelle_kwh=Decimal('4000'),
                          categorie_commerciale='bureau')
        with CaptureQueriesContext(connection) as requetes:
            etude_ci.etudier_ci(self.co, self.corps(), lead=lead)
        ecritures = [q['sql'] for q in requetes.captured_queries
                     if q['sql'].lstrip().upper().startswith(('INSERT', 'UPDATE', 'DELETE'))]
        self.assertEqual(ecritures, [])


class LeadTests(_Base):
    def _corps_lead(self, lead):
        corps = self.corps()
        for cle in ('consommation', 'rythme', 'tension', 'phases', 'site'):
            corps.pop(cle, None)
        corps['lead'] = lead.id
        return corps

    def test_kwh_saisis_priment_sur_la_facture_dhiver(self):
        lead = self._lead(conso_mensuelle_kwh=Decimal('4000'),
                          facture_hiver=Decimal('5000'), categorie_commerciale='bureau')
        data = self.post(self._corps_lead(lead))
        self.assertEqual(data['entrees_resolues']['kwh_mensuel_declare']['valeur'], 4000)
        self.assertAlmostEqual(
            sum(m['consommation_kwh'] for m in data['bilan']['par_mois']), 48000, delta=12)
        conso = sum(j['nb_jours'] * sum(j['charge_kwh'])
                    for j in data['profil_charge']['jours_types'])
        self.assertAlmostEqual(conso, 48000, delta=1)

    def test_lead_kwh_seulement_meme_taille_aperçu_et_moteur(self):
        lead = self._lead(conso_mensuelle_kwh=Decimal('6000'), categorie_commerciale='bureau')
        corps = self._corps_lead(lead)
        data = self.post(corps)
        direct = etude_ci.etudier_ci(
            self.co, {k: v for k, v in corps.items() if k != 'lead'}, lead=lead)
        self.assertIsNotNone(data['taille']['retenue_kwc'])
        self.assertEqual(data['taille']['retenue_kwc'], direct['taille']['retenue_kwc'])
        self.assertEqual(data['niveau_donnees'], 'estimation')
        self.assertTrue(data['sous_reserve_visite']['valeur'])

    def test_lead_dune_autre_societe_ignore(self):
        lead = Lead.objects.create(company=self.autre, nom='Étranger',
                                   type_installation='commercial',
                                   conso_mensuelle_kwh=Decimal('9999'))
        data = self.post(dict(self.corps(), lead=lead.id))
        self.assertNotIn('kwh_mensuel_declare', data['entrees_resolues'])

    def test_profil_societe_commercial_lu_par_la_facade(self):
        ProfilTypeConsommation.objects.create(
            company=self.co, cle='bureau', libelle='Bureau relevé',
            famille='commercial', provenance='relevé de compteur 2025',
            courbe={'annuel': [0] * 8 + [10] * 10 + [0] * 6})
        lead = self._lead(conso_mensuelle_kwh=Decimal('6000'), categorie_commerciale='bureau')
        data = self.post(self._corps_lead(lead))
        self.assertEqual(data['profil_charge']['methode'], 'archetype')
        self.assertEqual(data['profil_charge']['archetype']['cle'], 'bureau')
        self.assertEqual(data['profil_charge']['archetype']['source'],
                         'relevé de compteur 2025')
