"""QJR670 — le PDF public d'un devis ACCEPTÉ sert l'exemplaire SIGNÉ figé.

La vue publique re-rendait TOUJOURS le devis à la volée, y compris un
ACCEPTÉ : une évolution du moteur, d'une fiche produit ou de la société
changeait le document que le client avait SIGNÉ. Désormais : accepté +
``DevisSignature.signed_pdf_key`` → ces octets ; sinon re-rendu inchangé.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.ventes.tests.test_pdf_public_accepte_signe"
"""
import io
import uuid
from unittest.mock import patch

from django.test import Client as DjangoClient, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.stock.models import Produit
from apps.ventes.models import Devis, DevisSignature, ShareLink

from .test_l_niv_niveau import make_client, make_company, make_devis, make_user

CLE_SIGNEE = 'devis/signe/QJR670.pdf'
OCTETS_SIGNES = b'%PDF-exemplaire-signe'
OCTETS_RERENDU = b'%PDF-rerendu-du-jour'


def _telecharger(cle):
    return OCTETS_SIGNES if cle == CLE_SIGNEE else OCTETS_RERENDU


class TestPdfPublicAccepteSigne(TestCase):

    def setUp(self):
        self.company = make_company('test-qjr670-co')
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)

    def _devis(self, ref, statut, cle=None):
        devis = make_devis(self.company, self.user, self.client_obj, ref)
        Devis.objects.filter(pk=devis.pk).update(statut=statut)
        devis.refresh_from_db()
        if statut == 'accepte':
            DevisSignature.objects.create(
                company=self.company, devis=devis, signataire_nom='Client',
                consentement_explicite=True, signed_at=timezone.now(),
                signed_pdf_key=cle)
        link = ShareLink.objects.create(
            company=self.company, devis=devis, token=str(uuid.uuid4()),
            niveau=ShareLink.NIVEAU_CONFIANCE)
        return devis, link

    def _get(self, url, link, mock_gen):
        resp = DjangoClient().get(reverse(url, args=[link.token]))
        self.assertEqual(resp.status_code, 200)
        return b''.join(resp) if hasattr(resp, 'streaming_content') \
            else resp.content

    @patch('apps.ventes.public_views.download_pdf', side_effect=_telecharger)
    @patch('apps.ventes.public_views.generate_premium_devis_pdf',
           return_value='devis/rerendu.pdf')
    def test_accepte_avec_cle_sert_les_octets_signes(self, mock_gen, _dl):
        devis, link = self._devis('DEV-QJR670-A', 'accepte', CLE_SIGNEE)
        # Une fiche produit évolue APRÈS la signature.
        Produit.objects.filter(company=self.company).update(
            description='Nouvelle fiche produit après signature')
        for url in ('public-proposal-pdf', 'public-document'):
            contenu = self._get(url, link, mock_gen)
            self.assertEqual(contenu, OCTETS_SIGNES, url)
        mock_gen.assert_not_called()
        devis.refresh_from_db()
        self.assertEqual(devis.statut, 'accepte')

    @patch('apps.ventes.public_views.download_pdf', side_effect=_telecharger)
    @patch('apps.ventes.public_views.generate_premium_devis_pdf',
           return_value='devis/rerendu.pdf')
    def test_envoye_re_rendu(self, mock_gen, _dl):
        _, link = self._devis('DEV-QJR670-B', 'envoye')
        contenu = self._get('public-proposal-pdf', link, mock_gen)
        self.assertEqual(contenu, OCTETS_RERENDU)
        self.assertTrue(mock_gen.called)

    @patch('apps.ventes.public_views.download_pdf', side_effect=_telecharger)
    @patch('apps.ventes.public_views.generate_premium_devis_pdf',
           return_value='devis/rerendu.pdf')
    def test_accepte_sans_cle_re_rendu(self, mock_gen, _dl):
        _, link = self._devis('DEV-QJR670-C', 'accepte', None)
        contenu = self._get('public-proposal-pdf', link, mock_gen)
        self.assertEqual(contenu, OCTETS_RERENDU)
        self.assertTrue(mock_gen.called)

    # ── L'exemplaire signé suit la règle du LIEN (revue du 24/10/2026) ────

    @staticmethod
    def _deverrouiller(link):
        from django.core.cache import cache
        from apps.ventes.domain.cycle_vie import _otp_lecture_verified_key
        cache.set(_otp_lecture_verified_key(link.token), True, 3600)

    def _demander(self, link):
        return DjangoClient().post(
            f'/api/django/public/proposal/{link.token}/otp-lecture/demander/')

    @patch('apps.ventes.public_views.download_pdf', side_effect=_telecharger)
    @patch('apps.ventes.public_views.generate_premium_devis_pdf',
           return_value='devis/rerendu.pdf')
    def test_exemplaire_signe_suit_la_regle_du_lien(self, mock_gen, _dl):
        """Lien SANS code : l'exemplaire signé part au jeton (client joignable
        ou non), aucun code demandé. Lien SOUS code : 403 ``otp_required``
        jusqu'au code, puis les octets signés."""
        from django.core.cache import cache
        from apps.ventes.domain.cycle_vie import _otp_lecture_cache_key
        _, link = self._devis('DEV-ADEV97-A', 'accepte', CLE_SIGNEE)
        for url in ('public-proposal-pdf', 'public-document'):
            self.assertEqual(self._get(url, link, mock_gen), OCTETS_SIGNES, url)
        self.assertEqual(self._demander(link).json().get('code_requis'), False)
        link.otp_lecture = True
        link.save(update_fields=['otp_lecture'])
        for url in ('public-proposal-pdf', 'public-document'):
            resp = DjangoClient().get(reverse(url, args=[link.token]))
            self.assertEqual(resp.status_code, 403, url)
            self.assertEqual(resp.json()['detail'], 'otp_required')
        with patch('apps.ventes.domain.cycle_vie._send_otp_email',
                   return_value=True) as envoi:
            resp = self._demander(link)
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertTrue(envoi.called)
        self.assertIsNotNone(cache.get(_otp_lecture_cache_key(link.token)))
        self._deverrouiller(link)
        self.assertEqual(self._get('public-proposal-pdf', link, mock_gen),
                         OCTETS_SIGNES)
        # Déjà déverrouillé : aucun second code.
        self.assertEqual(self._demander(link).json().get('code_requis'), False)

    @patch('apps.ventes.public_views.download_pdf', side_effect=_telecharger)
    @patch('apps.ventes.public_views.generate_premium_devis_pdf',
           return_value='devis/rerendu.pdf')
    def test_sans_canal_le_pdf_signe_reste_servi(self, mock_gen, _dl):
        """Aucun code ne peut partir (client sans e-mail) : inchangé, jamais
        un exemplaire rendu illisible."""
        self.client_obj.email = ''
        self.client_obj.save(update_fields=['email'])
        _, link = self._devis('DEV-ADEV97-B', 'accepte', CLE_SIGNEE)
        self.assertEqual(self._get('public-proposal-pdf', link, mock_gen),
                         OCTETS_SIGNES)
        self.assertEqual(self._demander(link).json().get('code_requis'), False)

    # ── ADEV105 (C-L3-LIEN-11) — l'exemplaire signé n'est pas une lecture ──

    @patch('apps.crm.services.notify_devis_opened')
    @patch('apps.ventes.public.lecture_views._notify_first_open')
    @patch('apps.ventes.public_views.download_pdf', side_effect=_telecharger)
    @patch('apps.ventes.public_views.generate_premium_devis_pdf',
           return_value='devis/rerendu.pdf')
    def test_telecharger_l_exemplaire_signe_ne_compte_aucune_ouverture(
            self, mock_gen, _dl, premiere, reouverture):
        """Devis ACCEPTÉ : le signataire télécharge son exemplaire signé
        (écran de succès, e-mail) — ``view_count`` et les dates de lecture
        inchangés, aucune note « devis ouvert », aucune notification, même
        après la fenêtre de réouverture."""
        from datetime import timedelta
        _, link = self._devis('DEV-ADEV105-A', 'accepte', CLE_SIGNEE)
        avant = timezone.now() - timedelta(days=2)
        ShareLink.objects.filter(pk=link.pk).update(
            view_count=3, first_viewed_at=avant, last_viewed_at=avant)
        for _ in range(2):
            self.assertEqual(self._get('public-proposal-pdf', link, mock_gen),
                             OCTETS_SIGNES)
        link.refresh_from_db()
        self.assertEqual((link.view_count, link.first_viewed_at,
                          link.last_viewed_at), (3, avant, avant))
        premiere.assert_not_called()
        reouverture.assert_not_called()

    @patch('apps.ventes.public.lecture_views._notify_first_open')
    @patch('apps.ventes.public_views.download_pdf', side_effect=_telecharger)
    @patch('apps.ventes.public_views.generate_premium_devis_pdf',
           return_value='devis/rerendu.pdf')
    def test_pdf_d_un_envoye_compte_toujours_la_premiere_lecture(
            self, mock_gen, _dl, premiere):
        """Test-du-test : devis ENVOYÉ non accepté — le comptage d'avant
        (première ouverture comptée et notifiée) est inchangé."""
        _, link = self._devis('DEV-ADEV105-B', 'envoye')
        self.assertEqual(self._get('public-proposal-pdf', link, mock_gen),
                         OCTETS_RERENDU)
        link.refresh_from_db()
        self.assertEqual(link.view_count, 1)
        self.assertIsNotNone(link.first_viewed_at)
        premiere.assert_called_once()

    def test_envoye_aucun_code_requis(self):
        _, link = self._devis('DEV-ADEV97-C', 'envoye')
        resp = self._demander(link)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {
            'detail': 'Aucun code requis pour ce lien.', 'code_requis': False})


