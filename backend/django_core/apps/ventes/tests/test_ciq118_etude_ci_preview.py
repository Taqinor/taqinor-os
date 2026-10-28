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
import math
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
from apps.parametres import pvgis_profils as pp
from apps.parametres.models import CompanyProfile
from apps.parametres.pvgis_profils import (
    SAISONS,
    productible_mensuel,
    profil_production_journalier,
    vers_heure_locale,
)
from apps.stock.models import FicheTechnique, Produit
from apps.ventes.domain import etude_ci
from apps.ventes.moteur_ci.production import (
    CLE_POSE_RASANTE,
    SOURCE_ANGLE_POSE_RASANTE,
    plan_de_production,
)
from authentication.models import Company
from core.electrique.cables import SECTIONS_MM2_CI

User = get_user_model()

CONTRAT = json.loads(
    (Path(__file__).resolve().parent.parent / 'contract_samples'
     / 'etude_ci_preview.json').read_text(encoding='utf-8'))
URL = '/api/django/ventes/etude-ci/preview/'


def _production_casablanca(_site=None, toit=None):
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
        # ADEV79 (D-ACI-6=a) — coffret DC, disjoncteur AC et pose sont des
        # rôles de TAILLE : sans prix, aucune taille. Tarifés pour le test.
        cls._produit(cls.co, 'Coffret DC C&I', role_ci='coffret_dc', prix_vente=Decimal('1500'))
        disjoncteur = cls._produit(cls.co, 'Disjoncteur AC 80 A 4P', role_ci='protection_ac',
                                   prix_vente=Decimal('900'))
        FicheTechnique.objects.create(
            company=cls.co, produit=disjoncteur, type_fiche='protection',
            prot_type='disjoncteur', prot_cote='ac', prot_calibre_a=80, prot_poles=4)
        # Fondateur 26/10/2026 — devis préliminaire jamais vide : câbles et
        # structure (toit plat lesté par défaut) chiffrés d'office, tarifés ici.
        cls._produit(cls.co, 'Câble solaire 6 mm² (au mètre)', role_ci='cable_dc',
                     prix_vente=Decimal('11'))
        cls._produit(cls.co, 'Structure toit plat lestée', role_ci='structure_ci',
                     type_pose='toit_plat_leste', prix_vente=Decimal('450'))
        for section in SECTIONS_MM2_CI:
            cable = cls._produit(cls.co, 'Câble AC cuivre 5×%g mm² (au mètre)' % section,
                                 role_ci='cable_ac',
                                 prix_vente=Decimal(str(round(10 * section + 30, 2))))
            FicheTechnique.objects.create(
                company=cls.co, produit=cable, type_fiche='cable', cable_cote='ac',
                cable_section_mm2=float(section), cable_ame='cu')
        CompanyProfile.objects.update_or_create(company=cls.co, defaults={'forfaits_ci': {
            cle: {'fixe_ht': '500', 'par_kwc_ht': '50', 'source': 'grille CIQ118 de test'}
            for cle in ('pose_structure', 'pose_modules')}})
        # CORC6 — chaque prestation réglée a son article (rôle = clé du forfait).
        for cle in ('pose_structure', 'pose_modules'):
            cls._produit(cls.co, 'Prestation %s' % cle, role_ci=cle, prix_vente=Decimal('0'))
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
    def test_corps_tableau_400(self):
        # CI #997 — un corps hors schéma (``[null, null]``) répondait 200
        # (calcul « omis ») : 400.
        rep = self.api.post(URL, [None, None], format='json')
        self.assertEqual(rep.status_code, 400, rep.content)

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

    # ── CORC1 — l'aperçu dit si le devis automatique passera ────────────────

    def test_devis_auto_dit_le_refus_du_bouton_prix_a_renseigner(self):
        # Le catalogue de test ne règle que 2 prestations sur 8 : le bouton
        # refuserait (« Prix à renseigner ») — l'aperçu le dit AVANT le clic.
        data = self.post(self.corps(phases='tri'))
        self.assertFalse(data['devis_auto']['possible'])
        self.assertEqual(data['devis_auto']['champ'], 'composition')
        self.assertTrue(data['devis_auto']['message'].startswith('Prix à renseigner'))
        self.assertIsNone(data['option_avec'])  # aucun hybride au catalogue de test

    def test_devis_auto_refuse_nomme_le_champ_du_lead(self):
        data = self.post(self.corps(tarif=None))
        self.assertFalse(data['devis_auto']['possible'])
        self.assertEqual(data['devis_auto']['champ'], 'contrat_electricite')
        self.assertTrue(data['devis_auto']['message'].startswith('Demandez au client'))

    # ── ADEV82 — bande interne DH/kWc lue ───────────────────────────────────

    def test_bande_prix_kwc_posee_hors_bande_alerte_interne(self):
        CompanyProfile.objects.filter(company=self.co).update(bande_prix_kwc_ci={
            'min_ht': 1, 'max_ht': 2, 'source': 'bande de test'})
        data = self.post(self.corps())
        alerte = next(a for a in data['alertes'] if a['code'] == 'PRIX_KWC_HORS_BANDE')
        self.assertTrue(alerte['interne'])
        self.assertNotEqual(alerte['niveau'], 'bloquant')

    def test_bande_prix_kwc_vide_aucune_alerte(self):
        CompanyProfile.objects.filter(company=self.co).update(bande_prix_kwc_ci=None)
        data = self.post(self.corps())
        self.assertNotIn('PRIX_KWC_HORS_BANDE', [a['code'] for a in data['alertes']])

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

    def test_longueur_dc_declaree_fiches_completes_cable_dc_quantifie(self):
        # ADEV87 — module et onduleurs à fiches complètes : les chaînes se
        # calculent, le câble DC = 2 × Σ chaînes × distance DÉCLARÉE (D-CMP-2), au prix
        # catalogue. Le câble DC du catalogue de base (_Base) est retiré : seul
        # celui-ci doit être retenu.
        Produit.objects.filter(company=self.co, role_ci='cable_dc').delete()
        cable = self._produit(self.co, 'Câble solaire Nexans H1Z2Z2-K 6 mm² (au mètre)',
                              role_devis='cable_dc', prix_vente=Decimal('12'))
        corps = self.corps()
        corps['contraintes']['longueur_dc_m'] = 30
        data = self.post(corps)
        self.assertNotIn('OND_CHAINES_A_VERIFIER', [a['code'] for a in data['alertes']])
        chaines = data['composition']['onduleurs']['chaines']
        self.assertTrue(chaines)
        ligne = next(lg for lg in data['composition']['lignes'] if lg['role'] == 'cable_dc')
        self.assertEqual(ligne['produit'], cable.id)
        self.assertGreater(ligne['quantite'], 0)
        self.assertEqual(ligne['quantite'],
                         2 * sum(c['nb_chaines'] for c in chaines) * 30)
        self.assertTrue(ligne['prix_connu'])

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

    def test_kwh_annuel_contredisant_la_facture_bloque_aussi(self):
        # ADEV100 (L3) — le générateur pré-rempli envoie le kWh en ANNUEL :
        # la décision du 30/09 (kWh ≠ facture > 2× ⇒ bloquant) vaut aussi.
        lead = self._lead(facture_hiver=Decimal('5000'), categorie_commerciale='bureau',
                          tension_raccordement='bt', contrat_electricite='bt_patente')
        corps = self._corps_lead(lead)
        corps['consommation'] = {'kwh_annuel': 480000}
        data = self.post(corps)
        codes = {a['code']: a for a in data['alertes']}
        self.assertIn('kwh_incoherent_factures', codes)
        self.assertEqual(codes['kwh_incoherent_factures']['niveau'], 'bloquant')

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

    # ── ADEV77 (D-ACI-1=b) — relevé partiel : jamais un masque, une estimation ─

    def test_releve_un_mois_et_kwh_declare_les_deux_resolus_taille_calculee(self):
        lead = self._lead(conso_mensuelle_kwh=Decimal('3870'), categorie_commerciale='bureau',
                          releve_conso={'mois': [{'mois': '2026-08', 'kwh': '3870.00'}]})
        data = self.post(self._corps_lead(lead))
        self.assertIn('kwh_mensuel_declare', data['entrees_resolues'])
        self.assertIn('releve_kwh', data['entrees_resolues'])
        self.assertIsNotNone(data['taille']['retenue_kwc'])

    def test_releve_trois_mois_seul_moyenne_fois_douze_estimation(self):
        mois = [{'mois': '2026-06', 'kwh': '3000'}, {'mois': '2026-07', 'kwh': '4000'},
                {'mois': '2026-08', 'kwh': '5000'}]
        lead = self._lead(categorie_commerciale='bureau', releve_conso={'mois': mois})
        data = self.post(self._corps_lead(lead))
        self.assertAlmostEqual(
            sum(m['consommation_kwh'] for m in data['bilan']['par_mois']), 4000 * 12, delta=12)
        hypothese = next(h for h in data['hypotheses'] if h['cle'] == 'consommation')
        self.assertEqual(hypothese['statut'], 'estimation')
        self.assertEqual(hypothese['source'], 'relevé partiel (3 mois)')

    def test_zero_kwh_declare_la_facture_est_lue(self):
        lead = self._lead(conso_mensuelle_kwh=Decimal('0.00'), facture_hiver=Decimal('3500'),
                          categorie_commerciale='bureau', tension_raccordement='bt',
                          contrat_electricite='bt_patente')
        etude = etude_ci.etudier_ci(self.co, {'mode': 'commercial'}, lead=lead)
        self.assertNotIn('consommation_absente', [a['code'] for a in etude['alertes']])
        self.assertIn('facture_hiver_mad', etude['entrees_resolues'])

    def test_couverture_du_lead_pose_declaree_fondateur_2610(self):
        # Fondateur 26/10/2026 — terrasse béton = pose lestée ; tôle et
        # fibrociment = bac acier ; « autre » reste non déclarée.
        attendu = {'terrasse_beton': 'toit_plat_leste', 'tole_metal': 'bac_acier',
                   'fibrociment': 'bac_acier', 'bac_acier': 'bac_acier',
                   'tuiles': 'toiture_inclinee', 'autre': None}
        for toit, pose in attendu.items():
            lead = self._lead(conso_mensuelle_kwh=Decimal('6000'),
                              categorie_commerciale='bureau', type_toiture=toit)
            etude = etude_ci.etudier_ci(self.co, {'mode': 'commercial'}, lead=lead)
            resolue = etude['entrees_resolues'].get('type_pose') or {}
            self.assertEqual(resolue.get('valeur'), pose, toit)

    def test_type_de_surface_du_lead_ombriere_terrain_fondateur_2610(self):
        # Fondateur 26/10/2026 — ombrière / terrain : leur pose prime sur la
        # couverture ; une toiture garde la pose de sa couverture.
        attendu = {'ombriere': 'ombriere', 'terrain': 'sol', 'toiture': 'bac_acier'}
        for surface, pose in attendu.items():
            lead = self._lead(conso_mensuelle_kwh=Decimal('6000'),
                              categorie_commerciale='bureau', type_toiture='tole_metal',
                              type_surface=surface)
            etude = etude_ci.etudier_ci(self.co, {'mode': 'commercial'}, lead=lead)
            self.assertEqual(etude['entrees_resolues']['type_pose']['valeur'], pose, surface)
            self.assertNotIn('_type_surface', etude['entrees_resolues'])

    def test_pente_et_orientation_du_lead_si_les_panneaux_suivent_le_toit(self):
        # Fondateur 26/10/2026 — bac acier : la pente / l'orientation du toit
        # sont celles des panneaux ; toit plat lesté : jamais (tables inclinées).
        lead = self._lead(conso_mensuelle_kwh=Decimal('6000'), categorie_commerciale='bureau',
                          type_toiture='bac_acier', inclinaison_deg=Decimal('15'),
                          orientation='est')
        resolues = etude_ci.etudier_ci(self.co, {'mode': 'commercial'}, lead=lead)['entrees_resolues']
        self.assertEqual(resolues['pente_deg']['valeur'], 15)
        self.assertEqual(resolues['azimut_deg']['valeur'], -90)
        self.assertNotIn('_pente_toit', resolues)
        Lead.objects.filter(pk=lead.pk).update(type_toiture='terrasse_beton')
        lead.refresh_from_db()
        resolues = etude_ci.etudier_ci(self.co, {'mode': 'commercial'}, lead=lead)['entrees_resolues']
        self.assertNotIn('pente_deg', resolues)
        self.assertNotIn('azimut_deg', resolues)

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


