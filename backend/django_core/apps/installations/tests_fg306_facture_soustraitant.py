"""
FG306 / DC34 — Factures & règlements des sous-traitants PAR LA CHAÎNE STANDARD.

Depuis DC34 il n'existe PLUS de modèle AP parallèle : les factures & règlements
des sous-traitants passent par la chaîne comptes-à-payer standard de l'app stock
(``FactureFournisseur`` / ``PaiementFournisseur``), filtrée aux fournisseurs de
type « service ». Les endpoints ``factures-sous-traitant/`` et
``paiements-sous-traitant/`` restent identiques (contrat d'API FG306 préservé).

Couvre :
  * création d'une facture sous-traitant via l'API avec société + ``created_by``
    posés CÔTÉ SERVEUR (la référence FF est posée serveur, anti-collision) ;
  * l'injection de ``company``/``statut`` dans le corps est ignorée ;
  * le ``sous_traitant`` doit appartenir à la MÊME société ET être de type
    « service » (sinon rejet) ;
  * le reflet automatique du statut au fil des paiements (à payer →
    partiellement payée → payée) ;
  * un paiement ne peut pas dépasser le reste à payer ;
  * la suppression d'un paiement rafraîchit le statut de la facture ;
  * le scope société (la société B ne voit pas les factures de A) ;
  * la barrière de rôle (lecture & écriture responsable/admin).

Run :
    python manage.py test apps.installations.tests_fg306_facture_soustraitant -v2
"""
import itertools

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.models import FactureFournisseur, PaiementFournisseur
from apps.stock.services import create_sous_traitant

User = get_user_model()
_seq = itertools.count(1)

BASE = '/api/django/installations'


