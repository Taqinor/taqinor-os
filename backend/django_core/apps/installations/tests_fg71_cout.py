"""
FG71 — Synthèse de coût / marge par chantier (job-costing roll-up).

Assemble main-d'œuvre (jours estimés/réels), coût matériel prévu (BoM gelé) vs
réel (consommation terrain validée, F11) et total du devis en une vue de marge.
STRICTEMENT INTERNE : endpoint `chantiers/{id}/cout` réservé admin (les prix
d'achat ne doivent jamais apparaître sur un document client).

Run :
    python manage.py test apps.installations.tests_fg71_cout -v2
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
from apps.installations.models import (
    Installation, Intervention, MaterielConsommation, ConsommationLigne,
)
from apps.installations.services import (
    create_installation_from_devis, compute_chantier_cout,
)

User = get_user_model()
_seq = itertools.count(1)


def make_company(slug=None, nom=None):
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'fg71-co-{n}', defaults={'nom': nom or f'FG71 Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_produit(company, nom, prix_achat, prix_vente):
    n = next(_seq)
    return Produit.objects.create(
        company=company, nom=nom, sku=f'SKU-{company.id}-{n}',
        prix_achat=Decimal(str(prix_achat)), prix_vente=Decimal(str(prix_vente)),
        quantite_stock=100)


def make_chantier(company, user, lines):
    """lines = [(produit, quantite, prix_unitaire), ...]."""
    n = next(_seq)
    client = Client.objects.create(
        company=company, nom='Site', prenom='Client',
        email=f'fg71-{company.id}-{n}@example.invalid')
    lead = Lead.objects.create(
        company=company, nom='Site', prenom='Client', stage='SIGNED',
        type_installation='residentiel')
    devis = Devis.objects.create(
        company=company, reference=f'DEV-FG71-{company.id}-{n}', client=client,
        lead=lead, statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20'),
        mode_installation='residentiel')
    for produit, qte, pu in lines:
        LigneDevis.objects.create(
            devis=devis, produit=produit, designation=produit.nom,
            quantite=Decimal(str(qte)), prix_unitaire=Decimal(str(pu)))
    inst, _ = create_installation_from_devis(devis, user, company)
    return inst


class TestFG71CoutService(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='fg71_admin', password='x', role_legacy='admin',
            company=self.company)
        # prix_achat 70 / prix_vente 100 (HT)
        self.panneau = make_produit(self.company, 'Panneau', 70, 100)
        self.onduleur = make_produit(self.company, 'Onduleur', 400, 600)

    def test_material_cost_prevu_from_bom(self):
        """Coût matériel prévu = somme(quantité BoM × prix_achat)."""
        inst = make_chantier(
            self.company, self.user,
            [(self.panneau, 10, 100), (self.onduleur, 1, 600)])
        res = compute_chantier_cout(inst)
        # 10×70 + 1×400 = 1100
        self.assertEqual(res['materiel']['cout_prevu'], 1100.0)
        # Aucune consommation validée → on retombe sur le prévu.
        self.assertIsNone(res['materiel']['cout_reel'])
        self.assertEqual(res['materiel']['source_retenue'], 'prevu')

    def test_devis_total_and_margin(self):
        """Marge = total HT − coût matériel retenu (− MO si tarif fourni)."""
        inst = make_chantier(
            self.company, self.user,
            [(self.panneau, 10, 100), (self.onduleur, 1, 600)])
        res = compute_chantier_cout(inst)
        # Devis HT = 10×100 + 1×600 = 1600 ; matériel prévu = 1100
        self.assertEqual(res['devis_total_ht'], 1600.0)
        self.assertEqual(res['marge'], 500.0)
        # Taux = 500/1600 ≈ 31.2 %
        self.assertAlmostEqual(res['marge_taux'], 31.2, places=1)

    def test_labour_monetised_with_tarif(self):
        """Le coût main-d'œuvre n'entre dans la marge que si `tarif_jour` est donné."""
        inst = make_chantier(self.company, self.user, [(self.panneau, 10, 100)])
        inst.labour_jours_estimes = Decimal('2')
        inst.labour_jours_reels = Decimal('3')
        inst.save(update_fields=['labour_jours_estimes', 'labour_jours_reels'])
        # Sans tarif : pas de coût MO, marge = 1000 − 700 = 300.
        res = compute_chantier_cout(inst)
        self.assertIsNone(res['labour']['cout_reel'])
        self.assertEqual(res['marge'], 300.0)
        # Avec tarif 100/jour : MO réelle = 3×100 = 300, marge = 1000−700−300 = 0.
        res2 = compute_chantier_cout(inst, tarif_jour='100')
        self.assertEqual(res2['labour']['cout_estime'], 200.0)
        self.assertEqual(res2['labour']['cout_reel'], 300.0)
        self.assertEqual(res2['marge'], 0.0)

    def test_real_material_cost_overrides_prevu(self):
        """Une consommation VALIDÉE pilote le coût matériel réel (pas le BoM)."""
        inst = make_chantier(self.company, self.user, [(self.panneau, 10, 100)])
        interv = Intervention.objects.create(
            company=self.company, installation=inst,
            type_intervention='pose', created_by=self.user)
        conso = MaterielConsommation.objects.create(
            company=self.company, intervention=interv, valide=True)
        # Utilisé : 12 panneaux (au lieu de 10 prévus).
        ConsommationLigne.objects.create(
            company=self.company, consommation=conso, produit=self.panneau,
            designation='Panneau', quantite_prevue=Decimal('10'),
            quantite_utilisee=Decimal('12'))
        res = compute_chantier_cout(inst)
        # Réel = 12×70 = 840 ; prévu = 700 ; écart = 140.
        self.assertEqual(res['materiel']['cout_reel'], 840.0)
        self.assertEqual(res['materiel']['source_retenue'], 'reel')
        self.assertEqual(res['materiel']['ecart'], 140.0)
        # Marge sur le réel : 1000 − 840 = 160.
        self.assertEqual(res['marge'], 160.0)

    def test_unvalidated_consommation_ignored(self):
        """Une consommation NON validée n'écrase pas le coût prévu."""
        inst = make_chantier(self.company, self.user, [(self.panneau, 10, 100)])
        interv = Intervention.objects.create(
            company=self.company, installation=inst,
            type_intervention='pose', created_by=self.user)
        conso = MaterielConsommation.objects.create(
            company=self.company, intervention=interv, valide=False)
        ConsommationLigne.objects.create(
            company=self.company, consommation=conso, produit=self.panneau,
            designation='Panneau', quantite_prevue=Decimal('10'),
            quantite_utilisee=Decimal('20'))
        res = compute_chantier_cout(inst)
        self.assertIsNone(res['materiel']['cout_reel'])
        self.assertEqual(res['materiel']['source_retenue'], 'prevu')


