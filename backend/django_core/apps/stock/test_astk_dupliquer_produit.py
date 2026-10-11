"""ASTK87 — ``dupliquer`` copie TOUS les champs concrets du produit.

Sonde CAT-3 : un clone de forfait perdait prix_fixe_ht, prix_par_panneau_ht,
unite_stock, role_ci, delai_appro_jours, code_sh, suivi_serie… (constructeur
explicite). La copie est maintenant générique (méta-données Django).
"""
import itertools
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.models import Produit
from apps.stock.models_fiche_technique import FicheTechnique
from apps.stock.views.produit import CHAMPS_DUPLICATION_EXCLUS
from authentication.models import Company, CustomUser as User

_seq = itertools.count(1)


class DupliquerProduitCompletTests(TestCase):
    def setUp(self):
        n = next(_seq)
        self.company = Company.objects.create(
            nom=f'ASTK87 {n}', slug=f'astk87-{n}')
        self.user = User.objects.create_superuser(
            username=f'astk87_admin_{n}', password='x',
            email=f'astk87-{n}@example.test')
        self.user.company = self.company
        self.user.save(update_fields=['company'])
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.source = Produit.objects.create(
            company=self.company, nom='Forfait pose', sku='FORFAIT-1',
            prix_achat=Decimal('1500'), prix_vente=Decimal('2500'),
            quantite_stock=12, prix_fixe_ht=Decimal('2000'),
            prix_par_panneau_ht=Decimal('250'), unite_stock='m',
            role_ci='compteur_injection', delai_appro_jours=7,
            code_sh='8541', suivi_serie=True, tva=Decimal('10'),
            paliers_prix_vente=[{'qte_min': 10, 'prix': '2300'}],
            custom_data={'cle': 'valeur'}, code_barres='6111000000011')

    def _dupliquer(self):
        reponse = self.api.post(
            f'/api/django/stock/produits/{self.source.pk}/dupliquer/',
            {'nom': 'Copie'}, format='json')
        self.assertEqual(reponse.status_code, 201, reponse.content)
        return Produit.objects.get(pk=reponse.json()['id'])

    def test_exclusions_sont_des_champs_reels(self):
        """Une exclusion qui ne désigne plus un champ du modèle est périmée."""
        noms = {f.name for f in Produit._meta.concrete_fields}
        self.assertFalse(
            CHAMPS_DUPLICATION_EXCLUS - noms,
            'exclusions inconnues du modèle Produit')

    def test_exclusions_ensemble_exact(self):
        """ASTK252 — l'ensemble EXACT des exclusions est figé : en ajouter une
        (ex. `tva`) cesserait de copier un champ métier en silence."""
        self.assertEqual(CHAMPS_DUPLICATION_EXCLUS, frozenset({
            'id', 'company', 'nom', 'sku', 'code_barres', 'quantite_stock',
            'is_archived', 'date_creation', 'date_mise_a_jour', 'photo'}))

    def test_clone_copie_tous_les_champs(self):
        clone = self._dupliquer()  # relu depuis la base
        self.source.refresh_from_db()  # comparé à sa forme STOCKÉE

        for champ in Produit._meta.concrete_fields:
            if champ.name in CHAMPS_DUPLICATION_EXCLUS:
                continue
            self.assertEqual(
                getattr(clone, champ.attname),
                getattr(self.source, champ.attname),
                f'champ {champ.name} non copié par dupliquer')
        self.assertEqual(clone.nom, 'Copie')
        self.assertEqual(clone.quantite_stock, 0)
        self.assertFalse(clone.sku)
        self.assertFalse(clone.code_barres)
        self.assertFalse(clone.is_archived)
        self.assertNotEqual(clone.pk, self.source.pk)
        # valeurs de la sonde CAT-3, nommées pour un échec lisible
        self.assertEqual(clone.prix_fixe_ht, Decimal('2000'))
        self.assertEqual(clone.prix_par_panneau_ht, Decimal('250'))
        self.assertEqual(clone.unite_stock, 'm')
        self.assertEqual(clone.role_ci, 'compteur_injection')
        self.assertEqual(clone.delai_appro_jours, 7)
        self.assertEqual(clone.code_sh, '8541')
        self.assertTrue(clone.suivi_serie)

    def test_clone_copie_la_fiche_technique(self):
        FicheTechnique.objects.create(
            company=self.company, produit=self.source,
            pmax_wc=Decimal('550'))

        clone = self._dupliquer()

        fiche = FicheTechnique.objects.get(produit=clone)
        self.assertEqual(fiche.pmax_wc, Decimal('550'))
        self.assertEqual(
            FicheTechnique.objects.filter(produit=self.source).count(), 1)


class HomonymeTests(TestCase):
    """ASTK94 — unarchive et dupliquer passent par la garde d'unicité du nom
    (sonde CAT-11 : IntegrityError 500 sur
    ``stock_produit_company_nom_sans_sku_uniq``)."""

    def setUp(self):
        n = next(_seq)
        self.company = Company.objects.create(
            nom=f'ASTK94 {n}', slug=f'astk94-{n}')
        self.user = User.objects.create_superuser(
            username=f'astk94_admin_{n}', password='x',
            email=f'astk94-{n}@example.test')
        self.user.company = self.company
        self.user.save(update_fields=['company'])
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.source = Produit.objects.create(
            company=self.company, nom='Source', sku='SRC-94',
            prix_vente=Decimal('10'))
        self.archive = Produit.objects.create(
            company=self.company, nom='Frais', prix_vente=Decimal('10'),
            is_archived=True)
        self.actif = Produit.objects.create(
            company=self.company, nom='Frais', prix_vente=Decimal('10'))

    def test_unarchive_homonyme_400(self):
        reponse = self.api.patch(
            f'/api/django/stock/produits/{self.archive.pk}/unarchive/')

        self.assertEqual(reponse.status_code, 400, reponse.content)
        self.assertEqual(
            reponse.json()['nom'], ['Un produit actif de ce nom existe déjà.'])
        self.archive.refresh_from_db()
        self.assertTrue(self.archive.is_archived)

    def test_dupliquer_homonyme_400(self):
        avant = Produit.objects.count()

        reponse = self.api.post(
            f'/api/django/stock/produits/{self.source.pk}/dupliquer/',
            {'nom': 'Frais'}, format='json')

        self.assertEqual(reponse.status_code, 400, reponse.content)
        self.assertIn('nom', reponse.json())
        self.assertEqual(Produit.objects.count(), avant)
