"""SPL242 — golden de la découpe de ``etude_horaire.py`` (SPL254-SPL258).

``etude_horaire.py`` (3403 lignes, propriétaire moteur) est découpé en cinq
régions déplacées vers le sous-paquet ``apps/ventes/horaire/``. Ce module porte
la preuve « move only » de chaque déplacement, capturée sur le code d'AVANT :

(a) ``golden/split_eh_<region>.json`` — empreinte AST normalisée
    (``split_golden.empreintes`` : ``ImportFrom.level`` ramené à 0) de chaque
    symbole de la région ;
(b) ``DEPLACEMENTS`` — une entrée par région. Tant que son SPL n'a pas atterri
    (``actif=False``), le golden doit rester IDENTIQUE à la source actuelle
    (une tâche étrangère qui édite un symbole avant son déplacement rougit
    ici : recapturer avant de déplacer). Le SPL de la région passe ``actif`` à
    ``True`` dans le MÊME commit que le déplacement ;
(c) ``golden/split_eh_comportement.json`` — digests de COMPORTEMENT des
    vraies fonctions (jamais mockées), ``jour_reference`` figé sur deux dates
    dont une fenêtre de Ramadan : tables ``_num`` / ``saison_du_mois``,
    séries MAD → kWh, priorité de ``profil_depuis_factures``, bornes de
    cohérence kWh/factures, estimation de consommation, jours types,
    couverture batterie, production, appartenance d'une ligne à une option,
    les cinq fonctions de recharge VE nocturne.

Capture du golden de comportement (une fois, sur le code d'avant découpe —
identique après, puisque (a) prouve la copie fidèle) :
    SPLIT_GOLDEN_CAPTURE=1 python manage.py test \\
        apps.ventes.tests.test_split_devis_horaire.ComportementHoraireTests

Lancer :
    docker compose exec django_core python manage.py test \\
        apps.ventes.tests.test_split_devis_horaire -v 2
"""
import datetime
import importlib
import math
import os
from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.ventes import courbes_journalieres as CJ
from apps.ventes.tests import split_golden as sg

SOURCE = 'apps/ventes/etude_horaire.py'

#: Une entrée par région : (golden, module cible, SPL qui la déplace, actif).
DEPLACEMENTS = {
    'base': ('split_eh_base', 'apps/ventes/horaire/base.py', 'SPL254', True),
    'public': ('split_eh_public', 'apps/ventes/horaire/public.py', 'SPL255',
               True),
    'bat': ('split_eh_bat', 'apps/ventes/horaire/batterie_lignes.py',
            'SPL256', True),
    'conso': ('split_eh_conso', 'apps/ventes/horaire/conso.py', 'SPL257',
              True),
    've': ('split_eh_ve', 'apps/ventes/horaire/ve_nocturne.py', 'SPL258',
           True),
}

#: Modules où vit chaque fonction, avant ou après la découpe.
_MODULES = (
    'apps.ventes.etude_horaire', 'apps.ventes.horaire.base',
    'apps.ventes.horaire.public', 'apps.ventes.horaire.batterie_lignes',
    'apps.ventes.horaire.conso', 'apps.ventes.horaire.ve_nocturne',
)

#: Deux dates de référence : une ordinaire, une en fenêtre de Ramadan (2027 :
#: 8 fév → 8 mars, table ``ramadan.RAMADAN_PLAGES``).
JOURS_REFERENCE = (datetime.date(2026, 10, 1), datetime.date(2027, 2, 20))
TAILLES = (5.0, 10.0, 15.0, 20.0)


class DeplacementsHoraireTests(SimpleTestCase):
    """(a)+(b) — identité AST de chaque région, rouge d'abord."""

    def test_cinq_regions_disjointes_et_non_vides(self):
        vus = {}
        for region, (golden, _cible, _spl, _actif) in DEPLACEMENTS.items():
            symboles = sg.charger_golden(golden)
            self.assertTrue(symboles, f'golden {golden} vide')
            for nom in symboles:
                self.assertNotIn(nom, vus, f'{nom} dans {region} et {vus.get(nom)}')
                vus[nom] = region
        self.assertEqual(len(vus), 40)

    def test_regions_en_attente_identiques_a_la_source(self):
        for region, (golden, _cible, spl, actif) in DEPLACEMENTS.items():
            if actif:
                continue
            with self.subTest(region=region, spl=spl):
                attendu = sg.charger_golden(golden)
                self.assertEqual(
                    sg.empreintes(SOURCE, sorted(attendu)), attendu,
                    f'{region} : symbole édité depuis la capture — recapturer '
                    f'le golden AVANT {spl}')

    def test_regions_deplacees_fideles(self):
        for region, (golden, cible, spl, actif) in DEPLACEMENTS.items():
            if not actif:
                continue
            with self.subTest(region=region, spl=spl):
                sg.verifier_deplacement(golden, cible, SOURCE)


def _f(nom):
    """La VRAIE fonction ``nom``, où qu'elle vive (avant ou après découpe)."""
    for chemin in _MODULES:
        try:
            module = importlib.import_module(chemin)
        except ImportError:
            continue
        if nom in vars(module):
            return vars(module)[nom]
    raise AssertionError(f'{nom} introuvable dans {_MODULES}')


def _couches_ve(creneau=None, km=300):
    entree = {'voiture_electrique': True, 've_km_semaine': km}
    if creneau:
        entree['ve_creneau'] = creneau
    return CJ.composer_equipements(entree)


