"""Groupe ASTK — réservations de chantier : réception, BC, arrondi, retour.

Sondes RESA de l'audit stock du 2026-10-06 rejouées sur les services réels
(aucun mock) :
  * ASTK121 (RESA-2) — la réception d'un BCF « besoin chantier » ne fait que
    COMPLÉTER la réservation, jamais la réduire ;
  * ASTK122 (RESA-4) — la réservation depuis un BC relit la nomenclature
    gelée (option retenue), jamais toutes les lignes du devis ;
  * ASTK123 (RESA-5) — annuler un BC (toggle ON) ne libère plus les
    réservations d'un chantier vivant ;
  * ASTK127 (RESA-14) — réserver avec l'arrondi HALF_UP de la sortie de la
    vente (12,5 m réserve 13) ;
  * ASTK128 (RESA-12) — le retournable compte toutes les sorties réelles
    (N14 consommée à « Installé », soldée par une vente, F11) ;
  * ASTK124 (RESA-6) — prédicat unique `chantier_peut_reserver` : une
    réception ne réactive plus la réservation d'un chantier annulé/clôturé.

Run :
    python manage.py test apps.installations.tests_astk_reservations_reception
"""
import itertools
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company

from apps.crm.models import Client, Lead
from apps.installations.models import (
    Installation, InstallationActivity, StockReservation,
)
from apps.installations.services import (
    changer_statut_chantier, chantier_peut_reserver,
    consommer_reservation_bc, create_installation_from_devis,
    liberer_reservation_bc, quantite_retournable, release_reservations,
    reserver_stock_depuis_bc, solder_reservations_vente,
    valider_retour_materiel,
)
from apps.stock.models import (
    BonCommandeFournisseur, Fournisseur, Produit, ReceptionFournisseur,
)
from apps.stock.services import (
    available_quantity, confirm_reception_fournisseur,
    draft_bcf_for_shortfall,
)
from apps.ventes.models import BonCommande, Devis, LigneDevis

User = get_user_model()

_seq = itertools.count(1)


class ResaBase(TestCase):
    SLUG = 'co-astk-resa'

    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug=self.SLUG, defaults={'nom': 'Co ASTK RESA'})
        self.user = User.objects.create_user(
            username=f'resp-{self.SLUG}', password='x', company=self.company,
            role_legacy='responsable')
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fourn ASTK RESA')

    def produit(self, nom, stock):
        n = next(_seq)
        return Produit.objects.create(
            company=self.company, nom=nom, sku=f'SKU-ASTKRESA-{n}',
            prix_vente=Decimal('100'), prix_achat=Decimal('60'),
            quantite_stock=stock)

    def devis_accepte(self, lignes):
        n = next(_seq)
        client = Client.objects.create(
            company=self.company, nom='Site', prenom='Client',
            email=f'astkresa-{n}@example.invalid')
        lead = Lead.objects.create(
            company=self.company, nom='Site', prenom='Client',
            stage='SIGNED', type_installation='residentiel')
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-ASTKRESA-{n}',
            client=client, lead=lead, statut=Devis.Statut.ACCEPTE,
            taux_tva=Decimal('20'), mode_installation='residentiel')
        for produit, qte in lignes:
            LigneDevis.objects.create(
                devis=devis, produit=produit, designation=produit.nom,
                quantite=Decimal(str(qte)), prix_unitaire=Decimal('100'))
        return devis

    def chantier(self, lignes):
        devis = self.devis_accepte(lignes)
        inst, _ = create_installation_from_devis(
            devis, self.user, self.company)
        return inst

    def resa(self, inst, produit):
        return StockReservation.objects.get(
            installation=inst, produit=produit)

    def confirmer_reception(self, bc, produit, qte):
        n = next(_seq)
        rec = ReceptionFournisseur.objects.create(
            company=self.company, reference=f'REC-ASTKRESA-{n}',
            bon_commande=bc, created_by=self.user)
        rec.lignes.create(
            ligne_commande=bc.lignes.get(produit=produit), produit=produit,
            quantite=qte)
        confirm_reception_fournisseur(rec, self.user)
        rec.refresh_from_db()
        return rec

    def bcf_du_manque(self, inst):
        bon, _ = draft_bcf_for_shortfall(
            inst, self.fournisseur, self.user, self.company)
        bon.statut = BonCommandeFournisseur.Statut.ENVOYE
        bon.save(update_fields=['statut'])
        return bon

    def installer(self, inst):
        changer_statut_chantier(
            inst, Installation.Statut.INSTALLE, self.user,
            verifier_gates=False)
        inst.refresh_from_db()


