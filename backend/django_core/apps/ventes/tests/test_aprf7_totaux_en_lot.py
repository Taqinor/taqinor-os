"""APRF7 (C-APRF-004) — ``selectors.devis_avec_totaux`` : lire ``total_ttc`` /
``total_ht`` d'une liste de devis coûte un nombre CONSTANT de requêtes, pour
un devis mono-option ET un devis à deux options.

Avant : ``prefetch_related('lignes')`` laissait ``utils.options.
lignes_avec_produit`` retomber sur ``select_related('produit')`` — +1 requête
``ventes_lignedevis`` par devis mono, +2 par devis deux options (sondes V_VA
F/G/G2 ; contrôle V_VB : 15 devis → 26 requêtes). Mesure à DEUX tailles (5 puis
15 devis, moitié mono, moitié deux options) et égalité au centime avec la
lecture sans préchargement.

Run:
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_aprf7_totaux_en_lot -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from authentication.models import Company
from apps.crm.models import Client
from apps.entites.models import Entite
from apps.stock.models import Produit
from apps.ventes import selectors
from apps.ventes.models import Devis, LigneDevis
from apps.ventes.utils.options import deux_options_declarees

User = get_user_model()

MONO = [('Panneau Canadian Solar 550W', '10', '1400'),
        ('Onduleur réseau Deye 8kW', '1', '14000')]
DEUX = MONO + [('Onduleur hybride Deye 8kW', '1', '21000'),
               ('Batterie Dyness 5 kWh', '2', '12000')]


class TotauxEnLotTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(nom='APRF7 SARL')
        self.user = User.objects.create_user(
            username='aprf7_user', password='x', role_legacy='admin',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='APRF7', prenom='Client',
            email='aprf7@example.com', telephone='+212600000077')
        self.entite = Entite.objects.create(
            company=self.company, nom='Filiale APRF7', code='APRF7')
        self.n = 0

    def _devis(self, deux):
        self.n += 1
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-APRF7-{self.n:04d}',
            client=self.client_obj, created_by=self.user,
            taux_tva=Decimal('20'), remise_globale=Decimal('0'),
            entite=self.entite,
            etude_params=({'scenario': 'Les deux (Sans + Avec)'}
                          if deux else {}))
        for desig, qty, pu in (DEUX if deux else MONO):
            produit = Produit.objects.create(
                company=self.company, nom=desig,
                sku=f'APRF7-{self.n}-{desig[:10]}',
                prix_vente=Decimal(pu), prix_achat=Decimal('1'),
                quantite_stock=10)
            LigneDevis.objects.create(
                devis=devis, produit=produit, designation=desig,
                quantite=Decimal(qty), prix_unitaire=Decimal(pu),
                remise=Decimal('0'))
        return devis

    def _peupler(self, total):
        while self.n < total:
            self._devis(deux=self.n % 2 == 1)

    def _ids(self):
        return list(Devis.objects.filter(company=self.company)
                    .values_list('id', flat=True))

    def _lire_totaux(self, qs):
        with CaptureQueriesContext(connection) as ctx:
            montants = {d.id: (d.total_ttc, d.total_ht) for d in qs}
        return len(ctx.captured_queries), montants

    def test_mono_et_deux_options_constants(self):
        self._peupler(5)
        # Prémisse : les deux formes sont bien présentes.
        formes = {deux_options_declarees(d)
                  for d in Devis.objects.filter(company=self.company)}
        self.assertEqual(formes, {True, False})
        base = Devis.objects.filter(company=self.company)
        n5, m5 = self._lire_totaux(selectors.devis_avec_totaux(base))
        self._peupler(15)
        n15, m15 = self._lire_totaux(selectors.devis_avec_totaux(
            Devis.objects.filter(company=self.company)))
        self.assertEqual(len(m15), 15)
        self.assertEqual(n5, n15, f'requêtes {n5} (5 devis) ≠ {n15} (15)')
        # Montants égaux au centime à la lecture SANS préchargement.
        for devis in Devis.objects.filter(company=self.company):
            self.assertEqual(m15[devis.id], (devis.total_ttc, devis.total_ht))

    def test_selecteurs_constants(self):
        self._peupler(5)
        # Les ids sont lus HORS mesure (comme à 15 devis) : sinon la requête
        # ``_ids()`` gonfle la mesure à 5 d'une unité (8 ≠ 7).
        ids5 = self._ids()
        with CaptureQueriesContext(connection) as c5:
            montants5 = selectors.montants_devis(ids5, self.company)
            ca5 = selectors.ca_par_entite(self.company, [self.entite.id])
        self._peupler(15)
        ids = self._ids()
        with CaptureQueriesContext(connection) as c15:
            montants15 = selectors.montants_devis(ids, self.company)
            ca15 = selectors.ca_par_entite(self.company, [self.entite.id])
        self.assertEqual(len(montants5), 5)
        self.assertEqual(len(montants15), 15)
        self.assertEqual(ca5[self.entite.id]['nb_devis'], 5)
        self.assertEqual(ca15[self.entite.id]['nb_devis'], 15)
        self.assertEqual(len(c5.captured_queries), len(c15.captured_queries))
        # Égalité au centime avec la lecture unitaire.
        attendu = Decimal('0')
        for devis in Devis.objects.filter(company=self.company):
            ttc = Decimal(str(devis.total_ttc or 0))
            self.assertEqual(montants15[devis.id]['ttc'], ttc)
            self.assertEqual(montants15[devis.id]['ht'],
                             Decimal(str(devis.total_ht or 0)))
            attendu += ttc
        self.assertEqual(ca15[self.entite.id]['ca_devis'], attendu)
