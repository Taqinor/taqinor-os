"""QJR417 (DR2, lectures) — les QUATRE lectures publiques passent la garde OTP.

CE QUE LA RONDE A REQUALIFIÉ, ET QU'IL NE FAUT PAS « CORRIGER ». La garde
EXISTE déjà et fonctionne : ``apps.ventes.services.otp_lecture_verified``, posée
dans ``proposal_data`` et ``proposal_pdf`` (deux sites) plus ``proposal_accept``,
**avec l'ordre garde-avant-effet-de-bord déjà correct**. Il n'y avait donc ni
helper à créer, ni ``_stamp_view`` / ``_notify_first_open`` à déplacer.

CE QUI RESTAIT, ET QUI ÉTAIT GRAVE — deux lectures publiques ne consultaient
JAMAIS la garde, avec le MÊME jeton ShareLink :

* ``public_document`` — sert le **PDF CLIENT COMPLET**. C'était la fenêtre
  ouverte à côté de la porte fermée par QJR132/L-NIV : le code d'accès posé sur
  un lien protégeait la page et laissait le document en libre-service.
* ``suivi_public`` — le suivi post-signature (jalons, dates, avancement),
  l'orphelin validé par le critique.

DR2 tranche : **la garde couvre LES 4 LECTURES**. Le QR pointe la page, donc le
parcours client normal passe la garde exactement comme aujourd'hui.
"""
import ast
from decimal import Decimal
from pathlib import Path
from unittest import mock

from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company

from apps.crm.models import Client
from apps.ventes import public_views
from apps.ventes.models import Devis, ShareLink


class _BaseLienProtege(TestCase):
    """Un ShareLink de devis portant ``otp_lecture=True`` (code exigé)."""

    def setUp(self):
        cache.clear()
        self.company = Company.objects.get_or_create(
            slug='qjr417', defaults={'nom': 'QJR417'})[0]
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client QJR417', email='',
            telephone='')
        self.devis = Devis.objects.create(
            company=self.company, reference='DV-QJR417-1',
            client=self.client_obj, statut='envoye',
            taux_tva=Decimal('20'))
        self.link = ShareLink.objects.create(
            company=self.company, devis=self.devis, otp_lecture=True)
        self.anon = APIClient()

    def tearDown(self):
        cache.clear()

    def _deverrouiller(self):
        """Pose le drapeau que ``validate_otp_lecture`` pose après un code
        correct — on exerce la GARDE, pas l'envoi du code."""
        from apps.ventes.services import _otp_lecture_verified_key
        cache.set(_otp_lecture_verified_key(self.link.token), True, 3600)


class PublicDocumentGardeTests(_BaseLienProtege):
    """Lecture n°3 : le PDF client complet."""

    def _url(self):
        from django.urls import reverse
        return reverse('public-document', args=[self.link.token])

    def test_sans_otp_verifie_le_pdf_est_refuse_sans_effet_de_bord(self):
        """ROUGE avant QJR417 : le PDF complet partait, et la vue était
        marquée « ouverte »."""
        with mock.patch.object(
                public_views, '_stamp_view_si_public') as stamp, \
                mock.patch.object(public_views, '_notify_first_open') as notif:
            reponse = self.anon.get(self._url())
        self.assertEqual(reponse.status_code, 403)
        self.assertEqual(reponse.data['detail'], 'otp_required')
        # Aucun effet de bord : ni marquage d'ouverture, ni notification.
        stamp.assert_not_called()
        notif.assert_not_called()

    def test_un_lien_sans_code_est_inchange(self):
        """NO-OP sur les liens d'aujourd'hui : ``otp_lecture`` faux ⇒ la garde
        répond True, rien ne change."""
        self.link.otp_lecture = False
        self.link.save(update_fields=['otp_lecture'])
        with mock.patch.object(
                public_views, 'generate_premium_devis_pdf',
                return_value='cle') as rendu, \
                mock.patch.object(public_views, 'download_pdf',
                                  return_value=b'%PDF-1.4 fake'):
            reponse = self.anon.get(self._url())
        self.assertEqual(reponse.status_code, 200)
        rendu.assert_called_once()

    def test_avec_otp_verifie_le_pdf_est_servi_comme_avant(self):
        self._deverrouiller()
        with mock.patch.object(
                public_views, 'generate_premium_devis_pdf',
                return_value='cle'), \
                mock.patch.object(public_views, 'download_pdf',
                                  return_value=b'%PDF-1.4 fake'):
            reponse = self.anon.get(self._url())
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse['Content-Type'], 'application/pdf')


