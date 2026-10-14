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
from apps.crm.models import Client, Lead, LeadActivity, RelanceEtape
from apps.crm.leads_fusion import merge_leads
from apps.crm.clients_identite import resolve_client_for_lead
from apps.crm.fiche_bulk import coerce_id_list
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
        # ERR77 × CAD106 — `relance_date` n'est plus RECOPIÉE de l'absorbée.
        # Depuis CAD106 la fusion annule les touches ouvertes de l'absorbée
        # (motif « fusion ») et le filet QJ-INVARIANT pose une prochaine
        # étape à la SURVIVANTE : sa `relance_date` est donc DÉRIVÉE de cette
        # touche. Hériter le 01/07/2026 d'un dossier qu'on vient d'absorber
        # remettrait une date passée sur une fiche dont le prochain geste est
        # réellement programmé — la file mentirait. L'assertion suit la
        # dérivation (et ne dépend plus de l'horloge du jour).
        prochaine = (survivor.relance_etapes
                     .filter(statut=RelanceEtape.Statut.A_FAIRE)
                     .order_by('due_date').first())
        self.assertIsNotNone(prochaine)
        self.assertEqual(survivor.relance_date, prochaine.due_date)
        self.assertNotEqual(survivor.relance_date, date(2026, 7, 1))
        self.assertEqual(survivor.visite_prevue_le, date(2026, 6, 30))
        self.assertTrue(survivor.visite_effectuee)
        self.assertEqual(survivor.visite_notes, 'RDV confirmé')
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
            'city': 'Casablanca', 'billRange': '1500-3000',
        })
        lead = Lead.objects.create(company=self.company, **first)
        self.assertEqual(lead.ville, 'Casablanca')
        self.assertEqual(lead.bill_range_bucket, '1500-3000')

        # Second payload PLUS PAUVRE (sans city ni billRange) — mêmes champs
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
        self.assertEqual(lead.bill_range_bucket, '1500-3000')
        self.assertEqual(lead.nom, 'Amina')
        # Garde-fou : la note de chatter n'est pas testée ici (logique de vue).
        self.assertEqual(LeadActivity.objects.filter(lead=lead).count(), 0)


