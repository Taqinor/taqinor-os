"""CALX196 — le GOLDEN pluriannuel de la cascade, des quantiles et du PR.

POURQUOI UN GOLDEN, ET CE QU'IL GÈLE
--------------------------------------
Le noyau a déjà cette discipline (``core/calepinage/golden/villa/``), la
chaîne de pertes ne l'avait pas : rien ne disait, d'une semaine sur l'autre,
que la cascade rendait les mêmes kWh. PVsyst fait de chaque variante de
simulation un objet REPRODUCTIBLE dont le rapport réimprime tous les
paramètres employés
(https://www.pvsyst.com/help/project-design/results/index.html) ; c'est
exactement ce que ce fichier fait, en JSON committé.

Le golden gèle UN cas, sur la réponse PVGIS pluriannuelle ENREGISTRÉE
``fixtures_pvgis/seriescalc_casablanca_sud_deux_annees.json`` (Casablanca
33,5 / −7,6, plan 15° plein sud, années 2019 ET 2020, base PVGIS-SARAH3,
météo ERA5) : la cascade ENTIÈRE étape par étape, les agrégats mensuels et
annuels, le PR, σ et ses composantes, et les quatre quantiles.

CE QUI EST COMPARÉ, ET CE QUI NE L'EST PAS
--------------------------------------------
Tout est comparé SAUF le texte des ``motif_omission``. La raison est
concrète : les étapes de la chaîne sont livrées par des lanes parallèles, et
le jour où l'une d'elles livre son module, un poste qui disait « étape non
livrée » dira autre chose SANS que le moindre kWh bouge. Geler ce texte
ferait rougir le golden sur un changement qui ne change rien. En revanche
l'ÉTAT (omise / appliquée) et TOUTES les énergies sont gelés : qu'une étape
se mette à s'appliquer est précisément ce qu'on veut voir.

L'ENTRÉE DE LA CHAÎNE
-----------------------
``p_dc_w = kWc × G(i)`` — la DÉFINITION du kilowatt-crête (STC : 1 000 W/m²,
25 °C). Le convertisseur d'irradiance en puissance appartiendra à
``services/simulation.py`` (CALX5) ; tant qu'il n'existe pas, le harnais le
pose ici, dans le test, jamais dans le code produit.

RÉGÉNÉRER LE GOLDEN — UNIQUEMENT SUR DEMANDE EXPLICITE
--------------------------------------------------------
Aucun test ne réécrit le fichier : seul le drapeau ``--write``, lancé à la
main, le régénère. Depuis ``backend/django_core`` ::

    python -m apps.calepinage.tests.test_calx196_golden --write

(sur l'hôte Windows du dépôt : ``C:/dev/venv-tq/Scripts/python -m
apps.calepinage.tests.test_calx196_golden --write``, avec ``C:\\dev\\wpstub``
sur le ``sys.path``). ``--arbre <sha>`` force l'empreinte d'arbre inscrite en
tête quand ``git`` n'est pas joignable. Régénérer est un GESTE : le diff du
JSON doit être lu, et le message de commit doit dire pourquoi la cascade a
bougé.

Aucune base, aucun réseau : ``SimpleTestCase``.

Run :
    python manage.py test apps.calepinage.tests.test_calx196_golden
"""
from __future__ import annotations

import argparse
import ast
import datetime
import json
import pathlib
import subprocess
import sys

if __name__ == '__main__':  # pragma: no cover — chemin « --write » seulement
    import os

    os.environ.setdefault('DJANGO_SETTINGS_MODULE',
                          'erp_agentique.settings.dev')
    import django

    django.setup()

from django.test import SimpleTestCase  # noqa: E402

from apps.calepinage.services.incertitude import (  # noqa: E402
    bloc_incertitude,
)
from apps.calepinage.services.chaine_pertes import (  # noqa: E402
    appliquer_chaine,
)

RACINE = pathlib.Path(__file__).resolve().parent
FIXTURES = RACINE / 'fixtures_pvgis'
DOSSIER_GOLDEN = RACINE / 'golden_simulation'
GOLDEN = DOSSIER_GOLDEN / 'cascade_pluriannuelle_casablanca.json'

FIXTURE = 'seriescalc_casablanca_sud_deux_annees.json'

