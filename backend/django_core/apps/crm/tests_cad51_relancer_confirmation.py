"""CAD51 — « Relancer la cadence » ne TUE plus une cadence en cours en silence.

Avant : relancer depuis la fiche une cadence PLUS prioritaire que l'active
(« Prise de contact » sur un lead en réveil, « Après devis » sur un lead en
prise de contact) appelait ``arreter_cadence`` sans une question ni un motif,
et l'écran toastait « Cadence relancée. ».

Done : sans confirmation → REFUS (409) avant toute écriture, qui nomme la
cadence arrêtée et le nombre de touches ouvertes perdues ; avec confirmation
→ le motif est obligatoire et l'arrêt est tracé sous ce motif, comme un arrêt
normal. Le moteur (``initialiser_plan_relance`` sans ``exiger_confirmation``)
garde son remplacement silencieux. Contrat partagé :
``contract_samples/lead_relance_initialiser.json``.
"""
import datetime
import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm import services
from apps.crm.models import Lead, LeadActivity, RelanceEtape
from authentication.models import Company

User = get_user_model()

CONTRATS = Path(__file__).resolve().parent / 'contract_samples'


def _contrat(nom):
    return json.loads((CONTRATS / f'{nom}.json').read_text(encoding='utf-8'))


CONTRAT = _contrat('lead_relance_initialiser')


def _touche(lead, cadence, ordre, jours):
    due = timezone.now() + datetime.timedelta(days=jours)
    return RelanceEtape.objects.create(
        company=lead.company, lead=lead, cadence=cadence, ordre=ordre,
        canal=RelanceEtape.Canal.WHATSAPP, libelle=f'Touche {ordre}',
        due_at=due, due_date=due.date())


class RelancerAvecConfirmationTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(nom='CAD51 Solaire',
                                              slug='cad51')
        self.acteur = User.objects.create_user(
            username='cad51-resp', password='x', role_legacy='responsable',
            company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Benali', prenom='Aziz',
            owner=self.acteur, telephone='+212661510051')
        # Un dossier dormant : ses deux réveils (J30/J60) sont posés.
        self.reveils = [_touche(self.lead, 'reveil', 1, 30),
                        _touche(self.lead, 'reveil', 2, 60)]
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.acteur)}')
        self.url = (f'/api/django/crm/leads/{self.lead.pk}'
                    '/relance/initialiser/')

    def _statuts_reveil(self):
        return {e.statut for e in RelanceEtape.objects.filter(
            pk__in=[e.pk for e in self.reveils])}

    def test_sans_confirmation_refus_409_qui_affirme_le_contrat(self):
        reponse = self.api.post(self.url, CONTRAT['corps'], format='json')
        self.assertEqual(reponse.status_code, 409, reponse.data)
        # Le contrat committé EST la réponse — clé par clé, texte compris.
        self.assertEqual(reponse.data, CONTRAT['exemple'])
        # Rien n'a été écrit : les réveils sont intacts, aucune touche neuve.
        self.assertEqual(self._statuts_reveil(),
                         {RelanceEtape.Statut.A_FAIRE})
        self.assertFalse(self.lead.relance_etapes.filter(
            cadence='contact').exists())

    def test_confirmation_sans_motif_refusee_en_nommant_le_champ(self):
        corps = dict(CONTRAT['corps_confirme'], motif='  ')
        reponse = self.api.post(self.url, corps, format='json')
        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertEqual(reponse.data, CONTRAT['exemple_erreur_motif'])
        self.assertEqual(self._statuts_reveil(),
                         {RelanceEtape.Statut.A_FAIRE})

    def test_avec_confirmation_arret_trace_avec_motif(self):
        reponse = self.api.post(
            self.url, CONTRAT['corps_confirme'], format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertTrue(reponse.data)
        self.assertEqual({r['cadence'] for r in reponse.data}, {'contact'})
        motif = CONTRAT['corps_confirme']['motif']
        for etape in RelanceEtape.objects.filter(
                pk__in=[e.pk for e in self.reveils]):
            self.assertEqual(etape.statut, RelanceEtape.Statut.ANNULEE)
            self.assertIn(motif, etape.note)
            self.assertIn('Prise de contact', etape.note)
        # L'arrêt est journalisé comme un arrêt normal — note publiée au
        # contrat, au caractère près.
        self.assertTrue(LeadActivity.objects.filter(
            lead=self.lead,
            body=CONTRAT['notes']['note_historique']).exists())

    def test_apres_devis_sur_prise_de_contact_exige_aussi_la_confirmation(
            self):
        # Le cas cité par l'audit : « Après devis » sur un lead en prise de
        # contact annulait toutes ses touches sans une question.
        RelanceEtape.objects.filter(lead=self.lead).delete()
        contact = [_touche(self.lead, 'contact', 2, 0),
                   _touche(self.lead, 'contact', 3, 1),
                   _touche(self.lead, 'contact', 4, 2)]
        reponse = self.api.post(
            self.url, {'cadence': 'apres_devis'}, format='json')
        self.assertEqual(reponse.status_code, 409, reponse.data)
        remplacement = reponse.data['remplacement']
        self.assertEqual(remplacement['cadences_arretees'], ['contact'])
        self.assertEqual(remplacement['touches_ouvertes'], 3)
        self.assertIn('« Prise de contact »', reponse.data['detail'])
        self.assertIn('3 touches ouvertes', reponse.data['detail'])
        self.assertEqual(
            {e.statut for e in RelanceEtape.objects.filter(
                pk__in=[e.pk for e in contact])},
            {RelanceEtape.Statut.A_FAIRE})

    def test_sans_cadence_en_cours_aucune_confirmation_demandee(self):
        RelanceEtape.objects.filter(lead=self.lead).delete()
        reponse = self.api.post(self.url, CONTRAT['corps'], format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertTrue(reponse.data)

    def test_cadence_moins_prioritaire_reste_le_refus_cadx(self):
        # « Réveil » sur une prise de contact active : refus CADX inchangé
        # (400 `erreurs.cadence`) — ce n'est pas un remplacement.
        RelanceEtape.objects.filter(lead=self.lead).delete()
        _touche(self.lead, 'contact', 2, 0)
        reponse = self.api.post(
            self.url, {'cadence': 'reveil'}, format='json')
        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertIn('cadence', reponse.data['erreurs'])


class MoteurInchangeTests(TestCase):
    """Le moteur garde son remplacement silencieux (CADX) ; le service refuse
    le chemin humain sans motif, avant toute écriture."""

    def setUp(self):
        self.company = Company.objects.create(nom='CAD51 Moteur',
                                              slug='cad51-moteur')
        self.acteur = User.objects.create_user(
            username='cad51-moteur', password='x', role_legacy='responsable',
            company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Idrissi', owner=self.acteur)
        self.contact = _touche(self.lead, 'contact', 3, 1)

    def test_service_exige_confirmation_leve_avant_ecriture(self):
        with self.assertRaises(services.CadenceRemplacementAConfirmer) as ctx:
            services.initialiser_plan_relance(
                self.lead, self.acteur, cadence='apres_devis',
                exiger_confirmation=True)
        self.assertEqual(ctx.exception.apercu['cadences_arretees'],
                         ['contact'])
        self.assertEqual(ctx.exception.apercu['touches_ouvertes'], 1)
        self.contact.refresh_from_db()
        self.assertEqual(self.contact.statut, RelanceEtape.Statut.A_FAIRE)

    def test_moteur_remplace_toujours_en_silence(self):
        etapes = services.initialiser_plan_relance(
            self.lead, self.acteur, cadence='apres_devis',
            depart=timezone.now())
        self.assertTrue(etapes)
        self.contact.refresh_from_db()
        self.assertEqual(self.contact.statut, RelanceEtape.Statut.ANNULEE)
        self.assertIn('remplacée par la cadence « apres_devis »',
                      self.contact.note)
