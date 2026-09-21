"""CAD29 — le champ « Délai (min) » annonce 0-1439 : le serveur le tient.

L'aide du champ et l'écran annoncent la borne ; les deux relecteurs de l'audit
se contredisaient sur l'existence de la validation serveur et le critique ne
l'avait pas rouverte. Vérification faite :

  * la borne HAUTE existait déjà — `CadenceRelanceEtapeSerializer.
    validate_delai_minutes` refuse 1440 et plus depuis MRY4, et
    `tests_mry4_cadence_v2.py::test_delai_minutes_au_dela_de_24h_est_refuse`
    le prouve ;
  * la borne BASSE ne tenait que par le type de la colonne
    (`PositiveIntegerField`) : selon le moteur de base, un -1 pouvait
    ressortir en erreur d'intégrité (500) au lieu d'un refus NOMMÉ. Elle est
    désormais explicite dans le sérialiseur.

Ce fichier verrouille les deux bornes ET la forme du refus : un 400 dont la
clé est LE champ fautif, avec un message français — jamais un « non
enregistré » générique (règle fondateur du 08/09/2026).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.parametres.models import CompanyProfile
from apps.parametres.models_relance import Cadence, CadenceRelanceEtape
from authentication.models import Company

User = get_user_model()

CADENCE_URL = '/api/django/parametres/cadence-relance/'

#: Les bornes ANNONCÉES par l'aide du champ (`delai_minutes.help_text`).
MINUTES_MIN = 0
MINUTES_MAX = 1439


class DelaiMinutesBornesTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='CAD29 Solaire', slug='cad29-bornes')
        CompanyProfile.objects.get_or_create(company=self.company)
        self.admin = User.objects.create_user(
            username='cad29-admin', password='pw', role_legacy='admin',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')
        CadenceRelanceEtape.seed_cadence(self.company, Cadence.CONTACT)
        self.etape = CadenceRelanceEtape.objects.filter(
            company=self.company, cadence=Cadence.CONTACT).order_by(
            'ordre').first()

    def _patch(self, valeur):
        return self.api.patch(f'{CADENCE_URL}{self.etape.id}/',
                              {'delai_minutes': valeur}, format='json')

    def test_1440_est_refuse_en_nommant_le_champ(self):
        resp = self._patch(MINUTES_MAX + 1)
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('delai_minutes', resp.data)

    def test_moins_un_est_refuse_en_nommant_le_champ(self):
        resp = self._patch(MINUTES_MIN - 1)
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('delai_minutes', resp.data)

    def test_le_refus_nest_jamais_muet(self):
        """Règle fondateur du 08/09 : l'erreur désigne le champ ET dit
        quelque chose — jamais un « non enregistré » vide."""
        for valeur in (MINUTES_MAX + 1, MINUTES_MIN - 1):
            resp = self._patch(valeur)
            messages = [str(m).strip()
                        for m in resp.data['delai_minutes']]
            self.assertTrue(messages, (valeur, resp.data))
            self.assertTrue(all(messages), (valeur, resp.data))

    def test_la_borne_haute_dit_quoi_faire_a_la_place(self):
        """Elle existait déjà (MRY4) : on la verrouille avec son message —
        « utiliser le délai en jours » est l'action, pas un refus sec."""
        resp = self._patch(MINUTES_MAX + 1)
        messages = ' '.join(str(m) for m in resp.data['delai_minutes'])
        self.assertIn('jours', messages)

    def test_les_deux_bornes_elles_memes_sont_acceptees(self):
        for valeur in (MINUTES_MIN, MINUTES_MAX):
            resp = self._patch(valeur)
            self.assertEqual(resp.status_code, 200, (valeur, resp.data))
            self.etape.refresh_from_db()
            self.assertEqual(self.etape.delai_minutes, valeur)

    def test_une_valeur_ordinaire_passe_toujours(self):
        resp = self._patch(3)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.etape.refresh_from_db()
        self.assertEqual(self.etape.delai_minutes, 3)

    def test_laide_du_champ_annonce_bien_ces_bornes(self):
        """La règle du fichier et le comportement disent la même chose."""
        aide = CadenceRelanceEtape._meta.get_field(
            'delai_minutes').help_text
        self.assertIn(str(MINUTES_MIN), aide)
        self.assertIn(str(MINUTES_MAX), aide)