class SuiviPublicGardeTests(_BaseLienProtege):
    """Lecture n°4 : le suivi post-signature."""

    def _url(self):
        from django.urls import reverse
        return reverse('public-suivi', args=[self.link.token])

    def test_sans_otp_verifie_le_suivi_est_refuse(self):
        """ROUGE avant QJR417 : le suivi partait sans aucun code."""
        with mock.patch(
                'apps.ventes.selectors.devis_milestones') as jalons:
            reponse = self.anon.get(self._url())
        self.assertEqual(reponse.status_code, 403)
        self.assertEqual(reponse.data['detail'], 'otp_required')
        # La garde est posée AVANT la lecture elle-même.
        jalons.assert_not_called()

    def test_avec_otp_verifie_le_suivi_rend_les_memes_octets(self):
        self._deverrouiller()
        attendu = {'jalons': [], 'reference': 'DV-QJR417-1'}
        with mock.patch('apps.ventes.selectors.devis_milestones',
                        return_value=attendu):
            reponse = self.anon.get(self._url())
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse.data, attendu)

    def test_un_lien_sans_code_est_inchange(self):
        self.link.otp_lecture = False
        self.link.save(update_fields=['otp_lecture'])
        with mock.patch('apps.ventes.selectors.devis_milestones',
                        return_value={'jalons': []}):
            reponse = self.anon.get(self._url())
        self.assertEqual(reponse.status_code, 200)


class LesQuatreLecturesTests(TestCase):
    """Troisième test du `Done` : les quatre appellent la MÊME fonction."""

    #: Les quatre lectures publiques du parcours client.
    _LECTURES = ('proposal_data', 'proposal_pdf', 'public_document',
                 'suivi_public')

    @staticmethod
    def _fonctions():
        source = Path(public_views.__file__).read_text(encoding='utf-8')
        arbre = ast.parse(source)
        return {noeud.name: noeud for noeud in ast.walk(arbre)
                if isinstance(noeud, ast.FunctionDef)}

    def test_les_quatre_appellent_la_meme_garde(self):
        fonctions = self._fonctions()
        for nom in self._LECTURES:
            with self.subTest(lecture=nom):
                corps = ast.unparse(fonctions[nom])
                self.assertIn(
                    'otp_lecture_verified', corps,
                    '%s ne consulte pas la garde OTP' % nom)

    def test_aucun_second_helper_de_garde_n_a_ete_cree(self):
        """Règle permanente 2 : une seule formulation dans le dépôt.

        Aucune fonction de garde n'est DÉFINIE ici, et chaque usage vient de
        l'import ``from .services import otp_lecture_verified``."""
        source = Path(public_views.__file__).read_text(encoding='utf-8')
        arbre = ast.parse(source)
        definitions = [
            noeud.name for noeud in ast.walk(arbre)
            if isinstance(noeud, ast.FunctionDef)
            and 'lecture_verified' in noeud.name
        ]
        self.assertEqual(definitions, [])
        origines = {
            noeud.module for noeud in ast.walk(arbre)
            if isinstance(noeud, ast.ImportFrom)
            and any(a.name == 'otp_lecture_verified' for a in noeud.names)
        }
        self.assertEqual(origines, {'services'})

    def test_les_sites_deja_gardes_sont_inchanges(self):
        """``proposal_data`` / ``proposal_pdf`` gardent leur dispense de jeton
        interne, à l'identique."""
        fonctions = self._fonctions()
        for nom in ('proposal_data', 'proposal_pdf'):
            with self.subTest(lecture=nom):
                corps = ast.unparse(fonctions[nom])
                self.assertIn(
                    'if not link.via_interne and '
                    '(not otp_lecture_verified(link)):', corps)
