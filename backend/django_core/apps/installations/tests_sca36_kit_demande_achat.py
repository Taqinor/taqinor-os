"""SCA36 — Pilote 3 du kit ``core.documents`` : ``DemandeAchat`` (dégradation
gracieuse SANS totaux).

Prouve les « Done = » de la tâche :
  * ``DemandeAchat`` est SUR le kit (``DocumentMetier`` : socle ARC1 + contrat
    statut/transitions) **sans champ monétaire ajouté** — AUCUN
    ``montant_ht``/``montant_tva``/``montant_ttc`` du ``TotauxDocumentMixin``
    n'existe sur le modèle (le pilote qui prouve que le kit est COMPOSABLE,
    pas une uniformité forcée) ; ``montant_estime`` reste la property INTERNE
    historique (Σ lignes, jamais un total de document) ;
  * ``DA-`` CONTINU : format ``DA-YYYYMM-NNNN`` bit-identique + reprise du
    compteur courant (plus-haut-utilisé+1, jamais remis à zéro) ;
  * APPROBATIONS INCHANGÉES : le flux soumettre → approuver/refuser →
    marquer_commandee reste sur son moteur propre (chemin ARC10 nommé — pas de
    bascule vers ``changer_statut()``) ; la suite historique
    ``tests_fg310_demande_achat.py`` reste INCHANGÉE (non-régression
    comportementale) et un smoke de cycle complet est rejoué ici ;
  * CHATTER vivant : ``chatter/historique``/``chatter/noter`` via le mixin
    ARC8, cible ``('installations', 'demandeachat')`` déclarée au manifeste
    (ARC30).

Run :
    python manage.py test apps.installations.tests_sca36_kit_demande_achat -v2
"""
import itertools
import re

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.installations.models import DemandeAchat
from apps.records.models import ALLOWED_TARGETS, Activity
from core.documents import (
    DocumentMetier, TotauxDocumentMixin, TransitionRefusee, changer_statut,
)

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations'

# Format historique bit-identique : DA-YYYYMM-NNNN (4-pad mensuel).
REF_RE = re.compile(r'^DA-\d{6}-\d{4}$')


