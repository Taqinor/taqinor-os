"""Copilote vague 2 (BRF) — point du matin élargi et dossier d'un lead.

Couvre ``crm.digest_matin`` (blocs de la vague 2 derrière le copilote et le
droit de chaque module) et ``crm.lead.resume`` (bloc ``dossier``).

Run :
    python manage.py test apps.crm.test_assistant_vague2 -v 2
"""
import json
import pathlib
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.assistant_brief import LIMITE_CARACTERES, borner_taille
from authentication.models import Company
from apps.roles.models import Role

User = get_user_model()

DIGEST = '/api/django/crm/assistant/digest-matin/'
BLOCS_VAGUE2 = {'visites_equipe', 'calepinages', 'chantiers', 'impayes',
                'tickets'}
_SAMPLES = pathlib.Path(__file__).resolve().parent / 'contract_samples'


def _echantillon(fichier):
    return json.loads((_SAMPLES / fichier).read_text(encoding='utf-8'))


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class BornerTailleTest(SimpleTestCase):
    """BRF1 — la réponse tient en 5 000 caractères : on retire des lignes,
    jamais un compteur."""

    def _reponse(self, nb):
        ligne = {'texte': 'x' * 200}
        return {
            'relances': {'total': nb, 'lignes': [dict(ligne) for _ in range(nb)]},
            'tickets': {'ouverts': nb, 'en_retard_sla': 1,
                        'lignes': [dict(ligne) for _ in range(nb)]},
            'calepinages': {'total': 3, 'lignes': [dict(ligne)] * 3,
                            'sans_calepinage': {'total': 4, 'lignes': [dict(ligne)] * 4}},
        }

    def test_borne_les_lignes_et_garde_les_compteurs(self):
        reponse = borner_taille(self._reponse(30))
        self.assertLessEqual(len(json.dumps(reponse, ensure_ascii=False)),
                             LIMITE_CARACTERES)
        self.assertEqual(reponse['relances']['total'], 30)
        self.assertEqual(reponse['tickets']['ouverts'], 30)
        self.assertEqual(reponse['calepinages']['sans_calepinage']['total'], 4)

    def test_reponse_deja_courte_inchangee(self):
        reponse = {'visites': {'total': 0, 'en_retard': 0, 'lignes': []}}
        self.assertEqual(borner_taille(json.loads(json.dumps(reponse))), reponse)


class DigestVague2Test(TestCase):
    """BRF1 — blocs de la vague 2 : copilote ET droit du module."""

    def setUp(self):
        self.company = Company.objects.create(nom='BRF Co', slug='brf-co')
        role = Role.objects.create(
            company=self.company, nom='Commercial',
            permissions=['crm_voir', 'visites_voir'])
        self.commercial = User.objects.create_user(
            username='brf_com', password='x', role=role, company=self.company)
        self.admin = User.objects.create_user(
            username='brf_admin', password='x', company=self.company,
            is_superuser=True)

    @override_settings(ASSISTANT_COPILOTE='aucun')
    def test_copilote_eteint_aucun_bloc_et_aucun_selecteur_appele(self):
        with mock.patch('apps.crm.assistant_brief.blocs_du_matin',
                        side_effect=AssertionError('copilote éteint')):
            reponse = _api(self.admin).get(DIGEST)
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertFalse(BLOCS_VAGUE2 & set(reponse.data))
        exemple = _echantillon('assistant_digest_matin.json')['exemple']
        self.assertEqual(set(reponse.data), set(exemple))

    @override_settings(ASSISTANT_COPILOTE='tous')
    def test_copilote_allume_sans_le_droit_aucun_bloc(self):
        reponse = _api(self.commercial).get(DIGEST)
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertFalse(BLOCS_VAGUE2 & set(reponse.data))

    @override_settings(ASSISTANT_COPILOTE='tous')
    def test_copilote_allume_les_cinq_blocs_aux_formes_de_l_echantillon(self):
        reponse = _api(self.admin).get(DIGEST)
        self.assertEqual(reponse.status_code, 200, reponse.data)
        modele = _echantillon('assistant_digest_matin.json')[
            'vague2']['exemple_copilote']
        for cle in BLOCS_VAGUE2:
            self.assertIn(cle, reponse.data)
            self.assertEqual(set(reponse.data[cle]), set(modele[cle]), cle)

    @override_settings(ASSISTANT_COPILOTE='tous')
    def test_reponse_dans_la_limite_de_taille(self):
        reponse = _api(self.admin).get(DIGEST)
        self.assertLessEqual(
            len(json.dumps(reponse.data, ensure_ascii=False, default=str)),
            LIMITE_CARACTERES)


class SansCalepinageTest(TestCase):
    """BRF2 — « visite validée sans calepinage » : visite chez visites,
    calepinage chez calepinage, lead dans la portée de l'appelant."""

    def setUp(self):
        from apps.crm.models import Lead
        self.company = Company.objects.create(nom='BRF2 Co', slug='brf2-co')
        self.admin = User.objects.create_user(
            username='brf2_admin', password='x', company=self.company,
            is_superuser=True)
        self.lead = Lead.objects.create(
            company=self.company, nom='Alami', owner=self.admin)

    def _visite_validee(self, lead):
        from django.utils import timezone
        from apps.visites.models import VisiteTerrain
        return VisiteTerrain.objects.create(
            company=self.company, lead=lead, commercial=self.admin,
            statut=VisiteTerrain.Statut.VALIDEE,
            validee_le=timezone.now())

    @override_settings(ASSISTANT_COPILOTE='tous')
    def test_lead_sans_calepinage_est_liste(self):
        visite = self._visite_validee(self.lead)
        bloc = _api(self.admin).get(DIGEST).data['calepinages']
        sans = bloc['sans_calepinage']
        self.assertEqual(sans['total'], 1)
        self.assertEqual(sans['lignes'][0]['visite_id'], visite.pk)
        self.assertEqual(sans['lignes'][0]['lead_id'], self.lead.pk)
        modele = _echantillon('assistant_digest_matin.json')['vague2'][
            'exemple_copilote']['calepinages']['sans_calepinage']
        self.assertEqual(set(sans['lignes'][0]), set(modele['lignes'][0]))

    @override_settings(ASSISTANT_COPILOTE='tous')
    def test_lead_avec_calepinage_est_ecarte(self):
        from apps.calepinage.models import Calepinage
        self._visite_validee(self.lead)
        Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Toiture')
        bloc = _api(self.admin).get(DIGEST).data['calepinages']
        self.assertEqual(bloc['sans_calepinage']['total'], 0)


