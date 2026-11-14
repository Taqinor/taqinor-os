"""AANA22 (C-AANA-038) — tableau commercial et export classement donnent LE
même taux de victoire sur la même période.

Scénario R8 : un commercial a 2 leads ; le 2e est créé le jour ``to`` à 15 h.
Avant le correctif : l'export bornait par ``date_creation__lte=<date>``
(minuit) et ratait ce lead — 100,0 contre 50,0 au tableau commercial.

La fenêtre est désormais construite DANS ``build_leaderboard`` (bornes
``__date__`` inclusives). Données RÉELLES en base (aucun mock).
"""
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm import stages
from apps.crm.models import Client, Lead
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis
from authentication.models import Company

User = get_user_model()

BASE = '/api/django/reporting'


class TestMemeTauxDeuxEcrans(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='aana22-co', defaults={'nom': 'AANA22 Co'})[0]
        self.user = User.objects.create_user(
            username='aana22_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.owner = User.objects.create_user(
            username='aana22_comm', password='x', role_legacy='responsable',
            company=self.company)
        self.to = date.today() - timedelta(days=2)
        self.frm = self.to - timedelta(days=5)

        signe = Lead.objects.create(
            company=self.company, nom='Signé', stage=stages.SIGNED,
            owner=self.owner)
        tardif = Lead.objects.create(
            company=self.company, nom='Créé le jour to à 15 h',
            stage=stages.NEW, owner=self.owner)
        Lead.objects.filter(pk=signe.pk).update(date_creation=timezone.make_aware(
            datetime.combine(self.frm + timedelta(days=1), time(10, 0))))
        Lead.objects.filter(pk=tardif.pk).update(
            date_creation=timezone.make_aware(
                datetime.combine(self.to, time(15, 0))))

        client = Client.objects.create(company=self.company, nom='Cli R8')
        produit = Produit.objects.create(
            company=self.company, nom='Kit', sku='AANA22-P',
            prix_vente=Decimal('1000'), quantite_stock=0)
        devis = Devis.objects.create(
            company=self.company, reference='DEV-AANA22', client=client,
            lead=signe, statut=Devis.Statut.ACCEPTE,
            date_acceptation=self.to)
        LigneDevis.objects.create(
            devis=devis, produit=produit, designation='Kit',
            quantite=Decimal('1'), prix_unitaire=Decimal('1000'))

    def test_meme_taux_deux_ecrans(self):
        params = f'?from={self.frm.isoformat()}&to={self.to.isoformat()}'
        resp = self.api.get(f'{BASE}/commercial/dashboard/{params}')
        self.assertEqual(resp.status_code, 200)
        taux_tableau = resp.data['leaderboard'][0]['win_rate_pct']

        resp = self.api.get(f'{BASE}/insights/sales-leaderboard/{params}')
        self.assertEqual(resp.status_code, 200)
        taux_export = resp.data['rows'][0]['win_rate_pct']

        self.assertEqual(taux_tableau, 50.0)
        self.assertEqual(taux_export, taux_tableau)

    def test_devis_sans_lead_meme_ca_deux_ecrans(self):
        """AANA62 — un devis signé SANS lead (crédité à ``created_by``) compte
        dans les deux classements : 1 000 + 2 000 HT, 2 devis, partout."""
        client = Client.objects.get(company=self.company, nom='Cli R8')
        produit = Produit.objects.get(company=self.company, sku='AANA22-P')
        sans_lead = Devis.objects.create(
            company=self.company, reference='DEV-AANA62', client=client,
            statut=Devis.Statut.ACCEPTE, date_acceptation=self.to,
            created_by=self.owner)
        LigneDevis.objects.create(
            devis=sans_lead, produit=produit, designation='Kit',
            quantite=Decimal('2'), prix_unitaire=Decimal('1000'))
        params = f'?from={self.frm.isoformat()}&to={self.to.isoformat()}'
        lignes = []
        for url, cle in ((f'{BASE}/commercial/dashboard/{params}', 'leaderboard'),
                         (f'{BASE}/insights/sales-leaderboard/{params}', 'rows')):
            resp = self.api.get(url)
            self.assertEqual(resp.status_code, 200)
            ligne = next(r for r in resp.data[cle]
                         if r['commercial'] == self.owner.username)
            lignes.append(ligne)
            self.assertAlmostEqual(float(ligne['ca_ht']), 3000.0, places=2)
            self.assertEqual(ligne['nb_devis_signes'], 2)
        self.assertEqual(lignes[0]['ca_ht'], lignes[1]['ca_ht'])

    def test_commercial_soi_voit_ses_chiffres(self):
        """ALEC22 (D-ALEC-2 = portee_du_role) — un Commercial (portée « soi »)
        ne lit que ses montants : le collègue B reste nommé au classement, ses
        montants à null, son client absent des créances et son archive 404 ;
        le Directeur lit les valeurs de B."""
        from apps.roles.models import Role
        from apps.roles.permissions_registre import (
            COMMERCIAL_PERMISSIONS, DIRECTEUR_PERMISSIONS)
        from apps.ventes.models import Facture, LigneFacture

        def compte(nom, role_nom, perms):
            role, _ = Role.objects.get_or_create(
                company=self.company, nom=role_nom, defaults={'permissions': list(perms)})
            return User.objects.create_user(
                username=nom, password='x', company=self.company, role=role)
        a = compte('alec22_a', 'Commercial', COMMERCIAL_PERMISSIONS)
        b = compte('alec22_b', 'Commercial', COMMERCIAL_PERMISSIONS)
        directeur = compte('alec22_dir', 'Directeur', DIRECTEUR_PERMISSIONS)
        cli_b = Client.objects.create(company=self.company, nom='Client de B',
                                      email='alec22-b@example.com')
        produit = Produit.objects.get(company=self.company, sku='AANA22-P')
        devis = Devis.objects.create(
            company=self.company, reference='DEV-ALEC22', client=cli_b,
            statut=Devis.Statut.ACCEPTE, date_acceptation=self.to, created_by=b)
        LigneDevis.objects.create(devis=devis, produit=produit, designation='Kit',
                                  quantite=Decimal('1'), prix_unitaire=Decimal('1000'))
        facture = Facture.objects.create(
            company=self.company, reference='FAC-ALEC22', client=cli_b,
            statut=Facture.Statut.EMISE, created_by=b)
        LigneFacture.objects.create(facture=facture, produit=produit, designation='Kit',
                                    quantite=Decimal('1'), prix_unitaire=Decimal('1000'))

        def lire(user):
            self.api.force_authenticate(user)
            dash = self.api.get(f'{BASE}/dashboard/')
            comm = self.api.get(f'{BASE}/commercial/dashboard/')
            clas = self.api.get(f'{BASE}/insights/sales-leaderboard/')
            arch = self.api.get(f'{BASE}/archive/client/{cli_b.pk}/')
            for r in (dash, comm, clas):
                self.assertEqual(r.status_code, 200, r.content)
            ligne = [next(r for r in rows if r['commercial'] == 'alec22_b')
                     for rows in (comm.data['leaderboard'], clas.data['rows'])]
            return dash.data, ligne, arch.status_code

        dash, lignes_b, arch = lire(a)
        self.assertEqual(dash['kpis']['ca_attente'], 0.0)
        self.assertNotIn('Client de B', [c['client'].strip() for c in dash['creances']])
        for ligne in lignes_b:
            self.assertEqual([ligne[c] for c in ('ca_ht', 'nb_devis_signes', 'avg_deal_ht', 'kwc')],
                             [None] * 4)
        self.assertEqual(arch, 404)

        dash, lignes_b, arch = lire(directeur)
        self.assertIn('Client de B', [c['client'].strip() for c in dash['creances']])
        self.assertGreater(dash['kpis']['ca_attente'], 0)
        for ligne in lignes_b:
            self.assertAlmostEqual(float(ligne['ca_ht']), 1000.0, places=2)
            self.assertEqual(ligne['nb_devis_signes'], 1)
        self.assertEqual(arch, 200)
