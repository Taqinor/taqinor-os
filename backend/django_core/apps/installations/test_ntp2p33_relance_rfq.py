"""
NTP2P33 — Tâche planifiée de relance RFQ non répondues.

CRITÈRE D'ACCEPTATION : une RFQ à échéance dans 2 jours avec 1 fournisseur
non répondant génère une notification UNIQUE par jour à l'acheteur (pas de
doublon, même garde ``_deja_notifie_aujourdhui`` que
``stock.tasks.relancer_bcf_en_retard_task``).

Run :
    python manage.py test apps.installations.test_ntp2p33_relance_rfq -v2
"""
import itertools
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.installations.models import RFQ, RFQConsultation
from apps.installations.tasks import (
    casablanca_today, relancer_rfq_en_attente_task,
)
from apps.notifications.models import EventType, Notification
from apps.stock.models import Fournisseur

User = get_user_model()
_seq = itertools.count(1)


def make_company():
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=f'ntp2p33-co-{n}', defaults={'nom': f'NTP2P33 Co {n}'})
    return company


def make_user(company, role='responsable'):
    return User.objects.create_user(
        username=f'ntp2p33-{next(_seq)}', password='x',
        role_legacy=role, company=company)


class RelancerRfqEnAttenteTaskTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.acheteur = make_user(self.company)
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur NTP2P33')
        self.cible = casablanca_today() + timedelta(days=2)

    def _rfq_envoyee(self, date_limite):
        return RFQ.objects.create(
            company=self.company, reference=f'RFQ-{next(_seq)}',
            objet='Consultation NTP2P33', created_by=self.acheteur,
            statut=RFQ.Statut.ENVOYEE, date_limite_reponse=date_limite)

    def test_notifie_a_j_moins_2_pour_non_repondant(self):
        rfq = self._rfq_envoyee(self.cible)
        RFQConsultation.objects.create(
            company=self.company, rfq=rfq, fournisseur=self.fournisseur)

        result = relancer_rfq_en_attente_task()

        self.assertEqual(result[self.company.id], 1)
        notifs = Notification.objects.filter(
            recipient=self.acheteur, event_type=EventType.BCF_RELANCE_PROPOSEE)
        self.assertEqual(notifs.count(), 1)

    def test_pas_de_doublon_le_meme_jour(self):
        rfq = self._rfq_envoyee(self.cible)
        RFQConsultation.objects.create(
            company=self.company, rfq=rfq, fournisseur=self.fournisseur)

        relancer_rfq_en_attente_task()
        relancer_rfq_en_attente_task()

        notifs = Notification.objects.filter(
            recipient=self.acheteur, event_type=EventType.BCF_RELANCE_PROPOSEE)
        self.assertEqual(notifs.count(), 1)

    def test_fournisseur_ayant_repondu_exclu(self):
        from apps.installations.models import RFQOffre

        rfq = self._rfq_envoyee(self.cible)
        offre = RFQOffre.objects.create(
            company=self.company, rfq=rfq, fournisseur=self.fournisseur,
            montant_ht=1000)
        RFQConsultation.objects.create(
            company=self.company, rfq=rfq, fournisseur=self.fournisseur,
            offre=offre)

        result = relancer_rfq_en_attente_task()
        self.assertEqual(result[self.company.id], 0)

    def test_echeance_hors_j_moins_2_ignoree(self):
        rfq = self._rfq_envoyee(casablanca_today() + timedelta(days=10))
        RFQConsultation.objects.create(
            company=self.company, rfq=rfq, fournisseur=self.fournisseur)

        result = relancer_rfq_en_attente_task()
        self.assertEqual(result[self.company.id], 0)

    def test_rfq_brouillon_ignoree(self):
        rfq = RFQ.objects.create(
            company=self.company, reference=f'RFQ-{next(_seq)}',
            objet='Brouillon', created_by=self.acheteur,
            statut=RFQ.Statut.BROUILLON, date_limite_reponse=self.cible)
        RFQConsultation.objects.create(
            company=self.company, rfq=rfq, fournisseur=self.fournisseur)

        result = relancer_rfq_en_attente_task()
        self.assertEqual(result[self.company.id], 0)

    def test_consultation_revoquee_ignoree(self):
        rfq = self._rfq_envoyee(self.cible)
        RFQConsultation.objects.create(
            company=self.company, rfq=rfq, fournisseur=self.fournisseur,
            revoque=True)

        result = relancer_rfq_en_attente_task()
        self.assertEqual(result[self.company.id], 0)

    def test_societe_suspendue_jamais_balayee(self):
        from authentication.models import Company
        suspendue = Company.objects.create(
            nom='NTP2P33 Suspendue', slug='ntp2p33-suspendue', actif=False)
        acheteur2 = make_user(suspendue)
        fournisseur2 = Fournisseur.objects.create(
            company=suspendue, nom='Fournisseur suspendu')
        rfq = RFQ.objects.create(
            company=suspendue, reference=f'RFQ-{next(_seq)}',
            objet='Société suspendue', created_by=acheteur2,
            statut=RFQ.Statut.ENVOYEE, date_limite_reponse=self.cible)
        RFQConsultation.objects.create(
            company=suspendue, rfq=rfq, fournisseur=fournisseur2)

        result = relancer_rfq_en_attente_task()
        self.assertNotIn(suspendue.id, result)


class CasablancaTodayHelperTests(TestCase):
    def test_renvoie_une_date(self):
        # Garantit que le helper partagé du module reste importable et
        # renvoie bien une date (pas un datetime) pour l'arithmétique J-2.
        self.assertEqual(type(casablanca_today()), type(timezone.localdate()))
