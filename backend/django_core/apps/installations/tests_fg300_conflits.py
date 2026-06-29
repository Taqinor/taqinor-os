"""
FG300 — Détection de conflits d'affectation (double-booking) — sélecteur
``conflits_affectation`` + action ``InterventionViewSet.conflits_affectation``.

Un conflit existe quand une MÊME ressource (technicien principal OU membre
d'équipe, ou camionnette) est affectée à ≥ 2 interventions dont le créneau se
chevauche. Les interventions ne portent qu'une `date_prevue` (granularité jour),
le chevauchement = même jour.

Couvre :
  * conflit détecté pour un même technicien principal le même jour ;
  * conflit détecté pour une même camionnette le même jour ;
  * conflit détecté pour un membre d'équipe (M2M) ;
  * AUCUN conflit quand les créneaux sont disjoints (jours différents) ;
  * AUCUN double-comptage (technicien principal ET membre d'équipe) ;
  * la garde fenêtre vide/None/inversée ;
  * le fenêtrage (hors fenêtre ignoré, sans date prévue ignoré) ;
  * le scope société (aucune intervention d'une autre société) ;
  * l'endpoint ``conflits-affectation``.

Pure détection, lecture seule, aucun nouveau modèle.

Run :
    python manage.py test apps.installations.tests_fg300_conflits -v2
"""
import datetime
import itertools

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.installations.models import Installation, Intervention
from apps.installations.selectors import conflits_affectation
from apps.stock.models import EmplacementStock

User = get_user_model()
_seq = itertools.count(1)

BASE = '/api/django/installations'


# ── Helpers ──────────────────────────────────────────────────────────────────

