"""AUD215 — le registre des mouvements de stock est en LECTURE SEULE dans /admin/.

Défaut d'origine : `MouvementStockAdmin` ne déclarait que trois
`readonly_fields` (`quantite_avant`, `quantite_apres`, `date`). `produit`,
`type_mouvement` et `quantite` restaient librement éditables, et l'ajout comme
la suppression étaient ouverts — alors que `ProduitAdmin`, dans le MÊME
fichier, porte quatre verrous de suppression redondants.

Ce que cela corrompt : `services._quantite_produit_a_date` reconstruit une
quantité en repartant du dernier `quantite_apres` antérieur à une date ;
`valorisation_a_date` (XSTK13) s'appuie dessus, et `figer_inventaire_annuel`
en tire un inventaire déclaré « immuable ». Modifier ou supprimer une ligne
réécrit donc rétroactivement l'inventaire à toute date postérieure, en
silence.

Second volet (F10 d'AUD185) : AUCUN `admin.py` de `stock` ne scopait son
queryset — un compte staff d'une société y listait les mouvements, produits,
catégories et fournisseurs de TOUTES les autres. Le mixin partagé
`core.admin_scoping.CompanyScopedAdminMixin` (créé par AUD185) est appliqué
ici, sans rien redéfinir.

Run :
    python manage.py test apps.stock.test_aud215_admin_mouvement_registre -v 2
"""
from decimal import Decimal

from django.contrib import admin as django_admin
from django.core.exceptions import PermissionDenied
from django.test import Client, RequestFactory, TestCase
from django.urls import reverse

from apps.stock.admin import MOUVEMENT_STOCK_LECTURE_SEULE
from apps.stock.models import Categorie, Fournisseur, MouvementStock, Produit
from testkit.factories import CompanyFactory, ProduitFactory, UserFactory


class Aud215Base(TestCase):
    def setUp(self):
        super().setUp()
        self.societe_a = CompanyFactory(nom='AUD215 A', slug='aud215-a')
        self.societe_b = CompanyFactory(nom='AUD215 B', slug='aud215-b')

        self.produit_a = ProduitFactory(
            company=self.societe_a, nom='Panneau AUD215 A',
            prix_achat=Decimal('900.00'), quantite_stock=10)
        self.produit_b = ProduitFactory(
            company=self.societe_b, nom='Panneau AUD215 B',
            prix_achat=Decimal('900.00'), quantite_stock=10)

        self.mouvement_a = MouvementStock.objects.create(
            company=self.societe_a, produit=self.produit_a,
            type_mouvement=MouvementStock.TypeMouvement.ENTREE,
            quantite=10, quantite_avant=0, quantite_apres=10,
            reference='MVT-AUD215-A')
        self.mouvement_b = MouvementStock.objects.create(
            company=self.societe_b, produit=self.produit_b,
            type_mouvement=MouvementStock.TypeMouvement.ENTREE,
            quantite=7, quantite_avant=0, quantite_apres=7,
            reference='MVT-AUD215-B')

        self.superuser = UserFactory(
            company=self.societe_a, username='aud215-root-stock',
            is_staff=True, is_superuser=True)
        self.http = Client()
        self.http.force_login(self.superuser)
        self.model_admin = django_admin.site._registry[MouvementStock]

    def _request(self):
        request = RequestFactory().get('/')
        request.user = self.superuser
        return request


class Aud215RegistreLectureSeuleTests(Aud215Base):
    """Le registre ne s'ajoute pas, ne se modifie pas, ne se supprime pas."""

    def test_ajout_refuse(self):
        self.assertFalse(self.model_admin.has_add_permission(self._request()))

    def test_modification_refusee(self):
        self.assertFalse(self.model_admin.has_change_permission(
            self._request(), self.mouvement_a))

    def test_suppression_refusee(self):
        self.assertFalse(self.model_admin.has_delete_permission(
            self._request(), self.mouvement_a))

    def test_action_groupee_de_suppression_retiree(self):
        self.assertNotIn(
            'delete_selected', self.model_admin.get_actions(self._request()))

    def test_ecriture_directe_refusee_meme_hors_formulaire(self):
        with self.assertRaises(PermissionDenied):
            self.model_admin.save_model(
                self._request(), self.mouvement_a, None, True)

    def test_suppression_directe_refusee_meme_hors_formulaire(self):
        with self.assertRaises(PermissionDenied):
            self.model_admin.delete_model(self._request(), self.mouvement_a)
        with self.assertRaises(PermissionDenied):
            self.model_admin.delete_queryset(
                self._request(), MouvementStock.objects.all())

    def test_le_message_nomme_le_chemin_supporte(self):
        self.assertIn('AJUSTEMENT', MOUVEMENT_STOCK_LECTURE_SEULE)
        self.assertIn('LECTURE SEULE', MOUVEMENT_STOCK_LECTURE_SEULE)


