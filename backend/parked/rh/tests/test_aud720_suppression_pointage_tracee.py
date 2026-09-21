"""AUD720 — la suppression d'un `Pointage` ne contourne plus l'audit XRH11.

DÉFAUT (rouge avant ce correctif) : `PointageViewSet.update()` exigeait un motif
et écrivait une `CorrectionPointage` IMMUABLE par champ corrigé (contrôle XRH11
documenté), mais AUCUN `destroy()`/`perform_destroy()` n'était surchargé — le
DELETE générique restait actif, gardé par le seul rôle `rh_gerer`, sans motif.
Aggravant : `CorrectionPointage.pointage` est en CASCADE, donc supprimer le
pointage effaçait aussi les corrections DÉJÀ tracées ; `Pointage` était absent de
`TRACKED_MODELS` et n'a pas de soft-delete. Après un DELETE il ne restait
littéralement AUCUNE trace d'une heure travaillée effacée.

Après correctif : motif obligatoire (400 sinon), trace `DossierActivity` portée
par le DOSSIER (donc HORS de la cascade du pointage) et `('rh', 'Pointage')`
dans `TRACKED_MODELS`.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.rh.models import (
    CorrectionPointage,
    DossierActivity,
    DossierEmploye,
    Pointage,
)

User = get_user_model()

POINTAGES = '/api/django/rh/pointages/'


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class SuppressionPointageTraceeTests(TestCase):
    def setUp(self):
        self.co = make_company('aud720', 'A')
        self.rh = make_user(self.co, 'aud720-rh')
        self.emp = DossierEmploye.objects.create(
            company=self.co, matricule='P1', nom='Tazi', prenom='Reda')
        self.pointage = Pointage.objects.create(
            company=self.co, employe=self.emp,
            heure_arrivee=timezone.now())
        # Une correction XRH11 DÉJÀ tracée : c'est elle que la cascade
        # effaçait silencieusement.
        CorrectionPointage.objects.create(
            company=self.co, pointage=self.pointage, champ='heure_arrivee',
            ancienne_valeur='08:00', nouvelle_valeur='08:30',
            motif='Oubli de badge', auteur=self.rh)

    def test_delete_sans_motif_refuse(self):
        resp = auth(self.rh).delete(f'{POINTAGES}{self.pointage.pk}/')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('motif', resp.data)
        self.assertTrue(Pointage.objects.filter(pk=self.pointage.pk).exists())
        self.assertEqual(CorrectionPointage.objects.count(), 1)

    def test_delete_avec_motif_laisse_une_trace_non_cascadee(self):
        resp = auth(self.rh).delete(
            f'{POINTAGES}{self.pointage.pk}/?motif=doublon+pointeuse')
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(Pointage.objects.filter(pk=self.pointage.pk).exists())
        # La correction part bien en cascade (comportement du schéma)…
        self.assertEqual(CorrectionPointage.objects.count(), 0)
        # … mais la trace, elle, SURVIT : elle vit sur le dossier employé.
        trace = DossierActivity.objects.filter(
            employe=self.emp, message__contains='Pointage SUPPRIMÉ').first()
        self.assertIsNotNone(trace)
        self.assertEqual(trace.auteur, self.rh)              # WHO
        self.assertEqual(trace.company, self.co)
        self.assertIn(str(self.pointage.pk), trace.message)  # WHAT
        self.assertIn('doublon pointeuse', trace.message)    # WHY
        self.assertIn('1 correction(s)', trace.message)
        self.assertIsNotNone(trace.date_creation)            # WHEN

    def test_pointage_est_desormais_dans_tracked_models(self):
        from apps.audit.signals import TRACKED_MODELS
        self.assertIn(('rh', 'Pointage'), TRACKED_MODELS)

    def test_isolation_societe_inchangee(self):
        autre = make_company('aud720-b', 'B')
        etranger = make_user(autre, 'aud720-rh-b')
        resp = auth(etranger).delete(
            f'{POINTAGES}{self.pointage.pk}/?motif=x')
        self.assertEqual(resp.status_code, 404)
        self.assertTrue(Pointage.objects.filter(pk=self.pointage.pk).exists())
