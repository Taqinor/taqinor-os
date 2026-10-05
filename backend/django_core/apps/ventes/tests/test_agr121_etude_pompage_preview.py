# -*- coding: utf-8 -*-
"""AGR121 — aperçu serveur ``POST /ventes/etude-pompage/preview/`` : un
orchestrateur ventes (``domain/pompage.etudier_pompage``), le noyau
``core.pompage``, AUCUNE écriture.

Réseau : PVGIS et TMY sont TOUJOURS simulés (``profils_horaires_site`` /
``temperatures_du_site`` patchés) — aucun test ne touche le réseau.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.ventes.tests.test_agr121_etude_pompage_preview"
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

from apps.crm.models import Lead
from apps.parametres.models import CompanyProfile
from apps.stock.models import FicheTechnique, Produit
from apps.ventes.domain import pompage
from authentication.models import Company

User = get_user_model()

CONTRAT = json.loads(
    (Path(__file__).resolve().parent.parent / 'contract_samples'
     / 'etude_pompage_preview.json').read_text(encoding='utf-8'))
URL = '/api/django/ventes/etude-pompage/preview/'

_JOUR = ([0] * 6 + [100, 300, 500, 700, 850, 950, 1000, 950, 850, 700, 500,
                    300, 100] + [0] * 5)
PROFILS = [[g * (0.7 + 0.05 * i) for g in _JOUR] for i in range(12)]
COURBE = {'debits_m3h': [0, 12, 24, 30, 36, 39],
          'hmt_m': [91, 85, 70, 60, 43, 34]}


def _cles(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from _cles(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _cles(v)


def _ids(obj):
    """Toutes les valeurs « produit »/« id »/« pompe_produit » du résultat."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in ('produit', 'pompe_produit', 'id') and v is not None:
                yield v
            yield from _ids(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _ids(v)


class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.co = Company.objects.get_or_create(
            slug='agr121-co', defaults={'nom': 'AGR121 Co'})[0]
        cls.autre = Company.objects.get_or_create(
            slug='agr121-autre', defaults={'nom': 'AGR121 Autre'})[0]
        profil, _ = CompanyProfile.objects.get_or_create(company=cls.co)
        CompanyProfile.objects.filter(pk=profil.pk).update(
            agricole_pump_hours=Decimal('7'))
        cls.pompe = cls._produit(
            cls.co, 'Pompe immergée OSP 30/8 — 7.5 kW 380V',
            role_pompage='pompe', type_pompe='immergee', alimentation='tri',
            pompe_kw=Decimal('7.5'), tension_v=380, courbe_pompe=COURBE)
        cls.variateur = cls._produit(
            cls.co, 'VARIATEUR VEICHI SI23 7.5KW 380V',
            role_pompage='variateur_pompage', alimentation='tri',
            pompe_kw=Decimal('7.5'), tension_v=380)
        FicheTechnique.objects.create(
            company=cls.co, produit=cls.variateur,
            type_fiche='variateur_pompage', ond_mppt_v_min=Decimal('250'),
            ond_mppt_v_max=Decimal('750'), ond_v_max_abs=Decimal('800'),
            ond_i_max_mppt_a=Decimal('20'), ond_phases=3,
            var_v_sortie_v=Decimal('380'))
        cls.panneau = cls._produit(cls.co, 'Panneau 710W')
        FicheTechnique.objects.create(
            company=cls.co, produit=cls.panneau, type_fiche='module',
            pmax_wc=Decimal('710'), vmp_v=Decimal('40'), voc_v=Decimal('48'),
            isc_a=Decimal('18'), imp_a=Decimal('17'))
        cls.structure = cls._produit(cls.co, 'Structure au sol pompage',
                                     role_pompage='structure_sol')
        # Une pompe d'une AUTRE société, plus avantageuse : jamais lue.
        cls.pompe_etrangere = cls._produit(
            cls.autre, 'Pompe immergée étrangère 5.5 kW 380V',
            role_pompage='pompe', type_pompe='immergee', alimentation='tri',
            pompe_kw=Decimal('5.5'), tension_v=380, courbe_pompe=COURBE)

    @staticmethod
    def _produit(company, nom, **kw):
        kw.setdefault('prix_vente', Decimal('1000'))
        kw.setdefault('prix_achat', Decimal('600'))
        return Produit.objects.create(company=company, nom=nom, **kw)

    def setUp(self):
        self.user = User.objects.create_user(
            username='agr121_user', password='x', role_legacy='responsable',
            company=self.co)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        patcher_p = mock.patch.object(pompage, 'profils_horaires_site',
                                      return_value=PROFILS)
        patcher_t = mock.patch.object(pompage, 'temperatures_du_site',
                                      return_value=None)
        self.profils = patcher_p.start()
        patcher_t.start()
        self.addCleanup(patcher_p.stop)
        self.addCleanup(patcher_t.stop)

    def corps(self, **extra):
        corps = json.loads(json.dumps(CONTRAT['corps']))
        corps.update(extra)
        return corps

    def post(self, corps):
        rep = self.api.post(URL, corps, format='json')
        self.assertEqual(rep.status_code, 200, rep.content[:500])
        return rep.json()


class ContratTests(_Base):
    def test_reponse_conforme_au_contrat(self):
        data = self.post(self.corps())
        exemple = CONTRAT['exemple']
        self.assertEqual(set(data), set(exemple))
        for cle in ('hmt', 'besoin', 'conception', 'pompe', 'variateur',
                    'puissance_retenue', 'champ', 'production',
                    'controle_conception', 'ha_irrigables',
                    'autonomie_reservoir_jours', 'kit'):
            self.assertIsInstance(data[cle], dict, cle)
            self.assertEqual(set(data[cle]), set(exemple[cle]), cle)
        self.assertEqual(set(data['champ']['chaines']),
                         set(exemple['champ']['chaines']))
        self.assertEqual(set(data['conception']['plafonds']),
                         set(exemple['conception']['plafonds']))
        for taille in data['tailles']:
            self.assertEqual(set(taille), set(exemple['tailles'][0]))
        for alerte in data['alertes']:
            self.assertEqual(set(alerte), {'code', 'champ', 'message'})
        for entree in data['entrees_resolues'].values():
            self.assertEqual(set(entree), {'valeur', 'provenance'})
            self.assertEqual(set(entree['provenance']),
                             {'origine', 'detail', 'date'})

    def test_calcul_reel_pompe_neuve(self):
        data = self.post(self.corps())
        self.assertEqual(data['pompe']['produit'], self.pompe.id)
        self.assertEqual(data['variateur']['produit'], self.variateur.id)
        self.assertEqual(data['hmt']['source'], 'calculee')
        self.assertEqual(data['besoin']['nature'], 'declare')
        self.assertEqual(data['production']['mode'], 'courbe')
        self.assertEqual(data['production']['source_irradiation'], 'pvgis')
        self.assertEqual(len(data['couverture_pct_mois']), 12)
        self.assertEqual(
            data['entrees_resolues']['volume_m3_jour']['provenance']
            ['origine'], 'saisie')
        self.assertEqual(data['kit']['non_inclus'], ['forage', 'genie_civil'])

    def test_aucune_cle_prix_achat_ni_marge(self):
        data = self.post(self.corps())
        cles = set(_cles(data))
        self.assertNotIn('prix_achat', cles)
        self.assertNotIn('marge', cles)

    def test_produit_dune_autre_societe_jamais_lu(self):
        data = self.post(self.corps())
        self.assertNotIn(self.pompe_etrangere.id, set(_ids(data)))
        self.assertNotIn('étrangère', json.dumps(data, ensure_ascii=False))

    def test_pvgis_indisponible_repli_etiquete(self):
        self.profils.return_value = None
        data = self.post(self.corps())
        codes = [a['code'] for a in data['alertes']]
        self.assertIn('pvgis_indisponible', codes)
        self.assertEqual(data['production']['mode'], 'repli_plat')
        self.assertEqual(data['production']['source_irradiation'], 'repli')
        self.assertIsNone(data['production']['coordonnees_figees'])
        self.assertEqual(
            data['entrees_resolues']['heures_repli']['provenance']['origine'],
            'reglage_societe')

    def test_aucune_pompe_chiffrable_placeholder_nomme(self):
        Produit.objects.filter(pk=self.pompe.pk).update(prix_vente=0)
        data = self.post(self.corps())
        self.assertTrue(data['pompe']['placeholder'])
        self.assertIsNone(data['production'])
        self.assertIsNone(data['couverture_pct_mois'])
        self.assertEqual(data['tailles'], [])
        self.assertIn('aucune_pompe_chiffrable',
                      [a['code'] for a in data['alertes']])

    def test_anonyme_refuse(self):
        rep = APIClient().post(URL, self.corps(), format='json')
        self.assertIn(rep.status_code, (401, 403))


class PrioriteEtEcritureTests(_Base):
    def _lead(self, company=None):
        return Lead.objects.create(
            company=company or self.co, nom='Agri', prenom='Lead',
            telephone='+212600000121', ville='Taroudant',
            besoin_eau_m3j=Decimal('90'), besoin_eau_source='client')

    def test_lead_lu_quand_le_corps_se_tait(self):
        lead = self._lead()
        corps = self.corps(lead=lead.id)
        corps['besoin'] = dict(corps['besoin'], volume_m3_jour=None)
        data = self.post(corps)
        entree = data['entrees_resolues']['volume_m3_jour']
        self.assertEqual(entree['valeur'], 90)
        self.assertEqual(entree['provenance']['origine'], 'lead')
        self.assertEqual(entree['provenance']['detail'], 'client')

    def test_corps_prime_sur_le_lead(self):
        lead = self._lead()
        data = self.post(self.corps(lead=lead.id))
        entree = data['entrees_resolues']['volume_m3_jour']
        self.assertEqual(entree['valeur'], 135)
        self.assertEqual(entree['provenance']['origine'], 'saisie')

    def test_lead_dune_autre_societe_ignore(self):
        lead = self._lead(company=self.autre)
        corps = self.corps(lead=lead.id)
        corps['besoin'] = dict(corps['besoin'], volume_m3_jour=None)
        data = self.post(corps)
        self.assertNotIn('volume_m3_jour', data['entrees_resolues'])

    def test_aucune_ecriture(self):
        lead = self._lead()
        with CaptureQueriesContext(connection) as requetes:
            pompage.etudier_pompage(self.co, self.corps(), lead=lead)
        ecritures = [q['sql'] for q in requetes.captured_queries
                     if q['sql'].lstrip().upper().startswith(
                         ('INSERT', 'UPDATE', 'DELETE'))]
        self.assertEqual(ecritures, [])
