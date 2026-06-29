"""
FG303 — Planning des camionnettes (capacité véhicule) — sélecteur
``planning_camionnettes`` + action ``InterventionViewSet.planning_camionnettes``.

Pour chaque camionnette (``Intervention.camionnette`` — un EmplacementStock) qui
porte des interventions dans la fenêtre, on regroupe les interventions (date /
chantier / technicien) et on dérive une charge journalière qui EXCLUT les jours
d'indisponibilité du véhicule (FG302 ``IndisponibiliteRessource``). Cohérent avec
FG300 : deux interventions le même jour sur la même camionnette = sur-réservation.

Couvre :
  * interventions groupées par camionnette (date / chantier / technicien) ;
  * fenêtrage (hors fenêtre ignoré, sans date prévue ignoré, sans camionnette
    ignoré) ;
  * sur-réservation = deux interventions le même jour sur le même véhicule ;
  * indisponibilité FG302 : jour indisponible exclu de la capacité → toute
    intervention ce jour-là est en sur-réservation ; un jour 100 % indisponible
    sans intervention reste visible (count=0, indisponible=True) ;
  * le scope société (aucune camionnette d'une autre société) ;
  * les gardes fenêtre vide/None/inversée ;
  * l'endpoint ``planning-camionnettes`` (200 + lecture toute-rôle + 400 fenêtre
    inversée).

Pure agrégation, lecture seule, aucun nouveau modèle.

Run :
    python manage.py test apps.installations.tests_fg303_planning_camionnettes -v2
"""
import datetime
import itertools

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.installations.models import (
    Installation, Intervention, IndisponibiliteRessource,
)
from apps.installations.selectors import planning_camionnettes
from apps.stock.models import EmplacementStock

User = get_user_model()
_seq = itertools.count(1)

BASE = '/api/django/installations'


# ── Helpers ──────────────────────────────────────────────────────────────────

