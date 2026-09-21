"""Tests ARC35 — Abonnés du bus pour ``contrat_signe``/``contrat_actif``.

Ces deux événements (CONTRAT16/17, YDOCF5) étaient posés en seam SANS aucun
abonné (``core.event_coverage.ALLOWED_UNCONSUMED``) : une signature de
contrat ne déclenchait rien nulle part. ARC35 consomme le seam :

* chatter ARC8 (``records.services.log_note`` — DISTINCT du journal legacy
  ``ContratActivity``) sur ``contrat_signe`` ET ``contrat_actif`` ;
* dépôt GED du contrat signé (via ``deposer_contrat_signe_en_ged``,
  idempotent) sur ``contrat_signe`` ;
* notification (``EventType.CONTRAT_SIGNE``) au signataire, repli managers,
  sur ``contrat_signe``.

Couvre aussi le non-régression : ``contrat_signe``/``contrat_actif`` ne sont
plus dans ``ALLOWED_UNCONSUMED`` (le test YEVNT7 existant le verrouille déjà,
mais on l'affirme ici explicitement pour cette lane).
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company

from apps.contrats import services
from apps.contrats.models import Contrat, PartieContrat
from apps.ged.models import Document
from apps.notifications.models import EventType, Notification
from apps.records.models import Activity
from core import event_coverage

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={"nom": nom})
    return company


def make_user(company, username, role="admin"):
    return User.objects.create_user(
        username=username, password="x", company=company, role_legacy=role)


def make_contrat(company, reference="CT-ARC35"):
    contrat = Contrat.objects.create(
        company=company, objet="Contrat test ARC35", reference=reference,
        montant=Decimal("50000"), type_contrat="vente", statut="en_approbation",
        date_debut=timezone.localdate() + timedelta(days=30))
    PartieContrat.objects.create(
        company=company, contrat=contrat,
        type_partie="client", nom="Client SARL", ordre=0)
    PartieContrat.objects.create(
        company=company, contrat=contrat,
        type_partie="prestataire", nom="Taqinor", ordre=1)
    return contrat


class Arc35SignatureEvenementsTests(TestCase):
    def setUp(self):
        self.co = make_company("arc35", "ARC35")
        self.user = make_user(self.co, "arc35-admin", role="admin")
        self.contrat = make_contrat(self.co)

    def _signer_completement(self):
        services.signer_contrat(
            self.contrat, signataire_nom="Client", role_signataire="client",
            auteur=self.user)
        return services.signer_contrat(
            self.contrat, signataire_nom="Taqinor",
            role_signataire="prestataire", auteur=self.user)

    def test_signature_complete_pose_une_note_chatter_arc8(self):
        self._signer_completement()
        ct = __import__(
            'django.contrib.contenttypes.models', fromlist=['ContentType'],
        ).ContentType.objects.get_for_model(Contrat)
        notes = Activity.objects.filter(
            company=self.co, content_type=ct, object_id=self.contrat.pk,
            kind=Activity.Kind.NOTE)
        self.assertTrue(notes.filter(body__icontains='signé').exists())

    def test_signature_complete_depose_le_contrat_en_ged(self):
        self._signer_completement()
        docs = Document.objects.filter(company=self.co)
        self.assertEqual(docs.count(), 1)

    def test_signature_complete_notifie_le_signataire(self):
        self._signer_completement()
        notifs = Notification.objects.filter(
            company=self.co, recipient=self.user,
            event_type=EventType.CONTRAT_SIGNE)
        self.assertTrue(notifs.exists())
        self.assertIn(self.contrat.reference, notifs.first().body)

    def test_activation_automatique_pose_une_note_chatter_distincte(self):
        # Prise d'effet DÉJÀ atteinte (date_debut dans le passé) → active
        # automatiquement à la signature (CONTRAT17).
        self.contrat.date_debut = timezone.localdate() - timedelta(days=1)
        self.contrat.save(update_fields=['date_debut'])
        res = self._signer_completement()
        self.assertTrue(res['contrat_actif'])
        ct = __import__(
            'django.contrib.contenttypes.models', fromlist=['ContentType'],
        ).ContentType.objects.get_for_model(Contrat)
        notes = Activity.objects.filter(
            company=self.co, content_type=ct, object_id=self.contrat.pk,
            kind=Activity.Kind.NOTE)
        self.assertTrue(notes.filter(body__icontains='activé').exists())
        # Deux notes distinctes : signature + activation.
        self.assertEqual(notes.count(), 2)
        # Un seul document GED déposé (pas de second dépôt sur l'activation).
        self.assertEqual(Document.objects.filter(company=self.co).count(), 1)

    def test_signature_partielle_ne_declenche_aucun_effet(self):
        services.signer_contrat(
            self.contrat, signataire_nom="Client", role_signataire="client",
            auteur=self.user)
        self.assertEqual(Document.objects.filter(company=self.co).count(), 0)
        self.assertEqual(
            Notification.objects.filter(
                company=self.co, event_type=EventType.CONTRAT_SIGNE).count(),
            0)

    def test_contrat_signe_et_contrat_actif_ne_sont_plus_orphelins(self):
        """Non-régression explicite (au-delà du test YEVNT7 générique) :
        les deux signaux ne sont plus catalogués ``ALLOWED_UNCONSUMED``."""
        self.assertNotIn('contrat_signe', event_coverage.ALLOWED_UNCONSUMED)
        self.assertNotIn('contrat_actif', event_coverage.ALLOWED_UNCONSUMED)
        orphelins = event_coverage.orphan_signals()
        self.assertNotIn('contrat_signe', orphelins)
        self.assertNotIn('contrat_actif', orphelins)
