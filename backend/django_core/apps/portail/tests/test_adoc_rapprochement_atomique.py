"""ADOC143 — rapprochement d'un paiement portail ATOMIQUE.

Constat (C-ADOC-055, plausible — oracle = ce test) :
``rapprocher_paiement_facture`` posait ``PAYE`` + ``paye_le`` AVANT
d'appeler ``enregistrer_paiement``. Sur un acompte d'un bon signé au
domicile pendant le délai de la loi 31-08, ventes lève
``AcompteAvantDelaiLegal`` : la requête tombait en 500, le paiement restait
« payé » sans aucune ligne ``Paiement`` (facture toujours due), et le rejeu
après le délai était un no-op (statut déjà ``PAYE``).

Correctif : encaissement D'ABORD, statut ENSUITE, sous transaction avec
verrou ; refus loi 31-08 → 400 nommé, paiement INITIÉ re-rapprochable.

Run :
    python manage.py test apps.portail.tests.test_adoc_rapprochement_atomique -v2
"""
import itertools
from datetime import date
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient
from testkit.time import frozen

from apps.crm.models import Client
from apps.facturation.models import Facture, Paiement
from apps.portail.models import PaiementFacturePortail
from apps.ventes.models import BonCommande, Devis
from authentication.models import Company, CustomUser

_seq = itertools.count(1)


class RapprochementAtomiqueTests(TestCase):
    def setUp(self):
        n = next(_seq)
        self.co, _ = Company.objects.get_or_create(
            slug=f'adoc143-{n}', defaults={'nom': f'ADOC143 {n}'})
        client = Client.objects.create(
            company=self.co, nom='Client', prenom=f'ADOC143-{n}',
            email=f'adoc143-{n}@example.invalid')
        devis = Devis.objects.create(
            company=self.co, reference=f'DEV-ADOC143-{n}', client=client,
            statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20'))
        # Bon signé AU DOMICILE le 01/10/2026 : acompte encaissable le 08/10.
        BonCommande.objects.create(
            company=self.co, reference=f'BC-ADOC143-{n}', devis=devis,
            client=client, statut=BonCommande.Statut.CONFIRME,
            signe_au_domicile=True,
            date_signature_domicile=date(2026, 10, 1))
        self.facture = Facture.objects.create(
            company=self.co, reference=f'FAC-ADOC143-{n}', client=client,
            devis=devis, type_facture=Facture.TypeFacture.ACOMPTE,
            statut=Facture.Statut.EMISE, montant_ht=Decimal('1000.00'),
            montant_tva=Decimal('200.00'), montant_ttc=Decimal('1200.00'),
            taux_tva=Decimal('20'))
        self.paiement = PaiementFacturePortail.objects.create(
            company=self.co, facture_id=self.facture.id,
            montant=Decimal('1200.00'),
            methode=PaiementFacturePortail.Methode.VIREMENT,
            statut=PaiementFacturePortail.Statut.INITIE)
        self.resp = CustomUser.objects.create_user(
            username=f'adoc143-resp-{n}', password='motdepasse-test-1234',
            company=self.co, role_legacy='responsable')
        self.api = APIClient()
        self.api.force_authenticate(user=self.resp)
        self.url = ('/api/django/portail/paiements-facture-portail/'
                    f'{self.paiement.id}/rapprocher/')

    def _rapprocher(self):
        return self.api.post(self.url, {}, format='json')

    def test_acompte_delai_legal_400_paiement_initie(self):
        with frozen('2026-10-03 10:00:00'):
            res = self._rapprocher()

        self.assertEqual(res.status_code, 400, res.content)
        self.assertIn('08/10/2026', res.json()['detail'])
        self.paiement.refresh_from_db()
        self.assertEqual(self.paiement.statut,
                         PaiementFacturePortail.Statut.INITIE)
        self.assertIsNone(self.paiement.paye_le)
        self.assertFalse(Paiement.objects.filter(
            facture=self.facture).exists())
        self.facture.refresh_from_db()
        self.assertEqual(self.facture.montant_du, Decimal('1200.00'))

    def test_rejeu_apres_delai_encaisse(self):
        with frozen('2026-10-03 10:00:00'):
            self.assertEqual(self._rapprocher().status_code, 400)
        with frozen('2026-10-09 10:00:00'):
            res = self._rapprocher()

        self.assertEqual(res.status_code, 200, res.content)
        self.assertEqual(res.json()['statut'],
                         PaiementFacturePortail.Statut.PAYE)
        self.paiement.refresh_from_db()
        self.assertEqual(self.paiement.statut,
                         PaiementFacturePortail.Statut.PAYE)
        self.assertIsNotNone(self.paiement.paye_le)
        self.assertEqual(Paiement.objects.filter(
            facture=self.facture).count(), 1)
        self.facture.refresh_from_db()
        self.assertEqual(self.facture.montant_du, Decimal('0.00'))
