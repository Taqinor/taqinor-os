"""
Tests du gating « devis automatique » (devis_auto.py, champ sérialisé,
endpoint POST /leads/<id>/devis-auto/) et du mouvement automatique du
funnel quand le STATUT d'un devis change (envoye → QUOTE_SENT,
accepte → SIGNED) — clés d'étape scalaires, jamais de liste codée en dur
(STAGES.py canonique, CLAUDE.md règle #2).

Run:
    docker compose exec django_core python manage.py test \
        apps.crm.tests_devis_auto -v 2
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm import stages
from apps.crm.devis_auto import champs_manquants, message_manquants
from apps.crm.models import Lead, LeadActivity
from apps.ventes.models import Devis

User = get_user_model()


def make_company(slug='devisauto-co', nom='DevisAuto Co'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class TestChampsManquants(TestCase):
    """Règle métier pure, par mode (type_installation)."""

    def setUp(self):
        self.company = make_company()

    def _lead(self, **kwargs):
        return Lead(company=self.company, nom='Gate', **kwargs)

    def test_type_none_defaults_to_residentiel(self):
        self.assertEqual(champs_manquants(self._lead()), ['facture hiver'])
        self.assertEqual(champs_manquants(self._lead(type_installation='')),
                         ['facture hiver'])

    def test_residentiel_winter_only_when_toggle_off(self):
        lead = self._lead(type_installation='residentiel',
                          facture_hiver=650, ete_differente=False)
        # Été non différent : la facture hiver couvre toute l'année.
        self.assertEqual(champs_manquants(lead), [])

    def test_residentiel_summer_required_when_toggle_on(self):
        lead = self._lead(type_installation='residentiel',
                          facture_hiver=650, ete_differente=True)
        self.assertEqual(champs_manquants(lead), ['facture été'])
        lead.facture_ete = 900
        self.assertEqual(champs_manquants(lead), [])

    def test_residentiel_both_missing(self):
        lead = self._lead(type_installation='residentiel', ete_differente=True)
        self.assertEqual(champs_manquants(lead),
                         ['facture hiver', 'facture été'])

    def test_industriel_and_commercial_need_conso(self):
        for mode in ('industriel', 'commercial'):
            lead = self._lead(type_installation=mode)
            self.assertEqual(champs_manquants(lead),
                             ['consommation mensuelle (kWh)'], mode)
            lead.conso_mensuelle_kwh = 1234.5
            self.assertEqual(champs_manquants(lead), [], mode)

    def test_agricole_needs_pump_triplet(self):
        lead = self._lead(type_installation='agricole')
        self.assertEqual(champs_manquants(lead),
                         ['pompe (CV)', 'HMT', 'débit souhaité'])
        lead.pompe_cv = 5.5
        self.assertEqual(champs_manquants(lead), ['HMT', 'débit souhaité'])
        lead.pompe_hmt_m = 80
        lead.pompe_debit_m3h = 12
        self.assertEqual(champs_manquants(lead), [])

    def test_message_format(self):
        self.assertEqual(message_manquants(['HMT', 'débit souhaité']),
                         'Manque : HMT, débit souhaité')


class TestDevisAutoSerializerField(TestCase):
    """Le champ lecture seule `devis_auto` est exposé sur l'API leads."""

    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='devisauto_ser', password='x',
            role_legacy='responsable', company=self.company)
        self.api = make_api(self.user)

    def test_field_in_list_payload(self):
        Lead.objects.create(company=self.company, nom='PasPrêt')
        resp = self.api.get('/api/django/crm/leads/')
        self.assertEqual(resp.status_code, 200)
        data = resp.data['results'] if 'results' in resp.data else resp.data
        row = [r for r in data if r['nom'] == 'PasPrêt'][0]
        self.assertIn('devis_auto', row)
        self.assertFalse(row['devis_auto']['pret'])
        self.assertEqual(row['devis_auto']['manquants'], ['facture hiver'])
        self.assertEqual(row['devis_auto']['message'],
                         'Manque : facture hiver')

    def test_field_when_ready(self):
        lead = Lead.objects.create(
            company=self.company, nom='Prêt', facture_hiver=700)
        resp = self.api.get(f'/api/django/crm/leads/{lead.id}/')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data['devis_auto']['pret'])
        self.assertEqual(resp.data['devis_auto']['manquants'], [])
        self.assertIsNone(resp.data['devis_auto']['message'])


