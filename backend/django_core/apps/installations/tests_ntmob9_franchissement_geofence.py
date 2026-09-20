"""
NTMOB9 — Check-in/out géofencé sur chantier (sur les modèles GPS EXISTANTS).

Garde WIR113 (``docs/module-map.md``) : le consentement vit dans
``GpsConsentRecord``, la position dans ``PositionTechnicien``, le franchissement
dans ``GeofenceAlert`` — NTMOB9 n'ajoute donc qu'un ``type_franchissement``
(``entree``/``sortie``), JAMAIS une deuxième table de pointage.

Couvre :
  * CRITÈRE D'ACCEPTATION : franchir le rayon du chantier vers l'intérieur, avec
    un consentement actif, crée un point d'ENTRÉE sans aucune action de
    l'utilisateur ;
  * refuser/ne pas avoir de consentement ⇒ 403 sur le ping : il ne reste que la
    saisie manuelle (aucun point automatique, aucun tracking silencieux) ;
  * non-régression XFSM23 : un ping hors rayon reste une ``sortie``, un ping
    isolé à l'intérieur ne journalise rien ;
  * pas de spam : deux pings consécutifs à l'intérieur ne créent qu'UNE entrée ;
  * un aller-retour journalise entrée puis sortie, dans l'ordre ;
  * historique de présence : lecture filtrable par chantier et par type,
    scopée société.

Run :
    python manage.py test apps.installations.tests_ntmob9_franchissement_geofence -v2
"""
import itertools
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client, Lead
from apps.installations import gps_tracking_service
from apps.installations.models import GeofenceAlert, Intervention
from apps.installations.services import create_installation_from_devis
from apps.installations.tasks import casablanca_today
from apps.ventes.models import Devis

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations'

#: Coordonnées du chantier de test et deux points : un DEDANS (quelques
#: mètres) et un DEHORS (~5 km au nord, bien au-delà du rayon 0,5 km).
SITE_LAT, SITE_LNG = '33.573110', '-7.589843'
DEDANS = {'lat': '33.573150', 'lng': '-7.589800'}
DEHORS = {'lat': '33.62', 'lng': '-7.589843'}


def make_company(slug=None):
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'ntmob9-co-{n}', defaults={'nom': f'NTMOB9 Co {n}'})
    return company


