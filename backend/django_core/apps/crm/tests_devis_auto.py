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
import json
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm import stages
from apps.crm.devis_auto import (
    champs_manquants, champs_manquants_detail, champs_requis,
    message_manquants, source_conso, visite_avant_devis,
    visite_point_eau_avant_devis)
from apps.crm.models import Lead, LeadActivity
from apps.ventes.models import Devis

User = get_user_model()

# AGR403 — libellés du contrat ``devis_auto_pret.json`` (exemple_agricole).
LIB_HMT = "HMT (m) ou niveau d'eau"
LIB_DEBIT = ('Débit souhaité, besoin en eau (m³/jour) ou débit de la pompe '
             'actuelle')
MSG_AGRICOLE = f'Manque : {LIB_HMT}, {LIB_DEBIT}'

CONTRAT_DEVIS_AUTO = json.loads(
    (Path(__file__).resolve().parent / 'contract_samples'
     / 'devis_auto_pret.json').read_text(encoding='utf-8'))

# CIQ404 — libellés du groupe pro (industriel = exemple_industriel du contrat).
LIB_PRO = {
    'commercial': 'Consommation (kWh) ou facture mensuelle (MAD)',
    'industriel': CONTRAT_DEVIS_AUTO['exemple_industriel']['devis_auto'][
        'manquants'][0],
}


def _bloc_pro(lead):
    detail = champs_manquants_detail(lead)
    manquants = [e['label'] for e in detail]
    return {
        'pret': not manquants,
        'manquants': manquants,
        'manquants_detail': detail,
        'requis': champs_requis(lead),
        'source_conso': source_conso(lead),
        'visite_avant_devis': visite_avant_devis(lead),
    }


class TestDevisAutoProCIQ404(SimpleTestCase):
    """CIQ404 (D-CIQ-5, contrat CIQ1) — facture en MAD acceptée pour un BT,
    kWh exigés en MT, drapeau « visite avant devis ». Règle pure."""

    def _lead(self, **kw):
        return Lead(nom='Pro', **kw)

    def test_commercial_mad_sans_kwh_pret_source_facture(self):
        lead = self._lead(type_installation='commercial',
                          facture_hiver=Decimal('25000'))
        self.assertEqual(champs_manquants(lead), [])
        self.assertEqual(source_conso(lead), 'facture_hiver')

    def test_commercial_mt_et_mad_seul_pas_pret(self):
        lead = self._lead(type_installation='commercial',
                          tension_raccordement='mt',
                          facture_hiver=Decimal('25000'))
        self.assertEqual(champs_manquants(lead), [LIB_PRO['commercial']])
        self.assertIsNone(source_conso(lead))

    def test_industriel_mad_seul_tension_vide_pas_pret(self):
        lead = self._lead(type_installation='industriel',
                          facture_hiver=Decimal('40000'))
        detail = champs_manquants_detail(lead)
        self.assertEqual([e['champ'] for e in detail],
                         ['conso_mensuelle_kwh'])
        self.assertEqual(detail[0]['label'], LIB_PRO['industriel'])

    def test_industriel_bt_declaree_et_mad_pret(self):
        lead = self._lead(type_installation='industriel',
                          tension_raccordement='bt', tension_source='declare',
                          facture_hiver=Decimal('40000'))
        self.assertEqual(champs_manquants(lead), [])
        # Défaut visible du site : la basse tension n'est PAS déclarée.
        lead.tension_source = 'site_defaut_visible'
        self.assertNotEqual(champs_manquants(lead), [])

    def test_industriel_releve_seul_pret(self):
        lead = self._lead(type_installation='industriel', releve_conso={
            'mois': [{'mois': '2026-08', 'kwh': '40000.00'}],
            'source': 'lu_sur_facture'})
        self.assertEqual(champs_manquants(lead), [])
        self.assertEqual(source_conso(lead), 'releve_conso')

    def test_visite_avant_devis(self):
        mt = self._lead(type_installation='industriel',
                        tension_raccordement='mt')
        self.assertTrue(visite_avant_devis(mt)['requise'])
        self.assertIn('site en moyenne tension',
                      visite_avant_devis(mt)['motifs'])
        bt = self._lead(type_installation='commercial',
                        tension_raccordement='bt', tension_source='declare',
                        compteur_puissance_kva=Decimal('60'),
                        type_surface='toiture',
                        surface_toiture_m2=Decimal('300'))
        self.assertEqual(visite_avant_devis(bt),
                         {'requise': False, 'motifs': []})
        defaut = self._lead(type_installation='commercial',
                            tension_raccordement='bt',
                            tension_source='site_defaut_visible')
        self.assertIn('tension de raccordement inconnue',
                      visite_avant_devis(defaut)['motifs'])

    def test_residentiel_et_agricole_inchanges(self):
        for mode in ('residentiel', 'agricole', None):
            lead = self._lead(type_installation=mode)
            self.assertIsNone(visite_avant_devis(lead), mode)
            self.assertIsNone(source_conso(lead), mode)
        self.assertEqual(champs_requis(self._lead()), [['facture_hiver']])

    def test_exemples_commercial_et_industriel_du_contrat(self):
        commercial = self._lead(
            type_installation='commercial', tension_raccordement='bt',
            tension_source='declare', facture_hiver=Decimal('4000'),
            type_surface='toiture')
        self.assertEqual(
            _bloc_pro(commercial),
            CONTRAT_DEVIS_AUTO['exemple_commercial']['devis_auto'])
        industriel = self._lead(
            type_installation='industriel', tension_raccordement='mt',
            tension_source='facture', facture_hiver=Decimal('40000'),
            compteur_puissance_kva=Decimal('250'), type_surface='toiture',
            surface_toiture_m2=Decimal('2000'))
        self.assertEqual(
            _bloc_pro(industriel),
            CONTRAT_DEVIS_AUTO['exemple_industriel']['devis_auto'])

    def test_questionnaire_energie_ferme_pour_le_commercial_en_mad(self):
        from unittest import mock
        from apps.crm import questionnaire
        lead = self._lead(type_installation='commercial',
                          facture_hiver=Decimal('25000'),
                          raccordement='triphase')
        with mock.patch.object(questionnaire, '_libelles_pieces_jointes',
                               return_value=[]):
            self.assertFalse(questionnaire.manquantes(lead)['energie'])


