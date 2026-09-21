"""AUD510 — la preuve de signature et l'instantané « immuable » sont verrouillés
côté admin Django aussi.

``SignatureContratAdmin`` et ``VersionContratAdmin`` étaient des ``ModelAdmin``
NUS : aucun ``has_delete_permission``, aucun ``has_change_permission``. Un
simple compte ``is_staff`` doté des permissions modèle par défaut pouvait donc
SUPPRIMER une ``SignatureContrat`` (preuve loi 53-05) ou RÉÉCRIRE
``VersionContrat.contenu`` depuis ``/django-admin/``. ``VersionContrat`` promet
pourtant l'immuabilité dans son propre docstring — une promesse qui ne tenait
que côté API DRF (``ReadOnlyModelViewSet``), pas côté admin.
"""
import itertools
from decimal import Decimal

from django.contrib.admin.sites import site
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from apps.contrats.models import (
    Contrat, SignatureContrat, VersionContrat,
)
from authentication.models import Company

User = get_user_model()
_seq = itertools.count(1)


class TestAdminPreuvesVerrouillees(TestCase):
    def setUp(self):
        n = next(_seq)
        self.company = Company.objects.create(
            slug=f'aud510-{n}', nom=f'AUD510 Co {n}')
        # Le profil exact du constat : is_staff + permissions modèle par
        # défaut. C'est LUI qui pouvait supprimer une preuve.
        self.staff = User.objects.create_user(
            username=f'aud510-staff-{n}', password='x',
            company=self.company, is_staff=True, is_superuser=True)
        self.factory = RequestFactory()
        self.contrat = Contrat.objects.create(
            company=self.company, reference=f'CTR-AUD510-{n}',
            objet='Maintenance', montant=Decimal('12000'))

    def _requete(self):
        requete = self.factory.get('/django-admin/')
        requete.user = self.staff
        return requete

    def _admin(self, modele):
        return site._registry[modele]

    def test_signature_ni_supprimable_ni_modifiable(self):
        """ROUGE avant le correctif : les deux permissions étaient VRAIES."""
        signature = SignatureContrat.objects.create(
            company=self.company, contrat=self.contrat,
            signataire_nom='M. Alaoui',
            role_signataire=SignatureContrat.RoleSignataire.CLIENT)
        admin_sig = self._admin(SignatureContrat)
        requete = self._requete()
        self.assertFalse(admin_sig.has_delete_permission(requete, signature))
        self.assertFalse(admin_sig.has_change_permission(requete, signature))
        self.assertFalse(admin_sig.has_add_permission(requete))
        self.assertNotIn('delete_selected', admin_sig.get_actions(requete))

    def test_version_ni_supprimable_ni_modifiable(self):
        version = VersionContrat.objects.create(
            company=self.company, contrat=self.contrat, version=1,
            motif='Signature', contenu='Texte figé du contrat.')
        admin_ver = self._admin(VersionContrat)
        requete = self._requete()
        self.assertFalse(admin_ver.has_delete_permission(requete, version))
        self.assertFalse(admin_ver.has_change_permission(requete, version))
        self.assertFalse(admin_ver.has_add_permission(requete))
        self.assertNotIn('delete_selected', admin_ver.get_actions(requete))

    def test_le_verrou_vaut_meme_pour_un_superutilisateur(self):
        """Une preuve n'a pas de « sauf pour l'admin » : même patron que
        ``ClientAdmin`` (quatre verrous redondants)."""
        self.assertTrue(self.staff.is_superuser)
        requete = self._requete()
        for modele in (SignatureContrat, VersionContrat):
            with self.subTest(modele=modele.__name__):
                admin_obj = self._admin(modele)
                self.assertFalse(admin_obj.has_delete_permission(requete))
                self.assertFalse(admin_obj.has_change_permission(requete))
