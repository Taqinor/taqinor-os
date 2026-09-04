"""NTCRM27 — Signal d'intérêt automatique depuis la salle de vente.

3 consultations DISTINCTES en moins de 48h génèrent la note automatiquement ;
une 4e ne duplique pas la note du jour. Jamais un changement de stage
automatique.

CRX31 (02/09/2026) — « distinctes » n'était pas vérifié : le comptage portait
sur les vues BRUTES, si bien que trois rechargements de la page par le MÊME
visiteur déclenchaient « signal d'intérêt fort » et faisaient rappeler un
client qui n'avait fait qu'appuyer sur F5. Le comptage est désormais
dédupliqué par (empreinte de visiteur, jour local) — ce fichier porte les deux
moitiés du contrat : trois visiteurs distincts déclenchent, trois
rechargements d'un seul ne déclenchent pas.
"""
from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company
from apps.crm import stages
from apps.crm.models import Lead, LeadActivity, SalleVente, SalleVenteVue
from apps.crm.services import detecter_signal_interet_salle_vente


class SignalInteretServiceTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Taqinor NTCRM27', slug='taqinor-ntcrm27')
        self.lead = Lead.objects.create(
            company=self.company, nom='Lead QS27', stage=stages.QUOTE_SENT)
        self.salle = SalleVente.objects.create(
            company=self.company, lead=self.lead, titre='Salle NTCRM27')

    def _vues(self, empreintes, salle=None):
        """Une vue par empreinte de visiteur (``ip_hash``)."""
        for empreinte in empreintes:
            SalleVenteVue.objects.create(
                salle=salle or self.salle, ip_hash=empreinte)

    def test_3_visiteurs_distincts_en_48h_generent_la_note(self):
        self._vues(['visiteur-a', 'visiteur-b', 'visiteur-c'])
        note = detecter_signal_interet_salle_vente(self.salle)
        self.assertIsNotNone(note)
        self.assertEqual(note.kind, LeadActivity.Kind.NOTE)
        self.assertIn("signal d'intérêt fort", note.body)
        self.assertEqual(
            LeadActivity.objects.filter(lead=self.lead, kind=LeadActivity.Kind.NOTE).count(), 1)
        # Le stage du lead n'est JAMAIS modifié automatiquement.
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.stage, stages.QUOTE_SENT)

    def test_3_rechargements_du_meme_appareil_ne_declenchent_rien(self):
        """CRX31 — le cas qui faisait rappeler un client pour trois F5."""
        self._vues(['visiteur-a', 'visiteur-a', 'visiteur-a'])
        note = detecter_signal_interet_salle_vente(self.salle)
        self.assertIsNone(note)
        self.assertFalse(LeadActivity.objects.filter(lead=self.lead).exists())

    def test_vues_sans_empreinte_comptent_pour_une(self):
        """Empreinte vide (IP illisible) : indistinguables, donc UNE seule
        consultation — sous-compter, jamais sur-compter."""
        self._vues(['', '', ''])
        self.assertIsNone(detecter_signal_interet_salle_vente(self.salle))

    def test_4e_vue_meme_jour_ne_duplique_pas_la_note(self):
        for empreinte in ('visiteur-a', 'visiteur-b', 'visiteur-c',
                          'visiteur-d'):
            self._vues([empreinte])
            detecter_signal_interet_salle_vente(self.salle)
        self.assertEqual(
            LeadActivity.objects.filter(lead=self.lead, kind=LeadActivity.Kind.NOTE).count(), 1)

    def test_moins_de_3_vues_ne_genere_rien(self):
        self._vues(['visiteur-a', 'visiteur-b'])
        note = detecter_signal_interet_salle_vente(self.salle)
        self.assertIsNone(note)
        self.assertFalse(LeadActivity.objects.filter(lead=self.lead).exists())

    def test_lead_pas_en_quote_sent_ne_genere_rien(self):
        self.lead.stage = stages.NEW
        self.lead.save(update_fields=['stage'])
        self._vues(['visiteur-a', 'visiteur-b', 'visiteur-c'])
        note = detecter_signal_interet_salle_vente(self.salle)
        self.assertIsNone(note)

    def test_salle_sans_lead_ne_leve_jamais(self):
        salle_client = SalleVente.objects.create(company=self.company, titre='Sans lead')
        self._vues(['visiteur-a', 'visiteur-b', 'visiteur-c'],
                   salle=salle_client)
        note = detecter_signal_interet_salle_vente(salle_client)
        self.assertIsNone(note)


class SignalInteretEndpointTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor NTCRM27 API', slug='taqinor-ntcrm27-api')
        self.lead = Lead.objects.create(
            company=self.company, nom='Lead QS27 API', stage=stages.QUOTE_SENT)
        self.salle = SalleVente.objects.create(
            company=self.company, lead=self.lead, titre='Salle NTCRM27 API')

    def test_3_visiteurs_distincts_generent_la_note_via_endpoint(self):
        anon = APIClient()
        for ip in ('203.0.113.11', '203.0.113.12', '203.0.113.13'):
            resp = anon.get(
                f'/api/django/crm/salle-vente/{self.salle.token}/',
                HTTP_X_FORWARDED_FOR=ip)
            self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            LeadActivity.objects.filter(lead=self.lead, kind=LeadActivity.Kind.NOTE).count(), 1)

    def test_3_rechargements_du_meme_visiteur_ne_generent_rien(self):
        """CRX31 de bout en bout : le même appareil qui recharge trois fois
        n'invente plus un signal d'intérêt."""
        anon = APIClient()
        for _ in range(3):
            resp = anon.get(
                f'/api/django/crm/salle-vente/{self.salle.token}/',
                HTTP_X_FORWARDED_FOR='203.0.113.99')
            self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            LeadActivity.objects.filter(lead=self.lead, kind=LeadActivity.Kind.NOTE).count(), 0)