class TestAgricoleSansCvAGR403(SimpleTestCase):
    """AGR403 (D-AGR-3, D-AGR-4) — « devis auto prêt » agricole sans le CV,
    et drapeau « visite du point d'eau avant devis ». Règle pure."""

    def _lead(self, **kwargs):
        return Lead(nom='Ferme', type_installation='agricole', **kwargs)

    def test_hmt_et_debit_sans_cv_est_pret(self):
        lead = self._lead(pompe_hmt_m=Decimal('60'),
                          pompe_debit_m3h=Decimal('20'))
        self.assertEqual(champs_manquants(lead), [])

    def test_niveau_et_besoin_m3j_est_pret(self):
        lead = self._lead(niveau_statique_m=Decimal('32'),
                          besoin_eau_m3j=Decimal('135'))
        self.assertEqual(champs_manquants(lead), [])

    def test_niveau_et_debit_actuel_avec_heures_est_pret(self):
        lead = self._lead(niveau_statique_m=Decimal('32'),
                          pompe_actuelle_debit_m3h=Decimal('10'),
                          pompage_heures_jour=Decimal('7'))
        self.assertEqual(champs_manquants(lead), [])

    def test_debit_actuel_sans_heures_n_est_pas_pret(self):
        lead = self._lead(niveau_statique_m=Decimal('32'),
                          pompe_actuelle_debit_m3h=Decimal('10'))
        self.assertEqual(champs_manquants(lead), [LIB_DEBIT])

    def test_cv_seul_n_est_pas_pret_et_nomme_les_deux_groupes(self):
        # Le CV de la pompe ACTUELLE n'est dans aucun groupe : un lead qui ne
        # porte que lui reste « pas prêt », les deux groupes nommés.
        lead = self._lead()
        self.assertEqual(
            [e['champ'] for e in champs_manquants_detail(lead)],
            ['pompe_hmt_m', 'pompe_debit_m3h'])
        self.assertEqual(champs_manquants(lead), [LIB_HMT, LIB_DEBIT])
        for groupe in champs_requis(lead):
            self.assertNotIn('pompe_cv', groupe)
            self.assertNotIn('pompe_actuelle_cv', groupe)

    def test_visite_point_eau_requise_tant_que_niveau_ou_debit_manque(self):
        lead = self._lead()
        self.assertEqual(visite_point_eau_avant_devis(lead), {
            'requise': True,
            'motifs': ["niveau d'eau du forage inconnu",
                       'débit du forage inconnu']})
        lead.niveau_statique_m = Decimal('32')
        self.assertEqual(visite_point_eau_avant_devis(lead), {
            'requise': True, 'motifs': ['débit du forage inconnu']})
        lead.debit_forage_m3h = Decimal('36')
        self.assertEqual(visite_point_eau_avant_devis(lead),
                         {'requise': False, 'motifs': []})

    def test_visite_point_eau_vaut_none_hors_agricole(self):
        for mode in (None, '', 'residentiel', 'industriel', 'commercial'):
            lead = Lead(nom='x', type_installation=mode)
            self.assertIsNone(visite_point_eau_avant_devis(lead), mode)

    def test_non_regression_residentiel_et_pro(self):
        self.assertEqual(champs_requis(Lead(nom='x')), [['facture_hiver']])
        self.assertEqual(
            champs_requis(Lead(nom='x', ete_differente=True)),
            [['facture_hiver'], ['facture_ete']])
        for mode in ('industriel', 'commercial'):
            # CIQ404 — groupe pro du contrat CIQ1.
            self.assertEqual(champs_requis(Lead(nom='x', type_installation=mode)),
                             [['conso_mensuelle_kwh', 'bill_kwh',
                               'releve_conso', 'facture_hiver']])

    def test_sortie_reelle_egale_l_exemple_agricole_du_contrat(self):
        attendu = CONTRAT_DEVIS_AUTO['exemple_agricole']['devis_auto']
        lead = self._lead()
        detail = champs_manquants_detail(lead)
        manquants = [e['label'] for e in detail]
        self.assertEqual({
            'pret': not manquants,
            'manquants': manquants,
            'manquants_detail': detail,
            'requis': champs_requis(lead),
            'visite_point_eau_avant_devis': visite_point_eau_avant_devis(lead),
        }, attendu)


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
                             [LIB_PRO[mode]], mode)
            lead.conso_mensuelle_kwh = 1234.5
            self.assertEqual(champs_manquants(lead), [], mode)

    def test_agricole_needs_the_two_hydraulic_groups(self):
        lead = self._lead(type_installation='agricole')
        self.assertEqual(champs_manquants(lead), [LIB_HMT, LIB_DEBIT])
        lead.pompe_hmt_m = 80
        self.assertEqual(champs_manquants(lead), [LIB_DEBIT])
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
        # Lead agricole : HMT + débit manquants (AGR403 — le CV de la pompe
        # actuelle ne compte plus).
        self.lead = Lead.objects.create(
            company=self.company, nom='Agriculteur',
            type_installation='agricole')

    def _post(self, lead_id=None, api=None):
        api = api or self.api
        lead_id = lead_id or self.lead.id
        return api.post(f'/api/django/crm/leads/{lead_id}/devis-auto/')

    def test_400_with_exact_french_message(self):
        resp = self._post()
        self.assertEqual(resp.status_code, 400, resp.data)
        # EXACTEMENT les champs manquants, même message que le sérialiseur.
        self.assertEqual(resp.data['detail'], MSG_AGRICOLE)
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
        self.assertEqual(resp.data['detail'], MSG_AGRICOLE)


