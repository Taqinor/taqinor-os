"""U11 — Cohérence du funnel : « Signé sans devis actif » (DÉCISION fondateur).

Le funnel n'avance jamais en arrière, donc un lead peut rester à SIGNED alors
que son SEUL devis accepté a depuis été refusé : un « signé fantôme ». La
règle #2 (le funnel est une couche PERMANENTE, séparée des statuts DOCUMENT)
interdit de reculer l'étape à l'aveugle. Option conservatrice retenue :

  • on NE recule PAS l'étape ;
  • on EXPOSE un drapeau dérivé (lecture seule) ``lead_signe_sans_devis_actif`` ;
  • au refus, le récepteur ``crm`` consigne UNE note de chatter de signalement.

Les clés d'étape ('SIGNED', 'QUOTE_SENT'…) suivent la convention des tests
existants ; la source canonique reste STAGES.py.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company
from apps.crm.models import Client, Lead, LeadActivity
from apps.crm.services import (
    lead_signe_sans_devis_actif,
    signaler_mismatch_signe_sur_refus,
)
from apps.ventes.models import Devis
from core.events import devis_refused

import apps.crm.stages as stages

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


class TestSigneSansDevisActif(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='sanity-co', defaults={'nom': 'Sanity Co'})
        self.user = User.objects.create_user(
            username='sanity_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='Sanity',
            email='sanity@example.com', telephone='+212600000011')
        self._n = 0

    def _devis(self, lead, statut=Devis.Statut.ENVOYE):
        self._n += 1
        return Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-{self._n:04d}',
            client=self.client_obj, lead=lead, statut=statut,
            taux_tva=Decimal('20'))

    # ── Drapeau dérivé (lecture seule) ──────────────────────────────────────

    def test_uses_canonical_stage_key(self):
        """La clé SIGNED vient bien de STAGES.py (jamais codée en dur ailleurs)."""
        self.assertIn('SIGNED', stages.STAGES)

    def test_flag_true_when_signed_and_only_accepted_devis_refused(self):
        """SIGNED + son seul devis (jadis accepté) désormais refusé → drapeau."""
        lead = Lead.objects.create(
            company=self.company, nom='Fantome', stage='SIGNED')
        # Le devis qui avait fait passer le lead à Signé est maintenant refusé.
        self._devis(lead, statut=Devis.Statut.REFUSE)
        self.assertTrue(lead_signe_sans_devis_actif(lead))

    def test_flag_false_when_an_accepted_devis_remains(self):
        """SIGNED avec encore un devis accepté actif → pas de drapeau."""
        lead = Lead.objects.create(
            company=self.company, nom='Vrai Signe', stage='SIGNED')
        self._devis(lead, statut=Devis.Statut.REFUSE)
        self._devis(lead, statut=Devis.Statut.ACCEPTE)
        self.assertFalse(lead_signe_sans_devis_actif(lead))

    def test_flag_false_when_not_signed(self):
        """Hors de l'étape Signé, rien à signaler même sans devis accepté."""
        lead = Lead.objects.create(
            company=self.company, nom='En cours', stage='QUOTE_SENT')
        self._devis(lead, statut=Devis.Statut.REFUSE)
        self.assertFalse(lead_signe_sans_devis_actif(lead))

    # ── Réaction au refus : note de chatter, JAMAIS de recul d'étape ─────────

    def test_refusal_logs_chatter_note_and_keeps_stage(self):
        """Service direct : refus du seul devis accepté → note signalée, étape
        TOUJOURS à SIGNED (aucun recul automatique — règle #2)."""
        lead = Lead.objects.create(
            company=self.company, nom='Signal', stage='SIGNED')
        devis = self._devis(lead, statut=Devis.Statut.REFUSE)
        signaler_mismatch_signe_sur_refus(devis, self.user)
        lead.refresh_from_db()
        self.assertEqual(lead.stage, 'SIGNED')  # jamais reculé
        notes = LeadActivity.objects.filter(
            lead=lead, kind=LeadActivity.Kind.NOTE)
        self.assertTrue(
            any('sans devis actif' in (n.body or '') for n in notes))

    def test_refused_signal_triggers_chatter_note(self):
        """Bout en bout récepteur : émettre `devis_refused` consigne la note de
        signalement, sans cocher « marquer le lead perdu »."""
        lead = Lead.objects.create(
            company=self.company, nom='Signal Evt', stage='SIGNED')
        devis = self._devis(lead, statut=Devis.Statut.REFUSE)
        devis_refused.send(
            sender=Devis, devis=devis, user=self.user, motif_refus='Trop cher')
        lead.refresh_from_db()
        self.assertEqual(lead.stage, 'SIGNED')
        notes = LeadActivity.objects.filter(
            lead=lead, kind=LeadActivity.Kind.NOTE)
        self.assertTrue(
            any('sans devis actif' in (n.body or '') for n in notes))

    def test_refused_signal_no_note_when_other_accepted_devis(self):
        """Si un autre devis accepté reste actif, aucun signalement n'est émis."""
        lead = Lead.objects.create(
            company=self.company, nom='Toujours Signe', stage='SIGNED')
        self._devis(lead, statut=Devis.Statut.ACCEPTE)
        devis_refuse = self._devis(lead, statut=Devis.Statut.REFUSE)
        devis_refused.send(
            sender=Devis, devis=devis_refuse, user=self.user,
            motif_refus='Changement')
        lead.refresh_from_db()
        self.assertEqual(lead.stage, 'SIGNED')
        notes = LeadActivity.objects.filter(
            lead=lead, kind=LeadActivity.Kind.NOTE)
        self.assertFalse(
            any('sans devis actif' in (n.body or '') for n in notes))

    def test_refused_signal_ignored_when_no_lead(self):
        """Un devis sans lead ne provoque ni note ni erreur."""
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-9001',
            client=self.client_obj, lead=None, statut=Devis.Statut.REFUSE,
            taux_tva=Decimal('20'))
        # Ne doit pas lever.
        devis_refused.send(
            sender=Devis, devis=devis, user=self.user, motif_refus='x')
