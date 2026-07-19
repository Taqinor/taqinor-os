"""N49/N70/N95/N78/N80 — Insights (revenu récurrent, journal d'audit unifié,
coût de revient chantier, analytics). Lecture seule, multi-tenant.

Suit le patron de `tests_reports.py` : une société + un utilisateur
responsable/admin + objets minimaux, puis assertions HTTP 200, forme JSON, et
isolation par société (la donnée d'une 2e société n'est jamais renvoyée).
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client, Lead, LeadActivity
from apps.installations.models import Installation
from apps.sav.models import ContratMaintenance
from apps.ventes.models import Devis, LigneDevis, Facture, LigneFacture
from apps.stock.models import Produit
from apps.parametres.models import CompanyProfile

User = get_user_model()

BASE = '/api/django/reporting/insights'


class InsightsBase(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='ins-co', defaults={'nom': 'Ins Co'})[0]
        self.other = Company.objects.get_or_create(
            slug='ins-other', defaults={'nom': 'Ins Other'})[0]
        self.user = User.objects.create_user(
            username='ins_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')


class TestRecurringRevenue(InsightsBase):
    def test_shape_and_scope(self):
        client = Client.objects.create(company=self.company, nom='C1')
        other_client = Client.objects.create(company=self.other, nom='CX')
        ContratMaintenance.objects.create(
            company=self.company, client=client, periodicite='mensuel',
            date_debut=date.today(), prix=Decimal('1200'), actif=True)
        ContratMaintenance.objects.create(
            company=self.company, client=client, periodicite='annuel',
            date_debut=date.today(), prix=Decimal('600'), actif=False)
        ContratMaintenance.objects.create(
            company=self.other, client=other_client, periodicite='mensuel',
            date_debut=date.today(), prix=Decimal('9999'), actif=True)

        resp = self.api.get(f'{BASE}/recurring-revenue/')
        self.assertEqual(resp.status_code, 200)
        for key in ('monthly_total', 'annual_total', 'active_count',
                    'lapsed_count', 'upcoming', 'contracts'):
            self.assertIn(key, resp.data)
        # Société courante : 1 actif, 1 lapsed ; la 2e société est exclue.
        self.assertEqual(resp.data['active_count'], 1)
        self.assertEqual(resp.data['lapsed_count'], 1)
        # Mensuel 1200/mois → mensuel équivalent 1200, annuel 14400.
        self.assertEqual(Decimal(resp.data['monthly_total']), Decimal('1200'))
        self.assertEqual(Decimal(resp.data['annual_total']), Decimal('14400'))
        # xlsx.
        x = self.api.get(f'{BASE}/recurring-revenue/?export=xlsx')
        body = b''.join(x.streaming_content) if x.streaming else x.content
        self.assertTrue(body.startswith(b'PK'))


class TestAuditLog(InsightsBase):
    def test_unified_feed_and_scope(self):
        # stage CONTACTED (pas NEW) : la note ne déclenche pas l'auto-avance QJ7
        # (qui ajouterait une activité « modification ») — le feed reste focalisé.
        lead = Lead.objects.create(company=self.company, nom='L1', stage='CONTACTED')
        LeadActivity.objects.create(
            company=self.company, lead=lead, kind='note',
            body='Appel passé', user=self.user)
        # Donnée d'une autre société : doit être exclue.
        other_lead = Lead.objects.create(
            company=self.other, nom='LX', stage='NEW')
        LeadActivity.objects.create(
            company=self.other, lead=other_lead, kind='note',
            body='Secret', user=None)

        resp = self.api.get(f'{BASE}/audit-log/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('items', resp.data)
        self.assertEqual(resp.data['count'], 1)
        item = resp.data['items'][0]
        for key in ('date', 'user', 'type', 'type_label', 'object_ref',
                    'summary'):
            self.assertIn(key, item)
        self.assertEqual(item['type'], 'lead')
        self.assertEqual(item['user'], 'ins_admin')

        # Filtre par type inexistant → flux vide.
        empty = self.api.get(f'{BASE}/audit-log/?type=parametres')
        self.assertEqual(empty.data['count'], 0)
        # xlsx.
        x = self.api.get(f'{BASE}/audit-log/?export=xlsx')
        body = b''.join(x.streaming_content) if x.streaming else x.content
        self.assertTrue(body.startswith(b'PK'))

    def test_deep_link_object_ref(self):
        # N83 (L16) — chaque ligne porte object_type + object_id pour lier vers
        # la fiche concernée (lead/devis/chantier/ticket).
        lead = Lead.objects.create(company=self.company, nom='Linkable',
                                   stage='NEW')
        LeadActivity.objects.create(
            company=self.company, lead=lead, kind='note',
            body='Note', user=self.user)
        resp = self.api.get(f'{BASE}/audit-log/?type=lead')
        self.assertEqual(resp.status_code, 200)
        item = resp.data['items'][0]
        self.assertEqual(item['object_type'], 'lead')
        self.assertEqual(item['object_id'], lead.id)

    def test_field_change_format_consistent(self):
        # N83 (L16) — un changement de champ du chatter ET un changement de
        # réglage rendent le MÊME format « champ : ancien → nouveau ».
        from apps.parametres.models import SettingsAuditLog
        lead = Lead.objects.create(company=self.company, nom='L2', stage='NEW')
        LeadActivity.objects.create(
            company=self.company, lead=lead, kind='modification',
            field='stage', field_label='Étape', old_value='NEW',
            new_value='CONTACTED', user=self.user)
        SettingsAuditLog.objects.create(
            company=self.company, section='entreprise', field='nom',
            field_label='Nom', old_value='Ancien', new_value='Nouveau',
            user=self.user)
        resp = self.api.get(f'{BASE}/audit-log/')
        self.assertEqual(resp.status_code, 200)
        summaries = [it['summary'] for it in resp.data['items']]
        self.assertIn('Étape : NEW → CONTACTED', summaries)
        self.assertIn('Nom : Ancien → Nouveau', summaries)

    def test_field_change_empty_values(self):
        # Valeurs absentes → symbole ∅ identique des deux côtés.
        from apps.parametres.models import SettingsAuditLog
        SettingsAuditLog.objects.create(
            company=self.company, section='entreprise', field='note',
            field_label='Note', old_value='', new_value='Texte',
            user=self.user)
        resp = self.api.get(f'{BASE}/audit-log/?type=parametres')
        summaries = [it['summary'] for it in resp.data['items']]
        self.assertIn('Note : ∅ → Texte', summaries)


class TestJobCosting(InsightsBase):
    def test_margin_and_scope(self):
        client = Client.objects.create(company=self.company, nom='C1')
        produit = Produit.objects.create(
            company=self.company, nom='Panneau', sku='J-1',
            prix_vente=Decimal('1000'), prix_achat=Decimal('600'),
            quantite_stock=0)
        devis = Devis.objects.create(
            company=self.company, reference='DEV-J1', client=client,
            statut=Devis.Statut.ACCEPTE)
        LigneDevis.objects.create(
            devis=devis, produit=produit, designation='Panneau',
            quantite=Decimal('10'), prix_unitaire=Decimal('1000'))
        Installation.objects.create(
            company=self.company, reference='CH-J1', client=client,
            devis=devis, statut=Installation.Statut.RECEPTIONNE,
            date_reception=date.today(),
            puissance_installee_kwc=Decimal('5'))
        facture = Facture.objects.create(
            company=self.company, reference='FAC-J1', client=client,
            devis=devis, statut=Facture.Statut.EMISE)
        LigneFacture.objects.create(
            facture=facture, produit=produit, designation='Panneau',
            quantite=Decimal('10'), prix_unitaire=Decimal('1000'))

        # Donnée d'une autre société.
        other_client = Client.objects.create(company=self.other, nom='CX')
        Installation.objects.create(
            company=self.other, reference='CH-X', client=other_client,
            statut=Installation.Statut.SIGNE)

        resp = self.api.get(f'{BASE}/job-costing/')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data['internal'])
        self.assertEqual(len(resp.data['chantiers']), 1)
        row = resp.data['chantiers'][0]
        self.assertEqual(row['ref'], 'CH-J1')
        # Facturé 10×1000 = 10000 ; coût 10×600 = 6000 ; marge 4000.
        self.assertEqual(Decimal(row['invoiced_ht']), Decimal('10000'))
        self.assertEqual(Decimal(row['cost_estimate']), Decimal('6000'))
        self.assertEqual(Decimal(row['margin']), Decimal('4000'))
        self.assertEqual(row['margin_pct'], 40.0)

    def test_admin_gated(self):
        """Un responsable non-admin ne peut pas voir le coût de revient."""
        resp_user = User.objects.create_user(
            username='ins_resp', password='x', role_legacy='responsable',
            company=self.company)
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(resp_user)}')
        resp = api.get(f'{BASE}/job-costing/')
        self.assertEqual(resp.status_code, 403)


class TestAnalytics(InsightsBase):
    def test_shape_and_scope(self):
        client = Client.objects.create(company=self.company, nom='C1')
        lead = Lead.objects.create(company=self.company, nom='L1', stage='NEW')
        devis = Devis.objects.create(
            company=self.company, reference='DEV-A1', client=client,
            lead=lead, statut=Devis.Statut.ACCEPTE,
            date_acceptation=date.today())
        Installation.objects.create(
            company=self.company, reference='CH-A1', client=client,
            devis=devis, statut=Installation.Statut.RECEPTIONNE,
            date_signature=date.today() - timedelta(days=10),
            date_reception=date.today(),
            puissance_installee_kwc=Decimal('7.5'))

        # Donnée d'une autre société (chantier avec kWc) — ne doit pas compter.
        other_client = Client.objects.create(company=self.other, nom='CX')
        Installation.objects.create(
            company=self.other, reference='CH-X', client=other_client,
            statut=Installation.Statut.RECEPTIONNE,
            date_reception=date.today(),
            puissance_installee_kwc=Decimal('99'))

        resp = self.api.get(f'{BASE}/analytics/')
        self.assertEqual(resp.status_code, 200)
        for key in ('avg_days_lead_to_signature',
                    'avg_days_signature_to_commissioning',
                    'kwc_by_month'):
            self.assertIn(key, resp.data)
        # signature→mise en service = 10 jours.
        self.assertEqual(resp.data['avg_days_signature_to_commissioning'], 10)
        # kWc/mois : un seul mois, 7.5 (la 2e société exclue).
        self.assertEqual(len(resp.data['kwc_by_month']), 1)
        self.assertEqual(
            Decimal(resp.data['kwc_by_month'][0]['kwc']), Decimal('7.5'))

        # xlsx.
        x = self.api.get(f'{BASE}/analytics/?export=xlsx')
        body = b''.join(x.streaming_content) if x.streaming else x.content
        self.assertTrue(body.startswith(b'PK'))


class TestCommissions(InsightsBase):
    def _set_commission(self, mode, valeur):
        prof = CompanyProfile.get(self.company)
        prof.commission_mode = mode
        prof.commission_valeur = valeur
        prof.save(update_fields=['commission_mode', 'commission_valeur'])

    def test_disabled_by_default(self):
        resp = self.api.get(f'{BASE}/commissions/')
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.data['enabled'])

    def test_pct_devis_per_commercial(self):
        self._set_commission('pct_devis', Decimal('5'))
        commercial = User.objects.create_user(
            username='comm1', password='x', role_legacy='responsable',
            company=self.company)
        client = Client.objects.create(company=self.company, nom='C1')
        lead = Lead.objects.create(
            company=self.company, nom='L1', stage='NEW', owner=commercial)
        produit = Produit.objects.create(
            company=self.company, nom='Panneau', sku='CM-1',
            prix_vente=Decimal('1000'), quantite_stock=0)
        devis = Devis.objects.create(
            company=self.company, reference='DEV-CM1', client=client,
            lead=lead, statut=Devis.Statut.ACCEPTE,
            date_acceptation=date.today())
        LigneDevis.objects.create(
            devis=devis, produit=produit, designation='P',
            quantite=Decimal('10'), prix_unitaire=Decimal('1000'))
        resp = self.api.get(f'{BASE}/commissions/')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data['enabled'])
        self.assertEqual(len(resp.data['rows']), 1)
        row = resp.data['rows'][0]
        self.assertEqual(row['commercial'], 'comm1')
        # 5 % de 10×1000 = 500.
        self.assertEqual(Decimal(row['commission']), Decimal('500'))

    def test_admin_gated(self):
        resp_user = User.objects.create_user(
            username='cm_resp', password='x', role_legacy='responsable',
            company=self.company)
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(resp_user)}')
        resp = api.get(f'{BASE}/commissions/')
        self.assertEqual(resp.status_code, 403)


class TestSalesLeaderboard(InsightsBase):
    """FG93 — classement commerciaux : CA HT, taux victoire, deal moyen, kWc."""

    def _make_devis_with_ligne(self, company, reference, client, produit,
                               lead=None, statut='accepte',
                               date_acceptation=None):
        """Crée un devis avec une ligne (total_ht calculé dynamiquement)."""
        from datetime import date
        from apps.ventes.models import Devis, LigneDevis
        devis = Devis.objects.create(
            company=company, reference=reference, client=client,
            lead=lead, statut=statut,
            date_acceptation=date_acceptation or date.today())
        LigneDevis.objects.create(
            devis=devis, produit=produit, designation='Produit test',
            quantite=Decimal('5'), prix_unitaire=Decimal('10000'))
        return devis

    def test_leaderboard_shape_and_scope(self):
        """CA HT calculé depuis les lignes ; classement borné à la société."""
        from apps.crm.models import Client
        # Crée un commercial avec un lead et un devis signé.
        owner = User.objects.create_user(
            username='lb_comm1', password='x',
            role_legacy='responsable', company=self.company)
        client = Client.objects.create(company=self.company, nom='CLI-LB')
        produit = Produit.objects.create(
            company=self.company, nom='P-LB', sku='LB-1',
            prix_vente=Decimal('10000'))
        lead = Lead.objects.create(
            company=self.company, nom='Lead LB', stage='SIGNED', owner=owner)
        self._make_devis_with_ligne(
            self.company, 'D-LB-1', client, produit, lead=lead)

        resp = self.api.get('/api/django/reporting/insights/sales-leaderboard/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('rows', resp.data)
        rows = resp.data['rows']
        self.assertTrue(len(rows) >= 1)
        row = next((r for r in rows if r['commercial'] == 'lb_comm1'), None)
        self.assertIsNotNone(row, 'lb_comm1 manquant dans le classement')
        for key in ('ca_ht', 'nb_devis_signes', 'avg_deal_ht', 'kwc'):
            self.assertIn(key, row)
        self.assertEqual(row['nb_devis_signes'], 1)
        # CA HT = 5 × 10 000 = 50 000
        self.assertEqual(Decimal(row['ca_ht']), Decimal('50000'))

    def test_other_company_excluded(self):
        """Données d'une autre société jamais incluses."""
        from datetime import date
        from apps.crm.models import Client
        other_client = Client.objects.create(company=self.other, nom='OtherCli')
        other_produit = Produit.objects.create(
            company=self.other, nom='P-OTHER', sku='OTH-1',
            prix_vente=Decimal('100'))
        User.objects.create_user(
            username='other_lbcom', password='x',
            role_legacy='responsable', company=self.other)
        from apps.ventes.models import Devis, LigneDevis
        devis = Devis.objects.create(
            company=self.other, reference='D-LB-OTHER', client=other_client,
            statut=Devis.Statut.ACCEPTE, date_acceptation=date.today())
        LigneDevis.objects.create(
            devis=devis, produit=other_produit, designation='P',
            quantite=Decimal('1'), prix_unitaire=Decimal('9999'))
        resp = self.api.get('/api/django/reporting/insights/sales-leaderboard/')
        self.assertEqual(resp.status_code, 200)
        names = {r['commercial'] for r in resp.data['rows']}
        self.assertNotIn('other_lbcom', names)

    def test_xlsx_export(self):
        resp = self.api.get(
            '/api/django/reporting/insights/sales-leaderboard/?export=xlsx')
        self.assertEqual(resp.status_code, 200)
        body = b''.join(resp.streaming_content) if resp.streaming else resp.content
        self.assertTrue(body.startswith(b'PK'))

    def test_single_calc_matches_commercial_dashboard(self):
        """WIR82 — le classement de sales_leaderboard et celui inline du
        tableau de bord commercial proviennent du MÊME calcul partagé."""
        from apps.crm.models import Client
        owner = User.objects.create_user(
            username='lb_shared', password='x',
            role_legacy='responsable', company=self.company)
        client = Client.objects.create(company=self.company, nom='CLI-SHARED')
        produit = Produit.objects.create(
            company=self.company, nom='P-SH', sku='SH-1',
            prix_vente=Decimal('10000'))
        lead = Lead.objects.create(
            company=self.company, nom='Lead SH', stage='SIGNED', owner=owner)
        self._make_devis_with_ligne(
            self.company, 'D-SH-1', client, produit, lead=lead)

        lb = self.api.get('/api/django/reporting/insights/sales-leaderboard/')
        dash = self.api.get('/api/django/reporting/commercial/dashboard/')
        self.assertEqual(lb.status_code, 200)
        self.assertEqual(dash.status_code, 200)

        def row_for(rows, name):
            return next((r for r in rows if r['commercial'] == name), None)
        r_lb = row_for(lb.data['rows'], 'lb_shared')
        r_dash = row_for(dash.data['leaderboard'], 'lb_shared')
        self.assertIsNotNone(r_lb)
        self.assertIsNotNone(r_dash)
        # Mêmes chiffres depuis les deux endpoints (calcul unique).
        for key in ('ca_ht', 'nb_devis_signes', 'avg_deal_ht', 'kwc'):
            self.assertEqual(r_lb[key], r_dash[key], key)


