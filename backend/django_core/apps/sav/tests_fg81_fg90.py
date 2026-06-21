"""
Tests FG81 (SLA), FG82 (Checklist), FG83 (RMA), FG84 (Monitoring history),
FG85 (QR équipements), FG87 (KB SAV), FG89 (Prévision pièces), FG90 (nb_tickets_12m).

Run :
    python manage.py test apps.sav.tests_fg81_fg90 --noinput
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.stock.models import Produit
from apps.installations.models import Installation
from apps.sav.models import (
    Equipement, Ticket, PieceConsommee,
    SavSlaSettings, MaintenanceChecklistTemplate, MaintenanceChecklistItem,
    TicketChecklistItem, WarrantyClaim, KbArticle,
)

User = get_user_model()


# ── Fixtures ──────────────────────────────────────────────────────────────────

def make_company(slug='sav-fg-co', nom='SAV FG Co'):
    c, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return c


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_user(company, username='fg_admin', role='admin'):
    return User.objects.create_user(
        username=username, password='x', role_legacy=role, company=company)


def make_produit(company, nom='Onduleur', sku='OND-FG'):
    return Produit.objects.create(
        company=company, nom=nom, sku=sku,
        prix_achat=Decimal('100'), prix_vente=Decimal('200'))


def make_installation(company, ref='CHT-FG'):
    client = Client.objects.create(
        company=company, nom='Client', prenom='FG',
        email=f'fg-{company.id}-{ref}@example.invalid')
    return Installation.objects.create(
        company=company, reference=ref, client=client), client


def make_equipement(company, user, produit, installation, serie='SN-FG-1'):
    eq = Equipement.objects.create(
        company=company, produit=produit, installation=installation,
        numero_serie=serie, created_by=user)
    eq.equipement_token = f'EQUIP:{eq.pk}'
    eq.save(update_fields=['equipement_token'])
    return eq


def make_ticket(company, user, client, installation, equipement=None,
                priorite='normale', statut='nouveau'):
    from apps.ventes.utils.references import create_with_reference

    def _create(ref):
        return Ticket.objects.create(
            company=company, reference=ref, client=client,
            installation=installation, equipement=equipement,
            type='correctif', priorite=priorite, statut=statut,
            date_ouverture=date.today(), created_by=user)
    return create_with_reference(Ticket, 'SAV', company, _create)


# ── FG81 — SLA ───────────────────────────────────────────────────────────────

class TestSavSlaSettings(TestCase):
    def setUp(self):
        self.co = make_company(slug='sla-co', nom='SLA Co')
        self.user = make_user(self.co, username='sla_admin')
        self.api = auth(self.user)

    def test_singleton_created_on_first_get(self):
        sla = SavSlaSettings.get(self.co)
        self.assertIsNotNone(sla.pk)
        self.assertEqual(sla.sla_response_days, 1)
        self.assertEqual(sla.sla_resolution_days, 7)
        self.assertFalse(sla.sla_breach_enabled)

    def test_days_for_uses_par_priorite(self):
        sla = SavSlaSettings.get(self.co)
        sla.sla_par_priorite = {'urgente': {'response': 0, 'resolution': 1}}
        sla.save()
        resp_days, resol_days = sla.days_for('urgente')
        self.assertEqual(resp_days, 0)
        self.assertEqual(resol_days, 1)

    def test_days_for_falls_back_to_default(self):
        sla = SavSlaSettings.get(self.co)
        resp_days, resol_days = sla.days_for('basse')
        self.assertEqual(resp_days, 1)
        self.assertEqual(resol_days, 7)

    def test_api_list_returns_singleton(self):
        r = self.api.get('/api/django/sav/sla-settings/')
        self.assertEqual(r.status_code, 200)
        self.assertIn('sla_response_days', r.data)

    def test_api_update_singleton(self):
        r = self.api.post('/api/django/sav/sla-settings/', {
            'sla_response_days': 2,
            'sla_resolution_days': 14,
            'sla_breach_enabled': True,
        }, format='json')
        self.assertEqual(r.status_code, 200)
        sla = SavSlaSettings.get(self.co)
        self.assertEqual(sla.sla_resolution_days, 14)
        self.assertTrue(sla.sla_breach_enabled)

    def test_sla_due_at_computed_at_ticket_creation(self):
        """FG81 — sla_due_at = date_ouverture + resolution_days si breach activé."""
        sla = SavSlaSettings.get(self.co)
        sla.sla_breach_enabled = True
        sla.sla_resolution_days = 5
        sla.save()

        make_produit(self.co, sku='SLAP')
        inst, client = make_installation(self.co, ref='CHT-SLA')
        r = self.api.post('/api/django/sav/tickets/', {
            'client': client.id, 'installation': inst.id,
            'description': 'test SLA', 'priorite': 'normale',
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        ticket = Ticket.objects.get(pk=r.data['id'])
        expected = date.today() + timedelta(days=5)
        self.assertEqual(ticket.sla_due_at, expected)

    def test_sla_breach_false_when_not_enabled(self):
        """FG81 — sla_due_at est None quand breach non activé."""
        make_produit(self.co, sku='SLAP2')
        inst, client = make_installation(self.co, ref='CHT-SLA2')
        r = self.api.post('/api/django/sav/tickets/', {
            'client': client.id, 'installation': inst.id,
            'description': 'no SLA', 'priorite': 'normale',
        }, format='json')
        self.assertEqual(r.status_code, 201)
        ticket = Ticket.objects.get(pk=r.data['id'])
        self.assertIsNone(ticket.sla_due_at)

    def test_recompute_sla_breach(self):
        """FG81 — recompute_sla_breach marque True si dépassé et ouvert."""
        inst, client = make_installation(self.co, ref='CHT-SLA3')
        t = make_ticket(self.co, self.user, client, inst)
        t.sla_due_at = date.today() - timedelta(days=1)
        t.statut = 'nouveau'
        t.recompute_sla_breach()
        self.assertTrue(t.sla_breach)

    def test_recompute_sla_breach_false_when_closed(self):
        inst, client = make_installation(self.co, ref='CHT-SLA4')
        t = make_ticket(self.co, self.user, client, inst)
        t.sla_due_at = date.today() - timedelta(days=1)
        t.statut = 'cloture'
        t.recompute_sla_breach()
        self.assertFalse(t.sla_breach)

    def test_premier_reponse_action(self):
        """FG81 — action premier-reponse pose date_premiere_reponse."""
        inst, client = make_installation(self.co, ref='CHT-PR1')
        t = make_ticket(self.co, self.user, client, inst)
        r = self.api.post(
            f'/api/django/sav/tickets/{t.pk}/premier-reponse/', {}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        t.refresh_from_db()
        self.assertIsNotNone(t.date_premiere_reponse)

    def test_premier_reponse_idempotent(self):
        """FG81 — un second appel ne change pas la date déjà posée."""
        inst, client = make_installation(self.co, ref='CHT-PR2')
        t = make_ticket(self.co, self.user, client, inst)
        self.api.post(f'/api/django/sav/tickets/{t.pk}/premier-reponse/', {}, format='json')
        t.refresh_from_db()
        first_ts = t.date_premiere_reponse
        self.api.post(f'/api/django/sav/tickets/{t.pk}/premier-reponse/', {}, format='json')
        t.refresh_from_db()
        self.assertEqual(t.date_premiere_reponse, first_ts)

    def test_sla_company_isolation(self):
        """FG81 — Les réglages d'une société ne sont pas visibles depuis l'autre."""
        other = make_company(slug='sla-other', nom='Other Co')
        other_user = make_user(other, username='sla_other_admin')
        other_api = auth(other_user)
        # Configurer la société principale.
        sla = SavSlaSettings.get(self.co)
        sla.sla_resolution_days = 99
        sla.save()
        # L'autre société voit ses propres réglages (défaut).
        r = other_api.get('/api/django/sav/sla-settings/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['sla_resolution_days'], 7)  # défaut, pas 99


# ── FG82 — Checklist maintenance ─────────────────────────────────────────────

class TestMaintenanceChecklist(TestCase):
    def setUp(self):
        self.co = make_company(slug='ck-co', nom='CK Co')
        self.user = make_user(self.co, username='ck_admin')
        self.api = auth(self.user)
        self.inst, self.client = make_installation(self.co, ref='CHT-CK')

    def _make_template(self):
        tmpl = MaintenanceChecklistTemplate.objects.create(
            company=self.co, nom='Visite standard')
        for i, (cle, libelle) in enumerate([
            ('panneaux', 'Nettoyage panneaux'),
            ('couples', 'Vérification couples'),
            ('logs', 'Lecture logs onduleur'),
        ]):
            MaintenanceChecklistItem.objects.create(
                company=self.co, template=tmpl, cle=cle,
                libelle=libelle, ordre=i)
        return tmpl

    def test_template_list(self):
        tmpl = self._make_template()
        r = self.api.get('/api/django/sav/checklist-templates/')
        self.assertEqual(r.status_code, 200)
        ids = [x['id'] for x in r.data['results']]
        self.assertIn(tmpl.pk, ids)

    def test_init_checklist_from_template(self):
        """FG82 — POST checklist initialise les items depuis le template."""
        tmpl = self._make_template()
        t = make_ticket(self.co, self.user, self.client, self.inst)
        r = self.api.post(
            f'/api/django/sav/tickets/{t.pk}/checklist/',
            {'template_id': tmpl.pk}, format='json')
        self.assertIn(r.status_code, [200, 201])
        items = TicketChecklistItem.objects.filter(ticket=t)
        self.assertEqual(items.count(), 3)

    def test_init_checklist_idempotent(self):
        """FG82 — Initialiser deux fois ne duplique pas les items."""
        tmpl = self._make_template()
        t = make_ticket(self.co, self.user, self.client, self.inst)
        self.api.post(f'/api/django/sav/tickets/{t.pk}/checklist/',
                      {'template_id': tmpl.pk}, format='json')
        self.api.post(f'/api/django/sav/tickets/{t.pk}/checklist/',
                      {'template_id': tmpl.pk}, format='json')
        self.assertEqual(TicketChecklistItem.objects.filter(ticket=t).count(), 3)

    def test_patch_checklist_item(self):
        """FG82 — PATCH cocher un item."""
        tmpl = self._make_template()
        t = make_ticket(self.co, self.user, self.client, self.inst)
        self.api.post(f'/api/django/sav/tickets/{t.pk}/checklist/',
                      {'template_id': tmpl.pk}, format='json')
        r = self.api.patch(f'/api/django/sav/tickets/{t.pk}/checklist/',
                           {'cle': 'panneaux', 'coche': True}, format='json')
        self.assertEqual(r.status_code, 200)
        item = TicketChecklistItem.objects.get(ticket=t, cle='panneaux')
        self.assertTrue(item.coche)
        self.assertIsNotNone(item.coche_par)

    def test_get_checklist_items(self):
        """FG82 — GET checklist liste les items."""
        tmpl = self._make_template()
        t = make_ticket(self.co, self.user, self.client, self.inst)
        self.api.post(f'/api/django/sav/tickets/{t.pk}/checklist/',
                      {'template_id': tmpl.pk}, format='json')
        r = self.api.get(f'/api/django/sav/tickets/{t.pk}/checklist/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 3)

    def test_company_isolation_template(self):
        """FG82 — Un template d'une autre société n'est pas accessible."""
        other = make_company(slug='ck-other', nom='CK Other')
        other_user = make_user(other, username='ck_other_u')
        other_api = auth(other_user)
        r = other_api.get('/api/django/sav/checklist-templates/')
        self.assertEqual(r.status_code, 200)
        # Aucun résultat pour l'autre société.
        self.assertEqual(len(r.data['results']), 0)


# ── FG83 — RMA ────────────────────────────────────────────────────────────────

class TestWarrantyClaim(TestCase):
    def setUp(self):
        self.co = make_company(slug='rma-co', nom='RMA Co')
        self.user = make_user(self.co, username='rma_admin')
        self.api = auth(self.user)
        self.prod = make_produit(self.co, sku='RMA-P')
        self.inst, self.client = make_installation(self.co, ref='CHT-RMA')
        self.equip = make_equipement(self.co, self.user, self.prod, self.inst,
                                     serie='SN-RMA-1')

    def test_create_warranty_claim(self):
        r = self.api.post('/api/django/sav/warranty-claims/', {
            'equipement': self.equip.pk,
            'description': 'Onduleur défaillant sous garantie',
            'date_signalement': date.today().isoformat(),
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['statut'], 'ouvert')

    def test_claim_linked_to_ticket(self):
        t = make_ticket(self.co, self.user, self.client, self.inst, self.equip)
        r = self.api.post('/api/django/sav/warranty-claims/', {
            'equipement': self.equip.pk,
            'ticket': t.pk,
            'description': 'Test RMA ticket',
        }, format='json')
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data['ticket'], t.pk)

    def test_update_rma_ref(self):
        claim = WarrantyClaim.objects.create(
            company=self.co, equipement=self.equip,
            statut='ouvert', created_by=self.user)
        r = self.api.patch(f'/api/django/sav/warranty-claims/{claim.pk}/', {
            'rma_ref': 'HW-2026-001',
            'statut': 'envoye',
        }, format='json')
        self.assertEqual(r.status_code, 200)
        claim.refresh_from_db()
        self.assertEqual(claim.rma_ref, 'HW-2026-001')

    def test_company_isolation(self):
        """FG83 — RMA d'une société n'est pas visible par l'autre."""
        other = make_company(slug='rma-other', nom='RMA Other')
        other_user = make_user(other, username='rma_other_u')
        WarrantyClaim.objects.create(
            company=self.co, equipement=self.equip, statut='ouvert',
            created_by=self.user)
        other_api = auth(other_user)
        r = other_api.get('/api/django/sav/warranty-claims/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['count'], 0)

    def test_filter_by_equipement(self):
        WarrantyClaim.objects.create(
            company=self.co, equipement=self.equip, statut='ouvert',
            created_by=self.user)
        r = self.api.get(f'/api/django/sav/warranty-claims/?equipement={self.equip.pk}')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['count'], 1)

    def test_cross_company_equipement_rejected(self):
        """FG83 — Équipement d'une autre société est rejeté."""
        other = make_company(slug='rma-cross', nom='RMA Cross')
        other_user = make_user(other, username='rma_cross_u')
        other_prod = make_produit(other, sku='OND-CROSS')
        other_inst, _ = make_installation(other, ref='CHT-CROSS')
        other_equip = make_equipement(other, other_user, other_prod, other_inst,
                                      serie='SN-CROSS')
        r = self.api.post('/api/django/sav/warranty-claims/', {
            'equipement': other_equip.pk,
            'description': 'Cross-company test',
        }, format='json')
        self.assertEqual(r.status_code, 400)


