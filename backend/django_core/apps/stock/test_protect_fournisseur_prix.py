"""Supprimer un FOURNISSEUR ne doit jamais effacer ses PRIX D'ACHAT négociés.

Contexte fondateur : `stock.Produit` et `crm.Lead` sont les deux seuls jeux de
données réels de l'ERP, et le prix d'achat fournisseur EST de la donnée
catalogue — saisi/négocié à la main, non reconstructible. Or
`achats.PrixFournisseur.fournisseur` était en CASCADE : un fournisseur ne
portant QUE des prix (aucun bon de commande, aucune facture — donc aucune des
7 FK PROTECT « documents d'achat ») partait SILENCIEUSEMENT avec toute sa
grille tarifaire, aussi bien depuis /admin/ que depuis l'API REST
(`FournisseurViewSet` n'avait aucun `destroy`).

Ce module verrouille la correction sur les DEUX couches :

  * modèle  — `PrixFournisseur.fournisseur` est PROTECT (le collecteur Django
              refuse la suppression tant qu'un tarif existe) ;
  * API     — `FournisseurViewSet.destroy` rattrape `ProtectedError` et
              ARCHIVE (`is_archived = True`), exactement comme
              `ProduitViewSet.destroy` ; `force-delete` refuse en 409 ;
  * admin   — `FournisseurAdmin` REFUSE toute suppression (4 verrous), comme
              `ProduitAdmin`, en nommant le chemin supporté.

Run :
    python manage.py test apps.stock.test_protect_fournisseur_prix -v 2
"""
from decimal import Decimal

from django.contrib import admin as django_admin
from django.contrib.admin.utils import NestedObjects
from django.contrib.messages import get_messages
from django.core.exceptions import PermissionDenied
from django.db import models as dj_models
from django.db.models import ProtectedError
from django.test import Client, RequestFactory, TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.achats.models import PrixFournisseur
from apps.stock.admin import SUPPRESSION_FOURNISSEUR_INTERDITE
from apps.stock.models import (
    ContactFournisseur,
    Fournisseur,
    PalierPrixFournisseur,
    Produit,
)
from testkit.factories import CompanyFactory, ProduitFactory, UserFactory

FOURNISSEURS_URL = '/api/django/stock/fournisseurs/'


class FournisseurPrixBase(TestCase):
    """Un fournisseur porteur d'un prix d'achat négocié + un admin API."""

    def setUp(self):
        super().setUp()
        self.company = CompanyFactory(nom='Catalogue Réel Achats',
                                      slug='catalogue-reel-achats')
        self.produit = ProduitFactory(
            company=self.company, nom='Variateur VEICHI 5,5 kW',
            prix_achat=Decimal('4200.00'))
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='VEICHI Maroc')
        self.prix = PrixFournisseur.objects.create(
            company=self.company, produit=self.produit,
            fournisseur=self.fournisseur, prix_achat=Decimal('3870.50'),
            ref_produit_fournisseur='AC10-T3-R55G')

        self.admin_user = UserFactory(
            company=self.company, username='admin-fournisseur-prix',
            is_staff=True, is_superuser=True)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin_user)}')

    def assert_prix_intact(self):
        """Le tarif négocié survit, à la valeur EXACTE saisie."""
        prix = PrixFournisseur.objects.get(pk=self.prix.pk)
        self.assertEqual(prix.prix_achat, Decimal('3870.50'))
        self.assertEqual(prix.ref_produit_fournisseur, 'AC10-T3-R55G')
        self.assertEqual(prix.fournisseur_id, self.fournisseur.pk)


class TestModelePrixProtege(FournisseurPrixBase):
    """Couche modèle : le collecteur Django refuse la suppression."""

    def test_suppression_fournisseur_refusee_et_prix_conserve(self):
        with self.assertRaises(ProtectedError):
            self.fournisseur.delete()
        self.assertTrue(
            Fournisseur.objects.filter(pk=self.fournisseur.pk).exists(),
            'le fournisseur doit survivre à la tentative de suppression')
        self.assert_prix_intact()

    def test_paliers_de_quantite_conserves(self):
        """XPUR14 — les paliers pendent au tarif : protéger le tarif les
        protège aussi (ils cascadaient avec lui)."""
        palier = PalierPrixFournisseur.objects.create(
            prix_fournisseur=self.prix, qte_min=50, prix=Decimal('3650.00'))
        with self.assertRaises(ProtectedError):
            self.fournisseur.delete()
        self.assertEqual(
            PalierPrixFournisseur.objects.get(pk=palier.pk).prix,
            Decimal('3650.00'))

    def test_politique_on_delete_est_protect(self):
        """Verrou structurel : la politique elle-même ne doit pas régresser."""
        field = PrixFournisseur._meta.get_field('fournisseur')
        self.assertIs(
            field.remote_field.on_delete, dj_models.PROTECT,
            'PrixFournisseur.fournisseur doit rester PROTECT (prix négocié)')

    def test_alterfield_on_delete_n_emet_aucun_sql(self):
        """`on_delete` est un attribut NON-DB : l'`AlterField` CASCADE→PROTECT
        est state-only (aucun SQL), donc strictement réversible et sans perte.

        On rejoue la règle exacte de Django
        (``BaseDatabaseSchemaEditor._field_should_be_altered`` : deconstruct,
        puis retrait des ``non_db_attrs``) plutôt que de la paraphraser.
        """
        self.assertIn('on_delete', dj_models.Field.non_db_attrs)

        avant = dj_models.ForeignKey(
            'stock.Fournisseur', on_delete=dj_models.CASCADE,
            related_name='prix_produits')
        apres = dj_models.ForeignKey(
            'stock.Fournisseur', on_delete=dj_models.PROTECT,
            related_name='prix_produits')
        _, _, args_avant, kwargs_avant = avant.deconstruct()
        _, _, args_apres, kwargs_apres = apres.deconstruct()
        for kwargs in (kwargs_avant, kwargs_apres):
            for attr in dj_models.ForeignKey.non_db_attrs:
                kwargs.pop(attr, None)
        self.assertEqual((args_avant, kwargs_avant), (args_apres, kwargs_apres),
                         'seul on_delete change : aucune colonne à altérer')


