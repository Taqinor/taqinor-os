"""Garde admin — un produit ne peut pas être supprimé depuis /admin/.

Le catalogue produits est de la VRAIE donnée saisie à la main (prix d'achat
fournisseur, prix VEICHI réels, courbes de pompes OSP, fiches produit).
`ProduitViewSet.destroy` ne détruit jamais : il rattrape `ProtectedError` et
ARCHIVE (`is_archived = True`). L'admin Django court-circuitait ce repli — et
surtout, pour un produit dont les enfants restants sont TOUS en CASCADE (fiche
technique, conditionnements, prix fournisseur, lots…), il supprimait
SILENCIEUSEMENT le produit ET ses enfants. C'est exactement le cas des pompes
OSP à courbe constructeur, encore sans mouvement ni devis.

Ces tests prouvent :
  * le refus pour un produit ayant un dépendant PROTECT (mouvement de stock) ;
  * le refus pour un produit n'ayant QUE des enfants CASCADE — le cas
    silencieux, celui qui détruisait réellement de la donnée ;
  * que le message français NOMME le chemin supporté (archivage) ;
  * que l'action groupée `delete_selected` a disparu pour cet admin ;
  * que le garde reste CIBLÉ : une catégorie (donnée jetable) reste supprimable.
"""
from decimal import Decimal

from django.contrib import admin as django_admin
from django.contrib.messages import get_messages
from django.core.exceptions import PermissionDenied
from django.test import Client, RequestFactory, TestCase
from django.urls import reverse

from apps.stock.admin import SUPPRESSION_PRODUIT_INTERDITE
from apps.stock.models import (
    Categorie, FicheTechnique, MouvementStock, Produit,
)
from testkit.factories import CompanyFactory, ProduitFactory, UserFactory


class ProduitAdminDeleteGuardTests(TestCase):
    def setUp(self):
        super().setUp()
        self.company = CompanyFactory(nom='Catalogue Réel',
                                      slug='catalogue-reel')

        # Cas A — produit « utilisé » : un mouvement de stock le PROTECT.
        self.produit_protege = ProduitFactory(
            company=self.company, nom='Panneau 550 Wc',
            prix_achat=Decimal('980.00'))
        MouvementStock.objects.create(
            company=self.company, produit=self.produit_protege,
            type_mouvement=MouvementStock.TypeMouvement.ENTREE,
            quantite=10, quantite_avant=0, quantite_apres=10)

        # Cas B — le cas SILENCIEUX : aucun dépendant PROTECT, uniquement un
        # enfant CASCADE. C'est celui que l'admin détruisait sans un mot.
        self.produit_cascade = ProduitFactory(
            company=self.company, nom='Pompe OSP 30-15',
            prix_achat=Decimal('0'))
        self.fiche = FicheTechnique.objects.create(
            company=self.company, produit=self.produit_cascade,
            pmax_wc=Decimal('550.00'))

        self.superuser = UserFactory(
            company=self.company, username='root-guard-produit',
            is_staff=True, is_superuser=True)
        self.http = Client()
        self.http.force_login(self.superuser)
        self.model_admin = django_admin.site._registry[Produit]

    def _request(self):
        request = RequestFactory().get('/')
        request.user = self.superuser
        return request

    def _catalogue_intact(self):
        self.assertTrue(Produit.objects.filter(
            pk=self.produit_protege.pk).exists())
        cascade = Produit.objects.get(pk=self.produit_cascade.pk)
        # Ni supprimé, NI archivé en douce : l'admin refuse, il n'agit pas.
        self.assertFalse(cascade.is_archived)
        self.assertTrue(FicheTechnique.objects.filter(pk=self.fiche.pk).exists())

    def test_has_delete_permission_toujours_false(self):
        request = self._request()
        self.assertFalse(self.model_admin.has_delete_permission(request))
        self.assertFalse(self.model_admin.has_delete_permission(
            request, self.produit_cascade))

    def test_action_groupee_delete_selected_retiree(self):
        self.assertNotIn('delete_selected',
                         self.model_admin.get_actions(self._request()))

    def test_produit_avec_dependant_protege_refuse_avec_message(self):
        url = reverse('admin:stock_produit_delete',
                      args=[self.produit_protege.pk])
        response = self.http.get(url)

        self.assertEqual(response.status_code, 302)
        messages = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertEqual(messages, [SUPPRESSION_PRODUIT_INTERDITE])
        # Le message NOMME le chemin supporté : l'archivage.
        self.assertIn('ARCHIVAGE', messages[0])
        self.assertIn('/api/django/stock/produits/', messages[0])
        self._catalogue_intact()

    def test_produit_sans_dependant_protege_refuse_aussi(self):
        """Le cas qui détruisait réellement : enfants tous en CASCADE."""
        url = reverse('admin:stock_produit_delete',
                      args=[self.produit_cascade.pk])
        response = self.http.post(url, {'post': 'yes'})

        self.assertEqual(response.status_code, 302)
        self._catalogue_intact()

    def test_suppression_en_masse_refusee(self):
        url = reverse('admin:stock_produit_changelist')
        response = self.http.post(url, {
            'action': 'delete_selected',
            '_selected_action': [str(self.produit_protege.pk),
                                 str(self.produit_cascade.pk)],
            'post': 'yes',
        })

        self.assertEqual(response.status_code, 200)
        self._catalogue_intact()

    def test_delete_model_et_delete_queryset_refusent(self):
        request = self._request()
        with self.assertRaises(PermissionDenied):
            self.model_admin.delete_model(request, self.produit_cascade)
        with self.assertRaises(PermissionDenied):
            self.model_admin.delete_queryset(
                request, Produit.objects.filter(pk=self.produit_cascade.pk))
        self._catalogue_intact()

    def test_garde_cible_une_categorie_reste_supprimable(self):
        """Le garde ne désactive PAS la suppression partout : une catégorie
        (référentiel jetable, aucun dépendant PROTECT) part normalement."""
        categorie = Categorie.objects.create(
            company=self.company, nom='Catégorie jetable')
        url = reverse('admin:stock_categorie_delete', args=[categorie.pk])
        response = self.http.post(url, {'post': 'yes'})

        self.assertEqual(response.status_code, 302)
        self.assertFalse(Categorie.objects.filter(pk=categorie.pk).exists())
        self._catalogue_intact()
