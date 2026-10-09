"""SPL244 — golden de la découpe de ``domain/cycle_vie.py``, ``domain/creation.py``
et ``domain/pipeline.py`` (SPL262-SPL268).

Sept régions de ces trois fichiers-dieux partent vers sept modules neufs de
``apps/ventes/domain/``. Ce module porte la preuve « move only » de chaque
déplacement, capturée sur le code d'AVANT :

(a) ``golden/split_dm_<region>.json`` — empreinte AST normalisée
    (``split_golden.empreintes`` : ``ImportFrom.level`` ramené à 0) de chaque
    symbole de la région ;
(b) ``DEPLACEMENTS`` — une entrée par région. Tant que son SPL n'a pas atterri
    (``actif=False``), le golden doit rester IDENTIQUE à la source actuelle
    (une tâche étrangère qui édite un symbole avant son déplacement rougit
    ici : recapturer avant de déplacer). Le SPL de la région passe ``actif`` à
    ``True`` dans le MÊME commit que le déplacement ;
(c) ``golden/split_dm_comportement.json`` — digests de COMPORTEMENT des vraies
    fonctions (jamais mockées ; seules leurs LECTURES catalogue le sont, comme
    dans ``test_qjr_pipeline_verifier``), résolues par :func:`module_de` où
    qu'elles vivent :
      * ``pur`` (sans base) : ``verifier`` sur les cas ``MSG_*``,
        ``message_batterie_incompatible``, ``estampiller_variante`` (cas
        neutres), ``_cles_appariement`` / ``diff_configurations_devis``
        (appariement positionnel et par identité stable), ``_valeur_json``,
        ``corps_note_refus_auto_devis`` ;
      * ``base`` (avec base) : ``build_devis_from_layout`` (1 et 2 options,
        acier / aluminium, paires MPPT), ``configuration_devis_contenu`` et
        ``capturer_configuration_devis`` (dédoublonnage), ``mark_devis_sent``,
        ``reviser_devis`` et ``renouveler_devis``, ``cloner_devis`` /
        ``dupliquer_devis`` / ``save_devis_as_preset``, ``build_devis_auto`` et
        ``composer_devis_residentiel`` — dumps de ``Devis`` / ``LigneDevis``
        (ids, références datées et dates normalisés), statuts compris
        (brouillon/envoye/accepte/refuse/expire inchangés, règle #4).
(d) :func:`module_de` — le module de ``domain/`` qui DÉFINIT un symbole : les
    gardes qui patchaient ou lisaient « ``domain.creation`` » par son nom
    (test_qjr243, test_deux_optimiseurs) visent désormais le PORTEUR, jamais
    un nom importé (un patch posé sur un nom ré-importé réussit mais
    n'intercepte plus rien — faux vert).

Capture du golden de comportement (une fois, sur le code d'avant découpe —
identique après, puisque (a) prouve la copie fidèle) :
    docker compose exec -e SPLIT_GOLDEN_CAPTURE=1 django_core \\
        python manage.py test apps.ventes.tests.test_split_devis_domaine \\
        --keepdb

Lancer :
    docker compose exec django_core python manage.py test \\
        apps.ventes.tests.test_split_devis_domaine -v 2
"""
import functools
import importlib
import os
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from apps.ventes.tests import split_golden as sg

DOMAINE = Path(sg.DJANGO_CORE) / 'apps' / 'ventes' / 'domain'

#: Une entrée par région : (golden, source, cible, SPL qui la déplace, actif).
DEPLACEMENTS = {
    'hist': ('split_dm_hist', 'apps/ventes/domain/cycle_vie.py',
             'apps/ventes/domain/historique_config.py', 'SPL262', True),
    'rev': ('split_dm_rev', 'apps/ventes/domain/cycle_vie.py',
            'apps/ventes/domain/revision.py', 'SPL263', True),
    'envoi': ('split_dm_envoi', 'apps/ventes/domain/cycle_vie.py',
              'apps/ventes/domain/envoi.py', 'SPL264', True),
    'comp': ('split_dm_comp', 'apps/ventes/domain/pipeline.py',
             'apps/ventes/domain/etape_composer.py', 'SPL265', True),
    'cal': ('split_dm_cal', 'apps/ventes/domain/creation.py',
            'apps/ventes/domain/creation_calepinage.py', 'SPL266', True),
    'auto': ('split_dm_auto', 'apps/ventes/domain/creation.py',
             'apps/ventes/domain/creation_auto.py', 'SPL267', True),
    'clone': ('split_dm_clone', 'apps/ventes/domain/creation.py',
              'apps/ventes/domain/creation_clone.py', 'SPL268', True),
}

