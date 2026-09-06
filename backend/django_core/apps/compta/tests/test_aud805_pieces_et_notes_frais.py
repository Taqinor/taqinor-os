"""AUD805 — pièces comptables : `PieceJustificative` ajoutable/supprimable
APRÈS validation de l'écriture ; `NoteFrais` DELETE laissant des écritures
orphelines au grand livre.

Constat d'origine :

* `PieceJustificativeViewSet` hérite de `_ComptaBaseViewSet`
  (TenantMixin + IsResponsableOrAdmin) SANS `perform_create`/`perform_destroy`
  vérifiant `ecriture.statut` : n'importe quel Responsable supprimait la
  facture scannée d'une écriture VALIDÉE (204), ou en attachait une nouvelle
  après coup — la preuve documentaire du grand livre changeait sous une
  validation posée ;
* `NoteFraisViewSet` n'avait pas non plus de `perform_destroy` : un DELETE
  réussissait même sur `statut=remboursee`, alors qu'`ecriture_charge` et
  `ecriture_remboursement` sont en `on_delete=SET_NULL` — les DEUX écritures
  postées au grand livre survivaient ORPHELINES, sans preuve ni traçabilité de
  l'employé remboursé.

Après correctif : les trois opérations → 400. La moitié STOCKAGE FileField
(docstring trompeur, `store_attachment`) est une EXTENSION séparée d'AUD309,
cf. AUD835 — hors de ce test.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.compta import services
from apps.compta.models import EcritureComptable, Journal, PieceJustificative
from apps.frais.models import NoteFrais
from authentication.models import Company

User = get_user_model()

URL_PIECES = '/api/django/compta/pieces-justificatives/'
URL_NOTES = '/api/django/compta/notes-frais/'


class Aud805Base(TestCase):
    def setUp(self):
        self.co, _ = Company.objects.get_or_create(
            slug='aud805-co', defaults={'nom': 'AUD805 Co'})
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)
        self.saisisseur = User.objects.create_user(
            username='aud805_saisi', password='x', company=self.co,
            role_legacy='responsable')
        self.valideur = User.objects.create_user(
            username='aud805_valid', password='x', company=self.co,
            role_legacy='responsable')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.valideur)}')

    def _ecriture(self, jour, libelle, montant, validee=False):
        journal = services._journal(
            self.co, Journal.Type.OPERATIONS_DIVERSES)
        lignes = [
            {'compte': services.get_compte(self.co, '5141'),
             'debit': Decimal(montant), 'credit': Decimal('0')},
            {'compte': services.get_compte(self.co, '7121'),
             'debit': Decimal('0'), 'credit': Decimal(montant)},
        ]
        ec = services.creer_ecriture(
            self.co, journal, jour, libelle, lignes,
            created_by=self.saisisseur)
        if validee:
            services.valider_ecriture(ec, user=self.valideur)
            ec.refresh_from_db()
        return ec


class Aud805PiecesJustificativesTests(Aud805Base):
    def _piece(self, ecriture):
        return PieceJustificative.objects.create(
            company=self.co, ecriture=ecriture, libelle='Facture scannée',
            fichier=SimpleUploadedFile('f.pdf', b'%PDF-1.4', 'application/pdf'))

    def test_delete_piece_sur_ecriture_validee_refuse(self):
        ec = self._ecriture(date(2026, 4, 1), 'Validée', '400', validee=True)
        piece = self._piece(ec)
        res = self.api.delete(f'{URL_PIECES}{piece.id}/')
        self.assertEqual(res.status_code, 400)
        self.assertTrue(
            PieceJustificative.objects.filter(pk=piece.pk).exists())

    def test_post_piece_sur_ecriture_validee_refuse(self):
        ec = self._ecriture(date(2026, 4, 2), 'Validée 2', '400', validee=True)
        res = self.api.post(URL_PIECES, {
            'ecriture': ec.id, 'libelle': 'Ajoutée après coup',
            'fichier': SimpleUploadedFile(
                'g.pdf', b'%PDF-1.4', 'application/pdf'),
        }, format='multipart')
        self.assertEqual(res.status_code, 400)
        self.assertEqual(
            PieceJustificative.objects.filter(ecriture=ec).count(), 0)

    def test_piece_sur_ecriture_brouillon_reste_gerable(self):
        # AUD835 — le dépôt passe par MinIO (`records.storage`) : on le mocke
        # pour que ce test reste une assertion sur la RÈGLE AUD805, pas sur la
        # disponibilité du stockage objet.
        from unittest import mock

        ec = self._ecriture(date(2026, 4, 3), 'Brouillon', '400')
        meta = ({'file_key': f'attachments/{self.co.id}/h.pdf',
                 'filename': 'h.pdf', 'size': 8,
                 'mime': 'application/pdf'}, None)
        with mock.patch('apps.records.storage.store_attachment',
                        return_value=meta):
            res = self.api.post(URL_PIECES, {
                'ecriture': ec.id, 'libelle': 'Reçu',
                'fichier': SimpleUploadedFile(
                    'h.pdf', b'%PDF-1.4', 'application/pdf'),
            }, format='multipart')
        self.assertEqual(res.status_code, 201)
        piece_id = res.data['id']
        res = self.api.delete(f'{URL_PIECES}{piece_id}/')
        self.assertEqual(res.status_code, 204)


class Aud805NoteFraisTests(Aud805Base):
    def _note(self, statut, **kw):
        return NoteFrais.objects.create(
            company=self.co, employe=self.saisisseur,
            date_frais=date(2026, 4, 10), montant=Decimal('250.00'),
            motif='Déplacement', statut=statut, **kw)

    def test_delete_note_remboursee_refuse(self):
        ec_charge = self._ecriture(date(2026, 4, 10), 'Charge NDF', '250')
        note = self._note(NoteFrais.Statut.REMBOURSEE,
                          ecriture_charge=ec_charge)
        res = self.api.delete(f'{URL_NOTES}{note.id}/')
        self.assertEqual(res.status_code, 400)
        note.refresh_from_db()
        self.assertEqual(note.statut, NoteFrais.Statut.REMBOURSEE)
        # L'écriture de charge n'est PAS devenue orpheline.
        self.assertTrue(
            EcritureComptable.objects.filter(pk=ec_charge.pk).exists())

    def test_delete_note_validee_refuse(self):
        note = self._note(NoteFrais.Statut.VALIDEE)
        res = self.api.delete(f'{URL_NOTES}{note.id}/')
        self.assertEqual(res.status_code, 400)
        self.assertTrue(NoteFrais.objects.filter(pk=note.pk).exists())

    def test_delete_note_brouillon_reste_possible(self):
        note = self._note(NoteFrais.Statut.BROUILLON)
        res = self.api.delete(f'{URL_NOTES}{note.id}/')
        self.assertEqual(res.status_code, 204)
        self.assertFalse(NoteFrais.objects.filter(pk=note.pk).exists())

    def test_delete_note_soumise_avec_ecriture_liee_refuse(self):
        """Garde-fou par les ÉCRITURES, pas seulement par le statut."""
        ec_charge = self._ecriture(date(2026, 4, 11), 'Charge NDF 2', '250')
        note = self._note(NoteFrais.Statut.SOUMISE,
                          ecriture_charge=ec_charge)
        res = self.api.delete(f'{URL_NOTES}{note.id}/')
        self.assertEqual(res.status_code, 400)
        self.assertTrue(NoteFrais.objects.filter(pk=note.pk).exists())
