"""ASTK56 (C-ASTK-011) — `annuler_reception_confirmee` émet
`reception_fournisseur_annulee` après commit.

Constat : la confirmation émet `reception_fournisseur_confirmee` (abonnés
qhse + installations : provision GR/IR, séries, réservation) mais
l'annulation n'émettait RIEN (aucun `.send` dans le service) : la provision
GR/IR, les séries et la réservation chantier restaient comme si la
marchandise était entrée. Le signal (posé par ASTK55 dans core/events.py)
est désormais émis UNE fois, après commit, avec la réception et les quantités
annulées ; une annulation qui échoue n'émet rien.

Run :
    python manage.py test apps.stock.test_astk_evenement_annulation
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company
from apps.stock.models import (
    BonCommandeFournisseur, Fournisseur, Produit, ReceptionFournisseur,
)
from apps.stock.services import (
    annuler_reception_confirmee, confirm_reception_fournisseur,
)
from core.events import reception_fournisseur_annulee

User = get_user_model()


class EvenementAnnulationTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='ASTK56 Co', slug='astk56-co')
        self.user = User.objects.create_user(
            username='astk56-user', password='x', company=self.company,
            role_legacy='responsable')
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur ASTK56')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur ASTK56', sku='OND-ASTK56',
            prix_vente=Decimal('2000'), prix_achat=Decimal('1200'),
            quantite_stock=0)
        bc = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-ASTK56-1',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.ENVOYE)
        self.ligne_cmd = bc.lignes.create(
            produit=self.produit, quantite=10,
            prix_achat_unitaire=Decimal('100'))
        self.reception = ReceptionFournisseur.objects.create(
            company=self.company, reference='REC-ASTK56-1',
            bon_commande=bc, statut=ReceptionFournisseur.Statut.BROUILLON,
            created_by=self.user)
        self.ligne_rec = self.reception.lignes.create(
            ligne_commande=self.ligne_cmd, produit=self.produit, quantite=7)
        confirm_reception_fournisseur(self.reception, self.user)
        self.reception.refresh_from_db()

        self.emissions = []

        def _capter(sender, **kwargs):
            self.emissions.append(kwargs)

        self._capter = _capter
        reception_fournisseur_annulee.connect(_capter)
        self.addCleanup(reception_fournisseur_annulee.disconnect, _capter)

    def test_emis_une_fois_apres_commit(self):
        with self.captureOnCommitCallbacks(execute=False) as rappels:
            annuler_reception_confirmee(self.reception, self.user)
        # Rien n'est émis AVANT le commit.
        self.assertEqual(self.emissions, [])
        for rappel in rappels:
            rappel()
        self.assertEqual(len(self.emissions), 1)
        emission = self.emissions[0]
        self.assertEqual(emission['reception'].pk, self.reception.pk)
        self.assertEqual(emission['company'], self.company)
        self.assertEqual(emission['user'], self.user)
        self.assertEqual(len(emission['lignes']), 1)
        ligne = emission['lignes'][0]
        self.assertEqual(ligne['ligne'].pk, self.ligne_rec.pk)
        self.assertEqual(ligne['produit'].pk, self.produit.pk)
        self.assertEqual(ligne['quantite_annulee'], 7)

    def test_aucune_emission_si_l_annulation_echoue(self):
        with self.captureOnCommitCallbacks(execute=True):
            annuler_reception_confirmee(self.reception, self.user)
        self.assertEqual(len(self.emissions), 1)
        # Seconde annulation sur une instance périmée : refusée, rien émis.
        perimee = ReceptionFournisseur.objects.get(pk=self.reception.pk)
        perimee.statut = ReceptionFournisseur.Statut.CONFIRME
        with self.captureOnCommitCallbacks(execute=True):
            with self.assertRaises(ValueError):
                annuler_reception_confirmee(perimee, self.user)
        self.assertEqual(len(self.emissions), 1)
