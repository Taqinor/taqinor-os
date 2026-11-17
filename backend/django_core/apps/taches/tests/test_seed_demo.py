"""TCH169 — `manage.py seed_taches_demo` : la journée de `docs/taches/maquettes/SCENARIO.md`.

- Refus hors DEBUG ou sous des réglages de production : SANS base (`SimpleTestCase`), la garde passe avant
  tout accès aux données.
- Le semis (`TestCase`, joué par la CI) : deux lancements = mêmes comptes et mêmes lignes ; `aujourdhui/` du
  24/11 08:30 = « 0 sur 5 · essentiel 0/2 » et 3 proposées ; 15:00 = « 3 sur 5 · essentiel 1/2 » ; le rythme
  des 10 derniers jours travaillés = 5, 5, 4, 6, 3, 5, 4, 7, 5, 4 ; `--vide`, `--reinitialiser`, mot de passe
  jamais écrit dans le code.
"""
import datetime
import os
import secrets
from io import StringIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from apps.taches.choix import StatutTache
from apps.taches.management.commands import seed_taches_demo as commande
from apps.taches.models.journee import PlanJour
from apps.taches.models.projets import Projet
from apps.taches.models.taches import Tache
from apps.taches.services import journee

JOUR = datetime.date(2026, 11, 24)


def _instant(heure):
    return timezone.make_aware(datetime.datetime.combine(JOUR, datetime.time.fromisoformat(heure)))


def _semer(*arguments):
    sortie = StringIO()
    with override_settings(DEBUG=True):
        call_command('seed_taches_demo', *arguments, stdout=sortie)
    return sortie.getvalue()


class RefusTests(SimpleTestCase):
    def test_refuse_hors_debug(self):
        with override_settings(DEBUG=False), self.assertRaises(CommandError):
            call_command('seed_taches_demo', stdout=StringIO())

    def test_refuse_sous_les_reglages_de_production(self):
        with override_settings(DEBUG=True), \
                mock.patch.dict(os.environ, {'DJANGO_SETTINGS_MODULE': 'erp_agentique.settings.prod'}), \
                self.assertRaises(CommandError):
            call_command('seed_taches_demo', stdout=StringIO())


class SemisTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        _semer()
        cls.user = get_user_model().objects.get(username=commande.NOM_COMPTE)

    def _compter(self):
        return (get_user_model().objects.filter(username=commande.NOM_COMPTE).count(),
                Projet.objects.filter(proprietaire=self.user).count(),
                Tache.all_objects.filter(proprietaire=self.user).count(),
                PlanJour.objects.filter(proprietaire=self.user).count())

    def _aujourdhui(self, heure):
        return journee.aujourdhui(self.user, JOUR, _instant(heure))

    def test_le_compte_est_administrateur_avec_taches_voir_par_un_role_de_test(self):
        self.assertTrue(self.user.company.est_demo)
        self.assertEqual(self.user.role.nom, commande.NOM_ROLE)
        self.assertTrue(self.user.has_erp_permission('taches_voir'))
        self.assertFalse(self.user.has_usable_password())

    def test_deux_lancements_donnent_les_memes_comptes(self):
        avant = self._compter()
        sortie = _semer()
        self.assertIn('déjà semé', sortie)
        self.assertEqual(self._compter(), avant)
        self.assertEqual(avant[1], 5)

    def test_reinitialiser_rejoue_la_meme_journee(self):
        avant = self._compter()
        _semer('--reinitialiser')
        self.user = get_user_model().objects.get(username=commande.NOM_COMPTE)
        self.assertEqual(self._compter(), avant)

    def test_le_matin_0_sur_5_essentiel_0_sur_2_et_3_proposees(self):
        forme = self._aujourdhui('08:30')
        progression = forme['progression']
        self.assertEqual((progression['faites'], progression['essentiel_faites'], progression['essentiel_prevues']),
                         (0, 0, 2))
        self.assertEqual(forme['objectif']['nb'], 5)
        self.assertEqual(len(forme['propose']['pour_objectif']), 3)
        self.assertEqual(forme['a_trier']['boite_reception'], 5)

    def test_les_projets_ont_leurs_comptes_du_matin(self):
        ouvertes = {p.nom: Tache.objects.filter(projet=p, statut=StatutTache.A_FAIRE).count()
                    for p in Projet.objects.filter(proprietaire=self.user)}
        self.assertEqual(ouvertes, {commande.BENALI: 6, commande.SALON: 8, commande.RECRUTEMENT: 5,
                                    commande.ADMIN: 3, commande.SITE: 4})

    def test_le_rythme_des_dix_derniers_jours_travailles(self):
        comptes = list(PlanJour.objects.filter(proprietaire=self.user, jour__lt=JOUR, compte_rythme__gt=0)
                       .order_by('jour').values_list('compte_rythme', flat=True))
        self.assertEqual(comptes, [5, 5, 4, 6, 3, 5, 4, 7, 5, 4])

    def test_a_15_heures_3_sur_5_essentiel_1_sur_2(self):
        _semer('--reinitialiser', '--heure', '15:00')
        self.user = get_user_model().objects.get(username=commande.NOM_COMPTE)
        progression = self._aujourdhui('15:00')['progression']
        # regles.md §6.1 : l'activité ERP « Rappeler pour le devis » close à 10:40 compte 1 (invariant 13) en
        # plus des 3 tâches (rails, fournisseur, devis) ; SCENARIO.md §3 dit « 3 sur 5 » sans la compter.
        self.assertEqual((progression['faites'], progression['detail']['activites_closes'],
                          progression['essentiel_faites'], progression['essentiel_prevues']), (4, 1, 1, 2))

    def test_vide_ne_laisse_aucune_tache(self):
        _semer('--reinitialiser', '--vide')
        self.assertEqual(Tache.all_objects.filter(proprietaire=self.user).count(), 0)
        self.assertEqual(Projet.all_objects.filter(proprietaire=self.user).count(), 0)

    def test_le_mot_de_passe_vient_de_l_environnement(self):
        secret = secrets.token_urlsafe(16)
        with mock.patch.dict(os.environ, {commande.VARIABLE_MOT_DE_PASSE: secret}):
            _semer()
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(secret))
