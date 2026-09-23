"""CAD63 — changer la langue AU MOMENT UTILE, sans trois écrans.

Avant : le texte d'une touche était rendu dans la langue de la fiche
(``lead.langue_preferee or 'fr'``), l'action ``message`` ne lisait aucun
paramètre de langue et l'aperçu était en lecture seule. Si la commerciale
découvrait au téléphone que le client ne lit pas le français, elle devait
sortir de la touche, ouvrir la fiche, changer le champ, revenir.

Done : le basculeur recharge le texte dans l'autre langue (``?langue=``, sans
toucher la fiche) et la réponse « ne parle que darija » pose
``langue_preferee='darija'`` — par le « Fait » de la touche ou par la
confirmation de l'aperçu (``POST …/langue/``).

Contrat partagé : les réponses ont les clés des exemples COMMITTÉS
``relance_etape_message.json`` (le rendu) et ``relance_etape_v2.json`` (la
touche) — le test frontend importe les mêmes exemples.
"""
import datetime
import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from testkit.time import frozen

from apps.crm import horaires, stages
from apps.crm.models import Lead, LeadActivity, RelanceEtape
from apps.parametres.models import CompanyProfile

User = get_user_model()

MERCREDI = datetime.datetime(2026, 9, 23, 10, 0, tzinfo=horaires.CASABLANCA)

CONTRATS = Path(__file__).resolve().parent / 'contract_samples'


def _contrat(nom):
    return json.loads((CONTRATS / f'{nom}.json').read_text(encoding='utf-8'))


class _Base(TestCase):
    slug = 'cad63'

    def setUp(self):
        gel = frozen(MERCREDI)
        gel.start()
        self.addCleanup(gel.stop)
        self.company = Company.objects.create(
            nom='CAD63 Solaire', slug=self.slug)
        CompanyProfile.objects.get_or_create(company=self.company)
        self.acteur = User.objects.create_user(
            username=f'{self.slug}-resp', password='x',
            role_legacy='responsable', company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Benali', prenom='Aziz',
            stage=stages.CONTACTED, owner=self.acteur,
            telephone='+212651971400', whatsapp='+212651971400')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.acteur)}')

    def _touche(self, *, canal=RelanceEtape.Canal.WHATSAPP,
                template_cle='valeur_j1'):
        return RelanceEtape.objects.create(
            company=self.company, lead=self.lead, cadence='contact',
            ordre=5, canal=canal, libelle='Message valeur (J1)',
            template_cle=template_cle, due_at=MERCREDI,
            due_date=MERCREDI.date())

    def _message(self, etape, **params):
        return self.api.get(
            f'/api/django/crm/relance-etapes/{etape.pk}/message/', params)


class BasculeurDeLangueTests(_Base):
    slug = 'cad63-bascule'

    def test_le_basculeur_recharge_le_texte_dans_l_autre_langue(self):
        etape = self._touche()
        fr = self._message(etape)
        darija = self._message(etape, langue='darija')
        self.assertEqual(fr.status_code, 200, fr.data)
        self.assertEqual(darija.status_code, 200, darija.data)
        self.assertEqual(fr.data['langue'], 'fr')
        self.assertEqual(darija.data['langue'], 'darija')
        self.assertNotEqual(fr.data['message'], darija.data['message'])
        # Le texte darija validé est en écriture arabe (jamais une
        # traduction automatique du français).
        self.assertIn('السلام', darija.data['message'])
        # MÊME forme que le contrat, dans les deux langues.
        attendu = set(_contrat('relance_etape_message')['exemple'])
        self.assertEqual(set(fr.data), attendu)
        self.assertEqual(set(darija.data), attendu)

    def test_basculer_l_apercu_ne_touche_pas_la_fiche(self):
        self._message(self._touche(), langue='darija')
        self.lead.refresh_from_db()
        self.assertIsNone(self.lead.langue_preferee)

    def test_une_langue_inconnue_est_refusee_en_nommant_le_champ(self):
        resp = self._message(self._touche(), langue='en')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('langue', resp.data['erreurs'])
        self.assertIn('« en »', resp.data['erreurs']['langue'])

    def test_le_clic_whatsapp_rend_la_langue_choisie(self):
        etape = self._touche()
        resp = self.api.post(
            f'/api/django/crm/relance-etapes/{etape.pk}/whatsapp/',
            {'langue': 'darija'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['langue'], 'darija')
        self.assertIn('السلام', resp.data['message'])


class EnregistrerLaLangueTests(_Base):
    slug = 'cad63-fiche'

    def test_la_confirmation_de_l_apercu_pose_la_langue_et_la_journalise(self):
        etape = self._touche()
        resp = self.api.post(
            f'/api/django/crm/relance-etapes/{etape.pk}/langue/',
            {'langue': 'darija'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.langue_preferee, 'darija')
        self.assertEqual(resp.data['lead_langue'], 'darija')
        # Journalisée comme une édition de la fiche (ancien → nouveau).
        self.assertTrue(LeadActivity.objects.filter(
            lead=self.lead, kind=LeadActivity.Kind.MODIFICATION,
            field='langue_preferee', user=self.acteur).exists())
        # La réponse est la touche, forme `relance_etape_v2`.
        attendu = set(_contrat('relance_etape_v2')['exemple']['results'][0])
        self.assertEqual(set(resp.data), attendu)

    def test_une_langue_vide_ou_inconnue_est_refusee(self):
        etape = self._touche()
        for corps in ({}, {'langue': 'ar'}):
            resp = self.api.post(
                f'/api/django/crm/relance-etapes/{etape.pk}/langue/',
                corps, format='json')
            self.assertEqual(resp.status_code, 400)
            self.assertIn('langue', resp.data['erreurs'])
        self.lead.refresh_from_db()
        self.assertIsNone(self.lead.langue_preferee)

    def test_la_reponse_ne_parle_que_darija_pose_la_langue(self):
        etape = self._touche()
        resp = self.api.post(
            f'/api/django/crm/relance-etapes/{etape.pk}/fait/',
            {'outcome': 'non_joint', 'langue': 'darija'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.langue_preferee, 'darija')
        self.assertEqual(resp.data['lead_langue'], 'darija')

    def test_un_fait_refuse_ne_change_pas_la_langue(self):
        # Un APPEL clos sans issue est refusé (CKP2) : la langue ne bouge pas.
        etape = self._touche(canal=RelanceEtape.Canal.APPEL,
                             template_cle='appel_ouverture')
        resp = self.api.post(
            f'/api/django/crm/relance-etapes/{etape.pk}/fait/',
            {'langue': 'darija'}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('outcome', resp.data['erreurs'])
        self.lead.refresh_from_db()
        self.assertIsNone(self.lead.langue_preferee)

    def test_une_langue_inconnue_au_fait_est_refusee_avant_tout(self):
        etape = self._touche()
        resp = self.api.post(
            f'/api/django/crm/relance-etapes/{etape.pk}/fait/',
            {'outcome': 'non_joint', 'langue': 'klingon'}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('langue', resp.data['erreurs'])
        etape.refresh_from_db()
        self.assertEqual(etape.statut, RelanceEtape.Statut.A_FAIRE)
