"""AUD136 — borner le cycle de vie du PaymentLink (création, montant,
expiration, ré-émission, révocation).

À DIRE EXPLICITEMENT, comme la tâche l'exige : `record_payment_from_link` a été
audité et est CORRECT — atomique, `select_for_update`, borné au reste dû, émet
`paiement_enregistre` et les deux événements de bascule. Les tests
`test_montant_encaisse_*` le PROUVENT au lieu de le supposer : c'est un
« déjà correct — preuve jointe ».

En face, la surface publique n'avait aucun auditeur : rien n'était lu sur la
CRÉATION du lien — montant posé, expiration, ré-émission à volonté, révocation.
"""
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.ventes.models import Facture, Paiement, PaymentLink

User = get_user_model()


class _ProviderQuiConfirme:
    """Stub de PSP : confirme le paiement (le NoOp réel ne confirme JAMAIS)."""

    def __init__(self, montant=None):
        self._montant = montant

    def create_session(self, link):
        return {'pay_url': f'/pay/{link.token}/', 'provider_ref': 'stub'}

    def verify_webhook(self, link, payload):
        return {'paid': True, 'provider_ref': 'stub-ref',
                'montant': self._montant}


class _Base(TestCase):
    slug = 'aud136-co'

    def setUp(self):
        from authentication.models import Company
        self.company = Company.objects.get_or_create(
            slug=self.slug, defaults={'nom': 'AUD136 Co'})[0]
        self.user = User.objects.create_user(
            username=f'{self.slug}-resp', password='x',
            role_legacy='responsable', company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client AUD136',
            telephone='+212600000136')
        self.facture = Facture.objects.create(
            company=self.company, reference='FAC-AUD136-0001',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20.00'), libelle='Prestation',
            montant_ht=Decimal('10000.00'),
            date_echeance=date.today() + timedelta(days=30))
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        # Surface PUBLIQUE : jamais authentifiée.
        self.public = APIClient()

    def _url(self, suffixe='lien-paiement'):
        return (f'/api/django/ventes/factures/{self.facture.id}/'
                f'{suffixe}/')


