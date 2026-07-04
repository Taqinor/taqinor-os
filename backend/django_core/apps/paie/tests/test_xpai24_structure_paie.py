"""Tests XPAI24 — Structures de paie par catégorie (modèles de rubriques).

Couvre : le seed idempotent des 3 structures standard, l'application d'une
structure à un profil (copie des ``RubriqueEmploye``, jamais un doublon), et
la pré-affectation automatique à la CRÉATION d'un profil portant une
``structure``.
"""
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company
from apps.paie.models import ProfilPaie, RubriqueEmploye, StructurePaie
from apps.paie.services import (
    appliquer_structure_a_profil, ensure_rubriques_standard,
    ensure_structures_standard,
)
from apps.rh.models import DossierEmploye


def make_company(slug):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': slug})
    return company


class EnsureStructuresStandardTests(TestCase):
    def setUp(self):
        self.co = make_company('xpai24-structures')
        ensure_rubriques_standard(self.co)

    def test_seed_cree_3_structures(self):
        resultat = ensure_structures_standard(self.co)
        self.assertEqual(resultat['structures'], 3)
        self.assertEqual(
            StructurePaie.objects.filter(company=self.co).count(), 3)
        codes = set(
            StructurePaie.objects.filter(company=self.co)
            .values_list('code', flat=True))
        self.assertEqual(codes, {'CADRE', 'EMPLOYE', 'OUVRIER'})

    def test_seed_idempotent(self):
        ensure_structures_standard(self.co)
        resultat = ensure_structures_standard(self.co)
        self.assertEqual(resultat['structures'], 0)
        self.assertEqual(
            StructurePaie.objects.filter(company=self.co).count(), 3)

    def test_ouvrier_a_panier_et_transport(self):
        ensure_structures_standard(self.co)
        ouvrier = StructurePaie.objects.get(company=self.co, code='OUVRIER')
        codes = set(
            ouvrier.rubriques_defaut.values_list('rubrique__code', flat=True))
        self.assertEqual(codes, {'PANIER', 'TRANSPORT'})

    def test_seed_ne_touche_pas_structure_editee(self):
        ensure_structures_standard(self.co)
        ouvrier = StructurePaie.objects.get(company=self.co, code='OUVRIER')
        ouvrier.libelle = 'Ouvrier chantier (édité)'
        ouvrier.save()
        ensure_structures_standard(self.co)
        ouvrier.refresh_from_db()
        self.assertEqual(ouvrier.libelle, 'Ouvrier chantier (édité)')


class AppliquerStructureAProfilTests(TestCase):
    def setUp(self):
        self.co = make_company('xpai24-application')
        ensure_rubriques_standard(self.co)
        ensure_structures_standard(self.co)
        self.dossier = DossierEmploye.objects.create(
            company=self.co, matricule='M1', nom='Ali', prenom='Ben')

    def _profil(self):
        return ProfilPaie.objects.create(
            company=self.co, employe=self.dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('5000'))

    def test_applique_rattache_rubriques_ouvrier(self):
        profil = self._profil()
        ouvrier = StructurePaie.objects.get(company=self.co, code='OUVRIER')
        nb = appliquer_structure_a_profil(profil, ouvrier)
        self.assertEqual(nb, 2)
        codes = set(
            RubriqueEmploye.objects.filter(profil=profil)
            .values_list('rubrique__code', flat=True))
        self.assertEqual(codes, {'PANIER', 'TRANSPORT'})
        profil.refresh_from_db()
        self.assertEqual(profil.structure_id, ouvrier.id)

    def test_applique_idempotent_ne_duplique_pas(self):
        profil = self._profil()
        ouvrier = StructurePaie.objects.get(company=self.co, code='OUVRIER')
        appliquer_structure_a_profil(profil, ouvrier)
        nb2 = appliquer_structure_a_profil(profil, ouvrier)
        self.assertEqual(nb2, 0)
        self.assertEqual(RubriqueEmploye.objects.filter(profil=profil).count(), 2)

    def test_applique_ne_touche_pas_montant_deja_edite(self):
        profil = self._profil()
        ouvrier = StructurePaie.objects.get(company=self.co, code='OUVRIER')
        appliquer_structure_a_profil(profil, ouvrier)
        rattachement = RubriqueEmploye.objects.get(
            profil=profil, rubrique__code='PANIER')
        rattachement.montant = Decimal('999')
        rattachement.save()
        appliquer_structure_a_profil(profil, ouvrier)
        rattachement.refresh_from_db()
        self.assertEqual(rattachement.montant, Decimal('999'))

    def test_autre_societe_refusee(self):
        profil = self._profil()
        autre_co = make_company('xpai24-autre')
        autre_structure = StructurePaie.objects.create(
            company=autre_co, code='X', libelle='X')
        with self.assertRaises(ValueError):
            appliquer_structure_a_profil(profil, autre_structure)

    def test_creation_profil_avec_structure_preaffecte_via_api(self):
        from django.contrib.auth import get_user_model
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import AccessToken

        User = get_user_model()
        user = User.objects.create_user(
            username='resp24', password='x', company=self.co,
            role_legacy='responsable')
        client = APIClient()
        client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        ouvrier = StructurePaie.objects.get(company=self.co, code='OUVRIER')
        dossier2 = DossierEmploye.objects.create(
            company=self.co, matricule='M2', nom='Sara', prenom='K')
        resp = client.post('/api/django/paie/profils/', {
            'employe': dossier2.id,
            'type_remuneration': ProfilPaie.TYPE_MENSUEL,
            'salaire_base': '4000',
            'structure': ouvrier.id,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        profil = ProfilPaie.objects.get(employe=dossier2)
        self.assertEqual(
            RubriqueEmploye.objects.filter(profil=profil).count(), 2)
