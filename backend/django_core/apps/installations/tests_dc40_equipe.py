"""
DC40 — Modèle d'ÉQUIPE terrain CANONIQUE.

Couvre :
  * ``Equipe`` CRUD via l'API + scope société (une société ne voit/écrit jamais
    l'équipe d'une autre) ;
  * l'appartenance (M2M ``membres``) + garde tenant (membre/chef d'une autre
    société refusés) ;
  * la résolution CANONIQUE des membres d'une intervention via ``equipe_ref``
    (``selectors.membres_intervention``), avec repli sur le M2M ad-hoc ;
  * que le plan de charge (FG299) résout ses techniciens via l'équipe canonique
    quand ``equipe_ref`` est posée ;
  * que le planning camionnette (FG303) partage la MÊME intervention (donc la
    même équipe canonique) ;
  * l'unicité (société, nom).

Run :
    python manage.py test apps.installations.tests_dc40_equipe -v2
"""
import datetime
import itertools

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.installations.models import Equipe, Installation, Intervention
from apps.installations.selectors import (
    membres_intervention, plan_de_charge_equipes, planning_camionnettes,
)
from apps.stock.models import EmplacementStock

User = get_user_model()
_seq = itertools.count(1)

BASE = '/api/django/installations'


# ── Helpers ──────────────────────────────────────────────────────────────────

