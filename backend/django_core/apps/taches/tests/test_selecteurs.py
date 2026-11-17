"""TCH12 — sélecteur unique : société ET propriétaire, jours travaillés, recherche `filtrer_q`.

Base requise (`TestCase`) : joué par la CI. Deux sociétés réelles (`'a'`, `'b'`), des comptes dans
chacune ; une ligne posée dans la société B au nom d'un compte de A prouve que le filtre de société
ne dépend pas du seul propriétaire.
"""
import datetime
from unittest import mock

from django.test import TestCase

from apps.notifications.models import Holiday
from apps.taches.confidentialite import est_confidentielle
from apps.taches.models.gestes import GesteAnnulable
from apps.taches.models.rythme import Preference
from apps.taches.models.taches import Etiquette, EtiquetteTache, Rappel, Tache
from apps.taches.selectors.base import (
    TACHE_CONFIDENTIELLE,
    etiquettes_de,
    filtrer_q,
    gestes_de,
    jours_travailles_de,
    prochain_jour_travaille,
    projets_de,
    rappels_de,
    sections_de,
    taches_de,
)
from apps.taches.tests import fabriques

J = datetime.date(2026, 11, 17)  # mardi ; le 18 est férié pour la société A


def _jours(*numeros):
    return {datetime.date(2026, 11, n) for n in numeros}


class IsolementTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.a, cls.b = fabriques.societe('a'), fabriques.societe('b')
        cls.u1 = fabriques.compte(cls.a, nom='u1')
        cls.voisin = fabriques.compte(cls.a, nom='u2')
        cls.ailleurs = fabriques.compte(cls.b, nom='u1')

    def test_taches_de_filtre_societe_et_proprietaire(self):
        mienne = fabriques.tache(self.u1)
        fabriques.tache(self.voisin)
        fabriques.tache(self.ailleurs)
        Tache.objects.create(company=self.b, proprietaire=self.u1, titre='Ligne hors de ma société')
        self.assertEqual(list(taches_de(self.u1)), [mienne])

    def test_taches_supprimees_exclues(self):
        tache = fabriques.tache(self.u1)
        tache.soft_delete(self.u1, record=False)
        self.assertFalse(taches_de(self.u1).exists())

    def test_jumeaux_filtrent_pareil(self):
        projet = fabriques.projet(self.u1)
        section = fabriques.section(projet)
        tache = fabriques.tache(self.u1, projet=projet)
        etiquette = Etiquette.objects.create(company=self.a, proprietaire=self.u1, nom='urgent')
        rappel = Rappel.objects.create(company=self.a, proprietaire=self.u1, tache=tache, jour=J,
                                       heure=datetime.time(9, 0))
        geste = GesteAnnulable.objects.create(company=self.a, proprietaire=self.u1, type='creation', message='m')
        fabriques.section(fabriques.projet(self.voisin))
        fabriques.projet(self.ailleurs)
        Etiquette.objects.create(company=self.b, proprietaire=self.u1, nom='hors société')
        self.assertEqual(list(projets_de(self.u1)), [projet])
        self.assertEqual(list(sections_de(self.u1)), [section])
        self.assertEqual(list(etiquettes_de(self.u1)), [etiquette])
        self.assertEqual(list(rappels_de(self.u1)), [rappel])
        self.assertEqual(list(gestes_de(self.u1)), [geste])
        projet.soft_delete(self.u1, record=False)
        self.assertFalse(sections_de(self.u1).exists())

    def test_compte_sans_societe_ne_lit_rien(self):
        fabriques.tache(self.u1)
        self.u1.company = None
        self.assertFalse(taches_de(self.u1).exists())
        self.assertEqual(jours_travailles_de(self.u1, J, J), set())


class JoursTravaillesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.a, cls.b = fabriques.societe('a'), fabriques.societe('b')
        Holiday.objects.create(company=cls.a, date=datetime.date(2026, 11, 18), nom='Indépendance')
        cls.u1 = fabriques.compte(cls.a, nom='u1')
        cls.u2 = fabriques.compte(cls.b, nom='u2')

    def _dire(self, compte, cle, valeur):
        Preference.objects.create(company=compte.company, proprietaire=compte, cle=cle, valeur=valeur)

    def test_calendrier_de_la_societe_par_defaut(self):
        du, au = datetime.date(2026, 11, 16), datetime.date(2026, 11, 22)
        self.assertEqual(jours_travailles_de(self.u1, du, au), _jours(16, 17, 19, 20))
        self.assertEqual(jours_travailles_de(self.u2, du, au), _jours(16, 17, 18, 19, 20))

    def test_masque_et_conges_retires(self):
        self._dire(self.u1, 'jours_travailles', '1111000')  # lundi → jeudi
        self._dire(self.u1, 'conges', [{'du': '2026-11-23', 'au': '2026-11-24'}])
        du, au = datetime.date(2026, 11, 16), datetime.date(2026, 11, 27)
        self.assertEqual(jours_travailles_de(self.u1, du, au), _jours(16, 17, 19, 25, 26))
        self.assertEqual(jours_travailles_de(self.u2, du, au), _jours(16, 17, 18, 19, 20, 23, 24, 25, 26, 27))

    def test_prochain_jour_travaille_strictement_apres(self):
        self.assertEqual(prochain_jour_travaille(self.u1, J), datetime.date(2026, 11, 19))
        self._dire(self.u1, 'jours_travailles', '1111000')
        self._dire(self.u1, 'conges', [{'du': '2026-11-23', 'au': '2026-11-24'}])
        self.assertEqual(prochain_jour_travaille(self.u1, datetime.date(2026, 11, 19)), datetime.date(2026, 11, 25))
        self.assertEqual(prochain_jour_travaille(self.u2, J), datetime.date(2026, 11, 18))

    def test_aucun_jour_travaille_dans_l_annee(self):
        self._dire(self.u1, 'conges', [{'du': '2026-01-01', 'au': '2028-01-01'}])
        self.assertIsNone(prochain_jour_travaille(self.u1, J))


class RechercheTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.a = fabriques.societe('a')
        cls.u1 = fabriques.compte(cls.a, nom='u1')
        secret = fabriques.projet(cls.u1, nom='Canari-7Q9', confidentiel=True)
        cls.canari = fabriques.tache(cls.u1, projet=secret, titre='Canari-X3K')
        cls.notaire = fabriques.tache(cls.u1, titre='Appeler le notaire', notes='dossier succession')
        cls.tache_client = fabriques.tache(cls.u1, titre='Appeler le client')
        cls.reunion = fabriques.tache(cls.u1, titre='Réunion équipe')
        etiquette = Etiquette.objects.create(company=cls.a, proprietaire=cls.u1, nom='Urgent')
        EtiquetteTache.objects.create(company=cls.a, tache=cls.tache_client, etiquette=etiquette)

    def _trouve(self, q, assistant=False):
        return set(filtrer_q(taches_de(self.u1), q, assistant=assistant))

    def test_confidentielle_introuvable_par_son_titre_sous_l_assistant(self):
        self.assertEqual(self._trouve('Canari'), {self.canari})
        self.assertEqual(self._trouve('Canari', assistant=True), set())
        self.assertEqual(self._trouve('x3k', assistant=True), set())

    def test_mots_en_et(self):
        self.assertEqual(self._trouve('appeler'), {self.notaire, self.tache_client})
        self.assertEqual(self._trouve('appeler notaire'), {self.notaire})

    def test_notes_jamais_lues_sous_l_assistant(self):
        self.assertEqual(self._trouve('succession'), {self.notaire})
        self.assertEqual(self._trouve('succession', assistant=True), set())

    def test_etiquettes_et_nom_de_projet(self):
        self.assertEqual(self._trouve('urgent'), {self.tache_client})
        self.assertEqual(self._trouve('7q9'), {self.canari})

    def test_q_vide_ne_filtre_rien(self):
        self.assertEqual(self._trouve('  '), {self.canari, self.notaire, self.tache_client, self.reunion})

    def test_avec_f_unaccent_la_requete_normalise_les_accents(self):
        # La disponibilité est simulée au point d'entrée interrogé par `filtrer_q` ; on lit le SQL
        # produit (jamais exécuté) : le test ne dépend pas de la présence de `public.f_unaccent`.
        with mock.patch('apps.stock.selectors.recherche_sans_accents_disponible', return_value=True):
            sql = str(filtrer_q(taches_de(self.u1), 'reunion').query)
        self.assertIn('f_unaccent', sql)

    def test_sans_f_unaccent_repli_sensible_aux_accents(self):
        with mock.patch('apps.stock.selectors.recherche_sans_accents_disponible', return_value=False):
            sql = str(filtrer_q(taches_de(self.u1), 'reunion').query)
            self.assertNotIn('f_unaccent', sql)
            self.assertEqual(self._trouve('RÉUNION équipe'), {self.reunion})
            self.assertEqual(self._trouve('reunion'), set())


class ConfidentialiteEnBaseTests(TestCase):
    """`TACHE_CONFIDENTIELLE` (requête) et `est_confidentielle` (Python) disent la même chose."""

    def test_les_deux_regles_concordent(self):
        a = fabriques.societe('a')
        u1 = fabriques.compte(a, nom='u1')
        secret, ouvert = fabriques.projet(u1, confidentiel=True), fabriques.projet(u1)
        parent_secret = fabriques.tache(u1, confidentiel=True)
        parent_dans_secret = fabriques.tache(u1, projet=secret)
        taches = [
            fabriques.tache(u1),
            fabriques.tache(u1, confidentiel=True),
            fabriques.tache(u1, projet=secret),
            fabriques.tache(u1, projet=ouvert),
            fabriques.tache(u1, parent=parent_secret),
            fabriques.tache(u1, parent=parent_dans_secret),
            parent_secret,
            parent_dans_secret,
        ]
        selon_la_base = set(taches_de(u1).filter(TACHE_CONFIDENTIELLE))
        lues = Tache.objects.select_related('projet', 'parent__projet').filter(pk__in=[t.pk for t in taches])
        self.assertEqual(selon_la_base, {t for t in lues if est_confidentielle(t)})
        self.assertEqual(len(selon_la_base), 6)
