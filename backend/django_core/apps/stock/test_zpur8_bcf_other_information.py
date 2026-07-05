"""ZPUR8 — Champs « Other Information » Odoo au niveau du BCF : acheteur,
référence fournisseur, note de bas de page + report des défauts
incoterm/conditions de paiement du fournisseur.

Couvre :
  * un BCF créé sans acheteur explicite prend created_by par défaut ;
  * les défauts fournisseur (incoterm/conditions de paiement) sont reportés
    au document à la création, sans écraser une valeur déjà fournie ;
  * les champs s'impriment sur le PDF (contexte de rendu) ;
  * l'analyse achats peut grouper par acheteur (XPUR24) ;
  * migration additive : un BCF existant (créé sans ces champs) reste
    inchangé (valeurs vides).

Run:
    python manage.py test apps.stock.test_zpur8_bcf_other_information -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role
from apps.stock.models import (
    BonCommandeFournisseur, Fournisseur, LigneBonCommandeFournisseur, Produit,
)
from apps.stock.services import (
    default_other_information_bcf, depenses_achats_par_periode,
)
from apps.stock.utils.pdf_fournisseur import build_bcf_context

User = get_user_model()


def _company(slug):
    return Company.objects.create(nom=slug, slug=slug)


def _user(company, username, permissions=None):
    role = Role.objects.create(
        company=company, nom=f'r-{username}', permissions=permissions or [])
    return User.objects.create_user(
        username=username, password='x', company=company, role=role,
        role_legacy='responsable')


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Zpur8Base(TestCase):
    def setUp(self):
        self.company = _company('zpur8-co')
        self.user = _user(
            self.company, 'zpur8-user',
            permissions=['stock_modifier', 'stock_voir'])
        self.api = _api(self.user)
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur ZPUR8',
            incoterm='FOB', delai_paiement_jours=60, fin_de_mois=True)
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau ZPUR8', sku='PAN-ZPUR8',
            prix_vente=Decimal('2000'), prix_achat=Decimal('1000'))


class TestCreationViaApi(Zpur8Base):
    def test_acheteur_defaut_created_by(self):
        payload = {
            'fournisseur': self.fournisseur.id,
            'lignes': [{
                'produit': self.produit.id, 'quantite': 5,
                'prix_achat_unitaire': '1000',
            }],
        }
        url = '/api/django/stock/bons-commande-fournisseur/'
        resp = self.api.post(url, payload, format='json')
        self.assertEqual(resp.status_code, 201)
        bc = BonCommandeFournisseur.objects.get(pk=resp.data['id'])
        self.assertEqual(bc.acheteur_id, self.user.id)

    def test_incoterm_et_conditions_reportes_a_la_creation(self):
        payload = {
            'fournisseur': self.fournisseur.id,
            'lignes': [{
                'produit': self.produit.id, 'quantite': 5,
                'prix_achat_unitaire': '1000',
            }],
        }
        url = '/api/django/stock/bons-commande-fournisseur/'
        resp = self.api.post(url, payload, format='json')
        self.assertEqual(resp.status_code, 201)
        bc = BonCommandeFournisseur.objects.get(pk=resp.data['id'])
        self.assertEqual(bc.incoterm, 'FOB')
        self.assertEqual(bc.conditions_paiement, '60 jours fin de mois')

    def test_acheteur_explicite_non_ecrase(self):
        autre = _user(self.company, 'zpur8-autre-acheteur')
        payload = {
            'fournisseur': self.fournisseur.id,
            'acheteur': autre.id,
            'lignes': [{
                'produit': self.produit.id, 'quantite': 5,
                'prix_achat_unitaire': '1000',
            }],
        }
        url = '/api/django/stock/bons-commande-fournisseur/'
        resp = self.api.post(url, payload, format='json')
        self.assertEqual(resp.status_code, 201)
        bc = BonCommandeFournisseur.objects.get(pk=resp.data['id'])
        self.assertEqual(bc.acheteur_id, autre.id)


class TestDefaultOtherInformationBcf(Zpur8Base):
    def test_ne_jamais_ecraser_valeur_existante(self):
        bc = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-ZPUR8-0001',
            fournisseur=self.fournisseur, incoterm='EXW',
            conditions_paiement='comptant')
        default_other_information_bcf(bc)
        bc.refresh_from_db()
        self.assertEqual(bc.incoterm, 'EXW')
        self.assertEqual(bc.conditions_paiement, 'comptant')

    def test_sans_fournisseur_no_op(self):
        # Un BCF ne peut pas exister sans fournisseur (PROTECT non-nullable) —
        # ce test couvre le garde no-op du service directement.
        bc = BonCommandeFournisseur(
            company=self.company, reference='BCF-ZPUR8-NOFOURN')
        bc.fournisseur_id = None
        default_other_information_bcf(bc)  # ne lève jamais d'exception
        self.assertIsNone(bc.incoterm)

    def test_sans_delai_paiement_conditions_vides(self):
        fournisseur_sans_delai = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur ZPUR8 sans délai')
        bc = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-ZPUR8-0002',
            fournisseur=fournisseur_sans_delai)
        default_other_information_bcf(bc)
        bc.refresh_from_db()
        self.assertEqual(bc.conditions_paiement, None)


class TestRenduPdf(Zpur8Base):
    def test_contexte_pdf_contient_other_information(self):
        bc = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-ZPUR8-0003',
            fournisseur=self.fournisseur, acheteur=self.user,
            ref_fournisseur='CMD-FOURN-42', incoterm='CIF',
            conditions_paiement='30 jours', note_bas_page='Livraison 8h-17h.')
        LigneBonCommandeFournisseur.objects.create(
            bon_commande=bc, produit=self.produit, quantite=5,
            prix_achat_unitaire=Decimal('1000'))
        context = build_bcf_context(bc)
        self.assertIn(self.user.username, context['acheteur_nom'])
        self.assertEqual(context['ref_fournisseur'], 'CMD-FOURN-42')
        self.assertEqual(context['incoterm'], 'CIF')
        self.assertEqual(context['conditions_paiement'], '30 jours')
        self.assertEqual(context['note_bas_page'], 'Livraison 8h-17h.')

    def test_contexte_pdf_vide_sans_other_information(self):
        bc = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-ZPUR8-0004',
            fournisseur=self.fournisseur)
        LigneBonCommandeFournisseur.objects.create(
            bon_commande=bc, produit=self.produit, quantite=5,
            prix_achat_unitaire=Decimal('1000'))
        context = build_bcf_context(bc)
        self.assertEqual(context['acheteur_nom'], '')
        self.assertEqual(context['ref_fournisseur'], '')


class TestAnalyseAchatsParAcheteur(Zpur8Base):
    def test_depenses_groupees_par_acheteur(self):
        bc = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-ZPUR8-0005',
            fournisseur=self.fournisseur, acheteur=self.user)
        LigneBonCommandeFournisseur.objects.create(
            bon_commande=bc, produit=self.produit, quantite=5,
            prix_achat_unitaire=Decimal('1000'))
        result = depenses_achats_par_periode(self.company)
        acheteurs = {e['acheteur'] for e in result['par_acheteur']}
        self.assertIn(self.user.username, acheteurs)

    def test_bcf_sans_acheteur_groupe_sous_tiret(self):
        bc = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-ZPUR8-0006',
            fournisseur=self.fournisseur)
        LigneBonCommandeFournisseur.objects.create(
            bon_commande=bc, produit=self.produit, quantite=5,
            prix_achat_unitaire=Decimal('1000'))
        result = depenses_achats_par_periode(self.company)
        acheteurs = {e['acheteur'] for e in result['par_acheteur']}
        self.assertIn('—', acheteurs)


class TestMigrationAdditive(Zpur8Base):
    def test_bcf_existant_sans_champs_reste_vide(self):
        bc = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-ZPUR8-0007',
            fournisseur=self.fournisseur)
        self.assertIsNone(bc.acheteur_id)
        self.assertIsNone(bc.ref_fournisseur)
        self.assertIsNone(bc.note_bas_page)
        self.assertIsNone(bc.incoterm)
        self.assertIsNone(bc.conditions_paiement)
        self.assertEqual(bc.nb_relances, 0)
