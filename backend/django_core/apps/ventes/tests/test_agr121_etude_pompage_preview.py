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
from django.test import SimpleTestCase, TestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Lead
from apps.parametres.models import CompanyProfile
from apps.stock.models import FicheTechnique, Produit
from apps.ventes.domain import pompage
from authentication.models import Company
from core.tests.test_agr120_tailles import PROFILS as PROFILS_SAISONNIERS

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
    def test_corps_tableau_400(self):
        # CI #997 — un corps hors schéma (``[null, null]``) répondait 200
        # (calcul « omis ») : 400.
        rep = self.api.post(URL, [None, None], format='json')
        self.assertEqual(rep.status_code, 400, rep.content)

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
        # AGM8 — l'étiquette de similitude (« estimation ») est servie, comme
        # celle du rendement non publié (fiche variateur sans MPPT).
        from core.pompage.volumes import (
            ESTIMATION_SIMILITUDE, ETIQUETTE_RENDEMENT_NON_PUBLIE,
        )
        self.assertIn(ESTIMATION_SIMILITUDE,
                      data['production']['etiquettes'])
        self.assertIn(ETIQUETTE_RENDEMENT_NON_PUBLIE,
                      data['production']['etiquettes'])
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

    def test_sans_localisation_alerte_site_inconnu(self):
        """AGQ26 (C-AGQ-025) — aucune ville ni GPS : l'alerte nomme le SITE
        manquant (`site_inconnu`), jamais une panne PVGIS ; le repli plat
        reste étiqueté."""
        self.profils.return_value = None
        corps = self.corps()
        corps.pop('localisation', None)
        data = self.post(corps)
        codes = [a['code'] for a in data['alertes']]
        self.assertIn('site_inconnu', codes)
        self.assertNotIn('pvgis_indisponible', codes)
        alerte = next(a for a in data['alertes'] if a['code'] == 'site_inconnu')
        self.assertIn('Site non renseigné (ville ou GPS)', alerte['message'])
        self.assertEqual(data['production']['source_irradiation'], 'repli')

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


# ── Rejeu live AGQ41 (24/10) — pompe EXISTANTE sans kW de plaque ────────────

def _var_cat(id_, kw, tension=380):
    return {'id': id_, 'nom': 'VARIATEUR VEICHI SI23 %sKW %sV' % (kw, tension),
            'role_pompage': 'variateur_pompage', 'pompe_kw': str(kw),
            'tension_v': tension, 'fiche': None, 'prix_connu': True,
            'alimentation': 'tri' if tension == 380 else 'mono'}


def _catalogue_existante():
    return {
        'pompage': [
            _var_cat(401, 2.2, 220), _var_cat(402, 5.5), _var_cat(403, 7.5),
            {'id': 51, 'nom': 'Structure au sol pompage',
             'role_pompage': 'structure_sol', 'prix_connu': True},
            {'id': 60, 'nom': 'Installation pompage',
             'role_pompage': 'installation_pompage', 'prix_connu': True,
             'prix_fixe_ht': 1000.0, 'prix_par_panneau_ht': 100.0},
        ],
        'panneau': {'id': 3, 'nom': 'Panneau 710W', 'prix_connu': True,
                    'pmax_wc': 710.0, 'vmp_v': 40.4, 'voc_v': 48.6,
                    'isc_a': 18.6, 'imp_a': 17.6,
                    'temp_coeff_voc_pct_c': None,
                    'temp_coeff_pmax_pct_c': None},
        'transport': None, 'installation_toiture': None, 'socle': None,
    }


class PompeExistanteSansKwPlaqueTests(SimpleTestCase):
    """Sans DB : catalogue, PVGIS et TMY simulés (``etudier_pompage(None, …)``
    ne lit aucune société)."""

    def _etude(self, heures=7):
        corps = json.loads(json.dumps(CONTRAT['corps']))
        corps.update(
            mode_pompe='existante',
            plaque={'kw': None, 'tension_v': None, 'phases': None, 'cv': 7,
                    'courant_a': None},
            besoin=dict(corps['besoin'], mode='pompe_actuelle',
                        volume_m3_jour=None, debit_actuel_m3h=12,
                        heures_actuelles_jour=heures))
        with mock.patch.object(pompage, 'lire_catalogue',
                               return_value=_catalogue_existante()), \
                mock.patch.object(pompage, 'profils_horaires_site',
                                  return_value=PROFILS_SAISONNIERS), \
                mock.patch.object(pompage, 'temperatures_du_site',
                                  return_value=None):
            return pompage.etudier_pompage(None, corps)

    def test_champ_du_resume_egal_champ_de_la_taille_retenue(self):
        """Avant : « Champ 4,95 kWc (9 panneaux) » dans le résumé et
        « 5,5 kWc · 10 panneaux » sur la carte Recommandée (deux appels du
        noyau, l'un avec le mois critique de la passe 1, l'autre sans) ; ici
        6,39 kWc (9) contre 7,1 kWc (10) sur des profils SAISONNIERS (la
        passe 1 et le champ ne tombent pas sur le même mois)."""
        data = self._etude()
        self.assertIsNotNone(data['champ']['nb_panneaux'])
        retenue = [t for t in data['tailles'] if t['retenue']]
        self.assertEqual(len(retenue), 1)
        self.assertEqual(data['champ']['kwc'], retenue[0]['champ_kwc'])
        self.assertEqual(data['champ']['nb_panneaux'],
                         retenue[0]['nb_panneaux'])
        panneaux = next(ligne for ligne in data['kit']['inclus']
                        if ligne['cle'] == 'panneaux')
        self.assertEqual(panneaux['quantite'], data['champ']['nb_panneaux'])

    def test_agm5_heures_superieures_a_24_alerte_besoin_tel_que_saisi(self):
        """AGM5 — 30 h/jour : alerte qui nomme le champ, jamais un refus ni
        un rognage (le besoin reste débit × heures saisies)."""
        data = self._etude(heures=30)
        alerte = [a for a in data['alertes']
                  if a['code'] == 'heures_superieures_24']
        self.assertEqual(len(alerte), 1)
        self.assertEqual(alerte[0]['champ'], 'besoin.heures_actuelles_jour')
        self.assertEqual(max(data['besoin']['m3_jour_mois']), 12 * 30)
        self.assertNotIn(
            'heures_superieures_24',
            [a['code'] for a in self._etude(heures=7)['alertes']])

    def test_variateur_non_choisi_est_un_role_minimum_manquant(self):
        data = self._etude()
        # La clé servie est dans le contrat (exemples synchronisés).
        self.assertEqual(set(data), set(CONTRAT['exemple_pompe_existante']))
        self.assertIsNone(data['variateur']['produit'])
        self.assertIn('kW de plaque', data['variateur']['motif'])
        roles = {r['cle'] for r in data['roles_minimum_manquants']}
        self.assertIn('variateur', roles)
        # La pompe n'est jamais un rôle manquant en mode « existante ».
        self.assertNotIn('pompe', roles)
        self.assertNotIn('variateur',
                         [ligne['cle'] for ligne in data['kit']['inclus']])


