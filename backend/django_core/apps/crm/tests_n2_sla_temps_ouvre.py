"""N2 — les SLA du suivi commercial comptent en TEMPS OUVRÉ.

Décision fondateur du 25/09/2026 : « les notifications doivent être parmi
les étapes du suivi commercial et ne doivent pas être à minuit ni 23 h ».

Un délai de SLA (cinq minutes de premier contact, rappel promis) ne court que
pendant l'ouverture de la société : un lead arrivé à 23 h a son échéance à
l'ouverture du lendemain PLUS le délai, pas à 23 h 05 ; un rappel promis un
vendredi à 18 h n'est pas « en retard » pendant le week-end. Et une même
rupture ne renotifie pas à chaque passage du balayage.

`horaires.echeance_en_temps_ouvre` est l'inverse exact de
`minutes_ouvrees_entre` : même fenêtre, même découpage, aucune seconde table
d'horaires.
"""
import datetime
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company

from apps.crm import horaires
from apps.crm.management.commands.escalader_premier_contact import (
    escalader_premier_contact)
from apps.crm.management.commands.escalader_rappels_demandes import (
    escalader_rappels_demandes)
from apps.crm.models import Lead
from apps.crm.stages import NEW
from apps.notifications.models import EventType, Notification
from apps.parametres.models import CompanyProfile

User = get_user_model()

CASA = ZoneInfo('Africa/Casablanca')


def _t(annee, mois, jour, heure, minute=0):
    return datetime.datetime(annee, mois, jour, heure, minute, tzinfo=CASA)


#: Mardi 29 → mercredi 30 septembre 2026 (jours ouvrés ordinaires), vendredi
#: 2 octobre → lundi 5 octobre 2026.
MARDI_23H = _t(2026, 9, 29, 23, 0)
MERCREDI_10H = _t(2026, 9, 30, 10, 0)
VENDREDI_18H = _t(2026, 10, 2, 18, 0)


class _Base(TestCase):
    slug = 'n2-sla'

    def setUp(self):
        self.company = Company.objects.create(
            nom='N2 Solaire', slug=self.slug)
        self.profil, _ = CompanyProfile.objects.get_or_create(
            company=self.company)
        self.meryem = User.objects.create_user(
            username=f'{self.slug}-meryem', password='x',
            role_legacy='responsable', company=self.company)

    def _lead(self, cree_le, **kw):
        champs = {'company': self.company, 'nom': 'Prospect N2',
                  'owner': self.meryem, 'source': Lead.Source.OS_NATIVE,
                  'stage': NEW}
        champs.update(kw)
        lead = Lead.objects.create(**champs)
        Lead.objects.filter(pk=lead.pk).update(date_creation=cree_le)
        lead.refresh_from_db()
        return lead


class EcheanceEnTempsOuvreTests(_Base):
    slug = 'n2-echeance'

    def test_en_journee_le_delai_court_normalement(self):
        self.assertEqual(
            horaires.echeance_en_temps_ouvre(
                MERCREDI_10H, datetime.timedelta(minutes=5), self.company,
                canal='whatsapp'),
            _t(2026, 9, 30, 10, 5))

    def test_arrive_a_23h_echeance_a_louverture_plus_le_delai(self):
        self.assertEqual(
            horaires.echeance_en_temps_ouvre(
                MARDI_23H, datetime.timedelta(minutes=5), self.company,
                canal='whatsapp'),
            _t(2026, 9, 30, 8, 35))
        # Sur la fenêtre d'APPEL, l'ouverture est 09:00.
        self.assertEqual(
            horaires.echeance_en_temps_ouvre(
                MARDI_23H, datetime.timedelta(minutes=5), self.company,
                canal='appel'),
            _t(2026, 9, 30, 9, 5))

    def test_le_week_end_ne_compte_pas(self):
        """Vendredi 18:00 + 12 h d'appel : 2 h le vendredi (fermeture 20:00),
        rien samedi ni dimanche, 10 h le lundi → lundi 19:00."""
        self.assertEqual(
            horaires.echeance_en_temps_ouvre(
                VENDREDI_18H, datetime.timedelta(hours=12), self.company,
                canal='appel'),
            _t(2026, 10, 5, 19, 0))

    def test_la_pause_du_vendredi_est_retranchee_pour_les_appels(self):
        """Vendredi 11:00 + 1 h : 30 min avant la pause (11:30-15:00), puis
        30 min après → 15:30."""
        self.assertEqual(
            horaires.echeance_en_temps_ouvre(
                _t(2026, 10, 2, 11, 0), datetime.timedelta(hours=1),
                self.company, canal='appel'),
            _t(2026, 10, 2, 15, 30))

    def test_inverse_exact_de_minutes_ouvrees_entre(self):
        for depart, minutes, canal in (
                (MARDI_23H, 5, 'whatsapp'), (VENDREDI_18H, 720, 'appel'),
                (_t(2026, 10, 2, 11, 0), 60, 'appel')):
            with self.subTest(depart=depart, canal=canal):
                echeance = horaires.echeance_en_temps_ouvre(
                    depart, datetime.timedelta(minutes=minutes),
                    self.company, canal=canal)
                self.assertEqual(
                    horaires.minutes_ouvrees_entre(
                        depart, echeance, self.company, canal=canal),
                    minutes)


