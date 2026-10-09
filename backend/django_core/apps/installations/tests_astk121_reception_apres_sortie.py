"""ERR-ASTK121 — une réception APRÈS une sortie partielle ne re-réserve pas
ce qui est déjà sorti.

Scénario : besoin 20 (réservation N14 = 20), BCF du manque, réception 10,
vente partielle 10 (sortie 10, réservation soldée à 10), réception 10.
Avant le correctif, ``reserver_stock_recu_pour_chantier`` posait
``max(10, reçu 20) = 20`` sans retrancher le déjà sorti : « Installé »
sortait alors 20 ⇒ Σ SORTIE 30 pour un besoin de 20.

Run :
    python manage.py test apps.installations.tests.test_astk121_reception_apres_sortie -v 2
"""
import itertools
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.db.models import Sum

from authentication.models import Company

from apps.crm.models import Client, Lead
from apps.installations.models import Installation, StockReservation
from apps.installations.services import (
    changer_statut_chantier, create_installation_from_devis,
    solder_reservations_vente,
)
from apps.stock.models import (
    BonCommandeFournisseur, Fournisseur, MouvementStock, Produit,
    ReceptionFournisseur,
)
from apps.stock.services import (
    confirm_reception_fournisseur, draft_bcf_for_shortfall,
    record_stock_movement,
)
from apps.ventes.models import Devis, LigneDevis

User = get_user_model()
_seq = itertools.count(1)


class ReceptionApresSortiePartielleTests(TestCase):
    def setUp(self):
        n = next(_seq)
        self.company = Company.objects.create(
            slug=f'astk121-err-{n}', nom=f'ASTK121 Co {n}')
        self.user = User.objects.create_user(
            username=f'astk121-err-{n}', password='x', company=self.company,
            role_legacy='responsable')
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fourn ASTK121')
        # Stock nul : le manque (donc le BCF) couvre tout le besoin.
        self.panneau = Produit.objects.create(
            company=self.company, nom='Panneau ASTK121',
            sku=f'SKU-ASTK121-ERR-{n}', prix_vente=Decimal('100'),
            prix_achat=Decimal('60'), quantite_stock=0)
        client = Client.objects.create(
            company=self.company, nom='Site', prenom='Client',
            email=f'astk121-err-{n}@example.invalid')
        lead = Lead.objects.create(
            company=self.company, nom='Site', prenom='Client',
            stage='SIGNED', type_installation='residentiel')
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-ASTK121-ERR-{n}',
            client=client, lead=lead, statut=Devis.Statut.ACCEPTE,
            taux_tva=Decimal('20'), mode_installation='residentiel')
        LigneDevis.objects.create(
            devis=devis, produit=self.panneau, designation=self.panneau.nom,
            quantite=Decimal('20'), prix_unitaire=Decimal('100'))
        self.inst, _ = create_installation_from_devis(
            devis, self.user, self.company)

    def _resa(self):
        return StockReservation.objects.get(
            installation=self.inst, produit=self.panneau)

    def _mouvement(self, type_mouvement, qte, reference):
        p = Produit.objects.get(pk=self.panneau.pk)
        signe = 1 if type_mouvement == MouvementStock.TypeMouvement.ENTREE else -1
        record_stock_movement(
            company=self.company, produit=p, type_mouvement=type_mouvement,
            quantite=qte, quantite_avant=p.quantite_stock,
            quantite_apres=p.quantite_stock + signe * qte,
            reference=reference, note=reference, created_by=self.user)

    def _reception(self, bon, qte):
        n = next(_seq)
        rec = ReceptionFournisseur.objects.create(
            company=self.company, reference=f'REC-ASTK121-ERR-{n}',
            bon_commande=bon, created_by=self.user)
        rec.lignes.create(
            ligne_commande=bon.lignes.get(produit=self.panneau),
            produit=self.panneau, quantite=qte)
        confirm_reception_fournisseur(rec, self.user)

    def _scenario(self):
        self.assertEqual(self._resa().quantite, 20)
        bon, _ = draft_bcf_for_shortfall(
            self.inst, self.fournisseur, self.user, self.company)
        bon.statut = BonCommandeFournisseur.Statut.ENVOYE
        bon.save(update_fields=['statut'])
        self.assertEqual(bon.lignes.get(produit=self.panneau).quantite, 20)

        self._reception(bon, 10)
        self.assertEqual(self._resa().quantite, 20)

        # Vente partielle : 10 sortis par la facture, réservation soldée.
        self._mouvement(MouvementStock.TypeMouvement.SORTIE, 10, 'FAC-ASTK121')
        solder_reservations_vente(
            self.inst, {self.panneau.id: 10}, 'FAC-ASTK121', user=self.user)
        self.assertEqual(self._resa().quantite, 10)

        self._reception(bon, 10)

    def test_reception_apres_vente_ne_rereserve_pas_le_sorti(self):
        self._scenario()
        resa = self._resa()
        self.assertEqual((resa.quantite, resa.active, resa.consomme),
                         (10, True, False))

    def test_installe_ne_sort_que_le_reliquat(self):
        self._scenario()
        # Stock abondant d'une autre provenance : la garde plancher (ERR80)
        # ne doit pas masquer une double sortie.
        self._mouvement(MouvementStock.TypeMouvement.ENTREE, 100, 'AUTRE')
        changer_statut_chantier(
            self.inst, Installation.Statut.INSTALLE, self.user,
            verifier_gates=False)
        total_sortie = (MouvementStock.objects
                        .filter(produit=self.panneau,
                                type_mouvement=MouvementStock.TypeMouvement.SORTIE)
                        .aggregate(t=Sum('quantite'))['t'])
        self.assertEqual(total_sortie, 20)
