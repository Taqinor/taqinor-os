"""CAD111 — le message qui propose la visite laisse une TRACE, et son lien
wa.me est normalisé par le serveur.

Avant : ``MessageVisiteDialog`` construisait le lien côté écran en chiffres
bruts (« 06… » sans indicatif) et faisait ``window.open`` sans le moindre appel
serveur ; l'action ``message-visite`` est une lecture pure. Le message le plus
décisif du suivi pouvait partir sans rien au chatter — et RLC3 faisait ensuite
cocher l'aveu FAUX « marquée faite sans avoir ouvert le message ».

Done : ``POST leads/<id>/message-visite/ouvert/`` écrit une ligne au chatter
(« ouvert », jamais « fait »), rattachée à la touche quand elle est donnée ;
un numéro saisi « 06… » produit un lien E.164 valide. Contrats partagés :
``lead_message_visite.json`` et ``lead_message_visite_ouvert.json``.
"""
import datetime
import json
from pathlib import Path
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from testkit.time import frozen

from apps.crm import horaires, stages
from apps.crm.models import Lead, LeadActivity, RelanceEtape
from apps.crm.serializers import RelanceEtapeSerializer
from apps.parametres.models import CompanyProfile
from apps.roles.models import Role

User = get_user_model()

MERCREDI = datetime.datetime(2026, 9, 23, 10, 0, tzinfo=horaires.CASABLANCA)

CONTRATS = Path(__file__).resolve().parent / 'contract_samples'


def _contrat(nom):
    return json.loads((CONTRATS / f'{nom}.json').read_text(encoding='utf-8'))


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class _Base(TestCase):
    slug = 'cad111'

    def setUp(self):
        gel = frozen(MERCREDI)
        gel.start()
        self.addCleanup(gel.stop)
        self.company = Company.objects.create(nom='CAD111 Solaire',
                                              slug=self.slug)
        CompanyProfile.objects.get_or_create(company=self.company)
        self.acteur = User.objects.create_user(
            username=f'{self.slug}-resp', password='x',
            role_legacy='responsable', company=self.company)
        # Numéro SAISI « 06… » : le lien doit partir en E.164.
        self.lead = Lead.objects.create(
            company=self.company, nom='Idrissi', prenom='Salma',
            stage=stages.QUOTE_SENT, owner=self.acteur,
            telephone='0612345678')
        self.etape = RelanceEtape.objects.create(
            company=self.company, lead=self.lead, cadence='apres_devis',
            ordre=3, canal=RelanceEtape.Canal.WHATSAPP,
            libelle='Preuve — installation comparable',
            template_cle='j4_preuve', due_at=MERCREDI,
            due_date=MERCREDI.date())
        self.api = _api(self.acteur)

    def _ouvert(self, **corps):
        return self.api.post(
            f'/api/django/crm/leads/{self.lead.pk}/message-visite/ouvert/',
            corps, format='json')


class TraceTests(_Base):
    slug = 'cad111-trace'

    def test_l_ouverture_ecrit_une_ligne_au_chatter_jamais_fait(self):
        resp = self._ouvert(cle='visite_proposition', langue='darija',
                            etape=self.etape.pk)
        self.assertEqual(resp.status_code, 200, resp.data)
        ligne = LeadActivity.objects.get(lead=self.lead,
                                         kind=LeadActivity.Kind.WHATSAPP)
        self.assertEqual(ligne.user, self.acteur)
        self.assertEqual(ligne.outcome, '')
        self.assertIn('message de visite « proposer la visite »', ligne.body)
        # « ouvert », jamais « fait » : la touche reste à faire.
        self.etape.refresh_from_db()
        self.assertEqual(self.etape.statut, RelanceEtape.Statut.A_FAIRE)
        # Le premier contact est horodaté (même règle que la touche WhatsApp).
        self.lead.refresh_from_db()
        self.assertIsNotNone(self.lead.first_contacted_at)

    def test_la_touche_sait_que_le_message_a_ete_ouvert(self):
        """RLC3 ne fait plus cocher l'aveu faux « sans ouverture »."""
        self._ouvert(cle='visite_proposition', langue='fr',
                     etape=self.etape.pk)
        donnees = RelanceEtapeSerializer(
            self.etape,
            context={'request': SimpleNamespace(user=self.acteur)}).data
        self.assertIsNotNone(donnees['message_ouvert_le'])

    def test_la_reponse_a_la_forme_du_contrat(self):
        resp = self._ouvert(cle='visite_confirmation', langue='fr')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(set(resp.data),
                         set(_contrat('lead_message_visite_ouvert')['exemple']))
        self.assertIsNone(resp.data['etape'])
        self.assertTrue(LeadActivity.objects.filter(
            lead=self.lead, kind=LeadActivity.Kind.WHATSAPP,
            body__startswith='WhatsApp ouvert — message de visite').exists())

    def test_les_refus_nomment_le_champ(self):
        autre_lead = Lead.objects.create(company=self.company, nom='Autre')
        autre_touche = RelanceEtape.objects.create(
            company=self.company, lead=autre_lead, cadence='apres_devis',
            ordre=1, canal=RelanceEtape.Canal.WHATSAPP, libelle='Autre',
            due_at=MERCREDI, due_date=MERCREDI.date())
        cas = (
            ({'cle': 'apres_visite'}, 'cle'),
            ({'cle': 'visite_proposition', 'langue': 'en'}, 'langue'),
            ({'cle': 'visite_proposition', 'etape': autre_touche.pk}, 'etape'),
        )
        for corps, champ in cas:
            resp = self._ouvert(**corps)
            self.assertEqual(resp.status_code, 400, corps)
            self.assertIn(champ, resp.data['erreurs'])
        self.assertFalse(LeadActivity.objects.filter(
            lead=self.lead, kind=LeadActivity.Kind.WHATSAPP).exists())


class LienServeurTests(_Base):
    slug = 'cad111-lien'

    def test_un_numero_saisi_en_06_produit_un_lien_e164(self):
        resp = self.api.get(
            f'/api/django/crm/leads/{self.lead.pk}/message-visite/',
            {'cle': 'visite_proposition'})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(resp.data['wa_url_fr'].startswith(
            'https://wa.me/212612345678?text='))
        self.assertTrue(resp.data['wa_url_darija'].startswith(
            'https://wa.me/212612345678?text='))
        self.assertEqual(set(resp.data),
                         set(_contrat('lead_message_visite')['exemple']))

    def test_sans_droit_pii_aucun_numero_ne_sort(self):
        role = Role.objects.create(
            company=self.company, nom='CAD111 sans PII',
            permissions=['crm_voir'])
        lecteur = User.objects.create_user(
            username='cad111-lecteur', password='x', role=role,
            company=self.company)
        self.lead.owner = lecteur
        self.lead.save(update_fields=['owner'])
        resp = _api(lecteur).get(
            f'/api/django/crm/leads/{self.lead.pk}/message-visite/',
            {'cle': 'visite_proposition'})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIsNone(resp.data['wa_url_fr'])
        self.assertIsNone(resp.data['wa_url_darija'])
        self.assertEqual(resp.data['phone'], '')
