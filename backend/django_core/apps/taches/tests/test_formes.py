"""TCH14 — formes partagées (`serializers/formes.py`) contre leurs échantillons de contrat.

`TachesChargeesContreEchantillonsTests` (TestCase, CI) : des lignes posées par les fabriques aux
identifiants de l'annexe A, chargées par le VRAI chemin (`charger_items` / `charger_taches`),
rendent EXACTEMENT l'`exemple` de `item.json`, `tache.json`, `tache_ecrite.json` — clés, ordre et
valeurs. `FormesContreEchantillonsTests` (SimpleTestCase, sans base) : les formes qui ne lisent
aucune relation (`projet.json`, `proposition.json`, `rendez_vous.json`, LIEN, activité ERP), sur des
objets en mémoire — jamais de cache de préchargement fabriqué à la main (nplusone, actif en CI,
attend un QuerySet). `ChargementTests` (TestCase, CI) : le rendu d'une liste ne coûte pas une
requête par ligne.
"""
import datetime
import json
import re
from pathlib import Path
from zoneinfo import ZoneInfo

from django.contrib.contenttypes.models import ContentType
from django.db import connection
from django.test import SimpleTestCase, TestCase
from django.test.utils import CaptureQueriesContext

from apps.records.models import Activity
from apps.taches.models.projets import Projet
from apps.taches.models.rythme import IncitationCoach
from apps.taches.models.taches import ElementChecklist, Etiquette, EtiquetteTache, Rappel, Tache
from apps.taches.moteur.ics import RendezVousPur
from apps.taches.selectors.base import taches_de
from apps.taches.serializers import formes
from apps.taches.tests import fabriques

ECHANTILLONS = Path(__file__).resolve().parent.parent / 'contract_samples'
CASABLANCA = ZoneInfo('Africa/Casablanca')
J = datetime.date(2026, 11, 17)


#: Un instant ISO 8601 (« 2026-11-16T18:02:00+01:00 », « …Z »).
_INSTANT = re.compile(r'^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(\.\d+)?(Z|[+-]\d{2}:\d{2})$')


def exemple(nom):
    return json.loads((ECHANTILLONS / f'{nom}.json').read_text(encoding='utf-8'))['exemple']


def heure_murale(valeur):
    """`valeur` (JSON) où chaque instant est ramené à son heure MURALE (décalage retiré).

    Les échantillons portent « +01:00 » ; or le Maroc est repassé à UTC+0 le 20/09/2026
    (requirements.txt, `tzdata` épinglé) : le serveur rend la même heure murale avec « Z ».
    Les dates et heures sont murales (invariant 14) : c'est elle qui est comparée."""
    if isinstance(valeur, dict):
        return {cle: heure_murale(v) for cle, v in valeur.items()}
    if isinstance(valeur, list):
        return [heure_murale(v) for v in valeur]
    if isinstance(valeur, str) and _INSTANT.match(valeur):
        return _INSTANT.match(valeur).group(1)
    return valeur


def rendu_json(donnees):
    return heure_murale(json.loads(json.dumps(donnees)))


def instant(jour, heure, minute):
    return datetime.datetime(2026, *jour, heure, minute, tzinfo=CASABLANCA)


def projet_ventes():
    return Projet(
        pk=3, nom='Ventes', objectif='Fini quand les 4 devis sont signés', icone='', couleur='vert',
        priorite=3, statut='actif', statut_depuis=instant((10, 1), 9, 0), domaine='',
        date_debut=None, echeance=datetime.date(2026, 12, 15), termine_le=None, issue='', bilan='',
        planification_le=instant((10, 1), 9, 5), rang=2048, confidentiel=False,
        affichage={'vue': 'liste', 'tri': 'manuel', 'groupe': 'section', 'montrer_faites': False},
        updated_at=instant((11, 16), 18, 0), lock_version=4)


def tache_liee_en_memoire():
    """La tâche 20 de l'annexe A réduite à son lien (LIEN ne lit aucune relation préchargée)."""
    return Tache(pk=20, titre='Devis Settat', content_type=ContentType(pk=901, app_label='ventes', model='devis'),
                 object_id=512, lien_libelle='DEV-2026-11-0042', lien_etat='ok')


CALCULS_SETTAT = {
    ('tache', 20): {'explication': 'échéance jeu. 19 (1 jour travaillé) · projet prioritaire Ventes',
                    'essentielle': True, 'prevue_au_plan': True},
    ('tache', 22): {'explication': 'dans Ventes'},
}


