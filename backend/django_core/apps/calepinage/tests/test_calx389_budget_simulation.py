"""CALX389 — le TEMPS de la chaîne de simulation, déclaré et gardé.

CE QUE CE FICHIER TIENT
-----------------------
``services/simulation.py::simuler_calepinage`` (CALX5) compose une dizaine de
producteurs : chaîne de pertes UNE PASSE PAR PAN, simulation module par module
(CALX182), charge, batterie, incertitude… Aucun test ne mesurait son coût :
une régression qui ferait passer la chaîne deux fois par pan, ou qui rendrait
le coût quadratique en nombre de pans, serait passée inaperçue jusqu'à la
première toiture de douze pans d'un client.

Ce fichier exécute la simulation RÉELLE sur 1, 4 et 12 pans et affirme :

1. **un plafond MESURÉ par taille** — le travail (passages dans la chaîne,
   points horaires traversés, séries météo demandées) ET le temps mur ;
2. **la LINÉARITÉ** : le temps PAR PAN ne croît pas d'un ordre de grandeur
   entre 1 et 12 pans ;
3. **aucun réseau** : la météo est une série horaire FIGÉE, committée
   (``fixtures/calx389_serie_pvgis.json``, réponse PVGIS réelle enregistrée),
   servie par un client double — aucun quota PVGIS consommé, aucune
   flakiness réseau ;
4. **la garde mord** : un doublement artificiel du coût par pan (la chaîne
   exécutée deux fois à chaque passage) fait rougir le budget.

POURQUOI DEUX MESURES, LE TRAVAIL ET LE TEMPS
----------------------------------------------
Le temps mur, seul, ne distingue pas « la chaîne coûte deux fois plus » de
« le runner CI est deux fois plus lent » — et ``release-verify`` (où tournent
les tests ``slow``) instrumente en plus la couverture, qui ralentit tout le
code Python. Un plafond de temps serré serait donc une garde qui rougit la
nuit sans régression. Le budget est donc tenu à deux étages :

* le TRAVAIL — nombre de passages dans ``appliquer_chaine``, points horaires
  traversés, séries demandées — est DÉTERMINISTE : son plafond est le relevé
  EXACT. Un doublement du coût par pan le fait rougir à coup sûr, sur toute
  machine ;
* le TEMPS mur garde l'ordre de grandeur (plafond = relevé × ``MARGE_TEMPS``)
  et la linéarité (rapport mesuré DANS le même processus, donc indépendant de
  la vitesse de la machine et de l'instrumentation).

LES RELEVÉS
-----------
Écrits avec leur date et leur poste, jamais devinés (``RELEVES``). Une
optimisation qui baisse le travail est bienvenue : relevez le plafond à la
baisse dans le même commit. Une hausse n'est jamais « ajustée » ici sans
comprendre d'où elle vient.

AUCUNE BASE, AUCUN RÉSEAU, AUCUNE ATTENTE (``scripts/check_test_determinism.py``
proscrit ``time.sleep``). ``@tag('slow')`` : le palier par-merge exclut ces
mesures ; elles tournent dans ``release-verify``.

Run :
    python manage.py test apps.calepinage.tests.test_calx389_budget_simulation -v2
"""
from __future__ import annotations

import copy
import datetime
import gc
import json
import pathlib
import time
from unittest import mock

from django.test import SimpleTestCase, tag

from apps.calepinage.services import chaine_pertes, pvgis_serie, simulation

FIXTURE = (pathlib.Path(__file__).resolve().parent / 'fixtures'
           / 'calx389_serie_pvgis.json')

#: L'instant FIGÉ de chaque calcul (``calcule_le``, validation) : aucune
#: horloge vive n'entre dans une affirmation.
MAINTENANT = datetime.datetime(2026, 9, 24, 8, 0,
                               tzinfo=datetime.timezone.utc)

