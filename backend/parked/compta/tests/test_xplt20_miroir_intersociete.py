"""XPLT20 — Écritures inter-sociétés miroir (vente A → achat B).

Couvre :
  * sans ``RegleInterSociete`` active, ``facture_emise`` ne génère RIEN
    (comportement inchangé) ;
  * avec une règle active + ICE du client de A == ICE de B + Fournisseur B
    existant pour A (par ICE) : un ``FactureFournisseur`` BROUILLON est
    généré chez B avec les bons montants, jamais auto-validé ;
  * idempotence : ré-émettre le même signal ne duplique pas le miroir ;
  * pas de fiche fournisseur chez B pour A → NO-OP (jamais de création
    silencieuse d'un tiers hors du groupe) ;
  * isolation : un tiers hors du groupe (ICE ne matchant aucune règle) ne
    génère rien.
"""
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company
from apps.compta import receivers  # noqa: F401 (câblage ready())
from apps.compta.models import EcritureLiaisonInterSociete, RegleInterSociete
from apps.crm.models import Client
from apps.parametres.models_company import CompanyProfile
from apps.stock.models import FactureFournisseur, Fournisseur, Produit
from apps.ventes.models import Facture, LigneFacture
from apps.ventes import receivers as ventes_receivers  # noqa: F401
from core.events import facture_emise


def make_company(slug, nom):
    return Company.objects.get_or_create(slug=slug, defaults={'nom': nom})[0]


class TestXPLT20MiroirIntersociete(TestCase):
    def setUp(self):
        self.societe_a = make_company('xplt20-sarl', 'SARL A')
        self.societe_b = make_company('xplt20-ei', 'EI B')
        CompanyProfile.objects.update_or_create(
            company=self.societe_a, defaults={'ice': 'ICE-A-0001'})
        CompanyProfile.objects.update_or_create(
            company=self.societe_b, defaults={'ice': 'ICE-B-0001'})
        # Le client de A représentant B (même ICE que le CompanyProfile de B).
        self.client_b = Client.objects.create(
            company=self.societe_a, nom='EI B (client interne)',
            email='b@intersociete.example', ice='ICE-B-0001')
        # B a déjà une fiche fournisseur pour A (même ICE que CompanyProfile A).
        self.fournisseur_a = Fournisseur.objects.create(
            company=self.societe_b, nom='SARL A (fournisseur interne)',
            ice='ICE-A-0001')
        self.produit = Produit.objects.create(
            company=self.societe_a, nom='Prestation inter-sociétés',
            sku='XPLT20-PREST', prix_vente=Decimal('1000'),
            quantite_stock=10, tva=Decimal('20.00'))

    def _facture(self, ref='FAC-XPLT20-0001', montant_ht='1000.00',
                 taux_tva='20.00', client=None):
        facture = Facture.objects.create(
            company=self.societe_a, reference=ref,
            client=client or self.client_b, statut=Facture.Statut.EMISE,
            taux_tva=Decimal(taux_tva))
        LigneFacture.objects.create(
            facture=facture, produit=self.produit,
            designation='Prestation inter-sociétés',
            quantite=Decimal('1'), prix_unitaire=Decimal(montant_ht),
            taux_tva=Decimal(taux_tva))
        return facture

    def test_no_rule_no_mirror(self):
        facture = self._facture()
        facture_emise.send(
            sender=Facture, instance=facture, company=self.societe_a)
        self.assertEqual(EcritureLiaisonInterSociete.objects.count(), 0)
        self.assertEqual(
            FactureFournisseur.objects.filter(
                company=self.societe_b).count(), 0)

    def test_active_rule_generates_draft_mirror_with_correct_amounts(self):
        RegleInterSociete.objects.create(
            societe_a=self.societe_a, societe_b=self.societe_b,
            actif=True, compte_liaison='4468')
        facture = self._facture(montant_ht='1000.00', taux_tva='20.00')
        facture_emise.send(
            sender=Facture, instance=facture, company=self.societe_a)

        liaisons = EcritureLiaisonInterSociete.objects.filter(
            facture_source_id=facture.id)
        self.assertEqual(liaisons.count(), 1)
        liaison = liaisons.first()
        self.assertEqual(liaison.compte_liaison, '4468')
        self.assertEqual(liaison.montant_ht, Decimal('1000.00'))
        self.assertEqual(liaison.montant_ttc, Decimal('1200.00'))

        miroir = FactureFournisseur.objects.get(
            id=liaison.facture_fournisseur_miroir_id)
        self.assertEqual(miroir.company_id, self.societe_b.id)
        self.assertEqual(miroir.fournisseur_id, self.fournisseur_a.id)
        self.assertEqual(miroir.ref_fournisseur, facture.reference)
        self.assertEqual(miroir.montant_ttc, Decimal('1200.00'))
        # Jamais d'auto-validation : aucun statut « validé »/paiement créé.
        self.assertEqual(miroir.statut, FactureFournisseur.Statut.A_PAYER)

    def test_disabled_rule_is_a_no_op(self):
        RegleInterSociete.objects.create(
            societe_a=self.societe_a, societe_b=self.societe_b,
            actif=False, compte_liaison='4468')
        facture = self._facture()
        facture_emise.send(
            sender=Facture, instance=facture, company=self.societe_a)
        self.assertEqual(EcritureLiaisonInterSociete.objects.count(), 0)

    def test_idempotent_on_repeated_signal(self):
        RegleInterSociete.objects.create(
            societe_a=self.societe_a, societe_b=self.societe_b,
            actif=True, compte_liaison='4468')
        facture = self._facture()
        facture_emise.send(
            sender=Facture, instance=facture, company=self.societe_a)
        facture_emise.send(
            sender=Facture, instance=facture, company=self.societe_a)
        self.assertEqual(
            EcritureLiaisonInterSociete.objects.filter(
                facture_source_id=facture.id).count(), 1)
        self.assertEqual(
            FactureFournisseur.objects.filter(
                company=self.societe_b).count(), 1)

    def test_no_fournisseur_at_b_is_a_no_op_never_creates_tiers(self):
        self.fournisseur_a.delete()
        RegleInterSociete.objects.create(
            societe_a=self.societe_a, societe_b=self.societe_b,
            actif=True, compte_liaison='4468')
        facture = self._facture()
        facture_emise.send(
            sender=Facture, instance=facture, company=self.societe_a)
        self.assertEqual(EcritureLiaisonInterSociete.objects.count(), 0)
        self.assertEqual(Fournisseur.objects.filter(
            company=self.societe_b).count(), 0)

    def test_third_party_outside_group_never_leaks(self):
        RegleInterSociete.objects.create(
            societe_a=self.societe_a, societe_b=self.societe_b,
            actif=True, compte_liaison='4468')
        exterieur = Client.objects.create(
            company=self.societe_a, nom='Client externe',
            email='ext@example.com', ice='ICE-EXTERIEUR-9999')
        facture = self._facture(
            ref='FAC-XPLT20-EXT', montant_ht='500.00', client=exterieur)
        facture_emise.send(
            sender=Facture, instance=facture, company=self.societe_a)
        self.assertEqual(EcritureLiaisonInterSociete.objects.count(), 0)
        self.assertEqual(
            FactureFournisseur.objects.filter(
                company=self.societe_b).count(), 0)
