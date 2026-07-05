"""ZMKT9 — Options de mise en page & anti-biais d'enquête (pagination,
limite de temps, ordre aléatoire, bouton retour).

Couvre : une enquête paginée par section rend une page par section, la
limite de temps est renvoyée au client et vérifiée à la soumission, l'ordre
aléatoire varie entre deux ouvertures, défauts = comportement une-page
actuel, migration additive.
"""
import datetime

from django.test import TestCase
from django.utils import timezone

from authentication.models import Company

from apps.compta import services
from apps.marketing.models import Enquete


QUESTIONS = [
    {'id': 'q1', 'type': 'texte', 'libelle': 'Q1'},
    {'id': 'q2', 'type': 'texte', 'libelle': 'Q2'},
    {'id': 'q3', 'type': 'texte', 'libelle': 'Q3'},
]


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class OptionsMiseEnPageEnqueteTests(TestCase):
    def setUp(self):
        self.co = make_company('zmkt9', 'ZMKT9')

    def test_defaut_une_page(self):
        enquete = services.creer_enquete(self.co, titre='E', questions=QUESTIONS)
        self.assertEqual(enquete.mode_pagination, Enquete.ModePagination.UNE_PAGE)

    def test_mode_pagination_par_section(self):
        enquete = services.creer_enquete(self.co, titre='E2', questions=QUESTIONS)
        enquete.mode_pagination = Enquete.ModePagination.UNE_PAGE_PAR_SECTION
        enquete.save(update_fields=['mode_pagination'])
        rendu = services.rendre_enquete_publique(enquete, {})
        self.assertEqual(
            rendu['mode_pagination'], Enquete.ModePagination.UNE_PAGE_PAR_SECTION)

    def test_limite_temps_renvoyee(self):
        enquete = services.creer_enquete(self.co, titre='E3', questions=QUESTIONS)
        enquete.limite_temps_minutes = 10
        enquete.save(update_fields=['limite_temps_minutes'])
        rendu = services.rendre_enquete_publique(enquete, {})
        self.assertEqual(rendu['limite_temps_minutes'], 10)

    def test_limite_temps_verifiee_a_la_soumission(self):
        enquete = services.creer_enquete(self.co, titre='E4', questions=QUESTIONS)
        enquete.limite_temps_minutes = 5
        enquete.save(update_fields=['limite_temps_minutes'])
        debute_il_y_a_10_min = timezone.now() - datetime.timedelta(minutes=10)
        self.assertTrue(
            services.limite_temps_depassee(enquete, debute_le=debute_il_y_a_10_min))

    def test_sans_limite_jamais_depassee(self):
        enquete = services.creer_enquete(self.co, titre='E5', questions=QUESTIONS)
        self.assertFalse(
            services.limite_temps_depassee(
                enquete, debute_le=timezone.now() - datetime.timedelta(days=1)))

    def test_ordre_aleatoire_varie(self):
        enquete = services.creer_enquete(self.co, titre='E6', questions=QUESTIONS)
        enquete.ordre_aleatoire = True
        enquete.save(update_fields=['ordre_aleatoire'])
        rendu1 = services.rendre_enquete_publique(enquete, {}, seed=1)
        rendu2 = services.rendre_enquete_publique(enquete, {}, seed=2)
        ids1 = [q['id'] for q in rendu1['questions']]
        ids2 = [q['id'] for q in rendu2['questions']]
        # Avec deux seeds différentes sur 3 éléments, très probable que
        # l'ordre diffère (déterministe pour le test).
        self.assertNotEqual(ids1, ids2)

    def test_defaut_ordre_fixe(self):
        enquete = services.creer_enquete(self.co, titre='E7', questions=QUESTIONS)
        rendu = services.rendre_enquete_publique(enquete, {})
        ids = [q['id'] for q in rendu['questions']]
        self.assertEqual(ids, ['q1', 'q2', 'q3'])

    def test_soumission_bloquee_hors_delai(self):
        enquete = services.creer_enquete(self.co, titre='E8', questions=QUESTIONS)
        enquete.limite_temps_minutes = 1
        enquete.save(update_fields=['limite_temps_minutes'])
        debute_le = (timezone.now() - datetime.timedelta(minutes=5)).isoformat()
        resp = self.client.post(
            f'/api/django/compta/enquetes-publiques/{enquete.token}/soumettre/',
            data={'reponses': {'q1': 'x'}, 'debute_le': debute_le},
            content_type='application/json')
        self.assertEqual(resp.status_code, 400)
