"""APDF33 (D-APDF-4) — les prestations (Installation, Transport) ne sont plus des
composants installés / livrés : exclues du PV et du BL, listées à part sous
« Prestations » SANS garantie constructeur dans le dossier de remise.

Constat C-APDF-014 : PV, BL et dossier de remise listaient « Installation » et
« Transport », la remise avec « Garantie selon conditions constructeur ».
Rendu WeasyPrint RÉEL, texte extrait par fitz, vraies routes HTTP.

Run :
    python manage.py test apps.documents.tests.test_apdf_composants_sans_prestations -v2
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
from apps.stock.models import Categorie, Produit
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


class ComposantsTests(TestCase):
    def setUp(self):
        n = next(_seq)
        self.company = Company.objects.create(
            slug=f'apdf33-co-{n}', nom=f'APDF33 Co {n}')
        self.user = User.objects.create_user(
            username=f'apdf33-resp-{n}', password='x',
            company=self.company, role_legacy='responsable')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.cat_service = Categorie.objects.create(
            company=self.company, nom='Services',
            type_equipement=Categorie.TypeEquipement.SERVICE)
        self.panneau = self._produit('Panneau 550W', None, '25 ans linéaire')
        self.install = self._produit('Installation', self.cat_service)
        self.transport = self._produit('Transport', self.cat_service)

    def _produit(self, nom, categorie, garantie=''):
        return Produit.objects.create(
            company=self.company, nom=nom, sku=f'APDF33-{next(_seq)}',
            prix_vente=Decimal('1000.00'), prix_achat=Decimal('500.00'),
            quantite_stock=50, marque='MarqueX', garantie=garantie,
            categorie=categorie)

    def _chantier(self, avec_nature=True):
        client = Client.objects.create(
            company=self.company, nom='Alaoui', prenom='Sara',
            telephone='+212600000033')

        def row(produit, qte):
            r = {'produit_id': produit.id, 'designation': produit.nom,
                 'quantite': qte, 'marque': produit.marque}
            if avec_nature:
                r['nature'] = ('service' if produit.categorie_id
                               else 'materiel')
            return r

        return Installation.objects.create(
            company=self.company, reference=f'CH-APDF33-{next(_seq)}',
            client=client, statut=Installation.Statut.INSTALLE,
            bom=[row(self.panneau, 8.0), row(self.install, 1.0),
                 row(self.transport, 1.0)])

    def _get(self, chantier, route):
        r = self.api.get(f'{BASE}/{chantier.pk}/{route}/')
        self.assertEqual(r.status_code, 200, getattr(r, 'data', r))
        return _texte_pdf(b''.join(r.streaming_content)
                          if getattr(r, 'streaming', False) else r.content)

    def test_pv(self):
        texte = self._get(self._chantier(), 'pv-reception')
        self.assertIn('Panneau 550W', texte)
        self.assertNotIn('Installation', texte.replace(
            'Installation photovoltaïque', ''))
        self.assertNotIn('Transport', texte)

    def test_bl(self):
        texte = self._get(self._chantier(), 'bon-livraison')
        self.assertIn('Panneau 550W', texte)
        self.assertNotIn('Transport', texte)

    def test_remise_sans_garantie_prestation(self):
        texte = self._get(self._chantier(), 'dossier-remise')
        self.assertIn('25 ans linéaire', texte)
        self.assertIn('Prestations', texte)
        self.assertIn('Transport', texte)
        # Une seule garantie imprimée : celle du panneau, aucune par prestation.
        self.assertNotIn('Garantie selon conditions constructeur', texte)

    def _chantier_nature_figee_materiel(self):
        """Nomenclature gelée AVANT la recatégorisation : toutes les lignes
        portent ``nature=materiel`` alors que les produits Installation et
        Transport sont aujourd'hui de catégorie « service »."""
        chantier = self._chantier()
        chantier.bom = [dict(r, nature='materiel') for r in chantier.bom]
        chantier.save(update_fields=['bom'])
        return chantier

    def test_nature_figee_materiel_produit_vivant_service(self):
        """ERR-APDF-BL-PV-PRESTATIONS-COMPOSANTS — le produit vivant prime sur
        la nature figée : ni BL ni PV ne listent les prestations, le dossier de
        remise les range sous « Prestations » sans garantie constructeur."""
        chantier = self._chantier_nature_figee_materiel()
        from apps.documents import builders
        self.assertEqual(
            [c['designation'] for c in builders._composants(chantier)],
            ['Panneau 550W'])
        self.assertEqual(
            [c['designation']
             for c in builders._composants(chantier, services=True)],
            ['Installation', 'Transport'])
        for route in ('bon-livraison', 'pv-reception'):
            with self.subTest(route=route):
                lignes = {ln.strip() for ln in
                          self._get(chantier, route).splitlines()}
                self.assertNotIn('Installation', lignes)
                self.assertNotIn('Transport', lignes)
        remise = self._get(chantier, 'dossier-remise')
        self.assertIn('Prestations', remise)
        self.assertNotIn('Garantie selon conditions constructeur', remise)

    def test_nature_figee_service_reste_service(self):
        """La nature figée « service » reste honorée même si le produit a
        quitté la catégorie service (aucune prestation ne redevient matériel)."""
        chantier = self._chantier()
        self.transport.categorie = None
        self.transport.save(update_fields=['categorie'])
        from apps.documents import builders
        self.assertNotIn(
            'Transport',
            [c['designation'] for c in builders._composants(chantier)])

    def _assert_documents_sans_prestations(self, chantier):
        """BL et PV sans « Installation »/« Transport » ; dossier de remise :
        section « Prestations », aucune garantie constructeur par défaut."""
        from apps.documents import builders
        self.assertEqual(
            [c['designation'] for c in builders._composants(chantier)],
            ['Panneau 550W'])
        self.assertEqual(
            [c['designation']
             for c in builders._composants(chantier, services=True)],
            ['Installation', 'Transport'])
        for route in ('bon-livraison', 'pv-reception'):
            with self.subTest(route=route):
                lignes = {ln.strip() for ln in
                          self._get(chantier, route).splitlines()}
                # La cellule imprime « désignation — marque ».
                self.assertTrue(
                    any(ln.startswith('Panneau 550W') for ln in lignes),
                    lignes)
                self.assertNotIn('Installation', lignes)
                self.assertNotIn('Transport', lignes)
        remise = self._get(chantier, 'dossier-remise')
        self.assertIn('25 ans linéaire', remise)
        self.assertIn('Prestations', remise)
        self.assertNotIn('Garantie selon conditions constructeur', remise)

    def test_produit_absent_repli_role_de_la_designation(self):
        """ERR-APDF-BL-PV-PRESTATIONS-COMPOSANTS (chantier 17, société 4) — la
        nomenclature figée dit ``materiel`` et ses produits n'existent plus :
        le rôle canonique de la désignation (``role_effectif`` + classifieur
        ventes) range « Installation »/« Transport » en prestations."""
        chantier = self._chantier_nature_figee_materiel()
        absent = Produit.objects.order_by('-id').values_list(
            'id', flat=True).first() + 1000
        chantier.bom = [
            r if r['designation'] == 'Panneau 550W'
            else dict(r, produit_id=absent + i)
            for i, r in enumerate(chantier.bom)]
        chantier.save(update_fields=['bom'])
        self._assert_documents_sans_prestations(chantier)

    def test_devis_installation_transport_lignes_libres(self):
        """Un devis accepté avec des lignes « Installation » et « Transport »
        (lignes libres, sans produit catalogue) : le chantier créé du devis
        émet BL, PV et dossier de remise sans ces prestations comme
        composants, et sans « Garantie selon conditions constructeur »."""
        from apps.installations.services import create_installation_from_devis
        from apps.ventes.models import Devis, LigneDevis
        client = Client.objects.create(
            company=self.company, nom='Bennani', prenom='Omar',
            telephone='+212600000034')
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-APDF33-{next(_seq)}',
            client=client, statut='accepte', taux_tva=Decimal('20.00'),
            remise_globale=Decimal('0'))
        for designation, quantite, produit in (
                ('Panneau 550W', Decimal('8'), self.panneau),
                ('Installation', Decimal('1'), None),
                ('Transport', Decimal('1'), None)):
            LigneDevis.objects.create(
                devis=devis, produit=produit, designation=designation,
                quantite=quantite, prix_unitaire=Decimal('1000.00'),
                remise=Decimal('0'))
        chantier, _ = create_installation_from_devis(
            devis, self.user, self.company)
        self.assertIsNotNone(chantier)
        Installation.objects.filter(pk=chantier.pk).update(
            statut=Installation.Statut.INSTALLE)
        chantier.refresh_from_db()
        self._assert_documents_sans_prestations(chantier)
        # Même règle sur le repli sans nomenclature (lignes du devis).
        Installation.objects.filter(pk=chantier.pk).update(bom=[])
        chantier.refresh_from_db()
        self._assert_documents_sans_prestations(chantier)

    def test_bom_ancienne(self):
        """Nomenclature sans nature : filtrée par lecture du produit."""
        chantier = self._chantier(avec_nature=False)
        from apps.documents import builders
        self.assertEqual(
            [c['designation'] for c in builders._composants(chantier)],
            ['Panneau 550W'])
        self.assertEqual(
            [c['designation']
             for c in builders._composants(chantier, services=True)],
            ['Installation', 'Transport'])
