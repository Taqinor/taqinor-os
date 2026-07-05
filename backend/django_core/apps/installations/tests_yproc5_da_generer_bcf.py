"""
YPROC5 — Demande d'achat approuvée → génération du BCF (conversion + lien
bidirectionnel).

Couvre :
  * générer-bcf sur une DA approuvée crée un BCF brouillon avec les bonnes
    lignes/prix (produit catalogue) ;
  * une ligne sans produit catalogue est reportée en désignation libre
    (jamais ignorée) ;
  * le lien est bidirectionnel (DA.bon_commande posé, BCF navigable) et la DA
    passe `commandee` ;
  * re-générer sur une DA déjà liée est refusé (idempotence) ;
  * une DA non approuvée est refusée ;
  * sans fournisseur (ni suggéré ni fourni) → 400 ;
  * isolation multi-tenant (fournisseur d'une autre société refusé).

Run :
    python manage.py test apps.installations.tests_yproc5_da_generer_bcf -v2
"""
import itertools

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.installations.models import DemandeAchat, DemandeAchatLigne

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations'


def make_company(slug=None, nom=None):
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'yproc5-co-{n}', defaults={'nom': nom or f'Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_user(company, role='responsable', username=None):
    return User.objects.create_user(
        username=username or f'yproc5-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def make_produit(company, nom='Panneau 550W'):
    from apps.stock.models import Produit
    return Produit.objects.create(
        company=company, nom=nom, prix_vente=1500, prix_achat=1000)


def make_fournisseur(company, nom='SolarImport'):
    from apps.stock.models import Fournisseur
    return Fournisseur.objects.create(company=company, nom=nom)


def make_da_approuvee(company, user, lignes=None):
    da = DemandeAchat.objects.create(
        company=company, reference=f'DA-{next(_seq)}', objet='Chantier X',
        statut=DemandeAchat.Statut.APPROUVEE, created_by=user)
    for produit, designation, qte, prix in (lignes or []):
        DemandeAchatLigne.objects.create(
            demande=da, produit=produit, designation=designation,
            quantite=qte, prix_estime=prix)
    return da


class GenererBcfTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.fournisseur = make_fournisseur(self.company)
        self.produit = make_produit(self.company)

    def test_generer_bcf_cree_bon_avec_lignes(self):
        da = make_da_approuvee(self.company, self.user, lignes=[
            (self.produit, None, 10, 1200),
        ])
        r = self.api.post(
            f'{BASE}/demandes-achat/{da.id}/generer-bcf/',
            {'fournisseur': self.fournisseur.id})
        self.assertEqual(r.status_code, 200, r.data)
        da.refresh_from_db()
        self.assertEqual(da.statut, DemandeAchat.Statut.COMMANDEE)
        self.assertIsNotNone(da.bon_commande_id)
        bon = da.bon_commande
        self.assertEqual(bon.fournisseur_id, self.fournisseur.id)
        self.assertEqual(bon.lignes.count(), 1)
        ligne = bon.lignes.first()
        self.assertEqual(ligne.produit_id, self.produit.id)
        self.assertEqual(ligne.quantite, 10)
        self.assertEqual(float(ligne.prix_achat_unitaire), 1200.0)

    def test_ligne_libre_reportee_en_designation(self):
        da = make_da_approuvee(self.company, self.user, lignes=[
            (None, 'Transport spécial', 1, 500),
        ])
        r = self.api.post(
            f'{BASE}/demandes-achat/{da.id}/generer-bcf/',
            {'fournisseur': self.fournisseur.id})
        self.assertEqual(r.status_code, 200, r.data)
        da.refresh_from_db()
        ligne = da.bon_commande.lignes.first()
        self.assertIsNone(ligne.produit_id)
        self.assertEqual(ligne.designation, 'Transport spécial')
        self.assertTrue(ligne.sans_stock)

    def test_utilise_fournisseur_suggere_par_defaut(self):
        da = make_da_approuvee(self.company, self.user, lignes=[
            (self.produit, None, 2, 999),
        ])
        da.fournisseur_suggere = self.fournisseur
        da.save(update_fields=['fournisseur_suggere'])
        r = self.api.post(f'{BASE}/demandes-achat/{da.id}/generer-bcf/', {})
        self.assertEqual(r.status_code, 200, r.data)
        da.refresh_from_db()
        self.assertEqual(da.bon_commande.fournisseur_id, self.fournisseur.id)

    def test_regenerer_refuse_deja_lie(self):
        da = make_da_approuvee(self.company, self.user, lignes=[
            (self.produit, None, 2, 999),
        ])
        r1 = self.api.post(
            f'{BASE}/demandes-achat/{da.id}/generer-bcf/',
            {'fournisseur': self.fournisseur.id})
        self.assertEqual(r1.status_code, 200, r1.data)
        r2 = self.api.post(
            f'{BASE}/demandes-achat/{da.id}/generer-bcf/',
            {'fournisseur': self.fournisseur.id})
        self.assertEqual(r2.status_code, 400, r2.data)

    def test_da_non_approuvee_refusee(self):
        da = DemandeAchat.objects.create(
            company=self.company, reference=f'DA-{next(_seq)}',
            objet='Non approuvée', statut=DemandeAchat.Statut.SOUMISE,
            created_by=self.user)
        r = self.api.post(
            f'{BASE}/demandes-achat/{da.id}/generer-bcf/',
            {'fournisseur': self.fournisseur.id})
        self.assertEqual(r.status_code, 400, r.data)

    def test_sans_fournisseur_400(self):
        da = make_da_approuvee(self.company, self.user, lignes=[
            (self.produit, None, 2, 999),
        ])
        r = self.api.post(f'{BASE}/demandes-achat/{da.id}/generer-bcf/', {})
        self.assertEqual(r.status_code, 400, r.data)

    def test_sans_lignes_400(self):
        da = make_da_approuvee(self.company, self.user, lignes=[])
        r = self.api.post(
            f'{BASE}/demandes-achat/{da.id}/generer-bcf/',
            {'fournisseur': self.fournisseur.id})
        self.assertEqual(r.status_code, 400, r.data)

    def test_fournisseur_autre_societe_rejete(self):
        autre = make_company()
        fournisseur_o = make_fournisseur(autre, 'Autre')
        da = make_da_approuvee(self.company, self.user, lignes=[
            (self.produit, None, 2, 999),
        ])
        r = self.api.post(
            f'{BASE}/demandes-achat/{da.id}/generer-bcf/',
            {'fournisseur': fournisseur_o.id})
        self.assertEqual(r.status_code, 400, r.data)
