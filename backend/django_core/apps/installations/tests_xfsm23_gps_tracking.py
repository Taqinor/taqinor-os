"""
XFSM23 — Géolocalisation temps réel + géofencing techniciens (ENFORCED).

Couvre (décision fondateur : consentement DÉJÀ obtenu, tracking OBLIGATOIRE
pendant une intervention active — pas un opt-in que le technicien débranche) :

  * le consentement est enregistré durablement (une trace, idempotent) ;
  * ``gps_tracking_required`` reste vrai tant que le statut F3 est dans la
    plage active (Prête/En route/Sur site) et ne peut PAS être désactivé par
    le technicien (aucun endpoint client ne le pose) ;
  * une alerte géofence se déclenche quand la position live sort du rayon
    attendu du chantier pendant une intervention active ;
  * l'isolation société (une société ne voit jamais les positions/alertes
    d'une autre) ;
  * la purge respecte la fenêtre de rétention (positions anciennes supprimées,
    récentes conservées).

Run :
    python manage.py test apps.installations.tests_xfsm23_gps_tracking -v2
"""
import itertools
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client, Lead
from apps.ventes.models import Devis
from apps.installations import gps_tracking_service
from apps.installations.models import (
    GeofenceAlert, GpsConsentRecord, Intervention, PositionTechnicien,
)
from apps.installations.services import create_installation_from_devis

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations'