class BornePoseParDefautAdev90(_Base):
    """ADEV90 (D-ACI-13=a) — une surface déclarée SANS mode de pose borne la
    taille avec une pose ESTIMÉE (terrasse → lestée, sinon surimposition),
    dite « pose estimée, à confirmer au calepinage » ; plus d'alerte « non
    bornée » quand une surface est déclarée."""

    def _bornes(self, **toit):
        # La contenance d'une surface déclarée se calcule sur les COTES du
        # module (fiche technique) : le module 710 W du catalogue de test les reçoit.
        FicheTechnique.objects.filter(pmax_wc=Decimal('710')).update(
            longueur_mm=2384, largeur_mm=1303)
        corps = self.corps()
        corps['toit'] = dict({'type_pose': None, 'surface_utile_m2': 200}, **toit)
        return self.post(corps)

    def test_surface_sans_pose_bornee_en_pose_chiffree(self):
        # CORC5 — ni couverture ni pente : la borne suit la pose que la
        # composition CHIFFRE (toit plat lesté, fondateur 26/10/2026) ; la
        # latitude vient de la ville (gazetier) faute de GPS déclaré.
        rep = self._bornes()
        toit = rep['taille']['bornes']['toit']
        self.assertIsNotNone(toit['kwc'])
        self.assertIn('pose estimée « toit_plat_leste »', toit['source'])

    def test_pente_du_lead_sans_pose_panneaux_suivent_le_toit(self):
        # Critique Fable : la pente du LEAD (feuille privée ``_pente_toit``)
        # compte aussi — elle est recopiée quand la pose ESTIMÉE suit le toit.
        res = etude_ci._Resolution()
        res.poser('_pente_toit', 20, etude_ci._provenance('lead', 'client'))
        self.assertEqual(etude_ci._pose_estimee(res), 'toiture_inclinee')
        vide = etude_ci._Resolution()
        self.assertEqual(etude_ci._pose_estimee(vide), 'toit_plat_leste')

    def test_pente_declaree_sans_pose_panneaux_suivent_le_toit(self):
        rep = self._bornes(pente_deg=15)
        self.assertIn('pose estimée « toiture_inclinee »',
                      rep['taille']['bornes']['toit']['source'])
        self.assertNotIn('contenance_toit_inconnue', [a['code'] for a in rep['alertes']])

    def test_pose_declaree_inchangee(self):
        rep = self._bornes(type_pose='toit_plat_leste')
        toit = rep['taille']['bornes']['toit']
        self.assertNotIn('pose estimée', toit['source'])