#: Les fiches d'essai — les repères assumés de ``test_calx5_simulation``, plus
#: une NOCT pour que l'étape thermique CALCULE au lieu de s'omettre (aucune
#: installation réelle n'est décrite ; ce fichier mesure un coût, jamais un
#: chiffre de production). Un budget mesuré sur une chaîne dont toutes les
#: étapes s'omettent ne mesurerait que le coût des omissions.
MODULE = {
    'vmp_v': 41.5, 'voc_v': 49.6, 'isc_a': 18.4, 'imp_a': 17.1,
    'pmax_wc': 710.0, 'temp_coeff_voc_pct_c': -0.27,
    'temp_coeff_pmax_pct_c': -0.35, 'noct_c': 45.0,
}
ONDULEUR = {
    'n_mppt': 2, 'mppt_v_min': 150.0, 'mppt_v_max': 800.0,
    'v_max_abs': 1000.0, 'i_max_mppt_a': 26.0, 'ac_kw': 10.0, 'phases': 3,
}
MATERIEL = {
    'module': MODULE, 'onduleur': ONDULEUR, 'optimiseur': None,
    'designations': {'module': 'Module d essai',
                     'onduleur': 'Onduleur d essai', 'optimiseur': ''},
    'absents': (),
}

#: La provenance des réglages et des postes du cas : ce ne sont PAS des
#: valeurs par défaut du produit, ce sont ceux d'une société de TEST.
REFERENCE_CAS = ('Cas d’essai CALX389 — réglages de TEST, aucune valeur par '
                 'défaut du produit')

#: Les réglages SAISIS du cas (CALX145), chacun avec sa provenance. La fenêtre
#: est l'unique année que porte la réponse figée ; le fuseau du site (saisi,
#: jamais déduit) ouvre les étapes horaires (IAM, charge, autoconsommation).
REGLAGES = {
    'simulation': {
        'mode_meteo': {'valeur': 'pluriannuel', 'source': 'societe',
                       'reference': REFERENCE_CAS},
        'fenetre_annees': {'valeur': [2020, 2020], 'source': 'societe',
                           'reference': 'année de la réponse PVGIS figée'},
    },
    'imagerie': {'fuseau': 'Africa/Casablanca'},
    'norme_electrique': {},
    'electrique_societe': {},
}

#: L'épingle du site : le point de la requête PVGIS enregistrée (Casablanca).
EPINGLE = {'lat': 33.5, 'lng': -7.6}

#: Modules par pan, et les DEUX accès solaires distincts de chaque pan : la
#: simulation module par module (CALX182) calcule une passe par accès
#: distinct — c'est le cas réel d'un pan partiellement ombré.
MODULES_PAR_PAN = 12
ACCES_DU_PAN = [1.0] * 6 + [0.95] * 6

#: Les postes de pertes SAISIS (la liste plate de D-CALX 11) du cas d'essai —
#: la table du golden CALX196 : chaque poste porte le nom de l'étape qui le
#: reprend (CALX149), donc la cascade les APPLIQUE au lieu de s'omettre.
POSTES_SAISIS = [
    {'poste': poste, 'pct': pct, 'source': 'societe',
     'reference': REFERENCE_CAS}
    for poste, pct in (('salissure', 2.0), ('qualite_module', 0.8),
                       ('lid', 1.5), ('mismatch', 2.0), ('ohmique_dc', 1.0),
                       ('onduleur', 3.0), ('ohmique_ac', 0.5),
                       ('indisponibilite', 3.0))
]

#: La courbe de consommation 24 h SAISIE dans l'atelier (CALX255) : sans elle,
#: charge, autoconsommation et batterie s'omettent et ne coûtent rien.
CONSOMMATION = {'courbe24': [0.5] * 24, 'methode': 'courbe'}


def _extremes_t2m():
    """Les extrêmes de ``T2m`` de la réponse figée — rien d'inventé."""
    lignes = json.loads(FIXTURE.read_text(encoding='utf-8'))
    valeurs = [ligne['T2m'] for ligne in lignes['outputs']['hourly']]
    return min(valeurs), max(valeurs)


#: L'entrée électrique SAISIE du cas. Les températures de dimensionnement y
#: sont SAISIES (les extrêmes de ``T2m`` de la fixture) : sans elles, la
#: conception interroge le fournisseur TMY enregistré par ``apps.py``
#: (CALX61), qui ouvre un client PVGIS NEUF sur le réseau — un appel caché
#: que la sonde de ``BudgetSimulationTest`` a relevé au premier essai. La
#: saisie prime toujours (CAL123) : aucun appel n'est alors tenté.
_T2M_MIN, _T2M_MAX = _extremes_t2m()
ENTREE_ELECTRIQUE = {'temperature_min_c': _T2M_MIN,
                     'temperature_max_c': _T2M_MAX,
                     'dc_m': 25.0}

#: Les tailles mesurées — celles que la tâche nomme.
TAILLES = (1, 4, 12)

