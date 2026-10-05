"""CIQ503 — accusé « en attente d'un accord » et résumé pour la direction :
deux textes prêts, sans liste inventée.

(a) ``message_pour_etape(cle='attente_accord_accuse')`` rend le texte, et la
    clé ``crochets`` de la réponse liste ses crochets ;
(b) par l'action ``resume-associe``, la variante B2B de ``resume_associe``
    n'est servie qu'à un lead commercial ou industriel ; un agricole garde le
    texte d'AGR534 ;
(c) aucun des deux textes ne contient de chiffre, « crédit-bail » ni
    « famille ».

Run :
    python manage.py test apps.crm.tests_ciq_textes_attente -v 2
"""
import datetime
import re
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from testkit.time import frozen

from apps.crm import horaires
from apps.crm.models import Client, Lead, RelanceEtape
from apps.crm.services import CLES_MESSAGE_REPONSE, message_pour_etape
from apps.parametres.models import CompanyProfile
from apps.parametres.models_messages import (
    MESSAGE_TEMPLATE_DEFAULTS, MESSAGE_TEMPLATE_DEFAULTS_DARIJA,
    MessageTemplate, variante_segment,
)
from apps.ventes.domain.cycle_vie import mark_devis_sent
from apps.ventes.models import Devis

User = get_user_model()

MERCREDI = datetime.datetime(2026, 9, 23, 10, 0, tzinfo=horaires.CASABLANCA)

CRET = "qui doit donner son accord"


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class _Base(TestCase):
    slug = 'ciq503'
    segment = 'commercial'

    def setUp(self):
        gel = frozen(MERCREDI)
        gel.start()
        self.addCleanup(gel.stop)
        self.company = Company.objects.create(nom='CIQ503', slug=self.slug)
        CompanyProfile.objects.get_or_create(company=self.company)
        self.user = User.objects.create_user(
            username=f'{self.slug}-resp', password='x',
            role_legacy='responsable', company=self.company,
            first_name='Nadia')
        self.lead = Lead.objects.create(
            company=self.company, nom='Alaoui', prenom='Driss',
            owner=self.user, telephone='+212661000503',
            type_installation=self.segment, societe='Hôtel Atlas SARL',
            contact_secondaire_nom='Direction',
            contact_secondaire_telephone='0661223344')


class AccuseAttenteAccord(_Base):
    def _touche(self):
        quand = MERCREDI + datetime.timedelta(hours=1)
        return RelanceEtape.objects.create(
            company=self.company, lead=self.lead, cadence='contact',
            ordre=4, canal=RelanceEtape.Canal.APPEL, libelle='Appel 3',
            due_at=quand, due_date=quand.astimezone(horaires.CASABLANCA).date(),
            cadence_depart=MERCREDI - datetime.timedelta(days=1))

    def test_la_cle_est_un_texte_de_reponse(self):
        self.assertIn('attente_accord_accuse', CLES_MESSAGE_REPONSE)
        self.assertIn('attente_accord_accuse',
                      {c for c, _ in MessageTemplate.Cle.choices})

    def test_a_message_pour_etape_rend_le_texte_et_ses_crochets(self):
        rendu = message_pour_etape(self._touche(), user=self.user,
                                   cle='attente_accord_accuse', langue='fr')
        self.assertIn("c'est noté : la décision passe par", rendu['message'])
        self.assertEqual(rendu['crochets'], ['[' + CRET + ']', '[jour]'])

    def test_a_par_l_api_cle_acceptee(self):
        etape = self._touche()
        resp = _api(self.user).get(
            f'/api/django/crm/relance-etapes/{etape.pk}/message/'
            '?cle=attente_accord_accuse')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn('[' + CRET + ']', resp.data['crochets'])

    def test_c_aucun_chiffre_credit_bail_ni_famille(self):
        textes = (MESSAGE_TEMPLATE_DEFAULTS['attente_accord_accuse'],
                  MESSAGE_TEMPLATE_DEFAULTS_DARIJA['attente_accord_accuse'],
                  variante_segment('resume_associe', 'commercial'),
                  variante_segment('resume_associe', 'industriel'))
        for texte in textes:
            with self.subTest(texte=texte[:30]):
                self.assertIsNone(re.search(r'\d', texte))
                self.assertNotIn('crédit-bail', texte.lower())
                self.assertNotIn('famille', texte.lower())
                self.assertNotIn('العائلة', texte)


class ResumeAssocieB2B(_Base):
    def setUp(self):
        super().setUp()
        client = Client.objects.create(
            company=self.company, nom='Alaoui', email=f'{self.slug}@ex.com')
        self.devis = Devis.objects.create(
            company=self.company, reference=f'DEV-{self.slug}-1',
            client=client, lead=self.lead, statut='brouillon',
            taux_tva=Decimal('20.00'))
        mark_devis_sent(devis=self.devis, user=self.user)

    def _message(self):
        resp = _api(self.user).post(
            f'/api/django/crm/leads/{self.lead.pk}/resume-associe/',
            {'devis_id': self.devis.pk, 'accord_client': True},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        return resp.data['message']

    def test_b_commercial_recoit_la_variante_direction(self):
        message = self._message()
        self.assertIn('pour votre direction ou votre comité', message)
        self.assertIn('Hôtel Atlas SARL', message)
        self.assertNotIn('{', message)

    def test_b_industriel_sans_raison_sociale_phrase_omise(self):
        Lead.objects.filter(pk=self.lead.pk).update(
            type_installation='industriel', societe='')
        message = self._message()
        self.assertIn('pour votre direction ou votre comité', message)
        self.assertNotIn('Elle concerne le projet', message)
        self.assertNotIn('{', message)

    def test_b_agricole_garde_le_texte_d_agr534(self):
        Lead.objects.filter(pk=self.lead.pk).update(
            type_installation='agricole')
        message = self._message()
        self.assertNotIn('direction ou votre comité', message)
        self.assertIn("avec l'accord de notre client, le résumé de la "
                      'proposition solaire préparée par', message)

    def test_b_texte_personnalise_jamais_remplace(self):
        MessageTemplate.objects.create(
            company=self.company, cle='resume_associe',
            corps_fr='Texte maison {lien}')
        self.assertTrue(self._message().startswith('Texte maison'))
