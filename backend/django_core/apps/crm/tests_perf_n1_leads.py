"""Perf audit fix — LeadViewSet N+1 regression test.

Without select_related('owner', 'client') + prefetch_related('devis') on
LeadViewSet.queryset, listing N leads triggers extra per-row queries for:
  - client_nom (obj.client)
  - owner_nom/owner_poste/owner_avatar (obj.owner)
  - the `devis` SerializerMethodField (obj.devis.order_by(...))

Rather than pin an exact query count (fragile / a guess), this test proves
FLATNESS: the query count for listing 5 leads (each with an owner, a
resolved client, and one attached devis) must be IDENTICAL to the query
count for listing 10 such leads. Before the fix, each extra lead added ~2+
queries (one for `.client`, one for `.devis.order_by(...)`) so the count
would grow with row count. After the fix, select_related folds owner/client
into the base query and prefetch_related issues a constant number of extra
queries regardless of row count, so the two counts are equal.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client, Lead
from apps.ventes.models import Devis

User = get_user_model()


def _auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class TestLeadViewSetNPlusOne(TestCase):
    BASE = '/api/django/crm/leads/'

    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='perf-n1-leads-co', defaults={'nom': 'Perf N1 Leads Co'})
        self.admin = User.objects.create_user(
            username='perf_n1_leads_admin', password='x',
            role_legacy='admin', company=self.company)
        self.owner = User.objects.create_user(
            username='perf_n1_leads_owner', password='x',
            role_legacy='responsable', company=self.company)
        self.api = _auth(self.admin)

    def _make_leads(self, n, offset=0):
        for i in range(offset, offset + n):
            client_obj = Client.objects.create(
                company=self.company, nom=f'Client{i}', prenom='Perf',
                email=f'perf-n1-lead-{i}@example.invalid')
            lead = Lead.objects.create(
                company=self.company, nom=f'Lead{i}', stage='NEW',
                owner=self.owner, client=client_obj,
            )
            Devis.objects.create(
                company=self.company, reference=f'DEV-PERFN1-{i:04d}',
                client=client_obj, lead=lead, statut=Devis.Statut.ENVOYE,
                taux_tva=Decimal('20'))

    def _list_query_count(self):
        with CaptureQueriesContext(connection) as ctx:
            resp = self.api.get(self.BASE)
        self.assertEqual(resp.status_code, 200)
        return len(ctx.captured_queries), resp

    def test_list_query_count_flat_as_row_count_grows(self):
        # 5 leads, each with an owner + resolved client + one devis.
        self._make_leads(5)
        # Un premier appel NON mesuré amorce les caches transverses
        # (ContentType, permissions…) : sans lui, la toute première mesure
        # porte une requête de chauffe de plus et l'égalité stricte 5-vs-10
        # devient flaky (rouge CI observé : 13 vs 12 — le compte BAISSAIT).
        self._list_query_count()
        count_5, resp_5 = self._list_query_count()
        results_5 = (
            resp_5.data['results']
            if isinstance(resp_5.data, dict) and 'results' in resp_5.data
            else resp_5.data
        )
        self.assertEqual(len(results_5), 5)
        # Sanity: the serialized fields this fix targets are actually
        # present and populated (proves select_related/prefetch_related
        # wiring, not just that the endpoint returns 200).
        row = next(r for r in results_5 if r['nom'] == 'Lead0')
        self.assertIsNotNone(row['client_nom'])
        self.assertEqual(row['owner_nom'], self.owner.username)
        self.assertEqual(len(row['devis']), 1)

        # Double the rows (10 leads total), same shape (owner/client/devis).
        self._make_leads(5, offset=5)
        count_10, resp_10 = self._list_query_count()
        results_10 = (
            resp_10.data['results']
            if isinstance(resp_10.data, dict) and 'results' in resp_10.data
            else resp_10.data
        )
        self.assertEqual(len(results_10), 10)

        # The crux of the N+1 regression check: doubling the rows must NOT
        # increase the query count. Without select_related/prefetch_related,
        # each extra row adds queries for `.client` and `.devis`, so
        # count_10 > count_5. With the fix, count_10 == count_5.
        self.assertEqual(
            count_10, count_5,
            f"Query count grew from {count_5} (5 leads) to {count_10} "
            f"(10 leads) — N+1 regression on LeadViewSet.queryset "
            f"(missing select_related('owner','client')/"
            f"prefetch_related('devis'))."
        )


class TestLeadListeLignesProduitNPlusOne(TestCase):
    """ERR-PERF-CRM-N1 — rejeu APRF42 : la liste des leads montait 18 → 35 →
    72 requêtes à 5/25/50 lignes, une requête ``ventes_lignedevis`` PAR devis.
    Cause : ``prefetch_related('devis__lignes')`` sans le produit ;
    ``total_ttc`` → ``deux_options_declarees`` → ``lignes_avec_produit``
    retombait sur ``select_related('produit')`` dès qu'une ligne porte un
    produit (toute ligne réelle — le fixture de la classe d'au-dessus n'en
    avait aucune). Une V1 remplacée lisait en plus ``superseded_by.reference``.

    Test-du-test : remettre ``'devis__lignes'`` dans
    ``PREFETCH_DEVIS_LISTE_LEADS`` ⇒ +1 requête par lead, l'égalité tombe.
    """
    BASE = '/api/django/crm/leads/?page_size=50'

    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='perf-n1-lignes-co', defaults={'nom': 'Perf N1 Lignes Co'})
        self.admin = User.objects.create_user(
            username='perf_n1_lignes_admin', password='x',
            role_legacy='admin', company=self.company)
        self.api = _auth(self.admin)
        self.n = 0

    def _leads(self, nombre):
        from apps.stock.models import Produit
        from apps.ventes.models import LigneDevis
        for _ in range(nombre):
            self.n += 1
            client_obj = Client.objects.create(
                company=self.company, nom=f'C{self.n}',
                email=f'perf-n1-lignes-{self.n}@example.invalid')
            lead = Lead.objects.create(
                company=self.company, nom=f'L{self.n}', stage='NEW',
                owner=self.admin, client=client_obj)
            v2 = Devis.objects.create(
                company=self.company, reference=f'DEV-N1L-{self.n:04d}-2',
                client=client_obj, lead=lead, statut=Devis.Statut.ENVOYE,
                taux_tva=Decimal('20'), version=2)
            Devis.objects.create(
                company=self.company, reference=f'DEV-N1L-{self.n:04d}-1',
                client=client_obj, lead=lead, statut=Devis.Statut.ENVOYE,
                taux_tva=Decimal('20'), version=1, is_active=False,
                superseded_by=v2)
            for nom, prix in (('Panneau 550 W', Decimal('1200')),
                              ('Onduleur réseau 5 kW', Decimal('9000'))):
                produit = Produit.objects.create(
                    company=self.company, nom=nom,
                    sku=f'N1L-{self.n}-{int(prix)}',
                    prix_vente=prix, quantite_stock=10)
                LigneDevis.objects.create(
                    devis=v2, produit=produit, designation=nom,
                    quantite=Decimal('2'), prix_unitaire=prix,
                    remise=Decimal('0'))

    def _mesure(self):
        with CaptureQueriesContext(connection) as ctx:
            resp = self.api.get(self.BASE)
        self.assertEqual(resp.status_code, 200, resp.content)
        data = resp.data
        lignes = data['results'] if isinstance(data, dict) else data
        return len(ctx.captured_queries), lignes

    def test_requetes_plates_et_devis_identiques(self):
        from apps.crm.lead_devis_payload import lignes_devis_du_lead
        self._leads(5)
        self._mesure()  # échauffement des caches de processus
        a_5, lignes_5 = self._mesure()
        self.assertEqual(len(lignes_5), 5)
        self._leads(20)
        a_25, lignes_25 = self._mesure()
        self.assertEqual(len(lignes_25), 25)
        self.assertLessEqual(
            abs(a_25 - a_5), 1,
            f'liste des leads : {a_5} requêtes à 5 lignes, {a_25} à 25')
        # JSON identique à AVANT : l'oracle est le chemin unitaire d'origine
        # (lead relu SANS préchargement, contexte sans cartes).
        for ligne in lignes_25:
            lead = Lead.objects.get(pk=ligne['id'])
            self.assertEqual(ligne['devis'], lignes_devis_du_lead(lead, {}))
        remplaces = [d for ligne in lignes_25 for d in ligne['devis']
                     if d['superseded_by']]
        self.assertEqual(len(remplaces), 25)
        self.assertTrue(all(
            d['raison_non_modifiable'].startswith('Remplacé par')
            for d in remplaces))
