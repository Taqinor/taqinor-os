"""RLC3 — « le message a-t-il été ouvert ? » servi avec la touche.

Le panneau « Fait » d'une touche WhatsApp/e-mail rappelle l'ouverture du
message et, à défaut, demande une confirmation explicite (écran :
``RelanceEtapeRow.rlc3.test.jsx``). Ce fichier verrouille la MOITIÉ SERVEUR de
ce contrat :

  * ``message_ouvert_le`` porte l'horodatage de l'activité « WhatsApp ouvert »
    de CETTE touche, et rien d'autre (ni celle d'une autre touche, ni celle
    d'un autre lead) ;
  * il reste ``null`` là où la question n'a pas de sens — touche d'appel, touche
    déjà traitée — ce qui est AUSSI la garantie de coût : aucune requête pour
    ces lignes ;
  * le préfixe qui relie l'écriture à la lecture est UNIQUE : deux littéraux
    auraient dérivé et le rappel se serait tu en silence.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.crm import horaires
from apps.crm.models import Lead, RelanceEtape
from apps.crm.services import (
    journaliser_whatsapp_ouvert, marquer_etape_relance,
    prefixe_activite_message_ouvert)
from apps.parametres.models import CompanyProfile

User = get_user_model()

MARDI = datetime.datetime(2026, 9, 8, 12, 0, tzinfo=horaires.CASABLANCA)


def _company(slug):
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': slug})
    CompanyProfile.objects.get_or_create(company=company)
    return company


class MessageOuvertLeTests(TestCase):
    slug = 'rlc3'

    def setUp(self):
        self.company = _company(self.slug)
        self.acteur = User.objects.create_user(
            username=f'{self.slug}-u', password='x',
            role_legacy='responsable', company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Prospect', owner=self.acteur,
            telephone='+212651971400')
        self.api = APIClient()
        self.api.credentials(HTTP_AUTHORIZATION=(
            f'Bearer {AccessToken.for_user(self.acteur)}'))

    def _touche(self, canal, *, libelle, statut=RelanceEtape.Statut.A_FAIRE,
                ordre=1):
        return RelanceEtape.objects.create(
            company=self.company, lead=self.lead, cadence='apres_devis',
            ordre=ordre, canal=canal, libelle=libelle, statut=statut,
            due_at=MARDI, due_date=MARDI.astimezone(horaires.CASABLANCA).date())

    def _ligne(self, etape, *, rendu=False):
        """La ligne servie pour CETTE touche. ``rendu=True`` lit le JSON
        RÉELLEMENT envoyé (l'écran ne voit que celui-là)."""
        resp = self.api.get(
            '/api/django/crm/relance-etapes/', {'lead': etape.lead_id})
        self.assertEqual(resp.status_code, 200, resp.data)
        resultats = resp.json()['results'] if rendu else resp.data['results']
        return next(ligne for ligne in resultats if ligne['id'] == etape.pk)

    def _servi(self, etape):
        return self._ligne(etape)['message_ouvert_le']

    def test_null_tant_que_le_message_na_pas_ete_ouvert(self):
        etape = self._touche(
            RelanceEtape.Canal.WHATSAPP, libelle='Preuve — installation')
        self.assertIsNone(self._servi(etape))

    def test_porte_lhorodatage_de_louverture(self):
        etape = self._touche(
            RelanceEtape.Canal.WHATSAPP, libelle='Preuve — installation')
        activite = journaliser_whatsapp_ouvert(etape, self.acteur)

        # L'instant EXACT de l'activité de chatter — jamais une autre heure.
        self.assertEqual(self._servi(etape), activite.created_at)
        # Et sur le fil, un horodatage ISO-8601 : c'est tout ce que l'écran voit.
        self.assertRegex(
            self._ligne(etape, rendu=True)['message_ouvert_le'],
            r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}')

    def test_louverture_dune_AUTRE_touche_ne_compte_pas(self):
        etape = self._touche(
            RelanceEtape.Canal.WHATSAPP, libelle='Preuve — installation')
        autre = self._touche(
            RelanceEtape.Canal.WHATSAPP, libelle='Relance — dernier rappel',
            ordre=2)
        journaliser_whatsapp_ouvert(autre, self.acteur)

        self.assertIsNone(self._servi(etape))
        self.assertIsNotNone(self._servi(autre))

    def test_louverture_dun_AUTRE_lead_ne_compte_pas(self):
        etape = self._touche(
            RelanceEtape.Canal.WHATSAPP, libelle='Preuve — installation')
        voisin = Lead.objects.create(
            company=self.company, nom='Voisin', owner=self.acteur)
        jumelle = RelanceEtape.objects.create(
            company=self.company, lead=voisin, cadence='apres_devis', ordre=1,
            canal=RelanceEtape.Canal.WHATSAPP,
            libelle='Preuve — installation', due_at=MARDI,
            due_date=MARDI.astimezone(horaires.CASABLANCA).date())
        journaliser_whatsapp_ouvert(jumelle, self.acteur)

        self.assertIsNone(self._servi(etape))

    def test_une_touche_dappel_ne_pose_jamais_la_question(self):
        etape = self._touche(
            RelanceEtape.Canal.APPEL, libelle='Appel de suivi')
        journaliser_whatsapp_ouvert(etape, self.acteur)
        self.assertIsNone(self._servi(etape))

    def test_une_touche_deja_traitee_ne_pose_plus_la_question(self):
        etape = self._touche(
            RelanceEtape.Canal.WHATSAPP, libelle='Preuve — installation')
        journaliser_whatsapp_ouvert(etape, self.acteur)
        marquer_etape_relance(
            etape, self.acteur, RelanceEtape.Statut.FAIT, outcome='non_joint')

        self.assertIsNone(self._servi(etape))

    def test_le_prefixe_de_reconnaissance_est_celui_qui_est_ECRIT(self):
        """La garde anti-dérive : l'écriture et la lecture partagent LE préfixe.

        Sans ce test, changer la phrase de ``journaliser_whatsapp_ouvert``
        éteindrait le rappel du panneau « Fait » sans qu'aucune suite ne
        rougisse."""
        etape = self._touche(
            RelanceEtape.Canal.WHATSAPP, libelle='Preuve — installation')
        activite = journaliser_whatsapp_ouvert(etape, self.acteur)
        self.assertTrue(
            activite.body.startswith(prefixe_activite_message_ouvert(etape)),
            activite.body)