#: La puissance crête du cas figé, et le seul pan équipé.
KWC = 6.0

#: La provenance des réglages du cas. Ce ne sont PAS des valeurs par défaut
#: du produit : ce sont les réglages d'une société de TEST, écrits ici et
#: nulle part ailleurs.
REFERENCE_CAS = ('Cas figé CALX196 — réglages de TEST, aucune valeur par '
                 'défaut du produit')

SITE = {'lat': 33.5, 'lon': -7.6, 'altitude_m': 139.0,
        'fuseau': 'Africa/Casablanca'}

PLANS = [{'cle': 'A', 'pan': 'PAN-A', 'modules': 12, 'kwc': KWC,
          'inclinaison_deg': 15.0, 'azimut_pvgis_deg': 0.0}]

REGLAGES = {
    'mode_meteo': {'valeur': 'pluriannuel', 'source': 'societe'},
    'fenetre_annees': {'valeur': '2019-2020', 'source': 'societe'},
    'sigma_modele_pct': {'valeur': 3.0, 'source': 'societe',
                         'reference': REFERENCE_CAS},
    'sigma_biais_meteo_pct': {'valeur': 1.0, 'source': 'societe',
                              'reference': REFERENCE_CAS},
}

POSTES_SAISIS = [
    {'poste': 'salissure', 'pct': 2.0, 'source': 'societe',
     'reference': REFERENCE_CAS},
    {'poste': 'qualite_module', 'pct': 0.8, 'source': 'societe',
     'reference': REFERENCE_CAS},
    {'poste': 'lid', 'pct': 1.5, 'source': 'societe',
     'reference': REFERENCE_CAS},
    {'poste': 'mismatch', 'pct': 2.0, 'source': 'societe',
     'reference': REFERENCE_CAS},
    {'poste': 'ohmique_dc', 'pct': 1.0, 'source': 'societe',
     'reference': REFERENCE_CAS},
    {'poste': 'onduleur', 'pct': 3.0, 'source': 'societe',
     'reference': REFERENCE_CAS},
    {'poste': 'ohmique_ac', 'pct': 0.5, 'source': 'societe',
     'reference': REFERENCE_CAS},
    {'poste': 'indisponibilite', 'pct': 3.0, 'source': 'societe',
     'reference': REFERENCE_CAS},
]

HASH_ENTREE = 'calx196-cas-fige'

#: Les clés d'une étape que le golden COMPARE. ``motif_omission`` en est
#: absente, et l'en-tête du fichier dit pourquoi.
CLES_ETAPE_COMPAREES = (
    'rang', 'etape', 'libelle', 'omise', 'gain', 'source', 'entree',
    'kwh_avant', 'kwh_apres', 'perte_kwh', 'perte_pct',
)

#: Tolérances de comparaison — de l'arithmétique d'arrondi, pas des seuils.
DELTA_KWH = 0.01
DELTA_PCT = 0.01
DELTA_RATIO = 1e-4


# ── le cas figé, et son exécution ───────────────────────────────────────

def serie_entree():
    """La série d'entrée, bâtie sur la réponse PVGIS pluriannuelle réelle."""
    charge = json.loads((FIXTURES / FIXTURE).read_text(encoding='utf-8'))
    points = []
    for ligne in charge['outputs']['hourly']:
        moment = ligne['time']
        points.append({
            'annee': int(moment[0:4]), 'mois': int(moment[4:6]),
            'jour': int(moment[6:8]), 'heure': int(moment[9:11]),
            'gi_w_m2': ligne['G(i)'], 't2m_c': ligne['T2m'],
            'ws10m': ligne['WS10m'], 'h_sun_deg': ligne['H_sun'],
            'p_w': KWC * ligne['G(i)'],
        })
    return {'pas_minutes': 60, 'colonne_energie': 'p_w', 'points': points}


def cas():
    """Les ENTRÉES du cas figé, telles que le golden les recopie."""
    return {
        'fixture': FIXTURE,
        'kwc': KWC,
        'site': dict(SITE),
        'plans': [dict(plan) for plan in PLANS],
        'reglages_simulation': json.loads(json.dumps(REGLAGES)),
        'postes_saisis': json.loads(json.dumps(POSTES_SAISIS)),
        'hash_entree': HASH_ENTREE,
        'entree_de_chaine': ('p_dc_w = kWc × G(i) — définition du '
                             'kilowatt-crête aux conditions STC'),
    }


