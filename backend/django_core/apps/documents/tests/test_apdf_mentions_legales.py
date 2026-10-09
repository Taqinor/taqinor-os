"""APDF32 — ICE / IF / RC / patente de la société sur les documents chantier.

Constat C-APDF-016 (S3), décision D-APDF-2 = (a) : BL chantier (FR et AR), PV
de réception et dossier de remise portent les mêmes mentions légales que le BL
de livraison planifiée. Profil vide → aucun libellé orphelin.

Rendu WeasyPrint RÉEL (aucun mock), texte extrait par fitz.

Run :
    python manage.py test apps.documents.tests.test_apdf_mentions_legales -v2
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
from apps.parametres.models import CompanyProfile
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis
from authentication.models import Company

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/documents/chantiers'
ROUTES = ('bon-livraison', 'pv-reception', 'dossier-remise')


def _texte_pdf(contenu):
    doc = fitz.open(stream=contenu, filetype='pdf')
    try:
        return '\n'.join(page.get_text() for page in doc)
    finally:
        doc.close()


class MentionsLegalesChantierTests(TestCase):
    def setUp(self):
        n = next(_seq)
        self.company = Company.objects.create(
            slug=f'apdf32-co-{n}', nom=f'APDF32 Co {n}')
        self.user = User.objects.create_user(
            username=f'apdf32-resp-{n}', password='x',
            company=self.company, role_legacy='responsable')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def _profil(self, **champs):
        profil = CompanyProfile.get(company=self.company)
        for k, v in champs.items():
            setattr(profil, k, v)
        profil.save()

    def _chantier(self, langue='fr'):
        client = Client.objects.create(
            company=self.company, nom='Alaoui', prenom='Sara',
            telephone='+212600000032', langue_document=langue)
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-APDF32-{next(_seq)}',
            client=client, statut='accepte', taux_tva=Decimal('20.00'),
            remise_globale=Decimal('0'))
        produit = Produit.objects.create(
            company=self.company, nom='Panneau 550W',
            sku=f'APDF32-{next(_seq)}', prix_vente=Decimal('1000.00'),
            prix_achat=Decimal('777.77'), quantite_stock=50)
        LigneDevis.objects.create(
            devis=devis, produit=produit, designation='Panneau 550W',
            quantite=Decimal('8'), prix_unitaire=Decimal('1000.00'),
            remise=Decimal('0'))
        chantier, _ = create_installation_from_devis(
            devis, self.user, self.company)
        Installation.objects.filter(pk=chantier.pk).update(
            statut=Installation.Statut.INSTALLE)
        chantier.refresh_from_db()
        return chantier

    def _get(self, chantier, route):
        r = self.api.get(f'{BASE}/{chantier.pk}/{route}/')
        self.assertEqual(r.status_code, 200, getattr(r, 'data', r))
        return _texte_pdf(b''.join(r.streaming_content)
                          if getattr(r, 'streaming', False) else r.content)

    def _remplir(self):
        self._profil(ice='001234567000089', identifiant_fiscal='IF-4455',
                     rc='RC-9988', patente='PAT-7766')

    def _assert_mentions(self, texte):
        for valeur in ('001234567000089', 'IF-4455', 'RC-9988', 'PAT-7766'):
            self.assertIn(valeur, texte)

    def test_bl_fr(self):
        self._remplir()
        self._assert_mentions(self._get(self._chantier(), 'bon-livraison'))

    def test_bl_ar(self):
        self._remplir()
        chantier = self._chantier(langue='ar')
        self._assert_mentions(self._get(chantier, 'bon-livraison'))

    def test_pv_remise_selon_decision(self):
        """D-APDF-2 = (a) : PV et dossier de remise portent aussi les mentions."""
        self._remplir()
        chantier = self._chantier()
        for route in ('pv-reception', 'dossier-remise'):
            with self.subTest(route=route):
                self._assert_mentions(self._get(chantier, route))

    def test_profil_vide_rien(self):
        self._profil(ice='', identifiant_fiscal='', rc='', patente='')
        chantier = self._chantier()
        for route in ROUTES:
            with self.subTest(route=route):
                texte = self._get(chantier, route)
                for libelle in ('ICE :', 'IF :', 'RC :', 'Patente :'):
                    self.assertNotIn(libelle, texte)
