"""CAD61 — une facture émise hors cadence : une trace, et RIEN d'autre.

[TRANCHÉ 21/09/2026] Rien ne permettait d'enregistrer un document envoyé
spontanément par le client, et une facture envoyée hors cadence ne produisait
ni événement, ni réponse, ni touche.

La décision fondateur coupe en deux :
  * « le client envoie quelque chose » se traite par le geste « pièce reçue »
    de CAD101 — il n'est PAS dupliqué ici ;
  * une facture ENVOYÉE par la société hors cadence ne déclenche AUCUNE
    relance et se contente d'une ligne au chatter (elle part après la
    signature, donc hors protocole de suivi).

Garde-fou : aucun arrêt de cadence automatique sur un message entrant (un
« merci » ne doit pas tuer une cadence) ; le geste reste humain.
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company
from core.events import facture_emise

from apps.crm import horaires, stages
from apps.crm.models import Client, Lead, LeadActivity, RelanceEtape
from apps.crm.receivers import FACTURE_EMISE_TRACE
from apps.facturation.models import Facture
from apps.parametres.models import CompanyProfile

User = get_user_model()

#: Lundi 7 septembre 2026, 10 h.
QUAND = datetime.datetime(2026, 9, 7, 10, 0, tzinfo=horaires.CASABLANCA)


class _Base(TestCase):
    slug = 'cad61'

    def setUp(self):
        self.company = Company.objects.create(slug=self.slug, nom=self.slug)
        CompanyProfile.objects.create(company=self.company)
        self.acteur = User.objects.create_user(
            username=f'{self.slug}-u', password='x',
            role_legacy='responsable', company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client',
            email=f'{self.slug}@example.com')
        self.lead = Lead.objects.create(
            company=self.company, nom='Prospect', owner=self.acteur,
            client=self.client_obj, stage=stages.SIGNED)
        self.facture = Facture.objects.create(
            company=self.company, reference='FA-CAD61-0001',
            client=self.client_obj, taux_tva=Decimal('20.00'))

    def _emettre(self):
        facture_emise.send(sender=Facture, instance=self.facture,
                           company=self.company)

    def _notes(self):
        return list(LeadActivity.objects.filter(lead=self.lead)
                    .values_list('body', flat=True))


class UneTraceEtRienDAutreTests(_Base):
    slug = 'cad61-trace'

    def test_la_facture_emise_ecrit_UNE_ligne_de_chatter(self):
        self._emettre()
        attendu = FACTURE_EMISE_TRACE.format(reference='FA-CAD61-0001')
        self.assertIn(attendu, self._notes())

    def test_elle_n_ouvre_AUCUNE_touche(self):
        """Le cœur du Done."""
        self._emettre()
        self.assertFalse(
            RelanceEtape.objects.filter(lead=self.lead).exists())

    def test_elle_ne_deplace_PAS_l_etape_du_lead(self):
        """La note est SYSTÈME : elle ne compte pas comme un contact manuel
        (sinon un simple envoi de facture ferait bouger le funnel)."""
        self._emettre()
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.stage, stages.SIGNED)
        trace = LeadActivity.objects.get(
            lead=self.lead,
            body=FACTURE_EMISE_TRACE.format(reference='FA-CAD61-0001'))
        self.assertIsNone(trace.user_id)

    def test_elle_n_arrete_AUCUNE_cadence_en_cours(self):
        """Une cadence ouverte reste ouverte : la facture ne la tue pas."""
        due = QUAND.date()
        etape = RelanceEtape.objects.create(
            company=self.company, lead=self.lead, cadence='apres_devis',
            ordre=1, due_at=QUAND, due_date=due, canal='whatsapp',
            libelle='Le PDF s\'ouvre bien ?', template_cle='j1_pdf')
        self._emettre()
        etape.refresh_from_db()
        self.assertEqual(etape.statut, RelanceEtape.Statut.A_FAIRE)

    def test_elle_est_idempotente_par_emission_pas_par_facture(self):
        """Deux émissions = deux traces : c'est un JOURNAL, pas un drapeau."""
        self._emettre()
        self._emettre()
        attendu = FACTURE_EMISE_TRACE.format(reference='FA-CAD61-0001')
        self.assertEqual(self._notes().count(attendu), 2)


class SansLeadRattacheTests(_Base):
    slug = 'cad61-orphelin'

    def test_une_facture_sans_lead_ne_leve_jamais(self):
        autre_client = Client.objects.create(
            company=self.company, nom='Sans lead',
            email='orphelin@example.com')
        facture = Facture.objects.create(
            company=self.company, reference='FA-CAD61-ORPH',
            client=autre_client, taux_tva=Decimal('20.00'))
        facture_emise.send(sender=Facture, instance=facture,
                           company=self.company)
        self.assertEqual(
            LeadActivity.objects.filter(
                body__startswith='Facture FA-CAD61-ORPH').count(), 0)

    def test_une_societe_ne_trace_pas_sur_le_lead_d_une_autre(self):
        voisine = Company.objects.create(
            slug=f'{self.slug}-voisine', nom='voisine')
        CompanyProfile.objects.create(company=voisine)
        facture_emise.send(sender=Facture, instance=self.facture,
                           company=voisine)
        self.assertEqual(self._notes(), [])