# ── AMOT99 (D-ACI-18=a) — autoconsommation sur les 8 760 h de l'année type ──

def _serie_annee_type():
    """8 760 h kWh/kWc (heure GMT, 1er janvier 0 h) : un jour sur deux couvert
    (× 0,2) — exactement ce qu'une journée moyenne lisserait."""
    serie = []
    for jour in range(365):
        nuage = 1.0 if jour % 2 == 0 else 0.2
        serie.extend(round(0.9 * nuage * max(0.0, math.sin(math.pi * (h - 6) / 12)), 4)
                     for h in range(24))
    return {'kwh_kwc': serie, 'annees': [2014 + m % 10 for m in range(12)]}


SERIE = _serie_annee_type()


def _lecture_avec_serie(_site=None, toit=None):
    """``lire_production`` avec la série horaire (jamais le réseau)."""
    return (*_production_casablanca(), dict(SERIE, plan=plan_de_production(toit)))


def _autoconso_par_heure(jours_types, serie, kwc):
    """Σ_jours types (nb ÷ jours du mois) × Σ_jours réels Σ_h min(charge, kwc·prod)
    — la définition, à la main, sur les 8 760 h."""
    jours_du_mois = {}
    for jt in jours_types:
        jours_du_mois[jt['mois']] = jours_du_mois.get(jt['mois'], 0) + jt['nb_jours']
    debuts = [0]
    for jours in pp.JOURS_PAR_MOIS:
        debuts.append(debuts[-1] + 24 * jours)
    total = 0.0
    for jt in jours_types:
        m = jt['mois']
        heures = serie[debuts[m - 1]:debuts[m]]
        croise = sum(min(jt['charge_kwh'][i % 24], kwc * p) for i, p in enumerate(heures))
        total += croise * jt['nb_jours'] / jours_du_mois[m]
    return total