class Aud215RegistreHttpTests(Aud215Base):
    """Par le vrai client admin : les URLs d'écriture ne passent plus."""

    def test_url_d_ajout_refusee(self):
        reponse = self.http.get(reverse('admin:stock_mouvementstock_add'))
        self.assertIn(reponse.status_code, (302, 403))

    def test_url_de_modification_refusee(self):
        reponse = self.http.post(
            reverse('admin:stock_mouvementstock_change',
                    args=[self.mouvement_a.pk]),
            {'produit': self.produit_a.pk, 'type_mouvement': 'sortie',
             'quantite': 999})
        self.assertIn(reponse.status_code, (302, 403))
        self.mouvement_a.refresh_from_db()
        self.assertEqual(self.mouvement_a.quantite, 10)
        self.assertEqual(
            self.mouvement_a.type_mouvement,
            MouvementStock.TypeMouvement.ENTREE)

    def test_url_de_suppression_refusee(self):
        reponse = self.http.post(
            reverse('admin:stock_mouvementstock_delete',
                    args=[self.mouvement_a.pk]), {'post': 'yes'})
        self.assertIn(reponse.status_code, (302, 403))
        self.assertTrue(
            MouvementStock.objects.filter(pk=self.mouvement_a.pk).exists())

    def test_la_consultation_reste_possible(self):
        reponse = self.http.get(
            reverse('admin:stock_mouvementstock_changelist'))
        self.assertEqual(reponse.status_code, 200)


class Aud215ScopeSocieteTests(Aud215Base):
    """F10 — le queryset admin est scopé sur la société de l'utilisateur."""

    def test_le_registre_ne_montre_pas_les_mouvements_d_une_autre_societe(self):
        reponse = self.http.get(
            reverse('admin:stock_mouvementstock_changelist'))
        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, 'Panneau AUD215 A')
        self.assertNotContains(reponse, 'Panneau AUD215 B')

        queryset = self.model_admin.get_queryset(self._request())
        self.assertIn(self.mouvement_a, queryset)
        self.assertNotIn(self.mouvement_b, queryset)

    def test_les_produits_sont_scopes(self):
        produit_admin = django_admin.site._registry[Produit]
        queryset = produit_admin.get_queryset(self._request())
        self.assertIn(self.produit_a, queryset)
        self.assertNotIn(self.produit_b, queryset)

    def test_les_categories_sont_scopees(self):
        categorie_a = Categorie.objects.create(
            company=self.societe_a, nom='Catégorie AUD215 A')
        categorie_b = Categorie.objects.create(
            company=self.societe_b, nom='Catégorie AUD215 B')
        queryset = django_admin.site._registry[Categorie].get_queryset(
            self._request())
        self.assertIn(categorie_a, queryset)
        self.assertNotIn(categorie_b, queryset)

    def test_les_fournisseurs_sont_scopes(self):
        fournisseur_a = Fournisseur.objects.create(
            company=self.societe_a, nom='Fournisseur AUD215 A')
        fournisseur_b = Fournisseur.objects.create(
            company=self.societe_b, nom='Fournisseur AUD215 B')
        queryset = django_admin.site._registry[Fournisseur].get_queryset(
            self._request())
        self.assertIn(fournisseur_a, queryset)
        self.assertNotIn(fournisseur_b, queryset)

    def test_un_compte_sans_societe_voit_encore_tout(self):
        """Le mixin est défensif : l'opérateur plateforme n'est pas amputé."""
        operateur = UserFactory(
            company=None, username='aud215-plateforme',
            is_staff=True, is_superuser=True)
        request = RequestFactory().get('/')
        request.user = operateur
        queryset = self.model_admin.get_queryset(request)
        self.assertIn(self.mouvement_a, queryset)
        self.assertIn(self.mouvement_b, queryset)