#: Nombre total de symboles épinglés (somme des sept régions).
NB_SYMBOLES = 62  # ACAL : build_devis_depuis_calepinage_retenu retiré (CAL185 remplacé)


@functools.lru_cache(maxsize=None)
def _symboles(chemin):
    return frozenset(sg.symboles_de_niveau_module(chemin))


def module_de(symbole):
    """Le module de ``apps.ventes.domain`` qui DÉFINIT ``symbole`` au niveau module.

    Un nom seulement IMPORTÉ (pont de bas de fichier) ne compte pas : c'est le
    PORTEUR du corps qu'il faut patcher ou lire. Zéro ou plusieurs porteurs =
    échec bruyant (symbole perdu, ou jumeau).
    """
    porteurs = [
        chemin.stem for chemin in sorted(DOMAINE.glob('*.py'))
        if symbole in _symboles(chemin)
    ]
    if len(porteurs) != 1:
        raise AssertionError(
            f'{symbole} : {len(porteurs)} porteur(s) dans domain/ ({porteurs}) '
            '— attendu exactement un.')
    return importlib.import_module(f'apps.ventes.domain.{porteurs[0]}')


def _f(nom):
    """La VRAIE fonction ``nom``, où qu'elle vive (avant ou après découpe)."""
    return getattr(module_de(nom), nom)


def _sur(appel):
    """Résultat OU type d'exception : une levée fait partie du comportement."""
    try:
        return appel()
    except Exception as exc:  # noqa: BLE001 — caractérisation
        return f'<{type(exc).__name__}>'


class DeplacementsDomaineTests(SimpleTestCase):
    """(a)+(b) — identité AST de chaque région, rouge d'abord."""

    def test_sept_regions_disjointes_et_non_vides(self):
        vus = {}
        for region, (golden, source, _c, _s, _a) in DEPLACEMENTS.items():
            symboles = sg.charger_golden(golden)
            self.assertTrue(symboles, f'golden {golden} vide')
            for nom in symboles:
                cle = (source, nom)
                self.assertNotIn(cle, vus, f'{nom} dans {region} et {vus.get(cle)}')
                vus[cle] = region
        self.assertEqual(len(vus), NB_SYMBOLES)

    def test_regions_en_attente_identiques_a_la_source(self):
        for region, (golden, source, _cible, spl, actif) in DEPLACEMENTS.items():
            if actif:
                continue
            with self.subTest(region=region, spl=spl):
                attendu = sg.charger_golden(golden)
                self.assertEqual(
                    sg.empreintes(source, sorted(attendu)), attendu,
                    f'{region} : symbole édité depuis la capture — recapturer '
                    f'le golden AVANT {spl}')

    def test_regions_deplacees_fideles(self):
        for region, (golden, source, cible, spl, actif) in DEPLACEMENTS.items():
            if not actif:
                continue
            with self.subTest(region=region, spl=spl):
                sg.verifier_deplacement(golden, cible, source)

    def test_module_de_vise_le_porteur(self):
        for region, (golden, _s, _c, _spl, _a) in DEPLACEMENTS.items():
            for nom in sg.charger_golden(golden):
                with self.subTest(region=region, symbole=nom):
                    self.assertIn(nom, vars(module_de(nom)))


# ── (c) comportement ──────────────────────────────────────────────────────
class _CatalogueFictif:
    """Remplace les trois lectures catalogue de ``verifier``, dans le module
    qui le PORTE (patron de ``test_qjr_pipeline_verifier``)."""

    def __init__(self, *, reseau=True, hybride=True, batterie=True, plage=None):
        self.reseau, self.hybride = reseau, hybride
        self.batterie, self.plage = batterie, plage
        self._anciens = {}
        self._module = module_de('verifier')

    def __enter__(self):
        def _pick(company, predicat, *, role=None, gamme=None, **_):
            if role == 'onduleur_reseau':
                return object() if self.reseau else None
            if role == 'onduleur_hybride':
                return object() if self.hybride else None
            return None

        m = self._module
        self._anciens = {
            nom: getattr(m, nom) for nom in (
                '_pick_product', '_pick_batterie',
                '_plage_batterie_de_l_onduleur')}
        m._pick_product = _pick
        m._pick_batterie = (
            lambda company, onduleur=None: object() if self.batterie else None)
        m._plage_batterie_de_l_onduleur = lambda onduleur: self.plage
        return self

    def __exit__(self, *exc):
        for nom, valeur in self._anciens.items():
            setattr(self._module, nom, valeur)
        return False


