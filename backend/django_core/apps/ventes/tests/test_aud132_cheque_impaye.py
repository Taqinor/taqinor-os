"""AUD132 — chèque impayé : ingérable depuis le produit, et les deux documents
client mentaient sur les paiements rejetés.

(b) PAY-11 : dans `_releve_data`, `total_paye += f.montant_paye` EXCLUT les
    rejetés, mais le détail était construit par `for p in f.paiements.all():`
    sans aucun filtre — pendant que les escomptes et les avances ventilées,
    qui COMPTENT dans le total, n'étaient jamais listés. Ce même dict alimente
    l'écran interne, le PDF de relevé et, via `selectors.releve_client_portail`,
    le PORTAIL CLIENT.

(c) PAY-12 : `recu_pdf` et `envoyer_recu` prenaient `get_object()` sans
    contrôler `paiement.statut` — le client détenait une quittance pour un
    chèque sans provision.

(a) PAY-10 est la moitié écran : couverte par `PaiementsPage.test.jsx`.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.ventes.models import (
    AffectationPaiement, Facture, Paiement, RetenueSubie,
)

User = get_user_model()


class _Base(TestCase):
    slug = 'aud132-co'

    def setUp(self):
        from authentication.models import Company
        self.company = Company.objects.get_or_create(
            slug=self.slug, defaults={'nom': 'AUD132 Co'})[0]
        self.user = User.objects.create_user(
            username=f'{self.slug}-resp', password='x',
            role_legacy='responsable', company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Débiteur AUD132',
            email='aud132@example.com', telephone='+212600000132')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        mail.outbox = []

    def _facture(self, ht='10000.00', reference=None):
        return Facture.objects.create(
            company=self.company,
            reference=reference or f'FAC-AUD132-{Facture.objects.count() + 1:04d}',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20.00'), libelle='Prestation',
            montant_ht=Decimal(ht),
            date_emission=date.today() - timedelta(days=60),
            date_echeance=date.today() - timedelta(days=30))

    def _paiement(self, facture=None, montant='1000.00', **kwargs):
        return Paiement.objects.create(
            company=self.company, facture=facture,
            client=None if facture is not None else self.client_obj,
            montant=Decimal(montant), mode='cheque',
            date_paiement=date.today() - timedelta(days=10),
            created_by=self.user, **kwargs)


class TestAud132ReleveDetailEgaleTotal(_Base):
    """(b) Σ des lignes de paiement == totaux.paye, sur les TROIS surfaces."""

    slug = 'aud132-releve'

    def _somme_lignes(self, data):
        return sum(Decimal(ligne['montant']) for ligne in data['paiements'])

    def _verifier_les_trois_surfaces(self):
        """Écran interne, source du PDF et portail viennent du MÊME dict."""
        from apps.ventes.recouvrement import _releve_data
        from apps.ventes.selectors import releve_client_portail

        interne = _releve_data(self.client_obj, user=self.user)
        self.assertEqual(
            self._somme_lignes(interne), Decimal(interne['totaux']['paye']))

        # Le PDF est rendu depuis `_releve_data(client, user=None)` — même
        # dict, chemin sans filtre de portée.
        source_pdf = _releve_data(self.client_obj, user=None)
        self.assertEqual(
            self._somme_lignes(source_pdf),
            Decimal(source_pdf['totaux']['paye']))

        portail = releve_client_portail(self.client_obj)
        self.assertEqual(
            self._somme_lignes(portail), Decimal(portail['totaux']['paye']))
        return interne

    def test_cas_rejet(self):
        facture = self._facture()
        self._paiement(facture, '3000.00')
        rejete = self._paiement(facture, '5000.00')
        rejete.statut = Paiement.Statut.REJETE
        rejete.motif_rejet = 'Chèque sans provision'
        rejete.save(update_fields=['statut', 'motif_rejet'])

        data = self._verifier_les_trois_surfaces()
        # Le rejeté n'est PLUS listé comme un règlement.
        self.assertEqual(len(data['paiements']), 1)
        self.assertEqual(Decimal(data['totaux']['paye']), Decimal('3000.00'))

    def test_cas_escompte(self):
        facture = self._facture()
        self._paiement(
            facture, '2900.00', escompte_montant=Decimal('100.00'))

        data = self._verifier_les_trois_surfaces()
        # L'escompte est une LIGNE explicite, pas un écart silencieux.
        types = sorted(ligne['type'] for ligne in data['paiements'])
        self.assertEqual(types, ['escompte', 'paiement'])
        self.assertEqual(Decimal(data['totaux']['paye']), Decimal('3000.00'))

    def test_cas_avance_ventilee(self):
        facture = self._facture()
        avance = self._paiement(None, '4000.00')
        AffectationPaiement.objects.create(
            company=self.company, paiement=avance, facture=facture,
            montant=Decimal('4000.00'), created_by=self.user)

        data = self._verifier_les_trois_surfaces()
        lignes_avance = [x for x in data['paiements'] if x['type'] == 'avance']
        self.assertEqual(len(lignes_avance), 1)
        self.assertIn(str(avance.id), lignes_avance[0]['reference_source'])
        self.assertEqual(Decimal(data['totaux']['paye']), Decimal('4000.00'))

    def test_cas_retenue_a_la_source(self):
        """Une retenue ne compte PAS dans `montant_paye` : elle ne doit donc
        apparaître dans aucune ligne de paiement (l'égalité tient quand même)."""
        facture = self._facture()
        self._paiement(facture, '2000.00')
        RetenueSubie.objects.create(
            company=self.company, facture=facture,
            taux=Decimal('5.00'), base=Decimal('10000.00'),
            montant=Decimal('500.00'), created_by=self.user)

        data = self._verifier_les_trois_surfaces()
        self.assertEqual(Decimal(data['totaux']['paye']), Decimal('2000.00'))

    def test_les_quatre_cas_ensemble(self):
        facture = self._facture(ht='40000.00')
        self._paiement(facture, '2900.00', escompte_montant=Decimal('100.00'))
        rejete = self._paiement(facture, '5000.00')
        rejete.statut = Paiement.Statut.REJETE
        rejete.save(update_fields=['statut'])
        avance = self._paiement(None, '4000.00')
        AffectationPaiement.objects.create(
            company=self.company, paiement=avance, facture=facture,
            montant=Decimal('4000.00'), created_by=self.user)
        RetenueSubie.objects.create(
            company=self.company, facture=facture,
            taux=Decimal('5.00'), base=Decimal('10000.00'),
            montant=Decimal('500.00'), created_by=self.user)

        data = self._verifier_les_trois_surfaces()
        self.assertEqual(Decimal(data['totaux']['paye']), Decimal('7000.00'))

    def test_avance_ventilee_puis_rejetee_sort_du_detail(self):
        facture = self._facture()
        avance = self._paiement(None, '4000.00')
        AffectationPaiement.objects.create(
            company=self.company, paiement=avance, facture=facture,
            montant=Decimal('4000.00'), created_by=self.user)
        avance.statut = Paiement.Statut.REJETE
        avance.save(update_fields=['statut'])

        data = self._verifier_les_trois_surfaces()
        self.assertEqual(data['paiements'], [])
        self.assertEqual(Decimal(data['totaux']['paye']), Decimal('0.00'))


class TestAud132QuittanceRejetee(_Base):
    """(c) Aucune quittance pour un règlement rejeté."""

    slug = 'aud132-recu'

    def _rejete(self):
        facture = self._facture()
        paiement = self._paiement(facture, '30000.00')
        paiement.statut = Paiement.Statut.REJETE
        paiement.motif_rejet = 'Chèque sans provision'
        paiement.save(update_fields=['statut', 'motif_rejet'])
        return paiement

    def test_recu_pdf_sur_paiement_rejete_est_409(self):
        paiement = self._rejete()
        resp = self.api.get(
            f'/api/django/ventes/paiements/{paiement.id}/recu-pdf/')
        self.assertEqual(resp.status_code, 409, getattr(resp, 'data', resp))

    def test_envoyer_recu_sur_paiement_rejete_est_409_et_n_envoie_rien(self):
        paiement = self._rejete()
        resp = self.api.post(
            f'/api/django/ventes/paiements/{paiement.id}/envoyer-recu/',
            {}, format='json')
        self.assertEqual(resp.status_code, 409, resp.data)
        self.assertEqual(len(mail.outbox), 0)

    def test_quittance_reste_disponible_pour_un_paiement_valide(self):
        facture = self._facture()
        paiement = self._paiement(facture, '1000.00')
        resp = self.api.get(
            f'/api/django/ventes/paiements/{paiement.id}/recu-pdf/')
        self.assertEqual(resp.status_code, 200)
