"""XMKT2 — Journal d'envoi par destinataire (trace de campagne).

Couvre : une ligne EnvoiCampagne par destinataire à l'envoi, mise à jour par
webhook Brevo (gated, no-op sans clé mais le traitement du payload reste
testable indépendamment), drill-down company-scoped, compteurs dérivés
cohérents.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.compta import services
from apps.marketing.models import Campagne, EnvoiCampagne

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class EnvoiCampagneTests(TestCase):
    def setUp(self):
        self.co = make_company('xmkt2', 'XMKT2')
        self.user = make_user(self.co, 'xmkt2-user')

    def test_envoi_cree_une_ligne_par_destinataire(self):
        camp = Campagne.objects.create(
            company=self.co, nom='C', canal=Campagne.Canal.EMAIL)
        services.envoyer_campagne(
            camp, destinataires=['a@x.ma', 'b@x.ma'])
        self.assertEqual(
            EnvoiCampagne.objects.filter(campagne=camp).count(), 2)
        envoi = EnvoiCampagne.objects.get(
            campagne=camp, destinataire='a@x.ma')
        self.assertEqual(envoi.statut, EnvoiCampagne.Statut.QUEUED)

    def test_envoi_avec_contact_ref(self):
        camp = Campagne.objects.create(
            company=self.co, nom='C', canal=Campagne.Canal.EMAIL)
        services.envoyer_campagne(camp, destinataires=[
            {'destinataire': 'a@x.ma', 'contact_ref': 'lead:42'},
        ])
        envoi = EnvoiCampagne.objects.get(campagne=camp)
        self.assertEqual(envoi.contact_ref, 'lead:42')

    def test_webhook_met_a_jour_statut_et_recalcule_compteurs(self):
        camp = Campagne.objects.create(
            company=self.co, nom='C', canal=Campagne.Canal.EMAIL)
        services.envoyer_campagne(camp, destinataires=['a@x.ma'])
        services.webhook_brevo_evenement(
            self.co, campagne_id=camp.id, destinataire='a@x.ma',
            evenement='opened')
        camp.refresh_from_db()
        envoi = EnvoiCampagne.objects.get(campagne=camp)
        self.assertEqual(envoi.statut, EnvoiCampagne.Statut.OUVERT)
        self.assertIsNotNone(envoi.ouvert_le)
        self.assertEqual(camp.nb_ouvertures, 1)

    def test_webhook_bounce_stocke_raison_smtp(self):
        camp = Campagne.objects.create(
            company=self.co, nom='C', canal=Campagne.Canal.EMAIL)
        services.envoyer_campagne(camp, destinataires=['bad@x.ma'])
        services.webhook_brevo_evenement(
            self.co, campagne_id=camp.id, destinataire='bad@x.ma',
            evenement='bounce', raison_smtp='550 mailbox not found')
        envoi = EnvoiCampagne.objects.get(campagne=camp)
        self.assertEqual(envoi.statut, EnvoiCampagne.Statut.REBOND)
        self.assertEqual(envoi.raison_smtp, '550 mailbox not found')

    def test_webhook_destinataire_inconnu_noop(self):
        camp = Campagne.objects.create(
            company=self.co, nom='C', canal=Campagne.Canal.EMAIL)
        result = services.webhook_brevo_evenement(
            self.co, campagne_id=camp.id, destinataire='inconnu@x.ma',
            evenement='opened')
        self.assertIsNone(result)

    def test_endpoint_webhook_http(self):
        camp = Campagne.objects.create(
            company=self.co, nom='C', canal=Campagne.Canal.EMAIL)
        services.envoyer_campagne(camp, destinataires=['c@x.ma'])
        api = APIClient()  # aucune auth : webhook public
        resp = api.post('/api/django/compta/webhooks/brevo/', {
            'campagne_id': camp.id, 'destinataire': 'c@x.ma',
            'event': 'click',
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data['statut'], EnvoiCampagne.Statut.CLIQUE)

    def test_drill_down_endpoint_filtrable_par_statut(self):
        camp = Campagne.objects.create(
            company=self.co, nom='C', canal=Campagne.Canal.EMAIL)
        services.envoyer_campagne(camp, destinataires=['a@x.ma', 'b@x.ma'])
        services.webhook_brevo_evenement(
            self.co, campagne_id=camp.id, destinataire='a@x.ma',
            evenement='opened')
        api = auth(self.user)
        resp = api.get(
            f'/api/django/compta/envois-campagne/?campagne={camp.id}&statut=ouvert')
        self.assertEqual(resp.status_code, 200, resp.content)
        results = resp.data['results'] if 'results' in resp.data else resp.data
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['destinataire'], 'a@x.ma')

    def test_isolation_multi_tenant_drill_down(self):
        other = make_company('xmkt2-b', 'XMKT2-B')
        other_user = make_user(other, 'xmkt2-b-user')
        camp_a = Campagne.objects.create(
            company=self.co, nom='A', canal=Campagne.Canal.EMAIL)
        camp_b = Campagne.objects.create(
            company=other, nom='B', canal=Campagne.Canal.EMAIL)
        services.envoyer_campagne(camp_a, destinataires=['a@x.ma'])
        services.envoyer_campagne(camp_b, destinataires=['b@x.ma'])
        api = auth(other_user)
        resp = api.get('/api/django/compta/envois-campagne/')
        results = resp.data['results'] if 'results' in resp.data else resp.data
        destinataires = {r['destinataire'] for r in results}
        self.assertEqual(destinataires, {'b@x.ma'})