_SNAP_A = {
    'lignes': [
        {'type_ligne': 'section', 'designation': 'Kit', 'ordre': 0},
        {'type_ligne': 'produit', 'produit': 7, 'designation': 'Panneau',
         'quantite': '9', 'prix_unitaire': '1450.00', 'variante': '', 'ordre': 1},
        {'type_ligne': 'produit', 'produit': 7, 'designation': 'Panneau',
         'quantite': '3', 'prix_unitaire': '1450.00', 'variante': 'avec',
         'ordre': 2},
        {'type_ligne': 'produit', 'produit_id': 9, 'designation': 'Onduleur',
         'quantite': '1', 'prix_unitaire': '14000.00', 'ordre': 3},
    ],
    'remise_globale': '0', 'echeancier': None,
    'etude': {'scenario': 'sans', 'mppt_paires': 1},
}
_SNAP_B = {
    'lignes': [
        {'type_ligne': 'produit', 'produit': 7, 'designation': 'Panneau',
         'quantite': '10', 'prix_unitaire': '1450.00', 'variante': '', 'ordre': 0},
        {'type_ligne': 'section', 'designation': 'Kit', 'ordre': 1},
        {'type_ligne': 'produit', 'produit': 11, 'designation': 'Batterie',
         'quantite': '1', 'prix_unitaire': '16000.00', 'variante': 'avec',
         'ordre': 2},
        {'type_ligne': 'note', 'designation': 'Pose incluse', 'ordre': 3},
    ],
    'remise_globale': '5', 'echeancier': [{'pct': 50}, {'pct': 50}],
    'etude': {'scenario': 'les_deux', 'heures_pompage': 7},
}


class ComportementPurTests(SimpleTestCase):
    """Digests de comportement SANS base — identiques avant/après découpe."""

    def _scenarios(self):
        res = {}
        intention = _f('IntentionComposition')

        def verifier(scenario, nb=9, kwc=6.39, **catalogue):
            with _CatalogueFictif(**catalogue):
                return _f('verifier')(intention(
                    company=None, nb_panneaux=nb, kwc=kwc, scenario=scenario))

        res['verifier'] = [
            _sur(lambda: verifier('sans')),
            _sur(lambda: verifier('sans', reseau=False)),
            _sur(lambda: verifier('avec', reseau=False)),
            _sur(lambda: verifier('avec', hybride=False)),
            _sur(lambda: verifier('avec', batterie=False)),
            _sur(lambda: verifier('avec', batterie=False, plage=(160, 700))),
            _sur(lambda: verifier('les_deux')),
            _sur(lambda: verifier('les_deux', reseau=False, hybride=False,
                                  batterie=False)),
            _sur(lambda: verifier('sans', nb=0, kwc=0)),
        ]
        res['messages'] = [_f(nom) for nom in (
            'MSG_AUCUN_PANNEAU', 'MSG_SANS_ONDULEUR_HYBRIDE',
            'MSG_SANS_ONDULEUR_RESEAU', 'MSG_SANS_BATTERIE',
            'MSG_SANS_ONDULEUR_OFFGRID')]
        res['batterie_incompatible'] = [
            _sur(lambda p=p: _f('message_batterie_incompatible')(p))
            for p in ((160, 700), (40.0, 60.5), (48, 48))]
        res['scenarios'] = [
            _f('COMPOSITION_SANS'), _f('COMPOSITION_AVEC'),
            _f('COMPOSITION_LES_DEUX'), list(_f('SCENARIOS_COMPOSABLES')),
            list(_f('SCENARIOS_DEMANDABLES')), _f('_MARQUE_AUTO_DEVIS'),
            list(_f('FAMILLES_KIT_CAL185')), _f('TYPE_CGV_GELEES'),
            list(_f('_CHAMPS_POSITIONNELS'))]
        vide = []
        res['estampiller'] = [
            _f('estampiller_variante')(vide, 'avec') is vide,
            _f('estampiller_variante')(['x'], '') == ['x'],
        ]
        res['valeur_json'] = [_f('_valeur_json')(v) for v in (
            Decimal('12.50'), 3, 'a', None, [1])]
        res['appariement'] = sorted(_f('_cles_appariement')(_SNAP_A['lignes']))
        diff = _f('diff_configurations_devis')
        res['diff_ab'] = diff(_SNAP_A, _SNAP_B)
        res['diff_ba'] = diff(SimpleNamespace(contenu=_SNAP_B), _SNAP_A)
        res['diff_aa'] = diff(_SNAP_A, dict(_SNAP_A))
        res['diff_vide'] = diff(None, {})
        corps = _f('corps_note_refus_auto_devis')
        res['note_refus'] = [
            corps(SimpleNamespace(field='facture_hiver')),
            corps(ValueError('kWh incohérents')),
            corps(Exception()),
        ]
        return res

    def test_digests_identiques(self):
        _verifier_digests(self, 'pur', self._scenarios())


