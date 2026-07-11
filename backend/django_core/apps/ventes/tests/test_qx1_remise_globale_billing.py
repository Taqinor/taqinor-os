"""QX1 — la remise globale atteint TOUTE la chaîne de facturation.

Avant QX1, ``remise_globale`` n'était appliquée que sur le PDF client : la
facture, l'échéancier et le bon de commande facturaient le montant BRUT →
sur-facturation. Ces tests prouvent l'égalité au centime :

    TTC remisé de l'option acceptée
      == Σ des factures d'échéancier
      == total de la facture issue du bon de commande
      == totaux du PDF BC (chaîne canonique)

pour 1 option et 2 options, avec et sans remise par-ligne.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company
from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import (
    BonCommande, Facture, LigneFacture, Devis, LigneDevis,
)
from apps.ventes.utils.options import option_totaux
from apps.ventes.utils.echeancier import (
    creer_facture_tranche, next_tranche,
)
from apps.ventes.selectors import _canonical_totaux
from apps.ventes.utils.references import create_with_reference

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


def _q(x):
    return Decimal(x).quantize(Decimal('0.01'))


class Qx1RemiseGlobaleBillingTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='qx1-co', defaults={'nom': 'QX1 Co'})
        self.user = User.objects.create_user(
            username='qx1_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='QX1',
            telephone='+212600000041')

    def _devis(self, lignes, *, remise_globale='0', num=1, taux='20',
               option=None):
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-QX1{num:03d}',
            client=self.client_obj, statut=Devis.Statut.ACCEPTE,
            taux_tva=Decimal(taux), remise_globale=Decimal(remise_globale))
        if option:
            devis.option_acceptee = option
            devis.save(update_fields=['option_acceptee'])
        for i, (desig, qty, pu, lr) in enumerate(lignes):
            produit = Produit.objects.create(
                company=self.company, nom=desig, sku=f'QX1{num}-{i}',
                prix_vente=Decimal(pu), prix_achat=Decimal('1'),
                quantite_stock=100)
            LigneDevis.objects.create(
                devis=devis, produit=produit, designation=desig,
                quantite=Decimal(qty), prix_unitaire=Decimal(pu),
                remise=Decimal(lr))
        return devis

    def _facture_from_bc(self, devis, num):
        bc = BonCommande.objects.create(
            company=self.company, reference=f'BC-QX1-{num:04d}',
            client=self.client_obj, devis=devis,
            statut=BonCommande.Statut.CONFIRME)
        facture = Facture.objects.create(
            reference=f'FAC-{MONTH}-QX1{num:03d}', bon_commande=bc,
            client=self.client_obj, statut=Facture.Statut.BROUILLON,
            created_by=self.user, company=self.company)
        # Reproduit EXACTEMENT la logique de creer_facture (QX1) : persiste
        # remise_globale + copie les lignes de l'option.
        from apps.ventes.utils.options import option_lines
        g = Decimal(str(devis.remise_globale or 0))
        if g:
            facture.remise_globale = g
            facture.save(update_fields=['remise_globale'])
        for ligne in option_lines(devis):
            LigneFacture.objects.create(
                facture=facture, produit=ligne.produit,
                designation=ligne.designation, quantite=ligne.quantite,
                prix_unitaire=ligne.prix_unitaire, remise=ligne.remise,
                taux_tva=ligne.taux_tva)
        return facture

    def _assert_chain(self, devis, num):
        """Le TTC remisé de référence == BC facture == Σ échéancier."""
        ref = option_totaux(devis)
        ref_ttc = _q(ref['ttc'])

        # 1) Facture issue du BC.
        facture = self._facture_from_bc(devis, num)
        facture.refresh_from_db()
        self.assertEqual(_q(facture.total_ttc), ref_ttc,
                         'BC facture TTC != TTC remisé')

        # 2) Σ des factures d'échéancier (30/60/10 par défaut).
        somme = Decimal('0')
        while next_tranche(devis) is not None:
            f = creer_facture_tranche(
                devis, self.user, self.company, create_with_reference)
            somme += Decimal(str(f.total_ttc))
        self.assertEqual(_q(somme), ref_ttc,
                         'Σ échéancier != TTC remisé')

        # 3) Le TTC remisé de référence = chaîne canonique directe SUR LES
        #    MÊMES lignes que option_totaux (l'option acceptée pour un devis à
        #    deux options — sinon toutes les lignes). Comparer la canonique
        #    toutes-lignes au total de l'option acceptée était faux en 2-options.
        from apps.ventes.utils.options import (
            filter_lines_for_option, has_two_options,
        )
        opt = getattr(devis, 'option_acceptee', '') or ''
        lignes = (
            filter_lines_for_option(list(devis.lignes.all()), opt)
            if opt and has_two_options(devis)
            else list(devis.lignes.all()))
        can = _canonical_totaux(
            lignes, remise_globale_pct=devis.remise_globale,
            fallback_taux=devis.taux_tva)
        self.assertEqual(_q(can['ttc']), ref_ttc)

    def test_single_option_with_global_remise(self):
        # 10×1000 + 5×2000 = 20000 HT ; remise 15 % → 17000 HT ; TTC 20400.
        devis = self._devis(
            [('Panneau', '10', '1000', '0'), ('Onduleur', '5', '2000', '0')],
            remise_globale='15', num=1)
        ref = option_totaux(devis)
        self.assertEqual(_q(ref['ht']), Decimal('17000.00'))
        self.assertEqual(_q(ref['ttc']), Decimal('20400.00'))
        self._assert_chain(devis, num=1)

    def test_single_option_no_remise_unchanged(self):
        devis = self._devis(
            [('Panneau', '10', '1000', '0')], remise_globale='0', num=2)
        ref = option_totaux(devis)
        # Sans remise : total = somme des lignes, comportement historique.
        self.assertEqual(_q(ref['ht']), Decimal('10000.00'))
        self.assertEqual(_q(ref['ttc']), Decimal('12000.00'))
        self._assert_chain(devis, num=2)

    def test_with_per_line_remise_and_global(self):
        # Ligne remisée 10 % : 10×1000×0.9 = 9000 ; + 5×2000 = 10000 → 19000 HT
        # remise globale 20 % → 15200 HT ; TTC 18240.
        devis = self._devis(
            [('Panneau', '10', '1000', '10'),
             ('Onduleur', '5', '2000', '0')],
            remise_globale='20', num=3)
        ref = option_totaux(devis)
        self.assertEqual(_q(ref['ht']), Decimal('15200.00'))
        self.assertEqual(_q(ref['ttc']), Decimal('18240.00'))
        self._assert_chain(devis, num=3)

    def test_two_option_with_global_remise(self):
        devis = self._devis(
            [('Onduleur réseau', '1', '11700', '0'),
             ('Onduleur hybride', '1', '24000', '0'),
             ('Panneau mono 550W', '14', '1100', '0'),
             ('Batterie 5 kWh', '1', '14000', '0'),
             ('Installation', '1', '4000', '0')],
            remise_globale='10', num=4, option='sans_batterie')
        # sans batterie : 11700 + 15400 + 4000 = 31100 HT ; −10 % = 27990 HT ;
        # TTC 33588.
        ref = option_totaux(devis)
        self.assertEqual(_q(ref['ht']), Decimal('27990.00'))
        self.assertEqual(_q(ref['ttc']), Decimal('33588.00'))
        self._assert_chain(devis, num=4)

    def test_facture_no_remise_is_line_sum(self):
        """Une facture SANS remise globale garde total = somme des lignes."""
        devis = self._devis(
            [('Panneau', '3', '1000', '0')], remise_globale='0', num=5)
        facture = self._facture_from_bc(devis, num=5)
        facture.refresh_from_db()
        self.assertEqual(facture.remise_globale, Decimal('0'))
        self.assertEqual(_q(facture.total_ht), Decimal('3000.00'))
        self.assertEqual(_q(facture.total_ttc), Decimal('3600.00'))
