"""ZMKT17 — Communications programmées d'événement (rappels avant /
relance après).

Couvre : définir des communications à -2j/-2h/+1j, le beat les envoie à
l'heure aux bons inscrits, no-op sans clé, désinscrits exclus, migration
additive, tests (échéances, filtrage statut).
"""
import datetime

from django.test import TestCase
from django.utils import timezone

from authentication.models import Company

from apps.compta import services
from apps.compta.models import (
    CommunicationEvenement, EvenementMarketing, SuppressionMarketing,
)


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class CommunicationsEvenementTests(TestCase):
    def setUp(self):
        self.co = make_company('zmkt17', 'ZMKT17')

    def test_echeance_calculee_correctement(self):
        evt = EvenementMarketing.objects.create(
            company=self.co, nom='E',
            date_debut=timezone.datetime(
                2026, 8, 1, 10, 0, tzinfo=timezone.get_current_timezone()))
        comm = CommunicationEvenement.objects.create(
            company=self.co, evenement=evt, intervalle=-2,
            unite_intervalle=CommunicationEvenement.UniteIntervalle.JOURS)
        self.assertEqual(
            comm.echeance(),
            timezone.datetime(
                2026, 7, 30, 10, 0, tzinfo=timezone.get_current_timezone()))

    def test_beat_envoie_a_echeance(self):
        evt = EvenementMarketing.objects.create(
            company=self.co, nom='E2',
            date_debut=timezone.now() + datetime.timedelta(hours=1))
        CommunicationEvenement.objects.create(
            company=self.co, evenement=evt, intervalle=-2,
            unite_intervalle=CommunicationEvenement.UniteIntervalle.HEURES)
        services.inscrire_evenement(evt, nom='Inscrit', email='a@x.ma')
        envoyees = services.envoyer_communications_evenement_dues(self.co)
        self.assertEqual(len(envoyees), 1)
        self.assertEqual(envoyees[0]['nb_destinataires'], 1)

    def test_pas_encore_echue_no_op(self):
        evt = EvenementMarketing.objects.create(
            company=self.co, nom='E3',
            date_debut=timezone.now() + datetime.timedelta(days=10))
        CommunicationEvenement.objects.create(
            company=self.co, evenement=evt, intervalle=-2,
            unite_intervalle=CommunicationEvenement.UniteIntervalle.JOURS)
        envoyees = services.envoyer_communications_evenement_dues(self.co)
        self.assertEqual(len(envoyees), 0)

    def test_no_op_sans_cle_brevo(self):
        evt = EvenementMarketing.objects.create(
            company=self.co, nom='E4',
            date_debut=timezone.now() + datetime.timedelta(hours=1))
        CommunicationEvenement.objects.create(
            company=self.co, evenement=evt, intervalle=-2,
            unite_intervalle=CommunicationEvenement.UniteIntervalle.HEURES)
        envoyees = services.envoyer_communications_evenement_dues(self.co)
        self.assertFalse(envoyees[0]['envoye_reel'])

    def test_desinscrits_exclus(self):
        evt = EvenementMarketing.objects.create(
            company=self.co, nom='E5',
            date_debut=timezone.now() + datetime.timedelta(hours=1))
        CommunicationEvenement.objects.create(
            company=self.co, evenement=evt, intervalle=-2,
            unite_intervalle=CommunicationEvenement.UniteIntervalle.HEURES)
        services.inscrire_evenement(evt, nom='OK', email='ok@x.ma')
        services.inscrire_evenement(evt, nom='Supprimé', email='supprime@x.ma')
        SuppressionMarketing.objects.create(
            company=self.co, destinataire='supprime@x.ma')
        envoyees = services.envoyer_communications_evenement_dues(self.co)
        self.assertEqual(envoyees[0]['nb_destinataires'], 1)

    def test_ne_renvoie_pas_deux_fois(self):
        evt = EvenementMarketing.objects.create(
            company=self.co, nom='E6',
            date_debut=timezone.now() + datetime.timedelta(hours=1))
        CommunicationEvenement.objects.create(
            company=self.co, evenement=evt, intervalle=-2,
            unite_intervalle=CommunicationEvenement.UniteIntervalle.HEURES)
        services.envoyer_communications_evenement_dues(self.co)
        envoyees2 = services.envoyer_communications_evenement_dues(self.co)
        self.assertEqual(len(envoyees2), 0)
