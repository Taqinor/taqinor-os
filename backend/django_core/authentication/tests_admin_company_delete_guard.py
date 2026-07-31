"""Garde admin — une société ne peut JAMAIS être supprimée depuis /admin/.

Contexte : `stock.Produit.company` et `crm.Lead.company` sont volontairement en
`on_delete=CASCADE` (la purge de tenant conçue en dépend, et la règle YDATA3
interdit un SET_NULL sur un champ tenant). Sans garde, la page « Êtes-vous
sûr ? » de l'admin Django effaçait donc, d'un clic, l'INTÉGRALITÉ du catalogue
produits (prix d'achat saisis à la main) et l'INTÉGRALITÉ du pipeline de leads.

Ces tests prouvent :
  * qu'aucun chemin de l'admin (fiche OU action groupée) ne supprime une
    société, même pour un superutilisateur ;
  * que le produit et le lead de cette société survivent à la tentative ;
  * que le refus est EXPLIQUÉ en français et NOMME la procédure supportée
    (`manage.py close_company`), donc redirige vers le chemin sûr ;
  * que le garde reste CIBLÉ : un objet réellement jetable (un utilisateur)
    reste supprimable depuis le même admin.
"""
from decimal import Decimal

from django.apps import apps as django_apps
from django.contrib import admin as django_admin
from django.contrib.messages import get_messages
from django.core.exceptions import PermissionDenied
from django.test import Client, RequestFactory, TestCase
from django.urls import reverse

from authentication.admin import SUPPRESSION_SOCIETE_INTERDITE
from authentication.models import Company, CustomUser
from testkit.factories import CompanyFactory, ProduitFactory, UserFactory


class CompanyAdminDeleteGuardTests(TestCase):
    def setUp(self):
        super().setUp()
        self.company = CompanyFactory(nom='Tenant Réel', slug='tenant-reel')
        # Donnée RÉELLE n°1 : le catalogue (prix d'achat saisi à la main).
        self.produit = ProduitFactory(
            company=self.company, nom='Pompe OSP 30-15',
            prix_achat=Decimal('12345.67'))
        # Donnée RÉELLE n°2 : le pipeline commercial.
        # `get_model` plutôt qu'un import statique : aucune arête d'import
        # `authentication -> apps.crm` n'est créée pour un besoin de test.
        Lead = django_apps.get_model('crm', 'Lead')
        self.lead = Lead.objects.create(company=self.company, nom='Prospect Réel')

        self.superuser = UserFactory(
            company=self.company, username='root-guard-company',
            is_staff=True, is_superuser=True)
        self.http = Client()
        self.http.force_login(self.superuser)
        self.model_admin = django_admin.site._registry[Company]

    def _request(self):
        request = RequestFactory().get('/')
        request.user = self.superuser
        return request

    def _tout_survit(self):
        self.assertTrue(
            Company.objects.filter(pk=self.company.pk).exists(),
            'La société ne doit jamais être supprimée depuis /admin/.')
        Produit = django_apps.get_model('stock', 'Produit')
        Lead = django_apps.get_model('crm', 'Lead')
        produit = Produit.objects.get(pk=self.produit.pk)
        self.assertEqual(produit.prix_achat, Decimal('12345.67'))
        self.assertTrue(Lead.all_objects.filter(pk=self.lead.pk).exists())

    def test_has_delete_permission_toujours_false(self):
        request = self._request()
        self.assertFalse(self.model_admin.has_delete_permission(request))
        self.assertFalse(
            self.model_admin.has_delete_permission(request, self.company))

    def test_action_groupee_delete_selected_retiree(self):
        self.assertNotIn('delete_selected',
                         self.model_admin.get_actions(self._request()))

    def test_suppression_unitaire_refusee_et_expliquee(self):
        url = reverse('admin:authentication_company_delete',
                      args=[self.company.pk])
        response = self.http.get(url)

        self.assertEqual(response.status_code, 302)
        messages = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertEqual(messages, [SUPPRESSION_SOCIETE_INTERDITE])
        # Le message doit NOMMER la procédure supportée (pas un cul-de-sac).
        self.assertIn('close_company', messages[0])
        self.assertIn('--soft-close', messages[0])
        self.assertIn('--yes-je-confirme', messages[0])
        self._tout_survit()

    def test_suppression_unitaire_refusee_meme_en_post_confirme(self):
        """Le POST de confirmation (« Oui, je suis sûr ») ne supprime rien."""
        url = reverse('admin:authentication_company_delete',
                      args=[self.company.pk])
        response = self.http.post(url, {'post': 'yes'})

        self.assertEqual(response.status_code, 302)
        self._tout_survit()

    def test_suppression_en_masse_refusee(self):
        url = reverse('admin:authentication_company_changelist')
        response = self.http.post(url, {
            'action': 'delete_selected',
            '_selected_action': [str(self.company.pk)],
            'post': 'yes',
        })

        # L'action n'existe plus pour cet admin : le formulaire d'action est
        # invalide, la liste est simplement ré-affichée, rien n'est supprimé.
        self.assertEqual(response.status_code, 200)
        self._tout_survit()

    def test_delete_model_et_delete_queryset_refusent(self):
        """Même appelées directement (action maison), les primitives refusent."""
        request = self._request()
        with self.assertRaises(PermissionDenied):
            self.model_admin.delete_model(request, self.company)
        with self.assertRaises(PermissionDenied):
            self.model_admin.delete_queryset(
                request, Company.objects.filter(pk=self.company.pk))
        self._tout_survit()

    def test_garde_cible_un_utilisateur_reste_supprimable(self):
        """Le garde ne désactive PAS la suppression partout : un objet jetable
        (ici un utilisateur sans dépendance) part normalement."""
        jetable = UserFactory(company=self.company, username='jetable-guard')
        url = reverse('admin:authentication_customuser_delete',
                      args=[jetable.pk])
        response = self.http.post(url, {'post': 'yes'})

        self.assertEqual(response.status_code, 302)
        self.assertFalse(CustomUser.objects.filter(pk=jetable.pk).exists())
        self._tout_survit()