def contexte():
    """Le contexte de chaîne du cas figé — rien de plus que ce qui est déclaré.

    Aucune fiche produit, aucun ombrage, aucun câble : les étapes CALCULÉES
    n'ont donc aucune entrée et laissent la place aux postes SAISIS (CALX149).
    C'est ce qui rend le cas reproductible pendant que les lanes d'étapes
    atterrissent.
    """
    return {
        'site': dict(SITE),
        'meteo': {'heure': {'base': 'locale_standard'}},
        'plans': [dict(plan) for plan in PLANS],
        'reglages_simulation': json.loads(json.dumps(REGLAGES)),
        'postes_saisis': json.loads(json.dumps(POSTES_SAISIS)),
        'hash_entree': HASH_ENTREE,
    }


def simuler():
    """Le RÉSULTAT du cas figé : cascade, production, incertitude."""
    resultat = {}
    _, cascade = appliquer_chaine(serie_entree(), contexte(),
                                  resultat=resultat)
    production = resultat['production']
    annuel = {ligne['annee']: ligne['kwh']
              for ligne in production['annees']}
    incertitude = bloc_incertitude(production['total']['p50_kwh'],
                                   totaux_par_annee=annuel,
                                   reglages=REGLAGES)
    return {
        'cascade': {
            'total_pct': cascade['total_pct'],
            'ordre': list(cascade['ordre']),
            'postes_non_sources': list(cascade['postes_non_sources']),
            'hash_entree': cascade['hash_entree'],
            'etapes': [_etape_publiee(etape) for etape in cascade['etapes']],
        },
        'production': {
            'total': production['total'],
            'mensuel': production['mensuel'],
            'annees': production['annees'],
            'par_pan': production['par_pan'],
        },
        'incertitude': incertitude,
    }


def _etape_publiee(etape):
    """Une étape réduite aux clés que le golden compare, plus son motif."""
    ligne = {'omise': bool(etape['motif_omission'])}
    for cle in CLES_ETAPE_COMPAREES:
        if cle != 'omise':
            ligne[cle] = etape[cle]
    # Recopié pour la LECTURE du fichier, jamais comparé (voir l'en-tête).
    ligne['motif_omission_non_compare'] = etape['motif_omission']
    return ligne


# ── la comparaison, qui NOMME ce qui a bougé ────────────────────────────

def ecarts_de_cascade(attendu, obtenu):
    """Les écarts entre deux cascades, en phrases qui NOMMENT l'étape.

    Un golden qui dit « le total a changé » n'aide personne : il faut le nom
    de l'étape, la clé qui a bougé, et les deux valeurs.
    """
    messages = []
    if not _proches(attendu['total_pct'], obtenu['total_pct'], DELTA_PCT):
        messages.append(
            f'Perte totale de la cascade : attendue {attendu["total_pct"]} %, '
            f'obtenue {obtenu["total_pct"]} %.')
    if attendu['ordre'] != obtenu['ordre']:
        messages.append(
            "L'ORDRE des étapes a changé : attendu "
            f'{attendu["ordre"]}, obtenu {obtenu["ordre"]}.')
        return messages

    par_nom = {etape['etape']: etape for etape in obtenu['etapes']}
    for etape_attendue in attendu['etapes']:
        nom = etape_attendue['etape']
        etape_obtenue = par_nom.get(nom)
        if etape_obtenue is None:
            messages.append(f'L\'étape « {nom} » a disparu de la cascade.')
            continue
        messages += _ecarts_d_etape(nom, etape_attendue, etape_obtenue)
    return messages


def _ecarts_d_etape(nom, attendue, obtenue):
    messages = []
    for cle in ('kwh_avant', 'kwh_apres', 'perte_kwh'):
        if not _proches(attendue[cle], obtenue[cle], DELTA_KWH):
            messages.append(
                f'L\'étape « {nom} » : {cle} attendu {attendue[cle]} kWh, '
                f'obtenu {obtenue[cle]} kWh.')
    if not _proches(attendue['perte_pct'], obtenue['perte_pct'], DELTA_PCT):
        messages.append(
            f'L\'étape « {nom} » : perte_pct attendue '
            f'{attendue["perte_pct"]} %, obtenue {obtenue["perte_pct"]} %.')
    for cle in ('rang', 'libelle', 'omise', 'gain', 'source', 'entree'):
        if attendue[cle] != obtenue[cle]:
            messages.append(
                f'L\'étape « {nom} » : {cle} attendu '
                f'{attendue[cle]!r}, obtenu {obtenue[cle]!r}.')
    return messages


