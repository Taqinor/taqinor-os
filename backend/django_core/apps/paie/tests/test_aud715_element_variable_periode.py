"""AUD715 — l'écriture MANUELLE d'un élément variable respecte le statut.

ÉTAT AVANT LE FIX. ``ElementVariableSerializer.validate_periode`` n'appelait
que ``_meme_societe`` (société uniquement) ; ``ElementVariableViewSet`` est un
``ModelViewSet`` COMPLET gardé seulement par ``paie_gerer`` (un rôle, jamais un
statut) ; et le modèle ``ElementVariable`` n'avait ni ``save()`` ni
``delete()`` surchargés. À comparer à ``importer_elements_rh``, qui lève
explicitement ``TransitionPeriodeInterdite`` si ``periode.statut !=
brouillon`` AVANT toute écriture.

Une écriture manuelle sur une période déjà CALCULÉE/VALIDÉE/CLÔTURÉE
réussissait donc silencieusement (201/200/204) sans jamais influencer le
bulletin déjà émis : le net réellement viré divergeait des éléments variables
du mois, sans trace ni erreur.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.paie.models import ElementVariable, PeriodePaie, ProfilPaie
from apps.rh.models import DossierEmploye

User = get_user_model()


class ElementVariablePeriodeFigeeTests(TestCase):
    def setUp(self):
        self.co = Company.objects.create(slug='aud715', nom='AUD715')
        self.user = User.objects.create_user(
            username='aud715', password='x', company=self.co,
            role_legacy='responsable')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        dossier = DossierEmploye.objects.create(
            company=self.co, matricule='EV1', nom='Elem', prenom='Test')
        self.profil = ProfilPaie.objects.create(
            company=self.co, employe=dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('8000'))
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)

    def _figer(self, statut=PeriodePaie.STATUT_CALCULEE):
        self.periode.statut = statut
        self.periode.save(update_fields=['statut'])

    def _payload(self, **extra):
        payload = {
            'periode': self.periode.id, 'profil': self.profil.id,
            'type': 'prime', 'libelle': 'Prime', 'montant': '1000.00',
        }
        payload.update(extra)
        return payload

    def _element(self):
        return ElementVariable.objects.create(
            company=self.co, periode=self.periode, profil=self.profil,
            type='prime', libelle='Prime', montant=Decimal('1000'),
            source=ElementVariable.SOURCE_MANUEL)

    # ── Non-régression : en brouillon, rien ne change ──────────────────────

    def test_brouillon_autorise_creation_modification_suppression(self):
        resp = self.api.post(
            '/api/django/paie/elements-variables/', self._payload(),
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        url = f"/api/django/paie/elements-variables/{resp.data['id']}/"
        self.assertEqual(
            self.api.patch(url, {'montant': '1200.00'},
                           format='json').status_code, 200)
        self.assertEqual(self.api.delete(url).status_code, 204)

    # ── Le constat : hors brouillon, plus rien ne passe ────────────────────

    def test_creation_refusee_hors_brouillon(self):
        self._figer()
        resp = self.api.post(
            '/api/django/paie/elements-variables/', self._payload(),
            format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('periode', resp.data)
        self.assertEqual(
            ElementVariable.objects.filter(periode=self.periode).count(), 0)

    def test_modification_refusee_hors_brouillon(self):
        element = self._element()
        self._figer(PeriodePaie.STATUT_VALIDEE)
        resp = self.api.patch(
            f'/api/django/paie/elements-variables/{element.id}/',
            {'montant': '9999.00'}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        element.refresh_from_db()
        self.assertEqual(element.montant, Decimal('1000.00'))

    def test_suppression_refusee_hors_brouillon(self):
        element = self._element()
        self._figer(PeriodePaie.STATUT_CLOTUREE)
        resp = self.api.delete(
            f'/api/django/paie/elements-variables/{element.id}/')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertTrue(
            ElementVariable.objects.filter(id=element.id).exists())

    # ── La garde vit sur le MODÈLE : admin et scripts inclus ───────────────

    def test_garde_modele_hors_api(self):
        self._figer()
        with self.assertRaises(ElementVariable.PeriodeVerrouillee):
            ElementVariable.objects.create(
                company=self.co, periode=self.periode, profil=self.profil,
                type='prime', libelle='Hors API', montant=Decimal('500'))

    def test_garde_modele_suppression_hors_api(self):
        element = self._element()
        self._figer()
        with self.assertRaises(ElementVariable.PeriodeVerrouillee):
            element.delete()

    def test_element_ne_peut_pas_etre_deplace_hors_periode_figee(self):
        element = self._element()
        self._figer()
        cible = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=7)
        element.periode = cible
        with self.assertRaises(ElementVariable.PeriodeVerrouillee):
            element.save()