def make_company(slug=None, nom=None):
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'fg303-co-{n}', defaults={'nom': nom or f'FG303 Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_user(company, role='technicien', username=None):
    return User.objects.create_user(
        username=username or f'fg303-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def make_client(company):
    n = next(_seq)
    return Client.objects.create(
        company=company, nom='Client', prenom='Test',
        email=f'fg303-{company.id}-{n}@example.invalid')


def make_installation(company, reference=None):
    n = next(_seq)
    return Installation.objects.create(
        company=company, reference=reference or f'CH-{company.id}-{n}',
        client=make_client(company))


def make_camionnette(company, nom=None):
    return EmplacementStock.objects.create(
        company=company, nom=nom or f'Camion {next(_seq)}')


def make_intervention(company, installation, date_prevue,
                      technicien=None, camionnette=None):
    return Intervention.objects.create(
        company=company, installation=installation,
        type_intervention=Intervention.Type.POSE,
        date_prevue=date_prevue, technicien=technicien,
        camionnette=camionnette)


def make_indispo(company, camionnette, debut, fin):
    return IndisponibiliteRessource.objects.create(
        company=company, camionnette=camionnette,
        type_indispo=IndisponibiliteRessource.Type.ARRET,
        date_debut=debut, date_fin=fin)


# Fenêtre de référence : lundi 2026-06-01 → dimanche 2026-06-07.
LUNDI = datetime.date(2026, 6, 1)
MARDI = datetime.date(2026, 6, 2)
MERCREDI = datetime.date(2026, 6, 3)
SEMAINE_FIN = datetime.date(2026, 6, 7)


# ── Sélecteur : regroupement par camionnette ─────────────────────────────────

class TestPlanningGroupe(TestCase):
    def setUp(self):
        self.company = make_company()
        self.inst = make_installation(self.company, reference='CH-AAA')
        self.camion = make_camionnette(self.company, nom='Camionnette A')
        self.tech = make_user(self.company)

    def test_interventions_groupees_par_camionnette(self):
        """FG303 — les interventions d'une camionnette sont regroupées sous
        elle, triées par date, avec chantier + technicien."""
        a = make_intervention(self.company, self.inst, LUNDI,
                              technicien=self.tech, camionnette=self.camion)
        b = make_intervention(self.company, self.inst, MARDI,
                              technicien=self.tech, camionnette=self.camion)
        res = planning_camionnettes(self.company, LUNDI, SEMAINE_FIN)
        self.assertEqual(res['totaux']['nb_camionnettes'], 1)
        self.assertEqual(res['totaux']['nb_interventions'], 2)
        camion = res['camionnettes'][0]
        self.assertEqual(camion['camionnette_id'], self.camion.id)
        self.assertEqual(camion['nom'], 'Camionnette A')
        ids = [i['id'] for i in camion['interventions']]
        self.assertEqual(ids, [a.id, b.id])  # triées par date
        first = camion['interventions'][0]
        self.assertEqual(first['chantier_id'], self.inst.id)
        self.assertEqual(first['chantier_reference'], 'CH-AAA')
        self.assertEqual(first['technicien_id'], self.tech.id)
        self.assertEqual(first['date'], LUNDI.isoformat())

    def test_charge_journaliere_un_par_jour(self):
        """FG303 — deux jours distincts → deux entrées de charge, count=1,
        aucune sur-réservation (capacité par défaut 1/jour)."""
        make_intervention(self.company, self.inst, LUNDI, camionnette=self.camion)
        make_intervention(self.company, self.inst, MARDI, camionnette=self.camion)
        res = planning_camionnettes(self.company, LUNDI, SEMAINE_FIN)
        charge = res['camionnettes'][0]['charge']
        self.assertEqual(len(charge), 2)
        self.assertTrue(all(c['count'] == 1 for c in charge))
        self.assertTrue(all(not c['sur_reservation'] for c in charge))
        self.assertEqual(res['totaux']['nb_jours_sur_reservation'], 0)

    def test_deux_interventions_meme_jour_sur_reservation(self):
        """FG303 — deux interventions le MÊME jour sur le même véhicule =
        sur-réservation (cohérent avec FG300)."""
        make_intervention(self.company, self.inst, MERCREDI,
                          camionnette=self.camion)
        make_intervention(self.company, self.inst, MERCREDI,
                          camionnette=self.camion)
        res = planning_camionnettes(self.company, LUNDI, SEMAINE_FIN)
        camion = res['camionnettes'][0]
        jour = next(c for c in camion['charge']
                    if c['date'] == MERCREDI.isoformat())
        self.assertEqual(jour['count'], 2)
        self.assertTrue(jour['sur_reservation'])
        self.assertEqual(camion['jours_sur_reservation'], 1)
        self.assertEqual(res['totaux']['nb_jours_sur_reservation'], 1)

    def test_deux_camionnettes_triees_par_nom(self):
        """FG303 — plusieurs camionnettes sont listées et triées par nom."""
        camion_z = make_camionnette(self.company, nom='Zèbre')
        make_intervention(self.company, self.inst, LUNDI, camionnette=camion_z)
        make_intervention(self.company, self.inst, LUNDI,
                          camionnette=self.camion)
        res = planning_camionnettes(self.company, LUNDI, SEMAINE_FIN)
        noms = [c['nom'] for c in res['camionnettes']]
        self.assertEqual(noms, ['Camionnette A', 'Zèbre'])


# ── Fenêtrage & filtres ──────────────────────────────────────────────────────

class TestPlanningFenetre(TestCase):
    def setUp(self):
        self.company = make_company()
        self.inst = make_installation(self.company)
        self.camion = make_camionnette(self.company)

    def test_hors_fenetre_ignore(self):
        """FG303 — une intervention hors [debut, fin] n'apparaît pas."""
        hors = datetime.date(2026, 7, 1)
        make_intervention(self.company, self.inst, hors, camionnette=self.camion)
        res = planning_camionnettes(self.company, LUNDI, SEMAINE_FIN)
        self.assertEqual(res['totaux']['nb_camionnettes'], 0)

    def test_sans_date_prevue_ignore(self):
        """FG303 — une intervention sans date prévue n'a pas de créneau."""
        make_intervention(self.company, self.inst, None, camionnette=self.camion)
        res = planning_camionnettes(self.company, LUNDI, SEMAINE_FIN)
        self.assertEqual(res['totaux']['nb_camionnettes'], 0)

    def test_sans_camionnette_ignore(self):
        """FG303 — une intervention sans camionnette n'est pas un planning de
        véhicule."""
        make_intervention(self.company, self.inst, LUNDI, camionnette=None)
        res = planning_camionnettes(self.company, LUNDI, SEMAINE_FIN)
        self.assertEqual(res['totaux']['nb_camionnettes'], 0)

    def test_fenetre_none_renvoie_vide(self):
        """FG303 — fenêtre None : garde explicite, listes vides, aucune
        exception."""
        make_intervention(self.company, self.inst, LUNDI, camionnette=self.camion)
        res = planning_camionnettes(self.company, None, None)
        self.assertEqual(res['camionnettes'], [])
        self.assertEqual(res['totaux']['nb_camionnettes'], 0)
        self.assertIsNone(res['debut'])
        self.assertIsNone(res['fin'])

    def test_fenetre_inversee_renvoie_vide(self):
        """FG303 — fenêtre inversée (fin < debut) : listes vides, pas
        d'exception."""
        make_intervention(self.company, self.inst, LUNDI, camionnette=self.camion)
        res = planning_camionnettes(self.company, SEMAINE_FIN, LUNDI)
        self.assertEqual(res['camionnettes'], [])


# ── Indisponibilité FG302 exclue de la capacité ──────────────────────────────

class TestPlanningIndispo(TestCase):
    def setUp(self):
        self.company = make_company()
        self.inst = make_installation(self.company)
        self.camion = make_camionnette(self.company, nom='Camion Indispo')

    def test_jour_indispo_rend_lintervention_sur_reservee(self):
        """FG303 — une intervention un jour où la camionnette est indisponible
        (FG302) est en sur-réservation (capacité 0 ce jour-là)."""
        make_intervention(self.company, self.inst, MARDI, camionnette=self.camion)
        make_indispo(self.company, self.camion, MARDI, MARDI)
        res = planning_camionnettes(self.company, LUNDI, SEMAINE_FIN)
        camion = res['camionnettes'][0]
        jour = next(c for c in camion['charge']
                    if c['date'] == MARDI.isoformat())
        self.assertTrue(jour['indisponible'])
        self.assertEqual(jour['count'], 1)
        self.assertTrue(jour['sur_reservation'])

    def test_jour_indispo_sans_intervention_reste_visible(self):
        """FG303 — un jour 100 % indisponible sans intervention reste visible
        dans la charge (count=0, indisponible=True), sans sur-réservation."""
        # Une intervention un autre jour pour que la camionnette soit listée.
        make_intervention(self.company, self.inst, LUNDI, camionnette=self.camion)
        make_indispo(self.company, self.camion, MERCREDI, MERCREDI)
        res = planning_camionnettes(self.company, LUNDI, SEMAINE_FIN)
        camion = res['camionnettes'][0]
        jour = next(c for c in camion['charge']
                    if c['date'] == MERCREDI.isoformat())
        self.assertTrue(jour['indisponible'])
        self.assertEqual(jour['count'], 0)
        self.assertFalse(jour['sur_reservation'])

    def test_indispo_dune_autre_societe_ignoree(self):
        """FG303 — une indisponibilité d'une AUTRE société ne touche pas la
        capacité du véhicule de cette société (scope)."""
        make_intervention(self.company, self.inst, MARDI, camionnette=self.camion)
        # Indispo créée sous une autre société (scope filtrant).
        autre = make_company()
        IndisponibiliteRessource.objects.create(
            company=autre, camionnette=self.camion,
            type_indispo=IndisponibiliteRessource.Type.ARRET,
            date_debut=MARDI, date_fin=MARDI)
        res = planning_camionnettes(self.company, LUNDI, SEMAINE_FIN)
        camion = res['camionnettes'][0]
        jour = next(c for c in camion['charge']
                    if c['date'] == MARDI.isoformat())
        self.assertFalse(jour['indisponible'])
        self.assertFalse(jour['sur_reservation'])


# ── Scope société ────────────────────────────────────────────────────────────

class TestPlanningScope(TestCase):
    def test_scope_societe(self):
        """FG303 — une camionnette d'une AUTRE société n'apparaît jamais."""
        company_a = make_company()
        company_b = make_company()
        inst_b = make_installation(company_b)
        camion_b = make_camionnette(company_b)
        make_intervention(company_b, inst_b, LUNDI, camionnette=camion_b)
        res_a = planning_camionnettes(company_a, LUNDI, SEMAINE_FIN)
        self.assertEqual(res_a['totaux']['nb_camionnettes'], 0)
        res_b = planning_camionnettes(company_b, LUNDI, SEMAINE_FIN)
        self.assertEqual(res_b['totaux']['nb_camionnettes'], 1)


# ── Endpoint ─────────────────────────────────────────────────────────────────

class TestPlanningEndpoint(TestCase):
    def setUp(self):
        self.company = make_company()
        # Rôle « technicien » → vérifie la lecture toute-rôle (IsAnyRole).
        self.user = make_user(self.company, role='technicien')
        self.api = auth(self.user)
        self.inst = make_installation(self.company)
        self.camion = make_camionnette(self.company, nom='Camion API')

    def test_endpoint_renvoie_le_planning(self):
        """FG303 — l'endpoint planning-camionnettes renvoie 200 et le planning
        de la fenêtre demandée (lecture autorisée à tout rôle)."""
        make_intervention(self.company, self.inst, LUNDI, camionnette=self.camion)
        make_intervention(self.company, self.inst, MARDI, camionnette=self.camion)
        r = self.api.get(
            f'{BASE}/interventions/planning-camionnettes/',
            {'debut': LUNDI.isoformat(), 'fin': SEMAINE_FIN.isoformat()})
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['totaux']['nb_camionnettes'], 1)
        camion = r.data['camionnettes'][0]
        self.assertEqual(camion['camionnette_id'], self.camion.id)
        self.assertEqual(camion['total_interventions'], 2)

    def test_endpoint_default_window_is_current_week(self):
        """FG303 — sans paramètres, la fenêtre défaut = semaine en cours
        (lundi→dimanche) ; l'endpoint répond 200."""
        r = self.api.get(f'{BASE}/interventions/planning-camionnettes/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertIn('camionnettes', r.data)

    def test_endpoint_fenetre_inversee_400(self):
        """FG303 — fenêtre inversée côté endpoint → 400."""
        r = self.api.get(
            f'{BASE}/interventions/planning-camionnettes/',
            {'debut': SEMAINE_FIN.isoformat(), 'fin': LUNDI.isoformat()})
        self.assertEqual(r.status_code, 400, r.data)

    def test_endpoint_scope_societe(self):
        """FG303 — l'endpoint ne montre que les camionnettes de la société de
        l'utilisateur."""
        other = make_company()
        inst_o = make_installation(other)
        camion_o = make_camionnette(other)
        make_intervention(other, inst_o, LUNDI, camionnette=camion_o)
        r = self.api.get(
            f'{BASE}/interventions/planning-camionnettes/',
            {'debut': LUNDI.isoformat(), 'fin': SEMAINE_FIN.isoformat()})
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['totaux']['nb_camionnettes'], 0)
