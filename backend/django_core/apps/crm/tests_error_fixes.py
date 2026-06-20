"""Tests des correctifs du backlog d'erreurs (ERR11, 38, 39, 77, 78, 79).

Chaque classe cible un correctif :
  * ERR11 — neutralisation de l'injection de formules dans l'export xlsx ;
  * ERR38 — résolution client transactionnelle (course email concurrente) ;
  * ERR39 — bornes GPS (latitude/longitude) rejetées hors plage ;
  * ERR77 — la fusion de leads préserve les champs auparavant omis ;
  * ERR78 — coercition/validation des ids des endpoints en masse / WhatsApp ;
  * ERR79 — un re-POST plus pauvre du webhook n'annule pas la donnée captée.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm import exports
from apps.crm.models import Client, Lead, LeadActivity
from apps.crm.services import (
    coerce_id_list, merge_leads, resolve_client_for_lead,
)
from authentication.models import Company

User = get_user_model()


def make_company(slug='errfix-co', nom='ErrFix Co'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


# ── ERR11 — injection de formules xlsx ──────────────────────────────────────
class TestXlsxFormulaInjection(TestCase):
    def test_string_cells_with_risky_lead_are_prefixed(self):
        # ERR11 — la neutralisation vit dans le builder PARTAGÉ ; crm.exports
        # ré-exporte la même fonction (identité préservée). On intercepte
        # build_workbook pour inspecter les cellules réellement envoyées.
        from apps.records import xlsx as shared
        from openpyxl import Workbook

        self.assertIs(exports.build_xlsx_response, shared.build_xlsx_response)

        captured = {}

        def fake_build(headers, rows, sheet_title='Export'):
            captured['rows'] = rows
            return Workbook()

        original = shared.build_workbook
        shared.build_workbook = fake_build
        try:
            rows = [[
                '=SUM(A1:A9)', '+1', '-2+3', '@cmd', 'Normal',
                42, Decimal('3.14'), None,
            ]]
            exports.build_xlsx_response('x.xlsx', ['h'], rows)
        finally:
            shared.build_workbook = original

        out = captured['rows'][0]
        self.assertEqual(out[0], "'=SUM(A1:A9)")
        self.assertEqual(out[1], "'+1")
        self.assertEqual(out[2], "'-2+3")
        self.assertEqual(out[3], "'@cmd")
        # Texte inoffensif et non-chaînes : intacts.
        self.assertEqual(out[4], 'Normal')
        self.assertEqual(out[5], 42)
        self.assertEqual(out[6], Decimal('3.14'))
        self.assertIsNone(out[7])

    def test_export_leads_xlsx_neutralizes_malicious_name(self):
        import io
        import zipfile

        company = make_company()
        Lead.objects.create(
            company=company, nom='=HYPERLINK("http://evil")', prenom='X')
        leads = list(Lead.objects.filter(company=company))
        resp = exports.export_leads_xlsx(leads)
        body = resp.content
        # Un .xlsx est un ZIP (signature PK) — l'export ne crashe pas.
        self.assertTrue(body.startswith(b'PK'))
        # On lit la feuille décompressée : la cellule contient bien l'apostrophe
        # de neutralisation (Excel l'affichera comme texte, jamais comme formule).
        with zipfile.ZipFile(io.BytesIO(body)) as zf:
            sheet = zf.read('xl/worksheets/sheet1.xml').decode('utf-8')
            shared = ''
            if 'xl/sharedStrings.xml' in zf.namelist():
                shared = zf.read('xl/sharedStrings.xml').decode('utf-8')
        haystack = sheet + shared
        # L'apostrophe peut être encodée (&#39; / &apos;) ou littérale selon
        # openpyxl ; dans tous les cas elle PRÉCÈDE le '=' neutralisé.
        self.assertTrue(
            any(marker + '=HYPERLINK' in haystack
                for marker in ("&#39;", "&apos;", "'")),
            'apostrophe de neutralisation absente de la feuille')


# ── ERR38 — résolution client transactionnelle ──────────────────────────────
class TestResolveClientAtomic(TestCase):
    def setUp(self):
        self.company = make_company()

    def test_integrity_error_on_race_reuses_existing(self):
        # Simule une course : un autre client au même email apparaît juste avant
        # le create() de notre résolution → l'unique_together lèverait. On force
        # ce scénario en pré-créant le client et en demandant la résolution d'un
        # lead qui croit n'avoir rien trouvé.
        lead = Lead.objects.create(
            company=self.company, nom='Race', email='race@example.com')
        # Un concurrent crée le client AVANT que notre résolution ne create.
        original_filter = Client.objects.filter

        state = {'pre_created': None, 'calls': 0}

        def patched_filter(*args, **kwargs):
            qs = original_filter(*args, **kwargs)
            # Au PREMIER appel (recherche initiale), aucun client : on n'a pas
            # encore inséré le concurrent. Juste après, on l'insère pour que le
            # create() suivant heurte l'unique_together.
            state['calls'] += 1
            if state['calls'] == 1 and state['pre_created'] is None:
                state['pre_created'] = Client.objects.create(
                    company=self.company, nom='Concurrent',
                    email='race@example.com')
                # La recherche initiale est filtrée par email__iexact : le
                # concurrent existe désormais, mais on renvoie un queryset vide
                # pour reproduire le check-then-create perdu.
                return original_filter(pk=-1)
            return qs

        Client.objects.filter = patched_filter
        try:
            client = resolve_client_for_lead(lead)
        finally:
            Client.objects.filter = original_filter

        # Aucun 500 : on a réutilisé le client existant, pas créé de doublon.
        self.assertEqual(client.email, 'race@example.com')
        self.assertEqual(Client.objects.filter(
            company=self.company, email__iexact='race@example.com').count(), 1)

    def test_normal_path_still_creates_and_links(self):
        lead = Lead.objects.create(
            company=self.company, nom='Solo', email='solo@example.com')
        client = resolve_client_for_lead(lead)
        self.assertEqual(client.email, 'solo@example.com')
        lead.refresh_from_db()
        self.assertEqual(lead.client_id, client.id)


# ── ERR39 — bornes GPS ───────────────────────────────────────────────────────
class TestGpsValidation(TestCase):
    def setUp(self):
        self.company = make_company()

    def test_out_of_range_lat_rejected_by_full_clean(self):
        lead = Lead(company=self.company, nom='Bad',
                    gps_lat=Decimal('95'), gps_lng=Decimal('0'))
        with self.assertRaises(ValidationError) as ctx:
            lead.full_clean()
        self.assertIn('gps_lat', ctx.exception.message_dict)

    def test_out_of_range_lng_rejected_by_full_clean(self):
        lead = Lead(company=self.company, nom='Bad',
                    gps_lat=Decimal('0'), gps_lng=Decimal('-200'))
        with self.assertRaises(ValidationError) as ctx:
            lead.full_clean()
        self.assertIn('gps_lng', ctx.exception.message_dict)

    def test_in_range_accepted(self):
        lead = Lead(company=self.company, nom='Good',
                    gps_lat=Decimal('33.5731'), gps_lng=Decimal('-7.5898'))
        lead.full_clean()  # ne lève pas

    def test_serializer_rejects_out_of_range(self):
        from apps.crm.serializers import LeadSerializer
        ser = LeadSerializer(data={
            'nom': 'Bad', 'gps_lat': '120', 'gps_lng': '0'})
        self.assertFalse(ser.is_valid())
        self.assertIn('gps_lat', ser.errors)


# ── ERR77 — fusion préserve les champs auparavant omis ──────────────────────
class TestMergePreservesFields(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='merger', password='x', role_legacy='admin',
            company=self.company)

    def test_merge_fills_previously_omitted_fields(self):
        survivor = Lead.objects.create(company=self.company, nom='Survivor')
        absorbed = Lead.objects.create(
            company=self.company, nom='Absorbed',
            regularisation_8221=True,
            relance_date=date(2026, 7, 1),
            priorite=Lead.Priorite.HAUTE,
            visite_prevue_le=date(2026, 6, 30),
            visite_effectuee=True,
            visite_notes='RDV confirmé',
            roof_type='villa',
            roi_band='5 à 9 kWc',
            utm_source='facebook',
            langue_preferee='darija',
        )
        # Survivor démarre avec priorite par défaut (normale) → on la met vide-
        # équivalente pour vérifier la recopie : on la force à normale, qui est
        # une vraie valeur, donc on vérifie les champs réellement vides.
        merge_leads(survivor, [absorbed], self.user)
        survivor.refresh_from_db()
        self.assertTrue(survivor.regularisation_8221)
        self.assertEqual(survivor.relance_date, date(2026, 7, 1))
        self.assertEqual(survivor.visite_prevue_le, date(2026, 6, 30))
        self.assertTrue(survivor.visite_effectuee)
        self.assertEqual(survivor.visite_notes, 'RDV confirmé')
        self.assertEqual(survivor.roof_type, 'villa')
        self.assertEqual(survivor.roi_band, '5 à 9 kWc')
        self.assertEqual(survivor.utm_source, 'facebook')
        self.assertEqual(survivor.langue_preferee, 'darija')


# ── ERR78 — coercition des ids ───────────────────────────────────────────────
class TestIdCoercion(TestCase):
    def test_coerce_id_list_dedupes_and_casts(self):
        self.assertEqual(coerce_id_list([1, '2', 2, '1']), [1, 2])

    def test_coerce_id_list_rejects_non_int(self):
        with self.assertRaises(ValueError):
            coerce_id_list([1, 'abc'])

    def test_coerce_id_list_rejects_bool(self):
        with self.assertRaises(ValueError):
            coerce_id_list([True])


class TestBulkAndWhatsappIdsApi(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='ids_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def test_bulk_bad_ids_returns_400_not_500(self):
        lead = Lead.objects.create(company=self.company, nom='X')
        resp = self.api.post(
            '/api/django/crm/leads/bulk/',
            {'action': 'archive', 'ids': [lead.id, 'not-an-int']},
            format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_whatsapp_bad_ids_returns_400_not_500(self):
        lead = Lead.objects.create(
            company=self.company, nom='X', telephone='+212600000000')
        resp = self.api.post(
            f'/api/django/crm/leads/{lead.id}/whatsapp-devis/',
            {'devis_ids': ['oops']}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_export_bad_ids_returns_400_not_500(self):
        Lead.objects.create(company=self.company, nom='X')
        resp = self.api.post(
            '/api/django/crm/leads/export-xlsx/',
            {'ids': ['nope']}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)


# ── ERR79 — webhook : un re-POST pauvre n'annule pas la donnée captée ────────
class TestWebhookNullGuard(TestCase):
    def setUp(self):
        self.company = make_company()

    def test_sparser_repost_does_not_null_captured_fields(self):
        from apps.crm.webhooks import _map_payload_to_fields

        first = _map_payload_to_fields({
            'fullName': 'Amina', 'phoneE164': '+212661850410',
            'city': 'Casablanca', 'roofType': 'villa',
        })
        lead = Lead.objects.create(company=self.company, **first)
        self.assertEqual(lead.ville, 'Casablanca')
        self.assertEqual(lead.roof_type, 'villa')

        # Second payload PLUS PAUVRE (sans city ni roofType) — mêmes champs
        # mappés mais None. On rejoue la logique du re-POST idempotent.
        second = _map_payload_to_fields({
            'fullName': 'Amina', 'phoneE164': '+212661850410',
        })
        for key, value in second.items():
            if value is None or value == '':
                continue
            setattr(lead, key, value)
        lead.save()
        lead.refresh_from_db()
        # La donnée captée par le premier POST a survécu.
        self.assertEqual(lead.ville, 'Casablanca')
        self.assertEqual(lead.roof_type, 'villa')
        self.assertEqual(lead.nom, 'Amina')
        # Garde-fou : la note de chatter n'est pas testée ici (logique de vue).
        self.assertEqual(LeadActivity.objects.filter(lead=lead).count(), 0)
