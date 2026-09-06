"""AUD159 — « Mes factures » du portail : budget de requêtes borné.

``factures_du_client_portail`` faisait un ``Facture.objects.filter(...)[:200]``
SANS aucun ``select_related``/``prefetch_related`` puis sérialisait, pour
chaque ligne, ``f.total_ttc`` (→ ``lignes`` + ``tva_par_taux``) et
``f.montant_du`` (→ ``paiements``, ``affectations_paiement``, ``avoirs``,
``notes_debit``, ``retenues_subies``) : jusqu'à ~7 requêtes par facture, sur
200 factures par page — et sur une surface PUBLIQUE, donc exposée à la charge
externe. Le queryset interne des devis, lui, préfetche explicitement.

Le correctif ne change AUCUNE source de chiffre : les propriétés modèles
restent le propriétaire unique.
"""
import itertools
from decimal import Decimal

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

from apps.crm.models import Client
from apps.facturation.models import Facture, LigneFacture, Paiement
from apps.roles.models import (
    PORTAIL_CLIENT_PERMISSIONS, ROLE_PORTAIL_CLIENT, Role,
)
from authentication.models import Company, CustomUser

_seq = itertools.count(1)


class MesFacturesBudgetRequetesTests(TestCase):
    def setUp(self):
        n = next(_seq)
        self.company = Company.objects.create(
            slug=f'aud159-co-{n}', nom='AUD159 Société')
        self.client_obj = Client.objects.create(
            company=self.company, nom='AUD159', prenom='Client',
            email=f'aud159-{n}@example.invalid')
        role, _ = Role.objects.get_or_create(
            company=self.company, nom=ROLE_PORTAIL_CLIENT,
            defaults={'permissions': list(PORTAIL_CLIENT_PERMISSIONS),
                      'est_systeme': True})
        self.user = CustomUser.objects.create_user(
            username=f'aud159-portail-{n}', password='motdepasse-test-1234',
            company=self.company, role=role)
        self.user.portee = CustomUser.PORTEE_PORTAIL_CLIENT
        self.user.portail_client_id = self.client_obj.id
        self.user.save()
        self.api = APIClient()
        self.api.force_authenticate(user=self.user)

    def _facture(self):
        n = next(_seq)
        facture = Facture.objects.create(
            company=self.company, reference=f'FAC-AUD159-{n}',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20'))
        LigneFacture.objects.create(
            facture=facture, designation='Kit PV',
            quantite=Decimal('1'), prix_unitaire=Decimal('10000'),
            taux_tva=Decimal('20'))
        Paiement.objects.create(
            company=self.company, facture=facture,
            montant=Decimal('1000'), date_paiement=timezone.localdate(),
            mode=Paiement.Mode.VIREMENT)
        return facture

    def _cout(self, n_nouvelles):
        for _ in range(n_nouvelles):
            self._facture()
        with CaptureQueriesContext(connection) as ctx:
            res = self.api.get('/api/django/portail/mes-factures/')
            self.assertEqual(res.status_code, 200, res.content)
        return len(ctx.captured_queries), res

    def test_budget_independant_du_nombre_de_factures(self):
        cout_1, _ = self._cout(1)
        cout_5, _ = self._cout(4)
        self.assertEqual(
            cout_1, cout_5,
            f'N+1 portail : {cout_1} requêtes pour 1 facture, '
            f'{cout_5} pour 5.')

    def test_montants_identiques_au_centime(self):
        facture = self._facture()
        _, res = self._cout(0)
        ligne = next(r for r in res.data['results'] if r['id'] == facture.id)
        self.assertEqual(Decimal(ligne['montant_ttc']), facture.total_ttc)
        self.assertEqual(Decimal(ligne['montant_du']), facture.montant_du)
        self.assertEqual(Decimal(ligne['montant_ttc']), Decimal('12000.00'))
        self.assertEqual(Decimal(ligne['montant_du']), Decimal('11000.00'))