class TestDevisAutoEndpoint(TestCase):
    """Garde serveur POST /crm/leads/<id>/devis-auto/ — sans effet de bord."""

    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='devisauto_ep', password='x',
            role_legacy='responsable', company=self.company)
        self.api = make_api(self.user)
        # Lead agricole : pompe renseignée, HMT + débit manquants.
        self.lead = Lead.objects.create(
            company=self.company, nom='Agriculteur',
            type_installation='agricole', pompe_cv=7.5)

    def _post(self, lead_id=None, api=None):
        api = api or self.api
        lead_id = lead_id or self.lead.id
        return api.post(f'/api/django/crm/leads/{lead_id}/devis-auto/')

    def test_400_with_exact_french_message(self):
        resp = self._post()
        self.assertEqual(resp.status_code, 400, resp.data)
        # EXACTEMENT les champs manquants, même message que le sérialiseur.
        self.assertEqual(resp.data['detail'], 'Manque : HMT, débit souhaité')
        ser = self.api.get(f'/api/django/crm/leads/{self.lead.id}/').data
        self.assertEqual(ser['devis_auto']['message'], resp.data['detail'])

    def test_200_once_fields_filled(self):
        self.lead.pompe_hmt_m = 80
        self.lead.pompe_debit_m3h = 12
        self.lead.save()
        resp = self._post()
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(resp.data['ok'])
        self.assertEqual(resp.data['detail'],
                         'Lead prêt pour le devis automatique.')

    def test_no_side_effects(self):
        self._post()
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.stage, stages.NEW)
        self.assertEqual(
            LeadActivity.objects.filter(lead=self.lead).count(), 0)

    def test_company_scoped_404(self):
        other = make_company(slug='devisauto-other', nom='Other')
        intruder = User.objects.create_user(
            username='devisauto_intruder', password='x',
            role_legacy='responsable', company=other)
        resp = self._post(api=make_api(intruder))
        self.assertEqual(resp.status_code, 404)

    def test_granular_role_user_allowed(self):
        # Rôle fin façon « Commerciale » : permissions CRM seulement.
        from apps.roles.models import Role
        role = Role.objects.create(
            company=self.company, nom='Commerciale DevisAuto',
            permissions=['crm_voir', 'crm_creer', 'crm_modifier'],
        )
        commerciale = User.objects.create_user(
            username='devisauto_commerciale', password='x',
            role=role, company=self.company,
        )
        resp = self._post(api=make_api(commerciale))
        # Autorisée (la règle métier répond 400 « manquants », pas 403).
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertEqual(resp.data['detail'], 'Manque : HMT, débit souhaité')


