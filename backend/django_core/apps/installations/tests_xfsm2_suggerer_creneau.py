"""
XFSM2 — Assistant de planification : meilleur créneau + technicien suggéré.

Couvre :
  * l'endpoint renvoie des propositions valides (jamais un technicien en
    congé/conflit/sans habilitation) ;
  * tri déterministe (charge la plus faible d'abord) ;
  * lecture seule (ne mute rien) ;
  * bouton câblé côté frontend est hors périmètre backend (test API only).

Run :
    python manage.py test apps.installations.tests_xfsm2_suggerer_creneau -v2
"""
import itertools
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client, Lead
from apps.ventes.models import Devis
from apps.installations import selectors, services
from apps.installations.models import Installation, Intervention, IndisponibiliteRessource
from apps.installations.planification_lot import suggerer_creneaux_lot
from apps.installations.services import create_installation_from_devis

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations'


def make_company(slug=None, nom=None):
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'xfsm2-co-{n}', defaults={'nom': nom or f'XFSM2 Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_user(company, role='responsable', username=None):
    return User.objects.create_user(
        username=username or f'xfsm2-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def make_chantier(company, user):
    n = next(_seq)
    client = Client.objects.create(
        company=company, nom='Site', prenom='Client',
        email=f'xfsm2-{company.id}-{n}@example.invalid')
    lead = Lead.objects.create(
        company=company, nom='Site', prenom='Client', stage='SIGNED',
        type_installation='residentiel')
    devis = Devis.objects.create(
        company=company, reference=f'DEV-XFSM2-{company.id}-{n}', client=client,
        lead=lead, statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20'),
        mode_installation='residentiel')
    inst, _ = create_installation_from_devis(devis, user, company)
    return inst


class TestSuggererCreneau(TestCase):
    def setUp(self):
        self.company = make_company()
        self.admin = make_user(self.company, role='admin')
        self.api = auth(self.admin)
        self.inst = make_chantier(self.company, self.admin)
        self.tech1 = make_user(self.company, username='xfsm2-tech1')
        self.tech2 = make_user(self.company, username='xfsm2-tech2')
        # les deux techniciens entrent dans le "bassin éligible" via une
        # intervention passée déjà affectée (même patron que FG299).
        Intervention.objects.create(
            company=self.company, installation=self.inst,
            type_intervention='pose', created_by=self.admin,
            technicien=self.tech1, date_prevue=date.today() - timedelta(days=30))
        Intervention.objects.create(
            company=self.company, installation=self.inst,
            type_intervention='pose', created_by=self.admin,
            technicien=self.tech2, date_prevue=date.today() - timedelta(days=30))

    def test_renvoie_propositions_valides(self):
        resp = self.api.post(f'{BASE}/interventions/suggerer-creneau/', {
            'chantier': self.inst.id, 'type_intervention': 'controle',
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertGreater(len(resp.data['propositions']), 0)
        for prop in resp.data['propositions']:
            self.assertIn('technicien_id', prop)
            self.assertIn('date', prop)

    def test_ne_propose_jamais_technicien_en_conge(self):
        demain = date.today() + timedelta(days=1)
        IndisponibiliteRessource.objects.create(
            company=self.company, technicien=self.tech1,
            date_debut=date.today(), date_fin=demain + timedelta(days=20),
            type_indispo='conge')
        resp = self.api.post(f'{BASE}/interventions/suggerer-creneau/', {
            'chantier': self.inst.id, 'type_intervention': 'controle',
            'date_cible': demain.isoformat(),
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        ids_proposes = {p['technicien_id'] for p in resp.data['propositions']}
        self.assertNotIn(self.tech1.id, ids_proposes)

    def test_ne_propose_jamais_technicien_en_conflit(self):
        jour = date.today() + timedelta(days=2)
        Intervention.objects.create(
            company=self.company, installation=self.inst,
            type_intervention='pose', created_by=self.admin,
            technicien=self.tech1, date_prevue=jour)
        resp = self.api.post(f'{BASE}/interventions/suggerer-creneau/', {
            'chantier': self.inst.id, 'type_intervention': 'controle',
            'date_cible': jour.isoformat(),
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        propositions_ce_jour = [
            p for p in resp.data['propositions'] if p['date'] == jour.isoformat()]
        ids_ce_jour = {p['technicien_id'] for p in propositions_ce_jour}
        self.assertNotIn(self.tech1.id, ids_ce_jour)

    def test_tri_deterministe_par_charge(self):
        # tech2 a plus de charge future que tech1 dans la fenêtre.
        jour_cible = date.today() + timedelta(days=5)
        for i in range(3):
            Intervention.objects.create(
                company=self.company, installation=self.inst,
                type_intervention='pose', created_by=self.admin,
                technicien=self.tech2,
                date_prevue=jour_cible + timedelta(days=i + 1))
        resp = self.api.post(f'{BASE}/interventions/suggerer-creneau/', {
            'chantier': self.inst.id, 'type_intervention': 'controle',
            'date_cible': jour_cible.isoformat(),
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        propositions = resp.data['propositions']
        # tech1 (moins chargé) doit apparaître avant tech2 pour un même jour.
        rangs = {p['technicien_id']: i for i, p in enumerate(propositions)}
        if self.tech1.id in rangs and self.tech2.id in rangs:
            self.assertLess(rangs[self.tech1.id], rangs[self.tech2.id])

    def test_lecture_seule_ne_mute_rien(self):
        nb_avant = Intervention.objects.count()
        self.api.post(f'{BASE}/interventions/suggerer-creneau/', {
            'chantier': self.inst.id, 'type_intervention': 'controle',
        }, format='json')
        self.assertEqual(Intervention.objects.count(), nb_avant)

    def test_chantier_manquant_rejete(self):
        resp = self.api.post(f'{BASE}/interventions/suggerer-creneau/', {
            'type_intervention': 'controle',
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)

    def test_chantier_inconnu_propositions_vides(self):
        resp = self.api.post(f'{BASE}/interventions/suggerer-creneau/', {
            'chantier': 999999, 'type_intervention': 'controle',
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data['propositions'], [])

    def test_corps_mal_type_400_nomme(self):
        # ERR-ENF11-FUZZ-INSTALLATIONS — `chantier: 0` était lu « absent »,
        # `chantier: "abc"` et `duree_jours: 10**9` partaient au calcul : le
        # corps est validé par sa déclaration (400 nommant le champ).
        for corps, champ in (({'chantier': 0}, 'chantier'),
                             ({'chantier': 'abc'}, 'chantier'),
                             ({'chantier': self.inst.id, 'duree_jours': 0}, 'duree_jours'),
                             ({'chantier': self.inst.id, 'duree_jours': 10 ** 9}, 'duree_jours'),
                             ({'chantier': self.inst.id, 'type_intervention': 0},
                              'type_intervention')):
            resp = self.api.post(f'{BASE}/interventions/suggerer-creneau/',
                                 corps, format='json')
            self.assertEqual(resp.status_code, 400, (corps, resp.content))
            self.assertIn(champ, resp.json())


class TestSuggererCreneauDureeLongue(TestCase):
    """CI #997 (api-fuzz, « Network Error » : lecture expirée après 10 s) —
    ``duree_jours`` jusqu'à 365 : l'indisponibilité d'un bloc se lit en UNE
    requête par (jour, technicien), pas une par jour du bloc."""

    def setUp(self):
        self.company = make_company()
        self.admin = make_user(self.company, role='admin')
        self.api = auth(self.admin)
        self.inst = make_chantier(self.company, self.admin)
        self.tech = make_user(self.company, username='xfsm2-long-tech')
        Intervention.objects.create(
            company=self.company, installation=self.inst,
            type_intervention='pose', created_by=self.admin,
            technicien=self.tech, date_prevue=date.today() - timedelta(days=30))

    def test_bloc_de_364_jours_sans_une_requete_par_jour(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        with CaptureQueriesContext(connection) as requetes:
            resp = self.api.post(f'{BASE}/interventions/suggerer-creneau/', {
                'chantier': self.inst.id, 'type_intervention': '',
                'duree_jours': 364, 'date_cible': '2000-01-01',
            }, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertLess(len(requetes), 100)
        self.assertGreater(len(resp.data['propositions']), 0)

    def test_une_indisponibilite_au_milieu_du_bloc_l_exclut_toujours(self):
        debut = date.today() + timedelta(days=1)
        # Un jour OUVRÉ au milieu d'un bloc de 10 jours ouvrés.
        milieu = debut + timedelta(days=5)
        while milieu.weekday() >= 5:
            milieu += timedelta(days=1)
        IndisponibiliteRessource.objects.create(
            company=self.company, technicien=self.tech, date_debut=milieu,
            date_fin=milieu, type_indispo='conge')
        resp = self.api.post(f'{BASE}/interventions/suggerer-creneau/', {
            'chantier': self.inst.id, 'type_intervention': 'pose',
            'duree_jours': 10, 'date_cible': debut.isoformat(),
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        # Tout départ de moins de 5 jours avant le congé porte un bloc de 10
        # jours ouvrés qui le recouvre : jamais proposé.
        interdits = {(milieu - timedelta(days=k)).isoformat()
                     for k in range(5)}
        proposes = {prop['date'] for prop in resp.data['propositions']}
        self.assertFalse(proposes & interdits, proposes & interdits)


class TestReplanificationMasseEnLot(TestCase):
    """APRF41 (C-APRF-023) — la replanification en masse charge les ressources
    de la fenêtre UNE fois pour le lot (`suggerer_creneaux_lot`) : 2 puis 6
    interventions à replanifier coûtent le même nombre de requêtes, chaque
    proposition est égale à celle de `suggerer_creneau` unitaire, et `appliquer`
    écrit le créneau proposé."""

    def setUp(self):
        self.company = make_company()
        self.jour = date.today() + timedelta(days=3)
        self.absent = make_user(self.company, role='technicien')
        self.libres = [make_user(self.company, role='technicien') for _ in range(3)]
        self.inst = Installation.objects.create(
            company=self.company, reference='APRF41-0', statut=Installation.Statut.EN_COURS)
        # Techniciens libres « éligibles » (déjà affectés), charges variées,
        # hors du jour à replanifier.
        for k, tech in enumerate(self.libres):
            for d in range(k + 1):
                self._interv(self.inst, tech, self.jour + timedelta(days=5 + d))
        IndisponibiliteRessource.objects.create(
            company=self.company, technicien=self.libres[0],
            date_debut=date.today() + timedelta(days=1), date_fin=date.today() + timedelta(days=2))
        self.n = 0

    def _interv(self, inst, tech, jour):
        return Intervention.objects.create(
            company=self.company, installation=inst, type_intervention=Intervention.Type.POSE,
            statut=Intervention.Statut.PRETE, technicien=tech, date_prevue=jour)

    def _a_replanifier(self, nb):
        for _ in range(nb):
            self.n += 1
            inst = Installation.objects.create(
                company=self.company, reference=f'APRF41-{self.n}', statut=Installation.Statut.EN_COURS)
            self._interv(inst, self.absent, self.jour)

    def _apercu(self):
        with CaptureQueriesContext(connection) as ctx:
            res = services.previsualiser_replanification_masse(
                self.company, jour=self.jour, technicien_id=self.absent.id)
        return len(ctx.captured_queries), res

    def test_apercu_requetes_identiques_a_deux_tailles(self):
        self._a_replanifier(2)
        n2, res2 = self._apercu()
        self._a_replanifier(4)
        n6, res6 = self._apercu()
        self.assertEqual((len(res2['propositions']), len(res6['propositions'])), (2, 6))
        self.assertEqual(n2, n6, (n2, n6))

    def test_lot_egal_a_l_unitaire(self):
        self._a_replanifier(3)
        chantiers = list(Installation.objects.filter(company=self.company).values_list('id', flat=True))
        lot = suggerer_creneaux_lot(self.company, chantiers, n=10)
        for cid in chantiers:
            unitaire = selectors.suggerer_creneau(
                self.company, chantier_id=cid, type_intervention=Intervention.Type.POSE, n=10)
            self.assertEqual(lot[cid], unitaire, cid)
            self.assertTrue(lot[cid]['propositions'], cid)
        conge = {str(date.today() + timedelta(days=d)) for d in (1, 2)}
        for cid in chantiers:
            for p in lot[cid]['propositions']:
                if p['technicien_id'] == self.libres[0].id:
                    self.assertNotIn(p['date'], conge)

    def test_appliquer_persiste_le_creneau_choisi(self):
        self._a_replanifier(3)
        apercu = services.previsualiser_replanification_masse(
            self.company, jour=self.jour, technicien_id=self.absent.id)
        attendu = {p['intervention_id']: p['proposition'] for p in apercu['propositions']}
        res = services.appliquer_replanification_masse(
            self.company, jour=self.jour, motif='absence', user=self.libres[0],
            technicien_id=self.absent.id)
        self.assertEqual(len(res['deplacees']) + len(res['non_resolues']), 3)
        self.assertTrue(res['deplacees'])
        for d in res['deplacees']:
            iv = Intervention.objects.get(id=d['intervention_id'])
            prop = attendu[iv.id]
            self.assertEqual(iv.technicien_id, prop['technicien_id'])
            self.assertEqual(str(iv.date_prevue), prop['date'])