def make_company(slug=None, nom=None):
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'xfsm23-co-{n}', defaults={'nom': nom or f'XFSM23 Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_user(company, role='responsable', username=None):
    return User.objects.create_user(
        username=username or f'xfsm23-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def make_chantier(company, user, gps_lat='33.573110', gps_lng='-7.589843'):
    n = next(_seq)
    client = Client.objects.create(
        company=company, nom='Site', prenom='Client',
        email=f'xfsm23-{company.id}-{n}@example.invalid')
    lead = Lead.objects.create(
        company=company, nom='Site', prenom='Client', stage='SIGNED',
        type_installation='residentiel')
    devis = Devis.objects.create(
        company=company, reference=f'DEV-XFSM23-{company.id}-{n}', client=client,
        lead=lead, statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20'),
        mode_installation='residentiel')
    inst, _ = create_installation_from_devis(devis, user, company)
    inst.gps_lat = Decimal(gps_lat)
    inst.gps_lng = Decimal(gps_lng)
    inst.save(update_fields=['gps_lat', 'gps_lng'])
    return inst


def make_intervention(company, user, technicien, statut=Intervention.Statut.A_PREPARER):
    inst = make_chantier(company, user)
    return Intervention.objects.create(
        company=company, installation=inst, type_intervention='pose',
        created_by=user, technicien=technicien, statut=statut,
        date_prevue=date.today())


class TestGpsConsent(TestCase):
    def setUp(self):
        self.company = make_company()
        self.responsable = make_user(self.company, role='responsable')
        self.technicien = make_user(self.company, role='normal')
        self.api = auth(self.responsable)

    def test_record_consent_creates_durable_record(self):
        record = gps_tracking_service.record_consent(
            self.company, self.technicien, consent_ref='RH-2026-001',
            recorded_by=self.responsable)
        self.assertTrue(record.is_active)
        self.assertEqual(record.consent_ref, 'RH-2026-001')
        self.assertTrue(
            gps_tracking_service.has_active_consent(
                self.company, self.technicien))

    def test_record_consent_idempotent_no_duplicate(self):
        gps_tracking_service.record_consent(self.company, self.technicien)
        gps_tracking_service.record_consent(self.company, self.technicien)
        self.assertEqual(
            GpsConsentRecord.objects.filter(
                company=self.company, technicien=self.technicien).count(), 1)

    def test_revoke_consent_via_service(self):
        gps_tracking_service.record_consent(self.company, self.technicien)
        nb = gps_tracking_service.revoke_consent(
            self.company, self.technicien, reason='Fin de contrat')
        self.assertEqual(nb, 1)
        self.assertFalse(
            gps_tracking_service.has_active_consent(
                self.company, self.technicien))

    def test_ping_without_consent_is_refused(self):
        """Un technicien SANS consentement enregistré est refusé (403) —
        aucun ping GPS n'est accepté avant que le consentement existe."""
        api = auth(self.technicien)
        resp = api.post(
            f'{BASE}/positions-techniciens/ping/',
            {'lat': '33.5', 'lng': '-7.6'}, format='json')
        self.assertEqual(resp.status_code, 403, resp.content)

    def test_technicien_cannot_revoke_own_consent(self):
        """Seul un rôle responsable/admin peut révoquer — le technicien
        lui-même n'a pas la permission d'écriture sur ce viewset."""
        gps_tracking_service.record_consent(self.company, self.technicien)
        api = auth(self.technicien)
        record = GpsConsentRecord.objects.get(
            company=self.company, technicien=self.technicien)
        resp = api.post(
            f'{BASE}/gps-consentements/{record.id}/revoquer/', {}, format='json')
        self.assertEqual(resp.status_code, 403, resp.content)


class TestGpsTrackingRequired(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.technicien = make_user(self.company, role='normal')
        gps_tracking_service.record_consent(self.company, self.technicien)

    def test_tracking_not_required_before_preparation(self):
        interv = make_intervention(
            self.company, self.user, self.technicien,
            statut=Intervention.Statut.A_PREPARER)
        self.assertFalse(interv.gps_tracking_required)

    def test_tracking_required_when_prete(self):
        interv = make_intervention(
            self.company, self.user, self.technicien,
            statut=Intervention.Statut.PRETE)
        self.assertTrue(interv.gps_tracking_required)

    def test_tracking_required_when_en_route(self):
        interv = make_intervention(
            self.company, self.user, self.technicien,
            statut=Intervention.Statut.EN_ROUTE)
        self.assertTrue(interv.gps_tracking_required)

    def test_tracking_required_when_sur_site(self):
        interv = make_intervention(
            self.company, self.user, self.technicien,
            statut=Intervention.Statut.SUR_SITE)
        self.assertTrue(interv.gps_tracking_required)

    def test_tracking_not_required_once_terminee(self):
        interv = make_intervention(
            self.company, self.user, self.technicien,
            statut=Intervention.Statut.TERMINEE)
        self.assertFalse(interv.gps_tracking_required)

    def test_tracking_not_required_when_annulee(self):
        interv = make_intervention(
            self.company, self.user, self.technicien,
            statut=Intervention.Statut.SUR_SITE)
        interv.annulee = True
        interv.save(update_fields=['annulee'])
        self.assertFalse(interv.gps_tracking_required)

    def test_client_cannot_disable_tracking_via_api_patch(self):
        """``gps_tracking_required`` n'est PAS une colonne stockée — c'est une
        @property calculée sur le statut F3. Un PATCH tentant de la poser via
        l'API n'a AUCUN effet (le serializer l'ignore, aucun champ de ce nom
        n'existe sur le modèle) : la propriété reste dérivée du statut
        courant, jamais d'une valeur envoyée par le client mobile."""
        interv = make_intervention(
            self.company, self.user, self.technicien,
            statut=Intervention.Statut.EN_ROUTE)
        self.assertTrue(interv.gps_tracking_required)
        field_names = [f.name for f in Intervention._meta.get_fields()]
        self.assertNotIn('gps_tracking_required', field_names)
        api = auth(self.user)
        resp = api.patch(
            f'{BASE}/interventions/{interv.id}/',
            {'gps_tracking_required': False}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        interv.refresh_from_db()
        self.assertTrue(interv.gps_tracking_required)


class TestPositionPingAndGeofence(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.technicien = make_user(self.company, role='normal')
        gps_tracking_service.record_consent(self.company, self.technicien)
        self.interv = make_intervention(
            self.company, self.user, self.technicien,
            statut=Intervention.Statut.SUR_SITE)
        self.api = auth(self.technicien)

    def test_ping_inside_radius_no_alert(self):
        # Chantier à 33.573110/-7.589843 — un point à quelques mètres.
        resp = self.api.post(
            f'{BASE}/positions-techniciens/ping/',
            {'lat': '33.573150', 'lng': '-7.589800',
             'intervention': self.interv.id}, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertIsNone(resp.data['geofence_alert'])
        self.assertFalse(resp.data['hors_perimetre'])
        self.assertEqual(GeofenceAlert.objects.count(), 0)

    def test_ping_outside_radius_triggers_geofence_alert(self):
        # ~5km au nord — largement hors du rayon par défaut (0.5 km).
        resp = self.api.post(
            f'{BASE}/positions-techniciens/ping/',
            {'lat': '33.62', 'lng': '-7.589843',
             'intervention': self.interv.id}, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertTrue(resp.data['hors_perimetre'])
        self.assertIsNotNone(resp.data['geofence_alert'])
        alerte = GeofenceAlert.objects.get(intervention=self.interv)
        self.assertEqual(alerte.technicien, self.technicien)
        self.assertGreater(alerte.distance_site_km, alerte.rayon_attendu_km)

    def test_ping_without_intervention_records_position_only(self):
        resp = self.api.post(
            f'{BASE}/positions-techniciens/ping/',
            {'lat': '33.5', 'lng': '-7.6'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertIsNone(resp.data['geofence_alert'])
        pos = PositionTechnicien.objects.get(id=resp.data['id'])
        self.assertIsNone(pos.intervention)

    def test_ping_missing_coords_rejected(self):
        resp = self.api.post(
            f'{BASE}/positions-techniciens/ping/', {}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_carte_live_returns_latest_position(self):
        self.api.post(
            f'{BASE}/positions-techniciens/ping/',
            {'lat': '33.573150', 'lng': '-7.589800'}, format='json')
        supervisor_api = auth(self.user)
        resp = supervisor_api.get(f'{BASE}/positions-techniciens/carte-live/')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]['technicien'], self.technicien.id)


class TestCompanyIsolation(TestCase):
    def setUp(self):
        self.company_a = make_company()
        self.company_b = make_company()
        self.user_a = make_user(self.company_a)
        self.user_b = make_user(self.company_b)
        self.tech_a = make_user(self.company_a, role='normal')
        self.tech_b = make_user(self.company_b, role='normal')
        gps_tracking_service.record_consent(self.company_a, self.tech_a)
        gps_tracking_service.record_consent(self.company_b, self.tech_b)
        self.interv_a = make_intervention(
            self.company_a, self.user_a, self.tech_a,
            statut=Intervention.Statut.SUR_SITE)
        self.interv_b = make_intervention(
            self.company_b, self.user_b, self.tech_b,
            statut=Intervention.Statut.SUR_SITE)

    def test_positions_scoped_to_own_company(self):
        gps_tracking_service.enregistrer_position(
            self.company_a, self.tech_a, 33.573110, -7.589843,
            intervention=self.interv_a)
        gps_tracking_service.enregistrer_position(
            self.company_b, self.tech_b, 34.0, -6.8, intervention=self.interv_b)
        api_a = auth(self.user_a)
        resp = api_a.get(f'{BASE}/positions-techniciens/')
        ids_returned = {p['id'] for p in resp.data.get(
            'results', resp.data if isinstance(resp.data, list) else [])}
        positions_b = set(
            PositionTechnicien.objects.filter(
                company=self.company_b).values_list('id', flat=True))
        self.assertFalse(ids_returned & positions_b)

    def test_geofence_alerts_scoped_to_own_company(self):
        # Positions loin des deux chantiers → alerte pour chaque société.
        gps_tracking_service.enregistrer_position(
            self.company_a, self.tech_a, 33.7, -7.589843,
            intervention=self.interv_a)
        gps_tracking_service.enregistrer_position(
            self.company_b, self.tech_b, 34.2, -6.8, intervention=self.interv_b)
        api_a = auth(self.user_a)
        resp = api_a.get(f'{BASE}/geofence-alertes/')
        results = resp.data.get(
            'results', resp.data if isinstance(resp.data, list) else [])
        for row in results:
            self.assertEqual(row['intervention'], self.interv_a.id)

    def test_gps_consent_scoped_to_own_company(self):
        api_a = auth(self.user_a)
        resp = api_a.get(f'{BASE}/gps-consentements/')
        results = resp.data.get(
            'results', resp.data if isinstance(resp.data, list) else [])
        technicien_ids = {row['technicien'] for row in results}
        self.assertNotIn(self.tech_b.id, technicien_ids)


class TestRetentionPurge(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.technicien = make_user(self.company, role='normal')
        gps_tracking_service.record_consent(self.company, self.technicien)
        self.interv = make_intervention(
            self.company, self.user, self.technicien,
            statut=Intervention.Statut.SUR_SITE)

    def test_purge_deletes_old_positions_keeps_recent(self):
        old_pos = PositionTechnicien.objects.create(
            company=self.company, technicien=self.technicien,
            intervention=self.interv, lat=Decimal('33.5'), lng=Decimal('-7.6'),
            captured_at=timezone.now() - timedelta(days=45))
        recent_pos = PositionTechnicien.objects.create(
            company=self.company, technicien=self.technicien,
            intervention=self.interv, lat=Decimal('33.5'), lng=Decimal('-7.6'),
            captured_at=timezone.now() - timedelta(days=2))
        nb = gps_tracking_service.purge_positions_expirees(
            self.company, retention_jours=30)
        self.assertEqual(nb, 1)
        self.assertFalse(
            PositionTechnicien.objects.filter(id=old_pos.id).exists())
        self.assertTrue(
            PositionTechnicien.objects.filter(id=recent_pos.id).exists())

    def test_purge_scoped_to_company_when_given(self):
        other_company = make_company()
        other_tech = make_user(other_company, role='normal')
        gps_tracking_service.record_consent(other_company, other_tech)
        other_pos = PositionTechnicien.objects.create(
            company=other_company, technicien=other_tech,
            lat=Decimal('34.0'), lng=Decimal('-6.8'),
            captured_at=timezone.now() - timedelta(days=45))
        gps_tracking_service.purge_positions_expirees(
            self.company, retention_jours=30)
        self.assertTrue(
            PositionTechnicien.objects.filter(id=other_pos.id).exists())
