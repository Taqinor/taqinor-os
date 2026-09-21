"""Tests XQHS3 — Contrôle qualité à la réception fournisseur + quarantaine.

Couvre :

* le déclenchement (idempotent) des ``ControleReception`` depuis l'événement
  ``core.events.reception_fournisseur_confirmee`` émis par
  ``stock.services.confirm_reception_fournisseur`` ;
* le taux d'échantillonnage et la portée produit/catégorie du plan ;
* le verdict ``refuse`` qui lève automatiquement une NCR (pont XQHS3→XQHS2) ;
* le sélecteur advisory ``reception_controle_ouvert`` (jamais bloquant) ;
* l'isolation entre sociétés.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.qhse.models import ControleReception, NonConformite, PlanControleReception
from apps.qhse.selectors import reception_controle_ouvert
from apps.qhse.services import (
    instancier_controles_reception, plans_actifs_pour_produit,
    statuer_controle_reception,
)
from apps.stock.models import (
    BonCommandeFournisseur, Categorie, Fournisseur, LigneBonCommandeFournisseur,
    LigneReceptionFournisseur, Produit, ReceptionFournisseur,
)
from apps.stock.services import confirm_reception_fournisseur

User = get_user_model()

CONTROLES_URL = '/api/django/qhse/controles-reception/'
PLANS_URL = '/api/django/qhse/plans-controle-reception/'


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth_client(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_categorie(company, nom):
    return Categorie.objects.create(company=company, nom=nom)


def make_produit(company, nom, categorie=None, prix_vente=100):
    return Produit.objects.create(
        company=company, nom=nom, categorie=categorie,
        prix_vente=prix_vente)


def make_fournisseur(company, nom):
    return Fournisseur.objects.create(company=company, nom=nom)


def make_reception_confirmee(company, produit, user, quantite=5):
    fournisseur = make_fournisseur(company, f'Fourn-{produit.id}')
    bc = BonCommandeFournisseur.objects.create(
        company=company, fournisseur=fournisseur,
        reference=f'BC-{produit.id}')
    ligne_cmd = LigneBonCommandeFournisseur.objects.create(
        bon_commande=bc, produit=produit, quantite=quantite,
        prix_achat_unitaire=10)
    reception = ReceptionFournisseur.objects.create(
        company=company, reference=f'REC-{produit.id}', bon_commande=bc)
    LigneReceptionFournisseur.objects.create(
        reception=reception, ligne_commande=ligne_cmd, produit=produit,
        quantite=quantite)
    confirm_reception_fournisseur(reception, user)
    reception.refresh_from_db()
    return reception


# ── Service : instanciation depuis l'événement ──────────────────────────────

class InstancierControlesReceptionTests(TestCase):
    def setUp(self):
        self.company = make_company('co-xqhs3', 'CoXqhs3')
        self.user = make_user(self.company, 'resp-xqhs3')
        self.categorie = make_categorie(self.company, 'Onduleurs')
        self.produit = make_produit(
            self.company, 'Onduleur X', categorie=self.categorie)

    def test_reception_confirmee_ouvre_controle_si_plan_actif(self):
        PlanControleReception.objects.create(
            company=self.company, nom='QC onduleurs', produit=self.produit)
        reception = make_reception_confirmee(
            self.company, self.produit, self.user)
        controles = ControleReception.objects.filter(
            reception_id=reception.id)
        self.assertEqual(controles.count(), 1)
        self.assertEqual(
            controles.first().verdict, ControleReception.Verdict.EN_ATTENTE)

    def test_aucun_plan_aucun_controle(self):
        reception = make_reception_confirmee(
            self.company, self.produit, self.user)
        self.assertEqual(
            ControleReception.objects.filter(
                reception_id=reception.id).count(), 0)

    def test_plan_inactif_ignore(self):
        PlanControleReception.objects.create(
            company=self.company, nom='QC inactif', produit=self.produit,
            actif=False)
        reception = make_reception_confirmee(
            self.company, self.produit, self.user)
        self.assertEqual(
            ControleReception.objects.filter(
                reception_id=reception.id).count(), 0)

    def test_plan_par_categorie_couvre_le_produit(self):
        PlanControleReception.objects.create(
            company=self.company, nom='QC catégorie',
            categorie=self.categorie)
        reception = make_reception_confirmee(
            self.company, self.produit, self.user)
        self.assertEqual(
            ControleReception.objects.filter(
                reception_id=reception.id).count(), 1)

    def test_idempotent_ne_duplique_pas(self):
        PlanControleReception.objects.create(
            company=self.company, nom='QC onduleurs', produit=self.produit)
        reception = make_reception_confirmee(
            self.company, self.produit, self.user)
        # Ré-appel direct du service (simule une seconde émission) :
        # idempotent grâce à la contrainte d'unicité société+réception+plan.
        instancier_controles_reception(reception, self.company)
        self.assertEqual(
            ControleReception.objects.filter(
                reception_id=reception.id).count(), 1)

    def test_plans_actifs_pour_produit_direct(self):
        plan = PlanControleReception.objects.create(
            company=self.company, nom='QC direct', produit=self.produit)
        plans = plans_actifs_pour_produit(self.company, self.produit.id)
        self.assertIn(plan, plans)


# ── Verdict → NCR (pont XQHS3→XQHS2) ────────────────────────────────────────

class StatuerControleReceptionTests(TestCase):
    def setUp(self):
        self.company = make_company('co-xqhs3-verdict', 'CoXqhs3Verdict')
        self.user = make_user(self.company, 'resp-xqhs3-verdict')
        self.produit = make_produit(self.company, 'Panneau Y')
        self.plan = PlanControleReception.objects.create(
            company=self.company, nom='QC panneaux', produit=self.produit)

    def test_verdict_refuse_leve_ncr(self):
        reception = make_reception_confirmee(
            self.company, self.produit, self.user)
        controle = ControleReception.objects.get(reception_id=reception.id)
        statuer_controle_reception(
            controle, ControleReception.Verdict.REFUSE, controleur=self.user)
        controle.refresh_from_db()
        self.assertIsNotNone(controle.non_conformite_id)
        self.assertEqual(
            NonConformite.objects.filter(
                id=controle.non_conformite_id).count(), 1)

    def test_verdict_accepte_ne_leve_pas_ncr(self):
        reception = make_reception_confirmee(
            self.company, self.produit, self.user)
        controle = ControleReception.objects.get(reception_id=reception.id)
        statuer_controle_reception(
            controle, ControleReception.Verdict.ACCEPTE, controleur=self.user)
        controle.refresh_from_db()
        self.assertIsNone(controle.non_conformite_id)

    def test_verdict_invalide_leve_valueerror(self):
        reception = make_reception_confirmee(
            self.company, self.produit, self.user)
        controle = ControleReception.objects.get(reception_id=reception.id)
        with self.assertRaises(ValueError):
            statuer_controle_reception(controle, 'bogus')

    def test_refuse_deux_fois_ne_duplique_pas_ncr(self):
        reception = make_reception_confirmee(
            self.company, self.produit, self.user)
        controle = ControleReception.objects.get(reception_id=reception.id)
        statuer_controle_reception(
            controle, ControleReception.Verdict.REFUSE, controleur=self.user)
        ncr_id_1 = controle.non_conformite_id
        statuer_controle_reception(
            controle, ControleReception.Verdict.REFUSE, controleur=self.user)
        controle.refresh_from_db()
        self.assertEqual(controle.non_conformite_id, ncr_id_1)


# ── Sélecteur advisory ───────────────────────────────────────────────────────

class ReceptionControleOuvertTests(TestCase):
    def setUp(self):
        self.company = make_company('co-xqhs3-adv', 'CoXqhs3Adv')
        self.user = make_user(self.company, 'resp-xqhs3-adv')
        self.produit = make_produit(self.company, 'Batterie Z')
        self.plan = PlanControleReception.objects.create(
            company=self.company, nom='QC batteries', produit=self.produit)

    def test_ouvert_tant_que_verdict_en_attente(self):
        reception = make_reception_confirmee(
            self.company, self.produit, self.user)
        self.assertTrue(reception_controle_ouvert(reception.id))

    def test_ferme_une_fois_statue(self):
        reception = make_reception_confirmee(
            self.company, self.produit, self.user)
        controle = ControleReception.objects.get(reception_id=reception.id)
        statuer_controle_reception(
            controle, ControleReception.Verdict.ACCEPTE, controleur=self.user)
        self.assertFalse(reception_controle_ouvert(reception.id))

    def test_pas_de_controle_pas_ouvert(self):
        self.assertFalse(reception_controle_ouvert(999999))


# ── API ──────────────────────────────────────────────────────────────────────

class ControleReceptionApiTests(TestCase):
    def setUp(self):
        self.company = make_company('co-xqhs3-api', 'CoXqhs3Api')
        self.autre = make_company('co-xqhs3-api-autre', 'CoXqhs3ApiAutre')
        self.user = make_user(self.company, 'resp-xqhs3-api')
        self.client = auth_client(self.user)
        self.produit = make_produit(self.company, 'Structure W')
        self.plan = PlanControleReception.objects.create(
            company=self.company, nom='QC structures', produit=self.produit)

    def test_statuer_action_refuse(self):
        reception = make_reception_confirmee(
            self.company, self.produit, self.user)
        controle = ControleReception.objects.get(reception_id=reception.id)
        resp = self.client.post(
            f'{CONTROLES_URL}{controle.id}/statuer/',
            {'verdict': 'refuse', 'notes': 'Fissures visibles'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['verdict'], 'refuse')
        self.assertIsNotNone(resp.data['non_conformite'])

    def test_statuer_sans_verdict_400(self):
        reception = make_reception_confirmee(
            self.company, self.produit, self.user)
        controle = ControleReception.objects.get(reception_id=reception.id)
        resp = self.client.post(
            f'{CONTROLES_URL}{controle.id}/statuer/', {}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_isolation_societe(self):
        make_reception_confirmee(self.company, self.produit, self.user)
        autre_user = make_user(self.autre, 'resp-xqhs3-api-autre')
        autre_client = auth_client(autre_user)
        resp = autre_client.get(CONTROLES_URL)
        self.assertEqual(resp.status_code, 200)
        data = resp.data
        rows = data['results'] if isinstance(data, dict) and 'results' in data else data
        self.assertEqual(len(rows), 0)

    def test_creation_plan_scoped_company(self):
        resp = self.client.post(PLANS_URL, {
            'nom': 'Nouveau plan',
            'produit': self.produit.id,
            'taux_echantillonnage': 50,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        plan = PlanControleReception.objects.get(pk=resp.data['id'])
        self.assertEqual(plan.company, self.company)