# ── Base : dumps de Devis / LigneDevis ────────────────────────────────────
User = get_user_model()

CATALOGUE = [
    ('Panneau Canadien Solar 710W', 'PAN710', '1450'),
    ('Onduleur réseau Huawei 5kW Monophasé', 'ONDR5', '14000'),
    ('Onduleur hybride Deye 5kW Monophasé', 'ONDH5', '17000'),
    ('Batterie Dyness 5 kWh', 'BAT5', '16000'),
    ('Batterie Dyness 10 kWh', 'BAT10', '30000'),
    ('Structures acier', 'STR-ACIER', '500'),
    ('Structures aluminium', 'STR-ALU', '850'),
    ('Socles', 'SOC', '80'),
    ('Câble solaire Nexans 6 mm² (au mètre)', 'CAB-DC-M', '14.40'),
    ('Câble de terre Nexans 6 mm² (au mètre)', 'CAB-TER-M', '14.40'),
    ('Accessoires', 'ACC', '2000'),
    ('Tableau De Protection AC/DC', 'TAB', '2000'),
    ('Installation', 'INST', '4800'),
    ('Transport', 'TRANS', '1000'),
]


def _dump_devis(devis):
    """Champs MÉTIER d'un devis (ni id, ni référence datée, ni horodatage)."""
    if not hasattr(devis, 'lignes'):
        return devis
    devis.refresh_from_db()
    return {
        'statut': devis.statut,
        'version': getattr(devis, 'version', None),
        'is_active': getattr(devis, 'is_active', None),
        'remplace': getattr(devis, 'superseded_by_id', None) is not None,
        'mode_installation': devis.mode_installation,
        'remise_globale': str(devis.remise_globale),
        'taux_tva': str(devis.taux_tva),
        'total_ht': str(getattr(devis, 'total_ht', '')),
        'total_ttc': str(getattr(devis, 'total_ttc', '')),
        'date_validite': getattr(devis, 'date_validite', None),
        'clauses': devis.clauses_appliquees,
        'lignes': [
            {'designation': li.designation, 'quantite': str(li.quantite),
             'prix_unitaire': str(li.prix_unitaire),
             'variante': getattr(li, 'variante', ''),
             'type_ligne': getattr(li, 'type_ligne', ''),
             'optionnelle': getattr(li, 'optionnelle', False)}
            for li in devis.lignes.order_by('ordre', 'id')],
    }