class TestApiArchiveAuLieuDeDetruire(FournisseurPrixBase):
    """Couche API : `destroy` archive, ne détruit jamais un prix négocié."""

    def test_destroy_archive_et_conserve_le_prix(self):
        reponse = self.api.delete(f'{FOURNISSEURS_URL}{self.fournisseur.pk}/')

        self.assertEqual(reponse.status_code, 200)
        self.assertTrue(reponse.data['archived'])
        self.assertIn('Prix fournisseur', reponse.data['bloquants'])
        self.assertTrue(
            Fournisseur.objects.get(pk=self.fournisseur.pk).is_archived)
        self.assert_prix_intact()

    def test_archive_masque_de_la_liste_et_reversible(self):
        self.api.delete(f'{FOURNISSEURS_URL}{self.fournisseur.pk}/')

        liste = self.api.get(FOURNISSEURS_URL)
        self.assertEqual(liste.status_code, 200)
        self.assertNotIn(
            self.fournisseur.pk,
            [f['id'] for f in _resultats(liste)],
            'un fournisseur archivé sort des listes par défaut')

        avec_archives = self.api.get(f'{FOURNISSEURS_URL}?show_archived=true')
        self.assertIn(self.fournisseur.pk,
                      [f['id'] for f in _resultats(avec_archives)])

        remise = self.api.patch(
            f'{FOURNISSEURS_URL}{self.fournisseur.pk}/unarchive/')
        self.assertEqual(remise.status_code, 200)
        self.assertFalse(
            Fournisseur.objects.get(pk=self.fournisseur.pk).is_archived)
        self.assert_prix_intact()

    def test_fournisseur_sans_rien_reste_reellement_supprimable(self):
        """La garde reste CIBLÉE : un fournisseur jetable part normalement."""
        jetable = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur ponctuel')

        reponse = self.api.delete(f'{FOURNISSEURS_URL}{jetable.pk}/')

        self.assertEqual(reponse.status_code, 204)
        self.assertFalse(Fournisseur.objects.filter(pk=jetable.pk).exists())
        self.assert_prix_intact()

    def test_force_delete_refuse_409_tant_qu_un_prix_existe(self):
        self.fournisseur.is_archived = True
        self.fournisseur.save(update_fields=['is_archived'])

        reponse = self.api.delete(
            f'{FOURNISSEURS_URL}{self.fournisseur.pk}/force-delete/')

        self.assertEqual(reponse.status_code, 409)
        self.assertIn('Prix fournisseur', reponse.data['bloquants'])
        self.assertTrue(
            Fournisseur.objects.filter(pk=self.fournisseur.pk).exists())
        self.assert_prix_intact()

    def test_force_delete_exige_un_fournisseur_archive(self):
        reponse = self.api.delete(
            f'{FOURNISSEURS_URL}{self.fournisseur.pk}/force-delete/')

        self.assertEqual(reponse.status_code, 400)
        self.assert_prix_intact()

    def test_force_delete_supprime_un_archive_sans_donnee_reelle(self):
        vide = Fournisseur.objects.create(
            company=self.company, nom='Ancien fournisseur', is_archived=True)
        ContactFournisseur.objects.create(
            company=self.company, fournisseur=vide, nom='Contact obsolète')

        reponse = self.api.delete(f'{FOURNISSEURS_URL}{vide.pk}/force-delete/')

        self.assertEqual(reponse.status_code, 200)
        self.assertFalse(Fournisseur.objects.filter(pk=vide.pk).exists())
        self.assert_prix_intact()

    def test_isolation_multi_societe_preservee(self):
        """Un admin d'une autre société ne voit ni n'archive ce fournisseur."""
        autre = CompanyFactory(nom='Autre Société', slug='autre-societe-fp')
        intrus = UserFactory(company=autre, username='intrus-fournisseur-prix',
                             is_staff=True, is_superuser=True)
        client = APIClient()
        client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(intrus)}')

        reponse = client.delete(f'{FOURNISSEURS_URL}{self.fournisseur.pk}/')

        self.assertEqual(reponse.status_code, 404)
        self.assertFalse(
            Fournisseur.objects.get(pk=self.fournisseur.pk).is_archived)
        self.assert_prix_intact()


