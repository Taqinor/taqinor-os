"""
ZFSM4 — Facturer une intervention hors contrat directement.

Couvre :
  * `interventions/{id}/generer-facture/` construit une `ventes.Facture`
    brouillon via `apps.ventes.services.generer_facture_intervention`
    (jamais un import direct des models ventes depuis installations) ;
  * lignes matériel depuis `ConsommationLigne` au prix de VENTE catalogue
    (JAMAIS `prix_achat`) ;
  * ligne main-d'œuvre = durée F15 × taux horaire paramétrable
    (`CompanyProfile.taux_horaire_sav`, réutilisé de XFSM1) ;
  * idempotent : `intervention.facture_id` posé, un second appel renvoie la
    même facture sans en créer une seconde ;
  * sans client résolu sur le chantier → 400 (aucune facture orpheline).

Run :
    python manage.py test apps.installations.tests_zfsm4_facturer_intervention -v2
"""
import itertools
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.installations.models import (
    ConsommationLigne, Installation, Intervention, MaterielConsommation,
)
from apps.parametres.models import CompanyProfile
from apps.stock.models import Produit
from apps.ventes.models import Facture

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations'


def make_company(slug=None, nom=None):
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'zfsm4-co-{n}', defaults={'nom': nom or f'ZFSM4 Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_user(company, role='responsable'):
    return User.objects.create_user(
        username=f'zfsm4-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def make_installation(company, with_client=True):
    n = next(_seq)
    client = None
    if with_client:
        client = Client.objects.create(
            company=company, nom='Client', prenom='ZFSM4',
            email=f'zfsm4-{company.id}-{n}@example.invalid')
    return Installation.objects.create(
        company=company, reference=f'CHT-ZFSM4-{n}', client=client)


def make_produit(company, prix_vente='150.00', prix_achat='80.00'):
    n = next(_seq)
    return Produit.objects.create(
        company=company, nom=f'Panneau {n}', sku=f'ZFSM4-SKU-{n}',
        prix_vente=Decimal(prix_vente), prix_achat=Decimal(prix_achat),
        quantite_stock=10, tva=Decimal('20'))


class TestGenererFactureIntervention(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.inst = make_installation(self.company)
        self.interv = Intervention.objects.create(
            company=self.company, installation=self.inst,
            type_intervention='depannage', created_by=self.user,
            arrivee_site_le=timezone.now() - timedelta(hours=2),
            retour_depot_le=timezone.now())
        self.produit = make_produit(self.company)
        cons = MaterielConsommation.objects.create(
            company=self.company, intervention=self.interv)
        ConsommationLigne.objects.create(
            company=self.company, consommation=cons, produit=self.produit,
            designation=self.produit.nom, quantite_prevue=Decimal('1'),
            quantite_utilisee=Decimal('2'))
        profile = CompanyProfile.get(self.company)
        profile.taux_horaire_sav = Decimal('200')
        profile.save(update_fields=['taux_horaire_sav'])

    def test_generates_draft_facture(self):
        r = self.api.post(
            f'{BASE}/interventions/{self.interv.id}/generer-facture/',
            format='json')
        self.assertEqual(r.status_code, 201, r.content)
        facture = Facture.objects.get(id=r.data['facture_id'])
        self.assertEqual(facture.statut, Facture.Statut.BROUILLON)
        self.assertEqual(facture.client_id, self.inst.client_id)
        self.interv.refresh_from_db()
        self.assertEqual(self.interv.facture_id, facture.id)

    def test_facture_lines_use_prix_vente_never_prix_achat(self):
        r = self.api.post(
            f'{BASE}/interventions/{self.interv.id}/generer-facture/',
            format='json')
        facture = Facture.objects.get(id=r.data['facture_id'])
        lignes_materiel = facture.lignes.filter(produit=self.produit)
        self.assertEqual(lignes_materiel.count(), 1)
        ligne = lignes_materiel.first()
        self.assertEqual(ligne.prix_unitaire, Decimal('150.00'))
        self.assertEqual(ligne.quantite, Decimal('2'))
        self.assertNotEqual(ligne.prix_unitaire, self.produit.prix_achat)

    def test_facture_includes_main_oeuvre_line(self):
        r = self.api.post(
            f'{BASE}/interventions/{self.interv.id}/generer-facture/',
            format='json')
        facture = Facture.objects.get(id=r.data['facture_id'])
        mo_lignes = facture.lignes.filter(designation__icontains="main-d'œuvre")
        self.assertEqual(mo_lignes.count(), 1)
        mo = mo_lignes.first()
        # 2h de durée sur site × 200 MAD/h.
        self.assertEqual(mo.prix_unitaire, Decimal('200'))
        self.assertEqual(mo.quantite, Decimal('2.00'))

    def test_idempotent_second_call_returns_same_facture(self):
        r1 = self.api.post(
            f'{BASE}/interventions/{self.interv.id}/generer-facture/',
            format='json')
        r2 = self.api.post(
            f'{BASE}/interventions/{self.interv.id}/generer-facture/',
            format='json')
        self.assertEqual(r2.status_code, 200, r2.content)
        self.assertTrue(r2.data['deja_existant'])
        self.assertEqual(r1.data['facture_id'], r2.data['facture_id'])
        self.assertEqual(
            Facture.objects.filter(client_id=self.inst.client_id).count(), 1)

    def test_no_client_on_chantier_returns_400(self):
        inst_sans_client = make_installation(self.company, with_client=False)
        interv2 = Intervention.objects.create(
            company=self.company, installation=inst_sans_client,
            type_intervention='depannage', created_by=self.user)
        r = self.api.post(
            f'{BASE}/interventions/{interv2.id}/generer-facture/',
            format='json')
        self.assertEqual(r.status_code, 400)
        self.assertFalse(Facture.objects.filter(
            client_id=None, company=self.company).exists())