class ReceptionNeReduitPasTests(ResaBase):
    SLUG = 'co-astk121'

    def test_reception_complete_jamais_ne_reduit(self):
        panneau = self.produit('Panneau ASTK121', stock=5)
        inst = self.chantier([(panneau, 20)])
        self.assertEqual(self.resa(inst, panneau).quantite, 20)
        bon = self.bcf_du_manque(inst)
        self.confirmer_reception(bon, panneau, 10)

        resa = self.resa(inst, panneau)
        self.assertEqual((resa.quantite, resa.active), (20, True))
        panneau.refresh_from_db()
        self.assertEqual(panneau.quantite_stock, 15)
        self.assertEqual(available_quantity(panneau), -5)

        self.installer(inst)
        panneau.refresh_from_db()
        self.assertEqual(panneau.quantite_stock, 0)
        self.assertTrue(InstallationActivity.objects.filter(
            installation=inst, kind=InstallationActivity.Kind.NOTE,
            body__contains='manque 5').exists())


class BcPanierTests(ResaBase):
    SLUG = 'co-astk122'

    def setUp(self):
        super().setUp()
        self.reseau = self.produit('Onduleur réseau 8kW', stock=50)
        self.panneau = self.produit('Panneaux mono 550W', stock=50)
        self.hybride = self.produit('Onduleur hybride 5kW', stock=50)
        self.batterie = self.produit('Batterie 5 kWh', stock=50)

    def _devis_deux_options_sans_batterie(self):
        devis = self.devis_accepte([])
        for produit, variante in [(self.panneau, ''), (self.reseau, 'sans'),
                                  (self.hybride, 'avec'),
                                  (self.batterie, 'avec')]:
            LigneDevis.objects.create(
                devis=devis, produit=produit, designation=produit.nom,
                quantite=Decimal('1'), prix_unitaire=Decimal('1000'),
                variante=variante)
        devis.option_acceptee = Devis.OptionAcceptee.SANS_BATTERIE
        devis.save(update_fields=['option_acceptee'])
        return Devis.objects.get(pk=devis.pk)

    def _bc(self, devis):
        n = next(_seq)
        return BonCommande.objects.create(
            company=self.company, reference=f'BC-ASTK122-{n}', devis=devis,
            client=devis.client, statut=BonCommande.Statut.CONFIRME)

    def _skus_reserves(self, inst):
        return set(StockReservation.objects.filter(
            installation=inst, active=True).values_list(
            'produit_id', flat=True))

    def test_bc_ne_reserve_pas_l_option_non_retenue(self):
        devis = self._devis_deux_options_sans_batterie()
        inst, _ = create_installation_from_devis(
            devis, self.user, self.company)
        attendu = {self.reseau.id, self.panneau.id}
        self.assertEqual(self._skus_reserves(inst), attendu)
        bc = self._bc(devis)

        reserver_stock_depuis_bc(bc)
        self.assertEqual(self._skus_reserves(inst), attendu)

        consommer_reservation_bc(bc, self.user)
        for produit, stock in [(self.batterie, 50), (self.hybride, 50),
                               (self.reseau, 49), (self.panneau, 49)]:
            produit.refresh_from_db()
            self.assertEqual(produit.quantite_stock, stock, produit.nom)

    def test_devis_mono_option_inchange(self):
        devis = self.devis_accepte([(self.reseau, 1), (self.panneau, 10)])
        inst, _ = create_installation_from_devis(
            devis, self.user, self.company)
        reserver_stock_depuis_bc(self._bc(devis))
        self.assertEqual(
            {r.produit_id: r.quantite for r in StockReservation.objects
             .filter(installation=inst, active=True)},
            {self.reseau.id: 1, self.panneau.id: 10})


class ChantierMortTests(ResaBase):
    SLUG = 'co-astk124'

    def _chantier_mort_puis_reception(self, tuer):
        panneau = self.produit('Panneau ASTK124', stock=5)
        inst = self.chantier([(panneau, 20)])
        bon = self.bcf_du_manque(inst)
        tuer(inst)
        release_reservations(inst)
        self.assertFalse(self.resa(inst, panneau).active)
        self.confirmer_reception(bon, panneau, 10)
        return inst, panneau

    def test_reception_ne_reactive_pas_un_chantier_annule(self):
        def annuler(inst):
            Installation.objects.filter(pk=inst.pk).update(annule=True)
            inst.refresh_from_db()
        inst, panneau = self._chantier_mort_puis_reception(annuler)
        resa = self.resa(inst, panneau)
        self.assertFalse(resa.active)
        panneau.refresh_from_db()
        self.assertEqual(panneau.quantite_stock, 15)
        self.assertEqual(available_quantity(panneau), 15)

    def test_reception_ne_reactive_pas_un_chantier_cloture(self):
        def cloturer(inst):
            Installation.objects.filter(pk=inst.pk).update(
                statut=Installation.Statut.CLOTURE)
            inst.refresh_from_db()
        inst, panneau = self._chantier_mort_puis_reception(cloturer)
        self.assertFalse(self.resa(inst, panneau).active)

    def test_predicat(self):
        panneau = self.produit('Panneau ASTK124 B', stock=5)
        inst = self.chantier([(panneau, 1)])
        self.assertTrue(chantier_peut_reserver(inst))
        inst.annule = True
        self.assertFalse(chantier_peut_reserver(inst))
        inst.annule = False
        inst.statut = Installation.Statut.CLOTURE
        self.assertFalse(chantier_peut_reserver(inst))
        self.assertFalse(chantier_peut_reserver(None))