# ── ENF11 — entrées que le fuzz API a vues passer en silence (200) ou en 500 ─
class TestEntreesTypeesEnf11(TestCase):
    def setUp(self):
        self.company = make_company('enf11-co', 'Enf11 Co')
        self.user = User.objects.create_user(
            username='enf11_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def test_coerce_id_list_refuse_un_flottant(self):
        with self.assertRaises(ValueError):
            coerce_id_list([2.5890419884777833e-42])

    def test_export_clients_ids_non_entiers_400_pas_500(self):
        resp = self.api.post('/api/django/crm/clients/export-xlsx/',
                             {'ids': [{}]}, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)

    def test_export_clients_ids_pas_une_liste_400(self):
        # CI #956 (fuzz « accepted schema-violating ») : `ids` est un tableau
        # au schéma ; un objet (même vide) ou null est refusé, pas « tout ».
        for ids in ({}, None, 'a', 3):
            resp = self.api.post('/api/django/crm/clients/export-xlsx/',
                                 {'ids': ids}, format='json')
            self.assertEqual(resp.status_code, 400, (ids, resp.content))
        resp = self.api.post('/api/django/crm/clients/export-xlsx/', {},
                             format='json')
        self.assertEqual(resp.status_code, 200, resp.content)

    def test_jours_non_entier_refuse_et_entier_accepte(self):
        # Contrat STRICT (schéma `integer`) : cadences-echues refuse en 400
        # nommant le champ (avant : 500 ou défaut silencieux).
        url = '/api/django/crm/relance-etapes/cadences-echues/'
        for brut in ('null', 'abc', '2.5'):
            resp = self.api.get(url, {'jours': brut})
            self.assertEqual(resp.status_code, 400, (brut, resp.content))
            self.assertIn('jours', resp.data)
        self.assertEqual(self.api.get(url, {'jours': 10}).status_code, 200)
        # Contrat TOLÉRANT (97f493887, règle produit MRY19/MRY21/CAD87 ; schéma
        # `schema_docs.P_JOURS` = entier OU texte) : les trois agrégats KPI
        # retombent sur le défaut au lieu de bloquer un tableau de bord.
        for url in ('/api/django/crm/leads/kpi-cadences/',
                    '/api/django/crm/leads/kpi-premier-contact/',
                    '/api/django/crm/leads/mesure-cadence/'):
            for brut in ('null', 'abc', '2.5'):
                resp = self.api.get(url, {'jours': brut})
                self.assertEqual(resp.status_code, 200, (url, brut, resp.content))
            self.assertEqual(self.api.get(url, {'jours': 10}).status_code, 200)
            # hors plage : borné [1, 365], pas refusé.
            self.assertEqual(
                self.api.get(url, {'jours': 99999}).status_code, 200, url)

    def test_cadences_echues_jours_enorme_ne_leve_plus_500(self):
        resp = self.api.get('/api/django/crm/relance-etapes/cadences-echues/',
                            {'jours': 999999999})
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data['count'], 0)

    def test_attribution_date_impossible_400(self):
        resp = self.api.get('/api/django/crm/rapports/attribution/',
                            {'debut': '2026-13-45'})
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertIn('debut', resp.data)

    def test_booleen_strict_sur_canaux(self):
        corps = {'cle': 'enf11', 'libelle': 'Enf11', 'ordre': 0}
        resp = self.api.post('/api/django/crm/canaux/',
                             {**corps, 'archived': 0}, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)
        resp = self.api.post('/api/django/crm/canaux/',
                             {**corps, 'archived': False}, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)

    def test_ce_navigateur_corps_non_objet_400(self):
        resp = self.api.post('/api/django/crm/appareils-equipe/ce-navigateur/',
                             'texte nu', format='json')
        self.assertEqual(resp.status_code, 400, resp.content)
        resp = self.api.post('/api/django/crm/appareils-equipe/ce-navigateur/',
                             {'navigateur': {}}, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)

    def test_fait_langue_liste_400_pas_500(self):
        lead = Lead.objects.create(company=self.company, nom='Fait liste')
        etape = RelanceEtape.objects.create(
            company=self.company, lead=lead, cadence='contact', ordre=1,
            canal=RelanceEtape.Canal.APPEL, libelle='Appeler',
            due_date=date(2030, 1, 1))
        resp = self.api.post(
            f'/api/django/crm/relance-etapes/{etape.pk}/fait/',
            {'langue': [None, None]}, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)


class TestChampsApiEnf11(TestCase):
    def test_booleen_strict(self):
        from apps.crm.champs_api import BooleenStrict
        from rest_framework.exceptions import ValidationError as DRFError

        champ = BooleenStrict()
        self.assertIs(champ.run_validation(True), True)
        self.assertIs(champ.run_validation('false'), False)
        for brut in (0, 1, 'yes', 'on', [], {}):
            with self.assertRaises(DRFError):
                champ.run_validation(brut)

    def test_date_heure_ancienne_reste_rfc3339(self):
        import datetime

        from apps.crm.champs_api import DateHeureRfc3339

        ancienne = datetime.datetime(
            960, 3, 6, 12, 30, tzinfo=datetime.timezone.utc)
        rendu = DateHeureRfc3339().to_representation(ancienne)
        self.assertRegex(rendu, r'(Z|[+-]\d\d:\d\d)$', rendu)

    def test_email_et_url_blancs_publies_comme_tels(self):
        from drf_spectacular.openapi import AutoSchema
        from rest_framework import serializers

        from apps.crm import champs_api

        # L'import enregistre l'extension de schéma (métaclasse drf-spectacular).
        self.assertTrue(champs_api._EmailBlancAutorise.match_subclasses)
        for champ in (serializers.EmailField(allow_blank=True),
                      serializers.URLField(allow_blank=True)):
            schema = AutoSchema()._map_serializer_field(champ, 'response')
            self.assertIn('anyOf', schema)
            self.assertNotIn('format', schema)
        strict = AutoSchema()._map_serializer_field(
            serializers.EmailField(), 'response')
        self.assertEqual(strict.get('format'), 'email')