class TachesChargeesContreEchantillonsTests(TestCase):
    """La tâche 20 de l'annexe A, son enfant 22, son rappel 31, son point de check-list 71, son
    étiquette 2, dans le projet 3 : posés par les fabriques, relus par `charger_taches`."""

    @classmethod
    def setUpTestData(cls):
        cls.compte = fabriques.compte(fabriques.societe('formes'))
        projet = fabriques.projet(cls.compte, pk=3, nom='Ventes', couleur='vert', priorite=3)
        tache = fabriques.tache(
            cls.compte, projet=projet, pk=20, titre='Devis Settat', priorite=2, jour_prevu=J,
            moment='matin', heure_debut=datetime.time(10, 0), echeance=datetime.date(2026, 11, 19),
            estimation_minutes=60, rang_projet=1024, source='rapide', notes='Appeler avant 11 h.',
            content_type=ContentType.objects.get_by_natural_key('ventes', 'devis'), object_id=512,
            lien_libelle='DEV-2026-11-0042', lien_etat='ok', triee_le=instant((11, 16), 18, 2),
            premier_jour_prevu=J, lien_verifie_le=instant((11, 17), 9, 12))
        fabriques.tache(cls.compte, projet=projet, parent=tache, pk=22, titre='Relire les quantités',
                        rang_projet=1024, source='rapide')
        Rappel.objects.create(pk=31, company=tache.company, proprietaire=cls.compte, tache=tache,
                              jour=J, heure=datetime.time(9, 45))
        ElementChecklist.objects.create(pk=71, company=tache.company, tache=tache, libelle='Prix',
                                        fait=True, rang=1024)
        magasin = Etiquette.objects.create(pk=2, company=tache.company, proprietaire=cls.compte,
                                           nom='magasin', couleur='ciel')
        EtiquetteTache.objects.create(company=tache.company, tache=tache, etiquette=magasin)
        # `lock_version` et les horodatages auto de l'annexe A (un `update()` ne les recalcule pas).
        Tache.objects.filter(pk=20).update(
            lock_version=4, created_at=instant((11, 16), 18, 2), updated_at=instant((11, 17), 10, 42))

    def setUp(self):
        self.contexte = formes.contexte(calculs=CALCULS_SETTAT)

    def _tache(self, charger=formes.charger_taches):
        return charger(taches_de(self.compte).filter(pk=20)).get()

    def test_tache_rend_exactement_tache_json(self):
        rendu = formes.TacheSerializer(self._tache(), context=self.contexte).data
        self.assertEqual(list(rendu), list(exemple('tache')))
        self.assertEqual(rendu_json(rendu), heure_murale(exemple('tache')))

    def test_item_d_une_tache_a_les_cles_d_item_json(self):
        rendu = formes.ItemSerializer(self._tache(formes.charger_items), context=self.contexte).data
        self.assertEqual(list(rendu), list(exemple('item')))
        attendu = {**exemple('item'), 'rappel': {'jour': '2026-11-17', 'heure': '09:45'},
                   'lien': exemple('tache')['lien'], 'checklist': {'faits': 1, 'total': 1},
                   'sous_taches': {'faites': 0, 'total': 1}}
        self.assertEqual(rendu_json(rendu), heure_murale(attendu))

    def test_tache_ecrite_rend_exactement_tache_ecrite_json(self):
        instance = formes.tache_ecrite(
            self._tache(), avertissements=[{'code': 'prevue_apres_echeance', 'message': "Prévue après l'échéance."}],
            progression=exemple('tache_ecrite')['progression'], geste_id=77)
        rendu = formes.TacheEcriteSerializer(instance, context=self.contexte).data
        self.assertEqual(list(rendu), list(exemple('tache_ecrite')))
        self.assertEqual(rendu_json(rendu), heure_murale(exemple('tache_ecrite')))

    def test_assistant_ni_notes_ni_titre_confidentiel(self):
        Projet.objects.filter(pk=3).update(confidentiel=True)
        rendu = formes.TacheSerializer(self._tache(), context=formes.contexte(assistant=True)).data
        self.assertEqual(rendu['notes'], '')
        self.assertEqual(rendu['titre'], 'Tâche confidentielle')
        self.assertEqual(rendu['projet']['nom'], 'Projet confidentiel')
        self.assertTrue(rendu['confidentielle'])
        self.assertNotIn('Devis Settat', json.dumps(rendu, ensure_ascii=False))
        self.assertNotIn('Ventes', json.dumps(rendu, ensure_ascii=False))


