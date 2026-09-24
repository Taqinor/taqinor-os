"""CAD164 — [TRANCHÉ 21/09/2026] le client est locataire : demander le
propriétaire, sinon « Perdu — Locataire ».

Done : répondre « locataire » PROPOSE la création de la fiche du propriétaire,
liée ; le refus de communiquer le propriétaire clôt avec le motif
« Locataire ». Aucune valeur d'énumération neuve. Contrat partagé :
``apps/crm/contract_samples/lead_locataire.json``.
"""
import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.crm import horaires, services, stages
from apps.crm.models import Lead, LeadActivity, MotifPerte, RelanceEtape
from apps.parametres.models import CompanyProfile

User = get_user_model()

CONTRAT = json.loads(
    (Path(__file__).resolve().parent / 'contract_samples'
     / 'lead_locataire.json').read_text(encoding='utf-8'))


class LocatairePurTests(SimpleTestCase):

    def test_la_proposition_a_la_forme_du_contrat(self):
        oui = services.proposition_locataire(
            Lead(nom='x', ownership=Lead.Ownership.LOCATAIRE))
        non = services.proposition_locataire(
            Lead(nom='x', ownership=Lead.Ownership.PROPRIETAIRE))
        self.assertEqual(oui, CONTRAT['exemple'])
        self.assertEqual(non, CONTRAT['exemple_pas_locataire'])

    def test_aucune_valeur_d_enumeration_neuve(self):
        self.assertIn(services.MOTIF_PERTE_LOCATAIRE, ('Locataire',))
        self.assertIn(Lead.Canal.REFERENCE, Lead.Canal.values)
        self.assertIn(Lead.Ownership.LOCATAIRE, Lead.Ownership.values)

    def test_un_proprietaire_sans_numero_est_refuse_en_nommant_le_champ(self):
        self.assertEqual(
            services.refus_proprietaire({'nom': 'Tazi', 'telephone': ''}),
            CONTRAT['exemple_erreur_proprietaire']['proprietaire'])
        self.assertIsNone(services.refus_proprietaire(
            CONTRAT['corps_proprietaire']['proprietaire']))


class LocataireApiTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(nom='CAD164 Solaire',
                                              slug='cad164-solaire')
        CompanyProfile.objects.get_or_create(company=self.company)
        MotifPerte.objects.create(company=self.company, nom='Locataire')
        self.acteur = User.objects.create_user(
            username='cad164-resp', password='x', role_legacy='responsable',
            company=self.company)
        self.locataire = Lead.objects.create(
            company=self.company, nom='Idrissi', prenom='Salma',
            stage=stages.CONTACTED, owner=self.acteur,
            telephone='+212661000164', ville='Casablanca',
            type_installation=Lead.TypeInstallation.RESIDENTIEL)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.acteur)}')

    def _url(self):
        return f'/api/django/crm/leads/{self.locataire.pk}/locataire/'

    def test_repondre_locataire_propose_la_fiche_du_proprietaire(self):
        resp = self.api.patch(f'/api/django/crm/leads/{self.locataire.pk}/',
                              {'ownership': 'locataire'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        propose = self.api.get(self._url())
        self.assertEqual(propose.status_code, 200, propose.data)
        self.assertEqual(propose.data, CONTRAT['exemple'])

    def test_la_fiche_du_proprietaire_est_creee_et_liee(self):
        resp = self.api.post(self._url(), CONTRAT['corps_proprietaire'],
                             format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        attendu = CONTRAT['exemple_proprietaire_cree']
        self.assertEqual(set(resp.data), set(attendu))
        self.assertEqual(resp.data['issue'], attendu['issue'])
        self.assertEqual(set(resp.data['locataire']),
                         set(attendu['locataire']))
        proprietaire = Lead.objects.get(pk=resp.data['lead_proprietaire']['id'])
        donnees = CONTRAT['corps_proprietaire']['proprietaire']
        self.assertEqual(proprietaire.company, self.company)
        self.assertEqual(proprietaire.nom, donnees['nom'])
        self.assertEqual(proprietaire.canal, Lead.Canal.REFERENCE)
        self.assertEqual(proprietaire.ownership, Lead.Ownership.PROPRIETAIRE)
        self.assertEqual(proprietaire.owner, self.acteur)
        self.assertEqual(proprietaire.ville, 'Casablanca')
        # Le lien : une note de chaque côté, jamais une fusion.
        self.assertTrue(proprietaire.activites.filter(
            body__startswith=services.PREFIXE_LIEN_LOCATAIRE).exists())
        self.assertTrue(self.locataire.activites.filter(
            body__contains=f'#{proprietaire.pk}').exists())
        # Le locataire reste le prescripteur — son PRÉNOM, lu sur le lien.
        self.assertEqual(services._nom_prescripteur(proprietaire), 'Salma')
        self.locataire.refresh_from_db()
        self.assertEqual(self.locataire.ownership, Lead.Ownership.LOCATAIRE)
        self.assertFalse(self.locataire.perdu)

    def test_un_proprietaire_deja_connu_est_relie_jamais_duplique(self):
        deja = Lead.objects.create(
            company=self.company, nom='Tazi',
            telephone=CONTRAT['corps_proprietaire']['proprietaire']['telephone'])
        avant = Lead.objects.filter(company=self.company).count()
        resp = self.api.post(self._url(), CONTRAT['corps_proprietaire'],
                             format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['issue'], 'proprietaire_relie')
        self.assertEqual(resp.data['lead_proprietaire']['id'], deja.pk)
        self.assertEqual(Lead.objects.filter(company=self.company).count(),
                         avant)

    def test_proprietaire_inconnu_clot_perdu_locataire(self):
        maintenant = timezone.now().astimezone(horaires.CASABLANCA)
        touche = RelanceEtape.objects.create(
            company=self.company, lead=self.locataire, cadence='contact',
            ordre=2, canal=RelanceEtape.Canal.APPEL, libelle='Appel 2',
            due_at=maintenant, due_date=maintenant.date())
        resp = self.api.post(self._url(),
                             CONTRAT['corps_proprietaire_inconnu'],
                             format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data, {
            **CONTRAT['exemple_perdu_locataire'],
            'locataire': {**CONTRAT['exemple_perdu_locataire']['locataire'],
                          'id': self.locataire.pk}})
        self.locataire.refresh_from_db()
        self.assertTrue(self.locataire.perdu)
        self.assertEqual(self.locataire.motif_perte, 'Locataire')
        touche.refresh_from_db()
        self.assertEqual(touche.statut, RelanceEtape.Statut.ANNULEE)

    def test_un_corps_vide_est_refuse_en_nommant_le_champ(self):
        resp = self.api.post(self._url(), {}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('proprietaire', resp.data)

    def test_un_proprietaire_sans_numero_ne_cree_rien(self):
        avant = Lead.objects.filter(company=self.company).count()
        resp = self.api.post(
            self._url(), {'proprietaire': {'nom': 'Tazi', 'telephone': ''}},
            format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data, CONTRAT['exemple_erreur_proprietaire'])
        self.assertEqual(Lead.objects.filter(company=self.company).count(),
                         avant)
        self.assertFalse(LeadActivity.objects.filter(
            body__startswith=services.PREFIXE_LIEN_LOCATAIRE).exists())
