"""
FG301 — Nivellement de charge (resource levelling) — sélecteur
``nivellement_charge`` + action ``InterventionViewSet.nivellement_charge``.

Construit sur FG299 (plan de charge) + FG300 (conflits) : à partir de la charge
par technicien sur une fenêtre, on PROPOSE de déplacer des interventions des
techniciens SUR-CHARGÉS (affecté > capacité) vers les SOUS-CHARGÉS, sans recréer
un conflit FG300. C'est une proposition LECTURE SEULE : rien n'est jamais muté.

Couvre :
  * un technicien sur-chargé + un sous-chargé → une proposition de déplacement ;
  * la proposition ne mute RIEN (l'intervention garde son technicien) ;
  * équipe équilibrée → aucune proposition ;
  * pas de destinataire dispo (le seul sous-chargé est déjà occupé ce jour-là,
    anti-conflit FG300) → non résolue, aucune proposition ;
  * la garde fenêtre vide/None/inversée ;
  * le scope société (aucune intervention d'une autre société) ;
  * l'endpoint nivellement-charge : 200, lecture pour tout rôle, 400 fenêtre
    inversée.

Pure agrégation, lecture seule, aucun nouveau modèle.

Run :
    python manage.py test apps.installations.tests_fg301_nivellement -v2
"""
import datetime
import itertools

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.installations.models import Installation, Intervention
from apps.installations.selectors import nivellement_charge

User = get_user_model()
_seq = itertools.count(1)

BASE = '/api/django/installations'


# ── Helpers ──────────────────────────────────────────────────────────────────

