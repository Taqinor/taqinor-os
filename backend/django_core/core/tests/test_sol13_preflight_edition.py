"""SOL13 — le préflight de bascule d'édition est un RAPPORT, pas une action.

Deux invariants, dans cet ordre d'importance :

  1. **ZÉRO ÉCRITURE.** Prouvé au niveau SQL (aucun INSERT/UPDATE/DELETE émis),
     pas seulement en comparant deux compteurs : une commande de préflight qui
     modifie la base est un piège, et un compteur peut rester égal alors qu'une
     ligne a été réécrite.
  2. Le rapport DIT ce qu'il doit dire, en français : applications parquées
     nommées, données comptées par société, tâches beat retirées, ModuleToggle
     et permissions concernés.
"""
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.db import connection

from apps.roles.models import Role
from authentication.models import Company
from core.models import ModuleToggle
from erp_agentique.settings import editions

ECRITURES = ('insert ', 'update ', 'delete ', 'truncate ', 'alter ', 'drop ')


def _lancer(**options):
    sortie = StringIO()
    call_command('preflight_edition', stdout=sortie, stderr=StringIO(),
                 **options)
    return sortie.getvalue()


class LectureSeuleTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='Préflight', slug='sol13')
        ModuleToggle.objects.create(
            company=cls.company, module='mrp', actif=False)
        Role.objects.create(
            company=cls.company, nom='Atelier SOL13',
            permissions=['crm_voir', 'cout_non_qualite_voir'])

    def test_aucune_ecriture_sql(self):
        with CaptureQueriesContext(connection) as requetes:
            _lancer()
        fautives = [
            r['sql'] for r in requetes.captured_queries
            if any(mot in (r['sql'] or '').lower().lstrip()[:12]
                   for mot in ECRITURES)
        ]
        self.assertEqual(
            fautives, [],
            "le préflight a écrit en base — il doit être STRICTEMENT en "
            f'lecture seule : {fautives[:3]}')

    def test_aucune_ligne_creee(self):
        avant = (Company.objects.count(), ModuleToggle.objects.count(),
                 Role.objects.count())
        _lancer()
        apres = (Company.objects.count(), ModuleToggle.objects.count(),
                 Role.objects.count())
        self.assertEqual(avant, apres)

    def test_relancable(self):
        premier = _lancer()
        second = _lancer()
        self.assertIn('PRÉFLIGHT', premier)
        self.assertIn('PRÉFLIGHT', second)


class ContenuDuRapportTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='ACME SOL13', slug='sol13-b')
        ModuleToggle.objects.create(
            company=cls.company, module='sante', actif=False)
        Role.objects.create(
            company=cls.company, nom='Qualité SOL13',
            permissions=['cout_non_qualite_voir', 'crm_voir'])

    def test_les_sept_apps_parquees_sont_nommees(self):
        texte = _lancer()
        for libelle in editions.apps_parquees(editions.EDITION_SOLAR).values():
            self.assertIn(libelle, texte, libelle)

    def test_les_trois_sections_sont_presentes(self):
        texte = _lancer()
        self.assertIn('1. DONNÉES', texte)
        self.assertIn('2. TRAVAIL ASYNCHRONE', texte)
        self.assertIn('3. CONFIGURATION', texte)
        self.assertIn('RÉSUMÉ', texte)

    def test_le_rapport_est_en_francais_et_annonce_la_lecture_seule(self):
        texte = _lancer()
        self.assertIn('lecture seule, aucune écriture', texte)
        self.assertIn("Rien n'a été écrit", texte)

    def test_les_toggles_parques_sont_listes(self):
        texte = _lancer()
        self.assertIn('ACME SOL13', texte)
        self.assertIn('sante', texte)

    def test_les_taches_beat_retirees_sont_listees(self):
        texte = _lancer()
        self.assertIn('Tâches planifiées (beat) retirées par la bascule',
                      texte)
        self.assertIn('mrp.recalculer_besoins_nocturne', texte)

    def test_edition_sans_app_parquee_ne_dit_rien_a_verifier(self):
        texte = _lancer(edition=editions.EDITION_FULL)
        self.assertIn("n'a aucun impact", texte)
        self.assertNotIn('1. DONNÉES', texte)

    def test_permissions_inventoriees_et_jamais_retirees(self):
        """Le rapport INVENTORIE ; il ne touche à aucun rôle."""
        texte = _lancer()
        self.assertIn('Codes de permission appartenant à une app parquée',
                      texte)
        self.assertIn('réactiver l\'édition', texte)
        role = Role.objects.get(nom='Qualité SOL13')
        self.assertEqual(
            sorted(role.permissions),
            ['cout_non_qualite_voir', 'crm_voir'])

    def test_broker_non_interroge_par_defaut(self):
        """Hors serveur, aucun worker n'est joignable : pas d'attente inutile."""
        texte = _lancer()
        self.assertIn('Inspection du broker Celery non demandée', texte)