class TestAvancerStagePourDevis(TestCase):
    """Mouvement automatique du funnel quand le statut d'un devis change,
    via l'API ventes (perform_create / perform_update)."""

    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='devisauto_stage', password='x',
            role_legacy='responsable', company=self.company)
        self.api = make_api(self.user)
        self.lead = Lead.objects.create(company=self.company, nom='Funnel')

    def _create_devis(self, lead=None, extra=None):
        payload = {'statut': 'brouillon', 'taux_tva': '20.00',
                   'remise_globale': '0'}
        if lead is not None:
            payload['lead'] = lead.id
        payload.update(extra or {})
        resp = self.api.post('/api/django/ventes/devis/', payload,
                             format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        # La référence n'est pas exposée par le sérialiseur d'écriture.
        devis = Devis.objects.get(pk=resp.data['id'])
        return devis.id, devis.reference

    def _patch_statut(self, devis_id, statut):
        return self.api.patch(f'/api/django/ventes/devis/{devis_id}/',
                              {'statut': statut}, format='json')

    def _stage_acts(self):
        return LeadActivity.objects.filter(
            lead=self.lead, kind='modification', field='stage')

    def test_envoye_moves_new_to_quote_sent_and_logs(self):
        devis_id, ref = self._create_devis(self.lead)
        resp = self._patch_statut(devis_id, 'envoye')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.stage, 'QUOTE_SENT')
        acts = self._stage_acts()
        self.assertEqual(acts.count(), 1)
        act = acts.first()
        self.assertEqual(act.field_label, 'Étape')
        self.assertEqual(act.old_value, stages.STAGE_LABELS[stages.NEW])
        self.assertEqual(act.old_value, 'Nouveau')
        self.assertEqual(act.new_value, stages.STAGE_LABELS['QUOTE_SENT'])
        self.assertEqual(act.new_value, 'Devis envoyé')
        self.assertIn('auto — devis', act.body)
        self.assertIn(ref, act.body)
        self.assertIn('envoyé', act.body)
        self.assertEqual(act.user_id, self.user.id)
        self.assertEqual(act.company_id, self.company.id)

    def test_accepte_moves_to_signed_and_logs(self):
        devis_id, ref = self._create_devis(self.lead)
        self._patch_statut(devis_id, 'envoye')
        resp = self._patch_statut(devis_id, 'accepte')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.stage, 'SIGNED')
        act = self._stage_acts().first()  # plus récent en premier
        self.assertEqual(act.new_value, stages.STAGE_LABELS['SIGNED'])
        self.assertEqual(act.new_value, 'Signé')
        self.assertIn('auto — devis', act.body)
        self.assertIn(ref, act.body)
        self.assertIn('accepté', act.body)

    def test_create_directly_envoye_moves_stage(self):
        self._create_devis(self.lead, {'statut': 'envoye'})
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.stage, 'QUOTE_SENT')
        self.assertEqual(self._stage_acts().count(), 1)

    def test_same_statut_patch_does_not_duplicate(self):
        devis_id, _ = self._create_devis(self.lead)
        self._patch_statut(devis_id, 'envoye')
        self._patch_statut(devis_id, 'envoye')  # idempotent
        self.assertEqual(self._stage_acts().count(), 1)

    def test_never_backwards_from_signed(self):
        self.lead.stage = 'SIGNED'
        self.lead.save(update_fields=['stage'])
        devis_id, _ = self._create_devis(self.lead)
        resp = self._patch_statut(devis_id, 'envoye')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.stage, 'SIGNED')
        self.assertEqual(self._stage_acts().count(), 0)

    def test_never_backwards_from_follow_up(self):
        # FOLLOW_UP est APRÈS QUOTE_SENT dans le funnel — pas de recul.
        self.lead.stage = 'FOLLOW_UP'
        self.lead.save(update_fields=['stage'])
        devis_id, _ = self._create_devis(self.lead)
        self._patch_statut(devis_id, 'envoye')
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.stage, 'FOLLOW_UP')
        self.assertEqual(self._stage_acts().count(), 0)

    def test_cold_lead_is_reactivated(self):
        # COLD = parking, pas « plus avancé » : un devis envoyé le réactive.
        self.lead.stage = 'COLD'
        self.lead.save(update_fields=['stage'])
        devis_id, _ = self._create_devis(self.lead)
        self._patch_statut(devis_id, 'envoye')
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.stage, 'QUOTE_SENT')
        acts = self._stage_acts()
        self.assertEqual(acts.count(), 1)
        self.assertEqual(acts.first().old_value, stages.STAGE_LABELS['COLD'])

    def test_lost_lead_untouched(self):
        # Marqué Perdu via le DRAPEAU (sans motif) — le funnel l'ignore.
        self.lead.perdu = True
        self.lead.save(update_fields=['perdu'])
        devis_id, _ = self._create_devis(self.lead)
        self._patch_statut(devis_id, 'accepte')
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.stage, stages.NEW)
        self.assertEqual(self._stage_acts().count(), 0)

    def test_stale_motif_but_not_perdu_still_advances(self):
        # Texte de motif résiduel mais perdu=False : ce n'est PAS perdu, le
        # funnel doit avancer normalement (le texte seul ne signale plus rien).
        self.lead.motif_perte = 'Trop cher'
        self.lead.perdu = False
        self.lead.save(update_fields=['motif_perte', 'perdu'])
        devis_id, _ = self._create_devis(self.lead)
        self._patch_statut(devis_id, 'envoye')
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.stage, 'QUOTE_SENT')
        self.assertEqual(self._stage_acts().count(), 1)

    def test_devis_without_lead_no_crash(self):
        from apps.crm.models import Client
        client = Client.objects.create(
            company=self.company, nom='Direct', email='direct@devisauto.com')
        devis_id, _ = self._create_devis(extra={'client': client.id})
        resp = self._patch_statut(devis_id, 'envoye')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(LeadActivity.objects.count(), 0)
