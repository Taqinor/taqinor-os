"""AUD115 — une ligne de section/note ne fait plus planter la LISTE des BC.

``BonCommande.reliquat_par_ligne`` itérait TOUTES les lignes du devis et
calculait ``ligne.quantite - livre``. XSAL14 a rendu ``LigneDevis.quantite``
nullable (une ligne de section/note ne porte ni quantité ni prix) : ``None - 0``
levait TypeError, et la propriété est exposée SANS garde sur chaque ligne de la
liste (``est_partiellement_livre`` la rappelant une seconde fois). Un simple
intertitre « Kit batterie » dans un devis rendait l'écran Bons de commande de
toute la société inaccessible.

Le même geste referme le N+1 en série de la liste (constat FAC-9) : existence
de facture annotée, totaux calculés en UN passage.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import BonCommande, Devis, Facture, LigneDevis
from authentication.models import Company

User = get_user_model()
_CTR = [0]


def _nxt():
    _CTR[0] += 1
    return _CTR[0]


class TestReliquatLigneSection(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='AUD115 Co', slug=f'aud115-{_nxt()}')
        self.user = User.objects.create_user(
            username=f'aud115_{_nxt()}', password='x',
            role_legacy='responsable', company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.client_obj = Client.objects.create(
            company=self.company, nom='AUD115', prenom='Client',
            telephone='+212600000116')
        self.produit = Produit.objects.create(
            company=self.company, nom='Kit PV', sku=f'AUD115-{_nxt()}',
            prix_vente=Decimal('10000'), quantite_stock=500)

    def _devis_avec_section(self):
        devis = Devis.objects.create(
            company=self.company, created_by=self.user,
            client=self.client_obj, reference=f'DEV-AUD115-{_nxt()}',
            statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20'))
        LigneDevis.objects.create(
            devis=devis, type_ligne=LigneDevis.TypeLigne.SECTION,
            designation='Kit batterie', quantite=None, prix_unitaire=None,
            produit=None)
        LigneDevis.objects.create(
            devis=devis, produit=self.produit, designation='Kit PV',
            quantite=Decimal('2'), prix_unitaire=Decimal('10000'),
            taux_tva=Decimal('20'))
        return devis

    def _bc(self, devis):
        return BonCommande.objects.create(
            company=self.company, reference=f'BC-AUD115-{_nxt()}',
            devis=devis, client=self.client_obj,
            statut=BonCommande.Statut.CONFIRME)

    def test_liste_bc_200_avec_ligne_section(self):
        """ROUGE avant le correctif : TypeError (`None - 0`) → 500."""
        self._bc(self._devis_avec_section())
        resp = self.api.get('/api/django/ventes/bons-commande/')
        self.assertEqual(resp.status_code, 200, resp.content)
        results = resp.data.get('results', resp.data)
        self.assertEqual(len(results), 1)
        # La ligne de section est ABSENTE du reliquat : elle n'est pas livrable.
        reliquats = results[0]['reliquat_par_ligne']
        self.assertEqual(len(reliquats), 1)
        self.assertEqual(reliquats[0]['designation'], 'Kit PV')

    def test_propriete_modele_ignore_la_section(self):
        bc = self._bc(self._devis_avec_section())
        self.assertEqual(len(bc.reliquat_par_ligne), 1)
        self.assertFalse(bc.est_partiellement_livre)

    def test_budget_requetes_independant_du_nombre_de_bc(self):
        """Le coût de la page ne doit plus croître avec le nombre de BC."""
        def _mesurer(n):
            for _ in range(n):
                devis = self._devis_avec_section()
                bc = self._bc(devis)
                Facture.objects.create(
                    company=self.company, reference=f'FAC-AUD115-{_nxt()}',
                    client=self.client_obj, bon_commande=bc,
                    statut=Facture.Statut.EMISE, taux_tva=Decimal('20'))
            from django.test.utils import CaptureQueriesContext
            from django.db import connection
            with CaptureQueriesContext(connection) as ctx:
                resp = self.api.get('/api/django/ventes/bons-commande/')
                self.assertEqual(resp.status_code, 200, resp.content)
            return len(ctx.captured_queries)

        cout_1 = _mesurer(1)
        cout_5 = _mesurer(4)  # 5 BC au total
        self.assertEqual(
            cout_1, cout_5,
            f'N+1 : {cout_1} requêtes pour 1 BC, {cout_5} pour 5.')
