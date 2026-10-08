"""APRF16 (C-APRF-012) — ``scope_client_queryset`` par quatre ``Exists``.

Avant : ``Q(devis__…) | Q(factures__…) | Q(avoirs__…) | Q(leads__…)`` puis
``.distinct()`` — quatre jointures multi-valuées (1 client à 15 devis + 15
factures + 15 leads → ``Hash Right Join rows=225`` puis ``Unique rows=1``).

Ce test vérifie sur le queryset RÉEL rendu par la fonction :
  * le même ensemble de clients qu'avant (aucune fuite, aucun manque, rien
    d'une autre société) — y compris à travers ``company_search`` ;
  * un SQL sans jointure vers devis/factures/avoirs/leads et sans DISTINCT.

``visible_user_ids`` est patché (aucun rôle restreint à monter : seule la
portée calculée compte ici), le SQL de portée est réel.

Test-du-test : remettre les ``Q(relation__…)`` + ``.distinct()`` ⇒
``test_sans_jointure_multivaluee`` échoue ; oublier la branche avoirs ⇒
``test_meme_ensemble`` échoue.
"""
import importlib
from decimal import Decimal
from unittest import mock

from django.apps import apps as registre
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.test import TestCase

from authentication.models import Company
from core import scoping


class PorteeClientsExistsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Modèles résolus par CHAÎNE : ``core`` est une couche fondation.
        cls.Client = registre.get_model('crm', 'Client')
        Lead = registre.get_model('crm', 'Lead')
        Devis = registre.get_model('ventes', 'Devis')
        Facture = registre.get_model('facturation', 'Facture')
        Avoir = registre.get_model('facturation', 'Avoir')
        User = get_user_model()

        cls.co = Company.objects.create(nom='APRF16', slug='aprf16')
        cls.autre = Company.objects.create(nom='APRF16 autre', slug='aprf16-autre')
        cls.visible = User.objects.create_user(
            username='aprf16_visible', password='x', company=cls.co)
        cls.invisible = User.objects.create_user(
            username='aprf16_invisible', password='x', company=cls.co)

        n = iter(range(10_000))

        def ref(prefixe):
            return f'{prefixe}-APRF16-{next(n):05d}'

        def client(nom, company=None):
            return cls.Client.objects.create(
                company=company or cls.co, nom=f'APRF16 {nom}',
                email=f'aprf16-{nom}@example.com')

        cls.c_devis = client('devis')
        cls.c_facture = client('facture')
        cls.c_lead = client('lead')
        cls.c_avoir = client('avoir')
        cls.c_invisible = client('invisible')
        cls.c_autre = client('autre-societe', company=cls.autre)

        Devis.objects.create(company=cls.co, client=cls.c_devis,
                             reference=ref('DEV'), created_by=cls.visible)
        Facture.objects.create(company=cls.co, client=cls.c_facture,
                               reference=ref('FAC'), created_by=cls.visible)
        Lead.objects.create(company=cls.co, nom='lead aprf16 a',
                            client=cls.c_lead, owner=cls.visible)
        # Avoir visible sur une facture INVISIBLE : seule la branche avoirs
        # rend ce client visible.
        facture_x = Facture.objects.create(
            company=cls.co, client=cls.c_avoir, reference=ref('FAC'),
            created_by=cls.invisible)
        Avoir.objects.create(
            company=cls.co, reference=ref('AV'), facture=facture_x,
            client=cls.c_avoir, created_by=cls.visible,
            taux_tva=Decimal('20'), montant_ht=Decimal('100'),
            montant_tva=Decimal('20'), montant_ttc=Decimal('120'))
        # Client invisible : ses documents sont tous d'un utilisateur hors portée.
        Devis.objects.create(company=cls.co, client=cls.c_invisible,
                             reference=ref('DEV'), created_by=cls.invisible)
        # Autre société : document d'un utilisateur visible, mais hors société.
        Devis.objects.create(company=cls.autre, client=cls.c_autre,
                             reference=ref('DEV'), created_by=cls.visible)
        # 15 × 15 : la multiplication que les jointures produisaient.
        for i in range(15):
            Devis.objects.create(company=cls.co, client=cls.c_devis,
                                 reference=ref('DEV'), created_by=cls.visible)
            Facture.objects.create(company=cls.co, client=cls.c_devis,
                                   reference=ref('FAC'), created_by=cls.visible)
            Lead.objects.create(company=cls.co, nom=f'lead aprf16 m{i}',
                                client=cls.c_devis, owner=cls.visible)

    def setUp(self):
        patcher = mock.patch.object(
            scoping, 'visible_user_ids', return_value={self.visible.id})
        patcher.start()
        self.addCleanup(patcher.stop)

    def _base(self):
        return self.Client.objects.filter(company=self.co)

    def _attendu(self):
        return {self.c_devis.pk, self.c_facture.pk, self.c_lead.pk,
                self.c_avoir.pk}

    def test_meme_ensemble(self):
        ids = [self.visible.id]
        ancien = set(self._base().filter(
            Q(devis__created_by_id__in=ids)
            | Q(factures__created_by_id__in=ids)
            | Q(avoirs__created_by_id__in=ids)
            | Q(leads__owner_id__in=ids)
        ).distinct().values_list('pk', flat=True))
        nouveau_qs = scoping.scope_client_queryset(self._base(), self.visible)
        nouveau = list(nouveau_qs.values_list('pk', flat=True))

        self.assertEqual(ancien, self._attendu())
        self.assertEqual(set(nouveau), self._attendu())
        self.assertEqual(len(nouveau), len(set(nouveau)),
                         'aucun doublon sans distinct()')

        # Le même ensemble à travers l'appelant ``company_search`` (import
        # dynamique : aucune arête statique core → apps.crm).
        company_search = importlib.import_module('apps.crm.company_search')
        hits = company_search.own_data_search(
            self.co, 'APRF16', user=self.visible, limit=50)
        self.assertEqual(
            {h['id'] for h in hits if h['source'] == 'client'},
            self._attendu())

    def test_sans_jointure_multivaluee(self):
        qs = scoping.scope_client_queryset(self._base(), self.visible)
        sql = str(qs.query)
        self.assertNotIn('DISTINCT', sql.upper(), sql)
        for relation, _champ in scoping._CLIENT_RELATIONS_VISIBLES:
            table = self.Client._meta.get_field(relation).related_model._meta.db_table
            self.assertNotIn(f'JOIN "{table}"', sql, sql)
        self.assertGreaterEqual(sql.upper().count('EXISTS'), 4, sql)

    def test_portee_all_inchangee(self):
        with mock.patch.object(scoping, 'visible_user_ids', return_value=None):
            base = self._base()
            self.assertIs(scoping.scope_client_queryset(base, self.visible), base)
