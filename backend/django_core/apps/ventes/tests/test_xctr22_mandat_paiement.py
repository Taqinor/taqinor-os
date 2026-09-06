"""XCTR22 — Encaissement récurrent automatique des abonnements (tokenisation
carte / mandat) + dunning carte.

Couvre (avec le provider `mock_tokenized`, aucun réseau) :
  * mandat enregistré → un cycle débité automatiquement crée un Paiement
    rapproché sur la facture ;
  * jamais deux débits RÉUSSIS pour la même période (idempotence) ;
  * échec de débit → entrée d'exception (TentativeDebitMandat 'echec') avec
    retentative programmée (J+1/J+3/J+7) ;
  * révocation du mandat → retour immédiat à l'encaissement manuel (aucun
    débit tenté) ;
  * sans mandat actif (aucune config) → no-op complet, comportement inchangé ;
  * aucun PAN en base (test de schéma — seul un token opaque + 4 derniers
    chiffres sont stockés).
"""
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from authentication.models import Company
from apps.crm.models import Client
from apps.ventes.models import (
    Facture, MandatPaiement, TentativeDebitMandat, Paiement,
)
from apps.ventes.services import (
    debiter_mandat_pour_facture, mandat_actif_pour_client,
)


def make_company(slug='xctr22-co', nom='XCTR22 Co'):
    return Company.objects.get_or_create(slug=slug, defaults={'nom': nom})[0]


