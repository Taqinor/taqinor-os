"""NTGRC16 — bibliothèque de contrôles internes + seed idempotent.

Garanties : le seed installe 12 contrôles par société sans doublon, il ne
réécrit jamais ce qui appartient à la société (propriétaire, actif), et le
viewset les liste scopés société.
"""
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from apps.grc.management.commands.seed_controles_base import CONTROLES
from apps.grc.models import ControleInterne
from authentication.models import Company
from testkit.base import TenantAPITestCase


class SeedTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='NTGRC16 SA', slug='ntgrc16')
        cls.autre = Company.objects.create(nom='NTGRC16 B', slug='ntgrc16-b')

    def _seed(self, company=None):
        sortie = StringIO()
        if company is None:
            call_command('seed_controles_base', stdout=sortie)
        else:
            call_command('seed_controles_base', company=company.pk,
                         stdout=sortie)
        return sortie.getvalue()

    def test_le_catalogue_compte_douze_controles(self):
        self.assertEqual(len(CONTROLES), 12)
        self.assertEqual(len({c['code'] for c in CONTROLES}), 12)

    def test_le_seed_installe_douze_controles_par_societe(self):
        self._seed()
        for company in (self.company, self.autre):
            self.assertEqual(
                ControleInterne.objects.filter(company=company).count(), 12)

    def test_le_seed_est_idempotent(self):
        self._seed(self.company)
        self._seed(self.company)
        self.assertEqual(
            ControleInterne.objects.filter(company=self.company).count(), 12)

    def test_le_seed_ne_reecrit_ni_le_proprietaire_ni_lactif(self):
        self._seed(self.company)
        controle = ControleInterne.objects.get(
            company=self.company, code='ACC-01')
        controle.proprietaire = 'Direction financière'
        controle.actif = False
        controle.save()

        self._seed(self.company)
        controle.refresh_from_db()
        self.assertEqual(controle.proprietaire, 'Direction financière')
        self.assertFalse(controle.actif)

    def test_le_seed_cible_une_seule_societe_avec_company(self):
        self._seed(self.company)
        self.assertEqual(
            ControleInterne.objects.filter(company=self.autre).count(), 0)

    def test_chaque_controle_porte_une_fenetre_coherente(self):
        self._seed(self.company)
        for controle in ControleInterne.objects.filter(company=self.company):
            self.assertGreaterEqual(controle.fenetre_jours, 1)


class EndpointControlesTests(TenantAPITestCase):
    BASE = '/api/django/grc/controles-internes/'

    def _admin(self):
        return self.client_as(role='admin')

    def test_le_viewset_liste_les_controles_seedes(self):
        call_command('seed_controles_base', company=self.company.pk,
                     stdout=StringIO())
        r = self._admin().get(self.BASE)
        self.assertEqual(r.status_code, 200, r.content)
        lignes = r.data.get('results', r.data)
        self.assertEqual(len(lignes), 12)

    def test_filtre_par_domaine(self):
        call_command('seed_controles_base', company=self.company.pk,
                     stdout=StringIO())
        r = self._admin().get(self.BASE, {'domaine': 'sauvegarde'})
        lignes = r.data.get('results', r.data)
        self.assertEqual({le['code'] for le in lignes}, {'SAV-01', 'SAV-02'})

    def test_liste_scopee_societe(self):
        call_command('seed_controles_base', company=self.other_company.pk,
                     stdout=StringIO())
        r = self._admin().get(self.BASE)
        lignes = r.data.get('results', r.data)
        self.assertEqual(lignes, [])

    def test_deux_societes_peuvent_porter_le_meme_code(self):
        call_command('seed_controles_base', stdout=StringIO())
        self.assertEqual(
            ControleInterne.objects.filter(code='ACC-01').count(),
            Company.objects.count())