class Serie8760Amot99(_Base):
    SITE_GPS = {'ville': 'Casablanca', 'lat': 33.57, 'lon': -7.59}

    def setUp(self):
        super().setUp()
        self.production.side_effect = _lecture_avec_serie

    def _etude(self, **toit):
        corps = self.corps(site=dict(self.SITE_GPS), taille_explicite_kwc=100)
        corps['toit'] = dict({'type_pose': None, 'surface_utile_m2': None}, **toit)
        return self.post(corps)

    def test_bilan_somme_des_8760_heures_orientation_declaree_lue(self):
        data = self._etude(pente_deg=10, azimut_deg=-90)
        production, bilan = data['production'], data['bilan']
        self.assertEqual(production['methode_autoconso'], 'horaire_8760')
        self.assertEqual((production['inclinaison_deg'], production['azimut_deg']), (10, -90))
        toit = self.production.call_args.kwargs['toit']
        self.assertEqual((toit['pente_deg'], toit['azimut_deg']), (10, -90))
        # Pose non déclarée MAIS pente déclarée : CORC5 ⇒ les panneaux suivent
        # le toit (surimposition) ⇒ montage PVGIS « building ».
        self.assertEqual(plan_de_production(toit)['montage'], 'building')
        serie = production['serie_horaire']['kwh_kwc']
        self.assertEqual(len(serie), 8760)
        kwc = data['taille']['retenue_kwc']
        self.assertAlmostEqual(bilan['production_kwh'], sum(serie) * kwc, delta=1)
        self.assertAlmostEqual(bilan['autoconso_kwh'] + bilan['surplus_kwh'],
                               bilan['production_kwh'], delta=1)
        cellules = sum(h['nb_jours'] * (sum(h['autoconso_kwh']) + sum(h['surplus_kwh']))
                       for h in bilan['horaire'])
        self.assertAlmostEqual(cellules, bilan['production_kwh'], delta=bilan['production_kwh'] * 1e-3)
        jours_types = data['profil_charge']['jours_types']
        attendu = _autoconso_par_heure(jours_types, serie, kwc)
        self.assertAlmostEqual(bilan['autoconso_kwh'], attendu, delta=1)
        # Test-du-test : revenir à la journée moyenne donnerait un autre chiffre.
        moyennes = {j['mois']: j['production_kwh_kwc'] for j in production['jours_types']}
        journee_moyenne = sum(jt['nb_jours'] * sum(min(c, kwc * p) for c, p in zip(
            jt['charge_kwh'], moyennes[jt['mois']])) for jt in jours_types)
        self.assertGreater(abs(journee_moyenne - attendu), 0.01 * attendu)
        hyp = {h['cle']: h for h in data['hypotheses']}
        self.assertEqual(hyp['methode_autoconsommation']['valeur'], 'horaire_8760')
        self.assertEqual(hyp['inclinaison_deg']['source'], 'toit déclaré')
        self.assertNotIn('orientation_non_prise_en_compte', [a['code'] for a in data['alertes']])
        self.assertEqual(data['methode'], etude_ci.METHODE_8760)

    def test_sans_serie_horaire_repli_journees_moyennes_dit(self):
        self.production.side_effect = _production_casablanca
        data = self._etude(pente_deg=10, azimut_deg=-90)
        self.assertEqual(data['production']['methode_autoconso'], 'journees_moyennes')
        self.assertIsNone(data['production']['serie_horaire'])
        hyp = {h['cle']: h for h in data['hypotheses']}
        self.assertEqual(hyp['methode_autoconsommation']['valeur'], 'journees_moyennes')
        self.assertEqual(hyp['methode_autoconsommation']['statut'], 'estimation')
        self.assertIn('orientation_non_prise_en_compte', [a['code'] for a in data['alertes']])
        self.assertEqual(data['methode'], etude_ci.METHODE)

    def test_production_figee_dun_devis_envoye_rendu_inchange(self):
        # Règle « devis envoyés : nouveaux rendus seulement » : une production
        # figée AVANT la série (sans ses clés) garde ses journées moyennes.
        self.production.side_effect = _production_casablanca
        corps = self.corps(site=dict(self.SITE_GPS), taille_explicite_kwc=100)
        reference = etude_ci.etudier_ci(self.co, corps)
        figee = {k: v for k, v in reference['production'].items()
                 if k not in ('methode_autoconso', 'serie_horaire')}
        self.production.reset_mock()
        self.production.side_effect = _lecture_avec_serie
        rejeu = etude_ci.etudier_ci(self.co, corps, production_figee=figee)
        self.production.assert_not_called()
        self.assertEqual(rejeu['bilan'], reference['bilan'])
        self.assertEqual(rejeu['methode'], etude_ci.METHODE)