class ComportementBaseTests(TestCase):
    """Digests de comportement AVEC base — identiques avant/après découpe."""

    def setUp(self):
        from apps.crm.models import Lead
        from apps.stock.models import Produit
        from authentication.models import Company
        self.company, _ = Company.objects.get_or_create(
            slug='spl244-domaine', defaults={'nom': 'spl244-domaine'})
        self.user = User.objects.create_user(
            username='spl244-domaine', password='x', company=self.company,
            role_legacy='admin')
        for nom, sku, prix in CATALOGUE:
            Produit.objects.create(
                company=self.company, nom=nom,
                sku='%s-%s' % (sku, self.company.pk),
                prix_vente=Decimal(prix), prix_achat=Decimal('1'),
                quantite_stock=1000)
        self.lead = Lead.objects.create(
            company=self.company, nom='Domaine', prenom='SPL244',
            email='spl244@example.com')

    def _layout(self, scenario='reseau'):
        return {'result': {'panels': 9, 'kwc': 6.39}, 'panelWatt': 710,
                'scenario': scenario}

    def _depuis_layout(self, **kw):
        return _f('build_devis_from_layout')(
            layout=kw.pop('layout', self._layout()), user=self.user,
            company=self.company, lead=self.lead, **kw)

    def _scenarios(self):
        res = {}
        res['layout_sans_acier'] = _sur(lambda: _dump_devis(
            self._depuis_layout()))
        res['layout_alu_mppt3'] = _sur(lambda: _dump_devis(
            self._depuis_layout(mppt_paires=3, structure_type='aluminium')))
        res['layout_deux_options'] = _sur(lambda: _dump_devis(
            self._depuis_layout(layout=self._layout('hybride'),
                                deux_options=True)))
        res['apercu_residentiel'] = _sur(lambda: _f(
            'composer_devis_residentiel')(
                company=self.company, nb_panneaux=9, panel_watt=710,
                scenario='sans', mppt_paires=3, structure_type='aluminium'))

        devis = self._depuis_layout()
        contenu = _f('configuration_devis_contenu')
        res['configuration'] = _sur(lambda: contenu(devis))
        capturer = _f('capturer_configuration_devis')
        premier = _sur(lambda: capturer(devis, user=self.user))
        second = _sur(lambda: capturer(devis, user=self.user))
        res['capture_dedoublonnee'] = [premier is None, second is None]

        res['envoi'] = _sur(lambda: (
            _f('mark_devis_sent')(devis=devis, user=self.user),
            _dump_devis(devis))[1])
        res['revision'] = _sur(lambda: _dump_devis(
            _f('reviser_devis')(devis, user=self.user)))
        res['revision_v1'] = _sur(lambda: _dump_devis(devis))

        source = self._depuis_layout()
        res['dupliquer'] = _sur(lambda: _dump_devis(
            _f('dupliquer_devis')(source, user=self.user)))
        res['cloner'] = _sur(lambda: _dump_devis(
            _f('cloner_devis')(source, user=self.user)))
        res['modele'] = _sur(lambda: str(type(
            _f('save_devis_as_preset')(source, 'Modèle SPL244',
                                       user=self.user)).__name__))
        res['renouveler_brouillon'] = _sur(lambda: _dump_devis(
            _f('renouveler_devis')(source, user=self.user)))
        res['auto'] = _sur(lambda: _dump_devis(_f('build_devis_auto')(
            lead=self.lead, user=self.user, company=self.company)))
        return res

    def test_digests_identiques(self):
        _verifier_digests(self, 'base', self._scenarios(),
                          cles_ids=CLES_IDS_BASE)


#: Les scénarios AVEC base exposent la clé étrangère ``produit`` (pk SQL) :
#: sa valeur dépend de la séquence de la base (migrations de données, ordre
#: des tests, shard CI) — pas du comportement. Elle est figée comme un id ;
#: l'identité du produit reste vérifiée par ``designation``/``role``/prix.
#: ADEV18 — l'instantané de configuration porte l'en-tête : ``client`` (pk)
#: et ``date_validite`` (relative au jour) dépendent de la base / de la date.
CLES_IDS_BASE = sg.CLES_IDS_PAR_DEFAUT | {'produit', 'produit_id', 'client', 'date_validite'}


def _verifier_digests(test, cle, scenarios, cles_ids=sg.CLES_IDS_PAR_DEFAUT):
    digests = {nom: sg.digest(val, cles_ids) for nom, val in scenarios.items()}
    if os.environ.get('SPLIT_GOLDEN_CAPTURE') == '1':
        golden = sg.charger_golden('split_dm_comportement')
        golden[cle] = digests
        sg.ecrire_golden('split_dm_comportement', golden)
    attendu = sg.charger_golden('split_dm_comportement').get(cle)
    test.assertTrue(
        attendu, f'golden de comportement « {cle} » non capturé : lancer une '
        'fois SPLIT_GOLDEN_CAPTURE=1 sur ce module (voir la docstring)')
    test.assertEqual(digests, attendu)
