"""CAD70 — sans catalogue Réalisations, le message J4 le DIT et guide.

Avant : quand aucune ``parametres.Realisation`` n'est publiée — le cas PAR
DÉFAUT —, ``_contexte_preuve`` rend des valeurs vides, les phrases de preuve
sautent (MRY13) et il ne reste que « Le suivi de production est en temps
réel, je peux vous montrer. », envoyé à J4 sans salutation, sans sujet, sans
référent.

Done : catalogue vide → le rendu porte ``preuve_manquante`` (l'aperçu remplace
le CTA WhatsApp par l'aide — test frontend) et le POST ``whatsapp/`` est
refusé en nommant le champ ; catalogue rempli → le texte complet part.
Contrat partagé : ``relance_etape_message.json`` (variante
``exemple_preuve_manquante``).
"""
import datetime
import json
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.crm import horaires
from apps.crm.models import Lead, LeadActivity, RelanceEtape
from apps.crm.services import message_pour_etape
from apps.parametres.models import CompanyProfile
from apps.parametres.models_realisations import Realisation

User = get_user_model()

LUNDI = datetime.datetime(2026, 9, 7, 9, 0, tzinfo=horaires.CASABLANCA)

CONTRATS = Path(__file__).resolve().parent / 'contract_samples'


def _contrat(nom):
    return json.loads((CONTRATS / f'{nom}.json').read_text(encoding='utf-8'))


class _Base(TestCase):
    slug = 'cad70'

    def setUp(self):
        self.company = Company.objects.create(nom='CAD70 Solaire',
                                              slug=self.slug)
        CompanyProfile.objects.get_or_create(company=self.company)
        self.acteur = User.objects.create_user(
            username=f'{self.slug}-resp', password='x',
            role_legacy='responsable', company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Benali', prenom='Aziz',
            ville='Casablanca', telephone='+212661112233',
            whatsapp='+212661112233', owner=self.acteur)
        self.etape = RelanceEtape.objects.create(
            company=self.company, lead=self.lead, ordre=4, canal='whatsapp',
            libelle='Preuve — installation comparable',
            due_date=LUNDI.date(), due_at=LUNDI, cadence='apres_devis',
            template_cle='j4_preuve')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.acteur)}')


class CatalogueVideTests(_Base):
    slug = 'cad70-vide'

    def test_le_rendu_signale_la_preuve_manquante(self):
        rendu = message_pour_etape(self.etape, user=self.acteur)
        self.assertTrue(rendu['preuve_manquante'])
        # La phrase orpheline est exactement celle du contrat.
        self.assertEqual(
            rendu['message'],
            _contrat('relance_etape_message')[
                'exemple_preuve_manquante']['message'])

    def test_l_api_sert_le_drapeau_a_la_forme_du_contrat(self):
        resp = self.api.get(
            f'/api/django/crm/relance-etapes/{self.etape.pk}/message/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIs(resp.data['preuve_manquante'], True)
        self.assertEqual(set(resp.data),
                         set(_contrat('relance_etape_message')['exemple']))

    def test_le_clic_whatsapp_est_refuse_en_nommant_la_preuve(self):
        resp = self.api.post(
            f'/api/django/crm/relance-etapes/{self.etape.pk}/whatsapp/')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('preuve', resp.data['erreurs'])
        self.assertIn('aucune réalisation publiée',
                      resp.data['erreurs']['preuve'])
        # Rien n'est journalisé comme « ouvert ».
        self.assertFalse(LeadActivity.objects.filter(
            lead=self.lead, kind=LeadActivity.Kind.WHATSAPP).exists())


class CatalogueRempliTests(_Base):
    slug = 'cad70-rempli'

    def setUp(self):
        super().setUp()
        Realisation.objects.create(
            company=self.company, titre='Villa à Casablanca',
            ville='Casablanca', mise_en_service=datetime.date(2026, 7, 1),
            puissance_kwc=Decimal('11.44'),
            url_page='https://taqinor.ma/realisations/villa-casablanca/')

    def test_le_texte_complet_part(self):
        rendu = message_pour_etape(self.etape, user=self.acteur)
        self.assertFalse(rendu['preuve_manquante'])
        self.assertIn('Voici une installation comparable', rendu['message'])
        self.assertIn('juillet 2026', rendu['message'])
        self.assertIn('Casablanca', rendu['message'])

    def test_le_clic_whatsapp_est_journalise(self):
        resp = self.api.post(
            f'/api/django/crm/relance-etapes/{self.etape.pk}/whatsapp/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertFalse(resp.data['preuve_manquante'])


class HorsJ4Tests(_Base):
    slug = 'cad70-hors-j4'

    def test_un_texte_sans_preuve_ne_leve_jamais_le_drapeau(self):
        self.etape.template_cle = 'j6_garanties'
        self.etape.save(update_fields=['template_cle'])
        rendu = message_pour_etape(self.etape, user=self.acteur)
        self.assertFalse(rendu['preuve_manquante'])