# ═══════════════════════════════════════════════════════════════════════════
# LES RELEVÉS — le 24/09/2026, poste Windows 11, Python 3.13, SANS couverture,
# fixture de 288 heures ; trois tours de ``mesurer()`` (chacun le meilleur de
# 3 exécutions, après une exécution d'échauffement : les imports paresseux du
# service ne sont pas du coût de chaîne), poste partagé avec d'autres
# travaux — le relevé retenu est le MEILLEUR des trois tours. Le travail est
# identique à chaque tour et sur toute machine ; le temps ne l'est pas.
#
#   1 pan  :  3 passages (pan + 2 accès distincts)    ,    864 points,
#             0,074 s  (tours : 0,074 / 0,084 / 0,076 s)
#   4 pans : 13 passages (4 × 3 + pan de référence)   ,  3 744 points,
#             0,261 s  (tours : 0,297 / 0,273 / 0,261 s)
#   12 pans: 37 passages (12 × 3 + pan de référence)  , 10 656 points,
#             0,748 s  (tours : 0,748 / 0,903 / 0,818 s)
#
# Onze des vingt-quatre étapes de la cascade CALCULENT sur ce cas (salissure,
# thermique, qualité module, LID, mismatch, ohmique DC, MPPT, onduleur,
# écrêtage, ohmique AC, indisponibilité), plus la simulation module par
# module, la courbe de charge et l'autoconsommation : le budget mesure une
# chaîne qui travaille, pas une suite d'omissions.
#
# Au-delà d'un pan, le pan de RÉFÉRENCE (le plus puissant) repasse une fois
# dans la chaîne pour publier sa cascade et sa série (``simulation.py``,
# étape 2) : d'où le « + 1 ». Temps par pan à 12 pans / temps d'1 pan :
# 0,84 / 0,90 / 0,90 selon le tour — la chaîne est LINÉAIRE en pans.
# Doublement artificiel (la chaîne exécutée deux fois par passage) : 6 / 26 /
# 74 passages et 0,135 / 0,521 / 1,630 s — c'est ce que la garde refuse.
# ═══════════════════════════════════════════════════════════════════════════
RELEVES = {
    1: {'passages': 3, 'points': 864, 'series_meteo': 1, 'secondes': 0.074},
    4: {'passages': 13, 'points': 3744, 'series_meteo': 4, 'secondes': 0.261},
    12: {'passages': 37, 'points': 10656, 'series_meteo': 12,
         'secondes': 0.748},
}

#: La marge du plafond de TEMPS : un ordre de grandeur. Elle couvre un runner
#: plus lent et l'instrumentation de couverture de ``release-verify`` ; c'est
#: le budget de TRAVAIL, exact, qui garde le doublement.
MARGE_TEMPS = 10

#: « le temps par pan ne croît pas d'un ORDRE DE GRANDEUR entre 1 et 12 » —
#: la définition de la tâche, pas un réglage. Mesuré : 0,84 à 0,90.
PLAFOND_LINEARITE = 10

#: Les grandeurs de travail gardées au relevé EXACT (plafond, jamais plancher).
GRANDEURS_TRAVAIL = (
    ('passages', 'passages dans la chaîne de pertes'),
    ('points', 'points horaires traversés par la chaîne'),
    ('series_meteo', 'séries météo demandées'),
)


# ═══════════════════════════════════════════════════════════════════════════
# LA MÉTÉO FIGÉE — la réponse PVGIS enregistrée, lue par le VRAI client
# ═══════════════════════════════════════════════════════════════════════════

_REPONSE = {}


def charge_fixture():
    """La réponse PVGIS brute committée (``{inputs, outputs, _provenance}``)."""
    return json.loads(FIXTURE.read_text(encoding='utf-8'))


def reponse_fixture():
    """La réponse ``serie_irradiance`` de la fixture — une COPIE fraîche.

    La fixture est lue par le VRAI ``ClientPvgis`` (parse de ``outputs.hourly``,
    composantes, bloc météo), avec un transport qui la rejoue : c'est la forme
    exacte que la simulation reçoit en production. Le cache et le limiteur
    sont NEUFS (le cache partagé du processus n'est pas touché), et la date
    de réponse est figée. Lue une seule fois par processus.
    """
    if 'reponse' not in _REPONSE:
        corps = FIXTURE.read_text(encoding='utf-8')

        def rejouer(url, timeout_s):
            assert '/seriescalc?' in url, url
            return 200, corps

        client = pvgis_serie.ClientPvgis(
            transport=rejouer, cache=pvgis_serie._Cache(),
            limiteur=pvgis_serie._Limiteur(par_seconde=10 ** 6))
        _REPONSE['reponse'] = client.serie_irradiance(
            lat=EPINGLE['lat'], lon=EPINGLE['lng'], inclinaison_deg=15.0,
            aspect_deg=0.0, annee_debut=2020, annee_fin=2020,
            composantes=True, obtenue_le='2026-09-21T10:14:00Z')
    return copy.deepcopy(_REPONSE['reponse'])


