"""SCA39 — index chemin-de-l'argent Devis + Facture (sous-ensemble NTPLT20).

Prouve que les listes ventes filtrées par société (`company`) + `statut`
peuvent s'appuyer sur un Index Scan plutôt qu'un balayage séquentiel complet
de `ventes_devis` / `ventes_facture` (les deux tables les plus chaudes).

Le test EXPLAIN est DÉFENSIF :
  * ignoré (skip) si le moteur n'est pas PostgreSQL (SQLite n'a ni le même
    planificateur ni la même sortie EXPLAIN) ;
  * sur une table de test quasi vide, le planificateur PG choisit toujours un
    Seq Scan, indépendamment des index — on désactive donc `enable_seqscan`
    pour la durée de la requête EXPLAIN afin de VÉRIFIER QUE L'INDEX COUVRE la
    forme de requête (le planificateur bascule sur l'index dès qu'il y est
    autorisé). C'est exactement l'assurance recherchée : l'index existe et
    matche le filtre `(company, statut)`.

Un second test (indépendant du moteur) vérifie que les quatre index déclarés
dans `Meta.indexes` sont bien présents dans l'état du modèle.
"""
from decimal import Decimal

from django.db import connection
from django.test import TestCase

from authentication.models import Company
from apps.crm.models import Client
from apps.ventes.models import Devis, Facture


class Sca39IndexDeclarationTests(TestCase):
    """Indépendant du moteur : les index (company, statut) / (company, date_*)
    sont déclarés sur les deux modèles chauds."""

    def _index_names(self, model):
        return {idx.name for idx in model._meta.indexes}

    def test_devis_has_money_path_indexes(self):
        names = self._index_names(Devis)
        self.assertIn('ventes_devis_co_statut_idx', names)
        self.assertIn('ventes_devis_co_datecrea_idx', names)

    def test_facture_has_money_path_indexes(self):
        names = self._index_names(Facture)
        self.assertIn('ventes_fact_co_statut_idx', names)
        self.assertIn('ventes_fact_co_dateemis_idx', names)

    def test_devis_statut_index_fields(self):
        idx = next(i for i in Devis._meta.indexes
                   if i.name == 'ventes_devis_co_statut_idx')
        self.assertEqual(idx.fields, ['company', 'statut'])

    def test_facture_statut_index_fields(self):
        idx = next(i for i in Facture._meta.indexes
                   if i.name == 'ventes_fact_co_statut_idx')
        self.assertEqual(idx.fields, ['company', 'statut'])


class Sca39ExplainIndexScanTests(TestCase):
    """PostgreSQL uniquement : les listes ventes filtrées par (company, statut)
    empruntent un Index Scan quand le planificateur y est autorisé."""

    # Statuts de « remplissage » (autres que celui recherché) — un mélange rend
    # la colonne ``statut`` SÉLECTIVE : l'index (company, statut) devient
    # strictement plus discriminant que (company, date_*) pour la requête, donc
    # le planificateur le préfère de façon DÉTERMINISTE (sur des données
    # uniformes il pourrait choisir n'importe quel index en tête ``company``).
    DEVIS_STATUTS = ['envoye', 'accepte', 'refuse', 'expire']
    FACTURE_STATUTS = ['payee', 'en_retard', 'annulee', 'brouillon']

    def setUp(self):
        self.company = Company.objects.create(
            slug='sca39-explain-co', nom='SCA39 Explain Co')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='SCA39',
            email='sca39-explain@example.invalid')
        # Une ligne du statut RECHERCHÉ + plusieurs autres statuts : le statut
        # ciblé est minoritaire, donc (company, statut) est le plan le plus
        # sélectif. Le forçage enable_seqscan=off + ANALYZE (ci-dessous) rend le
        # choix d'index déterministe même sur une table de test quasi vide.
        Devis.objects.create(
            company=self.company, reference='DEV-SCA39-0000',
            client=self.client_obj, statut=Devis.Statut.BROUILLON,
            taux_tva=Decimal('20'))
        Facture.objects.create(
            company=self.company, reference='FAC-SCA39-0000',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20'))
        for i, (ds, fs) in enumerate(
                zip(self.DEVIS_STATUTS * 3, self.FACTURE_STATUTS * 3), start=1):
            Devis.objects.create(
                company=self.company, reference=f'DEV-SCA39-{i:04d}',
                client=self.client_obj, statut=ds, taux_tva=Decimal('20'))
            Facture.objects.create(
                company=self.company, reference=f'FAC-SCA39-{i:04d}',
                client=self.client_obj, statut=fs, taux_tva=Decimal('20'))
        # Statistiques fraîches pour que le planificateur voie la sélectivité
        # réelle du statut ciblé (sans ANALYZE, PG utilise des estimations par
        # défaut identiques pour tous les index en tête company).
        with connection.cursor() as cur:
            cur.execute('ANALYZE ventes_devis;')
            cur.execute('ANALYZE ventes_facture;')

    def _explain_uses_index(self, sql, params, index_name):
        """Retourne True si le plan EXPLAIN mentionne un Index Scan sur
        ``index_name`` (avec enable_seqscan désactivé pour prouver que l'index
        COUVRE la requête)."""
        with connection.cursor() as cur:
            cur.execute("SET LOCAL enable_seqscan = off;")
            cur.execute(f"EXPLAIN {sql}", params)
            plan = '\n'.join(row[0] for row in cur.fetchall())
        return plan, index_name in plan

    def test_devis_company_statut_uses_index(self):
        if connection.vendor != 'postgresql':
            self.skipTest("EXPLAIN spécifique PostgreSQL")
        plan, ok = self._explain_uses_index(
            'SELECT id FROM ventes_devis '
            'WHERE company_id = %s AND statut = %s',
            [self.company.id, Devis.Statut.BROUILLON],
            'ventes_devis_co_statut_idx',
        )
        self.assertTrue(
            ok,
            f"Le plan Devis (company, statut) n'utilise pas l'index attendu :\n"
            f"{plan}")

    def test_facture_company_statut_uses_index(self):
        if connection.vendor != 'postgresql':
            self.skipTest("EXPLAIN spécifique PostgreSQL")
        plan, ok = self._explain_uses_index(
            'SELECT id FROM ventes_facture '
            'WHERE company_id = %s AND statut = %s',
            [self.company.id, Facture.Statut.EMISE],
            'ventes_fact_co_statut_idx',
        )
        self.assertTrue(
            ok,
            f"Le plan Facture (company, statut) n'utilise pas l'index "
            f"attendu :\n{plan}")
