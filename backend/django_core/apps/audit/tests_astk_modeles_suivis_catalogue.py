"""ASTK145 — données maîtres catalogue et tarif fournisseur au journal d'audit.

Constat C-ASTK-024 (sondes PRIX-4 / CAT-6) : un PATCH du prix d'achat d'un
tarif fournisseur (100 → 75) ou la suppression d'une catégorie ne laissaient
AUCUNE ligne ``AuditLog``. Les six modèles maîtres (Categorie, Marque,
KitProduit, KitComposant, PrixFournisseur, PalierPrixFournisseur) entrent dans
``TRACKED_MODELS`` (app_label lu sur ``_meta``) : chaque création/
modification/suppression faite pendant une requête laisse une ligne avec
l'acteur et, pour une modification, le diff old→new. Un GET n'en écrit
aucune ; l'import xlsx du tarif ne compte pas double (sa ligne dédiée
« Import … » reste la seule ligne UPDATE).

Run :
    python manage.py test apps.audit.tests_astk_modeles_suivis_catalogue -v2
"""
import io
import itertools
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.audit.models import AuditLog
from apps.audit.modeles_suivis import TRACKED_MODELS
from apps.stock.models import (
    Categorie, Fournisseur, KitComposant, KitProduit, Marque,
    PalierPrixFournisseur, PrixFournisseur, Produit,
)
from authentication.models import Company, CustomUser as User

_seq = itertools.count(1)


def _lignes(instance, action=None):
    qs = AuditLog.objects.filter(
        content_type__app_label=instance._meta.app_label,
        content_type__model=instance._meta.model_name,
        object_id=str(instance.pk))
    if action is not None:
        qs = qs.filter(action=action)
    return qs


