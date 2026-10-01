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


class _StockageMemoire:
    """Bouchon MinIO en mémoire (put_object / get_object) : suit les écritures
    clé par clé sans conteneur."""

    def __init__(self):
        self.objets = {}

    def put_object(self, Bucket, Key, Body, ContentType=None):  # noqa: N803
        self.objets[Key] = bytes(Body)

    def get_object(self, Bucket, Key):  # noqa: N803
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
