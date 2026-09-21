"""
NTP2P45 (volet compta/frais) — Notification IMMÉDIATE du valideur direction
sur une note de frais escaladée.

CRITÈRE D'ACCEPTATION : une demande d'achat/note de frais dépassant le seuil
configuré notifie IMMÉDIATEMENT l'approbateur désigné sans attendre le
prochain cycle Celery beat. Gated par
``stock.AchatsParametres.plafond_notes_frais_actif`` (NTP2P31, OFF par
défaut) : le calcul d'escalade NTP2P11 lui-même (``escalade_direction`` posé
+ journalisé au chatter) reste comportement historique inchangé QUE le
réglage soit actif ou non — seule la notification immédiate en dépend.

Run :
    python manage.py test \
        apps.compta.tests.test_ntp2p45_notif_escalade_note_frais -v2
"""
import itertools
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.compta import services as compta_services
from apps.frais.models import NoteFrais, PlafondNoteFrais
from apps.notifications.models import EventType, Notification
from apps.stock.models import AchatsParametres

User = get_user_model()
_seq = itertools.count(1)


def make_company():
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=f'ntp2p45-cf-co-{n}', defaults={'nom': f'NTP2P45-CF Co {n}'})
    return company


def make_user(company, role='responsable'):
    return User.objects.create_user(
        username=f'ntp2p45-cf-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def make_note(company, employe, *, montant):
    return NoteFrais.objects.create(
        company=company, employe=employe,
        reference=f'NDF-NTP2P45-{next(_seq):04d}',
        # `date_frais` est OBLIGATOIRE en base (DateField sans défaut) :
        # l'omettre lève une NotNullViolation avant même le code testé.
        date_frais=timezone.localdate(),
        montant=Decimal(montant), motif='Test NTP2P45',
        categorie=NoteFrais.Categorie.AUTRE)


def activer_plafond_notif(company):
    params = AchatsParametres.for_company(company)
    params.plafond_notes_frais_actif = True
    params.save(update_fields=['plafond_notes_frais_actif'])
    return params


class NotificationEscaladeDirectionTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.employe = make_user(self.company)
        self.admin = make_user(self.company, role='admin')
        PlafondNoteFrais.objects.create(
            company=self.company, categorie=NoteFrais.Categorie.AUTRE,
            montant_max=Decimal('5000'),
            escalade_direction_au_dela_de=Decimal('3000'))

    def test_notifie_immediatement_quand_le_reglage_est_actif(self):
        activer_plafond_notif(self.company)
        note = make_note(self.company, self.employe, montant=8000)

        compta_services.soumettre_note_frais(note)

        note.refresh_from_db()
        self.assertTrue(note.escalade_direction)
        notifs = Notification.objects.filter(
            recipient=self.admin, event_type=EventType.APPROVAL_REQUESTED)
        self.assertEqual(notifs.count(), 1)
        self.assertIn(note.reference, notifs.first().title)

    def test_aucune_notification_immediate_quand_le_reglage_est_off(self):
        # OFF par défaut : l'escalade reste posée + journalisée (NTP2P11
        # inchangé), sans notification immédiate — jamais une régression.
        note = make_note(self.company, self.employe, montant=8000)

        compta_services.soumettre_note_frais(note)

        note.refresh_from_db()
        self.assertTrue(note.escalade_direction)
        self.assertEqual(
            Notification.objects.filter(
                recipient=self.admin,
                event_type=EventType.APPROVAL_REQUESTED).count(), 0)

    def test_sans_escalade_aucune_notification_meme_actif(self):
        activer_plafond_notif(self.company)
        note = make_note(self.company, self.employe, montant=100)

        compta_services.soumettre_note_frais(note)

        note.refresh_from_db()
        self.assertFalse(note.escalade_direction)
        self.assertEqual(
            Notification.objects.filter(
                recipient=self.admin,
                event_type=EventType.APPROVAL_REQUESTED).count(), 0)
