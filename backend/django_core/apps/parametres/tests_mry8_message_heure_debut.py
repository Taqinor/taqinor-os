"""Décision fondateur du 07/09/2026 — `CompanyProfile.message_heure_debut`.

MRY8 n'avait posé qu'UNE ouverture (`appel_heure_debut`, 08:30) et elle
servait à toutes les touches : un lead arrivé la nuit recevait son message
d'identité à 08:30 puis un APPEL à 08:33, avant l'heure à laquelle un appel
d'affaires se fait au Maroc. Deux ouvertures désormais — messages dès 08:30,
appels jamais avant 09:00.

Ce fichier verrouille les trois choses que le CODE ne dit pas tout seul :

  * l'opération de données de la migration 0085 REPRISE telle quelle — elle
    conserve l'heure choisie par la société pour les MESSAGES, et ne pousse
    les appels à 09:00 que si l'heure d'appel valait EXACTEMENT l'ancien
    défaut (08:30). Une société qui avait saisi 08:00 ou 09:30 n'est jamais
    réécrite ;
  * le nouveau champ voyage sur le MÊME endpoint profil que ses voisins
    (`GET`/`PATCH /api/django/parametres/`), sinon l'écran Paramètres → Leads
    afficherait un champ qui ne s'enregistre pas ;
  * une écriture du champ laisse une ligne d'audit, comme tout réglage de
    profil (AUD807).
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.parametres.models import CompanyProfile, SettingsAuditLog

User = get_user_model()

PROFIL_URL = '/api/django/parametres/'
MAJ_URL = '/api/django/parametres/update/'


def _company(slug):
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': slug})
    CompanyProfile.objects.get_or_create(company=company)
    return company


class DefautDuModeleTests(TestCase):
    """Une société créée APRÈS la migration doit naître avec les deux bonnes
    heures : c'est le défaut du modèle qui le garantit, pas la migration (qui
    ne voit que les lignes existantes)."""

    def test_une_nouvelle_societe_nait_message_0830_appel_0900(self):
        profil = CompanyProfile.objects.get(
            company=_company('mry8b-neuve'))
        self.assertEqual(profil.message_heure_debut, datetime.time(8, 30))
        self.assertEqual(profil.appel_heure_debut, datetime.time(9, 0))


class MigrationScinderLesOuverturesTests(TestCase):
    """L'opération de données de la migration 0085, exécutée telle quelle.

    On appelle la VRAIE fonction avec un registre d'applications simulé —
    jamais un `MigrationExecutor`, qui dé-migrerait la base de test partagée
    sous les autres suites (même patron que les tests de la migration 0081).
    """

    class _RegistreSimule:
        @staticmethod
        def get_model(app_label, model_name):
            assert (app_label, model_name) == (
                'parametres', 'CompanyProfile')
            return CompanyProfile

    def _migrer(self):
        from importlib import import_module

        # Nom de module commençant par un chiffre : seul `import_module` peut
        # le charger (un `import` littéral serait une erreur de syntaxe).
        module = import_module(
            'apps.parametres.migrations.0085_companyprofile_message_heure_debut')
        module.scinder_les_ouvertures(self._RegistreSimule, None)
        return module

    def test_lancien_defaut_0830_devient_message_0830_appel_0900(self):
        """La société qui n'avait JAMAIS touché au réglage : ses messages
        gardent 08:30 (l'heure à laquelle ses touches tombaient déjà) et ses
        appels reculent à 09:00 — la décision du fondateur."""
        profil = CompanyProfile.objects.get(company=_company('mry8b-defaut'))
        CompanyProfile.objects.filter(pk=profil.pk).update(
            appel_heure_debut=datetime.time(8, 30), message_heure_debut=None)
        self._migrer()
        profil.refresh_from_db()
        self.assertEqual(profil.message_heure_debut, datetime.time(8, 30))
        self.assertEqual(profil.appel_heure_debut, datetime.time(9, 0))

    def test_une_heure_saisie_a_la_main_nest_jamais_reecrite(self):
        """LE risque de cette migration : écraser un réglage choisi. Une
        société qui appelait dès 08:00 continue d'appeler à 08:00, et ses
        messages héritent de la même heure — c'est celle qu'elle avait
        choisie pour toutes ses touches."""
        for heure in (datetime.time(8, 0), datetime.time(9, 30),
                      datetime.time(10, 0)):
            with self.subTest(heure=heure):
                profil = CompanyProfile.objects.get(
                    company=_company(f'mry8b-choisie-{heure.hour}{heure.minute}'))
                CompanyProfile.objects.filter(pk=profil.pk).update(
                    appel_heure_debut=heure, message_heure_debut=None)
                self._migrer()
                profil.refresh_from_db()
                self.assertEqual(profil.appel_heure_debut, heure)
                self.assertEqual(profil.message_heure_debut, heure)

    def test_le_retour_est_un_no_op_assume(self):
        """Le reverse ne remet PAS 08:30 partout : il écraserait les heures
        saisies entre-temps. `git revert` du code suffit."""
        module = self._migrer()
        profil = CompanyProfile.objects.get(company=_company('mry8b-retour'))
        avant = (profil.message_heure_debut, profil.appel_heure_debut)
        module.noop(self._RegistreSimule, None)
        profil.refresh_from_db()
        self.assertEqual(
            (profil.message_heure_debut, profil.appel_heure_debut), avant)


class ProfilApiTests(TestCase):
    """Le champ voyage sur le MÊME endpoint que `appel_heure_debut` — un
    champ absent de la réponse serait un réglage que l'écran ne peut ni lire
    ni enregistrer."""

    def setUp(self):
        self.company = _company('mry8b-api')
        self.admin = User.objects.create_user(
            username='mry8b-admin', password='pw', role_legacy='admin',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')

    def test_le_get_expose_les_deux_ouvertures(self):
        resp = self.api.get(PROFIL_URL)
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data['message_heure_debut'], '08:30:00')
        self.assertEqual(resp.data['appel_heure_debut'], '09:00:00')

    def test_le_patch_enregistre_lheure_des_messages(self):
        resp = self.api.patch(
            MAJ_URL, {'message_heure_debut': '07:45'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        profil = CompanyProfile.objects.get(company=self.company)
        self.assertEqual(profil.message_heure_debut, datetime.time(7, 45))
        # Garde négative : l'heure des APPELS n'a pas bougé au passage.
        self.assertEqual(profil.appel_heure_debut, datetime.time(9, 0))

    def test_lecriture_laisse_une_ligne_daudit(self):
        """AUD807 — tout champ de profil écrit doit être tracé."""
        self.api.patch(
            MAJ_URL, {'message_heure_debut': '07:45'}, format='json')
        ligne = SettingsAuditLog.objects.filter(
            company=self.company, field='message_heure_debut').first()
        self.assertIsNotNone(ligne)
        self.assertEqual(ligne.field_label, 'Début des messages')

    def test_isolation_entre_societes(self):
        voisine = _company('mry8b-voisine')
        self.api.patch(
            MAJ_URL, {'message_heure_debut': '07:45'}, format='json')
        self.assertEqual(
            CompanyProfile.objects.get(company=voisine).message_heure_debut,
            datetime.time(8, 30))
