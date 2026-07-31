"""Garde admin — un client ne peut pas être supprimé depuis /admin/.

Le catalogue produits (`stock.Produit`) et le pipeline (`crm.Lead`) sont deux
des données réelles de l'ERP ; `crm.Client` est la troisième. 14 FK PROTECT
(devis, factures, installations, tickets SAV, ventes POS, parrainages…)
bloquent déjà la suppression d'un client qui a de vrais documents. Mais un
client SANS document ("propre") n'est retenu par AUCUNE d'elles — l'admin
Django le supprimait alors SILENCIEUSEMENT, effaçant en cascade son
`crm.SiteProfile` et son `crm.PlanCompte` (13 FK CASCADE au total), et
SET_NULLant le champ `client` de TOUS ses leads (les leads survivent, mais
perdent leur rattachement — 9 FK SET_NULL au total).

Ces tests prouvent :
  * le refus pour un client protégé par une FK PROTECT (un devis) ;
  * le refus pour le client "propre" — le cas silencieux, celui où la
    suppression Django aurait réellement réussi (prouvé dynamiquement via
    NestedObjects, le collecteur qu'utilise l'admin lui-même) ;
  * que SiteProfile/PlanCompte/le rattachement du lead survivent intacts ;
  * que le message français NOMME le chemin supporté (anonymisation RGPD) ;
  * que l'action groupée `delete_selected` a disparu pour cet admin ;
  * que le garde reste CIBLÉ : un utilisateur (donnée jetable) reste
    supprimable depuis le même admin.
"""
from django.apps import apps as django_apps
from django.contrib import admin as django_admin
from django.contrib.admin.utils import NestedObjects
from django.contrib.messages import get_messages
from django.core.exceptions import PermissionDenied
from django.test import Client as DjangoTestClient, RequestFactory, TestCase
from django.urls import reverse

from apps.crm.admin import SUPPRESSION_CLIENT_INTERDITE
from apps.crm.models import Client, PlanCompte, SiteProfile
from authentication.models import CustomUser
from testkit.factories import ClientFactory, CompanyFactory, DevisFactory, UserFactory


class ClientAdminDeleteGuardTests(TestCase):
    def setUp(self):
        super().setUp()
        self.company = CompanyFactory(nom='Pipeline Réel', slug='pipeline-reel')

        # Cas A — client "utilisé" : un devis le PROTECT.
        self.client_protege = ClientFactory(
            company=self.company, nom='Client Devis')
        DevisFactory(company=self.company, client=self.client_protege)

        # Cas B — le cas SILENCIEUX : client "propre", aucun document.
        # SiteProfile + PlanCompte (CASCADE) + un lead rattaché (SET_NULL).
        self.client_propre = ClientFactory(
            company=self.company, nom='Client Propre')
        self.site_profile = SiteProfile.objects.create(
            company=self.company, client=self.client_propre,
            conso_mensuelle_kwh=450)
        self.plan_compte = PlanCompte.objects.create(
            company=self.company, client=self.client_propre)
        Lead = django_apps.get_model('crm', 'Lead')
        self.lead = Lead.objects.create(
            company=self.company, nom='Lead Rattaché',
            client=self.client_propre)

        self.superuser = UserFactory(
            company=self.company, username='root-guard-client',
            is_staff=True, is_superuser=True)
        self.http = DjangoTestClient()
        self.http.force_login(self.superuser)
        self.model_admin = django_admin.site._registry[Client]

    def _request(self):
        request = RequestFactory().get('/')
        request.user = self.superuser
        return request

    def _catalogue_intact(self):
        self.assertTrue(Client.objects.filter(pk=self.client_protege.pk).exists())
        self.assertTrue(Client.objects.filter(pk=self.client_propre.pk).exists())
        # SiteProfile/PlanCompte du client "propre" survivent intacts.
        self.assertTrue(
            SiteProfile.objects.filter(pk=self.site_profile.pk).exists())
        self.assertTrue(
            PlanCompte.objects.filter(pk=self.plan_compte.pk).exists())
        # Le lead survit ET garde son rattachement client (pas de SET_NULL).
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.client_id, self.client_propre.pk)

    def test_has_delete_permission_toujours_false(self):
        request = self._request()
        self.assertFalse(self.model_admin.has_delete_permission(request))
        self.assertFalse(self.model_admin.has_delete_permission(
            request, self.client_propre))

    def test_action_groupee_delete_selected_retiree(self):
        self.assertNotIn('delete_selected',
                         self.model_admin.get_actions(self._request()))

    def test_client_protege_refuse_avec_message(self):
        url = reverse('admin:crm_client_delete', args=[self.client_protege.pk])
        response = self.http.get(url)

        self.assertEqual(response.status_code, 302)
        messages = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertEqual(messages, [SUPPRESSION_CLIENT_INTERDITE])
        self.assertIn('anonymize', messages[0])
        self._catalogue_intact()

    def test_client_propre_refuse_aussi(self):
        """Le cas qui détruisait réellement : RIEN ne retient ce client."""
        collector = NestedObjects(using='default')
        collector.collect([self.client_propre])
        self.assertEqual(collector.protected, set())

        url = reverse('admin:crm_client_delete', args=[self.client_propre.pk])
        response = self.http.post(url, {'post': 'yes'})

        self.assertEqual(response.status_code, 302)
        messages = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertEqual(messages, [SUPPRESSION_CLIENT_INTERDITE])
        self._catalogue_intact()

    def test_suppression_en_masse_refusee(self):
        url = reverse('admin:crm_client_changelist')
        response = self.http.post(url, {
            'action': 'delete_selected',
            '_selected_action': [str(self.client_protege.pk),
                                 str(self.client_propre.pk)],
            'post': 'yes',
        })

        self.assertEqual(response.status_code, 200)
        self._catalogue_intact()

    def test_delete_model_et_delete_queryset_refusent(self):
        request = self._request()
        with self.assertRaises(PermissionDenied):
            self.model_admin.delete_model(request, self.client_propre)
        with self.assertRaises(PermissionDenied):
            self.model_admin.delete_queryset(
                request, Client.objects.filter(pk=self.client_propre.pk))
        self._catalogue_intact()

    def test_garde_cible_un_utilisateur_reste_supprimable(self):
        """Le garde ne désactive PAS la suppression partout : un objet jetable
        (ici un utilisateur sans dépendance) part normalement."""
        jetable = UserFactory(company=self.company, username='jetable-client-guard')
        url = reverse('admin:authentication_customuser_delete', args=[jetable.pk])
        response = self.http.post(url, {'post': 'yes'})

        self.assertEqual(response.status_code, 302)
        self.assertFalse(CustomUser.objects.filter(pk=jetable.pk).exists())
        self._catalogue_intact()
