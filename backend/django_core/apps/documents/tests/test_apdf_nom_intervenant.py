"""APDF34 — le PV et le dossier de remise n'impriment jamais l'identifiant de
connexion du technicien (C-APDF-015, S3) : nom complet, sinon raison sociale.

Rendu WeasyPrint RÉEL (aucun mock), texte extrait par fitz.

Run :
    python manage.py test apps.documents.tests.test_apdf_nom_intervenant -v2
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


def _texte_pdf(contenu):
    doc = fitz.open(stream=contenu, filetype='pdf')
    try:
        return '\n'.join(page.get_text() for page in doc)
    finally:
        doc.close()


class NomIntervenantDocumentsTests(TestCase):
    def setUp(self):
        n = next(_seq)
        self.company = Company.objects.create(
            slug=f'apdf34-co-{n}', nom=f'APDF34 Co {n}')
        profil = CompanyProfile.get(company=self.company)
        profil.nom = 'Raison Sociale APDF34'
        profil.save()
        self.login = f'demo_admin_apdf34_{n}'
        self.user = User.objects.create_user(
            username=self.login, password='x',
            company=self.company, role_legacy='responsable')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def _chantier(self):
        client = Client.objects.create(
            company=self.company, nom='Alaoui', prenom='Sara',
            telephone='+212600000034')
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-APDF34-{next(_seq)}',
            client=client, statut='accepte', taux_tva=Decimal('20.00'),
            remise_globale=Decimal('0'))
        produit = Produit.objects.create(
            company=self.company, nom='Panneau 550W',
            sku=f'APDF34-{next(_seq)}', prix_vente=Decimal('1000.00'),
            prix_achat=Decimal('777.77'), quantite_stock=50)
        LigneDevis.objects.create(
            devis=devis, produit=produit, designation='Panneau 550W',
            quantite=Decimal('8'), prix_unitaire=Decimal('1000.00'),
            remise=Decimal('0'))
        chantier, _ = create_installation_from_devis(
            devis, self.user, self.company)
        Installation.objects.filter(pk=chantier.pk).update(
            statut=Installation.Statut.INSTALLE,
            technicien_responsable=self.user)
        chantier.refresh_from_db()
        return chantier

    def _get(self, chantier, route):
        r = self.api.get(f'{BASE}/{chantier.pk}/{route}/')
        self.assertEqual(r.status_code, 200, getattr(r, 'data', r))
        return _texte_pdf(b''.join(r.streaming_content)
                          if getattr(r, 'streaming', False) else r.content)

    def test_pv_sans_username(self):
        texte = self._get(self._chantier(), 'pv-reception')
        self.assertNotIn(self.login, texte)
        self.assertIn('Raison Sociale APDF34', texte)

    def test_remise_sans_username(self):
        texte = self._get(self._chantier(), 'dossier-remise')
        self.assertNotIn(self.login, texte)

    def test_nom_complet_prefere(self):
        self.user.first_name = 'Karim'
        self.user.last_name = 'Tazi'
        self.user.save()
        texte = self._get(self._chantier(), 'pv-reception')
        self.assertIn('Karim Tazi', texte)
        self.assertNotIn(self.login, texte)