class ClientFixture:
    """Le client PVGIS DOUBLE : il sert la série figée, il n'appelle rien.

    Il n'expose QUE ``serie_irradiance`` : l'écart contre PVcalc (CALX195) est
    donc publié sans mesure, avec son motif — aucune seconde requête.
    """

    def __init__(self):
        self.reponse = reponse_fixture()
        self.demandes = []

    def serie_irradiance(self, **parametres):
        self.demandes.append(parametres)
        return self.reponse


def document(nb_pans, *, epingle=None):
    """Le ``roof_layout`` v2 d'un calepinage de ``nb_pans`` pans équipés.

    Chaque pan a SON azimut (une série météo par pan, comme un vrai toit à
    plusieurs orientations), ``MODULES_PAR_PAN`` modules et deux accès
    solaires distincts.
    """
    zones = []
    for rang in range(nb_pans):
        zones.append({
            'id': 'z%02d' % (rang + 1),
            'label': 'PAN-%02d' % (rang + 1),
            'geometry': {
                'count': MODULES_PAR_PAN,
                'azimuthDeg': 90.0 + 15.0 * rang,
                'tiltDeg': 15.0,
                'family': 'surimposition',
                'solarAccess': {'values': list(ACCES_DU_PAN)},
            },
        })
    return {'version': 2, 'pin': dict(epingle or EPINGLE), 'zones': zones,
            'consumption': copy.deepcopy(CONSOMMATION)}


class CalepinageEssai:
    """Le strict minimum que le service lit sur un pivot — aucun ORM.

    ``pk = None`` : rien n'est enregistré en base, et la recherche d'un
    fichier météo déposé (CALX62) s'arrête avant la moindre requête. Le
    ``resultat`` de départ porte l'entrée électrique SAISIE et la liste plate
    des postes (D-CALX 11), comme un calepinage réel.
    """

    pk = None
    devis_id = None
    titre = 'Calepinage d essai'

    def __init__(self, layout, *, entree=None, pertes=None):
        postes = copy.deepcopy(POSTES_SAISIS if pertes is None else pertes)
        self.roof_layout = layout
        self.resultat = {
            'entree_electrique': dict(ENTREE_ELECTRIQUE if entree is None
                                      else entree),
            'pertes': copy.deepcopy(postes),
        }
        self.pertes = postes
        self.company = None


# ═══════════════════════════════════════════════════════════════════════════
# LA MESURE
# ═══════════════════════════════════════════════════════════════════════════

def _compteur_de_chaine(compte):
    """``appliquer_chaine`` RÉELLE, qui compte chaque passage et ses points."""
    reelle = chaine_pertes.appliquer_chaine

    def appliquer(serie, contexte, *args, **kwargs):
        compte['passages'] += 1
        compte['points'] += len((serie or {}).get('points') or ())
        return reelle(serie, contexte, *args, **kwargs)

    return appliquer


def mesurer(nb_pans, *, repetitions=3, doubler=False):
    """``{passages, points, series_meteo, secondes}`` d'une simulation.

    Le temps est le MEILLEUR de ``repetitions`` exécutions (l'estimateur le
    moins sensible au bruit d'un poste partagé) ; le travail doit être
    identique d'une exécution à l'autre, sinon la mesure est refusée.

    ``doubler`` simule la régression que la garde doit attraper : chaque
    passage dans la chaîne l'exécute DEUX fois (coût par pan doublé).
    """
    meilleur = None
    travail = None
    for _ in range(repetitions):
        compte = {'passages': 0, 'points': 0}
        comptee = _compteur_de_chaine(compte)
        if doubler:
            def appliquer(serie, contexte, *args, **kwargs):
                comptee(serie, contexte, *args, **kwargs)
                return comptee(serie, contexte, *args, **kwargs)
        else:
            appliquer = comptee
        client = ClientFixture()
        calepinage = CalepinageEssai(document(nb_pans))
        gc.collect()
        with mock.patch.object(simulation, 'appliquer_chaine', appliquer), \
                mock.patch.object(chaine_pertes, 'appliquer_chaine',
                                  appliquer):
            debut = time.perf_counter()
            simulation.simuler_calepinage(
                calepinage, client=client, materiel=MATERIEL,
                reglages=REGLAGES, enregistrer=False, maintenant=MAINTENANT)
            duree = time.perf_counter() - debut
        ce_passage = dict(compte, series_meteo=len(client.demandes))
        if travail is None:
            travail = ce_passage
        elif ce_passage != travail:
            raise AssertionError(
                'Travail NON déterministe à %d pan(s) : %r puis %r — une '
                'mesure de temps sur un travail variable ne veut rien dire.'
                % (nb_pans, travail, ce_passage))
        meilleur = duree if meilleur is None else min(meilleur, duree)
    return dict(travail, secondes=meilleur)


