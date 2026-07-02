"""QS3 — Envois WhatsApp + email d'un Bon de Commande FOURNISSEUR (stock).

Couvre :
  * WhatsApp : lien wa.me + lien tokenisé (public/bcf) + message FR, marque
    ENVOYE (idempotent, ne régresse jamais RECU/ANNULE) ;
  * Email : PDF joint + EmailLog écrit (NO-OP réseau backend console), marque
    ENVOYE ;
  * contact manquant → 400 sans changer le statut ;
  * permission stock_modifier requise ;
  * endpoint public tokenisé : sert le PDF, jeton invalide/expiré → 404, aucune
    fuite (le lien n'est jamais surfacé côté client) ;
  * ShareLink pour BCF : réutilisé tant que valide, borné à la société.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role
from apps.stock.models import (
    BonCommandeFournisseur, Fournisseur, LigneBonCommandeFournisseur, Produit,
)
from apps.ventes.models import EmailLog, ShareLink

User = get_user_model()


def _company(slug):
    return Company.objects.create(nom=slug, slug=slug)


def _user(company, username, permissions=None):
    role = None
    if permissions is not None:
        role = Role.objects.create(
            company=company, nom=f'r-{username}', permissions=permissions)
    return User.objects.create_user(
        username=username, password='x', company=company, role=role,
        role_legacy='responsable')


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class BcfSendBase(TestCase):
    def setUp(self):
        self.company = _company('qs3-co')
        self.user = _user(self.company, 'qs3-user',
                          permissions=['stock_modifier', 'stock_voir'])
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Solar Wholesale',
            telephone='0612345678', email='fournisseur@exemple.ma')
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau', sku='PV-1',
            prix_vente=Decimal('1000'), prix_achat=Decimal('600'))
        self.bcf = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-QS3-0001',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.BROUILLON)
        LigneBonCommandeFournisseur.objects.create(
            bon_commande=self.bcf, produit=self.produit,
            quantite=10, prix_achat_unitaire=Decimal('600'))
        self.api = _api(self.user)

    def _post(self, path, api=None, body=None):
        return (api or self.api).post(
            f'/api/django/stock/bons-commande-fournisseur/{self.bcf.id}/{path}/',
            body or {}, format='json')


class BcfWhatsappTests(BcfSendBase):
    def test_whatsapp_builds_link_and_marks_envoye(self):
        resp = self._post('whatsapp')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('wa.me/212612345678', resp.data['wa_url'])
        self.assertIn('/public/bcf/', resp.data['url'])
        self.assertIn('BCF-QS3-0001', resp.data['message'])
        self.bcf.refresh_from_db()
        self.assertEqual(self.bcf.statut,
                         BonCommandeFournisseur.Statut.ENVOYE)
        self.assertTrue(ShareLink.objects.filter(
            bon_commande_fournisseur=self.bcf).exists())

    def test_whatsapp_idempotent_no_regression_recu(self):
        self.bcf.statut = BonCommandeFournisseur.Statut.RECU
        self.bcf.save(update_fields=['statut'])
        self._post('whatsapp')
        self.bcf.refresh_from_db()
        self.assertEqual(self.bcf.statut, BonCommandeFournisseur.Statut.RECU)

    def test_whatsapp_no_regression_annule(self):
        self.bcf.statut = BonCommandeFournisseur.Statut.ANNULE
        self.bcf.save(update_fields=['statut'])
        self._post('whatsapp')
        self.bcf.refresh_from_db()
        self.assertEqual(self.bcf.statut, BonCommandeFournisseur.Statut.ANNULE)

    def test_whatsapp_no_phone_400_keeps_status(self):
        self.fournisseur.telephone = ''
        self.fournisseur.save(update_fields=['telephone'])
        resp = self._post('whatsapp')
        self.assertEqual(resp.status_code, 400)
        self.bcf.refresh_from_db()
        self.assertEqual(self.bcf.statut,
                         BonCommandeFournisseur.Statut.BROUILLON)

    def test_permission_required(self):
        weak = _user(self.company, 'qs3-weak', permissions=['stock_voir'])
        resp = self._post('whatsapp', api=_api(weak))
        self.assertEqual(resp.status_code, 403)


class BcfEmailTests(BcfSendBase):
    def test_email_sends_and_logs_and_marks_envoye(self):
        resp = self._post('envoyer-email')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['email_statut'], EmailLog.Statut.ENVOYE)
        log = EmailLog.objects.get(id=resp.data['log_id'])
        self.assertEqual(log.company, self.company)
        self.assertEqual(log.to_email, 'fournisseur@exemple.ma')
        self.assertEqual(log.reference, 'BCF-QS3-0001')
        self.assertTrue(log.piece_jointe)  # PDF joint
        self.bcf.refresh_from_db()
        self.assertEqual(self.bcf.statut,
                         BonCommandeFournisseur.Statut.ENVOYE)

    def test_email_no_address_400_keeps_status(self):
        self.fournisseur.email = ''
        self.fournisseur.save(update_fields=['email'])
        resp = self._post('envoyer-email')
        self.assertEqual(resp.status_code, 400)
        self.bcf.refresh_from_db()
        self.assertEqual(self.bcf.statut,
                         BonCommandeFournisseur.Statut.BROUILLON)

    def test_email_no_regression_recu(self):
        self.bcf.statut = BonCommandeFournisseur.Statut.RECU
        self.bcf.save(update_fields=['statut'])
        self._post('envoyer-email')
        self.bcf.refresh_from_db()
        self.assertEqual(self.bcf.statut, BonCommandeFournisseur.Statut.RECU)


class BcfPublicPdfTests(BcfSendBase):
    def test_public_token_serves_pdf(self):
        link = ShareLink.for_bon_commande_fournisseur(self.bcf)
        public = APIClient()
        resp = public.get(f'/api/django/public/bcf/{link.token}/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')
        self.assertIn('noindex', resp['X-Robots-Tag'])

    def test_invalid_token_404(self):
        public = APIClient()
        resp = public.get('/api/django/public/bcf/pas-un-jeton/')
        self.assertEqual(resp.status_code, 404)

    def test_expired_token_404(self):
        link = ShareLink.for_bon_commande_fournisseur(self.bcf)
        link.expires_at = timezone.now()
        link.save(update_fields=['expires_at'])
        public = APIClient()
        resp = public.get(f'/api/django/public/bcf/{link.token}/')
        self.assertEqual(resp.status_code, 404)

    def test_devis_token_not_served_as_bcf(self):
        # Un jeton NON-BCF (devis/facture) ne sert jamais un BCF.
        from apps.ventes.models import ShareLink as SL
        other = SL.objects.create(company=self.company)  # ni devis ni bcf
        public = APIClient()
        resp = public.get(f'/api/django/public/bcf/{other.token}/')
        self.assertEqual(resp.status_code, 404)


class ShareLinkForBcfTests(BcfSendBase):
    def test_reuses_valid_link(self):
        l1 = ShareLink.for_bon_commande_fournisseur(self.bcf)
        l2 = ShareLink.for_bon_commande_fournisseur(self.bcf)
        self.assertEqual(l1.pk, l2.pk)
        self.assertEqual(l1.company, self.company)

    def test_company_scoped_and_token_unguessable(self):
        link = ShareLink.for_bon_commande_fournisseur(self.bcf)
        self.assertEqual(link.company, self.company)
        self.assertGreaterEqual(len(link.token), 32)
        self.assertTrue(link.is_valid)
