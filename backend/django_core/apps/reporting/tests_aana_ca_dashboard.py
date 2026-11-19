"""AANA20 (C-AANA-020, D-AANA-6) — le CA du tableau de bord vient de
``Facture.total_ht`` et la créance de ``Facture.montant_du`` (TTC).

Scénario R2 : facture émise, une ligne 1×1000, ``remise_globale=50`` (%).
Avant le correctif : ``total_ht=500`` mais ``ca_attente=1000`` et créance
1000 (somme de lignes brute, remise ignorée, HT présenté comme dû).

Données RÉELLES en base, propriétés RÉELLES du modèle (aucun mock).
Rétablir l'ancien ``_ca_factures`` (somme de lignes) rougit ces tests.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.reporting.kpi_alertes import _resolve_representative_user
from apps.stock.models import Produit
from apps.ventes.models import (
    Avoir, Devis, Facture, LigneAvoir, LigneDevis, LigneFacture, Paiement)
from authentication.models import Company

User = get_user_model()

URL = '/api/django/reporting/dashboard/'


class TestCaDashboard(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='aana20-co', defaults={'nom': 'AANA20 Co'})[0]
        self.user = User.objects.create_user(
            username='aana20_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Cli R2')
        self.produit = Produit.objects.create(
            company=self.company, nom='Kit', sku='AANA20-P',
            prix_vente=Decimal('1000'), quantite_stock=0)

    def _facture(self, reference, statut, remise_globale=Decimal('0')):
        facture = Facture.objects.create(
            company=self.company, reference=reference, client=self.client_obj,
            statut=statut, remise_globale=remise_globale)
        LigneFacture.objects.create(
            facture=facture, produit=self.produit, designation='Kit',
            quantite=Decimal('1'),
            prix_unitaire=Decimal('1000'))
        return facture

    def test_remise_globale_appliquee(self):
        facture = self._facture('FAC-AANA20-1', Facture.Statut.EMISE,
                                remise_globale=Decimal('50'))
        self.assertEqual(facture.total_ht, Decimal('500.00'))

        resp = self.api.get(URL)
        self.assertEqual(resp.status_code, 200)
        # CA en attente = total_ht (remise globale honorée), pas 1000.
        self.assertEqual(resp.data['kpis']['ca_attente'], 500.0)
        # Créance = montant_du (TTC restant dû), pas une somme HT de lignes.
        self.assertEqual(len(resp.data['creances']), 1)
        self.assertEqual(resp.data['creances'][0]['montant_total'],
                         float(facture.montant_du))
        self.assertNotEqual(resp.data['creances'][0]['montant_total'], 1000.0)

    def test_creance_deduit_paiements(self):
        facture = self._facture('FAC-AANA20-2', Facture.Statut.EMISE)
        Paiement.objects.create(
            company=self.company, facture=facture, client=self.client_obj,
            montant=Decimal('200'), date_paiement=date.today(),
            mode=Paiement.Mode.VIREMENT)
        Facture.objects.filter(pk=facture.pk).update(
            statut=Facture.Statut.EMISE)
        facture.refresh_from_db()
        resp = self.api.get(URL)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['creances'][0]['montant_total'],
                         float(facture.montant_du))
        self.assertEqual(float(facture.montant_du),
                         float(facture.total_ttc) - 200.0)

    def test_payee_avec_reliquat_pas_encaissee_pour_le_reliquat(self):
        facture = self._facture('FAC-AANA20-3', Facture.Statut.PAYEE)
        moitie = (Decimal(facture.total_ttc) / 2).quantize(Decimal('0.01'))
        Paiement.objects.create(
            company=self.company, facture=facture, client=self.client_obj,
            montant=moitie, date_paiement=date.today(),
            mode=Paiement.Mode.VIREMENT)
        # État testé : statut « payée » malgré un reliquat (saisie manuelle).
        Facture.objects.filter(pk=facture.pk).update(
            statut=Facture.Statut.PAYEE)
        facture.refresh_from_db()
        self.assertGreater(facture.montant_du, 0)

        resp = self.api.get(URL)
        self.assertEqual(resp.status_code, 200)
        kpis = resp.data['kpis']
        # Seule la moitié du HT est encaissée ; l'autre moitié reste en attente.
        self.assertAlmostEqual(kpis['ca_paye'], 500.0, places=1)
        self.assertAlmostEqual(kpis['ca_attente'], 500.0, places=1)
        self.assertAlmostEqual(kpis['ca_paye'] + kpis['ca_attente'],
                               float(facture.total_ht), places=2)
        # Le CA mensuel lit la même base (encaissé HT).
        self.assertAlmostEqual(resp.data['ca_mensuel'][-1]['ca'], 500.0,
                               places=1)

    # ── AANA55 (C-AANA-VER-002) — encaissé = paiements reçus, attente =
    # ``montant_du`` (avoirs déduits), au prorata HT/TTC. ──────────────────

    def _avoir(self, facture, ht, ref):
        avoir = Avoir.objects.create(
            company=self.company, reference=ref, facture=facture,
            client=self.client_obj)
        LigneAvoir.objects.create(
            avoir=avoir, designation='Avoir', quantite=Decimal('1'),
            prix_unitaire=Decimal(ht))
        return avoir

    def _paye(self, facture, montant):
        Paiement.objects.create(
            company=self.company, facture=facture, client=self.client_obj,
            montant=Decimal(montant), date_paiement=date.today(),
            mode=Paiement.Mode.VIREMENT)

    def _force(self, facture, statut):
        Facture.objects.filter(pk=facture.pk).update(statut=statut)

    def test_avoir_total_sans_paiement_rien_d_encaisse(self):
        facture = self._facture('FAC-AANA55-A', Facture.Statut.EMISE)
        self._avoir(facture, '1000', 'AV-AANA55-A')
        self._force(facture, Facture.Statut.PAYEE)  # soldée par l'avoir
        resp = self.api.get(URL)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['kpis']['ca_paye'], 0.0)
        self.assertEqual(resp.data['kpis']['ca_attente'], 0.0)
        self.assertEqual(resp.data['ca_mensuel'][-1]['ca'], 0.0)

    def test_avoir_partiel_deduit_de_l_attente(self):
        facture = self._facture('FAC-AANA55-B', Facture.Statut.EMISE)
        self._avoir(facture, '250', 'AV-AANA55-B')  # 300 TTC
        resp = self.api.get(URL)
        self.assertEqual(resp.status_code, 200)
        self.assertAlmostEqual(resp.data['kpis']['ca_attente'], 750.0,
                               places=2)
        self.assertEqual(resp.data['kpis']['ca_paye'], 0.0)

    def test_quatre_factures_du_scenario(self):
        a = self._facture('FAC-AANA55-1', Facture.Statut.EMISE)
        self._avoir(a, '1000', 'AV-AANA55-1')
        self._force(a, Facture.Statut.PAYEE)
        b = self._facture('FAC-AANA55-2', Facture.Statut.EMISE)
        self._avoir(b, '250', 'AV-AANA55-2')
        c = self._facture('FAC-AANA55-3', Facture.Statut.EMISE)
        self._paye(c, '1200')
        self._force(c, Facture.Statut.PAYEE)
        d = self._facture('FAC-AANA55-4', Facture.Statut.EMISE)
        self._paye(d, '600')
        self._force(d, Facture.Statut.PAYEE)
        resp = self.api.get(URL)
        self.assertEqual(resp.status_code, 200)
        self.assertAlmostEqual(resp.data['kpis']['ca_paye'], 1500.0, places=2)
        self.assertAlmostEqual(resp.data['kpis']['ca_attente'], 1250.0,
                               places=2)
        self.assertAlmostEqual(resp.data['ca_mensuel'][-1]['ca'], 1500.0,
                               places=2)
        # Par facture : encaissé + attente + part HT des avoirs = total_ht.
        from apps.reporting.views import _ht_encaisse, _part_ht
        for f in Facture.objects.filter(pk__in=[a.pk, b.pk, c.pk, d.pk]):
            somme = (_ht_encaisse(f) + _part_ht(f, f.montant_du)
                     + _part_ht(f, f.avoirs_total))
            self.assertAlmostEqual(float(somme), float(f.total_ht), places=2)


class TestUtilisateurDeCalculKpi(TestCase):
    """AANA20 — l'encours échu se calcule au nom d'un admin/responsable,
    jamais du premier utilisateur venu (portée « ses enregistrements »)."""

    def test_admin_prefere_au_premier_utilisateur(self):
        company = Company.objects.get_or_create(
            slug='aana20-kpi', defaults={'nom': 'AANA20 KPI'})[0]
        User.objects.create_user(
            username='aana20_normal', password='x', role_legacy='normal',
            company=company)
        admin = User.objects.create_user(
            username='aana20_admin', password='x', role_legacy='admin',
            company=company)
        self.assertEqual(_resolve_representative_user(company), admin)

    def test_aucun_admin_ni_responsable(self):
        company = Company.objects.get_or_create(
            slug='aana20-kpi2', defaults={'nom': 'AANA20 KPI 2'})[0]
        User.objects.create_user(
            username='aana20_normal2', password='x', role_legacy='normal',
            company=company)
        self.assertIsNone(_resolve_representative_user(company))


class TestTroisChiffresCa(TestCase):
    """RPT1 — « signé », « facturé » et « encaissé » HT : chacun lit le calcul
    que son écran utilise déjà (tableau de bord, ``ca_ht``, classement)."""

    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='rpt1-co', defaults={'nom': 'RPT1 Co'})[0]
        self.admin = User.objects.create_user(
            username='rpt1_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Cli RPT1')
        self.produit = Produit.objects.create(
            company=self.company, nom='Kit', sku='RPT1-P',
            prix_vente=Decimal('1000'), quantite_stock=0)
        self.du, self.au = date(2026, 3, 1), date(2026, 3, 31)
        self.dedans, self.dehors = date(2026, 3, 15), date(2026, 2, 10)

    def _facture(self, reference, jour, ht='1000', auteur=None,
                 statut=Facture.Statut.EMISE):
        facture = Facture.objects.create(
            company=self.company, reference=reference, client=self.client_obj,
            statut=statut, date_emission=jour, created_by=auteur)
        LigneFacture.objects.create(
            facture=facture, produit=self.produit, designation='Kit',
            quantite=Decimal('1'), prix_unitaire=Decimal(ht))
        return facture

    def _paye(self, facture, montant, statut):
        Paiement.objects.create(
            company=self.company, facture=facture, client=self.client_obj,
            montant=Decimal(montant), date_paiement=date.today(),
            mode=Paiement.Mode.VIREMENT)
        Facture.objects.filter(pk=facture.pk).update(statut=statut)

    def _devis(self, reference, jour, ht='1000', auteur=None,
               remise=Decimal('0')):
        devis = Devis.objects.create(
            company=self.company, reference=reference, client=self.client_obj,
            statut=Devis.Statut.ACCEPTE, date_acceptation=jour,
            created_by=auteur, remise_globale=remise)
        LigneDevis.objects.create(
            devis=devis, produit=self.produit, designation='Kit',
            quantite=Decimal('1'), prix_unitaire=Decimal(ht))
        return devis

    def _agent(self, nom):
        from apps.roles.models import Role
        from apps.roles.permissions_registre import SCOPE_SELF
        role = Role.objects.create(
            company=self.company, nom=nom,
            permissions=['ventes_voir', 'reporting_voir', SCOPE_SELF])
        return User.objects.create_user(
            username=nom, password='x', company=self.company, role=role)

    def test_encaisse_est_celui_du_tableau_de_bord(self):
        from apps.reporting.metriques_ca import encaisse_ht
        dedans = self._facture('FAC-RPT1-E1', self.dedans)
        self._paye(dedans, '600', Facture.Statut.EMISE)  # 600 TTC = 500 HT
        dehors = self._facture('FAC-RPT1-E2', self.dehors)
        self._paye(dehors, '1200', Facture.Statut.PAYEE)  # 1 000 HT
        self.assertEqual(encaisse_ht(self.company, period=(self.du, self.au)),
                         Decimal('500'))
        tout = encaisse_ht(self.company)
        self.assertEqual(tout, Decimal('1500'))
        resp = self.api.get(URL)
        self.assertEqual(resp.status_code, 200)
        self.assertAlmostEqual(resp.data['kpis']['ca_paye'], float(tout),
                               places=2)

    def test_facture_net_d_avoirs_hors_brouillon_dans_la_fenetre(self):
        from apps.reporting.metriques_ca import (
            STATUTS_CA, ca_facture_ht_periode, ca_ht)
        facture = self._facture('FAC-RPT1-F1', self.dedans)
        avoir = Avoir.objects.create(
            company=self.company, reference='AV-RPT1-F1', facture=facture,
            client=self.client_obj)
        LigneAvoir.objects.create(
            avoir=avoir, designation='Avoir', quantite=Decimal('1'),
            prix_unitaire=Decimal('250'))
        self._facture('FAC-RPT1-F2', self.dehors)
        self._facture('FAC-RPT1-F3', self.dedans,
                      statut=Facture.Statut.BROUILLON)
        valeur = ca_facture_ht_periode(self.company, self.du, self.au)
        self.assertEqual(valeur, Decimal('750'))
        self.assertEqual(valeur, ca_ht(
            self.company, period=(self.du, self.au),
            filters={'statut__in': list(STATUTS_CA)}))

    def test_signe_remise_revision_et_fenetre(self):
        from apps.reporting.metriques_ca import ca_signe_ht
        self._devis('DEV-RPT1-S1', self.dedans, remise=Decimal('10'))  # 900
        self._devis('DEV-RPT1-S2', self.dehors)
        v1 = self._devis('DEV-RPT1-V1', self.dedans)
        v2 = self._devis('DEV-RPT1-V2', self.dedans, ht='2000')
        Devis.objects.filter(pk=v1.pk).update(
            is_active=False, superseded_by=v2)
        Devis.objects.create(
            company=self.company, reference='DEV-RPT1-B',
            client=self.client_obj, statut=Devis.Statut.BROUILLON,
            date_acceptation=self.dedans)
        self.assertEqual(ca_signe_ht(self.company, period=(self.du, self.au)),
                         Decimal('2900'))

    def test_portee_du_role_comme_le_tableau_de_bord(self):
        from apps.reporting.metriques_ca import (
            ca_facture_ht_periode, ca_signe_ht, encaisse_ht)
        c1, c2 = self._agent('rpt1-c1'), self._agent('rpt1-c2')
        periode = (self.du, self.au)
        for nom, auteur, ht in (('1', c1, '1000'), ('2', c2, '500')):
            facture = self._facture('FAC-RPT1-P' + nom, self.dedans, ht, auteur)
            self._paye(facture, '600', Facture.Statut.EMISE)
            self._devis('DEV-RPT1-P' + nom, self.dedans, ht, auteur)
        self.assertEqual(ca_facture_ht_periode(
            self.company, *periode, user=c1), Decimal('1000'))
        self.assertEqual(ca_facture_ht_periode(
            self.company, *periode), Decimal('1500'))
        self.assertEqual(ca_signe_ht(self.company, c1, period=periode),
                         Decimal('1000'))
        self.assertEqual(ca_signe_ht(self.company, period=periode),
                         Decimal('1500'))
        self.assertEqual(encaisse_ht(self.company, c1, period=periode),
                         Decimal('500'))  # 600 TTC payés sur 1 200 TTC
        self.assertEqual(encaisse_ht(self.company, period=periode),
                         Decimal('1000'))  # + 600 TTC payés sur 600 TTC

    def test_un_filtre_est_refuse_en_francais(self):
        from apps.reporting.metriques_ca import ca_signe_ht, encaisse_ht
        from apps.semantic.services import MetriqueNonResolvable
        for adaptateur in (ca_signe_ht, encaisse_ht):
            with self.assertRaises(MetriqueNonResolvable) as ctx:
                adaptateur(self.company, filters={'statut': 'payee'})
            self.assertIn('aucun filtre', str(ctx.exception))
