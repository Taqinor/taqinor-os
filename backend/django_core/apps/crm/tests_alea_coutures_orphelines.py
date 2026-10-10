"""ALEA3 (D-ALEA-3, recommandation (a) appliquée par défaut — révisable par le
fondateur) — coutures orphelines du bus d'événements côté CRM.

* ``salle_vente_signal_interet`` : enfin un abonné — le responsable du lead
  est notifié (``apps.notifications`` réel), une fois par jour local et par
  salle ;
* ``deal_commission_due`` : plus jamais émis (aucun abonné n'existait) ;
* ``ao_depose``/``ao_gagne`` : plus aucun récepteur crm (module ``ao`` parqué).

Aucun mock : service de détection, récepteur, notifications et bus réels.
"""
import inspect
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company
from apps.crm import receivers as crm_receivers
from apps.crm import stages
from apps.crm.models import (
    Apporteur, DealEnregistre, Lead, SalleVente, SalleVenteVue,
)
from apps.crm.clients_pilotage import detecter_signal_interet_salle_vente
from apps.crm.clients_identite import resolve_client_for_lead
from apps.notifications.models import Notification
from apps.ventes.models import Devis, LigneDevis
from core import event_coverage, events

User = get_user_model()


class CouturesOrphelinesTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor ALEA3', slug='taqinor-alea3')
        self.owner = User.objects.create_user(
            username='alea3-resp', password='x', role_legacy='responsable',
            company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Alaoui', prenom='Sara',
            stage=stages.QUOTE_SENT, owner=self.owner)
        self.salle = SalleVente.objects.create(
            company=self.company, lead=self.lead, titre='Salle ALEA3')

    def _trois_visiteurs(self, salle=None):
        for empreinte in ('visiteur-a', 'visiteur-b', 'visiteur-c'):
            SalleVenteVue.objects.create(
                salle=salle or self.salle, ip_hash=empreinte)

    def _notifications(self):
        return Notification.objects.filter(
            recipient=self.owner, title__contains='Intérêt signalé')

    def test_interet_notifie_responsable(self):
        self._trois_visiteurs()

        note = detecter_signal_interet_salle_vente(self.salle)

        self.assertIsNotNone(note)
        notif = self._notifications().get()
        self.assertEqual(notif.company_id, self.company.pk)
        self.assertIn('Salle ALEA3', notif.title)
        self.assertEqual(notif.link, f'/crm/leads?lead={self.lead.pk}')

    def test_interet_une_fois_par_jour(self):
        self._trois_visiteurs()
        detecter_signal_interet_salle_vente(self.salle)
        # Rejeu le même jour : nouvelle vue, nouvelle détection…
        SalleVenteVue.objects.create(salle=self.salle, ip_hash='visiteur-d')
        detecter_signal_interet_salle_vente(self.salle)
        # …et même un renvoi direct du signal : toujours UNE notification.
        events.salle_vente_signal_interet.send(
            sender=SalleVente, lead=self.lead, salle=self.salle,
            company=self.company)

        self.assertEqual(self._notifications().count(), 1)

        # Une AUTRE salle du même lead, le même jour, a sa propre notification.
        autre = SalleVente.objects.create(
            company=self.company, lead=self.lead, titre='Salle ALEA3 bis')
        self._trois_visiteurs(autre)
        self.assertIsNotNone(detecter_signal_interet_salle_vente(autre))
        self.assertEqual(self._notifications().count(), 2)

    def test_plus_de_deal_commission_due(self):
        apporteur = Apporteur.objects.create(
            company=self.company, nom='Apporteur ALEA3',
            taux_commission_pct=Decimal('5.00'))
        deal = DealEnregistre.objects.create(
            company=self.company, apporteur=apporteur, lead=self.lead,
            statut=DealEnregistre.Statut.APPROUVE)
        devis = Devis.objects.create(
            company=self.company, client=resolve_client_for_lead(self.lead),
            lead=self.lead, reference='DV-ALEA3',
            statut=Devis.Statut.ACCEPTE)
        LigneDevis.objects.create(
            devis=devis, designation='Panneau', quantite=1,
            prix_unitaire=Decimal('10000.00'))
        recus = []

        def _espion(sender, **kw):
            recus.append(kw)

        events.deal_commission_due.connect(_espion, weak=False)
        self.addCleanup(events.deal_commission_due.disconnect, _espion)

        events.devis_accepted.send(
            sender='test', devis=devis, user=None, ancien_statut='envoye')

        self.assertEqual(recus, [])
        # La commission reste calculée et lisible par le comptable.
        deal.refresh_from_db()
        self.assertEqual(deal.statut, DealEnregistre.Statut.A_PAYER)
        self.assertEqual(deal.montant_commission_du, Decimal('500.00'))
        source = inspect.getsource(crm_receivers)
        self.assertNotIn('deal_commission_due.send', source)

    def test_plus_de_recepteur_ao(self):
        source = inspect.getsource(crm_receivers)
        self.assertNotIn('ao_depose', source)
        self.assertNotIn('ao_gagne', source)
        self.assertFalse(event_coverage.signal_has_receiver(events.ao_depose))
        self.assertFalse(event_coverage.signal_has_receiver(events.ao_gagne))
        # Le bus reste sans orphelin non documenté, et la réserve du seam
        # « intérêt salle de vente » est retirée (il a un abonné).
        self.assertEqual(event_coverage.orphan_signals(), set())
        self.assertNotIn('salle_vente_signal_interet',
                         event_coverage.ALLOWED_UNCONSUMED)
        self.assertTrue(event_coverage.signal_has_receiver(
            events.salle_vente_signal_interet))
        self.assertEqual(event_coverage.catalog_payload_mismatches(), {})