def ecarts_de_bloc(libelle, attendu, obtenu, delta):
    """Les écarts d'un bloc de nombres, clé par clé et NOMMÉS."""
    messages = []
    for cle in sorted(set(attendu) | set(obtenu)):
        gauche, droite = attendu.get(cle), obtenu.get(cle)
        if isinstance(gauche, (int, float)) and not isinstance(gauche, bool) \
                and isinstance(droite, (int, float)):
            if not _proches(gauche, droite, delta):
                messages.append(f'{libelle} → « {cle} » : attendu {gauche}, '
                                f'obtenu {droite}.')
        elif gauche != droite:
            messages.append(f'{libelle} → « {cle} » : attendu {gauche!r}, '
                            f'obtenu {droite!r}.')
    return messages


def _proches(gauche, droite, delta):
    if gauche is None or droite is None:
        return gauche is None and droite is None
    return abs(float(gauche) - float(droite)) <= delta


# ── l'écriture du golden, et rien d'autre ne l'écrit ────────────────────

def _arbre_sha(force=''):
    """L'empreinte d'arbre du dépôt au moment de la génération."""
    if force:
        return force
    try:
        sortie = subprocess.run(
            ['git', 'rev-parse', 'HEAD^{tree}'], cwd=str(RACINE),
            capture_output=True, text=True, timeout=20, check=False)
    except (OSError, subprocess.SubprocessError):
        return 'inconnue (git injoignable à la génération)'
    valeur = (sortie.stdout or '').strip()
    return valeur or 'inconnue (git injoignable à la génération)'


def ecrire_le_golden(arguments=None):
    """Régénère le fichier golden. Appelé UNIQUEMENT par ``--write``."""
    analyseur = argparse.ArgumentParser(
        description="Régénère le golden pluriannuel de CALX196.")
    analyseur.add_argument('--write', action='store_true', required=True,
                           help='obligatoire : écrire écrase le golden.')
    analyseur.add_argument('--arbre', default='',
                           help="empreinte d'arbre à inscrire en tête.")
    options = analyseur.parse_args(arguments)

    charge = json.loads((FIXTURES / FIXTURE).read_text(encoding='utf-8'))
    meteo = charge['inputs']['meteo_data']
    document = {
        '_provenance': {
            'tache': 'CALX196',
            'produit_par': ('python -m '
                            'apps.calepinage.tests.test_calx196_golden '
                            '--write'),
            'produit_le': datetime.date.today().isoformat(),
            'arbre_sha': _arbre_sha(options.arbre),
            'fixture': FIXTURE,
            'fixture_url': charge['_provenance']['url'],
            'fenetre_annees': f'{meteo["year_min"]}-{meteo["year_max"]}',
            'base_rayonnement': meteo['radiation_db'],
            'base_meteo': meteo['meteo_db'],
            'cles_non_comparees': ['motif_omission'],
            'pourquoi_non_comparees': (
                "Le texte d'omission d'une étape change le jour où sa lane "
                'livre le module, sans qu\'un seul kWh bouge. L\'ÉTAT '
                '(« omise ») et toutes les énergies, eux, sont comparés.'),
            'comment_regenerer': (
                'Relancer la commande ci-dessus À LA MAIN, lire le diff, et '
                'dire dans le message de commit POURQUOI la cascade a bougé. '
                'Aucun test ne réécrit ce fichier.'),
        },
        'cas': cas(),
        'attendu': simuler(),
    }
    DOSSIER_GOLDEN.mkdir(parents=True, exist_ok=True)
    GOLDEN.write_text(
        json.dumps(document, ensure_ascii=False, indent=1) + '\n',
        encoding='utf-8')
    return GOLDEN


def golden():
    return json.loads(GOLDEN.read_text(encoding='utf-8'))


# ── les tests ────────────────────────────────────────────────────────────

