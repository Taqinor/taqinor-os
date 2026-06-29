"""
FG77 — Contrôle de préparation avant pose (readiness).

`chantiers/{id}/readiness` agrège le manque matériel (besoin vs stock), l'état
du dossier réglementaire loi 82-21 et la date de pose planifiée en une checklist
+ un verdict « prêt / non prêt ». ADVISORY : ne bloque aucun changement de
statut.

Run :
    python manage.py test apps.installations.tests_fg77_readiness -v2
"""
import itertools
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client, Lead
from apps.ventes.models import Devis, LigneDevis
from apps.stock.models import Produit
from apps.installations.models import Installation
from apps.installations.services import (
    create_installation_from_devis, compute_chantier_readiness,
)

User = get_user_model()
_seq = itertools.count(1)


def make_company(slug=None, nom=None):
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'fg77-co-{n}', defaults={'nom': nom or f'FG77 Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_produit(company, nom, stock):
    n = next(_seq)
    return Produit.objects.create(
        company=company, nom=nom, sku=f'SKU-{company.id}-{n}',
        prix_vente=Decimal('100'), quantite_stock=stock)


def make_chantier(company, user, lines):
    """lines = [(produit, quantite), ...]."""
    n = next(_seq)
    client = Client.objects.create(
        company=company, nom='Site', prenom='Client',
        email=f'fg77-{company.id}-{n}@example.invalid')
    lead = Lead.objects.create(
        company=company, nom='Site', prenom='Client', stage='SIGNED',
        type_installation='residentiel')
    devis = Devis.objects.create(
        company=company, reference=f'DEV-FG77-{company.id}-{n}', client=client,
        lead=lead, statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20'),
        mode_installation='residentiel')
    for produit, qte in lines:
        LigneDevis.objects.create(
            devis=devis, produit=produit, designation=produit.nom,
            quantite=Decimal(str(qte)), prix_unitaire=Decimal('100'))
    inst, _ = create_installation_from_devis(devis, user, company)
    return inst


def _check(res, cle):
    return next(c for c in res['checks'] if c['cle'] == cle)


class TestFG77Readiness(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='fg77_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = auth(self.user)

    def test_ready_when_stock_dossier_planning_ok(self):
        """Tout disponible, dossier non concerné, date planifiée → prêt."""
        panneau = make_produit(self.company, 'Panneau', stock=50)
        inst = make_chantier(self.company, self.user, [(panneau, 10)])
        inst.date_pose_prevue = '2026-07-01'
        inst.save(update_fields=['date_pose_prevue'])
        res = compute_chantier_readiness(inst)
        self.assertTrue(res['pret'])
        self.assertEqual(_check(res, 'materiel')['statut'], 'ok')
        self.assertEqual(_check(res, 'dossier')['statut'], 'ok')
        self.assertEqual(_check(res, 'planning')['statut'], 'ok')

    def test_material_shortfall_blocks(self):
        """Stock insuffisant → manque matériel bloquant, non prêt."""
        panneau = make_produit(self.company, 'Panneau', stock=3)
        inst = make_chantier(self.company, self.user, [(panneau, 10)])
        res = compute_chantier_readiness(inst)
        self.assertFalse(res['pret'])
        self.assertEqual(_check(res, 'materiel')['statut'], 'bloquant')
        self.assertEqual(res['materiel']['nb_manques'], 1)
        self.assertEqual(res['materiel']['manques'][0]['designation'], 'Panneau')

    def test_dossier_required_not_approved_blocks(self):
        """Régime requis + dossier non approuvé → bloquant."""
        panneau = make_produit(self.company, 'Panneau', stock=50)
        inst = make_chantier(self.company, self.user, [(panneau, 10)])
        inst.regime_8221 = Installation.Regime8221.DECLARATION_BT
        inst.dossier_statut = Installation.DossierStatut.A_DEPOSER
        inst.save(update_fields=['regime_8221', 'dossier_statut'])
        res = compute_chantier_readiness(inst)
        self.assertFalse(res['pret'])
        self.assertEqual(_check(res, 'dossier')['statut'], 'bloquant')
        self.assertTrue(res['dossier']['requis'])
        self.assertFalse(res['dossier']['ok'])

    def test_dossier_required_approved_ok(self):
        """Régime requis mais dossier approuvé → ok."""
        panneau = make_produit(self.company, 'Panneau', stock=50)
        inst = make_chantier(self.company, self.user, [(panneau, 10)])
        inst.regime_8221 = Installation.Regime8221.DECLARATION_BT
        inst.dossier_statut = Installation.DossierStatut.APPROUVE
        inst.date_pose_prevue = '2026-07-01'
        inst.save(update_fields=[
            'regime_8221', 'dossier_statut', 'date_pose_prevue'])
        res = compute_chantier_readiness(inst)
        self.assertTrue(res['pret'])
        self.assertEqual(_check(res, 'dossier')['statut'], 'ok')

    def test_no_planning_is_warning_not_blocking(self):
        """Pas de date de pose → avertissement, mais reste prêt (non bloquant)."""
        panneau = make_produit(self.company, 'Panneau', stock=50)
        inst = make_chantier(self.company, self.user, [(panneau, 10)])
        res = compute_chantier_readiness(inst)
        self.assertEqual(_check(res, 'planning')['statut'], 'avertissement')
        self.assertTrue(res['pret'])

    def test_endpoint_returns_readiness(self):
        panneau = make_produit(self.company, 'Panneau', stock=3)
        inst = make_chantier(self.company, self.user, [(panneau, 10)])
        r = self.api.get(
            f'/api/django/installations/chantiers/{inst.id}/readiness/')
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.data['pret'])
        self.assertEqual(r.data['materiel']['nb_manques'], 1)

    def test_endpoint_does_not_block_status_change(self):
        """ADVISORY : readiness n'empêche pas de passer le chantier « En cours »."""
        panneau = make_produit(self.company, 'Panneau', stock=3)
        inst = make_chantier(self.company, self.user, [(panneau, 10)])
        r = self.api.patch(
            f'/api/django/installations/chantiers/{inst.id}/',
            {'statut': Installation.Statut.EN_COURS}, format='json')
        self.assertEqual(r.status_code, 200)
        inst.refresh_from_db()
        self.assertEqual(inst.statut, Installation.Statut.EN_COURS)