def make_company(slug=None, nom=None):
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'fg300-co-{n}', defaults={'nom': nom or f'FG300 Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_user(company, role='responsable', username=None):
    return User.objects.create_user(
        username=username or f'fg300-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def make_client(company):
    n = next(_seq)
    return Client.objects.create(
        company=company, nom='Client', prenom='Test',
        email=f'fg300-{company.id}-{n}@example.invalid')


def make_installation(company):
    n = next(_seq)
    return Installation.objects.create(
        company=company, reference=f'CH-{company.id}-{n}',
        client=make_client(company))


def make_camionnette(company, nom=None):
    return EmplacementStock.objects.create(
        company=company, nom=nom or f'Camion {next(_seq)}')


def make_intervention(company, installation, date_prevue,
                      technicien=None, equipe=None, camionnette=None):
    interv = Intervention.objects.create(
        company=company, installation=installation,
        type_intervention=Intervention.Type.POSE,
        date_prevue=date_prevue, technicien=technicien,
        camionnette=camionnette)
    if equipe:
        interv.equipe.set(equipe)
    return interv


# Fenêtre de référence : lundi 2026-06-01 → dimanche 2026-06-07.
LUNDI = datetime.date(2026, 6, 1)
MARDI = datetime.date(2026, 6, 2)
MERCREDI = datetime.date(2026, 6, 3)
SEMAINE_FIN = datetime.date(2026, 6, 7)


# ── Sélecteur : conflits détectés ─────────────────────────────────────────────

class TestConflitsTechnicien(TestCase):
    def setUp(self):
        self.company = make_company()
        self.inst = make_installation(self.company)
        self.tech = make_user(self.company)

    def test_meme_technicien_meme_jour_est_un_conflit(self):
        """FG300 — un technicien principal sur 2 interventions le même jour =
        un conflit, avec les 2 interventions listées."""
        a = make_intervention(self.company, self.inst, LUNDI,
                              technicien=self.tech)
        b = make_intervention(self.company, self.inst, LUNDI,
                              technicien=self.tech)
        res = conflits_affectation(self.company, LUNDI, SEMAINE_FIN)
        self.assertEqual(res['totaux']['nb_conflits'], 1)
        self.assertEqual(res['totaux']['nb_techniciens'], 1)
        conflit = res['conflits'][0]
        self.assertEqual(conflit['type'], 'technicien')
        self.assertEqual(conflit['ressource_id'], self.tech.id)
        self.assertEqual(conflit['date'], LUNDI.isoformat())
        self.assertEqual(conflit['count'], 2)
        ids = {i['id'] for i in conflit['interventions']}
        self.assertEqual(ids, {a.id, b.id})

    def test_jours_disjoints_pas_de_conflit(self):
        """FG300 — même technicien mais sur 2 jours différents = pas de
        chevauchement, donc aucun conflit."""
        make_intervention(self.company, self.inst, LUNDI, technicien=self.tech)
        make_intervention(self.company, self.inst, MARDI, technicien=self.tech)
        res = conflits_affectation(self.company, LUNDI, SEMAINE_FIN)
        self.assertEqual(res['totaux']['nb_conflits'], 0)
        self.assertEqual(res['conflits'], [])

    def test_membre_equipe_double_booke(self):
        """FG300 — un membre d'équipe (M2M) compte comme une ressource : 2
        interventions le même jour avec le même membre = conflit."""
        membre = make_user(self.company)
        make_intervention(self.company, self.inst, MARDI, equipe=[membre])
        make_intervention(self.company, self.inst, MARDI, equipe=[membre])
        res = conflits_affectation(self.company, LUNDI, SEMAINE_FIN)
        self.assertEqual(res['totaux']['nb_conflits'], 1)
        conflit = res['conflits'][0]
        self.assertEqual(conflit['ressource_id'], membre.id)
        self.assertEqual(conflit['type'], 'technicien')
        self.assertEqual(conflit['count'], 2)

    def test_pas_de_double_comptage_principal_et_equipe(self):
        """FG300 — un technicien à la fois principal ET membre d'équipe sur les
        2 mêmes interventions ne crée qu'UN conflit, chaque intervention listée
        une seule fois."""
        a = make_intervention(self.company, self.inst, LUNDI,
                              technicien=self.tech, equipe=[self.tech])
        b = make_intervention(self.company, self.inst, LUNDI,
                              technicien=self.tech, equipe=[self.tech])
        res = conflits_affectation(self.company, LUNDI, SEMAINE_FIN)
        # Une seule entrée pour ce technicien (pas un doublon principal/équipe).
        tech_conflits = [c for c in res['conflits']
                         if c['ressource_id'] == self.tech.id]
        self.assertEqual(len(tech_conflits), 1)
        ids = [i['id'] for i in tech_conflits[0]['interventions']]
        self.assertEqual(sorted(ids), sorted([a.id, b.id]))  # pas de doublon
        self.assertEqual(tech_conflits[0]['count'], 2)


class TestConflitsCamionnette(TestCase):
    def setUp(self):
        self.company = make_company()
        self.inst = make_installation(self.company)
        self.camion = make_camionnette(self.company, nom='Camionnette A')

    def test_meme_camionnette_meme_jour_est_un_conflit(self):
        """FG300 — une camionnette sur 2 interventions le même jour = conflit
        de type camionnette, avec le nom de la camionnette."""
        make_intervention(self.company, self.inst, MERCREDI,
                          camionnette=self.camion)
        make_intervention(self.company, self.inst, MERCREDI,
                          camionnette=self.camion)
        res = conflits_affectation(self.company, LUNDI, SEMAINE_FIN)
        self.assertEqual(res['totaux']['nb_conflits'], 1)
        self.assertEqual(res['totaux']['nb_camionnettes'], 1)
        conflit = res['conflits'][0]
        self.assertEqual(conflit['type'], 'camionnette')
        self.assertEqual(conflit['ressource_id'], self.camion.id)
        self.assertEqual(conflit['ressource_nom'], 'Camionnette A')
        self.assertEqual(conflit['count'], 2)

    def test_camionnette_jours_disjoints_pas_de_conflit(self):
        """FG300 — même camionnette sur 2 jours différents = pas de conflit."""
        make_intervention(self.company, self.inst, LUNDI,
                          camionnette=self.camion)
        make_intervention(self.company, self.inst, MARDI,
                          camionnette=self.camion)
        res = conflits_affectation(self.company, LUNDI, SEMAINE_FIN)
        self.assertEqual(res['totaux']['nb_conflits'], 0)


# ── Fenêtrage & gardes ────────────────────────────────────────────────────────

class TestConflitsFenetre(TestCase):
    def setUp(self):
        self.company = make_company()
        self.inst = make_installation(self.company)
        self.tech = make_user(self.company)

    def test_hors_fenetre_ignore(self):
        """FG300 — un double-booking en dehors de [debut, fin] n'est pas
        signalé."""
        hors = datetime.date(2026, 7, 1)
        make_intervention(self.company, self.inst, hors, technicien=self.tech)
        make_intervention(self.company, self.inst, hors, technicien=self.tech)
        res = conflits_affectation(self.company, LUNDI, SEMAINE_FIN)
        self.assertEqual(res['totaux']['nb_conflits'], 0)

    def test_sans_date_prevue_ignore(self):
        """FG300 — une intervention sans date prévue n'a pas de créneau, donc
        ne peut pas entrer en collision."""
        make_intervention(self.company, self.inst, None, technicien=self.tech)
        make_intervention(self.company, self.inst, None, technicien=self.tech)
        res = conflits_affectation(self.company, LUNDI, SEMAINE_FIN)
        self.assertEqual(res['totaux']['nb_conflits'], 0)

    def test_fenetre_none_renvoie_vide(self):
        """FG300 — fenêtre None : garde explicite, liste vide, aucune
        exception."""
        make_intervention(self.company, self.inst, LUNDI, technicien=self.tech)
        make_intervention(self.company, self.inst, LUNDI, technicien=self.tech)
        res = conflits_affectation(self.company, None, None)
        self.assertEqual(res['conflits'], [])
        self.assertEqual(res['totaux']['nb_conflits'], 0)
        self.assertIsNone(res['debut'])
        self.assertIsNone(res['fin'])

    def test_fenetre_inversee_renvoie_vide(self):
        """FG300 — fenêtre inversée (fin < debut) : liste vide, pas
        d'exception."""
        make_intervention(self.company, self.inst, LUNDI, technicien=self.tech)
        make_intervention(self.company, self.inst, LUNDI, technicien=self.tech)
        res = conflits_affectation(self.company, SEMAINE_FIN, LUNDI)
        self.assertEqual(res['conflits'], [])


# ── Scope société ─────────────────────────────────────────────────────────────

class TestConflitsScope(TestCase):
    def test_scope_societe(self):
        """FG300 — un double-booking d'une AUTRE société n'apparaît jamais."""
        company_a = make_company()
        company_b = make_company()
        inst_b = make_installation(company_b)
        tech_b = make_user(company_b)
        make_intervention(company_b, inst_b, LUNDI, technicien=tech_b)
        make_intervention(company_b, inst_b, LUNDI, technicien=tech_b)
        # Vu depuis la société A : rien.
        res_a = conflits_affectation(company_a, LUNDI, SEMAINE_FIN)
        self.assertEqual(res_a['totaux']['nb_conflits'], 0)
        # Vu depuis la société B : le conflit existe bien.
        res_b = conflits_affectation(company_b, LUNDI, SEMAINE_FIN)
        self.assertEqual(res_b['totaux']['nb_conflits'], 1)


# ── Endpoint ──────────────────────────────────────────────────────────────────

class TestConflitsEndpoint(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.inst = make_installation(self.company)
        self.tech = make_user(self.company)

    def test_endpoint_liste_les_conflits(self):
        """FG300 — l'endpoint conflits-affectation renvoie les collisions de la
        fenêtre demandée."""
        make_intervention(self.company, self.inst, LUNDI, technicien=self.tech)
        make_intervention(self.company, self.inst, LUNDI, technicien=self.tech)
        r = self.api.get(
            f'{BASE}/interventions/conflits-affectation/',
            {'debut': LUNDI.isoformat(), 'fin': SEMAINE_FIN.isoformat()})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['totaux']['nb_conflits'], 1)
        self.assertEqual(r.data['conflits'][0]['ressource_id'], self.tech.id)

    def test_endpoint_fenetre_inversee_400(self):
        """FG300 — fenêtre inversée côté endpoint → 400."""
        r = self.api.get(
            f'{BASE}/interventions/conflits-affectation/',
            {'debut': SEMAINE_FIN.isoformat(), 'fin': LUNDI.isoformat()})
        self.assertEqual(r.status_code, 400)

    def test_endpoint_scope_societe(self):
        """FG300 — l'endpoint ne montre que les conflits de la société de
        l'utilisateur."""
        other = make_company()
        inst_o = make_installation(other)
        tech_o = make_user(other)
        make_intervention(other, inst_o, LUNDI, technicien=tech_o)
        make_intervention(other, inst_o, LUNDI, technicien=tech_o)
        r = self.api.get(
            f'{BASE}/interventions/conflits-affectation/',
            {'debut': LUNDI.isoformat(), 'fin': SEMAINE_FIN.isoformat()})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['totaux']['nb_conflits'], 0)
