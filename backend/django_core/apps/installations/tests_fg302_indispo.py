"""
FG302 — Calendrier de disponibilité des ressources terrain.

``IndisponibiliteRessource`` (congé/formation/arrêt/autre) marque un TECHNICIEN
(utilisateur) OU une CAMIONNETTE (``stock.EmplacementStock``) comme indisponible
sur une fenêtre [date_debut, date_fin] inclusive. Le plan de charge (FG299), la
détection de conflits (FG300) et le nivellement (FG301) peuvent EXCLURE une
ressource absente via le sélecteur ``ressource_indisponible``.

Couvre :
  * la requête de chevauchement (``ressource_indisponible``), scopée société ;
  * la garde MODÈLE « exactement une / au moins une cible » (ni zéro, ni les
    deux) et l'ordre des dates (fin ≥ début).

Run :
    python manage.py test apps.installations.tests_fg302_indispo -v2
"""
import datetime
import itertools

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.test import TestCase

from apps.installations.models import IndisponibiliteRessource
from apps.installations.selectors import ressource_indisponible
from apps.stock.models import EmplacementStock

User = get_user_model()
_seq = itertools.count(1)


# ── Helpers ──────────────────────────────────────────────────────────────────

def make_company(slug=None, nom=None):
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'fg302-co-{n}', defaults={'nom': nom or f'FG302 Co {n}'})
    return company


def make_user(company, role='responsable', username=None):
    return User.objects.create_user(
        username=username or f'fg302-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def make_camionnette(company, nom=None):
    return EmplacementStock.objects.create(
        company=company, nom=nom or f'Camion {next(_seq)}')


LUNDI = datetime.date(2026, 6, 1)
MERCREDI = datetime.date(2026, 6, 3)
VENDREDI = datetime.date(2026, 6, 5)
SEMAINE_FIN = datetime.date(2026, 6, 7)


# ── Gardes de validation MODÈLE ───────────────────────────────────────────────

class TestIndispoGuards(TestCase):
    def setUp(self):
        self.company = make_company()
        self.tech = make_user(self.company)
        self.camion = make_camionnette(self.company)

    def test_model_clean_no_target(self):
        """FG302 — la garde modèle ``clean`` refuse l'absence de cible."""
        indispo = IndisponibiliteRessource(
            company=self.company, type_indispo='conge',
            date_debut=LUNDI, date_fin=VENDREDI)
        with self.assertRaises(DjangoValidationError):
            indispo.clean()

    def test_model_clean_both_targets(self):
        """FG302 — la garde modèle ``clean`` refuse deux cibles à la fois."""
        indispo = IndisponibiliteRessource(
            company=self.company, technicien=self.tech, camionnette=self.camion,
            type_indispo='conge', date_debut=LUNDI, date_fin=VENDREDI)
        with self.assertRaises(DjangoValidationError):
            indispo.clean()

    def test_model_clean_inverted_dates(self):
        """FG302 — la garde modèle ``clean`` refuse fin < début."""
        indispo = IndisponibiliteRessource(
            company=self.company, technicien=self.tech,
            type_indispo='conge', date_debut=VENDREDI, date_fin=LUNDI)
        with self.assertRaises(DjangoValidationError):
            indispo.clean()


# ── Sélecteur de chevauchement ────────────────────────────────────────────────

class TestRessourceIndisponibleSelector(TestCase):
    def setUp(self):
        self.company = make_company()
        self.tech = make_user(self.company)
        self.camion = make_camionnette(self.company)

    def _indispo(self, debut, fin, technicien=None, camionnette=None):
        return IndisponibiliteRessource.objects.create(
            company=self.company, technicien=technicien,
            camionnette=camionnette, type_indispo='conge',
            date_debut=debut, date_fin=fin)

    def test_overlap_detected_for_user_instance(self):
        """FG302 — un technicien en congé chevauchant la fenêtre est
        indisponible (instance utilisateur passée)."""
        self._indispo(LUNDI, VENDREDI, technicien=self.tech)
        self.assertTrue(
            ressource_indisponible(self.company, self.tech, MERCREDI, MERCREDI))

    def test_overlap_detected_for_user_id(self):
        """FG302 — un id entier est interprété comme un technicien (cas
        FG299/300/301)."""
        self._indispo(LUNDI, VENDREDI, technicien=self.tech)
        self.assertTrue(
            ressource_indisponible(self.company, self.tech.id, LUNDI, LUNDI))

    def test_overlap_detected_for_camionnette(self):
        """FG302 — une camionnette en arrêt chevauchant la fenêtre est
        indisponible (instance EmplacementStock passée)."""
        self._indispo(LUNDI, VENDREDI, camionnette=self.camion)
        self.assertTrue(
            ressource_indisponible(
                self.company, self.camion, MERCREDI, SEMAINE_FIN))

    def test_no_overlap_outside_window(self):
        """FG302 — un congé hors fenêtre ne rend pas la ressource
        indisponible."""
        self._indispo(LUNDI, MERCREDI, technicien=self.tech)
        # Fenêtre après la fin du congé.
        self.assertFalse(
            ressource_indisponible(
                self.company, self.tech, VENDREDI, SEMAINE_FIN))

    def test_inverted_window_returns_false(self):
        """FG302 — une fenêtre inversée ne contraint rien (False, jamais une
        exception)."""
        self._indispo(LUNDI, VENDREDI, technicien=self.tech)
        self.assertFalse(
            ressource_indisponible(self.company, self.tech, VENDREDI, LUNDI))

    def test_none_resource_returns_false(self):
        """FG302 — une ressource None ne contraint rien."""
        self.assertFalse(
            ressource_indisponible(self.company, None, LUNDI, VENDREDI))


# ── Scope société (sélecteur) ─────────────────────────────────────────────────

class TestIndispoTenant(TestCase):
    def setUp(self):
        self.company = make_company()
        self.tech = make_user(self.company)

    def test_selector_company_isolation(self):
        """FG302 — le sélecteur ne voit pas l'indisponibilité d'une autre
        société."""
        company_b = make_company()
        tech_b = make_user(company_b)
        IndisponibiliteRessource.objects.create(
            company=company_b, technicien=tech_b, type_indispo='conge',
            date_debut=LUNDI, date_fin=VENDREDI)
        # Société A interroge l'absence du technicien de B : invisible.
        self.assertFalse(
            ressource_indisponible(self.company, tech_b, LUNDI, VENDREDI))
        # Et B la voit bien.
        self.assertTrue(
            ressource_indisponible(company_b, tech_b, LUNDI, VENDREDI))
