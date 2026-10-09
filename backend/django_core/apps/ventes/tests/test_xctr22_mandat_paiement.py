"""XCTR22 — Encaissement récurrent automatique (AFAC19 : pile PARQUÉE — seuls
les cas MODÈLE restent ; débit, dunning et révocation retirés avec le service)
— des abonnements (tokenisation
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
from apps.ventes.models import Facture, MandatPaiement


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