# ── FG85 — QR équipements ────────────────────────────────────────────────────

class TestEquipementQR(TestCase):
    def setUp(self):
        self.co = make_company(slug='qr-co', nom='QR Co')
        self.user = make_user(self.co, username='qr_admin')
        self.api = auth(self.user)
        self.prod = make_produit(self.co, sku='QR-P')
        self.inst, self.client = make_installation(self.co, ref='CHT-QR')

    def test_token_set_at_creation(self):
        """FG85 — Le jeton EQUIP:<id> est posé à la création via l'API."""
        r = self.api.post('/api/django/sav/equipements/', {
            'produit': self.prod.id, 'installation': self.inst.id,
            'numero_serie': 'SN-QR-1',
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        equip = Equipement.objects.get(pk=r.data['id'])
        self.assertEqual(equip.equipement_token, f'EQUIP:{equip.pk}')

    def test_etiquettes_action_returns_html(self):
        """FG85 — /etiquettes/ renvoie du HTML avec le token."""
        r_e = self.api.post('/api/django/sav/equipements/', {
            'produit': self.prod.id, 'installation': self.inst.id,
            'numero_serie': 'SN-QR-2',
        }, format='json')
        equip_id = r_e.data['id']
        r = self.api.get(f'/api/django/sav/equipements/etiquettes/?ids={equip_id}')
        self.assertEqual(r.status_code, 200)
        self.assertIn('text/html', r['Content-Type'])
        self.assertIn(f'EQUIP:{equip_id}', r.content.decode())

    def test_resolve_equip_token(self):
        """FG85 — /stock/produits/resolve/?code=EQUIP:<id> résout l'équipement."""
        equip = make_equipement(self.co, self.user, self.prod, self.inst,
                                serie='SN-QR-3')
        r = self.api.get(f'/api/django/stock/produits/resolve/?code=EQUIP:{equip.pk}')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['type'], 'equipement')
        self.assertEqual(r.data['id'], equip.pk)

    def test_resolve_equip_other_company_404(self):
        """FG85 — Équipement d'une autre société → 404."""
        other = make_company(slug='qr-other', nom='QR Other')
        other_user = make_user(other, username='qr_other_u')
        other_prod = make_produit(other, sku='QR-OTHER')
        other_inst, _ = make_installation(other, ref='CHT-QR-OTHER')
        other_equip = make_equipement(other, other_user, other_prod, other_inst,
                                      serie='SN-QR-OTHER')
        r = self.api.get(f'/api/django/stock/produits/resolve/?code=EQUIP:{other_equip.pk}')
        self.assertEqual(r.status_code, 404)


# ── FG87 — Base de connaissances SAV ─────────────────────────────────────────

class TestKbArticle(TestCase):
    def setUp(self):
        self.co = make_company(slug='kb-co', nom='KB Co')
        self.user = make_user(self.co, username='kb_admin')
        self.api = auth(self.user)

    def test_create_kb_article(self):
        r = self.api.post('/api/django/sav/kb-articles/', {
            'titre': 'Erreur E07 Huawei SUN2000',
            'corps': 'Vérifier les strings, tester la résistance à la terre.',
            'categorie': 'Onduleur',
            'tags': ['E07', 'Huawei', 'string'],
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['categorie'], 'Onduleur')

    def test_search_by_title(self):
        KbArticle.objects.create(
            company=self.co, titre='Code E07 onduleur', corps='Body',
            actif=True)
        r = self.api.get('/api/django/sav/kb-articles/?search=E07')
        self.assertEqual(r.status_code, 200)
        self.assertGreater(r.data['count'], 0)

    def test_filter_by_categorie(self):
        KbArticle.objects.create(
            company=self.co, titre='Pompe défaillante', corps='HMT trop élevée',
            categorie='Pompage', actif=True)
        KbArticle.objects.create(
            company=self.co, titre='Onduleur E07', corps='Check strings',
            categorie='Onduleur', actif=True)
        r = self.api.get('/api/django/sav/kb-articles/?categorie=Pompage')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['count'], 1)
        self.assertEqual(r.data['results'][0]['categorie'], 'Pompage')

    def test_company_isolation(self):
        """FG87 — Articles d'une autre société invisibles."""
        other = make_company(slug='kb-other', nom='KB Other')
        other_user = make_user(other, username='kb_other_u')
        KbArticle.objects.create(
            company=self.co, titre='Article Co1', corps='Corps', actif=True)
        other_api = auth(other_user)
        r = other_api.get('/api/django/sav/kb-articles/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['count'], 0)

    def test_filter_by_produit(self):
        """FG87 — Filtrage d'articles par produit (lien depuis ticket)."""
        prod = make_produit(self.co, sku='KB-PROD')
        KbArticle.objects.create(
            company=self.co, titre='Notice produit', corps='Instructions',
            produit=prod, actif=True)
        r = self.api.get(f'/api/django/sav/kb-articles/?produit={prod.pk}')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['count'], 1)


# ── FG89 — Prévision pièces SAV ───────────────────────────────────────────────

class TestPartsF89(TestCase):
    def setUp(self):
        self.co = make_company(slug='parts-co', nom='Parts Co')
        self.user = make_user(self.co, username='parts_admin')
        self.api = auth(self.user)
        self.prod = make_produit(self.co, sku='PIECE-1')
        self.inst, self.client = make_installation(self.co, ref='CHT-PARTS')

    def test_parts_forecast_empty(self):
        r = self.api.get('/api/django/sav/insights/sav-parts-forecast/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data, [])

    def test_parts_forecast_aggregates_consumption(self):
        t = make_ticket(self.co, self.user, self.client, self.inst)
        PieceConsommee.objects.create(
            company=self.co, ticket=t, produit=self.prod, quantite=Decimal('3'))
        r = self.api.get('/api/django/sav/insights/sav-parts-forecast/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 1)
        row = r.data[0]
        self.assertEqual(row['produit'], self.prod.pk)
        self.assertEqual(float(row['total_consomme']), 3.0)
        self.assertIn('qte_suggere_reappro', row)

    def test_parts_forecast_company_isolation(self):
        """FG89 — Les pièces d'une autre société n'apparaissent pas."""
        other = make_company(slug='parts-other', nom='Parts Other')
        other_user = make_user(other, username='parts_other_u')
        other_prod = make_produit(other, sku='PIECE-OTHER')
        other_inst, other_client = make_installation(other, ref='CHT-PARTS-O')
        t = make_ticket(other, other_user, other_client, other_inst)
        PieceConsommee.objects.create(
            company=other, ticket=t, produit=other_prod, quantite=Decimal('5'))
        r = self.api.get('/api/django/sav/insights/sav-parts-forecast/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data, [])


# ── FG90 — nb_tickets_12m ────────────────────────────────────────────────────

class TestFg90NbTickets12m(TestCase):
    def setUp(self):
        self.co = make_company(slug='fg90-co', nom='FG90 Co')
        self.user = make_user(self.co, username='fg90_admin')
        self.api = auth(self.user)
        self.prod = make_produit(self.co, sku='FG90-P')
        self.inst, self.client = make_installation(self.co, ref='CHT-FG90')
        self.equip = make_equipement(self.co, self.user, self.prod, self.inst,
                                     serie='SN-FG90')

    def test_nb_tickets_12m_zero_initially(self):
        r = self.api.get(f'/api/django/sav/equipements/{self.equip.pk}/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['nb_tickets_12m'], 0)

    def test_nb_tickets_12m_counts_recent_correctif(self):
        make_ticket(self.co, self.user, self.client, self.inst, self.equip)
        make_ticket(self.co, self.user, self.client, self.inst, self.equip)
        r = self.api.get(f'/api/django/sav/equipements/{self.equip.pk}/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['nb_tickets_12m'], 2)

    def test_nb_tickets_12m_excludes_preventif(self):
        """FG90 — Les tickets préventifs ne comptent pas."""
        from apps.ventes.utils.references import create_with_reference

        def _create(ref):
            return Ticket.objects.create(
                company=self.co, reference=ref, client=self.client,
                installation=self.inst, equipement=self.equip,
                type='preventif', statut='nouveau',
                date_ouverture=date.today(), created_by=self.user)
        create_with_reference(Ticket, 'SAV', self.co, _create)
        r = self.api.get(f'/api/django/sav/equipements/{self.equip.pk}/')
        self.assertEqual(r.data['nb_tickets_12m'], 0)

    def test_nb_tickets_ouverts_in_serializer(self):
        """FG90 — nb_tickets_ouverts et nb_tickets_12m exposés côté API."""
        make_ticket(self.co, self.user, self.client, self.inst, self.equip)
        r = self.api.get(f'/api/django/sav/equipements/{self.equip.pk}/')
        self.assertIn('nb_tickets_ouverts', r.data)
        self.assertIn('nb_tickets_12m', r.data)
        self.assertEqual(r.data['nb_tickets_ouverts'], 1)
        self.assertEqual(r.data['nb_tickets_12m'], 1)


# ── FG84 — Historique production monitoring ───────────────────────────────────

class TestFg84MonitoringHistory(TestCase):
    def setUp(self):
        from apps.monitoring.models import MonitoringConfig, ProductionReading
        self.co = make_company(slug='fg84-co', nom='FG84 Co')
        self.user = make_user(self.co, username='fg84_admin')
        self.api = auth(self.user)
        self.inst, _ = make_installation(self.co, ref='CHT-FG84')
        # Crée la config de monitoring.
        self.config = MonitoringConfig.objects.create(
            company=self.co, installation=self.inst,
            expected_annual_kwh=Decimal('12000'))
        # Insère 3 relevés sur les derniers mois.
        for i in range(3):
            d = date.today().replace(day=15) - timedelta(days=30 * i)
            ProductionReading.objects.create(
                company=self.co, installation=self.inst,
                date=d, period_days=30, energy_kwh=Decimal('900'),
                source='manual', created_by=self.user)

    def test_history_returns_data(self):
        r = self.api.get(
            f'/api/django/monitoring/configs/{self.config.pk}/history/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertIn('data', r.data)
        self.assertGreater(len(r.data['data']), 0)

    def test_history_includes_expected_kwh(self):
        r = self.api.get(
            f'/api/django/monitoring/configs/{self.config.pk}/history/')
        self.assertEqual(r.status_code, 200)
        # expected_annual_kwh renseigné → expected_kwh présent dans chaque point.
        for pt in r.data['data']:
            self.assertIn('expected_kwh', pt)
            self.assertIsNotNone(pt['expected_kwh'])
            self.assertIn('ratio_pct', pt)

    def test_history_csv_export(self):
        r = self.api.get(
            f'/api/django/monitoring/configs/{self.config.pk}/history/?export=csv')
        self.assertEqual(r.status_code, 200)
        self.assertIn('text/csv', r['Content-Type'])
        content = b''.join(r.streaming_content).decode()
        self.assertIn('month', content)
        self.assertIn('actual_kwh', content)

    def test_history_company_isolation(self):
        """FG84 — La config d'une autre société n'est pas accessible."""
        other = make_company(slug='fg84-other', nom='FG84 Other')
        other_user = make_user(other, username='fg84_other_u')
        other_api = auth(other_user)
        r = other_api.get(
            f'/api/django/monitoring/configs/{self.config.pk}/history/')
        self.assertEqual(r.status_code, 404)
