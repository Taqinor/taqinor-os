"""APRF21 — ``message_ouvert_le`` lu EN LOT et ``traite_par`` chargé dans la
frise ``?lead=`` : +10 touches WhatsApp à faire et +10 touches traitées
n'ajoutent aucune requête ; les valeurs restent celles d'avant.

Test-du-test : remettre la requête par touche dans
``get_message_ouvert_le`` (ou retirer ``traite_par`` du ``select_related``)
⇒ +1 requête par touche, test_file_plate / test_frise_plate échouent.
"""
import datetime

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm import stages
from apps.crm.models import Lead, LeadActivity, RelanceEtape
from apps.crm.cadence_reperes import prefixe_activite_message_ouvert

User = get_user_model()
URL = '/api/django/crm/relance-etapes/'


class RelanceEtapesRequetesTests(TestCase):

    def setUp(self):
        from apps.roles.models import Role
        from apps.roles.permissions_registre import ADMIN_PERMISSIONS
        self.company = Company.objects.create(
            nom='APRF21 Solaire', slug='aprf21-relances')
        role, _ = Role.objects.get_or_create(
            company=self.company, nom='Administrateur',
            defaults={'permissions': ADMIN_PERMISSIONS, 'est_systeme': True})
        self.user = User.objects.create_user(
            username='aprf21-admin', password='x', company=self.company,
            role=role, role_legacy='admin')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.n = 0
        self.attendu = {}

    def _touche(self, lead, statut=RelanceEtape.Statut.A_FAIRE, **kw):
        self.n += 1
        maintenant = timezone.now()
        return RelanceEtape.objects.create(
            company=self.company, lead=lead, cadence='contact',
            ordre=self.n, canal=RelanceEtape.Canal.WHATSAPP,
            libelle=f'Message {self.n}', due_at=maintenant,
            due_date=maintenant.date(), statut=statut, **kw)

    def _touches_whatsapp(self, nombre):
        for _ in range(nombre):
            lead = Lead.objects.create(
                company=self.company, nom=f'L{self.n}', owner=self.user,
                stage=stages.CONTACTED)
            touche = self._touche(lead)
            act = LeadActivity.objects.create(
                company=self.company, lead=lead, user=self.user,
                kind=LeadActivity.Kind.WHATSAPP,
                body=prefixe_activite_message_ouvert(touche) + ' (test)')
            self.attendu[touche.pk] = act.created_at

    def _requetes(self, params):
        with CaptureQueriesContext(connection) as ctx:
            resp = self.api.get(URL, params)
        self.assertEqual(resp.status_code, 200, resp.data)
        return len(ctx.captured_queries), resp.data['results']

    def test_file_plate(self):
        self._touches_whatsapp(10)
        self._requetes({'scope': 'all'})  # échauffement
        avant, _ = self._requetes({'scope': 'all'})
        self._touches_whatsapp(10)
        apres, lignes = self._requetes({'scope': 'all'})
        self.assertEqual(apres, avant)
        obtenu = {r['id']: r['message_ouvert_le'] for r in lignes}
        for pk, cree in self.attendu.items():
            self.assertIsNotNone(obtenu[pk])
            self.assertEqual(
                datetime.datetime.fromisoformat(
                    str(obtenu[pk]).replace('Z', '+00:00')), cree)

    def test_message_ouvert_par_touche(self):
        lead = Lead.objects.create(
            company=self.company, nom='Deux', owner=self.user,
            stage=stages.CONTACTED)
        ouverte = self._touche(lead)
        fermee = self._touche(lead)
        LeadActivity.objects.create(
            company=self.company, lead=lead, user=self.user,
            kind=LeadActivity.Kind.WHATSAPP,
            body=prefixe_activite_message_ouvert(ouverte))
        _, lignes = self._requetes({'lead': lead.pk})
        obtenu = {r['id']: r['message_ouvert_le'] for r in lignes}
        self.assertIsNotNone(obtenu[ouverte.pk])
        self.assertIsNone(obtenu[fermee.pk])

    def test_frise_plate(self):
        lead = Lead.objects.create(
            company=self.company, nom='Frise', owner=self.user,
            stage=stages.CONTACTED)

        def traitees(nombre):
            for _ in range(nombre):
                self._touche(lead, statut=RelanceEtape.Statut.FAIT,
                             traite_par=self.user, traite_le=timezone.now())

        traitees(10)
        self._requetes({'lead': lead.pk})
        avant, _ = self._requetes({'lead': lead.pk})
        traitees(10)
        apres, lignes = self._requetes({'lead': lead.pk})
        self.assertEqual(apres, avant)
        self.assertEqual(len(lignes), 20)
        self.assertTrue(all(r['traite_par_nom'] == 'aprf21-admin'
                            for r in lignes))