class PremierContactTests(_Base):
    slug = 'n2-premier-contact'

    def _escalades(self):
        return Notification.objects.filter(
            recipient=self.meryem,
            event_type=EventType.PREMIER_CONTACT_DEPASSE)

    def test_lead_de_23h_aucune_escalade_avant_louverture_plus_5_min(self):
        self._lead(MARDI_23H)
        for moment in (_t(2026, 9, 29, 23, 30), _t(2026, 9, 30, 3, 0),
                       _t(2026, 9, 30, 8, 30), _t(2026, 9, 30, 8, 34)):
            with self.subTest(controle=moment):
                self.assertEqual(escalader_premier_contact(now=moment), 0)
        self.assertEqual(
            escalader_premier_contact(now=_t(2026, 9, 30, 8, 35)), 1)
        self.assertEqual(self._escalades().count(), 1)

    def test_lead_de_10h_non_contacte_escalade_a_10h05(self):
        self._lead(MERCREDI_10H)
        self.assertEqual(
            escalader_premier_contact(now=_t(2026, 9, 30, 10, 4)), 0)
        self.assertEqual(
            escalader_premier_contact(now=_t(2026, 9, 30, 10, 5)), 1)

    def test_deux_passes_une_seule_notification(self):
        self._lead(MERCREDI_10H)
        escalader_premier_contact(now=_t(2026, 9, 30, 10, 5))
        self.assertEqual(
            escalader_premier_contact(now=_t(2026, 9, 30, 10, 10)), 0)
        self.assertEqual(self._escalades().count(), 1)


class RappelPromisTests(_Base):
    slug = 'n2-rappel'

    def setUp(self):
        super().setUp()
        # SLA générique 24 h → SLA rappel 12 h (services.callback_sla_hours).
        self.profil.lead_sla_hours = 24
        self.profil.save(update_fields=['lead_sla_hours'])
        self.lead = self._lead(
            VENDREDI_18H,
            contact_preference=Lead.ContactPreference.PHONE_OK,
            telephone='+212600445566')
        Lead.objects.filter(pk=self.lead.pk).update(
            contact_preference_set_at=VENDREDI_18H)

    def _ruptures(self):
        return Notification.objects.filter(
            recipient=self.meryem,
            event_type=EventType.LEAD_CALLBACK_SLA_BREACH)

    def test_rappel_promis_vendredi_18h_pas_de_rupture_le_week_end(self):
        for moment in (_t(2026, 10, 3, 10, 0), _t(2026, 10, 4, 12, 0),
                       _t(2026, 10, 5, 8, 0), _t(2026, 10, 5, 18, 59)):
            with self.subTest(controle=moment):
                self.assertEqual(escalader_rappels_demandes(now=moment), 0)
        self.assertEqual(self._ruptures().count(), 0)

    def test_la_rupture_tombe_a_lecheance_ouvree(self):
        self.assertEqual(
            escalader_rappels_demandes(now=_t(2026, 10, 5, 19, 0)), 1)
        self.assertEqual(self._ruptures().count(), 1)

    def test_deux_passes_une_seule_notification(self):
        escalader_rappels_demandes(now=_t(2026, 10, 5, 19, 0))
        self.assertEqual(
            escalader_rappels_demandes(now=_t(2026, 10, 5, 19, 30)), 0)
        self.assertEqual(self._ruptures().count(), 1)
