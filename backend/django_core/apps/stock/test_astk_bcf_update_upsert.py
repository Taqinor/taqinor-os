"""ASTK67 — lignes d'un BCF brouillon mises à jour par identifiant (upsert) et
update atomique.

Rejoue BCF-11 (PATCH 200 avec le payload de l'écran : frais_annexes 500 →
0.00, ligne 191 → 192) et BCF-16 (annuler / rouvrir / PATCH = 409 mais la
note modifiée était déjà écrite en base).

Source réelle : serializer réel, via l'API (aucun mock).

Run :
    python manage.py test apps.stock.test_astk_bcf_update_upsert -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.models import (
    BonCommandeFournisseur, Fournisseur, LigneBonCommandeFournisseur, Produit,
    ReceptionFournisseur,
)
from authentication.models import Company

User = get_user_model()

URL = '/api/django/stock/bons-commande-fournisseur/'


class BcfUpdateUpsertTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='ASTK67', slug='astk67-co')
        self.user = User.objects.create_user(
            username='astk67-resp', password='x', company=self.company,
            role_legacy='responsable')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur ASTK67')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur ASTK67', sku='ASTK67-1',
            prix_vente=Decimal('1500'), prix_achat=Decimal('900'))
        self.bcf = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-ASTK67-1',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.BROUILLON, note='NOTE')
        self.ligne = LigneBonCommandeFournisseur.objects.create(
            bon_commande=self.bcf, produit=self.produit, quantite=2,
            prix_achat_unitaire=Decimal('800'),
            frais_annexes=Decimal('500'))

    def _payload_ecran(self, note='NOTE-MODIFIEE', **ligne):
        """Payload de l'écran (buildPayload) : SANS frais_annexes, avec id."""
        data = {'id': self.ligne.pk, 'produit': self.produit.pk,
                'quantite': 3, 'prix_achat_unitaire': '800'}
        data.update(ligne)
        return {'fournisseur': self.fournisseur.pk, 'note': note,
                'lignes': [data]}

    def test_frais_conserves(self):
        rep = self.api.patch(f'{URL}{self.bcf.pk}/', self._payload_ecran(),
                             format='json')
        self.assertEqual(rep.status_code, 200, rep.data)
        lignes = list(self.bcf.lignes.all())
        self.assertEqual(len(lignes), 1)
        self.assertEqual(lignes[0].pk, self.ligne.pk)  # id stable
        self.assertEqual(lignes[0].quantite, 3)
        self.assertEqual(lignes[0].frais_annexes, Decimal('500'))
        # Rouvrir → réenregistrer sans toucher : objet serveur identique.
        detail = self.api.get(f'{URL}{self.bcf.pk}/').data
        rep = self.api.patch(f'{URL}{self.bcf.pk}/', {
            'note': detail['note'],
            'lignes': [{k: ligne[k] for k in (
                'id', 'produit', 'quantite', 'prix_achat_unitaire')}
                for ligne in detail['lignes']],
        }, format='json')
        self.assertEqual(rep.status_code, 200, rep.data)
        relu = self.api.get(f'{URL}{self.bcf.pk}/').data
        self.assertEqual(relu['lignes'], detail['lignes'])

    def test_ligne_sans_id_reste_une_creation(self):
        payload = self._payload_ecran()
        payload['lignes'].append({'produit': self.produit.pk, 'quantite': 1,
                                  'prix_achat_unitaire': '700'})
        rep = self.api.patch(f'{URL}{self.bcf.pk}/', payload, format='json')
        self.assertEqual(rep.status_code, 200, rep.data)
        self.assertEqual(self.bcf.lignes.count(), 2)
        self.assertTrue(self.bcf.lignes.filter(pk=self.ligne.pk).exists())

    def test_ligne_omise_supprimee(self):
        rep = self.api.patch(f'{URL}{self.bcf.pk}/', {
            'lignes': [{'produit': self.produit.pk, 'quantite': 1,
                        'prix_achat_unitaire': '700'}]}, format='json')
        self.assertEqual(rep.status_code, 200, rep.data)
        self.assertFalse(LigneBonCommandeFournisseur.objects.filter(
            pk=self.ligne.pk).exists())

    def _annuler_rouvrir_avec_reception(self):
        # Le BCF part, une réception brouillon référence sa ligne, puis il
        # est annulé (la réception brouillon est annulée en cascade) et
        # rouvert.
        BonCommandeFournisseur.objects.filter(pk=self.bcf.pk).update(
            statut=BonCommandeFournisseur.Statut.ENVOYE)
        rec = ReceptionFournisseur.objects.create(
            company=self.company, reference='REC-ASTK67-1',
            bon_commande=self.bcf,
            statut=ReceptionFournisseur.Statut.BROUILLON,
            created_by=self.user)
        rec.lignes.create(ligne_commande=self.ligne, produit=self.produit,
                          quantite=1)
        rep = self.api.post(f'{URL}{self.bcf.pk}/annuler/',
                            {'motif_annulation': 'test'}, format='json')
        self.assertEqual(rep.status_code, 200, rep.data)
        rep = self.api.post(f'{URL}{self.bcf.pk}/rouvrir/')
        self.assertEqual(rep.status_code, 200, rep.data)

    def test_rouvert_lignes_inchangees_200(self):
        self._annuler_rouvrir_avec_reception()
        rep = self.api.patch(f'{URL}{self.bcf.pk}/', self._payload_ecran(
            quantite=2), format='json')
        self.assertEqual(rep.status_code, 200, rep.data)
        self.bcf.refresh_from_db()
        self.assertEqual(self.bcf.note, 'NOTE-MODIFIEE')
        self.assertTrue(LigneBonCommandeFournisseur.objects.filter(
            pk=self.ligne.pk).exists())

    def test_entete_non_ecrit_si_409(self):
        self._annuler_rouvrir_avec_reception()
        # Ligne protégée (référencée par la réception) retirée du payload.
        rep = self.api.patch(f'{URL}{self.bcf.pk}/', {
            'note': 'NOTE-MODIFIEE',
            'lignes': [{'produit': self.produit.pk, 'quantite': 1,
                        'prix_achat_unitaire': '700'}]}, format='json')
        self.assertEqual(rep.status_code, 409, rep.data)
        self.bcf.refresh_from_db()
        self.assertEqual(self.bcf.note, 'NOTE')
        self.assertEqual(
            list(self.bcf.lignes.values_list('pk', flat=True)),
            [self.ligne.pk])
        self.assertEqual(self.bcf.lignes.get().frais_annexes,
                         Decimal('500'))
