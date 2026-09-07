"""VREF (fondateur 07/09/2026) — villes : auto-correction + rattachement.

Verrouille : le résolveur trois-étages (« belksiri » → Mechraa Bel Ksiri par
contenance unique ; « Casablanka » → Casablanca par similarité sûre ; ambigu/
inconnu → texte INTACT, jamais deviné), l'auto-correction aux écritures
(formulaire/serializer, webhook, sync Odoo), l'endpoint « Vérifier la
ville » (statut pur sans réseau ; proches sur demande), le champ
``ville_reference`` et la commande de rattrapage.
"""
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from io import StringIO
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.crm.models import Lead, LeadActivity
from apps.crm.odoo_sync import _ville_odoo_corrigee
from apps.crm.webhooks import _ville_corrigee
from apps.parametres.villes_resolution import (
    corriger_ville, resoudre_ville, villes_proches)

User = get_user_model()


class ResolveurTests(TestCase):
    def test_raccourci_unique_belksiri(self):
        """LE cas fondateur : le client écrit « belksiri »."""
        r = resoudre_ville('belksiri')
        self.assertEqual(r['statut'], 'corrigee')
        self.assertEqual(r['ville'], 'Mechraa Bel Ksiri')

    def test_faute_de_frappe_sure(self):
        self.assertEqual(corriger_ville('Casablanka'), 'Casablanca')
        self.assertEqual(corriger_ville('Mohamedia'), 'Mohammedia')

    def test_variante_connue_et_exacte(self):
        self.assertEqual(resoudre_ville('Fes')['statut'], 'corrigee')
        self.assertEqual(resoudre_ville('Fès')['statut'], 'exacte')
        self.assertEqual(corriger_ville('Kenitra'), 'Kénitra')

    def test_inconnue_reste_intacte(self):
        self.assertEqual(resoudre_ville('douar bidon')['statut'], 'inconnue')
        self.assertEqual(corriger_ville('douar bidon'), 'douar bidon')
        # Trop court pour la contenance : jamais un pari sur « ain ».
        self.assertEqual(resoudre_ville('ain')['statut'], 'inconnue')

    def test_nom_entier_proche_prime_sur_l_alias_court(self):
        """Cas prod #1452 : « El Kelaâ des Sraghna » (GeoNames écrit
        « Srarhna ») partait sur l'alias court « el kelaa »… attribué à
        Kelaat Mgouna, à 300 km. La similarité PLEIN NOM prime."""
        r = resoudre_ville('El Kelaâ des Sraghna')
        self.assertEqual(r['statut'], 'corrigee')
        self.assertEqual(r['ville'], 'El Kelaa des Srarhna')

    def test_deux_villes_dans_le_texte_est_ambigu(self):
        """Cas prod #1489 : « Skoura Ouarzazate » nomme DEUX villes du
        gazetier — jamais la première par ordre alphabétique : l'écran
        carte tranche."""
        r = resoudre_ville('Skoura Ouarzazate')
        self.assertEqual(r['statut'], 'ambigue')
        self.assertIn('Skoura', r['candidats'])
        self.assertIn('Ouarzazate', r['candidats'])

    def test_un_prenom_dans_le_champ_ville_nest_jamais_corrige(self):
        """Relecture du dry-run prod (07/09) : à 0.85, « Said » partait sur
        Saidia et « mohamed » sur Mohammedia — des PRÉNOMS. À 0.90, plus
        aucun pari ; l'écran carte tranche."""
        self.assertNotEqual(resoudre_ville('Said')['statut'], 'corrigee')
        self.assertNotEqual(resoudre_ville('mohamed')['statut'], 'corrigee')
        self.assertNotEqual(resoudre_ville('Tanja')['statut'], 'corrigee')
        self.assertNotEqual(
            resoudre_ville('Salla jadida')['statut'], 'corrigee')

    def test_ville_dans_un_texte(self):
        self.assertEqual(corriger_ville('settat centre ville'), 'Settat')

    def test_sahara_du_supplement(self):
        self.assertEqual(corriger_ville('laayoune'), 'Laayoune')

    def test_villes_proches_triees_par_distance(self):
        proches = villes_proches(34.5619, -5.9541, n=3)
        self.assertEqual(proches[0]['ville'], 'Mechraa Bel Ksiri')
        self.assertLessEqual(proches[0]['distance_km'],
                             proches[1]['distance_km'])

    def test_helpers_webhook_et_odoo(self):
        self.assertEqual(_ville_corrigee('belksiri'), 'Mechraa Bel Ksiri')
        self.assertEqual(_ville_odoo_corrigee('belksiri'),
                         'Mechraa Bel Ksiri')
        self.assertIsNone(_ville_odoo_corrigee(''))
        self.assertEqual(_ville_odoo_corrigee('douar bidon'), 'douar bidon')


