"""ZMKT18 — Borne de check-in événement (scan QR / recherche par nom) +
statuts présent/absent.

Couvre : scanner/rechercher un inscrit le marque présent une seule fois
(idempotent), la clôture marque absents les non-pointés, les compteurs
présents/absents alimentent les segments (XMKT6), tests.
"""
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company

from apps.compta import services
from apps.marketing.models import EvenementMarketing, InscriptionEvenement


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class BorneCheckinEvenementTests(TestCase):
    def setUp(self):
        self.co = make_company('zmkt18', 'ZMKT18')
        self.evt = EvenementMarketing.objects.create(
            company=self.co, nom='Salon', date_debut=timezone.now())

    def test_recherche_par_nom(self):
        services.inscrire_evenement(self.evt, nom='Ahmed Benali')
        resultats = services.rechercher_inscrits_borne(self.evt, 'Ahmed')
        self.assertEqual(len(resultats), 1)

    def test_recherche_par_email(self):
        services.inscrire_evenement(self.evt, nom='X', email='cherche@x.ma')
        resultats = services.rechercher_inscrits_borne(self.evt, 'cherche')
        self.assertEqual(len(resultats), 1)

    def test_pointer_via_qr_token(self):
        inscription = services.inscrire_evenement(self.evt, nom='ScanQR')
        resultat = services.pointer_presence_via_qr_ou_recherche(
            self.evt, qr_token=inscription.qr_token)
        self.assertEqual(resultat.statut, InscriptionEvenement.Statut.PRESENT)

    def test_pointer_via_recherche_id(self):
        inscription = services.inscrire_evenement(self.evt, nom='ParId')
        resultat = services.pointer_presence_via_qr_ou_recherche(
            self.evt, inscription_id=inscription.id)
        self.assertEqual(resultat.statut, InscriptionEvenement.Statut.PRESENT)

    def test_pointer_idempotent(self):
        inscription = services.inscrire_evenement(self.evt, nom='Idempotent')
        services.pointer_presence_via_qr_ou_recherche(
            self.evt, inscription_id=inscription.id)
        inscription.refresh_from_db()
        premier_pointage = inscription.date_pointage
        services.pointer_presence_via_qr_ou_recherche(
            self.evt, inscription_id=inscription.id)
        inscription.refresh_from_db()
        self.assertEqual(inscription.date_pointage, premier_pointage)

    def test_cloture_marque_absents(self):
        present = services.inscrire_evenement(self.evt, nom='Present')
        services.pointer_presence(present)
        services.inscrire_evenement(self.evt, nom='Absent')
        nb = services.cloturer_presences_evenement(self.evt)
        self.assertEqual(nb, 1)

    def test_qr_token_inexistant_none(self):
        resultat = services.pointer_presence_via_qr_ou_recherche(
            self.evt, qr_token='invalide')
        self.assertIsNone(resultat)

    def test_isolation_multi_tenant(self):
        other = make_company('zmkt18-b', 'ZMKT18-B')
        services.inscrire_evenement(self.evt, nom='Casablanca')
        other_evt = EvenementMarketing.objects.create(
            company=other, nom='AutreSalon', date_debut=timezone.now())
        resultats = services.rechercher_inscrits_borne(other_evt, 'Casablanca')
        self.assertEqual(len(resultats), 0)
