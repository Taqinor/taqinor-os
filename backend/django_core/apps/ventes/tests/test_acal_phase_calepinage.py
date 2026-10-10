"""ACAL32 (C-ACAL-105) — un devis né d'un layout (module calepinage ET
from-layout) est composé avec la PHASE et le SITE ISOLÉ du lead, déduits UNE
fois (``taille.phase_et_isolement_du_lead``) dans ``build_devis_from_layout``
et dans le pré-vol ``validate_composition_for_layout``.

* lead triphasé, 10 panneaux (7,1 kWc < 10) : jamais un onduleur monophasé,
  et le module comme from-layout composent le MÊME onduleur ;
* lead « aucun » (site isolé) — ACAL361, deux tests distincts : catalogue
  qui sert un onduleur autonome + une batterie tarifés ⇒ 201, ce kit, jamais
  un onduleur réseau ; catalogue seedé seul ⇒ 422 NOMMÉ ``{hors_reseau: …}``,
  aucun devis créé, jamais un 500 ;
* le pré-vol compose avec la phase / le site isolé du lead.

Vrais produits : le catalogue RÉELLEMENT seedé (``seed_catalogue``), aucun
mock du catalogue ni du pipeline.

Run:
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.ventes.tests.test_acal_phase_calepinage"
"""
from decimal import Decimal
from io import StringIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.calepinage.models import Calepinage
from apps.crm.models import Lead
from apps.roles.models import Role
from apps.roles.permissions_registre import DIRECTEUR_PERMISSIONS
from apps.stock.models import Produit
from apps.ventes.domain import catalogue as domaine_catalogue
from apps.ventes.domain.geometrie import layout_hash
from apps.ventes.models import Devis
from authentication.models import Company

User = get_user_model()

LAYOUT = {
    'scenario': 'reseau',
    'panelWatt': 710,
    'result': {'panels': 10, 'kwc': 7.1, 'annualKwh': 12000,
               'savings': 10000},
}


def _norm(texte):
    return domaine_catalogue._sans_accents(texte or '')


def _onduleurs(devis):
    return [ligne.designation for ligne in devis.lignes.all()
            if 'onduleur' in _norm(ligne.designation)]


def _textes_onduleur(valeur):
    """Toutes les chaînes d'un ``build_quote_data`` qui parlent d'onduleur."""
    if isinstance(valeur, str):
        return [valeur] if 'onduleur' in _norm(valeur) else []
    if isinstance(valeur, dict):
        valeur = list(valeur.values())
    if isinstance(valeur, (list, tuple)):
        sortie = []
        for element in valeur:
            sortie.extend(_textes_onduleur(element))
        return sortie
    return []


