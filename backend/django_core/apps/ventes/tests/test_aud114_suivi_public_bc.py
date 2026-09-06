"""AUD114 — la page publique de suivi ne renvoie plus 500 dès qu'un BC existe.

``devis_milestones`` écrivait ``bc.factures.exists()``. L'accesseur inverse de
``Facture.bon_commande`` est ``facture`` au SINGULIER (``OneToOneField``) :
``bc.factures`` levait AttributeError, et le court-circuit du ``or`` ne sauvait
rien puisque la branche gauche (``devis.factures``) est justement fausse pour
une facture de la chaîne BC. Le seul appelant, ``suivi_public``, n'enveloppe
rien — l'exception remontait en 500 sur le lien de suivi envoyé au client.
"""
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.crm.models import Client
from apps.ventes.models import BonCommande, Devis, Facture, ShareLink
from authentication.models import Company

MONTH = timezone.now().strftime('%Y%m')


class TestSuiviPublicAvecBonCommande(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='AUD114 Co')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='AUD114',
            telephone='+212600000115')
        self.devis = Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-AUD11401',
            client=self.client_obj, statut=Devis.Statut.ACCEPTE,
            taux_tva=Decimal('20'))
        self.link = ShareLink.for_devis(self.devis)
        self.api = APIClient()

    def _url(self):
        return f'/api/django/ventes/suivi/{self.link.token}/'

    def test_suivi_200_avec_bc_sans_facture(self):
        """ROUGE avant le correctif : AttributeError → 500."""
        BonCommande.objects.create(
            company=self.company, reference=f'BC-{MONTH}-AUD11401',
            devis=self.devis, client=self.client_obj,
            statut=BonCommande.Statut.CONFIRME)
        resp = self.api.get(self._url())
        self.assertEqual(resp.status_code, 200, resp.content)
        ms = {m['key']: m for m in resp.data['milestones']}
        self.assertTrue(ms['materiel']['done'])
        self.assertFalse(ms['facture']['done'])

    def test_facture_de_chaine_bc_marque_le_jalon(self):
        """Une facture rattachée AU SEUL BC (chaîne historique, sans
        ``Facture.devis``) allume bien le jalon « Facturé »."""
        bc = BonCommande.objects.create(
            company=self.company, reference=f'BC-{MONTH}-AUD11402',
            devis=self.devis, client=self.client_obj,
            statut=BonCommande.Statut.CONFIRME)
        Facture.objects.create(
            company=self.company, reference=f'FAC-{MONTH}-AUD11402',
            client=self.client_obj, bon_commande=bc, devis=None,
            statut=Facture.Statut.EMISE, taux_tva=Decimal('20'))
        resp = self.api.get(self._url())
        self.assertEqual(resp.status_code, 200, resp.content)
        ms = {m['key']: m for m in resp.data['milestones']}
        self.assertTrue(ms['facture']['done'])
