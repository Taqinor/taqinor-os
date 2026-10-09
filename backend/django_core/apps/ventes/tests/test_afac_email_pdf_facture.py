"""AFAC42 — tout e-mail de FACTURE (envoi unitaire, envoi groupé, relance avec
PDF) joint le PDF GARANTI à jour par ``cle_facture_pdf_a_jour`` ; quand ce PDF
promis « ci-joint » ne peut pas être produit, l'envoi est REFUSÉ (EmailLog
``echec``, erreur « PDF indisponible », aucun message).

Comportemental : APIClient, backend e-mail locmem, rendu WeasyPrint RÉEL du
gabarit facture ; seule l'I/O MinIO est simulée (un dict en mémoire), et rendue
défaillante pour le dernier cas.

Run :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_afac_email_pdf_facture -v 2
"""
from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import EmailLog, Facture, LigneFacture, Paiement

User = get_user_model()

LOCMEM = 'django.core.mail.backends.locmem.EmailBackend'


def _texte_pdf(pdf_bytes):
    import fitz
    doc = fitz.open(stream=pdf_bytes, filetype='pdf')
    try:
        return '\n'.join(page.get_text() for page in doc)
    finally:
        doc.close()


class _MinioMemoire:
    """Double de la seule frontière I/O : le bucket MinIO."""

    def __init__(self, panne=False):
        self.objets = {}
        self.panne = panne

    def upload(self, pdf_bytes, key):
        if self.panne:
            raise ConnectionError('stockage indisponible')
        self.objets[key] = pdf_bytes

    def download(self, key):
        if self.panne:
            raise ConnectionError('stockage indisponible')
        return self.objets[key]