class TestCFGroupBy(InsightsBase):
    """FG94 — group-by sur champ personnalisé (visible_liste)."""

    def setUp(self):
        super().setUp()
        from apps.customfields.models import CustomFieldDef
        # Crée un champ visible_liste sur lead pour la société courante.
        self.cf = CustomFieldDef.objects.create(
            company=self.company, module='lead', code='segment',
            libelle='Segment', type='choice',
            options=['Résidentiel', 'Industriel'],
            visible_liste=True, actif=True)

    def test_group_by_returns_counts(self):
        """L'endpoint compte les leads par valeur du champ personnalisé."""
        Lead.objects.create(
            company=self.company, nom='L1', stage='NEW',
            custom_data={'segment': 'Résidentiel'})
        Lead.objects.create(
            company=self.company, nom='L2', stage='NEW',
            custom_data={'segment': 'Résidentiel'})
        Lead.objects.create(
            company=self.company, nom='L3', stage='NEW',
            custom_data={'segment': 'Industriel'})
        # Lead sans valeur → groupe '(vide)'.
        Lead.objects.create(company=self.company, nom='L4', stage='NEW')

        resp = self.api.get(
            '/api/django/reporting/insights/cf-group-by/'
            '?module=lead&code=segment')
        self.assertEqual(resp.status_code, 200, resp.data)
        rows = {r['valeur']: r['count'] for r in resp.data['rows']}
        self.assertEqual(rows.get('Résidentiel'), 2)
        self.assertEqual(rows.get('Industriel'), 1)
        self.assertEqual(rows.get('(vide)'), 1)
        self.assertEqual(resp.data['total'], 4)

    def test_non_visible_liste_returns_404(self):
        """Un champ non visible_liste renvoie 404."""
        from apps.customfields.models import CustomFieldDef
        CustomFieldDef.objects.create(
            company=self.company, module='lead', code='interne',
            libelle='Interne', type='text',
            visible_liste=False, actif=True)
        resp = self.api.get(
            '/api/django/reporting/insights/cf-group-by/'
            '?module=lead&code=interne')
        self.assertEqual(resp.status_code, 404)

    def test_missing_params_returns_400(self):
        resp = self.api.get('/api/django/reporting/insights/cf-group-by/')
        self.assertEqual(resp.status_code, 400)

    def test_other_company_data_excluded(self):
        """Les leads d'une autre société ne sont pas comptés."""
        Lead.objects.create(
            company=self.other, nom='LX', stage='NEW',
            custom_data={'segment': 'Résidentiel'})
        Lead.objects.create(
            company=self.company, nom='L1', stage='NEW',
            custom_data={'segment': 'Résidentiel'})
        resp = self.api.get(
            '/api/django/reporting/insights/cf-group-by/'
            '?module=lead&code=segment')
        self.assertEqual(resp.status_code, 200)
        rows = {r['valeur']: r['count'] for r in resp.data['rows']}
        # Seul le lead de la société courante (1) doit apparaître.
        self.assertEqual(rows.get('Résidentiel'), 1)
        self.assertEqual(resp.data['total'], 1)

    def test_xlsx_export(self):
        resp = self.api.get(
            '/api/django/reporting/insights/cf-group-by/'
            '?module=lead&code=segment&export=xlsx')
        self.assertEqual(resp.status_code, 200)
        body = b''.join(resp.streaming_content) if resp.streaming else resp.content
        self.assertTrue(body.startswith(b'PK'))


