"""
FG312 — Paliers d'approbation de BCF par seuil.

Couvre :
  * configuration du seuil par société (écriture Administrateur seulement) ;
  * le palier requis : ≤ seuil → Responsable suffit ; > seuil → Admin requis ;
  * l'action `approuver` : un Responsable peut approuver sous le seuil, mais est
    REFUSÉ (403) au-dessus ; un Administrateur passe dans les deux cas ;
  * sans seuil configuré, le palier requis est Admin (prudence) ;
  * la société et l'approbateur sont posés serveur, montant figé ;
  * un BCF d'une autre société est rejeté (404) ;
  * idempotence (update_or_create par BCF).

Run :
    python manage.py test apps.installations.tests_fg312_approbation_bcf -v2
"""
import itertools

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.installations.models import SeuilApprobationBCF, ApprobationBCF

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations'


def make_company(slug=None, nom=None):
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'fg312-co-{n}', defaults={'nom': nom or f'FG312 Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_user(company, role='responsable', username=None):
    return User.objects.create_user(
        username=username or f'fg312-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def make_bcf_with_line(company, prix_unitaire, quantite=1):
    """Crée un BCF + une ligne pour que `total_achat` = prix × quantité."""
    from apps.stock.models import (
        Fournisseur, Produit, BonCommandeFournisseur,
        LigneBonCommandeFournisseur,
    )
    n = next(_seq)
    f = Fournisseur.objects.create(company=company, nom=f'Four-{n}')
    p = Produit.objects.create(
        company=company, nom=f'Prod-{n}', prix_vente=1, prix_achat=0)
    bcf = BonCommandeFournisseur.objects.create(
        company=company, reference=f'BCF-{n}', fournisseur=f)
    LigneBonCommandeFournisseur.objects.create(
        bon_commande=bcf, produit=p, quantite=quantite,
        prix_achat_unitaire=prix_unitaire)
    return bcf


class TestSeuilConfig(TestCase):
    def setUp(self):
        self.company = make_company()

    def test_admin_can_set_seuil(self):
        admin = make_user(self.company, role='admin')
        api = auth(admin)
        r = api.post(f'{BASE}/seuils-approbation-bcf/',
                     {'seuil_responsable': '50000'})
        self.assertEqual(r.status_code, 201, r.data)
        s = SeuilApprobationBCF.objects.get(id=r.data['id'])
        self.assertEqual(s.company_id, self.company.id)

    def test_responsable_cannot_set_seuil(self):
        resp = make_user(self.company, role='responsable')
        api = auth(resp)
        r = api.post(f'{BASE}/seuils-approbation-bcf/',
                     {'seuil_responsable': '50000'})
        self.assertEqual(r.status_code, 403, r.data)


class TestApprobation(TestCase):
    def setUp(self):
        self.company = make_company()
        self.admin = make_user(self.company, role='admin')
        self.resp = make_user(self.company, role='responsable')
        SeuilApprobationBCF.objects.create(
            company=self.company, seuil_responsable=50000, actif=True)

    def test_responsable_approves_below_threshold(self):
        bcf = make_bcf_with_line(self.company, prix_unitaire=10000, quantite=1)
        api = auth(self.resp)
        r = api.post(f'{BASE}/approbations-bcf/approuver/', {'bcf': bcf.id})
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['palier'], 'responsable')
        appr = ApprobationBCF.objects.get(bcf_id=bcf.id)
        self.assertEqual(appr.approuve_par_id, self.resp.id)
        self.assertEqual(float(appr.montant_approuve), 10000.0)

    def test_responsable_blocked_above_threshold(self):
        bcf = make_bcf_with_line(self.company, prix_unitaire=80000, quantite=1)
        api = auth(self.resp)
        r = api.post(f'{BASE}/approbations-bcf/approuver/', {'bcf': bcf.id})
        self.assertEqual(r.status_code, 403, r.data)
        self.assertFalse(ApprobationBCF.objects.filter(bcf_id=bcf.id).exists())

    def test_admin_approves_above_threshold(self):
        bcf = make_bcf_with_line(self.company, prix_unitaire=80000, quantite=1)
        api = auth(self.admin)
        r = api.post(f'{BASE}/approbations-bcf/approuver/', {'bcf': bcf.id})
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['palier'], 'admin')

    def test_foreign_bcf_rejected(self):
        other = make_company()
        bcf_o = make_bcf_with_line(other, prix_unitaire=1000, quantite=1)
        api = auth(self.admin)
        r = api.post(f'{BASE}/approbations-bcf/approuver/', {'bcf': bcf_o.id})
        self.assertEqual(r.status_code, 404, r.data)

    def test_idempotent_reapproval(self):
        bcf = make_bcf_with_line(self.company, prix_unitaire=1000, quantite=1)
        api = auth(self.admin)
        api.post(f'{BASE}/approbations-bcf/approuver/', {'bcf': bcf.id})
        api.post(f'{BASE}/approbations-bcf/approuver/', {'bcf': bcf.id})
        self.assertEqual(
            ApprobationBCF.objects.filter(bcf_id=bcf.id).count(), 1)


class TestNoSeuilDefaultsAdmin(TestCase):
    def setUp(self):
        self.company = make_company()
        self.resp = make_user(self.company, role='responsable')
        self.admin = make_user(self.company, role='admin')

    def test_no_seuil_requires_admin(self):
        bcf = make_bcf_with_line(self.company, prix_unitaire=100, quantite=1)
        # Responsable refusé en l'absence de seuil (défaut prudent = admin).
        r = auth(self.resp).post(
            f'{BASE}/approbations-bcf/approuver/', {'bcf': bcf.id})
        self.assertEqual(r.status_code, 403, r.data)
        # Admin passe.
        r = auth(self.admin).post(
            f'{BASE}/approbations-bcf/approuver/', {'bcf': bcf.id})
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['palier'], 'admin')