@override_settings(EMAIL_BACKEND=LOCMEM)
class EmailPdfFactureTests(TestCase):
    def setUp(self):
        from authentication.models import Company
        self.company = Company.objects.create(nom='AFAC42 Co', slug='afac42-co')
        self.user = User.objects.create_user(
            username='afac42-resp', password='x', role_legacy='responsable',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Alaoui', prenom='Karim',
            email='karim.afac42@example.ma', telephone='+212600004200')
        self.produit = Produit.objects.create(
            company=self.company, nom='Kit PV', sku='AFAC42-KIT',
            prix_vente=Decimal('1000'))
        # 1 000 HT × 20 % = 1 200 TTC.
        self.facture = self._facture('FAC-AFAC42-0001')
        self.minio = _MinioMemoire()
        p_up = patch('apps.ventes.utils.pdf._upload_pdf',
                     side_effect=lambda b, k: self.minio.upload(b, k))
        p_dl = patch('apps.ventes.utils.pdf.download_pdf',
                     side_effect=lambda k: self.minio.download(k))
        p_up.start()
        p_dl.start()
        self.addCleanup(p_up.stop)
        self.addCleanup(p_dl.stop)
        self.api = APIClient()
        self.api.force_authenticate(self.user)

    def _facture(self, reference):
        facture = Facture.objects.create(
            company=self.company, reference=reference,
            client=self.client_obj, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20.00'))
        LigneFacture.objects.create(
            facture=facture, produit=self.produit, designation='Kit PV',
            quantite=Decimal('1'), prix_unitaire=Decimal('1000'),
            taux_tva=Decimal('20.00'))
        return facture

    def _payer(self, montant, jour):
        Paiement.objects.create(
            company=self.company, facture=self.facture,
            montant=Decimal(montant), date_paiement=jour,
            mode=Paiement.Mode.VIREMENT, statut=Paiement.Statut.ENCAISSE)

    def _rendre_puis_encaisser(self):
        """« Générer PDF » après un paiement de 300, puis encaisser 500 :
        le fichier stocké imprime encore « Reste à payer 900.00 »."""
        from apps.ventes.utils.pdf import cle_facture_pdf_a_jour
        self._payer('300', date(2026, 9, 1))
        cle = cle_facture_pdf_a_jour(self.facture)
        self.assertIn('900.00', _texte_pdf(self.minio.objets[cle]))
        self._payer('500', date(2026, 9, 15))
        self.facture.refresh_from_db()
        self.assertEqual(self.facture.montant_du, Decimal('400.00'))

    def _pj_texte(self, message):
        self.assertEqual(len(message.attachments), 1)
        nom, contenu, mime = message.attachments[0]
        self.assertEqual(nom, f'{self.facture.reference}.pdf')
        self.assertEqual(mime, 'application/pdf')
        return _texte_pdf(contenu)

    def test_envoyer_email_pj_reste_courant(self):
        self._rendre_puis_encaisser()
        resp = self.api.post(
            f'/api/django/ventes/factures/{self.facture.id}/envoyer-email/',
            {}, format='json')
        self.assertEqual(resp.status_code, 202, resp.data)
        self.assertEqual(len(mail.outbox), 1)
        texte = self._pj_texte(mail.outbox[0])
        self.assertIn('Reste à payer', texte)
        self.assertIn('400.00', texte)
        self.assertNotIn('900.00', texte)
        log = EmailLog.objects.get(pk=resp.data['email_log_id'])
        self.assertEqual(log.statut, EmailLog.Statut.ENVOYE)
        self.assertEqual(log.piece_jointe, f'{self.facture.reference}.pdf')

    def test_bulk_envoyer_email_pj_reste_courant(self):
        self._rendre_puis_encaisser()
        resp = self.api.post(
            '/api/django/ventes/factures/bulk/',
            {'action': 'envoyer-email', 'ids': [self.facture.id]},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(resp.json()[str(self.facture.id)]['ok'])
        self.assertEqual(len(mail.outbox), 1)
        texte = self._pj_texte(mail.outbox[0])
        self.assertIn('400.00', texte)
        self.assertNotIn('900.00', texte)

    def test_relance_avec_pdf_pj_reste_courant(self):
        from apps.ventes.email_service import send_relance_email
        self._rendre_puis_encaisser()
        log = send_relance_email(self.facture, user=self.user, attach_pdf=True)
        log.refresh_from_db()
        self.assertEqual(log.statut, EmailLog.Statut.ENVOYE)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('400.00', self._pj_texte(mail.outbox[0]))

    def test_facture_jamais_rendue_part_avec_pj(self):
        self.assertFalse(self.facture.fichier_pdf)
        resp = self.api.post(
            f'/api/django/ventes/factures/{self.facture.id}/envoyer-email/',
            {}, format='json')
        self.assertEqual(resp.status_code, 202, resp.data)
        log = EmailLog.objects.get(pk=resp.data['email_log_id'])
        self.assertEqual(log.statut, EmailLog.Statut.ENVOYE)
        self.assertEqual(log.piece_jointe, f'{self.facture.reference}.pdf')
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(self.facture.reference, self._pj_texte(mail.outbox[0]))

    def test_pdf_impossible_refuse_envoi(self):
        from apps.ventes.email_service import send_relance_email
        self.minio.panne = True
        resp = self.api.post(
            f'/api/django/ventes/factures/{self.facture.id}/envoyer-email/',
            {}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('PDF indisponible', resp.data['detail'])
        log = EmailLog.objects.get(pk=resp.data['email_log_id'])
        self.assertEqual(log.statut, EmailLog.Statut.ECHEC)
        self.assertIn('PDF indisponible', log.erreur)
        self.assertEqual(log.piece_jointe, '')

        bulk = self.api.post(
            '/api/django/ventes/factures/bulk/',
            {'action': 'envoyer-email', 'ids': [self.facture.id]},
            format='json')
        self.assertEqual(bulk.status_code, 200, bulk.data)
        entree = bulk.json()[str(self.facture.id)]
        self.assertFalse(entree['ok'])
        self.assertIn('PDF indisponible', entree['detail'])

        relance = send_relance_email(
            self.facture, user=self.user, attach_pdf=True)
        relance.refresh_from_db()
        self.assertEqual(relance.statut, EmailLog.Statut.ECHEC)
        self.assertIn('PDF indisponible', relance.erreur)
        self.assertEqual(len(mail.outbox), 0)

    def test_relance_sans_pdf_inchangee(self):
        """Le beat de relance (``attach_pdf`` False par défaut) n'est pas
        concerné : il part sans pièce jointe, même stockage en panne."""
        from apps.ventes.email_service import send_relance_email
        self.minio.panne = True
        log = send_relance_email(self.facture, user=self.user)
        self.assertEqual(log.statut, EmailLog.Statut.ENVOYE)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].attachments, [])
