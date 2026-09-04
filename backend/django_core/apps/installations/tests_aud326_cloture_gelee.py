"""AUD326 — « Clôturé » est un état gelé : le recul est gardé et journalisé.

Défaut d'origine : `verifier_transition_statut` n'applique de gates QUE si la
destination est strictement en AVANT de l'origine (`j <= i → return []`, « un
recul n'est jamais bloqué ») ; c'est le SEUL gate appliqué à un changement de
statut dans `perform_update`, et aucun champ ne figeait à l'entrée en CLOTURE.
Un chantier CLÔTURÉ (situation soldée, garantie démarrée) repassait donc
« En cours » par un simple `PATCH {"statut": "en_cours"}` de n'importe quel
Responsable, sans motif ni confirmation, même sur une société ayant pleinement
configuré CH2 — pendant que facturation, garantie et parc en aval le
considéraient toujours clos.

Run :
    python manage.py test apps.installations.tests_aud326_cloture_gelee -v2
"""
import itertools

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.installations.models import Installation

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations/chantiers'


def make_company():
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=f'aud326-co-{n}', defaults={'nom': f'AUD326 Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_responsable(company):
    """Responsable LEGACY (aucun rôle fin) : passe `IsResponsableOrAdmin`,
    ne porte PAS l'autorité Directeur, et voit tous les chantiers (aucun
    marqueur de portée)."""
    return User.objects.create_user(
        username=f'aud326-resp-{next(_seq)}', password='x', company=company,
        role_legacy='responsable')


def make_directeur(company):
    """Directeur : rôle système « Directeur » (porte `journal_activite_voir`,
    le signal le plus discriminant du palier — même règle que
    `views.stage_config.IsDirecteur`)."""
    from apps.roles.models import Role, DIRECTEUR_PERMISSIONS
    role = Role.objects.create(
        company=company, nom='Directeur', est_systeme=True,
        permissions=list(DIRECTEUR_PERMISSIONS))
    u = User.objects.create_user(
        username=f'aud326-dir-{next(_seq)}', password='x', company=company)
    u.role = role
    u.save(update_fields=['role'])
    return u


class ClotureGeleeTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.responsable = make_responsable(self.company)
        self.directeur = make_directeur(self.company)
        self.inst = Installation.objects.create(
            company=self.company, reference='AUD326-1',
            statut=Installation.Statut.RECEPTIONNE)
        # Le verrou se pose côté SERVEUR au passage en CLOTURE.
        r = auth(self.responsable).patch(
            f'{BASE}/{self.inst.id}/',
            {'statut': Installation.Statut.CLOTURE}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.inst.refresh_from_db()

    def test_le_verrou_est_pose_a_lentree_en_cloture(self):
        self.assertTrue(self.inst.cloture_verrouillee)

    def test_recul_par_un_responsable_sans_motif_refuse(self):
        """ROUGE avant AUD326 : le PATCH réussissait silencieusement."""
        r = auth(self.responsable).patch(
            f'{BASE}/{self.inst.id}/',
            {'statut': Installation.Statut.EN_COURS}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.inst.refresh_from_db()
        self.assertEqual(self.inst.statut, Installation.Statut.CLOTURE)
        self.assertTrue(self.inst.cloture_verrouillee)

    def test_recul_par_un_responsable_avec_motif_refuse_quand_meme(self):
        r = auth(self.responsable).patch(
            f'{BASE}/{self.inst.id}/',
            {'statut': Installation.Statut.EN_COURS,
             'motif_reouverture': 'Réserve du client'}, format='json')
        self.assertEqual(r.status_code, 403, r.data)
        self.inst.refresh_from_db()
        self.assertEqual(self.inst.statut, Installation.Statut.CLOTURE)

    def test_recul_par_un_directeur_sans_motif_refuse(self):
        r = auth(self.directeur).patch(
            f'{BASE}/{self.inst.id}/',
            {'statut': Installation.Statut.EN_COURS}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.inst.refresh_from_db()
        self.assertEqual(self.inst.statut, Installation.Statut.CLOTURE)

    def test_recul_directeur_motive_passe_et_est_journalise_distinctement(self):
        r = auth(self.directeur).patch(
            f'{BASE}/{self.inst.id}/',
            {'statut': Installation.Statut.EN_COURS,
             'motif_reouverture': 'Réserve du client sur le raccordement'},
            format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.inst.refresh_from_db()
        self.assertEqual(self.inst.statut, Installation.Statut.EN_COURS)
        self.assertFalse(self.inst.cloture_verrouillee)
        notes = [a.body or '' for a in self.inst.activites.all()]
        self.assertTrue(
            any('rouvert' in n and 'Réserve du client' in n for n in notes),
            notes)

    def test_le_verrou_nest_pas_desarmable_par_patch(self):
        r = auth(self.directeur).patch(
            f'{BASE}/{self.inst.id}/',
            {'cloture_verrouillee': False}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.inst.refresh_from_db()
        self.assertTrue(self.inst.cloture_verrouillee)

    def test_un_chantier_non_clos_recule_librement(self):
        """Comportement historique intact hors CLOTURE."""
        autre = Installation.objects.create(
            company=self.company, reference='AUD326-2',
            statut=Installation.Statut.INSTALLE)
        r = auth(self.responsable).patch(
            f'{BASE}/{autre.id}/',
            {'statut': Installation.Statut.EN_COURS}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