class AnneeTypePvgisAmot99(TestCase):
    """``pvgis_profils.serie_horaire_annee_type`` — le réseau est simulé."""

    @staticmethod
    def _reponse():
        import datetime
        heures = []
        for annee, watts in ((2014, 500.0), (2015, 1000.0), (2016, 600.0)):
            t = datetime.datetime(annee, 1, 1)
            while t.year == annee:
                heures.append({'time': t.strftime('%Y%m%d:%H10'), 'P': watts})
                t += datetime.timedelta(hours=1)
        return {'outputs': {'hourly': heures}}

    def test_mois_representatif_et_plan_declare_dans_lappel(self):
        with mock.patch.object(pp, '_cache_lire', return_value=None), \
                mock.patch.object(pp, '_cache_ecrire'), \
                mock.patch.object(pp, '_appel_pvgis', return_value=self._reponse()) as reseau:
            serie = pp.serie_horaire_annee_type(33.57, -7.59, angle_deg=10, aspect_deg=-90,
                                                montage='building')
        # Moyenne de chaque mois = 700 W : l'année la plus proche est 2016 (600 W),
        # son 29 février écarté — 8 760 h exactement.
        self.assertEqual(serie['annees'], [2016] * 12)
        self.assertEqual(len(serie['kwh_kwc']), 8760)
        self.assertEqual(set(serie['kwh_kwc']), {0.6})
        url = reseau.call_args.args[0]
        for attendu in ('/seriescalc?', 'pvcalculation=1', 'angle=10', 'aspect=-90',
                        'mountingplace=building', 'loss=14'):
            self.assertIn(attendu, url)
        self.assertEqual(reseau.call_args.kwargs['timeout'], pp.SERIE_TIMEOUT_S)

    def test_pvgis_injoignable_none(self):
        with mock.patch.object(pp, '_cache_lire', return_value=None), \
                mock.patch.object(pp, '_appel_pvgis', return_value=None):
            self.assertIsNone(pp.serie_horaire_annee_type(
                33.57, -7.59, angle_deg=30, aspect_deg=0, montage='free'))
        self.assertIsNone(pp.serie_horaire_annee_type(
            None, None, angle_deg=30, aspect_deg=0, montage='free'))


