"""AUD509 — un contrat ENGAGÉ ne se supprime plus d'un DELETE d'API.

``ContratViewSet`` n'avait AUCUNE garde de statut : il était gouverné par la
seule permission de rôle ``contrat_gerer``. Un contrat SIGNÉ, ACTIF ou RÉSILIÉ
— donc porteur de preuves de signature (loi 53-05), de garanties financières,
d'un échéancier, d'avenants et d'une résiliation — partait sur un simple
DELETE.

DEUX BARRIÈRES, ET LA PREMIÈRE A DÉJÀ BOUGÉ. AUD818 a rendu ce DELETE DOUX (le
contrat est masqué, plus effacé) : le dégât en base est donc déjà borné pour le
chemin API — c'est une correction de constat à assumer, la cascade décrite par
l'audit ne s'exécute plus par cette porte. Restaient DEUX trous réels, que
cette tâche ferme :

  1. le geste lui-même — une pièce à valeur légale ne doit pas DISPARAÎTRE de
     l'API sur un clic, même « doucement » ;
  2. les FK encore en ``CASCADE`` — une suppression DURE (admin Django, shell,
     script de reprise) effaçait toujours les preuves en silence.
"""
import itertools
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import models as dj_models
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.contrats.models import (
    Caution, Contrat, PartieContrat, RetenueGarantie, SignatureContrat,
)
from authentication.models import Company

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/contrats/contrats'


class TestSuppressionGardee(TestCase):
    def setUp(self):
        n = next(_seq)
        self.company = Company.objects.create(
            slug=f'aud509-{n}', nom=f'AUD509 Co {n}')
        self.user = User.objects.create_user(
            username=f'aud509-{n}', password='x', role_legacy='admin',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def _contrat(self, statut):
        contrat = Contrat.objects.create(
            company=self.company, created_by=self.user,
            reference=f'CTR-AUD509-{next(_seq)}', objet='Maintenance',
            statut=statut, montant=Decimal('12000'))
        PartieContrat.objects.create(
            company=self.company, contrat=contrat, nom='Client', ordre=0)
        return contrat

    # ── Barrière 1 : la garde de statut ───────────────────────────────────

    def test_delete_refuse_en_409_sur_un_contrat_signe(self):
        """ROUGE avant le correctif : 204, le contrat disparaissait de l'API."""
        contrat = self._contrat(Contrat.Statut.SIGNE)
        SignatureContrat.objects.create(
            company=self.company, contrat=contrat, signataire_nom='M. Alaoui',
            role_signataire=SignatureContrat.RoleSignataire.CLIENT)
        resp = self.api.delete(f'{BASE}/{contrat.id}/')
        self.assertEqual(resp.status_code, 409, resp.data)
        self.assertTrue(Contrat.objects.filter(pk=contrat.pk).exists())
        self.assertTrue(
            SignatureContrat.objects.filter(contrat=contrat).exists())

    def test_delete_refuse_sur_actif_et_resilie(self):
        for statut in (Contrat.Statut.ACTIF, Contrat.Statut.RESILIE):
            with self.subTest(statut=statut):
                contrat = self._contrat(statut)
                resp = self.api.delete(f'{BASE}/{contrat.id}/')
                self.assertEqual(resp.status_code, 409, resp.data)
                self.assertTrue(
                    Contrat.objects.filter(pk=contrat.pk).exists())

    def test_un_brouillon_reste_supprimable(self):
        for statut in (Contrat.Statut.BROUILLON,
                       Contrat.Statut.EN_APPROBATION):
            with self.subTest(statut=statut):
                contrat = self._contrat(statut)
                resp = self.api.delete(f'{BASE}/{contrat.id}/')
                self.assertEqual(resp.status_code, 204, resp.data)
                self.assertFalse(
                    Contrat.objects.filter(pk=contrat.pk).exists())

    # ── Barrière 2 : PROTECT au niveau de la base ─────────────────────────

    def test_les_trois_fk_de_preuve_sont_en_protect(self):
        """Défense en profondeur : les chemins HORS API (admin, shell) ne
        peuvent plus effacer une preuve en silence."""
        for modele in (SignatureContrat, RetenueGarantie, Caution):
            with self.subTest(modele=modele.__name__):
                champ = modele._meta.get_field('contrat')
                self.assertIs(champ.remote_field.on_delete,
                              dj_models.PROTECT)

    def test_une_suppression_dure_leve_une_erreur_propre(self):
        contrat = self._contrat(Contrat.Statut.SIGNE)
        SignatureContrat.objects.create(
            company=self.company, contrat=contrat, signataire_nom='M. Alaoui',
            role_signataire=SignatureContrat.RoleSignataire.CLIENT)
        with self.assertRaises(dj_models.ProtectedError):
            contrat.delete()
        self.assertTrue(Contrat.objects.filter(pk=contrat.pk).exists())