def depassements(mesures, releves=None, *, marge_temps=MARGE_TEMPS,
                 plafond_linearite=PLAFOND_LINEARITE):
    """Les dépassements du budget, en français, taille par taille.

    Args:
        mesures: ``{nb_pans: {passages, points, series_meteo, secondes}}``.
        releves: les relevés de référence (``RELEVES`` par défaut).

    Returns:
        list[str] — vide quand le budget tient. Chaque ligne NOMME la taille,
        la grandeur, la mesure et le plafond.
    """
    releves = RELEVES if releves is None else releves
    lignes = []
    for taille in sorted(mesures):
        mesure, releve = mesures[taille], releves[taille]
        for cle, libelle in GRANDEURS_TRAVAIL:
            if mesure[cle] > releve[cle]:
                lignes.append(
                    '%d pan(s) : %d %s pour un plafond relevé de %d.'
                    % (taille, mesure[cle], libelle, releve[cle]))
        plafond = releve['secondes'] * marge_temps
        if mesure['secondes'] > plafond:
            lignes.append(
                '%d pan(s) : %.3f s de simulation pour un plafond de %.3f s '
                '(relevé %.3f s × %d).'
                % (taille, mesure['secondes'], plafond, releve['secondes'],
                   marge_temps))
    petite, grande = min(mesures), max(mesures)
    if grande > petite:
        par_pan_petite = mesures[petite]['secondes'] / petite
        par_pan_grande = mesures[grande]['secondes'] / grande
        if par_pan_grande > plafond_linearite * par_pan_petite:
            lignes.append(
                'Linéarité rompue : %.4f s par pan à %d pans contre %.4f s à '
                '%d — plus de %d fois plus cher par pan.'
                % (par_pan_grande, grande, par_pan_petite, petite,
                   plafond_linearite))
    return lignes


# ═══════════════════════════════════════════════════════════════════════════
# 1. LE VERDICT — pur, rapide (palier par-merge)
# ═══════════════════════════════════════════════════════════════════════════

class VerdictBudgetTest(SimpleTestCase):
    """La règle du budget, sur des mesures écrites à la main."""

    def test_les_releves_tiennent_leur_propre_budget(self):
        self.assertEqual(depassements(copy.deepcopy(RELEVES)), [])

    def test_un_travail_double_est_nomme_taille_par_taille(self):
        doubles = copy.deepcopy(RELEVES)
        for mesure in doubles.values():
            mesure['passages'] *= 2
            mesure['points'] *= 2

        lignes = depassements(doubles)

        for taille in TAILLES:
            self.assertTrue(
                any(ligne.startswith('%d pan(s)' % taille)
                    and 'passages' in ligne for ligne in lignes),
                'Le doublement à %d pan(s) doit être nommé : %r'
                % (taille, lignes))

    def test_un_temps_au_dela_d_un_ordre_de_grandeur_rougit(self):
        lentes = copy.deepcopy(RELEVES)
        lentes[4]['secondes'] = RELEVES[4]['secondes'] * (MARGE_TEMPS + 1)

        lignes = depassements(lentes)

        self.assertEqual(len(lignes), 1, lignes)
        self.assertIn('4 pan(s)', lignes[0])

    def test_une_croissance_quadratique_rompt_la_linearite(self):
        # Temps ∝ pans² : 12 fois plus cher PAR PAN à 12 pans qu'à 1 pan.
        quadratique = {taille: dict(RELEVES[taille],
                                    secondes=0.01 * taille * taille)
                       for taille in TAILLES}

        lignes = depassements(quadratique, marge_temps=10 ** 6)

        self.assertEqual(len(lignes), 1, lignes)
        self.assertTrue(lignes[0].startswith('Linéarité rompue'))

    def test_la_fixture_est_une_reponse_pvgis_reelle_committee(self):
        charge = charge_fixture()

        self.assertIn('re.jrc.ec.europa.eu', charge['_provenance']['url'])
        self.assertIn('pvcalculation=0', charge['_provenance']['url'])
        self.assertEqual(len(charge['outputs']['hourly']), 288)
        for cle in ('Gb(i)', 'Gd(i)', 'Gr(i)', 'T2m', 'WS10m'):
            self.assertIn(cle, charge['outputs']['hourly'][0])