class SerieAuPointDeLaVilleCorc12(TestCase):
    """CORC12 (27/10/2026, constat CMP) — un lead sans GPS (ville seule) :
    la série horaire 8 760 h se calcule au point de sa ville au gazetier,
    jamais un repli silencieux sur les journées moyennes ; ville inconnue ⇒
    aucune position devinée."""

    def _lire(self, ville):
        from apps.parametres import pvgis_profils
        from apps.ventes import etude_horaire
        with mock.patch.object(etude_horaire, '_formes_production_par_saison',
                               return_value=({'ete': [1]}, 'test')), \
                mock.patch.object(pvgis_profils, 'productible_mensuel',
                                  return_value=([100] * 12, 'PVGIS test')), \
                mock.patch.object(pvgis_profils, 'serie_horaire_annee_type',
                                  return_value={'kwh_kwc': [0.1] * 8760}) as serie:
            lecture = etude_ci.lire_production({'ville': ville, 'lat': None, 'lon': None})
        return lecture, serie

    def test_ville_connue_serie_au_point_de_la_ville(self):
        from apps.parametres.villes_maroc import coordonnees_ville
        lecture, serie = self._lire('Casablanca')
        self.assertIsNotNone(lecture[3])
        lat, lon = serie.call_args.args[:2]
        self.assertEqual((lat, lon), tuple(coordonnees_ville('Casablanca'))[:2])

    def test_ville_inconnue_aucune_serie(self):
        lecture, serie = self._lire('Zorglubville')
        self.assertIsNone(lecture[3])
        serie.assert_not_called()


