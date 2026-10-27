# -*- coding: utf-8 -*-
"""L-QA1 (24/08/2026) FIX1 — POST /ventes/etude-horaire/preview/ avec un
``lead`` (aucun devis persisté, écran GÉNÉRATEUR).

Preuve de bug live (audit navigateur 24/08/2026) : la même requête sans
``lead`` répondait ``profil.occupation: null`` et
``profil.equipements_actifs: []`` alors que le lead lié portait un script
d'appel complet (occupation_jour='present', VE/clim/piscine/chauffe-eau
renseignés) — le commercial ne voyait donc jamais l'effet réel de ces
réponses avant l'enregistrement du devis. Ce module épingle le correctif :
``lead`` résout le MÊME profil que le chemin ``devis`` (mêmes sélecteurs
CRM), scopé société, avec ``devis`` toujours prioritaire quand les deux sont
fournis.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.ventes.tests.test_l_qa1_etude_horaire_preview_lead"
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client, Lead
from apps.ventes.models import Devis

User = get_user_model()


class _LeadPreviewBase(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='lqa1-co', defaults={'nom': 'L-QA1 Co'})
        self.other_company, _ = Company.objects.get_or_create(
            slug='lqa1-other', defaults={'nom': 'L-QA1 Other'})
        self.user = User.objects.create_user(
            username='lqa1_user', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def _lead_complet(self, *, company=None, ville='Casablanca'):
        return Lead.objects.create(
            company=company or self.company, nom='Lead', prenom='Complet',
            telephone='+212600000090', ville=ville,
            facture_hiver=Decimal('1800'), ete_differente=False,
            occupation_jour='present',
            equip_voiture_electrique=True, equip_ve_chargeur_kw=7.4,
            equip_ve_creneau='nuit', equip_ve_km_semaine=150,
            equip_clim=True, equip_clim_kw=5, equip_clim_pieces=3,
            equip_piscine=True, equip_piscine_pompe_kw=1.1,
            equip_piscine_heures_jour=6,
            equip_chauffe_eau_electrique=True, equip_chauffe_eau_kw=2.4,
            equip_chauffe_eau_creneau='soir')


class PreviewAvecLeadTests(_LeadPreviewBase):
    def test_lead_seul_pose_occupation_et_equipements_actifs(self):
        """LE BUG LIVE : sans ce correctif, occupation=None et
        equipements_actifs=[] même avec un script d'appel complet."""
        lead = self._lead_complet()
        resp = self.api.post('/api/django/ventes/etude-horaire/preview/', {
            'mode_installation': 'residentiel', 'lead': lead.id,
            'dimensionner': False,
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        profil = resp.data['profil']
        self.assertEqual(profil['occupation'], 'presence_jour')
        self.assertEqual(
            set(profil['equipements_actifs']),
            {'ve', 'clim', 'piscine', 'chauffe_eau'})

    def test_lead_residentiel_sans_reponse_occupation_prend_le_defaut_presence(self):
        """Lead 1635 (23/10/2026) — l'écran générateur envoie ``lead`` SANS
        ``mode_installation`` et le lead n'a pas répondu à « présence en
        journée » : le profil retombait sur le défaut NON résidentiel
        ``absence_jour`` (8 panneaux / 5,68 kWc recommandés) pendant que le
        devis automatique du même lead (``occupation_du_lead``, D4) tournait
        en ``presence_jour`` (24 panneaux / 17,04 kWc). Le corps EXACT de
        l'écran, sans la clé que les autres tests de ce module ajoutent."""
        from apps.ventes.courbes_journalieres import occupation_du_lead
        lead = Lead.objects.create(
            company=self.company, nom='Oulkadi', prenom='Sans réponse',
            telephone='+212600000091', ville='Casablanca',
            type_installation='residentiel',
            facture_hiver=Decimal('6000'), ete_differente=False,
            occupation_jour=None)
        resp = self.api.post('/api/django/ventes/etude-horaire/preview/', {
            'lead': lead.id, 'dimensionner': False,
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data['profil']['occupation'], 'presence_jour')
        # Parité avec le chemin devis automatique : UNE occupation par lead.
        self.assertEqual(resp.data['profil']['occupation'],
                         occupation_du_lead(lead)[0])
        # Décision fondateur du 23/10/2026 : la présence en journée est le
        # défaut PARTOUT — un lead non résidentiel sans réponse ni profil
        # d'activité la reçoit aussi (plus de repli ``absence_jour``).
        lead.type_installation = 'commercial'
        lead.save(update_fields=['type_installation'])
        resp = self.api.post('/api/django/ventes/etude-horaire/preview/', {
            'lead': lead.id, 'dimensionner': False,
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data['profil']['occupation'], 'presence_jour')

    def test_lead_seul_ancre_la_consommation_sans_facture_dans_le_corps(self):
        """Le lead porte sa PROPRE facture d'hiver : aucune facture à
        retaper dans le corps de la requête pour ancrer un calcul."""
        lead = self._lead_complet()
        resp = self.api.post('/api/django/ventes/etude-horaire/preview/', {
            'mode_installation': 'residentiel', 'lead': lead.id,
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data['consommation']['source'], 'facture_hiver')
        self.assertTrue(any(v > 0 for v in resp.data['consommation']['kwh_mensuels']))

    def test_estimation_conso_presente_avec_equipements_actifs(self):
        """T4/L-QA1 — la décomposition mensuelle apparaît dès qu'au moins une
        couche équipement est active, absente du payload avant ce correctif."""
        lead = self._lead_complet()
        resp = self.api.post('/api/django/ventes/etude-horaire/preview/', {
            'mode_installation': 'residentiel', 'lead': lead.id,
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        estimation = resp.data.get('estimation_conso')
        self.assertIsNotNone(estimation)
        self.assertEqual(len(estimation['base_mensuelle']), 12)
        self.assertEqual(len(estimation['totale_mensuelle']), 12)
        self.assertTrue(estimation['ajouts'])

    def test_devis_prime_toujours_sur_un_lead_fourni_en_meme_temps(self):
        """Un devis existant reste la source de vérité — même chaîne que le
        serveur pour la résolution `devis` avant `lead`."""
        lead_devis = self._lead_complet(ville='Rabat')
        lead_devis.occupation_jour = 'absent'
        lead_devis.equip_clim = False
        lead_devis.save()
        client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='Devis')
        devis = Devis.objects.create(
            company=self.company, reference='DEV-LQA1-01',
            client=client_obj, lead=lead_devis, statut='brouillon',
            taux_tva=Decimal('20'), mode_installation='residentiel')
        lead_autre = self._lead_complet(ville='Casablanca')

        resp = self.api.post('/api/django/ventes/etude-horaire/preview/', {
            'mode_installation': 'residentiel',
            'devis': devis.id, 'lead': lead_autre.id,
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        # Le profil lu est celui du devis (absent, aucun équipement actif),
        # jamais celui du lead fourni en plus.
        self.assertEqual(resp.data['profil']['occupation'], 'absence_jour')

    def test_lead_dune_autre_societe_est_ignore_et_averti(self):
        """IDOR : un id de lead d'une autre société ne doit jamais faire
        fuiter son profil — repli sur le corps brut, avec avertissement."""
        lead_etranger = self._lead_complet(company=self.other_company)
        resp = self.api.post('/api/django/ventes/etude-horaire/preview/', {
            'mode_installation': 'residentiel', 'lead': lead_etranger.id,
            'facture_hiver': 1000,
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertIsNone(resp.data['profil']['occupation'])
        self.assertTrue(any(
            'introuvable' in a.lower() for a in resp.data['avertissements']))

    def test_sans_lead_ni_devis_comportement_byte_identique_au_corps_brut(self):
        """Non-régression : le chemin historique (corps brut) est inchangé."""
        resp = self.api.post('/api/django/ventes/etude-horaire/preview/', {
            'mode_installation': 'residentiel', 'facture_hiver': 1200,
            'occupation': 'presence_jour',
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data['profil']['occupation'], 'presence_jour')
        self.assertEqual(resp.data['profil']['equipements_actifs'], [])
        self.assertIsNone(resp.data['estimation_conso'])

    def test_grandeurs_hors_bornes_400_jamais_500(self):
        """CI #997 fuzz (24/10) : toute grandeur est publiée dans ±1e9 (latitude
        ±90, longitude ±180) et appliquée par le serveur — ``-2.6e16`` kWh ou
        ``1.9e-163`` kWh de batterie débordaient le calcul en 500 (page HTML)."""
        url = '/api/django/ventes/etude-horaire/preview/'
        for corps in ({'kwc': 1e12}, {'batterie_kwh': -1e300},
                      {'lat': 91, 'lon': 0}, {'lon': -181},
                      {'facture_hiver': 1e10},
                      {'conso_kwh_mensuelles': [-2.6e16] * 12},
                      {'factures_mensuelles': [1e10] * 12}):
            with self.subTest(corps=corps):
                resp = self.api.post(url, corps, format='json')
                self.assertEqual(resp.status_code, 400, resp.content)


# ENF1b — POST /ventes/etude-horaire/preview/ : `equipements` non-objet.
# api-fuzz du 09/10/2026 : le corps multipart `equipements={}` (une CHAÎNE) faisait planter
# `composer_equipements` (`'str' object has no attribute 'get'`) → 500. Un corps inexploitable répond
# 400 ; un objet reste accepté.
URL = '/api/django/ventes/etude-horaire/preview/'


# Corps EXACT du cas 0IhAeU du run 37897343514.
CORPS_FUZZ = {
    'devis': '0', 'lead': '0', 'ville': '0', 'lat': '0', 'lon': '0',
    'facture_hiver': '0', 'facture_ete': '0', 'ete_differente': 'False',
    'occupation': 'presence_jour', 'equipements': '{}', 'raccordement': '0',
    'kwc': '0', 'batterie_kwh': '0', 'dimensionner': 'False', 'critere': '',
}


class EtudeHoraireEquipementsTests(TestCase):
    def setUp(self):
        co = Company.objects.create(nom='ENF1b EH', slug='enf1b-eh')
        user = User.objects.create_user(
            username='enf1b_eh', password='x', role_legacy='responsable',
            company=co)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')

    def test_equipements_chaine_multipart_415(self):
        # CI #997 (D2) — la vue est JSON seul : le formulaire, où
        # ``equipements`` voyage en chaîne, reçoit 415 (plus 400).
        response = self.api.post(URL, CORPS_FUZZ, format='multipart')
        self.assertEqual(response.status_code, 415, response.content)

    def test_equipements_chaine_json_400(self):
        response = self.api.post(URL, {'equipements': 'piscine'},
                                 format='json')
        self.assertEqual(response.status_code, 400, response.content)

    def test_equipements_objet_accepte(self):
        response = self.api.post(
            URL, {'facture_hiver': 900, 'equipements': {'piscine': True}},
            format='json')
        self.assertEqual(response.status_code, 200, response.content)

    def test_drapeau_non_booleen_400(self):
        """CI #997 api-fuzz (cas fkaboo) : ``dimensionner: {}`` était lu par
        sa « vérité » Python → 200. Un drapeau publié ``boolean`` n'accepte
        qu'un vrai booléen JSON."""
        corps_fuzz = {
            'devis': 0, 'lead': 0, 'ville': '0', 'lat': 0, 'lon': 0,
            'facture_hiver': 0, 'facture_ete': 0, 'ete_differente': False,
            'factures_mensuelles': [], 'conso_kwh_mensuelles': [],
            'occupation': 'presence_jour', 'equipements': {},
            'raccordement': '0', 'kwc': 0, 'batterie_kwh': 0,
            'dimensionner': {}, 'critere': '0'}
        response = self.api.post(URL, corps_fuzz, format='json')
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn('dimensionner', response.json()['detail'])
        for nom, brut in (('dimensionner', 1), ('dimensionner', 'true'),
                          ('dimensionner', None), ('ete_differente', 0),
                          ('ete_differente', [])):
            with self.subTest(nom=nom, brut=brut):
                response = self.api.post(
                    URL, {'facture_hiver': 900, nom: brut}, format='json')
                self.assertEqual(response.status_code, 400, response.content)
                self.assertIn(nom, response.json()['detail'])

    def test_champs_scalaires_forme_publiee(self):
        """CI #997 (2) (cas EpXQ7i) — ``critere: "\\f"`` passait (200) comme
        ``lat: "0"`` ou ``devis: null`` : un champ PRÉSENT suit sa forme
        publiée (400 nommé) ; une occupation hors liste reste ignorée.
        CI #997 (3) (O3EAyQ) — un nul dans ville/raccordement sort du motif."""
        for nom, brut in (('critere', '\f'), ('critere', 'x'),
                          ('ville', ' '), ('ville', '\u001c'),
                          ('ville', 'a\u0000'), ('raccordement', 'm\u0000o'),
                          ('raccordement', 0), ('lat', '0'), ('kwc', True),
                          ('devis', None), ('lead', 1.5), ('occupation', 5),
                          ('equipements', '')):
            response = self.api.post(
                URL, {'facture_hiver': 900, nom: brut}, format='json')
            self.assertEqual(response.status_code, 400, (nom, brut))
            self.assertIn(nom, response.json()['detail'])
        response = self.api.post(
            URL, {'facture_hiver': 900, 'critere': 'economie_max',
                  'occupation': 'inconnue'}, format='json')
        self.assertEqual(response.status_code, 200, response.content)

    def test_drapeau_booleen_accepte(self):
        response = self.api.post(
            URL, {'facture_hiver': 900, 'dimensionner': False,
                  'ete_differente': False}, format='json')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertIsNone(response.data['dimensionnement'])
        # CI #997 (D2) — JSON seul : un formulaire reçoit 415.
        response = self.api.post(
            URL, {'facture_hiver': '900', 'dimensionner': 'false'},
            format='multipart')
        self.assertEqual(response.status_code, 415, response.content)

    def test_serie_12_nombres_sinon_400(self):
        """CI #997 api-fuzz (cas CnCcjq) : ``conso_kwh_mensuelles=True`` en
        formulaire répondait 200. Les deux séries publiées « 12 nombres ou
        null » refusent toute autre forme en 400 nommant le champ."""
        for nom in ('conso_kwh_mensuelles', 'factures_mensuelles'):
            for brut in (True, 'abc', [1] * 11, [True] * 12, ['1'] * 12, {}):
                with self.subTest(nom=nom, brut=brut):
                    response = self.api.post(
                        URL, {'facture_hiver': 900, nom: brut}, format='json')
                    self.assertEqual(response.status_code, 400,
                                     response.content)
                    self.assertIn(nom, response.json()['detail'])
        response = self.api.post(
            URL, {'conso_kwh_mensuelles': [400] * 12,
                  'factures_mensuelles': None}, format='json')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.data['consommation']['source'],
                         'kwh_mensuels_saisis')
        # CI #997 (D2) — JSON seul : le formulaire reçoit 415.
        response = self.api.post(
            URL, {'conso_kwh_mensuelles': ['400'] * 12}, format='multipart')
        self.assertEqual(response.status_code, 415, response.content)


class PreviewBatteriesDuCorpsTests(_LeadPreviewBase):
    """RHOR9 — sans devis enregistré, les lignes « avec » batterie envoyées
    par l'écran (``batteries``) sont lues sur leurs fiches (capacité utile,
    puissances, rendement), comme le bloc d'un devis ; un produit d'une autre
    société est ignoré ; sans le champ, la capacité du corps (inchangé)."""

    def _batterie(self, company, sku):
        from apps.stock.models import Produit
        return Produit.objects.create(
            company=company, nom='Batterie Dyness 5 kWh', sku=sku,
            prix_vente=Decimal('11666.67'), prix_achat=Decimal('8000'),
            quantite_stock=10)

    def _apercu(self, **extra):
        corps = {'mode_installation': 'residentiel', 'facture_hiver': 1500,
                 'occupation': 'presence_jour', 'ville': 'Casablanca',
                 'kwc': 6.0, 'batterie_kwh': 12.0}
        corps.update(extra)
        resp = self.api.post('/api/django/ventes/etude-horaire/preview/',
                             corps, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertIsNotNone(resp.data['etude'])
        return resp.data['etude']

    def test_rhor9_capacite_lue_sur_les_lignes_de_l_ecran(self):
        produit = self._batterie(self.company, 'RHOR9-BAT')
        etude = self._apercu(
            batteries=[{'produit': produit.pk, 'quantite': 2}])
        self.assertAlmostEqual(etude['batterie_kwh_utile'], 10.0, places=2)

    def test_rhor9_produit_d_une_autre_societe_ignore(self):
        etranger = self._batterie(self.other_company, 'RHOR9-BAT-X')
        etude = self._apercu(
            batteries=[{'produit': etranger.pk, 'quantite': 2}])
        self.assertAlmostEqual(etude['batterie_kwh_utile'], 12.0, places=2)

    def test_rhor9_sans_le_champ_comportement_d_avant(self):
        self.assertAlmostEqual(
            self._apercu()['batterie_kwh_utile'], 12.0, places=2)

    def test_rhor9_batteries_hors_forme_400(self):
        resp = self.api.post('/api/django/ventes/etude-horaire/preview/', {
            'mode_installation': 'residentiel', 'facture_hiver': 1500,
            'batteries': 'Dyness'}, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)