def make_company():
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=f'sca36-co-{n}', defaults={'nom': f'SCA36 Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_user(company, role='responsable'):
    return User.objects.create_user(
        username=f'sca36-{next(_seq)}', password='x',
        role_legacy=role, company=company)


# ── Continuité des références DA- ─────────────────────────────────────────────

class TestReferenceContinuity(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)

    def _create(self):
        r = self.api.post(f'{BASE}/demandes-achat/', {
            'objet': 'Panneaux chantier X',
        })
        self.assertEqual(r.status_code, 201, r.data)
        return r.data['reference']

    def test_format_bit_identique(self):
        # Mois attendu capturé hors assertion (déterminisme YTEST15) — pas de
        # gel d'horloge, qui invaliderait le JWT minté en setUp.
        expected_period = timezone.now().strftime('%Y%m')
        ref = self._create()
        self.assertRegex(ref, REF_RE)
        self.assertEqual(ref.split('-')[1], expected_period)

    def test_reprise_du_compteur_courant(self):
        """SCA36 — une demande pré-existante numérotée 0007 sur le mois
        courant donne 0008 au prochain create (le compteur CONTINUE)."""
        period = timezone.now().strftime('%Y%m')
        DemandeAchat.objects.create(
            company=self.company, reference=f'DA-{period}-0007',
            objet='Pré-existante')
        self.assertEqual(self._create(), f'DA-{period}-0008')


# ── Socle kit SANS totaux (dégradation gracieuse) ─────────────────────────────

class TestKitAdoptionSansTotaux(TestCase):
    def test_herite_du_kit_mais_pas_des_totaux(self):
        """SCA36 — sur le kit (DocumentMetier) SANS TotauxDocumentMixin :
        composable, pas une uniformité forcée."""
        self.assertTrue(issubclass(DemandeAchat, DocumentMetier))
        self.assertFalse(issubclass(DemandeAchat, TotauxDocumentMixin))

    def test_aucun_champ_monetaire_ajoute(self):
        """SCA36 — « sans champ monétaire ajouté » : aucun champ du mixin
        totaux n'existe sur le modèle."""
        champs = {f.name for f in DemandeAchat._meta.get_fields()}
        for interdit in ('montant_ht', 'montant_tva', 'montant_ttc'):
            self.assertNotIn(interdit, champs)

    def test_montant_estime_reste_la_property_interne(self):
        """SCA36 — ``montant_estime`` (Σ lignes, INTERNE) est intact."""
        company = make_company()
        da = DemandeAchat.objects.create(
            company=company, reference='DA-K-1', objet='Estimation')
        da.lignes.create(designation='Panneau', quantite=10, prix_estime=100)
        da.lignes.create(designation='Câble', quantite=2, prix_estime=50)
        self.assertEqual(da.montant_estime, 1100)

    def test_statut_choices_et_default_preserves(self):
        field = DemandeAchat._meta.get_field('statut')
        self.assertEqual(
            {c[0] for c in field.choices},
            {'brouillon', 'soumise', 'approuvee', 'refusee', 'commandee'})
        self.assertEqual(field.default, 'brouillon')
        self.assertEqual(field.max_length, 32)

    def test_timestamps_kit_ajoutes_et_historiques_conserves(self):
        champs = {f.name for f in DemandeAchat._meta.get_fields()}
        self.assertIn('created_at', champs)
        self.assertIn('updated_at', champs)
        self.assertIn('date_creation', champs)
        self.assertIn('date_modification', champs)

    def test_transitions_declaratives_et_garde(self):
        company = make_company()
        da = DemandeAchat.objects.create(
            company=company, reference='DA-K-2', objet='Transitions')
        self.assertEqual(da.statut, 'brouillon')
        self.assertEqual(da.transitions_permises(), {'soumise'})
        with self.assertRaises(TransitionRefusee):
            changer_statut(da, 'commandee')
        da.refresh_from_db()
        self.assertEqual(da.statut, 'brouillon')


# ── Approbations inchangées (moteur propre, chemin ARC10 nommé) ───────────────

class TestApprobationInchangee(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)

    def test_cycle_complet_via_les_actions_historiques(self):
        """SCA36 — brouillon → soumise → approuvée → commandée via les MÊMES
        actions de vue qu'avant (aucune bascule de moteur) ; l'approbateur et
        la date de décision restent tracés."""
        r = self.api.post(f'{BASE}/demandes-achat/', {'objet': 'Cycle'})
        self.assertEqual(r.status_code, 201, r.data)
        da_id = r.data['id']
        self.assertEqual(self.api.post(
            f'{BASE}/demandes-achat/{da_id}/soumettre/').status_code, 200)
        r = self.api.post(f'{BASE}/demandes-achat/{da_id}/approuver/')
        self.assertEqual(r.status_code, 200, r.data)
        da = DemandeAchat.objects.get(id=da_id)
        self.assertEqual(da.statut, 'approuvee')
        self.assertEqual(da.approuvee_par_id, self.user.id)
        self.assertIsNotNone(da.date_decision)
        r = self.api.post(
            f'{BASE}/demandes-achat/{da_id}/marquer_commandee/')
        self.assertEqual(r.status_code, 200, r.data)
        da.refresh_from_db()
        self.assertEqual(da.statut, 'commandee')

    def test_refus_avec_motif_inchange(self):
        r = self.api.post(f'{BASE}/demandes-achat/', {'objet': 'Refus'})
        da_id = r.data['id']
        self.api.post(f'{BASE}/demandes-achat/{da_id}/soumettre/')
        r = self.api.post(f'{BASE}/demandes-achat/{da_id}/refuser/',
                          {'motif_refus': 'Budget dépassé'})
        self.assertEqual(r.status_code, 200, r.data)
        da = DemandeAchat.objects.get(id=da_id)
        self.assertEqual(da.statut, 'refusee')
        self.assertEqual(da.motif_refus, 'Budget dépassé')


# ── Chatter (ARC8 via le manifeste ARC30) ─────────────────────────────────────

class TestChatter(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.da = DemandeAchat.objects.create(
            company=self.company, reference='DA-C-1', objet='Chatter')

    def test_cible_declaree_dans_allowed_targets(self):
        self.assertIn(('installations', 'demandeachat'), ALLOWED_TARGETS)

    def test_noter_puis_historique(self):
        r = self.api.post(
            f'{BASE}/demandes-achat/{self.da.id}/chatter/noter/',
            {'body': 'Relance approbateur.'})
        self.assertEqual(r.status_code, 201, r.data)
        act = Activity.objects.get(pk=r.data['id'])
        self.assertEqual(act.company_id, self.company.id)
        self.assertEqual(act.created_by_id, self.user.id)
        r = self.api.get(
            f'{BASE}/demandes-achat/{self.da.id}/chatter/historique/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertIn('Relance approbateur.',
                      [row['body'] for row in r.data])

    def test_historique_lisible_tout_role_noter_gate(self):
        lecteur = make_user(self.company, role='normal')
        r = auth(lecteur).get(
            f'{BASE}/demandes-achat/{self.da.id}/chatter/historique/')
        self.assertEqual(r.status_code, 200, r.data)
        r = auth(lecteur).post(
            f'{BASE}/demandes-achat/{self.da.id}/chatter/noter/',
            {'body': 'Tentative.'})
        self.assertEqual(r.status_code, 403, r.data)

    def test_chatter_cross_company_404(self):
        autre = make_user(make_company())
        r = auth(autre).get(
            f'{BASE}/demandes-achat/{self.da.id}/chatter/historique/')
        self.assertEqual(r.status_code, 404)
