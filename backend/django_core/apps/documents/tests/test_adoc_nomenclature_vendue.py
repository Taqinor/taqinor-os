"""ADOC60 — PV, BL (FR/AR) et dossier de remise listent la nomenclature VENDUE.

Constat C-ADOC-036 (S1) : ``builders._composants`` itérait
``devis.lignes.all()`` — les DEUX options d'un devis à deux options (le kit
batterie non acheté), les intertitres (quantité « None ») et les optionnelles
non activées, sans le ×N d'un devis multi-villas. Source corrigée : la
nomenclature gelée ``Installation.bom`` (``_freeze_bom`` : option retenue, ×N),
repli ``option_lines(devis)`` × N pour un chantier sans bom.

Rendu WeasyPrint RÉEL (aucun mock du rendu ni de la source), texte extrait par
fitz (PyMuPDF), via les vraies routes HTTP.

Run :
    python manage.py test apps.documents.tests.test_adoc_nomenclature_vendue -v2
"""
import itertools
from decimal import Decimal

import fitz
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.installations.models import Installation
from apps.installations.services import create_installation_from_devis
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis
from authentication.models import Company

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/documents/chantiers'


def _texte_pdf(contenu):
    doc = fitz.open(stream=contenu, filetype='pdf')
    try:
        return '\n'.join(page.get_text() for page in doc)
    finally:
        doc.close()


class NomenclatureVendueTests(TestCase):
    def setUp(self):
        n = next(_seq)
        self.company = Company.objects.create(
            slug=f'adoc60-co-{n}', nom=f'ADOC60 Co {n}')
        self.user = User.objects.create_user(
            username=f'adoc60-resp-{n}', password='x',
            company=self.company, role_legacy='responsable')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    # ── fixtures ────────────────────────────────────────────────────────────
    def _produit(self, nom, garantie=''):
        return Produit.objects.create(
            company=self.company, nom=nom, sku=f'ADOC60-{next(_seq)}',
            prix_vente=Decimal('1000.00'), prix_achat=Decimal('777.77'),
            quantite_stock=50, marque='MarqueX', garantie=garantie)

    def _devis_deux_options(self, langue='fr', nombre_proprietes=1):
        client = Client.objects.create(
            company=self.company, nom='Alaoui', prenom='Sara',
            telephone='+212600000060', langue_document=langue)
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-ADOC60-{next(_seq)}',
            client=client, statut='accepte', taux_tva=Decimal('20.00'),
            remise_globale=Decimal('0'), option_acceptee='sans_batterie',
            etude_params={'scenario': 'deux_options',
                          'nombre_proprietes': nombre_proprietes})

        def ligne(designation, quantite, produit=None, **kw):
            return LigneDevis.objects.create(
                devis=devis, produit=produit, designation=designation,
                quantite=quantite,
                prix_unitaire=Decimal('1000.00') if produit else None,
                remise=Decimal('0'), **kw)

        ligne('Panneau 550W', Decimal('8'),
              self._produit('Panneau 550W', garantie='25 ans linéaire'))
        ligne('Onduleur réseau 5kW', Decimal('1'),
              self._produit('Onduleur réseau 5kW', garantie='10 ans'),
              variante='sans')
        ligne('Kit batterie', None, type_ligne='section')
        ligne('Onduleur hybride 5kW', Decimal('1'),
              self._produit('Onduleur hybride 5kW'), variante='avec')
        ligne('Batterie lithium 5kWh', Decimal('1'),
              self._produit('Batterie lithium 5kWh'), variante='avec')
        ligne('Monitoring premium', Decimal('1'),
              self._produit('Monitoring premium'), optionnelle=True)
        return devis

    def _chantier(self, **kw):
        devis = self._devis_deux_options(**kw)
        chantier, _ = create_installation_from_devis(
            devis, self.user, self.company)
        self.assertIsNotNone(chantier)
        return chantier

    def _get(self, chantier, route, **params):
        r = self.api.get(f'{BASE}/{chantier.pk}/{route}/', params)
        self.assertEqual(r.status_code, 200, getattr(r, 'data', r))
        return _texte_pdf(b''.join(r.streaming_content)
                          if getattr(r, 'streaming', False) else r.content)

    def _assert_vendu(self, texte, panneaux='8'):
        self.assertIn('Panneau 550W', texte)
        self.assertIn('Onduleur réseau 5kW', texte)
        self.assertNotIn('Batterie lithium 5kWh', texte)
        self.assertNotIn('Onduleur hybride 5kW', texte)
        self.assertNotIn('Monitoring premium', texte)
        self.assertNotIn('Kit batterie', texte)
        self.assertNotIn('None', texte)
        self.assertNotIn('777', texte)  # prix d'achat jamais imprimé
        self.assertRegex(texte, rf'(?m)^\s*{panneaux}\s*$')

    # ── tests ───────────────────────────────────────────────────────────────
    def test_pv_bl_dossier_listent_la_bom_du_chantier(self):
        chantier = self._chantier()
        self.assertEqual(
            [(r['designation'], r['quantite']) for r in chantier.bom],
            [('Panneau 550W', 8.0), ('Onduleur réseau 5kW', 1.0)])
        for route in ('pv-reception', 'bon-livraison', 'dossier-remise'):
            with self.subTest(route=route):
                self._assert_vendu(self._get(chantier, route))
        attestation = self._get(chantier, 'attestation')
        self.assertNotIn('Batterie lithium 5kWh', attestation)
        # Garantie lue sur Produit.garantie via le produit_id de la bom.
        dossier = self._get(chantier, 'dossier-remise')
        self.assertIn('25 ans linéaire', dossier)
        self.assertIn('10 ans', dossier)

    def test_deux_get_memes_lignes(self):
        chantier = self._chantier()
        from apps.documents import builders
        a = builders._composants(chantier)
        b = builders._composants(Installation.objects.get(pk=chantier.pk))
        self.assertEqual(a, b)
        self.assertEqual([c['quantite'] for c in a], [8, 1])

    def test_quantites_multi_villas(self):
        chantier = self._chantier(nombre_proprietes=3)
        for route in ('pv-reception', 'bon-livraison', 'dossier-remise'):
            with self.subTest(route=route):
                self._assert_vendu(self._get(chantier, route), panneaux='24')

    def test_bl_arabe_meme_nomenclature(self):
        chantier = self._chantier(langue='ar')
        texte = self._get(chantier, 'bon-livraison')
        self._assert_vendu(texte)

    def test_repli_option_lines_sans_bom(self):
        """Chantier créé avant N1 (bom vide) : option_lines × N, lignes sans
        quantité exclues."""
        for n, attendu in ((1, '8'), (3, '24')):
            with self.subTest(nombre_proprietes=n):
                devis = self._devis_deux_options(nombre_proprietes=n)
                chantier = Installation.objects.create(
                    company=self.company, reference=f'CH-ADOC60-{next(_seq)}',
                    client=devis.client, devis=devis, bom=[])
                for route in ('pv-reception', 'bon-livraison',
                              'dossier-remise'):
                    self._assert_vendu(
                        self._get(chantier, route), panneaux=attendu)