# ═══════════════════════════════════════════════════════════════════════════
# 2. LA MESURE RÉELLE — étiquetée ``slow`` (release-verify)
# ═══════════════════════════════════════════════════════════════════════════

@tag('slow')
class BudgetSimulationTest(SimpleTestCase):
    """La simulation RÉELLE tient son budget à 1, 4 et 12 pans."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Aucun appel réseau n'est possible pendant les mesures : le
        # transport par défaut du client PVGIS est remplacé par une sonde
        # qui échoue le test s'il est jamais atteint.
        cls.transport_reseau = mock.MagicMock(
            side_effect=AssertionError('appel réseau PVGIS pendant la mesure'))
        with mock.patch.object(pvgis_serie, '_transport_urllib',
                               cls.transport_reseau):
            # Échauffement : les imports paresseux du service ne sont pas du
            # coût de chaîne.
            mesurer(1, repetitions=1)
            cls.mesures = {taille: mesurer(taille) for taille in TAILLES}

    def _releves_du_jour(self):
        return '\n'.join(
            '  %2d pan(s) : %s' % (taille, self.mesures[taille])
            for taille in TAILLES)

    def test_le_budget_de_chaque_taille_tient(self):
        self.assertEqual(
            depassements(self.mesures), [],
            'Budget de simulation dépassé. Mesures du jour :\n%s'
            % self._releves_du_jour())

    def test_le_travail_est_exactement_celui_du_releve(self):
        # Une BAISSE est une optimisation : relevez ``RELEVES`` dans le même
        # commit, pour que la garde reste serrée.
        for taille in TAILLES:
            with self.subTest(pans=taille):
                for cle, _libelle in GRANDEURS_TRAVAIL:
                    self.assertEqual(self.mesures[taille][cle],
                                     RELEVES[taille][cle], cle)

    def test_le_temps_par_pan_ne_croit_pas_d_un_ordre_de_grandeur(self):
        par_pan = {taille: self.mesures[taille]['secondes'] / taille
                   for taille in TAILLES}

        self.assertLessEqual(
            par_pan[12], PLAFOND_LINEARITE * par_pan[1],
            'Temps par pan : %r' % par_pan)

    def test_une_serie_meteo_par_pan_et_aucun_reseau(self):
        for taille in TAILLES:
            self.assertEqual(self.mesures[taille]['series_meteo'], taille)
        self.transport_reseau.assert_not_called()

    def test_la_chaine_mesuree_calcule_au_lieu_de_s_omettre(self):
        # Un budget pris sur une chaîne qui s'omet partout ne mesurerait que
        # des omissions : les étapes lourdes du cas doivent CALCULER.
        with mock.patch.object(pvgis_serie, '_transport_urllib',
                               self.transport_reseau):
            rendu = simulation.simuler_calepinage(
                CalepinageEssai(document(1)), client=ClientFixture(),
                materiel=MATERIEL, reglages=REGLAGES, enregistrer=False,
                maintenant=MAINTENANT)
        calculees = {etape['etape'] for etape
                     in rendu['blocs']['cascade']['etapes']
                     if etape['perte_pct'] is not None}

        for etape in ('thermique', 'mppt', 'onduleur', 'ecretage'):
            self.assertIn(etape, calculees)
        self.assertIsNotNone(rendu['blocs']['consommation'])
        self.assertTrue(rendu['blocs']['production']['par_module'])

    def test_un_doublement_du_cout_par_pan_fait_rougir_le_budget(self):
        doubles = {taille: mesurer(taille, repetitions=1, doubler=True)
                   for taille in TAILLES}

        lignes = depassements(doubles)

        for taille in TAILLES:
            self.assertTrue(
                any(ligne.startswith('%d pan(s)' % taille)
                    and 'passages' in ligne for ligne in lignes),
                'Un coût par pan doublé à %d pan(s) doit rougir : %r'
                % (taille, lignes))