def make_company(slug=None, nom=None):
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'dc40-co-{n}', defaults={'nom': nom or f'DC40 Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_user(company, role='responsable', username=None):
    return User.objects.create_user(
        username=username or f'dc40-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def make_client(company):
    n = next(_seq)
    return Client.objects.create(
        company=company, nom='Client', prenom='Test',
        email=f'dc40-{company.id}-{n}@example.invalid')


def make_installation(company, reference=None):
    n = next(_seq)
    return Installation.objects.create(
        company=company, reference=reference or f'CH-{company.id}-{n}',
        client=make_client(company))


def make_intervention(company, installation, date_prevue=None,
                      technicien=None, equipe=None, equipe_ref=None,
                      camionnette=None):
    interv = Intervention.objects.create(
        company=company, installation=installation,
        type_intervention=Intervention.Type.POSE,
        date_prevue=date_prevue, technicien=technicien,
        equipe_ref=equipe_ref, camionnette=camionnette)
    if equipe:
        interv.equipe.set(equipe)
    return interv


LUNDI = datetime.date(2026, 6, 1)
MARDI = datetime.date(2026, 6, 2)
SEMAINE_FIN = datetime.date(2026, 6, 7)


# ── CRUD + scope société ─────────────────────────────────────────────────────

class TestEquipeCrud(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company, role='admin')
        self.api = auth(self.user)

    def test_create_forces_company_and_created_by(self):
        """DC40 — la société et `created_by` sont posés côté serveur (jamais
        lus du corps), même si le client tente de les injecter."""
        autre = make_company()
        m1 = make_user(self.company)
        r = self.api.post(f'{BASE}/equipes/', {
            'nom': 'Équipe Nord', 'membres': [m1.id],
            'company': autre.id, 'created_by': 999,
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        eq = Equipe.objects.get(id=r.data['id'])
        self.assertEqual(eq.company_id, self.company.id)  # pas `autre`
        self.assertEqual(eq.created_by_id, self.user.id)
        self.assertEqual(list(eq.membres.values_list('id', flat=True)), [m1.id])

    def test_list_scoped_to_company(self):
        """DC40 — une société ne voit jamais l'équipe d'une autre."""
        Equipe.objects.create(company=self.company, nom='À moi')
        autre = make_company()
        Equipe.objects.create(company=autre, nom='Pas à moi')
        r = self.api.get(f'{BASE}/equipes/')
        self.assertEqual(r.status_code, 200, r.data)
        noms = {e['nom'] for e in r.data['results']} \
            if isinstance(r.data, dict) and 'results' in r.data \
            else {e['nom'] for e in r.data}
        self.assertIn('À moi', noms)
        self.assertNotIn('Pas à moi', noms)

    def test_cannot_retrieve_other_company_equipe(self):
        """DC40 — récupérer l'équipe d'une autre société → 404 (scope)."""
        autre = make_company()
        eq = Equipe.objects.create(company=autre, nom='Autre')
        r = self.api.get(f'{BASE}/equipes/{eq.id}/')
        self.assertEqual(r.status_code, 404)

    def test_update_and_deactivate(self):
        """DC40 — mise à jour du nom + désactivation (archivage sans
        suppression)."""
        eq = Equipe.objects.create(company=self.company, nom='V1')
        r = self.api.patch(f'{BASE}/equipes/{eq.id}/',
                           {'nom': 'V2', 'actif': False}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        eq.refresh_from_db()
        self.assertEqual(eq.nom, 'V2')
        self.assertFalse(eq.actif)

    def test_filter_actif(self):
        """DC40 — filtre `?actif=`."""
        Equipe.objects.create(company=self.company, nom='ON', actif=True)
        Equipe.objects.create(company=self.company, nom='OFF', actif=False)
        r = self.api.get(f'{BASE}/equipes/', {'actif': 'false'})
        rows = r.data['results'] if isinstance(r.data, dict) \
            and 'results' in r.data else r.data
        noms = {e['nom'] for e in rows}
        self.assertIn('OFF', noms)
        self.assertNotIn('ON', noms)


# ── Garde tenant sur membres / chef ──────────────────────────────────────────

class TestEquipeTenantGuard(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company, role='admin')
        self.api = auth(self.user)

    def test_member_of_other_company_rejected(self):
        """DC40 — un membre d'une autre société est refusé (400)."""
        autre = make_company()
        intrus = make_user(autre)
        r = self.api.post(f'{BASE}/equipes/', {
            'nom': 'Frauduleuse', 'membres': [intrus.id],
        }, format='json')
        self.assertEqual(r.status_code, 400, r.data)

    def test_chef_of_other_company_rejected(self):
        """DC40 — un chef d'une autre société est refusé (400)."""
        autre = make_company()
        intrus = make_user(autre)
        r = self.api.post(f'{BASE}/equipes/', {
            'nom': 'Frauduleuse2', 'chef': intrus.id,
        }, format='json')
        self.assertEqual(r.status_code, 400, r.data)


# ── Unicité (société, nom) ───────────────────────────────────────────────────

class TestEquipeUnique(TestCase):
    def test_nom_unique_per_company(self):
        company = make_company()
        Equipe.objects.create(company=company, nom='Dup')
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Equipe.objects.create(company=company, nom='Dup')

    def test_same_nom_ok_across_companies(self):
        a = make_company()
        b = make_company()
        Equipe.objects.create(company=a, nom='Partagé')
        # Pas d'exception : même nom, sociétés différentes.
        Equipe.objects.create(company=b, nom='Partagé')


# ── Résolution CANONIQUE des membres d'une intervention ──────────────────────

class TestMembresIntervention(TestCase):
    def setUp(self):
        self.company = make_company()
        self.inst = make_installation(self.company)
        self.u1 = make_user(self.company)
        self.u2 = make_user(self.company)
        self.tech = make_user(self.company)

    def test_resolves_via_equipe_ref_when_set(self):
        """DC40 — quand `equipe_ref` est posée, les membres viennent de
        l'équipe CANONIQUE (`Equipe.membres`), + le technicien principal."""
        eq = Equipe.objects.create(company=self.company, nom='Canonique')
        eq.membres.set([self.u1, self.u2])
        interv = make_intervention(
            self.company, self.inst, LUNDI,
            technicien=self.tech, equipe_ref=eq)
        membres = membres_intervention(interv)
        self.assertEqual(membres, {self.u1.id, self.u2.id, self.tech.id})

    def test_falls_back_to_adhoc_m2m(self):
        """DC40 — sans `equipe_ref`, on retombe sur le M2M ad-hoc
        historique."""
        interv = make_intervention(
            self.company, self.inst, LUNDI, equipe=[self.u1])
        self.assertEqual(membres_intervention(interv), {self.u1.id})

    def test_equipe_ref_takes_precedence_over_adhoc(self):
        """DC40 — l'équipe CANONIQUE prime sur le M2M ad-hoc : quand
        `equipe_ref` est posée, seuls ses membres (+ technicien) comptent."""
        eq = Equipe.objects.create(company=self.company, nom='Prioritaire')
        eq.membres.set([self.u1])
        interv = make_intervention(
            self.company, self.inst, LUNDI,
            equipe=[self.u2], equipe_ref=eq)
        # u2 (ad-hoc) est ignoré ; u1 (canonique) retenu.
        self.assertEqual(membres_intervention(interv), {self.u1.id})

    def test_no_team_no_tech_is_empty(self):
        interv = make_intervention(self.company, self.inst, LUNDI)
        self.assertEqual(membres_intervention(interv), set())


# ── FG299 plan de charge résout via l'équipe canonique ───────────────────────

class TestPlanChargeCanonique(TestCase):
    def setUp(self):
        self.company = make_company()
        self.inst = make_installation(self.company)

    def test_plan_charge_counts_canonical_members(self):
        """DC40 — un membre de l'équipe CANONIQUE (`equipe_ref`) est compté dans
        le plan de charge exactement comme un membre du M2M ad-hoc l'était."""
        m1 = make_user(self.company)
        m2 = make_user(self.company)
        eq = Equipe.objects.create(company=self.company, nom='Pose A')
        eq.membres.set([m1, m2])
        make_intervention(self.company, self.inst, LUNDI, equipe_ref=eq)
        res = plan_de_charge_equipes(self.company, LUNDI, SEMAINE_FIN)
        rows = {r['technicien_id']: r for r in res['techniciens']}
        self.assertIn(m1.id, rows)
        self.assertIn(m2.id, rows)
        self.assertEqual(rows[m1.id]['affecte_count'], 1)
        self.assertEqual(rows[m2.id]['affecte_count'], 1)

    def test_no_double_count_canonical_member_and_tech(self):
        """DC40 — un utilisateur à la fois technicien principal ET membre de
        l'équipe canonique n'est compté qu'UNE fois."""
        u = make_user(self.company)
        eq = Equipe.objects.create(company=self.company, nom='Solo')
        eq.membres.set([u])
        make_intervention(self.company, self.inst, LUNDI,
                          technicien=u, equipe_ref=eq)
        res = plan_de_charge_equipes(self.company, LUNDI, SEMAINE_FIN)
        rows = {r['technicien_id']: r for r in res['techniciens']}
        self.assertEqual(rows[u.id]['affecte_count'], 1)

    def test_adhoc_still_works_alongside_canonical(self):
        """DC40 — rétro-compat : une intervention ad-hoc (sans `equipe_ref`) et
        une intervention canonique coexistent dans le même plan de charge."""
        adhoc = make_user(self.company)
        canon = make_user(self.company)
        eq = Equipe.objects.create(company=self.company, nom='Canon')
        eq.membres.set([canon])
        make_intervention(self.company, self.inst, LUNDI, equipe=[adhoc])
        make_intervention(self.company, self.inst, MARDI, equipe_ref=eq)
        res = plan_de_charge_equipes(self.company, LUNDI, SEMAINE_FIN)
        ids = {r['technicien_id'] for r in res['techniciens']}
        self.assertIn(adhoc.id, ids)
        self.assertIn(canon.id, ids)


# ── FG303 planning camionnette partage la même équipe canonique ──────────────

class TestPlanningCamionnetteCanonique(TestCase):
    def test_camionnette_shares_canonical_intervention(self):
        """DC40 — le planning camionnette groupe la MÊME intervention que celle
        portant l'équipe canonique : les deux features partagent une seule
        définition d'équipe (via `Intervention.equipe_ref`)."""
        company = make_company()
        inst = make_installation(company, reference='CH-CAM')
        camion = EmplacementStock.objects.create(company=company, nom='Camion 1')
        tech = make_user(company)
        eq = Equipe.objects.create(company=company, nom='Camion Team')
        eq.membres.set([tech])
        interv = make_intervention(
            company, inst, LUNDI, technicien=tech,
            equipe_ref=eq, camionnette=camion)
        # Le planning camionnette voit l'intervention…
        planning = planning_camionnettes(company, LUNDI, SEMAINE_FIN)
        self.assertEqual(planning['totaux']['nb_camionnettes'], 1)
        ids = [i['id']
               for i in planning['camionnettes'][0]['interventions']]
        self.assertIn(interv.id, ids)
        # …et le plan de charge résout ses membres via la MÊME équipe canonique.
        charge = plan_de_charge_equipes(company, LUNDI, SEMAINE_FIN)
        charge_ids = {r['technicien_id'] for r in charge['techniciens']}
        self.assertIn(tech.id, charge_ids)


# ── Migration de données : correction du rétro-remplissage ───────────────────

class TestDc40BackfillLogic(TestCase):
    """Vérifie la LOGIQUE du rétro-remplissage (dédup par ensemble de membres)
    telle qu'implémentée dans la migration 0048, en la rejouant sur des données
    en base — un test d'intégrité de données (la migration réelle est jouée par
    la suite Django au montage du schéma de test)."""

    def setUp(self):
        self.company = make_company()
        self.inst = make_installation(self.company)
        self.a = make_user(self.company)
        self.b = make_user(self.company)

    def _backfill(self):
        """Réplique la logique de dédup de la migration 0048 en Python pur."""
        cache = {}
        for interv in Intervention.objects.filter(company=self.company):
            ids = sorted(interv.equipe.values_list('id', flat=True))
            if not ids:
                continue
            key = (interv.company_id, frozenset(ids))
            eq = cache.get(key)
            if eq is None:
                eq = Equipe.objects.create(
                    company_id=interv.company_id,
                    nom=f"Équipe {'-'.join(map(str, ids))}"[:120],
                    description='[DC40-backfill]')
                eq.membres.set(ids)
                cache[key] = eq
            interv.equipe_ref = eq
            interv.save(update_fields=['equipe_ref'])
        return cache

    def test_same_member_set_dedups_to_one_equipe(self):
        """DC40 — deux interventions avec le MÊME ensemble de membres partagent
        UNE seule équipe canonique (dédup)."""
        make_intervention(self.company, self.inst, LUNDI, equipe=[self.a, self.b])
        make_intervention(self.company, self.inst, MARDI, equipe=[self.a, self.b])
        self._backfill()
        equipes = Equipe.objects.filter(company=self.company)
        self.assertEqual(equipes.count(), 1)
        eq = equipes.first()
        self.assertEqual(
            set(eq.membres.values_list('id', flat=True)), {self.a.id, self.b.id})
        # Les deux interventions pointent la même équipe canonique.
        refs = set(Intervention.objects
                   .filter(company=self.company)
                   .values_list('equipe_ref_id', flat=True))
        self.assertEqual(refs, {eq.id})

    def test_distinct_member_sets_get_distinct_equipes(self):
        """DC40 — des ensembles de membres DIFFÉRENTS donnent des équipes
        différentes."""
        make_intervention(self.company, self.inst, LUNDI, equipe=[self.a])
        make_intervention(self.company, self.inst, MARDI, equipe=[self.a, self.b])
        self._backfill()
        self.assertEqual(Equipe.objects.filter(company=self.company).count(), 2)

    def test_empty_team_not_backfilled(self):
        """DC40 — une intervention sans équipe ad-hoc ne crée aucune équipe."""
        make_intervention(self.company, self.inst, LUNDI)
        self._backfill()
        self.assertEqual(Equipe.objects.filter(company=self.company).count(), 0)
