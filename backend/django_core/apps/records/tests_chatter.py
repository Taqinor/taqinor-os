"""ARC8 — chatter générique (records.Activity) : service + mixin + pilotes.

Couvre :
  - ``records.services.log_activity`` / ``log_note`` / ``chatter_qs`` : société
    et auteur posés côté serveur, la timeline n'inclut QUE les entrées de
    chatter (jamais les activités planifiées).
  - ``ChatterViewSetMixin`` câblé sur ``ContratViewSet`` (contrats.Contrat) et
    ``VehiculeViewSet`` (flotte.Vehicule) — endpoints ``chatter/historique`` +
    ``chatter/noter`` testés, isolation multi-tenant asservie.
"""
from testkit.base import TenantAPITestCase

from apps.records.models import Activity, ActivityType
from apps.records.services import chatter_qs, log_activity, log_note


class _Targets:
    """Fabrique paresseuse d'un Contrat et d'un Vehicule minimaux (pas de
    factory dédiée dans testkit) — company posée explicitement."""

    @staticmethod
    def contrat(company):
        from apps.contrats.models import Contrat
        return Contrat.objects.create(company=company, objet='Maintenance PV')

    @staticmethod
    def vehicule(company):
        from apps.flotte.models import Vehicule
        return Vehicule.objects.create(
            company=company, immatriculation='1234-A-56')


class TestLogActivityService(TenantAPITestCase):
    def test_log_note_forces_company_and_user(self):
        contrat = _Targets.contrat(self.company)
        act = log_note(contrat, self.user, 'Rappel client effectué')
        self.assertEqual(act.kind, Activity.Kind.NOTE)
        self.assertEqual(act.body, 'Rappel client effectué')
        # Société déduite de la cible ; auteur posé côté serveur.
        self.assertEqual(act.company_id, self.company.id)
        self.assertEqual(act.created_by_id, self.user.id)
        # Une entrée de chatter n'a pas de type d'activité planifiée.
        self.assertIsNone(act.activity_type_id)
        self.assertEqual(act.object_id, contrat.id)

    def test_log_activity_modification_snapshot(self):
        veh = _Targets.vehicule(self.company)
        act = log_activity(
            veh, Activity.Kind.MODIFICATION, user=self.user,
            field='statut', field_label='Statut',
            old_value='actif', new_value='maintenance')
        self.assertEqual(act.kind, Activity.Kind.MODIFICATION)
        self.assertEqual(act.field_label, 'Statut')
        self.assertEqual(act.old_value, 'actif')
        self.assertEqual(act.new_value, 'maintenance')

    def test_chatter_qs_excludes_planned_activities(self):
        contrat = _Targets.contrat(self.company)
        # Une activité PLANIFIÉE (kind vide) sur la même cible ne doit PAS
        # apparaître dans la timeline de chatter.
        from django.contrib.contenttypes.models import ContentType
        atype = ActivityType.objects.create(company=self.company, nom='Appel')
        ct = ContentType.objects.get_for_model(contrat.__class__)
        Activity.objects.create(
            company=self.company, content_type=ct, object_id=contrat.id,
            activity_type=atype, summary='À rappeler')
        note = log_note(contrat, self.user, 'Note de chatter')
        qs = chatter_qs(contrat, company=self.company)
        self.assertEqual(list(qs), [note])


class TestContratChatterEndpoints(TenantAPITestCase):
    def setUp(self):
        super().setUp()
        self.contrat = _Targets.contrat(self.company)
        self.url_hist = (
            f'/api/django/contrats/contrats/{self.contrat.id}/chatter/historique/')
        self.url_note = (
            f'/api/django/contrats/contrats/{self.contrat.id}/chatter/noter/')

    def test_noter_then_historique(self):
        api = self.client_as(role='responsable')
        r = api.post(self.url_note, {'body': 'Contrat relu'}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.data['kind'], 'note')
        self.assertEqual(r.data['body'], 'Contrat relu')
        self.assertEqual(r.data['target_model'], 'contrats.contrat')
        h = api.get(self.url_hist)
        self.assertEqual(h.status_code, 200)
        self.assertEqual(len(h.data), 1)
        self.assertEqual(h.data[0]['body'], 'Contrat relu')

    def test_noter_rejects_empty_body(self):
        api = self.client_as(role='responsable')
        r = api.post(self.url_note, {'body': '  '}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_other_company_cannot_read_or_note(self):
        api = self.client_as(user=self.other_user)
        self.assertIn(api.get(self.url_hist).status_code, (403, 404))
        self.assertIn(
            api.post(self.url_note, {'body': 'x'}, format='json').status_code,
            (403, 404))

    def test_bespoke_historique_untouched(self):
        # ARC8 ne touche pas au chatter maison (ContratActivity) : l'action
        # ``historique`` legacy répond toujours et reste distincte.
        api = self.client_as(role='responsable')
        legacy = api.get(
            f'/api/django/contrats/contrats/{self.contrat.id}/historique/')
        self.assertEqual(legacy.status_code, 200)


class TestVehiculeChatterEndpoints(TenantAPITestCase):
    def setUp(self):
        super().setUp()
        self.veh = _Targets.vehicule(self.company)
        self.url_hist = (
            f'/api/django/flotte/vehicules/{self.veh.id}/chatter/historique/')
        self.url_note = (
            f'/api/django/flotte/vehicules/{self.veh.id}/chatter/noter/')

    def test_noter_then_historique(self):
        api = self.client_as(role='responsable')
        r = api.post(self.url_note, {'body': 'Révision faite'}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.data['target_model'], 'flotte.vehicule')
        h = api.get(self.url_hist)
        self.assertEqual(h.status_code, 200)
        self.assertEqual(len(h.data), 1)
        self.assertEqual(h.data[0]['body'], 'Révision faite')

    def test_historique_readable_by_any_role(self):
        # ``chatter_historique`` est en READ_ACTIONS : tout rôle lit.
        api = self.client_as(role='normal')
        self.assertEqual(api.get(self.url_hist).status_code, 200)

    def test_other_company_isolated(self):
        api = self.client_as(user=self.other_user)
        self.assertIn(api.get(self.url_hist).status_code, (403, 404))