class TestCohorts(InsightsBase):
    """FG98 — analyse cohortes leads par mois d'acquisition."""

    def _make_lead(self, nom, stage, months_ago=0, canal=None):
        """Crée un lead dont la date_creation est décalée de months_ago mois."""
        from datetime import date as d, timedelta
        today = d.today()
        # Décaler au premier du mois cible.
        target_month = today.replace(day=1)
        for _ in range(months_ago):
            target_month = (target_month - timedelta(days=1)).replace(day=1)
        lead = Lead.objects.create(
            company=self.company, nom=nom, stage=stage,
            canal=canal or '')
        Lead.objects.filter(pk=lead.pk).update(date_creation=target_month)
        lead.refresh_from_db()
        return lead

    def test_cohorts_shape(self):
        """L'endpoint retourne from/to/cohorts."""
        resp = self.api.get('/api/django/reporting/insights/cohorts/')
        self.assertEqual(resp.status_code, 200)
        for key in ('from', 'to', 'cohorts'):
            self.assertIn(key, resp.data)
        self.assertIsInstance(resp.data['cohorts'], list)

    def test_cohorts_counts_leads_by_month(self):
        """Deux leads du mois courant appartiennent à la même cohorte."""
        self._make_lead('A', 'NEW', months_ago=0)
        self._make_lead('B', 'SIGNED', months_ago=0)
        resp = self.api.get('/api/django/reporting/insights/cohorts/')
        self.assertEqual(resp.status_code, 200)
        from datetime import date as d
        month_key = d.today().strftime('%Y-%m')
        entry = next(
            (c for c in resp.data['cohorts'] if c['cohorte'] == month_key), None)
        self.assertIsNotNone(entry, f'Cohorte {month_key} absente')
        self.assertGreaterEqual(entry['nb_leads'], 2)
        self.assertGreaterEqual(entry['nb_signes'], 1)

    def test_cohorts_taux_signature(self):
        """Taux de signature cohérent (0–100)."""
        self._make_lead('C1', 'SIGNED', months_ago=1)
        self._make_lead('C2', 'NEW', months_ago=1)
        resp = self.api.get('/api/django/reporting/insights/cohorts/')
        self.assertEqual(resp.status_code, 200)
        for entry in resp.data['cohorts']:
            self.assertGreaterEqual(entry['taux_signature'], 0)
            self.assertLessEqual(entry['taux_signature'], 100)

    def test_cohorts_company_scoped(self):
        """Les leads d'une autre société n'apparaissent pas."""
        Lead.objects.create(company=self.other, nom='Foreign', stage='NEW')
        self._make_lead('Local', 'NEW', months_ago=0)
        resp = self.api.get('/api/django/reporting/insights/cohorts/')
        total_leads = sum(c['nb_leads'] for c in resp.data['cohorts'])
        # Seulement le lead local.
        self.assertGreaterEqual(total_leads, 1)
        # Tous les leads comptés sont de la société courante.
        from apps.crm.models import Lead as L
        local_count = L.objects.filter(company=self.company, is_archived=False).count()
        self.assertEqual(total_leads, local_count)

    def test_cohorts_xlsx_export(self):
        """?export=xlsx retourne un fichier ZIP (xlsx)."""
        resp = self.api.get('/api/django/reporting/insights/cohorts/?export=xlsx')
        self.assertEqual(resp.status_code, 200)
        body = b''.join(resp.streaming_content) if resp.streaming else resp.content
        self.assertTrue(body.startswith(b'PK'))

    def test_cohorts_group_by_canal(self):
        """?group_by=canal scinde les cohortes par canal."""
        self._make_lead('G1', 'NEW', months_ago=0, canal='facebook')
        self._make_lead('G2', 'NEW', months_ago=0, canal='google')
        resp = self.api.get(
            '/api/django/reporting/insights/cohorts/?group_by=canal')
        self.assertEqual(resp.status_code, 200)
        # Les clés de cohorte contiennent un séparateur '/'.
        keys_with_canal = [
            c['cohorte'] for c in resp.data['cohorts']
            if '/' in c['cohorte']
        ]
        self.assertTrue(len(keys_with_canal) > 0,
                        'Les cohortes group_by=canal doivent avoir "mois/canal"')


