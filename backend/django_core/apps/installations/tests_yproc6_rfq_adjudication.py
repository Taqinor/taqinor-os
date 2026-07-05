"""
YPROC6 — Adjudication RFQ : l'offre retenue produit le BCF et mémorise le
prix gagnant.

Couvre :
  * retenir une offre à fournisseur CATALOGUE crée le BCF brouillon chez le
    gagnant, lien RFQ→BCF navigable ;
  * les lignes du BCF proviennent de la DA liée (produit/quantité/prix estimé)
    quand elle existe ;
  * sans DA liée, une ligne libre reprend l'objet + le montant HT de l'offre ;
  * la DA liée APPROUVÉE passe `commandee` et reçoit le lien BCF ;
  * le prix gagnant alimente `PrixFournisseur` (comparatif) pour les lignes à
    produit catalogue ;
  * re-adjuger une RFQ déjà liée à un BCF est idempotent (pas de second BCF) ;
  * une offre SANS fournisseur catalogue (nom libre) ne fait que basculer la
    sélection — comportement historique préservé, aucune erreur.

Run :
    python manage.py test apps.installations.tests_yproc6_rfq_adjudication -v2
"""
import itertools

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.installations.models import (
    RFQ, RFQOffre, DemandeAchat, DemandeAchatLigne,
)

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations'