class FormesContreEchantillonsTests(SimpleTestCase):
    def setUp(self):
        self.projet = projet_ventes()
        self.tache = tache_liee_en_memoire()

    def test_item_d_une_activite_rend_la_ligne_activite_d_aujourdhui(self):
        attendu = next(i for i in exemple('aujourdhui')['journee'] if i['type'] == 'activite')
        activite = Activity(pk=101, summary='Rappeler Benali', due_date=J, done=False, object_id=1637,
                            content_type=ContentType(pk=902, app_label='crm', model='lead'))
        contexte = formes.contexte(calculs={('activite', 101): {
            'explication': 'activité ERP du jour', 'prevue_au_plan': True, 'lien_libelle': 'Karim Benali'}})
        rendu = formes.ItemSerializer(activite, context=contexte).data
        self.assertEqual(list(rendu), list(exemple('item')))
        self.assertEqual(rendu_json(rendu), heure_murale(attendu))

    def test_projet_rend_exactement_projet_json(self):
        contexte = formes.contexte(calculs={('projet', 3): {
            'a_planifier': False, 'compteurs': {'ouvertes': 8, 'faites': 12}, 'focus_semaine': False,
            'sante': [{'code': 'a_l_arret', 'phrase': 'Rien de fait depuis 10 jours travaillés.',
                       'donnees': {'jours': 10, 'depuis': '2026-11-03'}}]}})
        rendu = formes.ProjetSerializer(self.projet, context=contexte).data
        self.assertEqual(list(rendu), list(exemple('projet')))
        self.assertEqual(rendu_json(rendu), heure_murale(exemple('projet')))

    def test_proposition_rend_exactement_proposition_json(self):
        carte = IncitationCoach(pk=41, type='proposition_palier', cle='monter',
                                donnees={'N': 5, 'N1': 6, 'tenus': 7}, expire_le=datetime.date(2026, 11, 24))
        contexte = formes.contexte(calculs={('proposition', 41): {
            'texte': exemple('proposition')['texte'],
            'boutons': [('Monter à 6', 'oui'), ('Pas maintenant', 'pas_maintenant')]}})
        rendu = formes.PropositionSerializer(carte, context=contexte).data
        self.assertEqual(rendu_json(rendu), exemple('proposition'))

    def test_rendez_vous_rend_exactement_rendez_vous_json(self):
        rdv = RendezVousPur('2-9f2c1a7b', 2, 'Réunion banque', datetime.datetime(2026, 11, 17, 11, 0),
                            datetime.datetime(2026, 11, 17, 12, 0), False)
        rendu = formes.RendezVousSerializer(rdv, context=formes.contexte(agendas={2: 'Microsoft 365'})).data
        self.assertEqual(rendu_json(rendu), heure_murale(exemple('rendez_vous')['results'][0]))

    def test_lien_a_les_cles_de_la_forme_lien(self):
        self.assertEqual(list(formes.LienSerializer().fields), list(exemple('tache')['lien']))
        self.assertEqual(formes.lien_de_tache(self.tache), exemple('tache')['lien'])

    def test_lien_hors_etat_ok_sans_libelle_ni_adresse(self):
        self.tache.lien_etat = 'inaccessible'
        self.assertEqual(formes.lien_de_tache(self.tache),
                         {'cible': 'ventes.devis', 'id': 512, 'libelle': '', 'url': None, 'etat': 'inaccessible'})
        self.tache.lien_etat = 'efface'
        self.assertEqual(formes.lien_de_tache(self.tache)['libelle'], 'Lead effacé')

    def test_rendez_vous_titre_neutre_pour_l_assistant(self):
        rdv = RendezVousPur('2-x', 2, 'Médecin', datetime.datetime(2026, 11, 17, 11, 0),
                            datetime.datetime(2026, 11, 17, 12, 0), False)
        rendu = formes.RendezVousSerializer(rdv, context=formes.contexte(assistant=True)).data
        self.assertEqual(rendu['titre'], 'Rendez-vous')

    def test_chaque_forme_nommee(self):
        self.assertEqual(set(formes.FORMES), {'ITEM', 'TACHE', 'TACHE_ECRITE', 'PROJET', 'PROPOSITION',
                                              'LIEN', 'RENDEZ_VOUS', 'PROGRESSION'})
        self.assertEqual(list(formes.ProgressionSerializer().fields),
                         list(exemple('tache_recurrente_ecrite')['progression']))


