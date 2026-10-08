"""CIQ213 — variante « règlement par l'organisme financeur à la réception
signée » : un payeur tiers sur le devis, les tranches qui lui reviennent lui
sont facturées, la chaîne devis → BC → facture reste 1:1.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.ventes.tests.test_ciq213_tiers_payeur"
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.ventes.utils.echeancier import (
    EcheancierInvalide, LIBELLE_FINANCEUR, modele_financeur,
    valider_echeancier)

User = get_user_model()


class ModeleFinanceurTest(SimpleTestCase):
    def test_zero_cent_une_seule_tranche_tiers(self):
        tranches = modele_financeur(None, 0)
        self.assertEqual(len(tranches), 1)
        self.assertEqual(tranches[0]['payeur'], 'tiers')
        self.assertEqual(tranches[0]['jalon'], 'reception_financeur')
        self.assertEqual(tranches[0]['pct_or_montant'], 100)

    def test_dix_quatre_vingt_dix(self):
        tranches = modele_financeur(None, 10)
        self.assertEqual([(t['payeur'], t['pct_or_montant']) for t in tranches],
                         [('client', 10), ('tiers', 90)])
        # Forme d'échéancier valide (même validation que l'écriture).
        self.assertEqual(len(valider_echeancier(tranches)), 2)

    def test_jamais_credit_bail(self):
        self.assertNotIn('crédit-bail', LIBELLE_FINANCEUR.lower())
        self.assertIn('organisme financeur', LIBELLE_FINANCEUR)

    def test_acompte_hors_bornes_refuse(self):
        with self.assertRaises(EcheancierInvalide):
            modele_financeur(None, 120)


class _Base(TestCase):
    def setUp(self):
        from apps.crm.models import Client
        from authentication.models import Company
        self.company = Company.objects.get_or_create(
            slug='ciq213-co', defaults={'nom': 'CIQ213 Co'})[0]
        self.autre = Company.objects.get_or_create(
            slug='ciq213-autre', defaults={'nom': 'CIQ213 Autre'})[0]
        self.client_final = Client.objects.create(
            company=self.company, nom='Clinique', prenom='CIQ213',
            email='ciq213@example.com')
        self.financeur = Client.objects.create(
            company=self.company, nom='Organisme', prenom='Financeur',
            email='financeur@example.com')
        self.financeur_etranger = Client.objects.create(
            company=self.autre, nom='Etranger', prenom='Financeur',
            email='etranger@example.com')
        self.user = User.objects.create_user(
            username='ciq213_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def _devis(self, ref, acompte, tiers=True, statut='accepte'):
        from apps.ventes.models import Devis, LigneDevis
        devis = Devis.objects.create(
            company=self.company, reference=ref, client=self.client_final,
            statut=statut, taux_tva=Decimal('20.00'),
            mode_installation='commercial',
            tiers_payeur=self.financeur if tiers else None,
            echeancier=modele_financeur(None, acompte))
        LigneDevis.objects.create(
            devis=devis, designation='Centrale PV', quantite=Decimal('1'),
            prix_unitaire=Decimal('10000.01'), remise=Decimal('0'),
            taux_tva=Decimal('20.00'))
        return devis

    def _generer(self, devis):
        return self.api.post(
            f'/api/django/ventes/devis/{devis.id}/generer-facture/')


class FacturationFinanceurTest(_Base):
    def test_zero_cent_une_facture_au_financeur(self):
        from apps.ventes.models import Facture
        devis = self._devis('DEV-CIQ213-0010', 0)
        r = self._generer(devis)
        self.assertEqual(r.status_code, 201, r.data)
        facture = Facture.objects.get(pk=r.data['id'])
        self.assertEqual(facture.client_id, self.financeur.id)
        self.assertEqual(facture.devis_id, devis.id)
        self.assertEqual(self._generer(devis).status_code, 400)

    def test_dix_quatre_vingt_dix_somme_au_centime(self):
        from apps.ventes.models import Facture
        from apps.ventes.utils.options import option_totaux
        devis = self._devis('DEV-CIQ213-0020', 10)
        r1, r2 = self._generer(devis), self._generer(devis)
        self.assertEqual(r1.status_code, 201, r1.data)
        self.assertEqual(r2.status_code, 201, r2.data)
        f1 = Facture.objects.get(pk=r1.data['id'])
        f2 = Facture.objects.get(pk=r2.data['id'])
        self.assertEqual(f1.client_id, self.client_final.id)
        self.assertEqual(f2.client_id, self.financeur.id)
        self.assertEqual(
            Decimal(r1.data['total_ttc']) + Decimal(r2.data['total_ttc']),
            Decimal(str(option_totaux(devis)['ttc'])))

    def test_tranche_tiers_sans_tiers_refusee_en_francais(self):
        from apps.ventes.utils.echeancier import creer_facture_tranche
        from apps.ventes.utils.references import create_with_reference
        devis = self._devis('DEV-CIQ213-0030', 0, tiers=False)
        with self.assertRaises(ValueError) as ctx:
            creer_facture_tranche(devis, self.user, self.company,
                                  create_with_reference)
        self.assertIn('organisme financeur', str(ctx.exception))

    def test_double_porte_aud112_respectee(self):
        # ATOT2 — la porte tranche passe par LA garde unique
        # `exiger_devis_facturable` (`factures_du_devis`, quatre portes) et
        # non plus par `factures_via_bon_commande` : on rejoue la double porte
        # AUD112 sur une VRAIE facture de bon de commande, sans mock.
        from apps.ventes.models import BonCommande, Facture
        from apps.ventes.selectors_facturation import DevisDejaFacture
        from apps.ventes.utils import echeancier
        devis = self._devis('DEV-CIQ213-0040', 10)
        bc = BonCommande.objects.create(
            company=self.company, reference='BC-CIQ213-0040', devis=devis,
            client=self.client_final, statut=BonCommande.Statut.CONFIRME)
        Facture.objects.create(
            company=self.company, reference='FAC-CIQ213-BC-0040',
            client=self.client_final, bon_commande=bc, devis=devis,
            statut=Facture.Statut.EMISE, taux_tva=Decimal('20'))
        with self.assertRaises(DevisDejaFacture) as ctx:
            echeancier.creer_facture_tranche(
                devis, self.user, self.company, lambda *a, **k: None)
        self.assertIn('FAC-CIQ213-BC-0040', str(ctx.exception))
        self.assertEqual(Facture.objects.filter(devis=devis).count(), 1)


class TiersPayeurApiTest(_Base):
    def test_tiers_d_une_autre_societe_400(self):
        devis = self._devis('DEV-CIQ213-0050', 10, tiers=False,
                            statut='brouillon')
        r = self.api.patch(f'/api/django/ventes/devis/{devis.id}/',
                           {'tiers_payeur': self.financeur_etranger.id},
                           format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('tiers_payeur', r.data)

    def test_tiers_de_la_societe_accepte(self):
        devis = self._devis('DEV-CIQ213-0060', 10, tiers=False,
                            statut='brouillon')
        r = self.api.patch(f'/api/django/ventes/devis/{devis.id}/',
                           {'tiers_payeur': self.financeur.id},
                           format='json')
        self.assertEqual(r.status_code, 200, r.data)
        devis.refresh_from_db()
        self.assertEqual(devis.tiers_payeur_id, self.financeur.id)
