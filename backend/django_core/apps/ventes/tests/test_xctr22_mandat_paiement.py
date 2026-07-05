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
        p1 = debiter_mandat_pour_facture(facture=self.facture, periode='2026-05')
        p2 = debiter_mandat_pour_facture(facture=self.facture, periode='2026-06')
        p3 = debiter_mandat_pour_facture(facture=self.facture, periode='2026-07')
        self.assertEqual(
            {p1.id, p2.id, p3.id},
            set(Paiement.objects.filter(
                facture=self.facture).values_list('id', flat=True)))
        self.assertEqual(Paiement.objects.filter(facture=self.facture).count(), 3)

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