class GoldenPluriannuelTest(SimpleTestCase):
    """La cascade, les agrégats, σ et les quantiles sont GELÉS."""

    def setUp(self):
        self.golden = golden()
        self.obtenu = simuler()

    def test_les_entrees_du_cas_n_ont_pas_bouge(self):
        """Un golden dont les ENTRÉES ont changé ne compare plus rien."""
        self.assertEqual(self.golden['cas'], cas())

    def test_la_cascade_etape_par_etape(self):
        messages = ecarts_de_cascade(self.golden['attendu']['cascade'],
                                     self.obtenu['cascade'])
        self.assertEqual(messages, [], '\n'.join(messages))

    def test_le_total_de_production_et_le_pr(self):
        messages = ecarts_de_bloc(
            'production.total', self.golden['attendu']['production']['total'],
            self.obtenu['production']['total'], DELTA_KWH)
        self.assertEqual(messages, [], '\n'.join(messages))

    def test_les_mois_et_les_annees(self):
        for cle in ('mensuel', 'annees', 'par_pan'):
            self.assertEqual(self.golden['attendu']['production'][cle],
                             self.obtenu['production'][cle], cle)

    def test_sigma_ses_composantes_et_les_quatre_quantiles(self):
        attendu = self.golden['attendu']['incertitude']
        obtenu = self.obtenu['incertitude']
        self.assertEqual(attendu['composantes'], obtenu['composantes'])
        self.assertAlmostEqual(attendu['sigma_total'], obtenu['sigma_total'],
                               delta=DELTA_RATIO)
        messages = ecarts_de_bloc('incertitude.quantiles',
                                  attendu['quantiles'], obtenu['quantiles'],
                                  DELTA_KWH)
        self.assertEqual(messages, [], '\n'.join(messages))
        self.assertEqual(sorted(obtenu['quantiles']),
                         ['p50_kwh', 'p75_kwh', 'p90_kwh', 'p95_kwh'])


class EnTeteDuGoldenTest(SimpleTestCase):
    """Le fichier porte EN TÊTE de quoi le relire dans un an."""

    def setUp(self):
        self.provenance = golden()['_provenance']

    def test_la_fenetre_d_annees_et_les_bases_meteo(self):
        self.assertEqual(self.provenance['fenetre_annees'], '2019-2020')
        self.assertEqual(self.provenance['base_rayonnement'], 'PVGIS-SARAH3')
        self.assertEqual(self.provenance['base_meteo'], 'ERA5')

    def test_comment_il_a_ete_produit_et_sur_quel_arbre(self):
        self.assertIn('--write', self.provenance['produit_par'])
        self.assertTrue(self.provenance['arbre_sha'])
        self.assertIn('Aucun test ne réécrit',
                      self.provenance['comment_regenerer'])

    def test_la_fenetre_du_golden_est_bien_pluriannuelle(self):
        annees = sorted({ligne['annee']
                         for ligne in golden()['attendu']['production']
                         ['annees']})
        self.assertEqual(annees, [2019, 2020])


class MessageDEchecTest(SimpleTestCase):
    """Le message NOMME l'étape qui a bougé, pas seulement le total."""

    def test_il_cite_l_etape_et_ses_kwh_avant_et_apres(self):
        attendu = golden()['attendu']['cascade']
        abime = json.loads(json.dumps(attendu))
        fautive = next(etape for etape in abime['etapes']
                       if not etape['omise'])
        fautive['kwh_apres'] = fautive['kwh_apres'] - 5.0
        fautive['perte_kwh'] = fautive['perte_kwh'] + 5.0

        messages = ecarts_de_cascade(attendu, abime)
        texte = '\n'.join(messages)
        self.assertIn(f'« {fautive["etape"]} »', texte)
        self.assertIn('kwh_apres', texte)
        self.assertIn(str(fautive['kwh_apres']), texte)
        attendue = next(etape for etape in attendu['etapes']
                        if etape['etape'] == fautive['etape'])
        self.assertIn(str(attendue['kwh_apres']), texte)

    def test_une_etape_qui_se_met_a_s_appliquer_est_nommee(self):
        attendu = golden()['attendu']['cascade']
        abime = json.loads(json.dumps(attendu))
        omise = next(etape for etape in abime['etapes'] if etape['omise'])
        omise['omise'] = False
        omise['source'] = 'societe'

        texte = '\n'.join(ecarts_de_cascade(attendu, abime))
        self.assertIn(f'« {omise["etape"]} »', texte)
        self.assertIn('omise', texte)

    def test_une_cascade_identique_ne_dit_rien(self):
        attendu = golden()['attendu']['cascade']
        self.assertEqual(ecarts_de_cascade(attendu,
                                           json.loads(json.dumps(attendu))),
                         [])


