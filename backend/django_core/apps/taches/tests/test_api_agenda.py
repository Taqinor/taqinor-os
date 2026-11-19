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

    def test_capacite_du_jour_servie(self):
        self.assertEqual(self.periode()['capacite'], {'minutes': 240, 'source': 'defaut'})
        self.client_.post('/api/django/taches/preferences/', {'cle': 'capacite_jour_min', 'valeur': 300},
                          format='json')
        self.assertEqual(self.periode()['capacite']['minutes'], 300)

    def test_42_jours_au_plus(self):
        self.periode(au=self.jour(41).isoformat())
        rendu = self.periode(statut=400, au=self.jour(42).isoformat())
        self.assertEqual(champs(rendu), {'au': ['42 jours au plus.']})

    def test_vue_inconnue_400(self):
        self.assertIn('vue', self.get(statut=400, vue='annee'))

    def test_mes_projets_en_vue_jour_et_semaine_le_meme_volet(self):
        """Le volet « À placer » est le MÊME en vue Jour et en vue Semaine (maquettes `agenda-jour.html` et
        `agenda-semaine.html` : « À placer · 12 » dans les deux ; SCENARIO §4) : « Mes projets » y est servi
        dans les deux vues, jamais en Mois ni À venir (pas de volet)."""
        self.tache()
        jour = self.periode(vue='jour', au=self.T.isoformat())['mes_projets']
        semaine = self.periode(vue='semaine')['mes_projets']
        self.assertEqual(jour, semaine)
        self.assertEqual(semaine[0]['projet']['id'], self.projet.pk)
        self.assertEqual(semaine[0]['items'][0]['raison']['code'], 'prochaine_action')
        self.assertEqual(self.get(vue='mois')['mes_projets'], [])
        self.assertEqual(self.get(vue='a-venir')['mes_projets'], [])

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

    def test_rendez_vous_minutes_par_jour(self):
        """R2-100 — chaque jour sert `rendez_vous_minutes` (durée des rendez-vous horodatés, invariant 35) : le
        front retranche cette durée de la capacité, il ne la devine pas. La journée entière vaut 0."""
        from unittest import mock

        from apps.taches.moteur.ics import RendezVousPur
        from apps.taches.selectors import journee as sel
        jour_t = datetime.datetime.combine(self.T, datetime.time(0, 0))
        rdv = RendezVousPur('2-x', 2, 'Réunion banque', jour_t.replace(hour=11), jour_t.replace(hour=12), False)
        entiere = RendezVousPur('2-y', 2, 'Congé', jour_t + datetime.timedelta(days=2),
                                jour_t + datetime.timedelta(days=3), True)
        with mock.patch.object(sel, 'rendez_vous_pour', return_value=((rdv, entiere), {2: 'Microsoft 365'})):
            rendu = self.periode()
        self.assertEqual(self.le_jour(rendu, self.T)['rendez_vous_minutes'], 60)
        self.assertEqual(self.le_jour(rendu, self.jour(2))['rendez_vous_minutes'], 0)
        self.assertEqual(self.le_jour(rendu, self.jour(1))['rendez_vous_minutes'], 0)

    def test_faites_nb_finies_ce_jour_la(self):
        """R2-102 (règle C-12) — « faites » un jour = les tâches PASSÉES à `fait` CE jour-là (prévues ce jour-là ou
        non), comptées comme Mon rythme : une sous-tâche vaut 0, une ouverte ne compte pas, un jour à venir dit 0."""
        from apps.taches.choix import StatutTache

        def a(jour, heure=10):
            return timezone.make_aware(datetime.datetime.combine(jour, datetime.time(heure, 0)))

        hier, avant, demain = self.jour(-1), self.jour(-2), self.jour(1)
        self.tache(jour_prevu=avant, statut=StatutTache.FAIT, fait_le=a(hier))  # prévue avant-hier, finie hier
        self.tache(jour_prevu=hier, statut=StatutTache.FAIT, fait_le=a(hier, 15))
        parent = self.tache(jour_prevu=hier)
        self.tache(parent=parent, statut=StatutTache.FAIT, fait_le=a(hier, 16))  # sous-tâche : 0
        self.tache(jour_prevu=self.T, statut=StatutTache.FAIT, fait_le=a(self.T, 9))
        rendu = self.get(du=avant.isoformat(), au=demain.isoformat())
        faites = {j['jour']: j['faites_nb'] for j in rendu['jours']}
        self.assertEqual(faites, {avant.isoformat(): 0, hier.isoformat(): 2, self.T.isoformat(): 1,
                                  demain.isoformat(): 0})

    def test_toute_la_journee_sans_la_ligne_des_relances(self):
        """« Toute la journée » = les éléments de l'ERP sans heure (visites, poses, interventions) ; « Suivi des
        relances » est une ligne de Prévu d'Aujourd'hui, jamais une bande d'agenda (textes.md §2, SCENARIO §4)."""
        from unittest import mock

        from apps.taches.selectors import journee as sel
        visite = {'famille': 'visite', 'id': 7, 'titre': 'Visite — Témara', 'jour': self.T.isoformat(),
                  'url': '/visites'}
        touches = {'famille': 'touches', 'id': None, 'titre': 'Suivi des relances', 'jour': self.T.isoformat(),
                   'url': '/crm/relances', 'nb': 5, 'en_retard': 0}
        with mock.patch.object(sel, 'obligations_du_jour', return_value=sel.Obligations(lignes=(visite, touches))):
            rendu = self.periode(vue='semaine')
        self.assertEqual(self.le_jour(rendu, self.T)['toute_la_journee'], [visite])
        self.assertTrue(all(j['toute_la_journee'] == [] for j in rendu['jours'] if j['jour'] != self.T.isoformat()))

    def test_jamais_les_taches_d_un_autre(self):
        autre = fabriques.compte(fabriques.societe('b'), nom='u1')
        fabriques.tache(autre, projet=fabriques.projet(autre), jour_prevu=self.T)
        self.assertEqual(self.le_jour(self.periode(), self.T)['sans_heure'], [])
