"""CAD123 — [TRANCHÉ 21/09/2026] une visite SANS devis envoyé : on AVERTIT, on
ne bloque pas.

La doctrine du 15/09 est « visite technique jamais avant le devis ». Le
panneau de coaching la respecte ; la fiche (``SectionVisite``) planifiait sans
aucune garde. Décision fondateur : l'écran NOMME la règle et laisse passer —
le terrain a des exceptions légitimes.

Ce fichier verrouille, contre le contrat COMMITTÉ
``apps/crm/contract_samples/lead_visites.json`` (le test écran l'importe) :

  * sans devis envoyé, la lecture des visites porte l'avertissement qui NOMME
    la règle, et son rappel juridique (CAD122) — mot pour mot le contrat ;
  * un devis sorti du brouillon ⇒ deux chaînes VIDES (jamais null) ;
  * planifier SANS devis n'est PAS refusé (201) ;
  * la visite ainsi posée est VISIBLE comme telle dans le suivi (note).
"""
import datetime
import json
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from testkit.time import frozen

from apps.crm import horaires, services
from apps.crm.models import Client, Lead
from apps.parametres.models import CompanyProfile

User = get_user_model()

MAINTENANT = datetime.datetime(2026, 9, 23, 10, 0, tzinfo=horaires.CASABLANCA)
DEMAIN = datetime.date(2026, 9, 24)

CONTRAT = json.loads(
    (Path(__file__).resolve().parent / 'contract_samples'
     / 'lead_visites.json').read_text(encoding='utf-8'))


class TextesDuContratTests(SimpleTestCase):
    """Le contrat dit EXACTEMENT ce que le serveur écrit (aucun mock retapé)."""

    def test_l_avertissement_nomme_la_regle(self):
        exemple = CONTRAT['exemple_sans_devis']
        self.assertEqual(exemple['avertissement_sans_devis'],
                         services.AVERTISSEMENT_VISITE_SANS_DEVIS)
        self.assertIn('se propose APRÈS le devis',
                      exemple['avertissement_sans_devis'])

    def test_le_rappel_juridique_est_celui_de_cad122(self):
        exemple = CONTRAT['exemple_sans_devis']
        self.assertEqual(exemple['rappel_juridique'],
                         services.RAPPEL_JURIDIQUE_VISITE_DOMICILE)
        self.assertIn('31-08', exemple['rappel_juridique'])

    def test_avec_devis_deux_chaines_vides(self):
        self.assertEqual(CONTRAT['exemple']['avertissement_sans_devis'], '')
        self.assertEqual(CONTRAT['exemple']['rappel_juridique'], '')

    def test_les_deux_etats_ont_la_meme_forme(self):
        self.assertEqual(sorted(CONTRAT['exemple']),
                         sorted(CONTRAT['exemple_sans_devis']))


class VisiteSansDevisTests(TestCase):

    def setUp(self):
        gel = frozen(MAINTENANT)
        gel.start()
        self.addCleanup(gel.stop)
        self.company = Company.objects.create(nom='CAD123 Solaire',
                                              slug='cad123-solaire')
        CompanyProfile.objects.get_or_create(company=self.company)
        self.acteur = User.objects.create_user(
            username='cad123-resp', password='x', role_legacy='responsable',
            company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Alaoui', prenom='Hicham',
            owner=self.acteur, telephone='+212661000123')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.acteur)}')

    def _url(self, suffixe):
        return f'/api/django/crm/leads/{self.lead.pk}/{suffixe}'

    def _devis_envoye(self):
        from apps.ventes.models import Devis

        client = Client.objects.create(company=self.company, nom='Alaoui',
                                       email='cad123@example.com')
        return Devis.objects.create(
            company=self.company, reference='DEV-2609-CAD123', client=client,
            lead=self.lead, statut='envoye', taux_tva=Decimal('20.00'),
            date_envoi=MAINTENANT)

    def test_sans_devis_la_lecture_porte_l_avertissement_du_contrat(self):
        reponse = self.api.get(self._url('visites/'))
        self.assertEqual(reponse.status_code, 200, reponse.data)
        attendu = CONTRAT['exemple_sans_devis']
        self.assertEqual(sorted(reponse.data), sorted(attendu))
        self.assertEqual(reponse.data['avertissement_sans_devis'],
                         attendu['avertissement_sans_devis'])
        self.assertEqual(reponse.data['rappel_juridique'],
                         attendu['rappel_juridique'])

    def test_avec_un_devis_envoye_rien_a_dire(self):
        self._devis_envoye()
        reponse = self.api.get(self._url('visites/'))
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(reponse.data['avertissement_sans_devis'],
                         CONTRAT['exemple']['avertissement_sans_devis'])
        self.assertEqual(reponse.data['rappel_juridique'],
                         CONTRAT['exemple']['rappel_juridique'])

    def test_planifier_sans_devis_n_est_pas_refuse(self):
        reponse = self.api.post(self._url('visites/planifier/'),
                                {'date_prevue': DEMAIN.isoformat()},
                                format='json')
        self.assertEqual(reponse.status_code, 201, reponse.data)

    def test_la_visite_sans_devis_est_signalee_dans_le_suivi(self):
        self.api.post(self._url('visites/planifier/'),
                      {'date_prevue': DEMAIN.isoformat()}, format='json')
        note = self.lead.activites.filter(
            body__startswith='Visite technique planifiée').get()
        self.assertIn(services.MENTION_VISITE_SANS_DEVIS, note.body)

    def test_avec_devis_la_note_reste_ordinaire(self):
        self._devis_envoye()
        self.api.post(self._url('visites/planifier/'),
                      {'date_prevue': DEMAIN.isoformat()}, format='json')
        note = self.lead.activites.filter(
            body__startswith='Visite technique planifiée').get()
        self.assertNotIn(services.MENTION_VISITE_SANS_DEVIS, note.body)