def make_user(company, role='responsable'):
    return User.objects.create_user(
        username=f'ntmob9-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_chantier(company, user):
    n = next(_seq)
    client = Client.objects.create(
        company=company, nom='Site', prenom='Client',
        email=f'ntmob9-{company.id}-{n}@example.invalid')
    lead = Lead.objects.create(
        company=company, nom='Site', prenom='Client', stage='SIGNED',
        type_installation='residentiel')
    devis = Devis.objects.create(
        company=company, reference=f'DEV-NTMOB9-{company.id}-{n}',
        client=client, lead=lead, statut=Devis.Statut.ACCEPTE,
        taux_tva=Decimal('20'), mode_installation='residentiel')
    inst, _ = create_installation_from_devis(devis, user, company)
    inst.gps_lat = Decimal(SITE_LAT)
    inst.gps_lng = Decimal(SITE_LNG)
    inst.save(update_fields=['gps_lat', 'gps_lng'])
    return inst


def make_intervention(company, user, technicien):
    return Intervention.objects.create(
        company=company, installation=make_chantier(company, user),
        type_intervention='pose', created_by=user, technicien=technicien,
        statut=Intervention.Statut.SUR_SITE,
        date_prevue=casablanca_today())


class FranchissementEntreeTests(TestCase):
    """Le point d'entrée se pose tout seul au franchissement du rayon."""

    def setUp(self):
        self.company = make_company()
        self.responsable = make_user(self.company)
        self.technicien = make_user(self.company, role='normal')
        gps_tracking_service.record_consent(self.company, self.technicien)
        self.interv = make_intervention(
            self.company, self.responsable, self.technicien)
        self.api = auth(self.technicien)

    def _ping(self, point):
        return self.api.post(
            f'{BASE}/positions-techniciens/ping/',
            dict(point, intervention=self.interv.id), format='json')

    def test_entrer_dans_le_rayon_cree_un_point_dentree_sans_action(self):
        """CRITÈRE D'ACCEPTATION NTMOB9."""
        # Le technicien est en route, loin du site.
        self.assertEqual(self._ping(DEHORS).status_code, 201)
        # Il arrive : le seul geste est le ping périodique de `watchPosition`.
        resp = self._ping(DEDANS)

        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertFalse(resp.data['hors_perimetre'])
        self.assertIsNotNone(resp.data['geofence_alert'])
        self.assertEqual(
            resp.data['geofence_alert']['type_franchissement'], 'entree')
        entrees = GeofenceAlert.objects.filter(
            intervention=self.interv,
            type_franchissement=GeofenceAlert.TypeFranchissement.ENTREE)
        self.assertEqual(entrees.count(), 1)
        self.assertEqual(entrees.first().technicien, self.technicien)

    def test_deux_pings_dedans_ne_creent_quune_entree(self):
        self._ping(DEHORS)
        self._ping(DEDANS)
        self._ping(DEDANS)

        self.assertEqual(
            GeofenceAlert.objects.filter(
                intervention=self.interv,
                type_franchissement=GeofenceAlert.TypeFranchissement.ENTREE
            ).count(),
            1)

    def test_ping_isole_dedans_ne_journalise_rien(self):
        """Non-régression XFSM23 : sans position précédente évaluée, un ping à
        l'intérieur n'est pas un franchissement."""
        resp = self._ping(DEDANS)

        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertIsNone(resp.data['geofence_alert'])
        self.assertFalse(
            GeofenceAlert.objects.filter(intervention=self.interv).exists())

    def test_aller_retour_journalise_entree_puis_sortie(self):
        self._ping(DEHORS)
        self._ping(DEDANS)
        self._ping(DEHORS)

        types = list(
            GeofenceAlert.objects
            .filter(intervention=self.interv)
            .order_by('created_at', 'id')
            .values_list('type_franchissement', flat=True))
        self.assertEqual(types, ['sortie', 'entree', 'sortie'])

    def test_sortie_reste_le_defaut_du_journal(self):
        """Non-régression XFSM23 : un dépassement reste typé ``sortie``."""
        resp = self._ping(DEHORS)

        self.assertTrue(resp.data['hors_perimetre'])
        self.assertEqual(
            resp.data['geofence_alert']['type_franchissement'], 'sortie')

    def test_sans_consentement_aucun_point_automatique(self):
        """Refuser le consentement ⇒ il ne reste que la saisie manuelle."""
        autre_tech = make_user(self.company, role='normal')
        api = auth(autre_tech)

        resp = api.post(
            f'{BASE}/positions-techniciens/ping/',
            dict(DEDANS, intervention=self.interv.id), format='json')

        self.assertEqual(resp.status_code, 403, resp.content)
        self.assertFalse(
            GeofenceAlert.objects.filter(technicien=autre_tech).exists())


class HistoriquePresenceTests(TestCase):
    """Lecture « historique de présence » par chantier, pour le responsable."""

    def setUp(self):
        self.company = make_company()
        self.responsable = make_user(self.company)
        self.technicien = make_user(self.company, role='normal')
        gps_tracking_service.record_consent(self.company, self.technicien)
        self.interv = make_intervention(
            self.company, self.responsable, self.technicien)
        # Un aller-retour complet : une sortie, une entrée, une sortie.
        for point in (DEHORS, DEDANS, DEHORS):
            gps_tracking_service.enregistrer_position(
                self.company, self.technicien,
                float(point['lat']), float(point['lng']),
                intervention=self.interv)

    def test_selecteur_filtre_par_chantier_et_par_type(self):
        entrees = gps_tracking_service.franchissements_geofence(
            self.company, chantier=self.interv.installation,
            type_franchissement=GeofenceAlert.TypeFranchissement.ENTREE)
        toutes = gps_tracking_service.franchissements_geofence(
            self.company, chantier=self.interv.installation)

        self.assertEqual(entrees.count(), 1)
        self.assertEqual(toutes.count(), 3)

    def test_api_filtre_par_type_franchissement(self):
        api = auth(self.responsable)

        resp = api.get(f'{BASE}/geofence-alertes/?type_franchissement=entree')

        self.assertEqual(resp.status_code, 200, resp.content)
        results = resp.data.get(
            'results', resp.data if isinstance(resp.data, list) else [])
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['type_franchissement'], 'entree')
        self.assertEqual(results[0]['type_franchissement_display'], 'Entrée')

    def test_selecteur_scope_societe(self):
        autre = make_company()

        self.assertEqual(
            gps_tracking_service.franchissements_geofence(autre).count(), 0)