class Xctr22TestBase(TestCase):
    def setUp(self):
        self.company = make_company()
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='XCTR22',
            telephone='+212600000022')
        self.facture = Facture.objects.create(
            company=self.company, reference='FAC-XCTR22-0001',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20.00'), montant_ttc=Decimal('1200.00'))

    def _mandat(self, **extra):
        defaults = dict(
            company=self.company, client=self.client_obj,
            provider='mock_tokenized', token='TOK-ABC123',
            derniers_chiffres='4242', expiration_mois='12/2028',
            statut=MandatPaiement.Statut.ACTIF,
            consentement_horodate=timezone.now(),
        )
        defaults.update(extra)
        return MandatPaiement.objects.create(**defaults)


class TestSansMandat(Xctr22TestBase):
    def test_sans_mandat_noop(self):
        self.assertIsNone(mandat_actif_pour_client(self.client_obj))
        result = debiter_mandat_pour_facture(
            facture=self.facture, periode='2026-07')
        self.assertIsNone(result)
        self.assertFalse(Paiement.objects.filter(facture=self.facture).exists())


class TestDebitReussi(Xctr22TestBase):
    def test_debit_cree_paiement_rapproche(self):
        self._mandat()
        paiement = debiter_mandat_pour_facture(
            facture=self.facture, periode='2026-07')
        self.assertIsNotNone(paiement)
        self.assertEqual(paiement.montant, Decimal('1200.00'))
        self.assertEqual(paiement.mode, Paiement.Mode.CARTE)
        tentative = TentativeDebitMandat.objects.get(
            mandat__client=self.client_obj, periode='2026-07')
        self.assertEqual(tentative.statut, TentativeDebitMandat.Statut.REUSSI)

    def test_trois_cycles_trois_paiements_zero_doublon(self):
        self._mandat()
        # AUD123 — le débit est désormais BORNÉ au reste dû. Trois cycles, ce
        # sont donc trois FACTURES (une par période), comme en facturation
        # récurrente réelle : rejouer la MÊME facture déjà soldée ne prélève
        # plus rien, et c'est exactement le double-prélèvement que AUD123 ferme.
        factures = [self.facture] + [
            Facture.objects.create(
                company=self.company, reference=f'FAC-XCTR22-000{n}',
                client=self.client_obj, statut=Facture.Statut.EMISE,
                taux_tva=Decimal('20.00'), montant_ttc=Decimal('1200.00'))
            for n in (2, 3)
        ]
        paiements = [
            debiter_mandat_pour_facture(facture=f, periode=p)
            for f, p in zip(factures, ('2026-05', '2026-06', '2026-07'))
        ]
        self.assertNotIn(None, paiements)
        self.assertEqual(
            {p.id for p in paiements},
            set(Paiement.objects.filter(
                facture__in=factures).values_list('id', flat=True)))
        self.assertEqual(
            Paiement.objects.filter(facture__in=factures).count(), 3)

    def test_jamais_deux_debits_reussis_meme_periode(self):
        self._mandat()
        p1 = debiter_mandat_pour_facture(facture=self.facture, periode='2026-07')
        p2 = debiter_mandat_pour_facture(facture=self.facture, periode='2026-07')
        self.assertIsNotNone(p1)
        self.assertIsNone(p2)  # déjà réussie → no-op, pas de second Paiement
        self.assertEqual(
            TentativeDebitMandat.objects.filter(
                mandat__client=self.client_obj, periode='2026-07',
                statut=TentativeDebitMandat.Statut.REUSSI).count(),
            1)


class TestDebitEchecEtDunning(Xctr22TestBase):
    def test_echec_cree_exception_avec_retentative(self):
        self._mandat(token='FAIL')  # le mock refuse ce token
        result = debiter_mandat_pour_facture(
            facture=self.facture, periode='2026-07')
        self.assertIsNone(result)
        tentative = TentativeDebitMandat.objects.get(
            mandat__client=self.client_obj, periode='2026-07')
        self.assertEqual(tentative.statut, TentativeDebitMandat.Statut.ECHEC)
        self.assertTrue(tentative.motif_echec)
        self.assertIsNotNone(tentative.prochaine_retentative)
        jours = (tentative.prochaine_retentative
                 - timezone.localdate()).days
        self.assertEqual(jours, 1)  # premier échec → J+1

    def test_retentatives_espacees_j1_j3_j7(self):
        self._mandat(token='FAIL')
        for _ in range(3):
            debiter_mandat_pour_facture(facture=self.facture, periode='2026-07')
        tentatives = list(TentativeDebitMandat.objects.filter(
            mandat__client=self.client_obj, periode='2026-07',
        ).order_by('id'))
        deltas = [
            (t.prochaine_retentative - timezone.localdate()).days
            for t in tentatives
        ]
        self.assertEqual(deltas, [1, 3, 7])


class TestRevocationMandat(Xctr22TestBase):
    def test_revocation_stoppe_les_debits(self):
        mandat = self._mandat()
        mandat.statut = MandatPaiement.Statut.REVOQUE
        mandat.revoked_at = timezone.now()
        mandat.save(update_fields=['statut', 'revoked_at'])

        self.assertIsNone(mandat_actif_pour_client(self.client_obj))
        result = debiter_mandat_pour_facture(
            facture=self.facture, periode='2026-07')
        self.assertIsNone(result)
        self.assertFalse(Paiement.objects.filter(facture=self.facture).exists())


class TestSchemaAucunPan(Xctr22TestBase):
    def test_aucun_champ_pan_sur_le_modele(self):
        field_names = {f.name for f in MandatPaiement._meta.get_fields()}
        for interdit in ('pan', 'numero_carte', 'card_number', 'cvv', 'cvc'):
            self.assertNotIn(interdit, field_names)
        # Seuls token opaque + 4 derniers chiffres/expiration sont stockés.
        self.assertIn('token', field_names)
        self.assertIn('derniers_chiffres', field_names)

    def test_derniers_chiffres_longueur_bornee(self):
        mandat = self._mandat()
        self.assertLessEqual(len(mandat.derniers_chiffres), 4)


class TestAUD123MontantDebite(Xctr22TestBase):
    """AUD123 — le montant prélevé était lu sur `montant_ttc`, NULL pour
    toute facture à lignes, et n'était jamais borné au reste dû.

    Deux cas, tous deux ROUGES avant le correctif :
      1. facture classique à lignes de 12 000 TTC → le débit valait
         `None` (`montant_ttc` NULL) au lieu de 12 000 ;
      2. facture dont 5 000 sont déjà réglés → le TTC intégral était
         prélevé une seconde fois au lieu du reste dû.
    """

    def _facture_a_lignes(self, reference='FAC-AUD123-0001'):
        """Facture CLASSIQUE (montant_ttc NULL) : 10 × 1 000 HT à 20 % de
        TVA = 10 000 HT + 2 000 TVA = 12 000 TTC, dérivés des lignes."""
        from apps.stock.models import Produit
        from apps.ventes.models import LigneFacture
        produit = Produit.objects.create(
            company=self.company, nom='Abonnement supervision',
            sku=f'AUD123-{reference[-4:]}', prix_vente=Decimal('1000'),
            quantite_stock=100, tva=Decimal('20.00'))
        facture = Facture.objects.create(
            company=self.company, reference=reference,
            client=self.client_obj, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20.00'))
        LigneFacture.objects.create(
            facture=facture, produit=produit,
            designation='Abonnement supervision', quantite=Decimal('10'),
            prix_unitaire=Decimal('1000'), taux_tva=Decimal('20.00'))
        facture.refresh_from_db()
        self.assertIsNone(facture.montant_ttc)
        self.assertEqual(facture.total_ttc, Decimal('12000.00'))
        return facture

    def test_facture_a_lignes_debite_le_ttc_reel(self):
        self._mandat()
        facture = self._facture_a_lignes()
        paiement = debiter_mandat_pour_facture(
            facture=facture, periode='2026-05')
        self.assertIsNotNone(paiement)
        self.assertEqual(paiement.montant, Decimal('12000.00'))

    def test_debit_borne_au_reste_du(self):
        self._mandat()
        facture = self._facture_a_lignes(reference='FAC-AUD123-0002')
        Paiement.objects.create(
            company=self.company, facture=facture,
            montant=Decimal('5000.00'), date_paiement=timezone.now().date(),
            mode=Paiement.Mode.VIREMENT)
        facture.refresh_from_db()
        self.assertEqual(facture.montant_du, Decimal('7000.00'))
        paiement = debiter_mandat_pour_facture(
            facture=facture, periode='2026-06')
        self.assertIsNotNone(paiement)
        self.assertEqual(paiement.montant, Decimal('7000.00'))

    def test_facture_deja_soldee_aucun_debit(self):
        self._mandat()
        facture = self._facture_a_lignes(reference='FAC-AUD123-0003')
        Paiement.objects.create(
            company=self.company, facture=facture,
            montant=Decimal('12000.00'), date_paiement=timezone.now().date(),
            mode=Paiement.Mode.VIREMENT)
        facture.refresh_from_db()
        self.assertEqual(facture.montant_du, Decimal('0'))
        self.assertIsNone(debiter_mandat_pour_facture(
            facture=facture, periode='2026-07'))


class TestAudv18CreerFactureContratDebiteLeMandat(Xctr22TestBase):
    """AUDV18 — branchement additif XCTR22 : le chemin RÉEL de facturation
    récurrente des contrats de maintenance (``sav.services.
    facturer_contrat_maintenance_beat`` → ``facturer_contrat_maintenance`` →
    ``ventes.services.creer_facture_contrat``) doit tenter le débit du
    mandat actif du client juste après avoir émis la facture. Le branchement
    vit dans ``facturer_contrat_maintenance`` (APRÈS la ligne d'usage XCTR16
    éventuelle, AUD151 — jamais dans ``creer_facture_contrat`` lui-même, qui
    ignore encore l'usage à ce stade), mais ce test couvre le chemin PUBLIC
    de bout en bout, pas un point d'appel interne précis. ROUGE avant ce
    correctif : le débit n'était jamais tenté depuis ce chemin, malgré le
    docstring de ``debiter_mandat_pour_facture`` l'annonçant explicitement."""

    def _contrat_maintenance(self, **extra):
        from datetime import date
        from apps.sav.models import ContratMaintenance
        defaults = dict(
            company=self.company, client=self.client_obj,
            periodicite='annuel', date_debut=date(2024, 1, 1),
            actif=True, prix=Decimal('3000'), facturation_active=True,
            derniere_facturation=None)
        defaults.update(extra)
        return ContratMaintenance.objects.create(**defaults)

    def test_beat_maintenance_debite_le_mandat_actif(self):
        from apps.sav import services as sav_services
        self._mandat()
        contrat = self._contrat_maintenance()
        facture = sav_services.facturer_contrat_maintenance_beat(contrat)
        facture.refresh_from_db()
        self.assertEqual(facture.statut, Facture.Statut.PAYEE)
        paiement = Paiement.objects.get(facture=facture)
        self.assertEqual(paiement.mode, Paiement.Mode.CARTE)
        tentative = TentativeDebitMandat.objects.get(
            mandat__client=self.client_obj,
            periode=timezone.localdate().strftime('%Y-%m'))
        self.assertEqual(
            tentative.statut, TentativeDebitMandat.Statut.REUSSI)

    def test_beat_maintenance_sans_mandat_comportement_inchange(self):
        from apps.sav import services as sav_services
        contrat = self._contrat_maintenance()
        facture = sav_services.facturer_contrat_maintenance_beat(contrat)
        facture.refresh_from_db()
        self.assertEqual(facture.statut, Facture.Statut.EMISE)
        self.assertFalse(Paiement.objects.filter(facture=facture).exists())
