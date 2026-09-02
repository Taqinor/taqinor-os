"""CRX23 — réservation publique : anti-double-réservation + bornes du créneau.

Deux défauts de ``services.reserver_creneau_public`` relevés par l'audit L3 :

1. **Double réservation.** ``resolve_booking_link`` lit ``used_at`` en mémoire,
   puis le lien n'était marqué qu'APRÈS la création du rendez-vous. Deux
   requêtes simultanées passaient donc toutes les deux la vérification,
   créaient DEUX ``Appointment`` sur le même lien, et la seconde écrasait
   ``link.appointment`` : le commercial voyait deux visites pour un créneau.
   Le lien est maintenant RÉCLAMÉ par un UPDATE conditionnel
   (``used_at__isnull=True``) dans ``transaction.atomic`` — c'est le nombre de
   lignes touchées qui arbitre, jamais la copie en mémoire.

2. **Créneau non borné.** Le corps public passe par ``parse_datetime``, qui
   rend un datetime NAÏF dès que la chaîne n'a pas d'offset et accepte
   n'importe quelle année : une visite « en 9999 » ou déjà passée entrait
   telle quelle dans le calendrier du commercial.
"""
import datetime
import json
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from apps.crm.models import Appointment, BookingLink, Lead
from apps.crm.services import (
    BOOKING_HORIZON_JOURS, BookingLinkUnavailable, reserver_creneau_public,
)
from authentication.models import Company


class BornesDuCreneauTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor CRX23 bornes', slug='taqinor-crx23-bornes')
        self.lead = Lead.objects.create(
            company=self.company, nom='Prospect bornes')
        self.link = BookingLink.objects.create(
            company=self.company, lead=self.lead)

    def _reserver(self, creneau):
        return reserver_creneau_public(self.link.token, scheduled_at=creneau)

    def assertLienIntact(self):
        """Un refus de créneau ne consomme JAMAIS le lien."""
        self.link.refresh_from_db()
        self.assertIsNone(self.link.used_at)
        self.assertEqual(Appointment.objects.count(), 0)

    def test_creneau_naif_refuse(self):
        naif = datetime.datetime(2099, 5, 1, 10, 0)  # sans fuseau
        self.assertTrue(timezone.is_naive(naif))
        with self.assertRaises(ValueError) as ctx:
            self._reserver(naif)
        self.assertIn('fuseau', str(ctx.exception))
        self.assertLienIntact()

    def test_creneau_passe_refuse(self):
        with self.assertRaises(ValueError) as ctx:
            self._reserver(timezone.now() - datetime.timedelta(hours=1))
        self.assertIn('passé', str(ctx.exception))
        self.assertLienIntact()

    def test_creneau_annee_9999_refuse(self):
        lointain = timezone.now().replace(year=9999)
        with self.assertRaises(ValueError) as ctx:
            self._reserver(lointain)
        self.assertIn('lointain', str(ctx.exception))
        self.assertLienIntact()

    def test_creneau_juste_au_dela_de_l_horizon_refuse(self):
        au_dela = timezone.now() + datetime.timedelta(
            days=BOOKING_HORIZON_JOURS, hours=1)
        with self.assertRaises(ValueError):
            self._reserver(au_dela)
        self.assertLienIntact()

    def test_creneau_dans_l_horizon_accepte(self):
        dedans = timezone.now() + datetime.timedelta(
            days=BOOKING_HORIZON_JOURS - 1)
        appt = self._reserver(dedans)
        self.assertEqual(appt.lead_id, self.lead.pk)
        self.link.refresh_from_db()
        self.assertIsNotNone(self.link.used_at)

    def test_jeton_inconnu_prime_sur_les_bornes(self):
        """Le jeton est vérifié D'ABORD : un jeton inconnu ne révèle jamais
        quelle borne de créneau il aurait franchie."""
        with self.assertRaises(BookingLinkUnavailable):
            reserver_creneau_public(
                'jeton-inconnu-crx23',
                scheduled_at=timezone.now() - datetime.timedelta(days=400))


class AntiDoubleReservationTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor CRX23 course', slug='taqinor-crx23-course')
        self.lead = Lead.objects.create(
            company=self.company, nom='Prospect course')
        self.link = BookingLink.objects.create(
            company=self.company, lead=self.lead)
        self.creneau = timezone.now() + datetime.timedelta(days=3)

    def test_lien_reclame_par_une_requete_concurrente_perd(self):
        """Reproduit la course : la vue tient un ``BookingLink`` dont la copie
        EN MÉMOIRE est encore libre alors que la ligne en base a déjà été
        réclamée par la requête gagnante. L'UPDATE conditionnel doit arbitrer,
        pas la copie périmée."""
        perime = BookingLink.objects.get(pk=self.link.pk)
        self.assertIsNone(perime.used_at)
        # La requête GAGNANTE réclame le lien pendant ce temps.
        BookingLink.objects.filter(pk=self.link.pk).update(
            used_at=timezone.now())

        with patch('apps.crm.services.resolve_booking_link',
                   return_value=perime):
            with self.assertRaises(BookingLinkUnavailable):
                reserver_creneau_public(
                    self.link.token, scheduled_at=self.creneau)

        self.assertEqual(Appointment.objects.count(), 0)

    def test_echec_de_creation_libere_le_lien(self):
        """La réclamation et la création sont dans la MÊME transaction : si le
        rendez-vous échoue, le lien n'est pas brûlé pour rien."""
        with patch('apps.crm.services.book_appointment',
                   side_effect=RuntimeError('base indisponible')):
            with self.assertRaises(RuntimeError):
                reserver_creneau_public(
                    self.link.token, scheduled_at=self.creneau)

        self.link.refresh_from_db()
        self.assertIsNone(self.link.used_at)
        self.assertEqual(Appointment.objects.count(), 0)

    def test_reservation_normale_marque_le_lien_et_le_rdv(self):
        appt = reserver_creneau_public(
            self.link.token, scheduled_at=self.creneau)
        self.link.refresh_from_db()
        self.assertIsNotNone(self.link.used_at)
        self.assertEqual(self.link.appointment_id, appt.pk)
        self.assertEqual(Appointment.objects.count(), 1)


class EndpointBornesTests(TestCase):
    """La vue publique traduit les bornes en 400 (jamais un 500, jamais un
    faux succès)."""

    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor CRX23 http', slug='taqinor-crx23-http')
        self.lead = Lead.objects.create(company=self.company, nom='Prospect http')
        self.link = BookingLink.objects.create(
            company=self.company, lead=self.lead)

    def _post(self, valeur):
        return self.client.post(
            f'/api/django/crm/public/booking/{self.link.token}/reserve/',
            data=json.dumps({'scheduled_at': valeur}),
            content_type='application/json')

    def test_creneau_naif_400(self):
        res = self._post('2099-05-01T10:00:00')  # aucun offset ⇒ naïf
        self.assertEqual(res.status_code, 400, res.content)
        self.link.refresh_from_db()
        self.assertIsNone(self.link.used_at)

    def test_creneau_passe_400(self):
        passe = (timezone.now() - datetime.timedelta(days=2)).isoformat()
        res = self._post(passe)
        self.assertEqual(res.status_code, 400, res.content)
        self.link.refresh_from_db()
        self.assertIsNone(self.link.used_at)

    def test_creneau_valide_201(self):
        futur = (timezone.now() + datetime.timedelta(days=2)).isoformat()
        res = self._post(futur)
        self.assertEqual(res.status_code, 201, res.content)
