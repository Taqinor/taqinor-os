"""NTGRC21 — relance des attestations de politique manquantes.

Garanties : seuls les employés SANS attestation à jour sont relancés, une
seule fois par jour (idempotent), jamais ceux qui ont attesté, jamais une
autre société. Horloge FIGÉE partout où la date entre dans une assertion.
"""
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from apps.grc.management.commands.relancer_attestations import (
    relancer_societe,
)
from apps.grc.models import PolitiqueInterne
from apps.grc.selectors import attestations_manquantes
from apps.grc.services import attester_politique, publier_politique
from apps.notifications.models import EventType, Notification
from apps.rh.models import DossierEmploye
from authentication.models import Company
from testkit.time import frozen

INSTANT = '2026-09-12 09:00:00+00:00'
LENDEMAIN = '2026-09-13 09:00:00+00:00'


class RelanceAttestationsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='NTGRC21 SA', slug='ntgrc21')
        User = get_user_model()
        cls.u1 = User.objects.create_user(
            username='ntgrc21-a', password='x', company=cls.company)
        cls.u2 = User.objects.create_user(
            username='ntgrc21-b', password='x', company=cls.company)
        cls.d1 = DossierEmploye.objects.create(
            company=cls.company, matricule='E1', nom='A', prenom='A',
            user=cls.u1)
        cls.d2 = DossierEmploye.objects.create(
            company=cls.company, matricule='E2', nom='B', prenom='B',
            user=cls.u2)

    def _publiee(self, titre='Charte'):
        politique = PolitiqueInterne.objects.create(
            company=self.company, titre=titre, contenu='Texte')
        publier_politique(politique)
        politique.refresh_from_db()
        return politique

    def test_selector_liste_les_manquants(self):
        politique = self._publiee()
        attester_politique(self.company, politique,
                           employe_ref=str(self.d1.pk), nom_saisi='A')
        dus = attestations_manquantes(self.company)
        self.assertEqual(len(dus), 1)
        self.assertEqual(dus[0]['version'], 1)
        self.assertEqual(dus[0]['manquants'], [self.d2.pk])

    def test_une_politique_brouillon_ne_declenche_rien(self):
        PolitiqueInterne.objects.create(
            company=self.company, titre='Brouillon', contenu='Texte')
        self.assertEqual(attestations_manquantes(self.company), [])

    def test_relance_uniquement_les_employes_sans_attestation(self):
        politique = self._publiee()
        attester_politique(self.company, politique,
                           employe_ref=str(self.d1.pk), nom_saisi='A')
        with frozen(INSTANT):
            envoyees, _ = relancer_societe(self.company)
        self.assertEqual(envoyees, 1)
        destinataires = set(Notification.objects.filter(
            event_type=EventType.ANNONCE_READ_REMINDER
        ).values_list('recipient_id', flat=True))
        self.assertEqual(destinataires, {self.u2.pk})

    def test_relancer_deux_fois_le_meme_jour_ne_double_pas(self):
        self._publiee()
        with frozen(INSTANT):
            premier, _ = relancer_societe(self.company)
            second, ignorees = relancer_societe(self.company)
        self.assertEqual(premier, 2)
        self.assertEqual(second, 0)
        self.assertEqual(ignorees, 2)
        self.assertEqual(Notification.objects.filter(
            event_type=EventType.ANNONCE_READ_REMINDER).count(), 2)

    def test_le_lendemain_relance_de_nouveau(self):
        self._publiee()
        with frozen(INSTANT):
            relancer_societe(self.company)
        with frozen(LENDEMAIN):
            demain, _ = relancer_societe(self.company)
        self.assertEqual(demain, 2)

    def test_rien_a_relancer_quand_tout_le_monde_a_atteste(self):
        politique = self._publiee()
        for dossier in (self.d1, self.d2):
            attester_politique(self.company, politique,
                               employe_ref=str(dossier.pk), nom_saisi='X')
        with frozen(INSTANT):
            envoyees, _ = relancer_societe(self.company)
        self.assertEqual(envoyees, 0)
        self.assertEqual(Notification.objects.count(), 0)

    def test_une_autre_societe_n_est_jamais_relancee(self):
        autre = Company.objects.create(nom='Autre', slug='ntgrc21-autre')
        politique = PolitiqueInterne.objects.create(
            company=autre, titre='Etrangere', contenu='T')
        publier_politique(politique)
        with frozen(INSTANT):
            envoyees, _ = relancer_societe(self.company)
        self.assertEqual(envoyees, 0)

    def test_commande_en_simulation_n_envoie_rien(self):
        self._publiee()
        sortie = StringIO()
        with frozen(INSTANT):
            call_command('relancer_attestations', '--dry-run',
                         '--company', str(self.company.pk), stdout=sortie)
        self.assertIn('simulation', sortie.getvalue())
        self.assertEqual(Notification.objects.count(), 0)

    def test_commande_envoie_reellement(self):
        self._publiee()
        sortie = StringIO()
        with frozen(INSTANT):
            call_command('relancer_attestations',
                         '--company', str(self.company.pk), stdout=sortie)
        self.assertEqual(Notification.objects.filter(
            event_type=EventType.ANNONCE_READ_REMINDER).count(), 2)