# ── les valeurs publiées par les concurrents — ENTRÉES SAISIES seulement ──

#: AURORA — « System Losses », valeurs par défaut publiées :
#: https://help.aurorasolar.com/hc/en-us/articles/220450107-System-Losses
#: Elles sont ici des ENTRÉES de test, avec leur URL. Aucune ne doit exister
#: dans ``apps/calepinage/services/`` — la garde plus bas le vérifie.
AURORA_URL = ('https://help.aurorasolar.com/hc/en-us/articles/'
              '220450107-System-Losses')
AURORA_DEFAUTS_PCT = {
    'lid': 1.5,
    'ombrage': 3.0,
    'salissure': 2.0,
    'mismatch': 2.0,
    'connexions': 0.5,
    'cablage': 2.0,
    'disponibilite': 3.0,
}

#: Le rattachement des défauts d'Aurora aux postes de NOTRE catalogue.
#: « ombrage » n'y figure pas : chez nous l'ombrage est une LECTURE calculée
#: (``ETAPES_HORS_CATALOGUE``), jamais un pourcentage saisi — c'est dit ici
#: plutôt que forcé dans un poste qui ne lui correspond pas.
AURORA_VERS_NOS_POSTES = {
    'lid': 'lid',
    'salissure': 'salissure',
    'mismatch': 'mismatch',
    'connexions': 'ohmique_dc',
    'cablage': 'ohmique_ac',
    'disponibilite': 'indisponibilite',
}

#: OPENSOLAR — pertes par défaut selon la configuration d'onduleur :
#: https://support.opensolar.com/hc/en-us/articles/
#: 4406931180313-Stringing-Micro-Inverters-and-Power-Optimizers
#: La DEUXIÈME valeur est le « DC Wiring » que la page nomme (0,1 % en
#: micro-onduleur) ; la troisième tombe à 0 avec optimiseurs et
#: micro-onduleurs. Le rattachement de la PREMIÈRE à un poste de notre
#: catalogue n'affirme rien sur ce qu'OpenSolar nomme : seul le COMPOSÉ
#: MULTIPLICATIF est vérifié ici.
OPENSOLAR_URL = ('https://support.opensolar.com/hc/en-us/articles/'
                 '4406931180313-Stringing-Micro-Inverters-and-Power-'
                 'Optimizers')
OPENSOLAR_PAR_CONFIGURATION = {
    'chaine': (5.0, 2.0, 2.0),
    'chaine_optimiseur': (5.0, 1.0, 0.0),
    'micro_onduleur': (5.0, 0.1, 0.0),
}
OPENSOLAR_POSTES = ('ohmique_ac', 'ohmique_dc', 'mismatch')

#: L'arithmétique qu'Aurora PUBLIE sur la même page : « two losses of 4% and
#: 3% will result in a 1−(1−4%)×(1−3%)=6.88% estimated overall loss ».
AURORA_PROPRIETE = ((4.0, 3.0), 6.88)


def _cascade_de_saisies(saisies):
    """La cascade obtenue en n'alimentant QUE ces postes saisis sourcés."""
    reglages = {'mode_meteo': {'valeur': 'pluriannuel', 'source': 'societe'},
                'fenetre_annees': {'valeur': '2019-2020',
                                   'source': 'societe'}}
    contexte_essai = {
        'site': dict(SITE),
        'meteo': {'heure': {'base': 'locale_standard'}},
        'plans': [dict(plan) for plan in PLANS],
        'reglages_simulation': reglages,
        'postes_saisis': [
            {'poste': poste, 'pct': pct, 'source': 'concurrent_cite',
             'reference': reference}
            for poste, pct, reference in saisies],
    }
    _, cascade = appliquer_chaine(serie_entree(), contexte_essai)
    return cascade


