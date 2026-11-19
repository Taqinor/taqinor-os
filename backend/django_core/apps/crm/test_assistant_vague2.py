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
            self.assertEqual(set(reponse.data[cle]),
                             set(modele[cle]) - {'sans_calepinage'}, cle)

    @override_settings(ASSISTANT_COPILOTE='tous')
    def test_reponse_dans_la_limite_de_taille(self):
        reponse = _api(self.admin).get(DIGEST)
        self.assertLessEqual(
            len(json.dumps(reponse.data, ensure_ascii=False, default=str)),
            LIMITE_CARACTERES)