class CodesChampNonDimensionneTests(SimpleTestCase):
    """AGM3 — les deux vraies causes (HMT inconnue, besoin nul) rejoignent la
    liste du domaine (déplacé de core/tests : core n'importe pas apps — M3)."""

    def test_agm3_les_deux_codes_rejoignent_la_liste_du_domaine(self):
        codes = pompage.CODES_CHAMP_NON_DIMENSIONNE
        self.assertIn("hmt_inconnue", codes)
        self.assertIn("besoin_nul", codes)
        self.assertIn("irradiation_inconnue", codes)


class MotifVariateurAbsentTests(SimpleTestCase):
    """AGM15 — rendu R2 : « Variateur : aucun article au catalogue » alors
    que le catalogue porte 16 VEICHI (pompe existante au CV seul, ou aucune
    pompe retenue). La cause servie par ``variateur.motif`` est reprise."""

    def _manquants(self, motif):
        sortie = {'pompe': {'mode': 'existante'},
                  'variateur': {'nom': None, 'motif': motif},
                  'champ': {'nb_panneaux': 6}, 'kit': {'inclus': []}}
        return {m['cle']: m['motif']
                for m in pompage.roles_minimum_manquants(sortie)}

    def test_kw_de_plaque_a_relever_nomme(self):
        motif = ("kW de plaque à relever (visite « relevé du point d'eau », "
                 "D-AGR-4) : variateur non choisi")
        self.assertEqual(self._manquants(motif)['variateur'], motif)

    def test_aucune_pompe_retenue_nomme(self):
        motif = 'aucune pompe retenue : variateur non choisi'
        self.assertEqual(self._manquants(motif)['variateur'], motif)

    def test_absence_au_catalogue_inchangee(self):
        # Le refus AGQ6 du devis auto reformule CE motif : il reste tel quel.
        for motif in (pompage.MOTIF_VARIATEUR_CATALOGUE, None):
            self.assertEqual(self._manquants(motif)['variateur'],
                             'aucun article au catalogue')


class ModeEtTypePompeAlertesTests(SimpleTestCase):
    """AGM6 — jamais de bascule silencieuse : un mode de pompe inconnu et un
    type de pompe absent sont DITS au vendeur (SimpleTestCase : catalogue,
    PVGIS et TMY simulés, aucune base)."""

    def _etude(self, **extra):
        corps = json.loads(json.dumps(CONTRAT['corps']))
        corps.update(extra)
        for cle in [c for c, v in extra.items() if v is None]:
            del corps[cle]
        with mock.patch.object(pompage, 'lire_catalogue',
                               return_value=_catalogue_existante()), \
                mock.patch.object(pompage, 'profils_horaires_site',
                                  return_value=PROFILS_SAISONNIERS), \
                mock.patch.object(pompage, 'temperatures_du_site',
                                  return_value=None):
            return pompage.etudier_pompage(None, corps)

    @staticmethod
    def _codes(data):
        return [a['code'] for a in data['alertes']]

    def test_mode_inconnu_alerte_et_pompe_neuve_etudiee(self):
        data = self._etude(mode_pompe='nouvelle')
        alerte = [a for a in data['alertes']
                  if a['code'] == 'mode_pompe_invalide']
        self.assertEqual(len(alerte), 1)
        self.assertEqual(alerte[0]['champ'], 'mode_pompe')
        self.assertIn('nouvelle', alerte[0]['message'])
        self.assertEqual(data['pompe']['mode'], 'neuve')

    def test_mode_valide_ou_vide_aucune_alerte_de_mode(self):
        for corps in ({'mode_pompe': 'neuve'}, {'mode_pompe': None}):
            self.assertNotIn('mode_pompe_invalide',
                             self._codes(self._etude(**corps)), corps)

    def test_neuve_sans_type_pompe_alerte_type_suppose(self):
        data = self._etude(type_pompe=None)
        alerte = [a for a in data['alertes']
                  if a['code'] == 'type_pompe_supposee']
        self.assertEqual(len(alerte), 1)
        self.assertEqual(alerte[0]['champ'], 'type_pompe')
        self.assertNotIn('type_pompe_supposee',
                         self._codes(self._etude(type_pompe='immergee')))