def _compose(pourcentages):
    """1 − Π(1 − p) en pourcentage — la composition multiplicative."""
    reste = 1.0
    for pct in pourcentages:
        reste *= 1.0 - pct / 100.0
    return (1.0 - reste) * 100.0


class ValeursConcurrentesEnEntreeTest(SimpleTestCase):
    """Les défauts publiés par Aurora et OpenSolar, en ENTRÉES SAISIES."""

    def test_aurora_la_cascade_compose_multiplicativement(self):
        saisies = [(poste, AURORA_DEFAUTS_PCT[nom], AURORA_URL)
                   for nom, poste in AURORA_VERS_NOS_POSTES.items()]
        cascade = _cascade_de_saisies(saisies)
        attendu = _compose(pct for _poste, pct, _ref in saisies)
        self.assertAlmostEqual(cascade['total_pct'], round(attendu, 1),
                               delta=0.1)
        from apps.calepinage.services.chaine_pertes import POSTE_PAR_ETAPE
        appliquees = [etape['etape'] for etape in cascade['etapes']
                      if not etape['motif_omission']]
        # Un poste du catalogue et l'étape qui le porte n'ont pas toujours le
        # même nom (« mismatch » → « mismatch_fabricant ») : la table de
        # correspondance de la chaîne tranche, jamais une supposition.
        attendues = {etape for etape, poste in POSTE_PAR_ETAPE.items()
                     if poste in set(AURORA_VERS_NOS_POSTES.values())}
        self.assertEqual(sorted(appliquees), sorted(attendues))

    def test_aurora_l_ombrage_n_a_aucun_poste_saisi_chez_nous(self):
        from apps.calepinage.services.chaine_pertes import (
            ETAPES_HORS_CATALOGUE, POSTE_PAR_ETAPE,
        )
        self.assertIn('ombrage', AURORA_DEFAUTS_PCT)
        self.assertNotIn('ombrage', AURORA_VERS_NOS_POSTES)
        self.assertNotIn('ombrage_proche', POSTE_PAR_ETAPE)
        self.assertIn('ombrage_proche', ETAPES_HORS_CATALOGUE)

    def test_opensolar_chaque_configuration_rend_son_total(self):
        for configuration, valeurs in OPENSOLAR_PAR_CONFIGURATION.items():
            with self.subTest(configuration=configuration):
                saisies = [(poste, pct, OPENSOLAR_URL)
                           for poste, pct in zip(OPENSOLAR_POSTES, valeurs)
                           if pct > 0.0]
                cascade = _cascade_de_saisies(saisies)
                attendu = _compose(pct for _p, pct, _r in saisies)
                self.assertAlmostEqual(cascade['total_pct'],
                                       round(attendu, 1), delta=0.1)

    def test_opensolar_le_micro_onduleur_perd_moins_que_la_chaine(self):
        totaux = {}
        for configuration, valeurs in OPENSOLAR_PAR_CONFIGURATION.items():
            totaux[configuration] = _compose(valeurs)
        self.assertLess(totaux['micro_onduleur'],
                        totaux['chaine_optimiseur'])
        self.assertLess(totaux['chaine_optimiseur'], totaux['chaine'])

    def test_la_propriete_arithmetique_publiee_par_aurora(self):
        """« 1−(1−4%)×(1−3%) = 6,88 % », rejouée sur DEUX étapes réelles."""
        (premiere, seconde), attendu = AURORA_PROPRIETE
        cascade = _cascade_de_saisies([
            ('salissure', premiere, AURORA_URL),
            ('lid', seconde, AURORA_URL)])
        etapes = {etape['etape']: etape for etape in cascade['etapes']}
        entree = etapes['salissure']['kwh_avant']
        sortie = etapes['lid']['kwh_apres']
        mesure = (1.0 - sortie / entree) * 100.0
        self.assertAlmostEqual(mesure, attendu, delta=0.01)
        self.assertAlmostEqual(_compose((premiere, seconde)), attendu,
                               delta=0.01)
        self.assertAlmostEqual(cascade['total_pct'], round(attendu, 1),
                               delta=0.05)


