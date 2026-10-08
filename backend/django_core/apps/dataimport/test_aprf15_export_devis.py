"""APRF15 (C-APRF-004 + C-APRF-028) — l'export générique « Devis »
(``POST /imports/export/devis/``, ``_devis_rows``) lit des devis passés par
``devis_avec_totaux`` (APRF7) et refuse ``ids=[]``.

Sonde V_VB (avant) : 3 devis 8 requêtes, 15 devis 35 (``ventes_lignedevis``
34) ; ``ids=[]`` → 200 avec TOUS les devis de la société. Ici : 3 puis 15
devis exportés coûtent le même nombre de requêtes, chaque « Total TTC » du
fichier est celui du devis relu un à un, et ``ids=[]`` → 400.

Test-du-test : retirer le préchargement ⇒ +requêtes par devis,
``test_requetes_constantes`` échoue ; retirer le 400 ⇒
``test_ids_vide_refuse`` échoue.

Run :
    docker compose exec django_core python manage.py test \
        apps.dataimport.test_aprf15_export_devis -v 2
"""
import io
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis
from authentication.models import Company

User = get_user_model()
URL = '/api/django/imports/export/devis/'


class ExportDevisTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(nom='APRF15 Co', slug='aprf15-co')
        self.user = User.objects.create_user(
            username='aprf15_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = APIClient()
        self.api.force_authenticate(user=self.user)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client APRF15')
        self.produits = [
            Produit.objects.create(
                company=self.company, nom=f'Produit {i}', sku=f'APRF15-{i}',
                prix_vente=Decimal('1000'), quantite_stock=0)
            for i in range(2)]
        self.n = 0

    def _devis(self, nombre):
        crees = []
        for _ in range(nombre):
            self.n += 1
            devis = Devis.objects.create(
                company=self.company, reference=f'DEV-APRF15-{self.n:03d}',
                client=self.client_obj, statut=Devis.Statut.ENVOYE,
                taux_tva=Decimal('20'), remise_globale=Decimal('0'))
            for i, produit in enumerate(self.produits):
                LigneDevis.objects.create(
                    devis=devis, produit=produit, designation=produit.nom,
                    quantite=Decimal(str(1 + (self.n + i) % 5)),
                    prix_unitaire=Decimal('1000'), remise=Decimal('0'))
            crees.append(devis)
        return crees

    def _exporter(self, ids):
        # Échauffement (profil société créé à la volée au premier appel).
        self.api.post(URL, {'ids': ids}, format='json')
        with CaptureQueriesContext(connection) as ctx:
            reponse = self.api.post(URL, {'ids': ids}, format='json')
        self.assertEqual(reponse.status_code, 200)
        corps = (b''.join(reponse.streaming_content) if reponse.streaming
                 else reponse.content)
        return len(ctx.captured_queries), corps

    def _lignes_xlsx(self, corps):
        from openpyxl import load_workbook
        feuille = load_workbook(io.BytesIO(corps)).active
        return [list(r) for r in feuille.iter_rows(values_only=True)]

    def test_requetes_constantes(self):
        trois = [d.id for d in self._devis(3)]
        quinze = trois + [d.id for d in self._devis(12)]
        n3, _ = self._exporter(trois)
        n15, corps = self._exporter(quinze)
        self.assertEqual(n15, n3)
        # Fichier : chaque « Total TTC » est celui du devis relu un à un.
        lignes = self._lignes_xlsx(corps)
        entetes, donnees = lignes[0], lignes[1:]
        col_ref = entetes.index('Référence')
        col_ttc = entetes.index('Total TTC')
        self.assertEqual(len(donnees), 15)
        for ligne in donnees:
            devis = Devis.objects.get(company=self.company,
                                      reference=ligne[col_ref])
            self.assertEqual(str(ligne[col_ttc]), str(devis.total_ttc or 0))

    def test_ids_vide_refuse(self):
        self._devis(3)
        reponse = self.api.post(URL, {'ids': []}, format='json')
        self.assertEqual(reponse.status_code, 400)
        self.assertIn('Sélection requise', reponse.data['detail'])
        reponse = self.api.post(URL, {}, format='json')
        self.assertEqual(reponse.status_code, 400)