class _StockageMemoire:
    """Bouchon MinIO en mémoire (put_object / get_object) : suit les écritures
    clé par clé sans conteneur."""

    def __init__(self):
        self.objets = {}

    def put_object(self, Bucket, Key, Body, ContentType=None):
        self.objets[Key] = bytes(Body)

    def get_object(self, Bucket, Key):
        return {'Body': io.BytesIO(self.objets[Key])}


class TestExemplaireSigneCleDediee(TestCase):
    """QJR670 suivi — l'exemplaire signé vit sous SA PROPRE clé MinIO.

    Avant : ``signed_pdf_key`` valait la clé fixe du PDF interne
    (``devis/<co>/<ref>.pdf``) ; tout re-rendu interne persistant écrasait
    donc la copie « signée ». Désormais les octets sont copiés, à
    l'acceptation, sous ``…__signe.pdf``, clé qu'aucun rendu n'écrit."""

    def setUp(self):
        self.company = make_company('test-qjr670-cle-co')
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        self.stock = _StockageMemoire()
        patcher = patch('apps.ventes.utils.pdf.get_minio_client',
                        return_value=self.stock)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _faux_moteur(self, octets):
        def rendre(devis_id, options=None, persist=True):
            devis = Devis.objects.get(pk=devis_id)
            cle = f'devis/{devis.company_id}/{devis.reference}.pdf'
            self.stock.put_object(Bucket='pdf', Key=cle, Body=octets)
            return cle
        return rendre

    def test_re_rendu_persistant_laisse_les_octets_signes_intacts(self):
        from apps.ventes.domain.cycle_vie import _store_signed_pdf
        devis = make_devis(self.company, self.user, self.client_obj,
                           'DEV-QJR670-D')
        Devis.objects.filter(pk=devis.pk).update(statut='accepte')
        devis.refresh_from_db()
        sig = DevisSignature.objects.create(
            company=self.company, devis=devis, signataire_nom='Client',
            consentement_explicite=True, signed_at=timezone.now())
        cle_interne = f'devis/{devis.company_id}/{devis.reference}.pdf'

        with patch('apps.ventes.quote_engine.generate_premium_devis_pdf',
                   side_effect=self._faux_moteur(b'%PDF-signe-v1')):
            _store_signed_pdf(devis=devis)
        sig.refresh_from_db()
        self.assertNotEqual(sig.signed_pdf_key, cle_interne)
        self.assertTrue(sig.signed_pdf_key.endswith('__signe.pdf'))

        # Re-rendu interne ultérieur, persisté, sur la clé fixe.
        self._faux_moteur(b'%PDF-rerendu-v2')(devis.pk, {}, persist=True)
        self.assertEqual(self.stock.objets[cle_interne], b'%PDF-rerendu-v2')
        self.assertEqual(self.stock.objets[sig.signed_pdf_key],
                         b'%PDF-signe-v1')

        link = ShareLink.objects.create(
            company=self.company, devis=devis, token=str(uuid.uuid4()),
            niveau=ShareLink.NIVEAU_CONFIANCE)
        with patch('apps.ventes.public_views.generate_premium_devis_pdf') \
                as mock_gen:
            resp = DjangoClient().get(
                reverse('public-proposal-pdf', args=[link.token]))
        self.assertEqual(resp.status_code, 200)
        contenu = b''.join(resp) if hasattr(resp, 'streaming_content') \
            else resp.content
        self.assertEqual(contenu, b'%PDF-signe-v1')
        mock_gen.assert_not_called()

    def test_aucune_cle_de_rendu_ne_vise_le_suffixe_signe(self):
        from apps.ventes.quote_engine.builder import VARIANTES_PDF, _pdf_key
        devis = make_devis(self.company, self.user, self.client_obj,
                           'DEV-QJR670-E')
        for filigrane in (False, True):
            for variante in (None, *VARIANTES_PDF):
                cle = _pdf_key(devis, watermark=filigrane, variante=variante)
                self.assertNotIn('__signe', cle)