class AucunChiffreConcurrentDansLeProduitTest(SimpleTestCase):
    """Ces nombres sont des ENTRÉES de test — jamais des défauts du produit.

    CE QUE LA GARDE REGARDE : les constantes de niveau MODULE et les valeurs
    par défaut de paramètres, dans ``apps/calepinage/services/``, dont le NOM
    désigne un poste de pertes. C'est là, et seulement là, qu'un défaut de
    concurrent pourrait s'installer.

    CE QU'ELLE NE REGARDE PAS, ET POURQUOI : un ``0.5`` au milieu d'une
    formule géométrique n'est pas une valeur d'Aurora, et un ``2`` non plus.
    Une garde qui crie au loup sur chaque littéral ne garde rien ; celle-ci
    vise l'endroit exact où la faute se commet.
    """

    NOMS_DE_POSTE = ('LID', 'SALISSURE', 'SOILING', 'MISMATCH', 'OMBRAGE',
                     'SHADING', 'DISPONIB', 'CABLAGE', 'CONNEX', 'OHMIQUE',
                     'ONDULEUR', 'WIRING')

    def valeurs_interdites(self):
        valeurs = set(AURORA_DEFAUTS_PCT.values())
        for triplet in OPENSOLAR_PAR_CONFIGURATION.values():
            valeurs.update(triplet)
        valeurs.discard(0.0)
        # Les mêmes valeurs écrites en COEFFICIENT (1,5 % → 0,015).
        return valeurs | {round(valeur / 100.0, 6) for valeur in valeurs}

    def test_aucun_defaut_de_concurrent_dans_les_services(self):
        racine = (pathlib.Path(__file__).resolve().parents[1] / 'services')
        interdites = self.valeurs_interdites()
        fautes = []
        for chemin in sorted(racine.rglob('*.py')):
            arbre = ast.parse(chemin.read_text(encoding='utf-8'))
            for noeud in arbre.body:
                fautes += self._fautes_du_noeud(chemin, noeud, interdites)
        self.assertEqual(fautes, [], '\n'.join(fautes))

    def _fautes_du_noeud(self, chemin, noeud, interdites):
        if isinstance(noeud, (ast.Assign, ast.AnnAssign)):
            cibles = ([noeud.target] if isinstance(noeud, ast.AnnAssign)
                      else noeud.targets)
            noms = [fils.id for cible in cibles
                    for fils in ast.walk(cible) if isinstance(fils, ast.Name)]
            return self._fautes(chemin, noeud, noms, interdites)
        if isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef)):
            defauts = list(noeud.args.defaults) + [
                valeur for valeur in noeud.args.kw_defaults if valeur]
            fautes = []
            for defaut in defauts:
                fautes += self._fautes(chemin, defaut, [noeud.name],
                                       interdites)
            return fautes
        return []

    def _fautes(self, chemin, noeud, noms, interdites):
        if not any(poste in nom.upper() for nom in noms
                   for poste in self.NOMS_DE_POSTE):
            return []
        fautes = []
        for fils in ast.walk(noeud):
            if not isinstance(fils, ast.Constant) or isinstance(fils.value,
                                                                bool):
                continue
            if not isinstance(fils.value, (int, float)):
                continue
            if float(fils.value) in interdites:
                fautes.append(
                    f'{chemin.name}:{getattr(fils, "lineno", "?")} — '
                    f'« {", ".join(noms)} » vaut {fils.value}, qui est une '
                    "valeur par défaut publiée par un concurrent. Elle n'a "
                    'sa place que dans un fichier de TEST, avec son URL.')
        return fautes

    def test_la_garde_voit_une_faute_qu_on_lui_montre(self):
        """Une garde qu'on n'a jamais vue mordre ne garde rien."""
        # Nom et valeur concaténés : la garde de test_politique_pertes_pvgis
        # ne doit pas lire ce FAUX comme une perte posée en dur.
        faux = ast.parse('PERTE_LID_PAR_DEFAUT_PCT' + ' = ' + '1.5\n')
        fautes = self._fautes_du_noeud(pathlib.Path('faux.py'),
                                       faux.body[0],
                                       self.valeurs_interdites())
        self.assertEqual(len(fautes), 1)
        self.assertIn('1.5', fautes[0])


if __name__ == '__main__':  # pragma: no cover — chemin « --write » seulement
    print(ecrire_le_golden(sys.argv[1:]))