class ModelesSuivisCatalogueTests(TestCase):
    def setUp(self):
        n = next(_seq)
        self.company = Company.objects.create(
            nom=f'ASTK145 {n}', slug=f'astk145-{n}')
        self.user = User.objects.create_superuser(
            username=f'astk145_admin_{n}', password='x',
            email=f'astk145-{n}@example.test')
        self.user.company = self.company
        self.user.save(update_fields=['company'])
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur A145', sku=f'OND-A145-{n}',
            prix_vente=Decimal('2000'), prix_achat=Decimal('1200'))
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom=f'Fournisseur A145 {n}')

    def test_six_modeles_inscrits_par_app_label_meta(self):
        for model in (Categorie, Marque, KitProduit, KitComposant,
                      PrixFournisseur, PalierPrixFournisseur):
            with self.subTest(modele=model.__name__):
                self.assertIn(
                    (model._meta.app_label, model._meta.object_name),
                    TRACKED_MODELS)

    def test_prix_fournisseur_patch_trace_le_diff_et_l_acteur(self):
        pf = PrixFournisseur.objects.create(
            company=self.company, produit=self.produit,
            fournisseur=self.fournisseur, prix_achat=Decimal('100.00'))
        self.assertEqual(_lignes(pf).count(), 0)  # hors requête : rien

        get = self.api.get(f'/api/django/stock/prix-fournisseurs/{pf.pk}/')
        self.assertEqual(get.status_code, 200, get.content)
        self.assertEqual(_lignes(pf).count(), 0)  # un GET n'écrit rien

        rep = self.api.patch(
            f'/api/django/stock/prix-fournisseurs/{pf.pk}/',
            {'prix_achat': '75.00'}, format='json')
        self.assertEqual(rep.status_code, 200, rep.content)
        lignes = _lignes(pf, AuditLog.Action.UPDATE)
        self.assertEqual(lignes.count(), 1)
        ligne = lignes.get()
        self.assertEqual(ligne.user, self.user)
        diff = {c['field']: c for c in (ligne.changes or [])}
        self.assertEqual(diff['prix_achat']['old'], '100.00')
        self.assertEqual(diff['prix_achat']['new'], '75.00')

    def test_palier_prix_fournisseur_trace(self):
        pf = PrixFournisseur.objects.create(
            company=self.company, produit=self.produit,
            fournisseur=self.fournisseur, prix_achat=Decimal('100.00'))
        palier = PalierPrixFournisseur.objects.create(
            prix_fournisseur=pf, qte_min=10, prix=Decimal('90.00'))
        from apps.audit import recorder
        from types import SimpleNamespace
        recorder.begin_request(SimpleNamespace(user=self.user))
        try:
            palier.prix = Decimal('85.00')
            palier.save()
        finally:
            recorder.end_request()
        ligne = _lignes(palier, AuditLog.Action.UPDATE).get()
        self.assertEqual(ligne.user, self.user)
        diff = {c['field']: c for c in (ligne.changes or [])}
        self.assertEqual(diff['prix']['old'], '90.00')
        self.assertEqual(diff['prix']['new'], '85.00')

    def test_categorie_delete_trace(self):
        categorie = Categorie.objects.create(
            company=self.company, nom='Catégorie vide A145')
        pk = categorie.pk
        rep = self.api.delete(f'/api/django/stock/categories/{pk}/')
        self.assertIn(rep.status_code, (200, 204), rep.content)
        ligne = AuditLog.objects.get(
            content_type__app_label='stock', content_type__model='categorie',
            object_id=str(pk), action=AuditLog.Action.DELETE)
        self.assertEqual(ligne.user, self.user)

    def test_marque_patch_trace(self):
        marque = Marque.objects.create(company=self.company, nom='Marque A')
        rep = self.api.patch(
            f'/api/django/stock/marques/{marque.pk}/', {'nom': 'Marque B'},
            format='json')
        self.assertEqual(rep.status_code, 200, rep.content)
        ligne = _lignes(marque, AuditLog.Action.UPDATE).get()
        self.assertEqual(ligne.user, self.user)
        diff = {c['field']: c for c in (ligne.changes or [])}
        self.assertEqual(diff['nom']['old'], 'Marque A')
        self.assertEqual(diff['nom']['new'], 'Marque B')

    def test_kit_put_trace_kit_et_composants(self):
        autre = Produit.objects.create(
            company=self.company, nom='Câble A145', sku='CAB-A145',
            prix_vente=Decimal('10'))
        kit = KitProduit.objects.create(company=self.company, nom='Kit A')
        KitComposant.objects.create(
            kit=kit, produit=self.produit, quantite=Decimal('1'))
        rep = self.api.put(
            f'/api/django/stock/kits/{kit.pk}/',
            {'nom': 'Kit A renommé',
             'composants': [{'produit': autre.pk, 'quantite': '2'}]},
            format='json')
        self.assertEqual(rep.status_code, 200, rep.content)
        ligne = _lignes(kit, AuditLog.Action.UPDATE).get()
        self.assertEqual(ligne.user, self.user)
        diff = {c['field']: c for c in (ligne.changes or [])}
        self.assertEqual(diff['nom']['new'], 'Kit A renommé')
        nouveau = KitComposant.objects.get(kit=kit, produit=autre)
        self.assertEqual(
            _lignes(nouveau, AuditLog.Action.CREATE).count(), 1)
        self.assertTrue(AuditLog.objects.filter(
            content_type__app_label='stock',
            content_type__model='kitcomposant',
            action=AuditLog.Action.DELETE).exists())

    def test_import_tarif_une_seule_ligne_update(self):
        """Jumeau : l'import xlsx écrit déjà sa ligne dédiée « Import … » —
        le suivi générique ne doit pas en ajouter une seconde."""
        from openpyxl import Workbook
        pf = PrixFournisseur.objects.create(
            company=self.company, produit=self.produit,
            fournisseur=self.fournisseur, prix_achat=Decimal('100.00'))
        wb = Workbook()
        ws = wb.active
        ws.append(['sku', 'produit', 'ref_produit_fournisseur', 'prix_achat',
                   'date_debut', 'date_fin', 'paliers'])
        ws.append([self.produit.sku, self.produit.nom, '', 75, None, None,
                   ''])
        buf = io.BytesIO()
        wb.save(buf)
        upload = SimpleUploadedFile(
            'tarif.xlsx', buf.getvalue(),
            content_type=('application/vnd.openxmlformats-officedocument'
                          '.spreadsheetml.sheet'))
        rep = self.api.post(
            '/api/django/stock/prix-fournisseurs/import-xlsx/',
            {'fournisseur': self.fournisseur.pk, 'file': upload,
             'ecraser': 'true'}, format='multipart')
        self.assertEqual(rep.status_code, 200, rep.content)
        pf.refresh_from_db()
        self.assertEqual(pf.prix_achat, Decimal('75.00'))
        lignes = _lignes(pf, AuditLog.Action.UPDATE)
        self.assertEqual(lignes.count(), 1, list(lignes.values('detail')))
        self.assertTrue(lignes.get().detail.startswith('Import'))