class TestAvenantSigneParLeClient(TestCase):
    """VNT61 — un avenant (V2 acceptée en interne d'une vente signée) se
    signe par le lien public : UNE DevisSignature, statut inchangé, aucun
    ``devis_accepted``, aucun CAPI, aucun webhook ; 2e soumission ⇒ rien."""

    def setUp(self):
        self.company = make_company('test-vnt61-co')
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        self.v2 = make_devis(self.company, self.user, self.client_obj,
                             'DEV-VNT61-20')
        v1 = make_devis(self.company, self.user, self.client_obj,
                        'DEV-VNT61-10')
        Devis.objects.filter(pk=v1.pk).update(
            statut='accepte', is_active=False, superseded_by=self.v2)
        Devis.objects.filter(pk=self.v2.pk).update(statut='accepte')
        self.v2.refresh_from_db()
        self.link = ShareLink.objects.create(
            company=self.company, devis=self.v2, token=str(uuid.uuid4()),
            niveau=ShareLink.NIVEAU_CONFIANCE)

    def _signer(self):
        from apps.ventes.public.signature_views import empreinte_contenu
        return DjangoClient().post(
            f'/api/django/public/proposal/{self.link.token}/accept/',
            {'nom': 'Client Avenant', 'consent_esign': True,
             'empreinte_contenu': empreinte_contenu(self.v2)},
            content_type='application/json')

    @patch('apps.publicapi.signals.delivery.dispatch_event')
    @patch('apps.ventes.domain.cycle_vie._fire_capi_signed_quote')
    @patch('apps.ventes.domain.cycle_vie._store_signed_pdf')
    def test_signature_seule_sans_statut_ni_evenement(
            self, store_pdf, capi, webhook):
        from core.events import devis_accepted
        evenements = []

        def _ecoute(sender, **kwargs):
            evenements.append(kwargs.get('devis'))

        devis_accepted.connect(_ecoute, dispatch_uid='vnt61', weak=False)
        self.addCleanup(devis_accepted.disconnect, dispatch_uid='vnt61')

        r = self._signer()
        self.assertEqual(r.status_code, 200, r.content)
        self.assertIn('avenant_signe', r.json())
        self.assertEqual(
            DevisSignature.objects.filter(devis=self.v2).count(), 1)
        store_pdf.assert_called_once()
        self.v2.refresh_from_db()
        self.assertEqual(self.v2.statut, 'accepte')

        r = self._signer()  # 2e soumission : rien n'est écrit.
        self.assertEqual(r.status_code, 200, r.content)
        self.assertNotIn('avenant_signe', r.json())
        self.assertEqual(
            DevisSignature.objects.filter(devis=self.v2).count(), 1)
        store_pdf.assert_called_once()
        self.assertEqual(evenements, [])
        capi.assert_not_called()
        webhook.assert_not_called()

    @patch('apps.ventes.domain.cycle_vie._store_signed_pdf')
    def test_proposal_data_sert_le_bloc_avenant(self, _store_pdf):
        """VNT61 — la page publique lit ``avenant`` : à signer, puis signé
        (``signe_le`` daté) — contrat ``proposal_data.json`` › ``notes_vnt2``."""
        url = f'/api/django/public/proposal/{self.link.token}/data/'
        r = DjangoClient().get(url)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()['avenant'], {
            'a_signer': True, 'remplace': {'reference': 'DEV-VNT61-10'},
            'signe_le': None})
        self.assertEqual(self._signer().status_code, 200)
        avenant = DjangoClient().get(url).json()['avenant']
        self.assertIs(avenant['a_signer'], False)
        signature = DevisSignature.objects.get(devis=self.v2)
        self.assertEqual(avenant['signe_le'], signature.signed_at.isoformat())

    def test_avenant_public_absent_hors_avenant(self):
        """Clé ABSENTE (``None``) hors avenant : la version remplacée, et une
        V2 acceptée dont la version précédente n'a jamais été vendue."""
        from apps.ventes.domain.negociation import avenant_public
        v1 = Devis.objects.get(reference='DEV-VNT61-10')
        self.assertIsNone(avenant_public(v1))
        Devis.objects.filter(pk=v1.pk).update(statut='refuse')
        self.v2.refresh_from_db()
        self.assertIsNone(avenant_public(self.v2))