class DossierDuLeadTest(TestCase):
    """BRF3 — ``dossier`` du résumé : copilote allumé et droit du module."""

    def setUp(self):
        from apps.crm.models import Lead
        self.company = Company.objects.create(nom='BRF3 Co', slug='brf3-co')
        role = Role.objects.create(
            company=self.company, nom='Commercial', permissions=['crm_voir'])
        self.commercial = User.objects.create_user(
            username='brf3_com', password='x', role=role, company=self.company)
        self.admin = User.objects.create_user(
            username='brf3_admin', password='x', company=self.company,
            is_superuser=True)
        self.lead = Lead.objects.create(
            company=self.company, nom='Lahlou', owner=self.admin)
        self.url = f'/api/django/crm/leads/{self.lead.pk}/resume/'

    @override_settings(ASSISTANT_COPILOTE='aucun')
    def test_copilote_eteint_pas_de_dossier(self):
        with mock.patch('apps.crm.assistant_brief.bloc_dossier',
                        side_effect=AssertionError('copilote éteint')):
            reponse = _api(self.admin).get(self.url)
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertNotIn('dossier', reponse.data)
        exemple = _echantillon('assistant_lead_resume.json')['exemple']
        self.assertEqual(set(reponse.data), set(exemple))

    @override_settings(ASSISTANT_COPILOTE='tous')
    def test_dossier_toutes_les_cles_pour_qui_lit_tous_les_modules(self):
        reponse = _api(self.admin).get(self.url)
        self.assertEqual(reponse.status_code, 200, reponse.data)
        modele = _echantillon('assistant_lead_resume.json')['vague2'][
            'exemple_dossier_debut']
        self.assertEqual(set(reponse.data['dossier']), set(modele))
        self.assertEqual(reponse.data['dossier']['tickets'],
                         {'ouverts': 0, 'lien': None})

    @override_settings(ASSISTANT_COPILOTE='tous')
    def test_dossier_sans_le_droit_du_module_la_cle_est_absente(self):
        dossier = _api(self.commercial).get(self.url).data['dossier']
        self.assertNotIn('visite', dossier)
        self.assertNotIn('calepinage', dossier)
        self.assertNotIn('tickets', dossier)
        self.assertNotIn('factures', dossier)

    @override_settings(ASSISTANT_COPILOTE='tous')
    def test_dossier_visite_et_devis_accepte(self):
        from apps.crm.models import Client
        from apps.ventes.models import Devis
        from apps.visites.models import VisiteTerrain
        client = Client.objects.create(company=self.company, nom='BRF3')
        devis = Devis.objects.create(
            company=self.company, lead=self.lead, client=client,
            statut='accepte', reference='DEV-BRF3')
        visite = VisiteTerrain.objects.create(
            company=self.company, lead=self.lead, commercial=self.admin)
        dossier = _api(self.admin).get(self.url).data['dossier']
        self.assertEqual(dossier['visite']['id'], visite.pk)
        self.assertEqual(dossier['devis']['id'], devis.pk)
        self.assertEqual(dossier['factures']['devis_id'], devis.pk)
        modele = _echantillon('assistant_lead_resume.json')['vague2'][
            'exemple_dossier']['dossier']
        self.assertEqual(set(dossier['factures']), set(modele['factures']))
        self.assertEqual(set(dossier['devis']), set(modele['devis']))


class ControleSuiviAssistantTest(TestCase):
    """BRF4 — ``crm.controle_suivi.lire`` enveloppe la route existante."""

    def setUp(self):
        from apps.crm.agent_actions import register_crm_actions
        register_crm_actions()

    def test_action_declaree_lecture_du_lot_copilote(self):
        from apps.agent.registry import LOT_COPILOTE, RISK_INTERNAL, all_actions
        action = {a.key: a for a in all_actions()}['crm.controle_suivi.lire']
        self.assertEqual(action.lot, LOT_COPILOTE)
        self.assertEqual(action.risk, RISK_INTERNAL)
        self.assertEqual(action.method, 'GET')
        self.assertLessEqual(len(action.description), 600)
        for section in ('Sert à :', 'Ne pas utiliser pour :', 'Exemple :',
                        'Résultat :'):
            self.assertIn(section, action.description)
        self.assertIn('aucun score', action.description)
        self.assertIn('aucun classement', action.description)

    def test_la_route_repond_a_un_role_quelconque(self):
        from apps.crm.agent_actions import CONTROLE_SUIVI
        company = Company.objects.create(nom='BRF4 Co', slug='brf4-co')
        role = Role.objects.create(
            company=company, nom='Terrain', permissions=['visites_voir'])
        user = User.objects.create_user(
            username='brf4_ter', password='x', role=role, company=company)
        reponse = _api(user).get(CONTROLE_SUIVI.endpoint)
        self.assertEqual(reponse.status_code, 200, reponse.data)
        modele = _echantillon('controle_suivi.json')['exemple']
        self.assertEqual(set(reponse.data), set(modele))