class TestFG71CoutEndpoint(TestCase):
    def setUp(self):
        self.company = make_company()
        self.admin = User.objects.create_user(
            username='fg71_adm', password='x', role_legacy='admin',
            company=self.company)
        self.resp = User.objects.create_user(
            username='fg71_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.panneau = make_produit(self.company, 'Panneau', 70, 100)
        self.inst = make_chantier(
            self.company, self.admin, [(self.panneau, 10, 100)])

    def test_endpoint_admin_ok(self):
        api = auth(self.admin)
        r = api.get(f'/api/django/installations/chantiers/{self.inst.id}/cout/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['materiel']['cout_prevu'], 700.0)
        self.assertEqual(r.data['marge'], 300.0)

    def test_endpoint_non_admin_forbidden(self):
        """FG71 est INTERNE : un responsable (non admin) est refusé."""
        api = auth(self.resp)
        r = api.get(f'/api/django/installations/chantiers/{self.inst.id}/cout/')
        self.assertIn(r.status_code, (403, 404))

    def test_endpoint_tarif_jour_param(self):
        self.inst.labour_jours_reels = Decimal('2')
        self.inst.save(update_fields=['labour_jours_reels'])
        api = auth(self.admin)
        r = api.get(
            f'/api/django/installations/chantiers/{self.inst.id}/cout/',
            {'tarif_jour': '150'})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['labour']['cout_reel'], 300.0)
        # Marge = 1000 − 700 − 300 = 0.
        self.assertEqual(r.data['marge'], 0.0)