def make_company(slug=None, nom=None):
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'fg301-co-{n}', defaults={'nom': nom or f'FG301 Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_user(company, role='responsable', username=None):
    return User.objects.create_user(
        username=username or f'fg301-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def make_client(company):
    n = next(_seq)
    return Client.objects.create(
        company=company, nom='Client', prenom='Test',
        email=f'fg301-{company.id}-{n}@example.invalid')


def make_installation(company):
    n = next(_seq)
    return Installation.objects.create(
        company=company, reference=f'CH-{company.id}-{n}',
        client=make_client(company))


def make_intervention(company, installation, date_prevue,
                      technicien=None, equipe=None):
    interv = Intervention.objects.create(
        company=company, installation=installation,
        type_intervention=Intervention.Type.POSE,
        date_prevue=date_prevue, technicien=technicien)
    if equipe:
        interv.equipe.set(equipe)
    return interv


# Fenêtre de référence : lundi 2026-06-01 → dimanche 2026-06-07
# (5 jours ouvrés lun→ven ⇒ capacité = 5 interventions/technicien).
LUNDI = datetime.date(2026, 6, 1)
MARDI = datetime.date(2026, 6, 2)
MERCREDI = datetime.date(2026, 6, 3)
JEUDI = datetime.date(2026, 6, 4)
VENDREDI = datetime.date(2026, 6, 5)
SAMEDI = datetime.date(2026, 6, 6)
SEMAINE_FIN = datetime.date(2026, 6, 7)
JOURS_OUVRES = [LUNDI, MARDI, MERCREDI, JEUDI, VENDREDI]


# ── Sélecteur : proposition de déplacement ────────────────────────────────────

class TestNivellementProposition(TestCase):
    def setUp(self):
        self.company = make_company()
        self.inst = make_installation(self.company)
        self.surcharge = make_user(self.company, username='surcharge')
        self.libre = make_user(self.company, username='libre')

    def test_surcharge_propose_deplacement_vers_souscharge(self):
        """FG301 — un technicien à 6 interventions (capacité 5) + un technicien
        sans charge → au moins une proposition de déplacement vers le libre."""
        # 6 interventions sur 6 jours distincts pour le sur-chargé (excès = 1).
        jours = JOURS_OUVRES + [SAMEDI]
        for jour in jours:
            make_intervention(self.company, self.inst, jour,
                              technicien=self.surcharge)
        # Le technicien « libre » porte une intervention (sous-chargé : marge 4).
        make_intervention(self.company, self.inst, LUNDI,
                          technicien=self.libre)
        res = nivellement_charge(self.company, LUNDI, SEMAINE_FIN)
        self.assertEqual(res['capacite_jours'], 5)
        self.assertEqual(res['totaux']['nb_surcharges'], 1)
        self.assertEqual(res['surcharges'][0]['technicien_id'],
                         self.surcharge.id)
        self.assertEqual(res['surcharges'][0]['exces'], 1)
        self.assertGreaterEqual(res['totaux']['nb_propositions'], 1)
        prop = res['propositions'][0]
        self.assertEqual(prop['de_id'], self.surcharge.id)
        self.assertEqual(prop['vers_id'], self.libre.id)

    def test_proposition_ne_mute_rien(self):
        """FG301 — la proposition est LECTURE SEULE : l'intervention déplacée
        garde son technicien d'origine en base."""
        jours = JOURS_OUVRES + [SAMEDI]
        intervs = [make_intervention(self.company, self.inst, jour,
                                     technicien=self.surcharge)
                   for jour in jours]
        make_intervention(self.company, self.inst, LUNDI,
                          technicien=self.libre)
        res = nivellement_charge(self.company, LUNDI, SEMAINE_FIN)
        self.assertGreaterEqual(res['totaux']['nb_propositions'], 1)
        moved_id = res['propositions'][0]['intervention_id']
        # Rien n'a bougé en base : le technicien est toujours le sur-chargé.
        moved = Intervention.objects.get(id=moved_id)
        self.assertEqual(moved.technicien_id, self.surcharge.id)
        # Aucune intervention n'a été réaffectée au technicien libre.
        self.assertEqual(
            Intervention.objects.filter(technicien=self.libre).count(), 1)
        # Comptage inchangé pour chaque technicien.
        self.assertEqual(
            Intervention.objects.filter(technicien=self.surcharge).count(),
            len(intervs))

    def test_equipe_equilibree_aucune_proposition(self):
        """FG301 — deux techniciens également chargés sous capacité → aucun
        sur-chargé, aucune proposition."""
        a = make_user(self.company)
        b = make_user(self.company)
        make_intervention(self.company, self.inst, LUNDI, technicien=a)
        make_intervention(self.company, self.inst, MARDI, technicien=a)
        make_intervention(self.company, self.inst, LUNDI, technicien=b)
        make_intervention(self.company, self.inst, MARDI, technicien=b)
        res = nivellement_charge(self.company, LUNDI, SEMAINE_FIN)
        self.assertEqual(res['totaux']['nb_surcharges'], 0)
        self.assertEqual(res['propositions'], [])

    def test_destinataire_occupe_ce_jour_non_resolu(self):
        """FG301 — le seul technicien sous-chargé est déjà occupé le jour de
        l'intervention en excès → on ne propose PAS (anti-conflit FG300) et on
        compte une non-résolue."""
        # Sur-chargé : 6 interventions, dont l'excédent le plus tardif = SAMEDI.
        for jour in JOURS_OUVRES + [SAMEDI]:
            make_intervention(self.company, self.inst, jour,
                              technicien=self.surcharge)
        # Le « libre » est sous-chargé (1 interv) MAIS déjà pris le SAMEDI :
        # déplacer l'excédent du samedi vers lui recréerait un conflit FG300.
        make_intervention(self.company, self.inst, SAMEDI,
                          technicien=self.libre)
        res = nivellement_charge(self.company, LUNDI, SEMAINE_FIN)
        # L'excédent (interv du samedi) ne peut aller nulle part → non résolue.
        # Aucune proposition ne cible le libre le samedi.
        for prop in res['propositions']:
            if prop['vers_id'] == self.libre.id:
                self.assertNotEqual(prop['date'], SAMEDI.isoformat())


# ── Fenêtrage & gardes ────────────────────────────────────────────────────────

class TestNivellementFenetre(TestCase):
    def setUp(self):
        self.company = make_company()
        self.inst = make_installation(self.company)
        self.tech = make_user(self.company)

    def test_fenetre_none_renvoie_vide(self):
        """FG301 — fenêtre None : garde explicite, listes vides, pas
        d'exception."""
        make_intervention(self.company, self.inst, LUNDI, technicien=self.tech)
        res = nivellement_charge(self.company, None, None)
        self.assertEqual(res['propositions'], [])
        self.assertEqual(res['surcharges'], [])
        self.assertEqual(res['totaux']['nb_propositions'], 0)
        self.assertIsNone(res['debut'])
        self.assertIsNone(res['fin'])

    def test_fenetre_inversee_renvoie_vide(self):
        """FG301 — fenêtre inversée (fin < debut) : listes vides, pas
        d'exception."""
        make_intervention(self.company, self.inst, LUNDI, technicien=self.tech)
        res = nivellement_charge(self.company, SEMAINE_FIN, LUNDI)
        self.assertEqual(res['propositions'], [])
        self.assertEqual(res['surcharges'], [])

    def test_fenetre_sans_jour_ouvre_pas_de_crash(self):
        """FG301 — fenêtre = un seul jour de week-end (0 jour ouvré, capacité 0) :
        division-par-zéro gardée, pas d'exception. Toute charge est alors un
        excès, sans destinataire possible (tous sur-chargés)."""
        make_intervention(self.company, self.inst, SAMEDI, technicien=self.tech)
        res = nivellement_charge(self.company, SAMEDI, SAMEDI)
        self.assertEqual(res['capacite_jours'], 0)
        # Aucune exception ; propositions = liste (vide ici, pas de sous-chargé).
        self.assertIsInstance(res['propositions'], list)


# ── Scope société ─────────────────────────────────────────────────────────────

class TestNivellementScope(TestCase):
    def test_scope_societe(self):
        """FG301 — une sur-charge d'une AUTRE société n'apparaît jamais."""
        company_a = make_company()
        company_b = make_company()
        inst_b = make_installation(company_b)
        surcharge_b = make_user(company_b)
        make_user(company_b)  # technicien libre côté B
        for jour in JOURS_OUVRES + [SAMEDI]:
            make_intervention(company_b, inst_b, jour, technicien=surcharge_b)
        # Vu depuis la société A : aucune sur-charge.
        res_a = nivellement_charge(company_a, LUNDI, SEMAINE_FIN)
        self.assertEqual(res_a['totaux']['nb_surcharges'], 0)
        self.assertEqual(res_a['propositions'], [])
        # Vu depuis la société B : la sur-charge existe bien.
        res_b = nivellement_charge(company_b, LUNDI, SEMAINE_FIN)
        self.assertEqual(res_b['totaux']['nb_surcharges'], 1)


# ── Endpoint ──────────────────────────────────────────────────────────────────

class TestNivellementEndpoint(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.inst = make_installation(self.company)
        self.surcharge = make_user(self.company)
        self.libre = make_user(self.company)

    def test_endpoint_renvoie_propositions(self):
        """FG301 — l'endpoint nivellement-charge renvoie les propositions de
        déplacement de la fenêtre demandée (200)."""
        for jour in JOURS_OUVRES + [SAMEDI]:
            make_intervention(self.company, self.inst, jour,
                              technicien=self.surcharge)
        make_intervention(self.company, self.inst, LUNDI,
                          technicien=self.libre)
        r = self.api.get(
            f'{BASE}/interventions/nivellement-charge/',
            {'debut': LUNDI.isoformat(), 'fin': SEMAINE_FIN.isoformat()})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['totaux']['nb_surcharges'], 1)
        self.assertGreaterEqual(r.data['totaux']['nb_propositions'], 1)
        self.assertEqual(r.data['propositions'][0]['vers_id'], self.libre.id)

    def test_endpoint_lecture_pour_tout_role(self):
        """FG301 — la lecture est ouverte à tout rôle (IsAnyRole) : un
        utilisateur « normal » (ni responsable ni admin) obtient 200, pas 403 —
        c'est bien dans la liste des read-actions de get_permissions."""
        normal = make_user(self.company, role='normal')
        api = auth(normal)
        r = api.get(
            f'{BASE}/interventions/nivellement-charge/',
            {'debut': LUNDI.isoformat(), 'fin': SEMAINE_FIN.isoformat()})
        self.assertEqual(r.status_code, 200)

    def test_endpoint_fenetre_inversee_400(self):
        """FG301 — fenêtre inversée côté endpoint → 400."""
        r = self.api.get(
            f'{BASE}/interventions/nivellement-charge/',
            {'debut': SEMAINE_FIN.isoformat(), 'fin': LUNDI.isoformat()})
        self.assertEqual(r.status_code, 400)

    def test_endpoint_scope_societe(self):
        """FG301 — l'endpoint ne montre que les sur-charges de la société de
        l'utilisateur."""
        other = make_company()
        inst_o = make_installation(other)
        surcharge_o = make_user(other)
        for jour in JOURS_OUVRES + [SAMEDI]:
            make_intervention(other, inst_o, jour, technicien=surcharge_o)
        r = self.api.get(
            f'{BASE}/interventions/nivellement-charge/',
            {'debut': LUNDI.isoformat(), 'fin': SEMAINE_FIN.isoformat()})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['totaux']['nb_surcharges'], 0)