class ChargementTests(TestCase):
    """Rendre 1 ou 4 tâches coûte le même nombre de requêtes (préchargement, jamais par ligne)."""

    @classmethod
    def setUpTestData(cls):
        cls.compte = fabriques.compte(fabriques.societe('a'))
        projet = fabriques.projet(cls.compte)
        for _ in range(4):
            parent = fabriques.tache(cls.compte, projet=projet)
            fabriques.tache(cls.compte, projet=projet, parent=parent)
            ElementChecklist.objects.create(company=parent.company, tache=parent, libelle='x')
            Rappel.objects.create(company=parent.company, proprietaire=cls.compte, tache=parent,
                                  jour=J, heure=datetime.time(9, 0))

    def _requetes(self, n):
        qs = formes.charger_taches(taches_de(self.compte).filter(parent__isnull=True))[:n]
        with CaptureQueriesContext(connection) as capture:
            formes.TacheSerializer(list(qs), many=True, context=formes.contexte()).data
        return len(capture)

    def test_aucune_requete_par_ligne(self):
        self.assertEqual(self._requetes(1), self._requetes(4))


#: Chaque texte d'une tâche et d'un projet confidentiels (regles.md §8, test canari des formes).
CANARIS = ('Canari-titre', 'Canari-notes', 'Canari-attente', 'Canari-lien', 'Canari-étape',
           'Canari-point', 'Canari-étiq', 'Canari-enfant', 'Canari-sous-attente', 'Canari-projet',
           'Canari-objectif', 'Canari-dom', 'Canari-iss', 'Canari-bilan')


class CanariFormesTests(TestCase):
    """M1 — tâche et projet confidentiels portant « Canari » dans tout leur contenu, chargés par
    `charger_taches` : sous l'en-tête assistant, aucune forme n'en sert un mot ; à l'écran, chacun
    est servi (preuve que le canari est vivant)."""

    @classmethod
    def setUpTestData(cls):
        cls.compte = fabriques.compte(fabriques.societe('canari'))
        projet = fabriques.projet(
            cls.compte, nom='Canari-projet', objectif='Canari-objectif', domaine='Canari-dom',
            issue='Canari-iss', bilan='Canari-bilan', confidentiel=True)
        tache = fabriques.tache(
            cls.compte, projet=projet, section=fabriques.section(projet, nom='Canari-étape'),
            titre='Canari-titre', notes='Canari-notes', en_attente_de='Canari-attente',
            content_type=ContentType.objects.get_by_natural_key('ventes', 'devis'), object_id=512,
            lien_libelle='Canari-lien', lien_etat='ok')
        fabriques.tache(cls.compte, projet=projet, parent=tache, titre='Canari-enfant',
                        en_attente_de='Canari-sous-attente')
        ElementChecklist.objects.create(company=tache.company, tache=tache, libelle='Canari-point')
        etiquette = Etiquette.objects.create(company=tache.company, proprietaire=cls.compte, nom='Canari-étiq')
        EtiquetteTache.objects.create(company=tache.company, tache=tache, etiquette=etiquette)
        cls.tache_id = tache.pk

    def _rendus(self, assistant):
        tache = formes.charger_taches(taches_de(self.compte).filter(pk=self.tache_id)).get()
        contexte = formes.contexte(assistant=assistant)
        return {
            'tache': formes.TacheSerializer(tache, context=contexte).data,
            'item': formes.ItemSerializer(tache, context=contexte).data,
            'tache_ecrite': formes.TacheEcriteSerializer(formes.tache_ecrite(tache), context=contexte).data,
            'projet': formes.ProjetSerializer(tache.projet, context=contexte).data,
        }

    def test_assistant_aucun_canari(self):
        texte = json.dumps(self._rendus(True), ensure_ascii=False).lower()
        self.assertNotIn('canari', texte)

    def test_ecran_sert_chaque_canari(self):
        texte = json.dumps(self._rendus(False), ensure_ascii=False)
        for canari in CANARIS:
            self.assertIn(canari, texte)

    def test_assistant_garde_les_champs_declares(self):
        rendus = self._rendus(True)
        tache = rendus['tache']
        self.assertEqual(list(tache), list(formes.TacheSerializer().fields))
        self.assertEqual(list(rendus['projet']), list(formes.ProjetSerializer().fields))
        self.assertEqual(tache['elements_checklist'], [])
        self.assertEqual(tache['checklist'], {'faits': 0, 'total': 1})
        self.assertEqual(tache['etiquettes'], [])
        self.assertIsNone(tache['lien'])
        self.assertEqual(tache['section']['nom'], '')
        self.assertEqual(tache['en_attente_de'], '')
        self.assertEqual(tache['enfants'][0]['en_attente_de'], '')
        for champ in formes.TEXTES_PROJET:
            self.assertEqual(rendus['projet'][champ], '')
