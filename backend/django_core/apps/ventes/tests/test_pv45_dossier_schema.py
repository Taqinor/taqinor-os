"""PV45 — la pièce « schéma unifilaire » du dossier réglementaire est FOURNIE.

Depuis FG267, ``regulatory_docs`` déclare la pièce ``schema_unifilaire`` et
``generer-checklist`` la SÈME — mais rien ne la fournissait. Ces tests arment la
boucle enfin fermée : POST ``generer-schema`` rend le PDF (service partagé
``core.pdf``), l'attache par ``records.Attachment`` (jamais un FileField, ARC26)
et bascule la pièce en « fourni », sans doublon au second passage.

Run :
    DB_NAME=erp_ventes python manage.py test \
        apps.ventes.tests.test_pv45_dossier_schema -v 2
"""
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from rest_framework.test import APIClient

from apps.crm.models import Client
from apps.records.models import ALLOWED_TARGETS, Attachment
from apps.stock.models import Produit
from apps.ventes.models import (
    Devis, DossierChecklistItem, LigneDevis, RegulatoryDossier)
from authentication.models import Company

User = get_user_model()

_FAUX_PDF = b'%PDF-1.4 faux schema'


def _faux_rendu(*args, **kwargs):
    """Remplace ``core.pdf.render_pdf`` : rend (octets, clé) comme le vrai."""
    cle = kwargs.get('upload_to')
    return (_FAUX_PDF, cle) if cle else _FAUX_PDF


class GenererSchemaTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom="Acme", slug="pv45-acme")
        self.other = Company.objects.create(nom="Autre", slug="pv45-autre")
        self.user = User.objects.create_user(
            username="pv45_resp", password="x",
            role_legacy="responsable", company=self.company)
        self.api = APIClient()
        self.api.force_authenticate(self.user)
        self.crm_client = Client.objects.create(
            company=self.company, nom="Client PV45", email="pv45@example.com")

    def _make_dossier(self, company):
        devis = Devis.objects.create(
            company=company, reference="DV-PV45/%s" % company.id,
            client=self.crm_client,
            etude_params={"phases": 3, "injection": True})
        panneau = Produit.objects.create(
            company=company, nom="Panneau PV 550W mono",
            sku="PV45-PV-%s" % company.id, prix_vente=Decimal("1000"),
            prix_achat=Decimal("600"), quantite_stock=100)
        LigneDevis.objects.create(
            devis=devis, produit=panneau, designation="Panneau PV 550W mono",
            quantite=20, prix_unitaire=Decimal("1000"))
        return RegulatoryDossier.objects.create(
            company=company, devis=devis, regime_8221='declaration_bt')

    def _url(self, dossier):
        return ("/api/django/ventes/dossiers-reglementaires/%s/generer-schema/"
                % dossier.id)

    def test_le_dossier_est_une_cible_de_piece_jointe(self):
        self.assertIn(('ventes', 'regulatorydossier'), ALLOWED_TARGETS)

    def test_piece_fournie_et_attachee(self):
        dossier = self._make_dossier(self.company)
        with mock.patch('core.pdf.render_pdf', side_effect=_faux_rendu):
            resp = self.api.post(self._url(dossier), {}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.data['remplacee'])

        piece = dossier.checklist_items.get(code='schema_unifilaire')
        self.assertEqual(piece.statut, DossierChecklistItem.Statut.FOURNI)

        attachements = Attachment.objects.filter(
            content_type=ContentType.objects.get_for_model(RegulatoryDossier),
            object_id=dossier.pk)
        self.assertEqual(attachements.count(), 1)
        piece_jointe = attachements.get()
        self.assertEqual(piece_jointe.company_id, self.company.id)
        self.assertEqual(piece_jointe.mime, 'application/pdf')
        self.assertEqual(piece_jointe.size, len(_FAUX_PDF))
        # Clé scopée société : jamais de collision ni de fuite inter-tenant.
        self.assertTrue(
            piece_jointe.file_key.startswith('ventes/%s/' % self.company.id))
        self.assertTrue(piece_jointe.file_key.endswith('.pdf'))

    def test_rejouer_remplace_sans_dupliquer(self):
        dossier = self._make_dossier(self.company)
        with mock.patch('core.pdf.render_pdf', side_effect=_faux_rendu):
            premier = self.api.post(self._url(dossier), {}, format="json")
            second = self.api.post(self._url(dossier), {}, format="json")
        self.assertEqual(second.status_code, 200)
        self.assertTrue(second.data['remplacee'])
        self.assertEqual(premier.data['attachment_id'],
                         second.data['attachment_id'])
        self.assertNotEqual(premier.data['file_key'], second.data['file_key'])
        self.assertEqual(
            Attachment.objects.filter(
                content_type=ContentType.objects.get_for_model(
                    RegulatoryDossier),
                object_id=dossier.pk).count(), 1)
        self.assertEqual(
            dossier.checklist_items.filter(code='schema_unifilaire').count(),
            1)

    def test_apres_generer_checklist_la_piece_existante_bascule(self):
        dossier = self._make_dossier(self.company)
        self.api.post(
            "/api/django/ventes/dossiers-reglementaires/%s/generer-checklist/"
            % dossier.id, {}, format="json")
        piece = dossier.checklist_items.get(code='schema_unifilaire')
        self.assertEqual(piece.statut, DossierChecklistItem.Statut.A_FAIRE)

        with mock.patch('core.pdf.render_pdf', side_effect=_faux_rendu):
            self.api.post(self._url(dossier), {}, format="json")
        piece.refresh_from_db()
        self.assertEqual(piece.statut, DossierChecklistItem.Statut.FOURNI)
        self.assertEqual(
            dossier.checklist_items.filter(code='schema_unifilaire').count(),
            1)

    def test_scope_societe_404(self):
        dossier = self._make_dossier(self.other)
        with mock.patch('core.pdf.render_pdf', side_effect=_faux_rendu):
            resp = self.api.post(self._url(dossier), {}, format="json")
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(Attachment.objects.count(), 0)

    def test_ne_touche_pas_le_statut_du_devis(self):
        dossier = self._make_dossier(self.company)
        statut = dossier.devis.statut
        with mock.patch('core.pdf.render_pdf', side_effect=_faux_rendu):
            self.api.post(self._url(dossier), {}, format="json")
        dossier.devis.refresh_from_db()
        self.assertEqual(dossier.devis.statut, statut)

    def test_aucun_prix_dans_le_schema_rendu(self):
        dossier = self._make_dossier(self.company)
        capture = {}

        def _capture(*args, **kwargs):
            capture['html'] = kwargs.get('html', '')
            return _faux_rendu(*args, **kwargs)

        with mock.patch('core.pdf.render_pdf', side_effect=_capture):
            self.api.post(self._url(dossier), {}, format="json")
        self.assertIn('<svg', capture['html'])
        self.assertNotIn('1000', capture['html'])
        self.assertNotIn('prix', capture['html'].lower())

    def test_role_insuffisant_refuse(self):
        dossier = self._make_dossier(self.company)
        technicien = User.objects.create_user(
            username="pv45_tech", password="x", role_legacy="technicien",
            company=self.company)
        api = APIClient()
        api.force_authenticate(technicien)
        with mock.patch('core.pdf.render_pdf', side_effect=_faux_rendu):
            resp = api.post(self._url(dossier), {}, format="json")
        self.assertIn(resp.status_code, (401, 403))
        self.assertEqual(Attachment.objects.count(), 0)