class TestAdminRefuseLaSuppression(FournisseurPrixBase):
    """Couche admin : mêmes 4 verrous que `ProduitAdmin`, message qui NOMME
    le chemin supporté. L'admin et l'API ne divergent jamais sur ce qui
    compte : NI l'un NI l'autre ne peut détruire un prix négocié."""

    def setUp(self):
        super().setUp()
        self.http = Client()
        self.http.force_login(self.admin_user)
        self.model_admin = django_admin.site._registry[Fournisseur]

    def _request(self):
        request = RequestFactory().get('/')
        request.user = self.admin_user
        return request

    def _tout_intact(self):
        self.assert_prix_intact()
        fournisseur = Fournisseur.objects.get(pk=self.fournisseur.pk)
        # Ni supprimé, NI archivé en douce : l'admin refuse, il n'agit pas.
        self.assertFalse(fournisseur.is_archived)

    def test_has_delete_permission_toujours_false(self):
        request = self._request()
        self.assertFalse(self.model_admin.has_delete_permission(request))
        self.assertFalse(self.model_admin.has_delete_permission(
            request, self.fournisseur))

    def test_action_groupee_delete_selected_retiree(self):
        self.assertNotIn('delete_selected',
                         self.model_admin.get_actions(self._request()))

    def test_delete_view_refuse_avec_message_nommant_l_archivage(self):
        url = reverse('admin:stock_fournisseur_delete',
                      args=[self.fournisseur.pk])
        response = self.http.post(url, {'post': 'yes'})

        self.assertEqual(response.status_code, 302)
        messages = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertEqual(messages, [SUPPRESSION_FOURNISSEUR_INTERDITE])
        self.assertIn('ARCHIVAGE', messages[0])
        self.assertIn('/api/django/stock/fournisseurs/', messages[0])
        self._tout_intact()

    def test_fournisseur_sans_dependant_protege_refuse_aussi(self):
        """Le cas SILENCIEUX : rien ne retient ce fournisseur, la suppression
        admin aurait réussi et emporté contacts/jetons/profil sans un mot."""
        nu = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur nu')
        ContactFournisseur.objects.create(
            company=self.company, fournisseur=nu, nom='Contact')
        collector = NestedObjects(using='default')
        collector.collect([nu])
        self.assertEqual(collector.protected, set())

        url = reverse('admin:stock_fournisseur_delete', args=[nu.pk])
        response = self.http.post(url, {'post': 'yes'})

        self.assertEqual(response.status_code, 302)
        self.assertTrue(Fournisseur.objects.filter(pk=nu.pk).exists())
        self._tout_intact()

    def test_suppression_en_masse_refusee(self):
        url = reverse('admin:stock_fournisseur_changelist')
        response = self.http.post(url, {
            'action': 'delete_selected',
            '_selected_action': [str(self.fournisseur.pk)],
            'post': 'yes',
        })

        self.assertEqual(response.status_code, 200)
        self._tout_intact()

    def test_delete_model_et_delete_queryset_refusent(self):
        request = self._request()
        with self.assertRaises(PermissionDenied):
            self.model_admin.delete_model(request, self.fournisseur)
        with self.assertRaises(PermissionDenied):
            self.model_admin.delete_queryset(
                request, Fournisseur.objects.filter(pk=self.fournisseur.pk))
        self._tout_intact()

    def test_admin_et_api_accordent_sur_le_prix(self):
        """L'invariant commun aux deux couches : le prix négocié survit."""
        with self.assertRaises(PermissionDenied):
            self.model_admin.delete_model(self._request(), self.fournisseur)
        self.assert_prix_intact()

        reponse = self.api.delete(f'{FOURNISSEURS_URL}{self.fournisseur.pk}/')
        self.assertEqual(reponse.status_code, 200)
        self.assert_prix_intact()
        self.assertTrue(
            Fournisseur.objects.get(pk=self.fournisseur.pk).is_archived)

    def test_produit_lie_conserve_son_prix_achat(self):
        """`prix_achat` reste une donnée INTERNE, jamais client-facing — et
        surtout jamais perdue par une suppression de fournisseur."""
        self.assertEqual(
            Produit.objects.get(pk=self.produit.pk).prix_achat,
            Decimal('4200.00'))


def _resultats(reponse):
    """Liste paginée ou non — les deux formes existent selon les réglages."""
    data = reponse.data
    if isinstance(data, dict) and 'results' in data:
        return data['results']
    return data