def make_company(slug=None, nom=None):
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'yproc6-co-{n}', defaults={'nom': nom or f'Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_user(company, role='responsable', username=None):
    return User.objects.create_user(
        username=username or f'yproc6-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def make_produit(company, nom='Panneau 550W'):
    from apps.stock.models import Produit
    return Produit.objects.create(
        company=company, nom=nom, prix_vente=1500, prix_achat=1000)


def make_fournisseur(company, nom='SolarImport'):
    from apps.stock.models import Fournisseur
    return Fournisseur.objects.create(company=company, nom=nom)


class AdjudicationAvecDATests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.fournisseur = make_fournisseur(self.company)
        self.produit = make_produit(self.company)
        self.da = DemandeAchat.objects.create(
            company=self.company, reference=f'DA-{next(_seq)}',
            objet='Chantier Y', statut=DemandeAchat.Statut.APPROUVEE,
            created_by=self.user)
        DemandeAchatLigne.objects.create(
            demande=self.da, produit=self.produit, quantite=8,
            prix_estime=1100)
        self.rfq = RFQ.objects.create(
            company=self.company, reference=f'RFQ-{next(_seq)}',
            objet='Consultation', demande=self.da, created_by=self.user)
        self.offre = RFQOffre.objects.create(
            company=self.company, rfq=self.rfq, fournisseur=self.fournisseur,
            montant_ht=8800)

    def test_retenir_cree_bcf_depuis_lignes_da(self):
        r = self.api.post(f'{BASE}/rfq/{self.rfq.id}/retenir/',
                          {'offre': self.offre.id})
        self.assertEqual(r.status_code, 200, r.data)
        self.rfq.refresh_from_db()
        self.assertIsNotNone(self.rfq.bon_commande_id)
        self.assertEqual(self.rfq.statut, RFQ.Statut.CLOTUREE)
        bon = self.rfq.bon_commande
        self.assertEqual(bon.fournisseur_id, self.fournisseur.id)
        ligne = bon.lignes.first()
        self.assertEqual(ligne.produit_id, self.produit.id)
        self.assertEqual(ligne.quantite, 8)
        self.assertEqual(float(ligne.prix_achat_unitaire), 1100.0)

    def test_da_passe_commandee_avec_lien(self):
        self.api.post(f'{BASE}/rfq/{self.rfq.id}/retenir/',
                      {'offre': self.offre.id})
        self.da.refresh_from_db()
        self.rfq.refresh_from_db()
        self.assertEqual(self.da.statut, DemandeAchat.Statut.COMMANDEE)
        self.assertIsNotNone(self.rfq.bon_commande_id)
        self.assertEqual(self.da.bon_commande_id, self.rfq.bon_commande_id)

    def test_prix_gagnant_alimente_prix_fournisseur(self):
        from apps.stock.models import PrixFournisseur
        self.api.post(f'{BASE}/rfq/{self.rfq.id}/retenir/',
                      {'offre': self.offre.id})
        pf = PrixFournisseur.objects.filter(
            produit=self.produit, fournisseur=self.fournisseur).first()
        self.assertIsNotNone(pf)
        self.assertEqual(float(pf.prix_achat), 1100.0)

    def test_readjuger_idempotent_pas_de_second_bcf(self):
        self.api.post(f'{BASE}/rfq/{self.rfq.id}/retenir/',
                      {'offre': self.offre.id})
        self.rfq.refresh_from_db()
        bcf_id_1 = self.rfq.bon_commande_id
        # Une seconde offre catalogue (perdante) rappelle retenir : la RFQ
        # est déjà liée à un BCF, aucun second BCF n'est créé.
        offre2 = RFQOffre.objects.create(
            company=self.company, rfq=self.rfq, fournisseur=self.fournisseur,
            montant_ht=9500)
        self.api.post(f'{BASE}/rfq/{self.rfq.id}/retenir/',
                      {'offre': offre2.id})
        self.rfq.refresh_from_db()
        self.assertEqual(self.rfq.bon_commande_id, bcf_id_1)
        from apps.stock.models import BonCommandeFournisseur
        self.assertEqual(
            BonCommandeFournisseur.objects.filter(
                company=self.company).count(), 1)


class AdjudicationSansDATests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.fournisseur = make_fournisseur(self.company)
        self.rfq = RFQ.objects.create(
            company=self.company, reference=f'RFQ-{next(_seq)}',
            objet='Prestation ponctuelle', created_by=self.user)
        self.offre = RFQOffre.objects.create(
            company=self.company, rfq=self.rfq, fournisseur=self.fournisseur,
            montant_ht=3000)

    def test_retenir_sans_da_cree_ligne_libre(self):
        r = self.api.post(f'{BASE}/rfq/{self.rfq.id}/retenir/',
                          {'offre': self.offre.id})
        self.assertEqual(r.status_code, 200, r.data)
        self.rfq.refresh_from_db()
        bon = self.rfq.bon_commande
        self.assertIsNotNone(bon)
        ligne = bon.lignes.first()
        self.assertIsNone(ligne.produit_id)
        self.assertEqual(float(ligne.prix_achat_unitaire), 3000.0)


class OffreNomLibreCompatibiliteTests(TestCase):
    """Comportement historique préservé : une offre sans fournisseur
    catalogue (nom libre) ne fait QUE basculer la sélection, jamais
    d'adjudication ni d'erreur — même scénario que TestRetenir (FG311)."""

    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.rfq = RFQ.objects.create(
            company=self.company, reference=f'RFQ-{next(_seq)}', objet='X',
            created_by=self.user)
        self.o1 = RFQOffre.objects.create(
            company=self.company, rfq=self.rfq,
            fournisseur_nom_libre='A', montant_ht=100)
        self.o2 = RFQOffre.objects.create(
            company=self.company, rfq=self.rfq,
            fournisseur_nom_libre='B', montant_ht=200)

    def test_bascule_sans_adjudication(self):
        r1 = self.api.post(f'{BASE}/rfq/{self.rfq.id}/retenir/',
                           {'offre': self.o2.id})
        self.assertEqual(r1.status_code, 200, r1.data)
        self.rfq.refresh_from_db()
        self.assertIsNone(self.rfq.bon_commande_id)
        self.assertEqual(self.rfq.statut, RFQ.Statut.BROUILLON)
        r2 = self.api.post(f'{BASE}/rfq/{self.rfq.id}/retenir/',
                           {'offre': self.o1.id})
        self.assertEqual(r2.status_code, 200, r2.data)
        self.o1.refresh_from_db()
        self.o2.refresh_from_db()
        self.assertTrue(self.o1.retenue)
        self.assertFalse(self.o2.retenue)
