"""QJ-EQUIPE (fondateur 09/09/2026) — les appareils de l'ÉQUIPE ne comptent
jamais comme des lectures client.

Le piège permanent : Reda/Meryem ouvrent le VRAI lien client depuis leur
téléphone (vérifier que « le PDF s'ouvre bien », relire une proposition) →
compteur + note chatter + notification « devis ouvert ». Le marquage
(cookie ``tq_equipe`` posé par la page publique ``/equipe`` ou par toute
ouverture d'un Aperçu interne, traduit en en-tête ``X-Equipe-Appareil: 1``
par le SSR apps/web) rend ces appareils invisibles au suivi : ni stamp, ni
notification, ni beacon d'engagement — exactement le contrat du jeton
interne L-INTPREV, étendu au vrai lien.
"""
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIClient

from apps.crm.models import Client, Lead, LeadActivity
from apps.ventes.models import Devis, ShareLink

UA_CHROME = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
             '(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36')

_PATCH_GEN = patch(
    'apps.ventes.public_views.generate_premium_devis_pdf',
    return_value='devis/1/DEV-QJE-0001.pdf',
)
_PATCH_DL = patch(
    'apps.ventes.public_views.download_pdf',
    return_value=b'%PDF-1.4 stub',
)


class TestAppareilEquipe(TestCase):
    def setUp(self):
        from authentication.models import Company
        self.company = Company.objects.get_or_create(
            slug='qje-co', defaults={'nom': 'QJE Co'})[0]
        self.lead = Lead.objects.create(company=self.company, nom='QJE')
        self.client_obj = Client.objects.get_or_create(
            company=self.company, nom='Client QJE')[0]
        self.devis = Devis.objects.get_or_create(
            company=self.company, reference='DEV-QJE-1',
            defaults={'client': self.client_obj, 'lead': self.lead,
                      'taux_tva': Decimal('20')},
        )[0]
        self.link = ShareLink.objects.create(
            company=self.company, devis=self.devis)

    @_PATCH_GEN
    @_PATCH_DL
    def test_en_tete_equipe_servi_mais_jamais_compte(self, m_dl, m_gen):
        resp = APIClient().get(
            f'/api/django/public/document/{self.link.token}/',
            HTTP_USER_AGENT=UA_CHROME, HTTP_X_EQUIPE_APPAREIL='1')
        self.assertEqual(resp.status_code, 200)
        self.link.refresh_from_db()
        self.assertEqual(self.link.view_count, 0)
        self.assertIsNone(self.link.first_viewed_at)
        # Aucune note chatter, donc aucune notification possible.
        self.assertEqual(
            LeadActivity.objects.filter(lead=self.lead).count(), 0)

    @_PATCH_GEN
    @_PATCH_DL
    def test_cookie_equipe_direct_jamais_compte(self, m_dl, m_gen):
        api = APIClient()
        api.cookies['tq_equipe'] = '1'
        api.get(f'/api/django/public/document/{self.link.token}/',
                HTTP_USER_AGENT=UA_CHROME)
        self.link.refresh_from_db()
        self.assertEqual(self.link.view_count, 0)

    @_PATCH_GEN
    @_PATCH_DL
    def test_sans_marquage_le_client_compte_toujours(self, m_dl, m_gen):
        APIClient().get(
            f'/api/django/public/document/{self.link.token}/',
            HTTP_USER_AGENT=UA_CHROME)
        self.link.refresh_from_db()
        self.assertEqual(self.link.view_count, 1)

    def test_beacon_engagement_equipe_silencieux(self):
        resp = APIClient().post(
            f'/api/django/public/proposal/{self.link.token}/engagement/',
            {'section': 'hero', 'seconds': 30}, format='json',
            HTTP_X_EQUIPE_APPAREIL='1')
        self.assertEqual(resp.status_code, 204)
        self.link.refresh_from_db()
        self.assertIsNone(self.link.engagement)

    def test_beacon_engagement_silencieux_pour_un_appareil_du_registre(self):
        """QJEQUIPE3 — le beacon ne regardait QUE le cookie/l'en-tête
        `tq_equipe` : un appareil marqué dans le registre SERVEUR
        (`crm.AppareilEquipe`) mais sans ce cookie écrivait quand même
        `ShareLink.engagement` et ses notes « a commencé à lire en détail ».
        L'identifiant arrive ici par l'en-tête `X-Appareil-Id` — ce que le
        Worker SSR transmet réellement, d'après le cookie `tq_appareil`."""
        from apps.crm.models import AppareilEquipe

        appareil = 'ffffffff-eeee-4ddd-8ccc-bbbbbbbbbbbb'
        AppareilEquipe.objects.create(
            company=self.company, appareil_id=appareil,
            libelle='Téléphone équipe')
        resp = APIClient().post(
            f'/api/django/public/proposal/{self.link.token}/engagement/',
            {'section': 'hero', 'seconds': 30}, format='json',
            HTTP_X_APPAREIL_ID=appareil)
        self.assertEqual(resp.status_code, 204)
        self.link.refresh_from_db()
        self.assertIsNone(self.link.engagement)

    def test_beacon_engagement_compte_pour_un_appareil_inconnu(self):
        """TÉMOIN — un vrai client garde exactement le comportement d'avant."""
        resp = APIClient().post(
            f'/api/django/public/proposal/{self.link.token}/engagement/',
            {'section': 'hero', 'seconds': 30}, format='json',
            HTTP_X_APPAREIL_ID='00000000-1111-4222-8333-444444444444')
        self.assertEqual(resp.status_code, 204)
        self.link.refresh_from_db()
        self.assertEqual(
            (self.link.engagement or {}).get('hero', {}).get('seconds'), 30)
