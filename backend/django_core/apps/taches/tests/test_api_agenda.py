"""Agenda (reference/api.md §3.1, §4 `agenda/` ; échantillon `agenda.json`).

Avec base (CI). La route lit l'heure murale du serveur : les jours des tests sont relatifs à
aujourd'hui (`timezone.localdate()`), jamais une date figée qui vieillirait.
"""
import datetime
import json
from pathlib import Path

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.taches.tests import fabriques
from apps.taches.tests.test_api_saisie import champs

URL = '/api/django/taches/agenda/'


def exemple(nom):
    chemin = Path(__file__).resolve().parents[1] / 'contract_samples' / f'{nom}.json'
    return json.loads(chemin.read_text(encoding='utf-8'))['exemple']


CLES_ITEM = set(exemple('item'))


class AgendaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.societe = fabriques.societe('a')
        cls.u = fabriques.compte(cls.societe, nom='u1')
        cls.projet = fabriques.projet(cls.u, nom='Équipe', priorite=3)

    def setUp(self):
        self.T = timezone.localdate()
        self.client_ = APIClient()
        self.client_.force_authenticate(self.u)

    def jour(self, n):
        return self.T + datetime.timedelta(days=n)

    def tache(self, **champs):
        champs.setdefault('projet', self.projet)
        return fabriques.tache(self.u, **champs)

    def get(self, statut=200, **params):
        reponse = self.client_.get(URL, params)
        self.assertEqual(reponse.status_code, statut, reponse.content[:300])
        return reponse.json()

    def periode(self, **params):
        params.setdefault('du', self.T.isoformat())
        params.setdefault('au', self.jour(6).isoformat())
        return self.get(**params)

    def le_jour(self, rendu, jour):
        return next(j for j in rendu['jours'] if j['jour'] == jour.isoformat())

    def test_forme_de_l_echantillon(self):
        self.tache(jour_prevu=self.T, heure_debut=datetime.time(10, 0))
        self.tache(jour_prevu=self.T)
        self.tache(echeance=self.jour(1))
        self.tache()  # Mes projets
        rendu, modele = self.periode(vue='semaine'), exemple('agenda')
        self.assertEqual(set(rendu), set(modele))
        self.assertEqual(len(rendu['jours']), 7)
        jour = self.le_jour(rendu, self.T)
        self.assertEqual(set(jour), set(modele['jours'][0]))
        for liste in ('sans_heure', 'blocs'):
            self.assertEqual(set(jour[liste][0]), CLES_ITEM)
        self.assertEqual(set(rendu['mes_projets'][0]), set(modele['mes_projets'][0]))
        self.assertEqual(set(rendu['mes_projets'][0]['items'][0]), CLES_ITEM)

    def test_blocs_sans_heure_echeances(self):
        a_onze = self.tache(jour_prevu=self.T, heure_debut=datetime.time(11, 0))
        a_neuf = self.tache(jour_prevu=self.T, heure_debut=datetime.time(9, 0))
        sans = self.tache(jour_prevu=self.T)
        echeance = self.tache(echeance=self.jour(2))
        rendu = self.periode()
        jour = self.le_jour(rendu, self.T)
        self.assertEqual([i['id'] for i in jour['blocs']], [a_neuf.pk, a_onze.pk])
        self.assertEqual([i['id'] for i in jour['sans_heure']], [sans.pk])
        self.assertEqual([i['id'] for i in self.le_jour(rendu, self.jour(2))['echeances']], [echeance.pk])

    def test_42_jours_au_plus(self):
        self.periode(au=self.jour(41).isoformat())
        rendu = self.periode(statut=400, au=self.jour(42).isoformat())
        self.assertEqual(champs(rendu), {'au': ['42 jours au plus.']})

    def test_vue_inconnue_400(self):
        self.assertIn('vue', self.get(statut=400, vue='annee'))

    def test_mes_projets_en_vue_semaine_seulement(self):
        self.tache()
        self.assertEqual(self.periode(vue='jour', au=self.T.isoformat())['mes_projets'], [])
        groupes = self.periode(vue='semaine')['mes_projets']
        self.assertEqual(groupes[0]['projet']['id'], self.projet.pk)
        self.assertEqual(groupes[0]['items'][0]['raison']['code'], 'prochaine_action')

    def test_a_placer_du_jour_sans_heure_et_a_revoir(self):
        sans = self.tache(jour_prevu=self.T)
        self.tache(jour_prevu=self.T, heure_debut=datetime.time(9, 0))
        a_revoir = self.tache(jour_prevu=self.jour(-9))
        ids = [i['id'] for i in self.periode()['a_placer']]
        self.assertEqual(ids, [sans.pk, a_revoir.pk])

    def test_projet_d_un_autre_404(self):
        autre = fabriques.compte(self.societe, nom='u2')
        self.periode(statut=404, projet=str(fabriques.projet(autre).pk))

    def test_filtre_par_projet(self):
        autre_projet = fabriques.projet(self.u, nom='Maison')
        dedans = self.tache(jour_prevu=self.T)
        self.tache(projet=autre_projet, jour_prevu=self.T)
        jour = self.le_jour(self.periode(projet=str(self.projet.pk)), self.T)
        self.assertEqual([i['id'] for i in jour['sans_heure']], [dedans.pk])

    def test_rendez_vous_externes_vides_sans_agenda(self):
        self.assertTrue(all(j['externes'] == [] for j in self.periode()['jours']))

    def test_jamais_les_taches_d_un_autre(self):
        autre = fabriques.compte(fabriques.societe('b'), nom='u1')
        fabriques.tache(autre, projet=fabriques.projet(autre), jour_prevu=self.T)
        self.assertEqual(self.le_jour(self.periode(), self.T)['sans_heure'], [])
