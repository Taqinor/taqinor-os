"""QX33be — acompte au moment de la signature (mode dégradé sans PSP).

  * le payload de succès post-signature porte l'acompte (tranche 1 sur le TTC
    remisé QX1) + RIB si configuré ; ADEV53 : jamais de ``card_payment_url``
    (aucune route ``pay-card``), clés = contrat ``proposal_accept.json`` ;
  * l'endpoint « j'ai effectué le virement » notifie le vendeur + stampe le
    chatter, sans changer le statut ni créer de Paiement ; ADEV53 : il est
    gardé par l'OTP de lecture exactement comme la lecture (403).
"""
import json
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from authentication.models import Company
from apps.crm.models import Client
from apps.ventes.models import Devis, LigneDevis, Paiement, ShareLink

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


@override_settings(CACHES={'default': {
    'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}})
class Qx33DepositSuccessTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='QX33 Co')
        self.seller = User.objects.create_user(
            username='qx33_seller', password='x', role_legacy='commercial',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='QX33',
            telephone='+212600000054')
        self.devis = Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-QX3301',
            client=self.client_obj, statut=Devis.Statut.ENVOYE,
            taux_tva=Decimal('20'), remise_globale=Decimal('10'),
            created_by=self.seller)
        produit = self._produit()
        LigneDevis.objects.create(
            devis=self.devis, produit=produit, designation='Panneau',
            quantite=Decimal('10'), prix_unitaire=Decimal('1000'),
            remise=Decimal('0'))
        self.link = ShareLink.for_devis(self.devis)
        self.api = APIClient()

    def _produit(self):
        from apps.stock.models import Produit
        return Produit.objects.create(
            company=self.company, nom='Panneau', sku='QX33-PV',
            prix_vente=Decimal('1000'), quantite_stock=100)

    def test_accept_success_payload_has_deposit(self):
        from apps.ventes.public.signature_views import empreinte_contenu
        # AFAC59 — le RIB vient du profil de la SOCIÉTÉ émettrice (le réglage
        # global n'existe pas).
        from apps.parametres.models import CompanyProfile
        profile = CompanyProfile.get(company=self.company)
        profile.rib = '001 TAQINOR BANK 1234567'
        profile.save()
        resp = self.api.post(
            f'/api/django/public/proposal/{self.link.token}/accept/',
            {'nom': 'Client', 'consent_esign': True,
             'empreinte_contenu': empreinte_contenu(self.devis)},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        pay = resp.data['paiement']
        # 10000 HT − 10 % = 9000 ; TTC 10800 ; acompte 30 % = 3240.
        self.assertEqual(pay['acompte_ttc'], '3240.00')
        self.assertIn('TAQINOR BANK', pay['rib'])
        self.assertNotIn('card_payment_url', pay)
        self.assertIn('virement', pay['declare_url'])
        # ADEV53 — la réponse RÉELLE porte exactement les clés `paiement` du
        # contrat partagé avec la page (PACT10).
        contrat = json.loads((Path(__file__).resolve().parents[1]
                              / 'contract_samples' / 'proposal_accept.json')
                             .read_text(encoding='utf-8'))
        self.assertEqual(set(pay), set(contrat['reponse_200']['paiement']))
        # Même TYPE que l'exemple : montants et pourcentage en chaînes.
        self.assertIsInstance(pay['pourcentage'], str)
        self.assertIsInstance(contrat['reponse_200']['paiement']['pourcentage'], str)

    @override_settings(PAYMENT_PROVIDER='hosted')
    def test_pas_de_card_payment_url(self):
        """ADEV53 (C-ADEV-023) — même avec un PSP déclaré, aucune clé
        ``card_payment_url`` : la route ``pay-card`` n'existe pas."""
        from django.urls import Resolver404, resolve
        from apps.ventes.public.signature_views import empreinte_contenu
        resp = self.api.post(
            f'/api/django/public/proposal/{self.link.token}/accept/',
            {'nom': 'Client', 'consent_esign': True,
             'empreinte_contenu': empreinte_contenu(self.devis)},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertNotIn('card_payment_url', resp.data['paiement'])
        # Le fait vérifié : la route qu'on servait n'existe pas.
        with self.assertRaises(Resolver404):
            resolve(f'/api/django/public/proposal/{self.link.token}/pay-card/')

    def test_virement_garde_otp_lecture(self):
        """ADEV53 — un lien à OTP de lecture non déverrouillé : 403
        ``otp_required`` comme la lecture, rien déclaré ; déverrouillé par le
        vrai code : 200."""
        from django.core.cache import cache
        from apps.notifications.models import Notification
        from apps.ventes.domain.cycle_vie import _otp_lecture_cache_key
        self.devis.statut = Devis.Statut.ACCEPTE
        self.devis.save(update_fields=['statut'])
        self.link.otp_lecture = True
        self.link.save(update_fields=['otp_lecture'])
        base = f'/api/django/public/proposal/{self.link.token}'
        lecture = self.api.get(f'{base}/data/')
        refus = self.api.post(f'{base}/virement/', {}, format='json')
        self.assertEqual(lecture.status_code, 403)
        self.assertEqual(refus.status_code, 403)
        self.assertEqual(refus.data, {'detail': 'otp_required'})
        virement = Notification.objects.filter(
            recipient=self.seller, title__startswith='Virement déclaré')
        self.assertFalse(virement.exists())
        cache.set(_otp_lecture_cache_key(self.link.token), '123456', 600)
        # ASEC23 — le vrai code, puis la preuve DE CE navigateur relayée en
        # en-tête (comme ``apps/web``) : le code seul ne déverrouille rien.
        verif = self.api.post(f'{base}/otp-lecture/verifier/',
                              {'otp_code': '123456'}, format='json')
        self.assertEqual(verif.status_code, 200, verif.data)
        self.assertEqual(
            self.api.post(f'{base}/virement/', {}, format='json').status_code,
            403)
        self.api.credentials(HTTP_X_PROPOSITION_PREUVE=verif.data['preuve'])
        ok = self.api.post(f'{base}/virement/', {}, format='json')
        self.assertEqual(ok.status_code, 200, ok.data)
        self.assertTrue(virement.exists())

    def test_virement_declaration_notifies_seller(self):
        self.devis.statut = Devis.Statut.ACCEPTE
        self.devis.save(update_fields=['statut'])
        from apps.notifications.models import Notification
        resp = self.api.post(
            f'/api/django/public/proposal/{self.link.token}/virement/',
            {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(Notification.objects.filter(
            recipient=self.seller).exists())
        # Statut inchangé, aucun Paiement créé (règle #4).
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.statut, Devis.Statut.ACCEPTE)
        self.assertEqual(
            Paiement.objects.filter(facture__devis=self.devis).count(), 0)

    def test_virement_declaration_idempotent(self):
        self.devis.statut = Devis.Statut.ACCEPTE
        self.devis.save(update_fields=['statut'])
        url = f'/api/django/public/proposal/{self.link.token}/virement/'
        self.api.post(url, {}, format='json')
        second = self.api.post(url, {}, format='json')
        self.assertEqual(second.status_code, 200)
        self.assertTrue(second.data.get('already'))
