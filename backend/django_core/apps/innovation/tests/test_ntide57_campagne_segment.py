"""Tests consolidés des campagnes d'innovation et de leur segment (NTIDE57).

Couvre les 6 critères d'acceptation de NTIDE57 en un module autoportant :
création via l'API (``company`` posée par le SERVEUR), ``segment`` JSON
(liste de rôles) vs ``cible_departement`` mono-valeur, le sélecteur
``users_for_campaign``, la création « en masse » NTIDE35 (UNE campagne
multi-segment, jamais une campagne par rôle), les transitions de statut
brouillon → active → fermée, et le tag auto-appliqué (NTIDE28) aux idées
proposées par le segment pendant que la campagne est active.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.innovation import selectors
from apps.innovation.models import CampagneInnovation, Idee
from apps.records.models import Tag, TaggedItem
from apps.roles.models import Role

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_role(company, nom):
    role, _ = Role.objects.get_or_create(company=company, nom=nom)
    return role


def make_user(company, username, role=None, role_legacy='normal'):
    return User.objects.create_user(
        username=username, password='x', company=company, role=role,
        role_legacy=role_legacy)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def tags_of(idee):
    from django.contrib.contenttypes.models import ContentType
    ct = ContentType.objects.get_for_model(Idee)
    tagged = TaggedItem.objects.filter(content_type=ct, object_id=idee.id)
    return set(Tag.objects.filter(id__in=tagged.values('tag_id'))
               .values_list('nom', flat=True))


class CampagneSegmentTests(TestCase):
    BASE = '/api/django/innovation/campagnes/'
    IDEES = '/api/django/innovation/idees/'

    def setUp(self):
        self.co_a = make_company('innov-ntide57-a', 'A')
        self.co_b = make_company('innov-ntide57-b', 'B')
        self.role_tech = make_role(self.co_a, 'Technicien')
        self.role_com = make_role(self.co_a, 'Commercial')
        self.admin = make_user(self.co_a, 'ntide57-admin', role_legacy='admin')
        self.tech = make_user(self.co_a, 'ntide57-tech', role=self.role_tech)
        self.com = make_user(self.co_a, 'ntide57-com', role=self.role_com)

    # ── 1. création ─────────────────────────────────────────────────────────
    def test_create_company_is_server_set(self):
        resp = auth(self.admin).post(self.BASE, {
            'nom': 'Campagne NTIDE57',
            'segment': ['Technicien'],
            'company': self.co_b.id,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        campagne = CampagneInnovation.objects.get(id=resp.data['id'])
        self.assertEqual(campagne.company, self.co_a)
        self.assertEqual(campagne.statut, CampagneInnovation.Statut.BROUILLON)

    def test_create_reserved_to_admin_tier(self):
        resp = auth(self.tech).post(
            self.BASE, {'nom': 'Interdite'}, format='json')
        self.assertEqual(resp.status_code, 403)
        self.assertFalse(
            CampagneInnovation.objects.filter(nom='Interdite').exists())

    # ── 2. segment JSON vs cible mono-valeur ────────────────────────────────
    def test_segment_is_stored_as_json_list(self):
        resp = auth(self.admin).post(self.BASE, {
            'nom': 'Multi', 'segment': ['Technicien', 'Commercial'],
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        campagne = CampagneInnovation.objects.get(id=resp.data['id'])
        self.assertEqual(campagne.segment, ['Technicien', 'Commercial'])
        # Défaut : liste vide, jamais ``None`` (JSONField default=list).
        vide = CampagneInnovation.objects.create(company=self.co_a, nom='Vide')
        self.assertEqual(vide.segment, [])

    def test_cible_departement_is_the_mono_value_fallback(self):
        campagne = CampagneInnovation.objects.create(
            company=self.co_a, nom='Mono', cible_departement='Technicien')
        self.assertEqual(campagne.segment, [])
        self.assertEqual(
            list(selectors.users_for_campaign(self.co_a, campagne)), [self.tech])

    # ── 3. sélecteur des utilisateurs ciblés ────────────────────────────────
    def test_users_for_campaign_targets_segment_union_only(self):
        campagne = CampagneInnovation.objects.create(
            company=self.co_a, nom='Union',
            segment=['Technicien', 'Commercial'])
        make_user(self.co_a, 'ntide57-sans-role')
        cibles = set(selectors.users_for_campaign(self.co_a, campagne))
        self.assertEqual(cibles, {self.tech, self.com})

    def test_users_for_campaign_isolated_per_company(self):
        role_tech_b = make_role(self.co_b, 'Technicien')
        make_user(self.co_b, 'ntide57-tech-b', role=role_tech_b)
        campagne = CampagneInnovation.objects.create(
            company=self.co_a, nom='Isolée', segment=['Technicien'])
        self.assertEqual(
            list(selectors.users_for_campaign(self.co_a, campagne)), [self.tech])

    # ── 4. création « en masse » (NTIDE35) ──────────────────────────────────
    def test_bulk_creation_is_one_campaign_not_one_per_role(self):
        """« Lancer chez tous les Techniciens + tous les Commerciaux » crée
        UNE campagne dont ``segment`` mappe la liste — jamais deux."""
        resp = auth(self.admin).post(self.BASE, {
            'nom': 'Techniciens + Commerciaux',
            'segment': ['Technicien', 'Commercial'],
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(
            CampagneInnovation.objects.filter(
                company=self.co_a, nom='Techniciens + Commerciaux').count(), 1)

    # ── 5. transitions de statut ────────────────────────────────────────────
    def test_statut_transitions_brouillon_active_fermee(self):
        campagne = CampagneInnovation.objects.create(
            company=self.co_a, nom='Cycle', segment=['Technicien'])
        api = auth(self.admin)
        url = f'{self.BASE}{campagne.id}/'
        active = api.patch(
            url, {'statut': CampagneInnovation.Statut.ACTIVE}, format='json')
        self.assertEqual(active.status_code, 200, active.data)
        campagne.refresh_from_db()
        self.assertEqual(campagne.statut, CampagneInnovation.Statut.ACTIVE)
        fermee = api.patch(
            url, {'statut': CampagneInnovation.Statut.FERMEE}, format='json')
        self.assertEqual(fermee.status_code, 200, fermee.data)
        campagne.refresh_from_db()
        self.assertEqual(campagne.statut, CampagneInnovation.Statut.FERMEE)

    def test_lancement_notifie_le_segment_une_seule_fois(self):
        from apps.notifications.models import EventType, Notification

        campagne = CampagneInnovation.objects.create(
            company=self.co_a, nom='Lancement', segment=['Technicien'])
        api = auth(self.admin)
        url = f'{self.BASE}{campagne.id}/'
        recues = Notification.objects.filter(
            event_type=EventType.INNOVATION_CAMPAIGN, recipient=self.tech)
        api.patch(url, {'statut': CampagneInnovation.Statut.ACTIVE},
                  format='json')
        self.assertEqual(recues.count(), 1)
        # Republier une campagne DÉJÀ active n'inonde pas le segment.
        api.patch(url, {'statut': CampagneInnovation.Statut.ACTIVE},
                  format='json')
        self.assertEqual(recues.count(), 1)

    # ── 6. tag auto-appliqué ────────────────────────────────────────────────
    def test_tag_auto_applied_to_segment_idea_while_active(self):
        CampagneInnovation.objects.create(
            company=self.co_a, nom='Pompage', segment=['Technicien'],
            statut=CampagneInnovation.Statut.ACTIVE, tag_auto='Pompage')
        resp = auth(self.tech).post(
            self.IDEES, {'titre': 'Idée technicien'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(tags_of(Idee.objects.get(id=resp.data['id'])),
                         {'Pompage'})

    def test_tag_auto_not_applied_outside_segment_or_when_draft_campaign(self):
        CampagneInnovation.objects.create(
            company=self.co_a, nom='Pompage', segment=['Technicien'],
            statut=CampagneInnovation.Statut.ACTIVE, tag_auto='Pompage')
        hors = auth(self.com).post(
            self.IDEES, {'titre': 'Idée commerciale'}, format='json')
        self.assertEqual(hors.status_code, 201, hors.data)
        self.assertEqual(tags_of(Idee.objects.get(id=hors.data['id'])), set())

        CampagneInnovation.objects.create(
            company=self.co_a, nom='Brouillon', segment=['Commercial'],
            statut=CampagneInnovation.Statut.BROUILLON, tag_auto='Jamais')
        encore = auth(self.com).post(
            self.IDEES, {'titre': 'Idée commerciale 2'}, format='json')
        self.assertEqual(tags_of(Idee.objects.get(id=encore.data['id'])), set())
