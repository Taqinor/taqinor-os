"""ASTK179 (C-ASTK-040) — révoquer l'accès d'un fournisseur coupe TOUTES ses
portes (compte ET jetons publics) ; un fournisseur archivé, bloqué total ou
rejeté ne passe plus par son jeton.

Constat (sonde FOUR-4) : GET portail à jeton avant révocation = 200, APRÈS
révocation du compte = 200, confirmer un BCF après = 200 — le jeton XPUR22
(90 jours) restait une porte ouverte. Désormais `revoquer-acces` révoque
chaque jeton actif (réponse `jetons_revoques`, contrat
fournisseur_portail_jetons.json) et `resoudre_token_portail_fournisseur`
refuse le jeton d'un fournisseur coupé : 404 identique à un jeton inconnu.

Run :
    python manage.py test apps.stock.test_astk_revocation_fournisseur
"""
import json
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.stock.models import (
    BonCommandeFournisseur, Fournisseur, PortailFournisseurToken, Produit,
)
from apps.stock.services import (
    generer_token_portail_fournisseur, provisionner_compte_fournisseur,
    reactiver_acces_compte_fournisseur,
)

User = get_user_model()

PUBLIC = '/api/django/public/stock/portail-fournisseur/'
CONTRAT = (Path(__file__).resolve().parent / 'contract_samples'
           / 'fournisseur_portail_jetons.json')


class RevocationTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='ASTK179 Co', slug='astk179-co')
        self.admin = User.objects.create_user(
            username='astk179-admin', password='x', company=self.company,
            role_legacy='admin')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')
        self.anonyme = APIClient()
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Import Solar ASTK179',
            email='astk179@fournisseur.ma')
        produit = Produit.objects.create(
            company=self.company, nom='Onduleur ASTK179', sku='OND-ASTK179',
            prix_vente=Decimal('2000'), prix_achat=Decimal('1200'),
            quantite_stock=0)
        self.bc = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-ASTK179-1',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.ENVOYE)
        self.bc.lignes.create(
            produit=produit, quantite=2, prix_achat_unitaire=Decimal('100'))
        self.user_portail, _ = provisionner_compte_fournisseur(
            self.company, self.fournisseur.id)
        self.jeton = generer_token_portail_fournisseur(
            self.company, self.fournisseur, self.admin)
        self.jeton_2 = generer_token_portail_fournisseur(
            self.company, self.fournisseur, self.admin)

    def _revoquer(self):
        return self.api.post(
            f'/api/django/stock/fournisseurs/{self.fournisseur.id}/'
            'revoquer-acces/')

    def _portail(self, token):
        return self.anonyme.get(f'{PUBLIC}{token}/')

    def _confirmer(self, token):
        return self.anonyme.post(
            f'{PUBLIC}{token}/bcf/{self.bc.id}/confirmer/',
            {'date_confirmee_fournisseur': '2026-11-02'}, format='json')

    def _assert_404_indistinct(self, token):
        inconnu = self._portail('jeton-inconnu-astk179')
        for rep in (self._portail(token), self._confirmer(token),
                    self.anonyme.get(f'{PUBLIC}{token}/creneaux-disponibles/'),
                    self.anonyme.post(f'{PUBLIC}{token}/reserver-creneau/',
                                      {}, format='json')):
            self.assertEqual(rep.status_code, 404, rep.content)
            self.assertEqual(rep.json()['detail'], inconnu.json()['detail'])

    def test_revoquer_acces_revoque_les_jetons(self):
        self.assertEqual(self._portail(self.jeton.token).status_code, 200)
        rep = self._revoquer()
        self.assertEqual(rep.status_code, 200, rep.content)
        self.assertEqual(rep.json()['jetons_revoques'], 2)
        self.assertFalse(rep.json()['actif'])
        self.user_portail.refresh_from_db()
        self.assertFalse(self.user_portail.is_active)
        # Relu en base : plus aucun jeton actif pour ce fournisseur.
        self.assertFalse(PortailFournisseurToken.objects.filter(
            fournisseur=self.fournisseur, revoked=False).exists())
        self._assert_404_indistinct(self.jeton.token)
        self._assert_404_indistinct(self.jeton_2.token)

    def test_reprovisionner_ne_ressuscite_pas_les_jetons(self):
        self.assertEqual(self._revoquer().status_code, 200)
        provisionner_compte_fournisseur(self.company, self.fournisseur.id)
        reactiver_acces_compte_fournisseur(self.company, self.fournisseur.id)
        self.assertFalse(PortailFournisseurToken.objects.filter(
            fournisseur=self.fournisseur, revoked=False).exists())
        self.assertEqual(self._portail(self.jeton.token).status_code, 404)

    def test_confirmer_apres_revocation_404(self):
        self.assertEqual(self._revoquer().status_code, 200)
        rep = self._confirmer(self.jeton.token)
        self.assertEqual(rep.status_code, 404, rep.content)
        self.bc.refresh_from_db()
        self.assertIsNone(self.bc.date_confirmee_fournisseur)

    def test_jeton_fournisseur_archive_404(self):
        Fournisseur.objects.filter(pk=self.fournisseur.pk).update(
            is_archived=True)
        self._assert_404_indistinct(self.jeton.token)

    def test_jeton_fournisseur_bloque_total_404(self):
        Fournisseur.objects.filter(pk=self.fournisseur.pk).update(
            statut=Fournisseur.Statut.BLOQUE_TOTAL)
        self._assert_404_indistinct(self.jeton.token)
        # Un blocage PARTIEL (commandes) ne coupe pas le portail.
        Fournisseur.objects.filter(pk=self.fournisseur.pk).update(
            statut=Fournisseur.Statut.BLOQUE_COMMANDES)
        self.assertEqual(self._portail(self.jeton.token).status_code, 200)

    def test_jeton_candidature_rejetee_404(self):
        Fournisseur.objects.filter(pk=self.fournisseur.pk).update(
            statut_validation=Fournisseur.StatutValidation.REJETE)
        self._assert_404_indistinct(self.jeton.token)

    def test_reponse_conforme_contrat(self):
        contrat = json.loads(CONTRAT.read_text(encoding='utf-8'))
        decl = contrat['routes']['fournisseur_revoquer_acces']
        rep = self._revoquer()
        self.assertEqual(rep.status_code, 200, rep.content)
        self.assertEqual(
            sorted(rep.json()), sorted(decl['exemple_nouveau_astk179']))
        self.assertIn('jetons_revoques', decl['cles_nouvelles_astk179'])
