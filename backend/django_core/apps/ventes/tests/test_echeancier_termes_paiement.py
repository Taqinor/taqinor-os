"""QJR622 — la correspondance « échéancier du devis → acompte / matériel /
solde » vit dans ``utils.echeancier.termes_paiement_devis``.

Elle était écrite EN LIGNE dans ``public_views._conditions_publiques`` ; le
PDF (QJR623) en a besoin aussi : une seule correspondance, deux lecteurs.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.ventes.tests.test_echeancier_termes_paiement"
"""
from decimal import Decimal

from django.test import TestCase

from apps.crm.models import Client
from apps.ventes.models import Devis


def _company():
    from authentication.models import Company
    c, _ = Company.objects.get_or_create(
        slug='test-qjr622-co', defaults={'nom': 'Test QJR622 Co'})
    return c


class TermesPaiementDevis(TestCase):

    def setUp(self):
        self.company = _company()
        self.client_obj = Client.objects.create(
            company=self.company, nom='Termes', prenom='Client',
            email='termes622@example.com', telephone='+212600000622')

    def _devis(self, ref, echeancier=None):
        return Devis.objects.create(
            company=self.company, reference=ref, client=self.client_obj,
            statut='brouillon', taux_tva=Decimal('20.00'),
            remise_globale=Decimal('0'), echeancier=echeancier)

    def test_40_50_10_positionnel(self):
        from apps.ventes.utils.echeancier import termes_paiement_devis
        devis = self._devis('DEV-QJR622-A', echeancier=[
            {'libelle': 'Acompte', 'type': 'acompte', 'pct_or_montant': 40},
            {'libelle': 'Livraison', 'type': 'materiel', 'pct_or_montant': 50},
            {'libelle': 'Solde', 'type': 'solde', 'pct_or_montant': 10},
        ])
        slots = termes_paiement_devis(devis, {'acompte': 30, 'materiel': 60,
                                              'solde': 10})
        self.assertEqual(
            {k: Decimal(str(v)) for k, v in slots.items()},
            {'acompte': Decimal('40'), 'materiel': Decimal('50'),
             'solde': Decimal('10')})

    def test_premiere_tranche_est_l_acompte(self):
        from apps.ventes.utils.echeancier import termes_paiement_devis
        devis = self._devis('DEV-QJR622-B', echeancier=[
            {'libelle': 'Commande', 'type': 'acompte', 'pct_or_montant': 45},
            {'libelle': 'Solde', 'type': 'solde', 'pct_or_montant': 55},
        ])
        slots = termes_paiement_devis(devis, {'acompte': 30, 'materiel': 60,
                                              'solde': 10})
        self.assertEqual(Decimal(str(slots['acompte'])), Decimal('45'))
        self.assertEqual(Decimal(str(slots['solde'])), Decimal('55'))
        # Créneau absent de l'échéancier : la société.
        self.assertEqual(slots['materiel'], 60)

    def test_sans_devis_la_societe_seule(self):
        from apps.ventes.utils.echeancier import termes_paiement_devis
        self.assertEqual(
            termes_paiement_devis(None, {'acompte': 50, 'materiel': 40,
                                         'solde': 10}),
            {'acompte': 50, 'materiel': 40, 'solde': 10})
        self.assertEqual(termes_paiement_devis(None, {}),
                         {'acompte': 30, 'materiel': 60, 'solde': 10})

    def test_sans_echeancier_la_societe(self):
        from apps.ventes.utils.company_settings import (
            creneaux_depuis_jalons, payment_terms_for)
        from apps.ventes.utils.echeancier import termes_paiement_devis
        devis = self._devis('DEV-QJR622-C')
        # CIQ212 — ``payment_terms_for`` rend une LISTE de jalons.
        societe = creneaux_depuis_jalons(
            payment_terms_for(self.company, 'residentiel'))
        slots = termes_paiement_devis(devis, societe)
        for cle in ('acompte', 'materiel', 'solde'):
            self.assertEqual(Decimal(str(slots[cle])),
                             Decimal(str(societe[cle])))
