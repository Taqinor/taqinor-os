"""
NTP2P11 — Plafonds de notes de frais : délai de soumission + escalade direction.

CRITÈRE D'ACCEPTATION : une note de frais soumise 45 jours après la dépense
(plafond configuré à 30 jours) affiche un WARNING au valideur SANS bloquer la
soumission.

Couvre aussi : l'escalade DIRECTION au-delà du seuil de montant (jamais un
blocage silencieux — la note part quand même), le no-op total sans plafond
configuré (comportement FG135 historique), la journalisation au chatter
générique ``records`` (ARC8, aucun modèle de chatter maison), et le fait que
ces deux champs sont posés CÔTÉ SERVEUR (jamais lus du corps).

Run :
    python manage.py test apps.frais.tests.test_ntp2p11_plafond_delai_escalade -v2
"""
import itertools
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.compta import services as compta_services
from apps.frais.models import NoteFrais, PlafondNoteFrais

User = get_user_model()
_seq = itertools.count(1)


def make_company():
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=f'ntp2p11-co-{n}', defaults={'nom': f'NTP2P11 Co {n}'})
    return company


def make_user(company, role='responsable'):
    return User.objects.create_user(
        username=f'ntp2p11-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def make_note(company, employe, *, montant, jours_apres=0,
              categorie=NoteFrais.Categorie.AUTRE):
    return NoteFrais.objects.create(
        company=company, employe=employe,
        reference=f'NDF-T-{next(_seq):04d}',
        date_frais=timezone.localdate() - timedelta(days=jours_apres),
        montant=Decimal(montant), motif='Test', categorie=categorie)


class SansPlafondTests(TestCase):
    """Non-régression : sans plafond configuré, rien ne change (FG135)."""

    def setUp(self):
        self.company = make_company()
        self.employe = make_user(self.company)

    def test_soumission_sans_warning_ni_escalade(self):
        note = make_note(self.company, self.employe, montant=99999,
                         jours_apres=365)
        compta_services.soumettre_note_frais(note)
        note.refresh_from_db()
        self.assertEqual(note.statut, NoteFrais.Statut.SOUMISE)
        self.assertEqual(note.warning_delai, '')
        self.assertFalse(note.escalade_direction)

    def test_defauts_des_nouveaux_champs_du_plafond(self):
        plafond = PlafondNoteFrais.objects.create(
            company=self.company, categorie=NoteFrais.Categorie.AUTRE,
            montant_max=Decimal('500'))
        self.assertIsNone(plafond.jours_max_apres_depense)
        self.assertIsNone(plafond.escalade_direction_au_dela_de)


class DelaiSoumissionTests(TestCase):
    """CRITÈRE D'ACCEPTATION — warning de délai, jamais bloquant."""

    def setUp(self):
        self.company = make_company()
        self.employe = make_user(self.company)
        PlafondNoteFrais.objects.create(
            company=self.company, categorie=NoteFrais.Categorie.AUTRE,
            montant_max=Decimal('5000'), jours_max_apres_depense=30)

    def test_45_jours_apres_la_depense_warning_sans_blocage(self):
        note = make_note(self.company, self.employe, montant=100,
                         jours_apres=45)
        compta_services.soumettre_note_frais(note)
        note.refresh_from_db()
        # La soumission ABOUTIT (jamais un blocage).
        self.assertEqual(note.statut, NoteFrais.Statut.SOUMISE)
        # Et le valideur voit le warning.
        self.assertIn('45 jours', note.warning_delai)
        self.assertIn('30', note.warning_delai)

    def test_dans_le_delai_aucun_warning(self):
        note = make_note(self.company, self.employe, montant=100,
                         jours_apres=10)
        compta_services.soumettre_note_frais(note)
        note.refresh_from_db()
        self.assertEqual(note.warning_delai, '')

    def test_pile_a_la_limite_aucun_warning(self):
        note = make_note(self.company, self.employe, montant=100,
                         jours_apres=30)
        compta_services.soumettre_note_frais(note)
        note.refresh_from_db()
        self.assertEqual(note.warning_delai, '')

    def test_warning_journalise_au_chatter_generique(self):
        from apps.records.models import Activity

        note = make_note(self.company, self.employe, montant=100,
                         jours_apres=45)
        compta_services.soumettre_note_frais(note)
        activites = Activity.objects.filter(company=self.company)
        self.assertTrue(
            any('45 jours' in (a.body or '') for a in activites),
            'le warning de délai doit être journalisé au chatter records')

    def test_delai_dune_autre_categorie_sans_effet(self):
        note = make_note(self.company, self.employe, montant=100,
                         jours_apres=45,
                         categorie=NoteFrais.Categorie.CARBURANT)
        compta_services.soumettre_note_frais(note)
        note.refresh_from_db()
        self.assertEqual(note.warning_delai, '')


class EscaladeDirectionTests(TestCase):

    def setUp(self):
        self.company = make_company()
        self.employe = make_user(self.company)
        PlafondNoteFrais.objects.create(
            company=self.company, categorie=NoteFrais.Categorie.AUTRE,
            montant_max=Decimal('5000'),
            escalade_direction_au_dela_de=Decimal('3000'))

    def test_au_dela_du_seuil_escalade_sans_blocage(self):
        note = make_note(self.company, self.employe, montant=4000)
        compta_services.soumettre_note_frais(note)
        note.refresh_from_db()
        # Jamais un blocage silencieux : la note EST soumise.
        self.assertEqual(note.statut, NoteFrais.Statut.SOUMISE)
        self.assertTrue(note.escalade_direction)

    def test_sous_le_seuil_pas_descalade(self):
        note = make_note(self.company, self.employe, montant=2000)
        compta_services.soumettre_note_frais(note)
        note.refresh_from_db()
        self.assertFalse(note.escalade_direction)

    def test_pile_au_seuil_pas_descalade(self):
        note = make_note(self.company, self.employe, montant=3000)
        compta_services.soumettre_note_frais(note)
        note.refresh_from_db()
        self.assertFalse(note.escalade_direction)

    def test_escalade_journalisee_au_chatter(self):
        from apps.records.models import Activity

        note = make_note(self.company, self.employe, montant=4000)
        compta_services.soumettre_note_frais(note)
        self.assertTrue(
            Activity.objects.filter(
                company=self.company, field='escalade_direction',
                new_value='direction').exists())

    def test_champs_poses_serveur_pas_lus_du_corps(self):
        """Une valeur injectée à la création est écrasée à la soumission."""
        note = make_note(self.company, self.employe, montant=100)
        note.escalade_direction = True
        note.warning_delai = 'injecté'
        note.save(update_fields=['escalade_direction', 'warning_delai'])
        compta_services.soumettre_note_frais(note)
        note.refresh_from_db()
        self.assertFalse(note.escalade_direction)
        self.assertEqual(note.warning_delai, '')

    def test_plafond_dune_autre_societe_sans_effet(self):
        autre = make_company()
        employe_autre = make_user(autre)
        note = make_note(autre, employe_autre, montant=4000)
        compta_services.soumettre_note_frais(note)
        note.refresh_from_db()
        self.assertFalse(note.escalade_direction)