# ── ERR-ENF11-FUZZ-CRM (2e tour, nocturne 13/10) — 500, 409, entrées typées ──
class TestFuzzCrmTour2(TestCase):
    def setUp(self):
        self.company = make_company('fuzz2-co', 'Fuzz2 Co')
        self.user = User.objects.create_user(
            username='fuzz2_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def test_reservation_publique_minute_impossible_400_pas_500(self):
        resp = self.api.post(
            '/api/django/crm/public/booking/jeton-inconnu/reserve/',
            {'scheduled_at': '2024-01-01T12:99:00Z'}, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)

    def test_objectifs_metric_hors_enum_400_pas_500(self):
        url = '/api/django/crm/objectifs/'
        for brut in ('$\x00Q', 'inconnue'):
            resp = self.api.get(url, {'metric': brut})
            self.assertEqual(resp.status_code, 400, (brut, resp.content))
            self.assertIn('metric', resp.data)
        resp = self.api.get(url, {'period_type': 'semaine'})
        self.assertEqual(resp.status_code, 400, resp.content)
        resp = self.api.get(url, {'metric': 'nb_leads', 'period_type': 'month'})
        self.assertEqual(resp.status_code, 200, resp.content)

    def test_point_contact_ordre_au_plafond_ne_deborde_plus(self):
        from django.utils import timezone

        from apps.crm.models import PointContact
        lead = Lead.objects.create(company=self.company, nom='Plafond')
        PointContact.objects.create(
            company=self.company, lead=lead, canal='autre',
            date_contact=timezone.now(), ordre=2147483647)
        resp = self.api.post('/api/django/crm/points-contact/',
                             {'canal': 'autre', 'lead': lead.pk},
                             format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(resp.data['ordre'], 2147483647)

    def test_doublon_client_409_unique_conflict(self):
        corps = {'nom': 'Doublon', 'email': 'doublon@exemple.ma'}
        premier = self.api.post('/api/django/crm/clients/', corps,
                                format='json')
        self.assertEqual(premier.status_code, 201, premier.content)
        second = self.api.post('/api/django/crm/clients/', corps,
                               format='json')
        self.assertEqual(second.status_code, 409, second.content)
        self.assertEqual(second.data['error']['code'], 'unique_conflict')

    def test_pagination_ignoree_reste_validee(self):
        resp = self.api.get('/api/django/crm/leads/doublons/',
                            {'page_size': 'null'})
        self.assertEqual(resp.status_code, 400, resp.content)
        resp = self.api.get('/api/django/crm/leads/doublons/',
                            {'page_size': 10})
        self.assertEqual(resp.status_code, 200, resp.content)

    def test_dates_vides_acceptees_comme_publiees(self):
        resp = self.api.get('/api/django/crm/leads/roi-sources/', {'to': ''})
        self.assertEqual(resp.status_code, 200, resp.content)
        resp = self.api.get('/api/django/crm/leads/roi-sources/',
                            {'canal': 'a\x00b'})
        self.assertEqual(resp.status_code, 400, resp.content)

    def test_corps_null_refuse(self):
        resp = self.api.post('/api/django/crm/leads/placement-cadences/',
                             {'apply': False, 'limite': None}, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertIn('limite', resp.data)
        resp = self.api.post('/api/django/crm/leads/ville-statut/',
                             {'ville': '', 'proches': None}, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)
        resp = self.api.post('/api/django/crm/appareils-equipe/ce-navigateur/',
                             {'appareil_id': '', 'navigateur': None},
                             format='json')
        self.assertEqual(resp.status_code, 400, resp.content)

    def test_texte_strict_sur_les_etiquettes(self):
        resp = self.api.post('/api/django/crm/tags/',
                             {'nom': 'Chaud', 'couleur': 0}, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)
        resp = self.api.post('/api/django/crm/tags/',
                             {'nom': 'Chaud', 'couleur': '#ff0000'},
                             format='json')
        self.assertEqual(resp.status_code, 201, resp.content)

    def test_fusion_ids_inconnus_404(self):
        lead = Lead.objects.create(company=self.company, nom='Survivant')
        resp = self.api.post(f'/api/django/crm/leads/{lead.pk}/merge/',
                             {'others': [987654321]}, format='json')
        self.assertEqual(resp.status_code, 404, resp.content)

    def test_tour3_ids_inconnus_404_et_bornes_publiees(self):
        """ERR-ENF11-FUZZ-CRM (nocturnes 11-14/10) — FK ``0``/inconnue → 404
        (``IdInconnu404Mixin``) ; mois ``0`` d'un objectif hors bornes → 400."""
        resp = self.api.post('/api/django/crm/playbook-taches/',
                             {'etape': 0, 'libelle': 'X'}, format='json')
        self.assertEqual(resp.status_code, 404, resp.content)
        self.assertIn('etape', resp.data)
        resp = self.api.post('/api/django/crm/objectifs/', {
            'cible': '1', 'metric': 'nb_rdv', 'owner': None,
            'period_month': 0, 'period_quarter': None,
            'period_year': 2026}, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertIn('period_month', resp.data)

    def test_ci997_client_fk_inconnue_404(self):
        """CI #997 fuzz — ``liste_prix``/``parent``/``tiers`` bien formés mais
        inexistants : 404 (ressource absente), plus 400 sur requête valide."""
        for champ in ('liste_prix', 'parent', 'tiers'):
            with self.subTest(champ=champ):
                resp = self.api.post(
                    '/api/django/crm/clients/',
                    {'nom': 'Client FK', champ: 987654321}, format='json')
                self.assertEqual(resp.status_code, 404, resp.content)
                self.assertIn(champ, resp.data)

    def test_tour3_corps_types_jamais_500(self):
        """ERR-ENF11-FUZZ-CRM — textes non chaîne : 400 nommé, plus de 500
        (``.strip()`` sur un nombre) ; adresse sans résultat → 404."""
        lead = Lead.objects.create(company=self.company, nom='Loc')
        for url, corps in (
                ('/api/django/crm/leads/ville-statut/', {'ville': 5}),
                ('/api/django/crm/leads/resoudre-gps/', {'lien': 5}),
                (f'/api/django/crm/leads/{lead.pk}/locataire/',
                 {'proprietaire': {'nom': 5, 'telephone': '0612345678'}})):
            with self.subTest(url=url):
                resp = self.api.post(url, corps, format='json')
                self.assertEqual(resp.status_code, 400, resp.content)
        resp = self.api.post(
            '/api/django/crm/leads/resoudre-gps/',
            {'lien': 'https://exemple.com/pas-une-carte'}, format='json')
        self.assertEqual(resp.status_code, 404, resp.content)

    def test_tour3_regles_de_corps_publiees(self):
        from drf_spectacular.generators import SchemaGenerator
        from django.urls import include, path

        from apps.crm import urls as crm_urls

        chemins = SchemaGenerator(patterns=[
            path('api/django/crm/', include(crm_urls)),
        ]).get_schema(request=None, public=True)['paths']

        def regle(route, methode='post'):
            corps = chemins[route][methode]['requestBody']['content'][
                'application/json']['schema']
            return corps['allOf'][1]

        self.assertIn('oneOf', regle('/api/django/crm/salles-vente/'))
        self.assertIn('anyOf', regle('/api/django/crm/objectifs/'))
        self.assertIn('anyOf', regle('/api/django/crm/objectifs/{id}/', 'put'))
        self.assertIn('anyOf', regle('/api/django/crm/leads/resoudre-gps/'))
        self.assertIn('anyOf', regle('/api/django/crm/leads/{id}/locataire/'))
        self.assertIn(
            'anyOf', regle('/api/django/crm/leads/{id}/convertir-client/'))