class TestProfitability(InsightsBase):
    """FG99 — rentabilité par segment (ADMIN uniquement, prix achat INTERNE)."""

    def setUp(self):
        super().setUp()
        # L'utilisateur InsightsBase a role_legacy='admin' mais IsAdminRole
        # vérifie le rôle via can_view_activity_log ou role_legacy.
        # On force role_legacy='admin' déjà fait dans InsightsBase.setUp.

    def test_requires_admin_role(self):
        """Un responsable non-admin ne peut pas accéder."""
        User = get_user_model()
        resp_user = User.objects.create_user(
            username='resp_p99', password='x', role_legacy='responsable',
            company=self.company)
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(resp_user)}')
        resp = api.get('/api/django/reporting/insights/profitability/')
        self.assertEqual(resp.status_code, 403)

    def test_shape_and_200(self):
        """L'admin reçoit un 200 avec les clés attendues."""
        resp = self.api.get('/api/django/reporting/insights/profitability/')
        self.assertEqual(resp.status_code, 200)
        for key in ('internal', 'segment', 'rows',
                    'total_revenue_ht', 'total_cost_estimate', 'total_margin'):
            self.assertIn(key, resp.data, f'Clé manquante : {key}')
        self.assertTrue(resp.data['internal'])

    def test_invalid_segment_returns_400(self):
        """Un segment non supporté retourne 400."""
        resp = self.api.get(
            '/api/django/reporting/insights/profitability/?segment=invalid')
        self.assertEqual(resp.status_code, 400)

    def test_rows_have_margin_fields(self):
        """Chaque ligne contient revenue_ht, cost_estimate, margin, margin_pct."""
        from apps.installations.models import Installation
        from apps.crm.models import Client
        client = Client.objects.create(company=self.company, nom='ProfCli')
        Installation.objects.create(
            company=self.company, client=client, reference='PROF-01',
            type_installation='residentiel')
        resp = self.api.get('/api/django/reporting/insights/profitability/')
        self.assertEqual(resp.status_code, 200)
        for row in resp.data['rows']:
            for key in ('segment_value', 'count', 'revenue_ht',
                        'cost_estimate', 'margin', 'margin_pct'):
                self.assertIn(key, row, f'Clé manquante dans row: {key}')

    def test_company_scoped(self):
        """Les chantiers d'une autre société ne sont pas inclus."""
        from apps.installations.models import Installation
        from apps.crm.models import Client
        other_client = Client.objects.create(company=self.other, nom='OtherCli')
        Installation.objects.create(
            company=self.other, client=other_client, reference='OTHER-PROF')
        resp = self.api.get('/api/django/reporting/insights/profitability/')
        self.assertEqual(resp.status_code, 200)
        # total count n'inclut que la société courante
        total = sum(r['count'] for r in resp.data['rows'])
        from apps.installations.models import Installation as Inst
        local_count = Inst.objects.filter(company=self.company).count()
        self.assertEqual(total, local_count)

    def test_xlsx_export(self):
        """?export=xlsx retourne un fichier xlsx valide."""
        resp = self.api.get(
            '/api/django/reporting/insights/profitability/?export=xlsx')
        self.assertEqual(resp.status_code, 200)
        body = b''.join(resp.streaming_content) if resp.streaming else resp.content
        self.assertTrue(body.startswith(b'PK'))


class TestCfModuleModelSingleSource(TestCase):
    """WIR83 — `_cf_module_model` dérive de la source unique (registre
    customfields), sans liste dupliquée."""

    def test_resolves_native_modules_via_registry(self):
        from apps.reporting.insights import _cf_module_model
        from apps.customfields import registry
        for key in ('lead', 'client', 'produit', 'devis',
                    'installation', 'ticket'):
            self.assertIs(_cf_module_model(key), registry.get_model(key), key)

    def test_unknown_module_returns_none(self):
        from apps.reporting.insights import _cf_module_model
        self.assertIsNone(_cf_module_model('module_inexistant_zzz'))

    def test_no_hardcoded_model_imports_in_helper(self):
        """La fonction ne doit plus re-hardcoder la liste (dérive interdite)."""
        import inspect
        from apps.reporting.insights import _cf_module_model
        src = inspect.getsource(_cf_module_model)
        self.assertIn('registry.get_model', src)
        # Aucune branche if module == '...' hardcodée ne subsiste.
        self.assertNotIn("if module ==", src)