class PhaseDuLeadSurLeLayout(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='ACAL32 Co',
                                             slug='acal32-co')
        call_command('seed_catalogue', company_slug=cls.company.slug,
                     stdout=StringIO())

    def setUp(self):
        role = Role.objects.create(company=self.company, nom='Directeur',
                                   permissions=list(DIRECTEUR_PERMISSIONS))
        self.user = User.objects.create_user(
            username='acal32', password='x', company=self.company,
            role=role, role_legacy='responsable')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.n = 0

    def _lead(self, raccordement):
        self.n += 1
        return Lead.objects.create(
            company=self.company, nom='ACAL32', prenom='Lead%d' % self.n,
            email='acal32-%d@example.test' % self.n,
            raccordement=raccordement)

    def _generer_module(self, lead):
        calepinage = Calepinage.objects.create(
            company=self.company, lead_id=lead.pk, titre='ACAL32',
            roof_layout=dict(LAYOUT), layout_hash=layout_hash(LAYOUT))
        return self.api.post(
            f'/api/django/calepinage/calepinages/{calepinage.pk}/'
            'generer-devis/', {}, format='json')

    def _from_layout(self, lead):
        return self.api.post('/api/django/ventes/devis/from-layout/',
                             {'layout': dict(LAYOUT), 'lead': lead.pk},
                             format='json')

    def _assert_jamais_mono(self, devis):
        onduleurs = _onduleurs(devis)
        self.assertTrue(onduleurs, 'aucun onduleur composé')
        for designation in onduleurs:
            self.assertNotIn('monophas', _norm(designation), designation)
        # Ce que le client voit (PDF /proposal) : même lignes.
        from apps.ventes.quote_engine.builder import build_quote_data
        for texte in _textes_onduleur(build_quote_data(devis)):
            self.assertNotIn('monophas', _norm(texte), texte)
        return onduleurs

    def test_generer_devis_module_lead_triphase_sans_onduleur_mono(self):
        r = self._generer_module(self._lead('triphase'))
        self.assertEqual(r.status_code, 201, r.data)
        devis = Devis.objects.get(pk=r.data['devis'])
        self._assert_jamais_mono(devis)

    def test_from_layout_et_module_meme_onduleur(self):
        r_module = self._generer_module(self._lead('triphase'))
        self.assertEqual(r_module.status_code, 201, r_module.data)
        r_vente = self._from_layout(self._lead('triphase'))
        self.assertEqual(r_vente.status_code, 201, r_vente.data)
        module = self._assert_jamais_mono(
            Devis.objects.get(pk=r_module.data['devis']))
        vente = self._assert_jamais_mono(
            Devis.objects.get(pk=r_vente.data['id']))
        self.assertEqual(sorted(module), sorted(vente))

    def test_module_lead_isole_compose_onduleur_autonome(self):
        from apps.ventes.solar_classification import (
            is_offgrid_inverter, is_reseau_inverter)
        for nom, sku, prix in (
                ('Onduleur Off-Grid Deye 8kW', 'A361-OFF-8', '16000'),
                ('Batterie lithium 5 kWh', 'A361-BAT-5', '15000')):
            Produit.objects.create(
                company=self.company, nom=nom, sku=sku,
                prix_vente=Decimal(prix), prix_achat=Decimal('1'),
                quantite_stock=100)
        for geste in (self._generer_module, self._from_layout):
            with self.subTest(geste=geste.__name__):
                r = geste(self._lead('aucun'))
                self.assertEqual(r.status_code, 201, r.data)
                pk = r.data.get('devis') or r.data.get('id')
                devis = Devis.objects.get(pk=pk)
                onduleurs = _onduleurs(devis)
                self.assertTrue(any(is_offgrid_inverter(o)
                                    for o in onduleurs), onduleurs)
                self.assertFalse(any(is_reseau_inverter(o)
                                     for o in onduleurs), onduleurs)
                self.assertTrue(any('batterie' in _norm(ligne.designation)
                                    for ligne in devis.lignes.all()))

    def test_module_lead_isole_sans_kit_autonome_422_nomme(self):
        for geste in (self._generer_module, self._from_layout):
            with self.subTest(geste=geste.__name__):
                avant = Devis.objects.filter(company=self.company).count()
                r = geste(self._lead('aucun'))
                self.assertEqual(r.status_code, 422, r.data)
                self.assertIn('hors_reseau', r.data)
                self.assertTrue(str(r.data['hors_reseau']).strip())
                self.assertEqual(
                    Devis.objects.filter(company=self.company).count(), avant)

    def test_preflight_lit_la_phase_du_lead(self):
        from apps.ventes.domain import geometrie
        from apps.ventes.domain.taille import AutoDevisError

        reel = geometrie.verifier
        with mock.patch.object(geometrie, 'verifier',
                               side_effect=reel) as espion:
            geometrie.validate_composition_for_layout(
                dict(LAYOUT), self.company, lead=self._lead('triphase'))
        intention = espion.call_args.args[0]
        self.assertEqual(intention.phase, 'triphase')
        self.assertFalse(intention.hors_reseau)

        with mock.patch.object(geometrie, 'verifier',
                               side_effect=reel) as espion:
            try:
                geometrie.validate_composition_for_layout(
                    dict(LAYOUT), self.company, lead=self._lead('aucun'))
            except AutoDevisError as refus:
                self.assertEqual(refus.field, 'hors_reseau')
        self.assertTrue(espion.call_args.args[0].hors_reseau)

        # Sans lead : aucun filtre, comportement d'hier.
        with mock.patch.object(geometrie, 'verifier',
                               side_effect=reel) as espion:
            geometrie.validate_composition_for_layout(dict(LAYOUT),
                                                      self.company)
        self.assertIsNone(espion.call_args.args[0].phase)
        self.assertFalse(espion.call_args.args[0].hors_reseau)