class PoseRasanteR1(_Base):
    """R1 (fondateur 28/10/2026) — l'orchestrateur sert les DEUX contenances
    d'un toit plat sans pente déclarée (même service de calepinage : 30°,
    puis pose rasante 10° jointive), lit la série PVGIS rasante au premier
    palier qui ne tient pas à 30° et sert le bloc production de l'inclinaison
    retenue ; une pente déclarée ou une production figée ne bascule jamais."""

    SITE_GPS = {'ville': 'Casablanca', 'lat': 33.57, 'lon': -7.59}

    def setUp(self):
        super().setUp()
        FicheTechnique.objects.filter(pmax_wc=Decimal('710')).update(
            longueur_mm=2384, largeur_mm=1303)
        self.production.side_effect = _lecture_avec_serie

    def _corps(self, **toit):
        corps = self.corps(site=dict(self.SITE_GPS))
        corps['toit'] = dict({'type_pose': 'toit_plat_leste', 'surface_utile_m2': 200}, **toit)
        return corps

    @staticmethod
    def _hyp(data, cle):
        return next((h for h in data['hypotheses'] if h['cle'] == cle), None)

    def test_a_boulangerie_lead_1637_pose_rasante_jamais_20(self):
        # 200 m² déclarés, toit plat lesté sans pente, 120 MWh/an, 6 h-22 h,
        # BT patenté. Avant R1 : 20,02 kWc par la seule borne 30° (21,3 kWc).
        corps = self._corps()
        corps['categorie_commerciale'] = 'boulangerie'
        corps['consommation'] = {'kwh_mensuels': [10000] * 12, 'kwh_annuel': None,
                                 'factures_mad': []}
        corps['rythme'] = dict(corps['rythme'], plages={'ouvre': [[6, 22]]},
                               jours_ouverts=[True] * 7, categorie_commerciale='boulangerie',
                               reponses_categorie={},
                               talon={'kw': None, 'part_pct': None, 'inconnu': True})
        data = self.post(corps)
        toit = data['taille']['bornes']['toit']
        self.assertAlmostEqual(toit['kwc_30'], 21.3, places=2)
        self.assertAlmostEqual(toit['kwc_10'], 35.5, places=2)
        self.assertEqual((toit['kwc'], toit['surface_m2']), (toit['kwc_10'], 200))
        self.assertIn('28/10/2026', toit['source_10'])
        self.assertGreater(data['taille']['retenue_kwc'], toit['kwc_30'])
        self.assertEqual(self._hyp(data, 'inclinaison_retenue_deg')['valeur'], 10)
        # Le bloc production servi est celui de la rasante (série au plan 10°).
        self.assertEqual(data['production']['inclinaison_deg'], 10)
        self.assertEqual(data['production']['inclinaison_source'], SOURCE_ANGLE_POSE_RASANTE)
        self.assertEqual(self._hyp(data, 'inclinaison_deg')['valeur'], 10)
        self.assertEqual(self._hyp(data, 'inclinaison_deg')['source'], SOURCE_ANGLE_POSE_RASANTE)
        # Deux lectures PVGIS : la série 30°, puis la rasante (marqueur, même pose).
        self.assertEqual(self.production.call_count, 2)
        toit_r = self.production.call_args.kwargs['toit']
        self.assertTrue(toit_r[CLE_POSE_RASANTE])
        self.assertEqual((toit_r['type_pose'], toit_r['pente_deg']), ('toit_plat_leste', None))
        # Même la rasante ne loge pas la taille économique : le devis le dit.
        self.assertEqual(data['taille']['raison_arret'], 'toit')
        self.assertEqual(self._hyp(data, 'taille_limitee_toit')['source'],
                         'taille limitée par le toit : 200 m² déclarés → 35.5 kWc en pose rasante')

    def test_b_taille_qui_tient_a_30_garde_30_et_sa_production(self):
        # Petite consommation : la taille économique tient à 30° → 30° gardé,
        # bloc production servi = la série 30° (le balayage a pu REGARDER des
        # paliers au-delà de 21,3 kWc — lus en rasante — sans les retenir).
        corps = self._corps()
        corps['consommation'] = {'kwh_mensuels': [1500] * 12, 'kwh_annuel': None,
                                 'factures_mad': []}
        data = self.post(corps)
        toit = data['taille']['bornes']['toit']
        self.assertLessEqual(data['taille']['retenue_kwc'], toit['kwc_30'])
        self.assertEqual(self._hyp(data, 'inclinaison_retenue_deg')['valeur'], 30)
        self.assertEqual(data['production']['inclinaison_deg'], 30)
        self.assertNotIn('inclinaison_source', data['production'])
        self.assertEqual(self.production.call_args_list[0].kwargs['toit'].get(CLE_POSE_RASANTE), None)
        self.assertIsNone(self._hyp(data, 'taille_limitee_toit'))

    def test_d_pente_declaree_aucune_bascule(self):
        data = self.post(self._corps(pente_deg=15))
        toit = data['taille']['bornes']['toit']
        self.assertNotIn('kwc_10', toit)
        self.assertIsNone(self._hyp(data, 'inclinaison_retenue_deg'))
        self.assertEqual(self.production.call_count, 1)
        self.assertEqual(data['production']['inclinaison_deg'], 15)

    def test_production_figee_jamais_rebasculee(self):
        # CIQ119 — le rafraîchisseur relit la production FIGÉE du devis en
        # « taille donnée » : aucune lecture PVGIS, aucune bascule, jamais
        # redimensionné.
        corps = self._corps()
        data = self.post(corps)
        self.production.reset_mock()
        etude = etude_ci.etudier_ci(
            self.co, dict(corps, taille_explicite_kwc=20),
            production_figee=data['production'], source_production_figee='PVGIS test')
        self.production.assert_not_called()
        self.assertEqual(etude['taille']['raison_arret'], 'taille_explicite')
        self.assertEqual(etude['production']['inclinaison_deg'], data['production']['inclinaison_deg'])
        self.assertEqual(etude['production']['kwh_kwc_mensuel'], data['production']['kwh_kwc_mensuel'])