class _Base(TestCase):
    slug = 'vref'

    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug=self.slug, defaults={'nom': self.slug})
        self.user = User.objects.create_user(
            username=f'{self.slug}-u', password='x',
            role_legacy='responsable', company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')


class SerializerTests(_Base):
    slug = 'vref-ser'

    def test_patch_corrige_la_ville_en_canonique(self):
        lead = Lead.objects.create(
            company=self.company, nom='VREF', owner=self.user)
        resp = self.api.patch(
            f'/api/django/crm/leads/{lead.pk}/',
            {'ville': 'belksiri'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        lead.refresh_from_db()
        self.assertEqual(lead.ville, 'Mechraa Bel Ksiri')

    def test_patch_laisse_une_ville_inconnue_intacte(self):
        lead = Lead.objects.create(
            company=self.company, nom='VREF2', owner=self.user)
        self.api.patch(
            f'/api/django/crm/leads/{lead.pk}/',
            {'ville': 'douar bidon', 'ville_reference': 'Kénitra'},
            format='json')
        lead.refresh_from_db()
        self.assertEqual(lead.ville, 'douar bidon')
        self.assertEqual(lead.ville_reference, 'Kénitra')


class VilleStatutEndpointTests(_Base):
    slug = 'vref-api'

    URL = '/api/django/crm/leads/ville-statut/'

    def test_statut_pur_sans_proches(self):
        resp = self.api.post(self.URL, {'ville': 'belksiri'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['statut'], 'corrigee')
        self.assertEqual(resp.data['ville_canonique'], 'Mechraa Bel Ksiri')
        self.assertEqual(resp.data['proches'], [])
        self.assertIsNone(resp.data['position'])

    def test_proches_depuis_le_gps_fourni(self):
        """GPS fourni ⇒ aucune résolution réseau : les proches viennent du
        gazetier seul."""
        resp = self.api.post(
            self.URL,
            {'ville': 'douar bidon', 'proches': True,
             'gps_lat': 34.5619, 'gps_lng': -5.9541},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['statut'], 'inconnue')
        self.assertGreater(len(resp.data['proches']), 0)
        self.assertEqual(resp.data['proches'][0]['ville'],
                         'Mechraa Bel Ksiri')


class EffacerGpsTests(_Base):
    slug = 'vref-effacer'

    def _lead_avec_gps(self):
        return Lead.objects.create(
            company=self.company, nom='GPS', owner=self.user,
            gps_lat='33.5731', gps_lng='-7.5898')

    def test_sans_flag_la_garde_du_24_08_protege_toujours(self):
        lead = self._lead_avec_gps()
        self.api.patch(
            f'/api/django/crm/leads/{lead.pk}/',
            {'gps_lat': None, 'gps_lng': None}, format='json')
        lead.refresh_from_db()
        self.assertIsNotNone(lead.gps_lat)

    def test_avec_le_flag_l_humain_peut_effacer(self):
        """08/09/2026 (relevé fondateur) : on pouvait MODIFIER le GPS mais
        pas l'EFFACER — le geste explicite de l'écran passe désormais."""
        lead = self._lead_avec_gps()
        resp = self.api.patch(
            f'/api/django/crm/leads/{lead.pk}/',
            {'gps_lat': None, 'gps_lng': None, 'effacer_gps': True},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        lead.refresh_from_db()
        self.assertIsNone(lead.gps_lat)
        self.assertIsNone(lead.gps_lng)


class GpsHorsZoneTests(_Base):
    slug = 'vref-gps'

    URL = '/api/django/crm/leads/ville-statut/'

    def test_un_gps_hors_maroc_est_ignore_et_signale(self):
        """Incident 08/09 : un GPS de test en plein Atlantique (19.59/-30.61)
        rendait « Bir Ghandouz, 1 466 km » comme ville la plus proche. Hors
        de l'emprise Maroc+Sahara, le repère est IGNORÉ et signalé."""
        from unittest.mock import patch
        with patch('requests.get', side_effect=OSError('down')):
            resp = self.api.post(
                self.URL,
                {'ville': 'douar bidon', 'proches': True,
                 'gps_lat': 19.5883, 'gps_lng': -30.6114},
                format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(resp.data['gps_hors_zone'])
        self.assertIsNone(resp.data['position'])
        self.assertEqual(resp.data['proches'], [])

    def test_un_gps_marocain_reste_utilise(self):
        resp = self.api.post(
            self.URL,
            {'ville': 'douar bidon', 'proches': True,
             'gps_lat': 34.5619, 'gps_lng': -5.9541},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertFalse(resp.data['gps_hors_zone'])
        self.assertEqual(resp.data['proches'][0]['ville'],
                         'Mechraa Bel Ksiri')


class RattrapageVillesTests(_Base):
    slug = 'vref-cmd'

    def test_dry_run_puis_apply(self):
        casse = Lead.objects.create(
            company=self.company, nom='Casse', owner=self.user,
            ville='belksiri')
        inconnu = Lead.objects.create(
            company=self.company, nom='Inconnu', owner=self.user,
            ville='douar bidon')
        sortie = StringIO()
        call_command('corriger_villes_leads', stdout=sortie)
        self.assertIn('Dry-run', sortie.getvalue())
        casse.refresh_from_db()
        self.assertEqual(casse.ville, 'belksiri')

        call_command('corriger_villes_leads', '--apply', stdout=StringIO())
        casse.refresh_from_db()
        inconnu.refresh_from_db()
        self.assertEqual(casse.ville, 'Mechraa Bel Ksiri')
        self.assertEqual(inconnu.ville, 'douar bidon')
        self.assertTrue(LeadActivity.objects.filter(
            lead=casse, body__contains='Ville corrigée automatiquement',
        ).exists())