def _sur(appel):
    """Résultat OU type d'exception : une levée fait partie du comportement."""
    try:
        return appel()
    except Exception as exc:  # noqa: BLE001 — caractérisation
        return f'<{type(exc).__name__}>'


class ComportementHoraireTests(SimpleTestCase):
    """Digests de comportement — identiques avant/après la découpe."""

    def _scenarios(self):
        res = {}
        num = _f('_num')
        res['num'] = [num(v) for v in (None, '3.5', 'abc', 7, 2.25)] + [
            num(None, 9.0), num('x', -1.0), math.isnan(num(float('nan')))]
        res['saison_du_mois'] = [_f('saison_du_mois')(m) for m in range(14)]
        res['mois_ete'] = sorted(_f('MOIS_ETE_FACTURE'))

        mad = _f('serie_mad_mensuelle')
        res['serie_mad'] = [mad(800), mad(800, 1200, True), mad(800, 1200)]
        kwh = _f('serie_kwh_depuis_mad')
        res['serie_kwh'] = [kwh(mad(800)), kwh(mad(800, 1200, True)),
                            kwh(mad(800), tppan=False)]
        profil = _f('profil_depuis_factures')
        res['profil'] = [
            _sur(lambda: profil(facture_hiver_mad=800)),
            _sur(lambda: profil(conso_kwh_mensuelle_unique=450)),
            _sur(lambda: profil(facture_hiver_mad=800,
                                conso_kwh_mensuelle_unique=450)),
            _sur(lambda: profil(conso_kwh_mensuelles=[300 + 10 * i
                                                      for i in range(12)])),
            _sur(lambda: profil()),
        ]
        coherence = _f('coherence_kwh_declare_factures')
        res['coherence'] = [
            _sur(lambda k=k: coherence(k, [800.0] * 12))
            for k in (None, 50, 200, 400, 900, 3000)]
        res['ratios'] = [_f('RATIO_KWH_FACTURE_MIN'),
                         _f('RATIO_KWH_FACTURE_MAX'),
                         _f('CODE_KWH_INCOHERENT'),
                         _f('MESSAGE_KWH_INCOHERENT')]

        conso = [300.0 + 20 * i for i in range(12)]
        ve = _couches_ve()
        res['estimation'] = [
            _sur(lambda: _f('estimation_conso_mensuelle')(conso, {})),
            _sur(lambda: _f('estimation_conso_mensuelle')(conso, ve))]
        for jour in JOURS_REFERENCE:
            cle = jour.isoformat()
            res[f'jours_types_{cle}'] = _sur(lambda jour=jour: _f(
                'jours_types_publics')(kwc=6.0, conso_kwh_mensuelles=conso,
                                       ville='Casablanca',
                                       jour_reference=jour))
            res[f'couverture_{cle}'] = _sur(lambda jour=jour: _f(
                'couverture_batterie_publique')(
                    kwc=6.0, conso_kwh_mensuelles=conso,
                    capacite_utile_pack_kwh=4.8, nb_packs_max=3,
                    ville='Casablanca', equipements=ve,
                    jour_reference=jour))
        res['production_annuelle'] = _sur(lambda: _f(
            'production_annuelle_pour_kwc')(6.0, ville='Casablanca'))
        res['production_saison'] = _sur(lambda: _f(
            'production_journaliere_par_saison')(6.0, ville='Casablanca'))

        dans = _f('ligne_dans_option')
        res['ligne_dans_option'] = [
            dans(SimpleNamespace(variante=v), o)
            for v in ('', 'sans', 'avec', None)
            for o in (None, 'sans', 'avec')]
        res['roles_onduleur'] = sorted(_f('ROLES_ONDULEUR'))
        res['rendement_sources'] = [_f('RENDEMENT_SOURCE_HYPOTHESE'),
                                    _f('RENDEMENT_SOURCE_FICHE')]

        for creneau in (None, 'nuit', 'jour', 'soir'):
            couches = _couches_ve(creneau)
            cle = creneau or 'defaut'
            res[f've_{cle}'] = [
                _sur(lambda: _f('_couche_ve_nocturne')(couches)),
                _sur(lambda: _f('recharge_ve_nocturne_kwh_jour')(couches)),
                _sur(lambda: _f('besoin_stockage_avec_recharge_ve')(
                    8.0, couches, TAILLES)),
                _sur(lambda: _f('equipements_sans_recharge_ve_nocturne')(
                    couches)),
                _sur(lambda: _f('plancher_batterie_recharge_ve')(
                    8.0, couches, TAILLES)),
            ]
        res['ve_absent'] = [
            _f('recharge_ve_nocturne_kwh_jour')(None),
            _f('recharge_ve_nocturne_kwh_jour')({}),
            _sur(lambda: _f('plancher_batterie_recharge_ve')(8.0, {}, TAILLES))]
        return res

    def test_digests_identiques(self):
        digests = {nom: sg.digest(val) for nom, val in self._scenarios().items()}
        if os.environ.get('SPLIT_GOLDEN_CAPTURE') == '1':
            sg.ecrire_golden('split_eh_comportement', {'comportement': digests})
        attendu = sg.charger_golden('split_eh_comportement').get('comportement')
        self.assertTrue(
            attendu, 'golden de comportement non capturé : lancer une fois '
            'SPLIT_GOLDEN_CAPTURE=1 sur ce module (voir la docstring)')
        self.assertEqual(digests, attendu)