def make_company(slug=None, nom=None):
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'fg306-co-{n}', defaults={'nom': nom or f'FG306 Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_user(company, role='responsable', username=None):
    return User.objects.create_user(
        username=username or f'fg306-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def make_sous_traitant(company, raison='Terrasol SARL', metier='terrassement'):
    # DC34 — un sous-traitant est un stock.Fournisseur(type='service').
    return create_sous_traitant(company=company, nom=raison, metier=metier)


def _facture_url(fid=None, suffix=''):
    base = f'{BASE}/factures-sous-traitant/'
    if fid is not None:
        base += f'{fid}/'
    return base + suffix


class TestFactureCreation(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.st = make_sous_traitant(self.company)

    def test_create_server_side_company(self):
        r = self.api.post(_facture_url(), {
            'sous_traitant': self.st.id,
            'numero': 'F-2026-001',
            'montant_ht': '40000', 'montant_tva': '8000',
            'montant_ttc': '48000',
        })
        self.assertEqual(r.status_code, 201, r.data)
        fac = FactureFournisseur.objects.get(id=r.data['id'])
        # Société + créateur posés serveur ; passe par la chaîne standard.
        self.assertEqual(fac.company_id, self.company.id)
        self.assertEqual(fac.created_by_id, self.user.id)
        self.assertEqual(fac.fournisseur_id, self.st.id)
        # Statut initial de la chaîne standard = à payer.
        self.assertEqual(fac.statut, FactureFournisseur.Statut.A_PAYER)
        # Référence anti-collision posée serveur (préfixe FF).
        self.assertTrue(fac.reference.startswith('FF'), fac.reference)

    def test_injected_company_statut_ignored(self):
        autre = make_company()
        r = self.api.post(_facture_url(), {
            'company': autre.id,
            'statut': 'payee',
            'sous_traitant': self.st.id,
            'montant_ttc': '1000',
        })
        self.assertEqual(r.status_code, 201, r.data)
        fac = FactureFournisseur.objects.get(id=r.data['id'])
        self.assertEqual(fac.company_id, self.company.id)
        self.assertEqual(fac.statut, FactureFournisseur.Statut.A_PAYER)

    def test_foreign_sous_traitant_rejected(self):
        autre = make_company()
        st_autre = make_sous_traitant(autre)
        r = self.api.post(_facture_url(), {
            'sous_traitant': st_autre.id, 'montant_ttc': '1000',
        })
        self.assertEqual(r.status_code, 400, r.data)

    def test_materiel_fournisseur_rejected(self):
        """DC34 — un fournisseur de type matériel n'est pas un sous-traitant."""
        from apps.stock.models import Fournisseur
        mat = Fournisseur.objects.create(
            company=self.company, nom='Panneaux SARL', type='materiel')
        r = self.api.post(_facture_url(), {
            'sous_traitant': mat.id, 'montant_ttc': '1000',
        })
        self.assertEqual(r.status_code, 400, r.data)


class TestPaiementReflectsStatut(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.st = make_sous_traitant(self.company)
        r = self.api.post(_facture_url(), {
            'sous_traitant': self.st.id, 'montant_ttc': '1000',
        })
        self.fac = FactureFournisseur.objects.get(id=r.data['id'])

    def _pay(self, montant):
        return self.api.post(f'{BASE}/paiements-sous-traitant/', {
            'facture': self.fac.id, 'montant': montant,
        })

    def test_partial_then_full_payment(self):
        r1 = self._pay('400')
        self.assertEqual(r1.status_code, 201, r1.data)
        self.fac.refresh_from_db()
        self.assertEqual(self.fac.statut,
                         FactureFournisseur.Statut.PARTIELLEMENT_PAYEE)

        r2 = self._pay('600')
        self.assertEqual(r2.status_code, 201, r2.data)
        self.fac.refresh_from_db()
        self.assertEqual(self.fac.statut, FactureFournisseur.Statut.PAYEE)

    def test_payment_over_remaining_rejected(self):
        r = self._pay('1500')
        self.assertEqual(r.status_code, 400, r.data)

    def test_delete_payment_reverts_statut(self):
        r = self._pay('1000')
        pid = r.data['id']
        self.fac.refresh_from_db()
        self.assertEqual(self.fac.statut, FactureFournisseur.Statut.PAYEE)
        d = self.api.delete(f'{BASE}/paiements-sous-traitant/{pid}/')
        self.assertEqual(d.status_code, 204)
        self.fac.refresh_from_db()
        self.assertEqual(self.fac.statut, FactureFournisseur.Statut.A_PAYER)


class TestLifecycleAndScope(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.st = make_sous_traitant(self.company)

    def _make_facture(self, montant_ttc='500'):
        r = self.api.post(_facture_url(), {
            'sous_traitant': self.st.id, 'montant_ttc': montant_ttc,
        })
        return FactureFournisseur.objects.get(id=r.data['id'])

    def test_annuler_blocked_when_paid(self):
        fac = self._make_facture()
        PaiementFournisseur.objects.create(
            company=self.company, facture=fac, montant=200)
        r = self.api.post(_facture_url(fac.id, 'annuler/'))
        self.assertEqual(r.status_code, 400, getattr(r, 'data', None))

    def test_annuler_deletes_unpaid(self):
        """DC34 — annuler une facture non réglée la supprime (204)."""
        fac = self._make_facture()
        r = self.api.post(_facture_url(fac.id, 'annuler/'))
        self.assertEqual(r.status_code, 204)
        self.assertFalse(
            FactureFournisseur.objects.filter(id=fac.id).exists())

    def test_scope_isolation(self):
        other = make_company()
        st_o = make_sous_traitant(other)
        FactureFournisseur.objects.create(
            company=other, reference='FF-O-1', fournisseur=st_o,
            montant_ttc=1, statut=FactureFournisseur.Statut.A_PAYER)
        self._make_facture(montant_ttc='1')
        r = self.api.get(_facture_url())
        self.assertEqual(r.status_code, 200, r.data)
        results = r.data['results'] if 'results' in r.data else r.data
        self.assertEqual(len(results), 1)

    def test_only_service_factures_listed(self):
        """DC34 — la liste sous-traitant ne montre QUE les factures de
        fournisseurs de type service (jamais les factures matériel)."""
        from apps.stock.models import Fournisseur
        mat = Fournisseur.objects.create(
            company=self.company, nom='Mat SARL', type='materiel')
        FactureFournisseur.objects.create(
            company=self.company, reference='FF-MAT-1', fournisseur=mat,
            montant_ttc=999, statut=FactureFournisseur.Statut.A_PAYER)
        self._make_facture(montant_ttc='1')
        r = self.api.get(_facture_url())
        results = r.data['results']
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['sous_traitant'], self.st.id)

    def test_read_requires_role(self):
        viewer = make_user(self.company, role='normal')
        api = auth(viewer)
        r = api.get(_facture_url())
        self.assertEqual(r.status_code, 403, r.data)