class AnnulationBcTests(ResaBase):
    SLUG = 'co-astk123'

    def _bc(self, devis):
        n = next(_seq)
        return BonCommande.objects.create(
            company=self.company, reference=f'BC-ASTK123-{n}', devis=devis,
            client=devis.client, statut=BonCommande.Statut.CONFIRME)

    def test_annuler_bc_garde_la_reservation_du_chantier_vivant(self):
        panneau = self.produit('Panneau ASTK123', stock=50)
        devis = self.devis_accepte([(panneau, 10)])
        inst, _ = create_installation_from_devis(
            devis, self.user, self.company)
        bc = self._bc(devis)
        reserver_stock_depuis_bc(bc)

        self.assertEqual(liberer_reservation_bc(bc), 0)
        resa = self.resa(inst, panneau)
        self.assertEqual((resa.active, resa.quantite), (True, 10))

        self.installer(inst)
        panneau.refresh_from_db()
        self.assertEqual(panneau.quantite_stock, 40)

    def test_chantier_annule_libere(self):
        panneau = self.produit('Panneau ASTK123 B', stock=50)
        devis = self.devis_accepte([(panneau, 10)])
        inst, _ = create_installation_from_devis(
            devis, self.user, self.company)
        bc = self._bc(devis)
        Installation.objects.filter(pk=inst.pk).update(annule=True)
        self.assertEqual(liberer_reservation_bc(bc), 1)
        self.assertFalse(self.resa(inst, panneau).active)


class ArrondiTests(ResaBase):
    SLUG = 'co-astk127'

    def test_demi_unite_arrondie_comme_la_facture(self):
        from apps.installations.field_capture import (
            _bom_quantities as besoin_terrain,
        )
        cable = self.produit('Câble 6mm² (m)', stock=100)
        gaine = self.produit('Gaine (m)', stock=100)
        inst = self.chantier([(cable, '12.5'), (gaine, '2.5')])
        self.assertEqual(self.resa(inst, cable).quantite, 13)
        self.assertEqual(self.resa(inst, gaine).quantite, 3)
        terrain = {pid: qte for (pid, _d), qte in besoin_terrain(inst).items()}
        self.assertEqual(terrain[cable.id], Decimal('13'))
        self.assertEqual(terrain[gaine.id], Decimal('3'))


class RetournableTests(ResaBase):
    SLUG = 'co-astk128'

    def test_retour_apres_installe(self):
        from apps.installations.models import (
            RetourMateriel, RetourMaterielLigne,
        )
        from apps.stock.models import MouvementStock
        panneau = self.produit('Panneau ASTK128', stock=30)
        inst = self.chantier([(panneau, 10)])
        self.installer(inst)
        panneau.refresh_from_db()
        self.assertEqual(panneau.quantite_stock, 20)
        self.assertEqual(quantite_retournable(inst, panneau.id), 10)

        retour = RetourMateriel.objects.create(
            company=self.company, installation=inst, created_by=self.user)
        RetourMaterielLigne.objects.create(
            retour=retour, produit=panneau, designation=panneau.nom,
            quantite=Decimal('1'))
        self.assertEqual(valider_retour_materiel(retour, self.user), 1)
        retour.refresh_from_db()
        self.assertEqual(retour.statut, RetourMateriel.Statut.VALIDE)
        panneau.refresh_from_db()
        self.assertEqual(panneau.quantite_stock, 21)
        self.assertTrue(MouvementStock.objects.filter(
            produit=panneau, reference=f'RETOUR-{inst.reference}',
            type_mouvement=MouvementStock.TypeMouvement.ENTREE,
            quantite=1).exists())
        self.assertEqual(quantite_retournable(inst, panneau.id), 9)

    def test_reservation_soldee_par_une_vente_compte(self):
        panneau = self.produit('Panneau ASTK128 B', stock=30)
        inst = self.chantier([(panneau, 10)])
        solder_reservations_vente(inst, {panneau.id: 10}, 'FAC-ASTK128')
        self.installer(inst)
        self.assertEqual(quantite_retournable(inst, panneau.id), 10)