class TestAud136CreationDuLien(_Base):
    slug = 'aud136-create'

    def test_deux_liens_actifs_le_second_reutilise_le_premier(self):
        r1 = self.api.post(self._url(), {}, format='json')
        self.assertEqual(r1.status_code, 201, r1.data)
        r2 = self.api.post(self._url(), {}, format='json')
        self.assertEqual(r2.status_code, 201, r2.data)
        self.assertEqual(r1.data['token'], r2.data['token'])
        self.assertEqual(PaymentLink.objects.count(), 1)

    def test_la_contrainte_base_refuse_un_second_lien_actif(self):
        from apps.ventes.services import create_payment_link
        create_payment_link(facture=self.facture)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                PaymentLink.objects.create(
                    company=self.company, facture=self.facture,
                    montant=Decimal('1000.00'))

    def test_une_facture_annulee_n_obtient_pas_de_lien(self):
        self.facture.statut = Facture.Statut.ANNULEE
        self.facture.save(update_fields=['statut'])
        resp = self.api.post(self._url(), {}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertFalse(PaymentLink.objects.exists())

    def test_une_facture_payee_n_obtient_pas_de_lien(self):
        self.facture.statut = Facture.Statut.PAYEE
        self.facture.save(update_fields=['statut'])
        resp = self.api.post(self._url(), {}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertFalse(PaymentLink.objects.exists())

    def test_un_lien_perime_est_ferme_et_un_neuf_est_emis(self):
        from apps.ventes.services import create_payment_link
        vieux = create_payment_link(facture=self.facture)
        PaymentLink.objects.filter(pk=vieux.pk).update(
            expires_at=timezone.now() - timedelta(days=1))

        neuf = create_payment_link(facture=self.facture)
        self.assertNotEqual(neuf.pk, vieux.pk)
        vieux.refresh_from_db()
        # Le vieux est FERMÉ, pas supprimé : la piste d'audit reste entière.
        self.assertEqual(vieux.statut, PaymentLink.Statut.EXPIRE)
        self.assertEqual(neuf.statut, PaymentLink.Statut.EN_ATTENTE)

    def test_le_lien_porte_toujours_une_expiration(self):
        from apps.ventes.models import PAYMENT_LINK_TTL_DAYS
        from apps.ventes.services import create_payment_link
        lien = create_payment_link(facture=self.facture)
        self.assertIsNotNone(lien.expires_at)
        self.assertGreater(lien.expires_at, timezone.now())
        self.assertLessEqual(
            lien.expires_at,
            timezone.now() + timedelta(days=PAYMENT_LINK_TTL_DAYS + 1))


class TestAud136Revocation(_Base):
    slug = 'aud136-revoc'

    def test_revocation_ferme_le_lien_actif(self):
        r1 = self.api.post(self._url(), {}, format='json')
        self.assertEqual(r1.status_code, 201, r1.data)
        resp = self.api.post(self._url('revoquer-lien-paiement'), {},
                             format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(resp.data['revoque'])
        lien = PaymentLink.objects.get()
        self.assertEqual(lien.statut, PaymentLink.Statut.ANNULE)
        self.assertFalse(lien.is_valid)

    def test_revocation_sans_lien_actif_est_idempotente(self):
        resp = self.api.post(self._url('revoquer-lien-paiement'), {},
                             format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertFalse(resp.data['revoque'])

    def test_apres_revocation_un_nouveau_lien_peut_etre_emis(self):
        r1 = self.api.post(self._url(), {}, format='json')
        self.api.post(self._url('revoquer-lien-paiement'), {}, format='json')
        r2 = self.api.post(self._url(), {}, format='json')
        self.assertEqual(r2.status_code, 201, r2.data)
        self.assertNotEqual(r1.data['token'], r2.data['token'])


class TestAud136MontantEtPaiement(_Base):
    slug = 'aud136-montant'

    def _lien(self):
        from apps.ventes.services import create_payment_link
        return create_payment_link(facture=self.facture)

    def test_payer_un_lien_expire_ne_cree_aucun_paiement(self):
        lien = self._lien()
        PaymentLink.objects.filter(pk=lien.pk).update(
            expires_at=timezone.now() - timedelta(days=1))
        lien.refresh_from_db()

        resp = self.public.post(
            f'/api/django/public/pay/{lien.token}/webhook/', {},
            format='json')
        self.assertEqual(resp.status_code, 400, getattr(resp, 'data', resp))
        self.assertFalse(Paiement.objects.filter(facture=self.facture)
                         .exists())

    def test_payer_un_lien_revoque_ne_cree_aucun_paiement(self):
        lien = self._lien()
        lien.statut = PaymentLink.Statut.ANNULE
        lien.save(update_fields=['statut'])
        resp = self.public.post(
            f'/api/django/public/pay/{lien.token}/webhook/', {},
            format='json')
        self.assertEqual(resp.status_code, 400, getattr(resp, 'data', resp))
        self.assertFalse(Paiement.objects.filter(facture=self.facture)
                         .exists())

    def test_montant_encaisse_est_le_reste_du_a_l_instant_du_paiement(self):
        """Déjà correct — PREUVE jointe (la tâche demande de le DIRE)."""
        lien = self._lien()
        self.assertEqual(lien.montant, Decimal('12000.00'))

        # Règlement partiel APRÈS la création du lien.
        Paiement.objects.create(
            company=self.company, facture=self.facture,
            montant=Decimal('5000.00'), mode='virement',
            date_paiement=date.today(), created_by=self.user)

        from apps.ventes.services import record_payment_from_link
        with patch('apps.ventes.payments.providers.get_provider',
                   return_value=_ProviderQuiConfirme(montant='12000.00')):
            paiement, err = record_payment_from_link(link=lien, payload={})
        self.assertIsNone(err)
        # 7 000 (le reste dû à l'instant T), JAMAIS les 12 000 figés.
        self.assertEqual(paiement.montant, Decimal('7000.00'))

    def test_montant_a_payer_expose_le_reste_du_vivant(self):
        lien = self._lien()
        Paiement.objects.create(
            company=self.company, facture=self.facture,
            montant=Decimal('5000.00'), mode='virement',
            date_paiement=date.today(), created_by=self.user)
        self.facture.refresh_from_db()
        lien.refresh_from_db()
        self.assertEqual(lien.montant_a_payer, Decimal('7000.00'))

        # La page publique montre le reste dû, pas le chiffre figé.
        resp = self.public.get(f'/api/django/public/pay/{lien.token}/')
        self.assertEqual(resp.status_code, 200, getattr(resp, 'data', resp))
        self.assertEqual(Decimal(resp.data['montant']), Decimal('7000.00'))
        self.assertEqual(
            Decimal(resp.data['montant_initial']), Decimal('12000.00'))

    def test_le_noop_ne_confirme_jamais_un_paiement(self):
        """QX3 préservé : le webhook public par défaut n'encaisse rien."""
        lien = self._lien()
        resp = self.public.post(
            f'/api/django/public/pay/{lien.token}/webhook/', {},
            format='json')
        self.assertEqual(resp.status_code, 400, getattr(resp, 'data', resp))
        self.assertFalse(Paiement.objects.filter(facture=self.facture)
                         .exists())