class TestAvancerStagePourDevis(TestCase):
    """Mouvement automatique du funnel quand le statut d'un devis change.

    QJR541 — ``statut`` n'est plus écrivable au PATCH/POST : l'envoi passe par
    sa porte (``mark_devis_sent`` → événement ``devis_sent`` → récepteur crm),
    jamais par un corps brut. Un PATCH ``statut`` est IGNORÉ (200)."""

    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='devisauto_stage', password='x',
            role_legacy='responsable', company=self.company)
        self.api = make_api(self.user)
        self.lead = Lead.objects.create(company=self.company, nom='Funnel')

    def _create_devis(self, lead=None, extra=None):
        payload = {'taux_tva': '20.00', 'remise_globale': '0'}
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

    def _envoyer(self, devis_id):
        """La VRAIE porte d'envoi (lien / courriel / WhatsApp)."""
        from apps.ventes.services import mark_devis_sent
        mark_devis_sent(devis=Devis.objects.get(pk=devis_id), user=self.user)

    def _stage_acts(self):
        return LeadActivity.objects.filter(
            lead=self.lead, kind='modification', field='stage')

    def test_envoye_moves_new_to_quote_sent_and_logs(self):
        devis_id, ref = self._create_devis(self.lead)
        self._envoyer(devis_id)
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

    def test_patch_statut_accepte_ignored_lead_not_advanced(self):
        """AUD505 / QJR541 — un PATCH brut vers « accepte » ne fait rien :
        seul POST /devis/<id>/accepter/ (accept_devis) fait avancer le statut
        ET le lead. Depuis QJR541 le champ est en lecture seule : 200, statut
        inchangé (plus un 400)."""
        devis_id, ref = self._create_devis(self.lead)
        self._envoyer(devis_id)
        resp = self._patch_statut(devis_id, 'accepte')
        self.assertEqual(resp.status_code, 200, resp.data)
        devis = Devis.objects.get(pk=devis_id)
        self.assertEqual(devis.statut, 'envoye')
        self.lead.refresh_from_db()
        # Le lead reste où l'envoi l'a amené (QUOTE_SENT) — jamais SIGNED
        # via un PATCH brut.
        self.assertEqual(self.lead.stage, 'QUOTE_SENT')
        self.assertEqual(self._stage_acts().count(), 1)  # seul l'envoi a loggé

    def test_create_with_statut_envoye_stays_brouillon_stage_unmoved(self):
        """QJR541 — un POST ``statut: envoye`` crée un BROUILLON ; le lead
        n'avance pas (aucun envoi réel)."""
        devis_id, _ = self._create_devis(self.lead, {'statut': 'envoye'})
        self.assertEqual(Devis.objects.get(pk=devis_id).statut, 'brouillon')
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.stage, stages.NEW)
        self.assertEqual(self._stage_acts().count(), 0)

    def test_patch_statut_envoye_is_ignored(self):
        devis_id, _ = self._create_devis(self.lead)
        resp = self._patch_statut(devis_id, 'envoye')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(Devis.objects.get(pk=devis_id).statut, 'brouillon')
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.stage, stages.NEW)

    def test_same_statut_send_does_not_duplicate(self):
        devis_id, _ = self._create_devis(self.lead)
        self._envoyer(devis_id)
        self._envoyer(devis_id)  # idempotent
        self.assertEqual(self._stage_acts().count(), 1)

    def test_never_backwards_from_signed(self):
        self.lead.stage = 'SIGNED'
        self.lead.save(update_fields=['stage'])
        devis_id, _ = self._create_devis(self.lead)
        self._envoyer(devis_id)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.stage, 'SIGNED')
        self.assertEqual(self._stage_acts().count(), 0)

    def test_never_backwards_from_follow_up(self):
        # FOLLOW_UP est APRÈS QUOTE_SENT dans le funnel — pas de recul.
        self.lead.stage = 'FOLLOW_UP'
        self.lead.save(update_fields=['stage'])
        devis_id, _ = self._create_devis(self.lead)
        self._envoyer(devis_id)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.stage, 'FOLLOW_UP')
        self.assertEqual(self._stage_acts().count(), 0)

    def test_cold_lead_is_reactivated(self):
        # COLD = parking, pas « plus avancé » : un devis envoyé le réactive.
        self.lead.stage = 'COLD'
        self.lead.save(update_fields=['stage'])
        devis_id, _ = self._create_devis(self.lead)
        self._envoyer(devis_id)
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
        self._envoyer(devis_id)
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
        self._envoyer(devis_id)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.stage, 'QUOTE_SENT')
        self.assertEqual(self._stage_acts().count(), 1)

    def test_devis_without_lead_no_crash(self):
        from apps.crm.models import Client
        client = Client.objects.create(
            company=self.company, nom='Direct', email='direct@devisauto.com')
        devis_id, _ = self._create_devis(extra={'client': client.id})
        self._envoyer(devis_id)
        self.assertEqual(Devis.objects.get(pk=devis_id).statut, 'envoye')
        self.assertEqual(LeadActivity.objects.count(), 0)
