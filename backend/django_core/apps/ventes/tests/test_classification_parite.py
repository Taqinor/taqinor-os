"""QJR91 (M4, audit L3 du 29/08/2026) — PARITÉ DES CLASSIFIEURS : PDF vs ÉCRAN.

CE QUE CE FICHIER PROTÈGE, ET POURQUOI IL EXISTE.

``apps/ventes/quote_engine/builder.py`` et
``frontend/src/features/ventes/solar.js`` classifient CHACUN de leur côté la
MÊME désignation de ligne de devis, sans jamais lire une table commune. Le
commentaire de ``builder.py:258-261`` PRÉTEND être le « miroir de solar.js » —
et c'est FAUX depuis le 19/08 : exactement le mode d'échec qu'un commentaire ne
peut jamais prévenir et qu'une fixture partagée prévient toujours. La fixture
QJR2 (``apps/ventes/contract_samples/classification_lignes.json``) est cette
table commune ; ce fichier en est la moitié PDF, son jumeau JavaScript
(``frontend/src/features/ventes/classifieurs.parite.test.mjs``) la moitié
écran. Mêmes entrées, mêmes valeurs attendues, un seul fichier source de
vérité.

ÉTAT ATTENDU AUJOURD'HUI (QJR91 pose la garde, QJR92 met au vert) :

* ROUGE ici — cas « Batterie Deye BOS-B-Pack », capacité batterie.
  ``builder.py:263 BATTERY_DEFAULT_KWH = 5.0``, appliqué ``builder.py:290``,
  fait contribuer 5,0 kWh à une ligne dont la désignation ne porte AUCUN kWh
  lisible : un nombre FABRIQUÉ, publié sur un PDF client. L'ÉCRAN a raison
  (règle BAT5DEF du 26/08 : contribuer 0, faire remonter l'inconnu) — c'est la
  règle fondateur absolue « zéro chiffre inventé ». QJR92b retire ce défaut
  ici ET dans ``public_views.py:1862-1886`` (même défaut, page publique).
* VERT ici — cas « Module PV 550 W » : ``_is_panel`` le classe correctement
  panneau. C'est l'ÉCRAN qui est rouge sur ce cas (``solar.js:947 isPanel`` ne
  teste que le mot « panneau », et le devis est refusé à l'enregistrement comme
  n'ayant aucun panneau) — QJR92a y élargit ``isPanel``.

Aucune de ces deux corrections n'est dans ce commit : QJR91 CONSTATE, QJR92
corrige.
"""
import json
from pathlib import Path
from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.ventes.domain.catalogue import _parse_kwh, classer_produit
from apps.ventes.quote_engine.lignes_classement import (
    _battery_kwh_from_items,
    _is_battery,
    _is_hybrid_inverter,
    _is_inverter,
    _is_offgrid_inverter,
    _is_panel,
    _is_reseau_inverter,
    panneaux_et_watt_lu,
)
from apps.ventes.utils.options import (
    blob_va_dans_avec,
    blob_va_dans_sans,
    texte_classement,
)

CONTRAT = (Path(__file__).resolve().parent.parent
           / 'contract_samples' / 'classification_lignes.json')

# Les six colonnes que les DEUX moitiés doivent reproduire à l'identique
# (``notes.colonnes`` de la fixture).
COLONNES = (
    'designation', 'panneau', 'batterie',
    'onduleur_hybride', 'onduleur_reseau', 'kwh_lisible',
)


def _cas():
    with CONTRAT.open(encoding='utf-8') as fh:
        return json.load(fh).get('exemple', {}).get('cas', [])


def _etiquette(cas):
    """Nomme le cas dans la sortie de test, divergence QJR92 comprise."""
    div = cas.get('divergence_actuelle')
    if not div:
        return cas['designation']
    return '{} [DIVERGENCE {} — ROUGE ATTENDU jusqu\'à QJR92]'.format(
        cas['designation'], div.get('champ'))


class ClassificationPariteFixtureTest(SimpleTestCase):
    """La fixture partagée est lisible et porte ses six colonnes."""

    def test_fixture_lisible_et_complete(self):
        cas = _cas()
        self.assertTrue(cas, 'classification_lignes.json ne porte aucun cas')
        for c in cas:
            for col in COLONNES:
                self.assertIn(
                    col, c,
                    "le cas « {} » ne porte pas la colonne {}".format(
                        c.get('designation'), col))


class ClasserProduitMemoTest(SimpleTestCase):
    def test_une_repasse_est_servie_par_le_memo_memes_classes(self):
        """ERR-PERF-DEVIS-ATOMIC-CATALOGUE — un balayage reclasse le catalogue
        à chaque taille : la repasse ne recalcule rien et rend les mêmes
        classes (l'ordre des tests du classifieur reste le sien)."""
        attendu = {
            'Onduleur hybride 5kW': 'onduleur_hybride',
            'Onduleur réseau 5kW': 'onduleur_reseau',
            'Câble AC Onduleur réseau vers TGBT': 'cable_dc',
            'Panneau mono 550W': 'panneau',
            'Divers': None,
        }
        classer_produit.cache_clear()
        premiere = {nom: classer_produit(nom) for nom in attendu}
        avant = classer_produit.cache_info()
        seconde = {nom: classer_produit(nom) for nom in attendu}
        apres = classer_produit.cache_info()
        self.assertEqual(premiere, attendu)
        self.assertEqual(seconde, attendu)
        self.assertEqual(apres.misses, avant.misses)
        self.assertEqual(apres.hits, avant.hits + len(attendu))


class ClassificationPariteBackendTest(SimpleTestCase):
    """Les classifieurs de ``builder.py`` sur CHAQUE cas de la fixture QJR2.

    Un ``subTest`` par (cas, colonne) : un cas rouge nomme EXACTEMENT la
    colonne qui diverge, et les autres colonnes du même cas continuent d'être
    vérifiées.
    """

    def test_colonnes_de_classification(self):
        for c in _cas():
            d = c['designation']
            nom = _etiquette(c)

            with self.subTest(cas=nom, colonne='panneau'):
                self.assertEqual(
                    _is_panel(d), c['panneau'],
                    "_is_panel(« {} ») attendu {} (contrat QJR2)".format(
                        d, c['panneau']))

            with self.subTest(cas=nom, colonne='batterie'):
                self.assertEqual(
                    _is_battery(d), c['batterie'],
                    "_is_battery(« {} ») attendu {} (contrat QJR2)".format(
                        d, c['batterie']))

            with self.subTest(cas=nom, colonne='onduleur_hybride'):
                self.assertEqual(
                    _is_hybrid_inverter(d), c['onduleur_hybride'],
                    "_is_hybrid_inverter(« {} ») attendu {} (contrat QJR2)"
                    .format(d, c['onduleur_hybride']))

            with self.subTest(cas=nom, colonne='onduleur_reseau'):
                self.assertEqual(
                    _is_reseau_inverter(d), c['onduleur_reseau'],
                    "_is_reseau_inverter(« {} ») attendu {} (contrat QJR2)"
                    .format(d, c['onduleur_reseau']))

            with self.subTest(cas=nom, colonne='kwh_lisible'):
                self.assertEqual(
                    _parse_kwh(d), c['kwh_lisible'],
                    "_parse_kwh(« {} ») attendu {} (contrat QJR2)".format(
                        d, c['kwh_lisible']))

            # Sens UNIQUE, jamais l'inverse : un onduleur classé hybride ou
            # réseau est forcément un onduleur. La réciproque est fausse par
            # construction (un « Onduleur Huawei 5kW » sans famille est
            # ``_is_inverter`` sans être ni l'un ni l'autre ; le micro-onduleur,
            # lui, est réseau depuis ADCG45) — ne jamais l'affirmer ici.
            if c['onduleur_hybride'] or c['onduleur_reseau']:
                with self.subTest(cas=nom, colonne='_is_inverter'):
                    self.assertTrue(
                        _is_inverter(d),
                        "_is_inverter(« {} ») doit être vrai pour un onduleur "
                        "classé".format(d))

    def test_onduleur_autonome_amot57(self):
        """AMOT57 — colonnes facultatives ``onduleur_offgrid`` / ``onduleur``.

        Moteur (``solar_classification``) ET seeder (copie de frontière
        stock → ventes) jouent les MÊMES cas : « hors-réseau », « off_grid »
        et « Deye off-Grid 6kw » sont des onduleurs autonomes, jamais réseau.
        """
        from apps.stock.management.commands import seed_catalogue as seed
        cas = [c for c in _cas() if 'onduleur_offgrid' in c]
        self.assertTrue(cas, 'aucun cas AMOT57 dans classification_lignes.json')
        for c in cas:
            d = c['designation']
            with self.subTest(cas=d, colonne='onduleur_offgrid'):
                self.assertEqual(_is_offgrid_inverter(d), c['onduleur_offgrid'])
                self.assertEqual(seed.is_offgrid(d), c['onduleur_offgrid'])
            with self.subTest(cas=d, colonne='onduleur'):
                self.assertEqual(_is_inverter(d), c['onduleur'])


class MicroOnduleurReseauAdcg45Test(SimpleTestCase):
    """ADCG45 (D-ADCG-3 = réseau) — un micro-onduleur est un onduleur RÉSEAU.

    « Micro-onduleur 800W » (``OND-800M`` de ``seed_demo``) n'entrait dans
    aucune famille : ``familles_servables`` rendait (False, False) et le
    document à options était refusé. Mutant : retirer « micro » du prédicat ⇒
    ce test et le cas de fixture rougissent.
    """

    def test_graphies_reconnues_et_exclusions(self):
        for nom in ('Micro-onduleur 800W', 'MICRO ONDULEUR 800W',
                    'Microonduleur 600W', 'micro_onduleur 800W',
                    'Micro-inverter 800W', 'Micro-ondûleur 800W'):
            with self.subTest(nom=nom):
                self.assertTrue(_is_reseau_inverter(nom))
                self.assertFalse(_is_hybrid_inverter(nom))
                self.assertFalse(_is_offgrid_inverter(nom))
                self.assertTrue(_is_inverter(nom))
        # Un micro-onduleur hybride reste hybride, un câble reste un câble, un
        # micro-onduleur autonome reste autonome.
        self.assertFalse(_is_reseau_inverter('Micro-onduleur hybride 800W'))
        self.assertTrue(_is_hybrid_inverter('Micro-onduleur hybride 800W'))
        for cable in ('Câble micro-onduleur', 'cable micro onduleur 2 m'):
            self.assertFalse(_is_reseau_inverter(cable), cable)
            self.assertFalse(_is_inverter(cable), cable)
        self.assertFalse(_is_reseau_inverter('Micro-onduleur off-grid 800W'))
        self.assertTrue(_is_offgrid_inverter('Micro-onduleur off-grid 800W'))

    def test_familles_servables_option_sans_batterie(self):
        """6 « Module PV 330 W » + 6 « Micro-onduleur 800W » : l'option « sans
        batterie » est servable (avant : (False, False) ⇒ PDF refusé)."""
        from apps.ventes.utils.options import (
            familles_des_lignes, familles_servables)
        lignes = [SimpleNamespace(designation='Module PV 330 W', quantite=6,
                                  produit=None),
                  SimpleNamespace(designation='Micro-onduleur 800W',
                                  quantite=6, produit=None)]
        familles = familles_des_lignes(lignes)
        self.assertTrue(familles['has_reseau'])
        self.assertEqual(familles_servables(**familles), (True, False))
        self.assertTrue(blob_va_dans_sans('Micro-onduleur 800W'))
        self.assertFalse(blob_va_dans_avec('Micro-onduleur 800W'))


class BatterieCapaciteParitesTest(SimpleTestCase):
    """``_battery_kwh_from_items`` — la capacité totale, ligne par ligne.

    BAT5DEF (26/08/2026, règle fondateur « zéro chiffre inventé ») : une ligne
    batterie sans kWh lisible contribue 0, JAMAIS un défaut fabriqué. C'est le
    comportement de ``solar.js batteryKwhFromLines`` que ce moteur doit adopter
    (QJR92b retire ``BATTERY_DEFAULT_KWH``).
    """

    def test_capacite_ligne_par_ligne(self):
        for c in _cas():
            if not c['batterie']:
                continue
            attendu = c['kwh_lisible'] or 0
            with self.subTest(cas=_etiquette(c)):
                total = _battery_kwh_from_items(
                    [{'designation': c['designation'], 'quantite': 1}])
                self.assertAlmostEqual(
                    total, attendu, places=6,
                    msg="attendu {} kWh (contrat QJR2), obtenu {}".format(
                        attendu, total))

    def test_capacite_totale_aucune_ligne_n_invente_de_kwh(self):
        cas = _cas()
        lignes = [{'designation': c['designation'], 'quantite': 1}
                  for c in cas]
        attendu = sum((c['kwh_lisible'] or 0) for c in cas if c['batterie'])
        total = _battery_kwh_from_items(lignes)
        self.assertAlmostEqual(
            total, attendu, places=6,
            msg="capacité totale attendue {} kWh (somme des kWh RÉELLEMENT "
                "lisibles), obtenu {}".format(attendu, total))


class ClassementPlafondMemoTest(SimpleTestCase):
    """ERR-PERF-DEVIS-ATOMIC-LRU — un catalogue plus grand que le plafond relit
    tout le cache à vide (8 947 produits : 313 s)."""

    def test_plafond_au_dessus_de_tout_catalogue(self):
        self.assertGreaterEqual(classer_produit.cache_info().maxsize, 50_000)


class ClassificationRoleStkcat19Test(SimpleTestCase):
    """STKCAT19 — colonne ``role`` (``classer_produit`` / ``classifyProduct``).

    Comportement MOT-CLÉ COURANT, REPLI DERRIÈRE LE RÔLE DÉCLARÉ (voir
    ``notes.role_stkcat19`` de la fixture) : STKCAT21 fera du rôle produit
    DÉCLARÉ sur la fiche la source PRIORITAIRE, ce classifieur par mot-clé
    n'en restera qu'un repli pour les produits sans rôle déclaré. ``role``
    n'est porté QUE par les cas structure/accessoire ajoutés par STKCAT19 (pas
    par les neuf cas résidentiels panneau/batterie/onduleur ci-dessus, hors
    périmètre de cette colonne) — on ne teste donc que ceux qui la portent.
    """

    def test_role_sur_les_cas_qui_la_portent(self):
        cas_avec_role = [c for c in _cas() if 'role' in c]
        self.assertTrue(
            cas_avec_role,
            'aucun cas ne porte la colonne role (STKCAT19) — '
            'classification_lignes.json a régressé')
        for c in cas_avec_role:
            d = c['designation']
            with self.subTest(cas=_etiquette(c), colonne='role'):
                self.assertEqual(
                    classer_produit(d), c['role'],
                    "classer_produit(« {} ») attendu {} (contrat "
                    "QJR2/STKCAT19)".format(d, c['role']))


class CasLigneProduitTest(SimpleTestCase):
    """AGNR2 — section ``exemple.cas_ligne_produit`` (contrat d'abord).

    Une désignation RETOUCHÉE à la main est classée sur désignation + nom du
    produit lié (``texte_classement``) : paniers sans/avec, kWh batterie,
    provision onduleur, panneau et watt LU (``panneaux_et_watt_lu``). Le
    serveur est la référence ; la moitié JS (AGNR18, AGNR36) lira la même
    section.
    """

    COLONNES = ('designation', 'produit_nom', 'panier_sans', 'panier_avec',
                'kwh_batterie', 'provision_onduleur', 'est_panneau',
                'watt_lu')

    @staticmethod
    def _section():
        with CONTRAT.open(encoding='utf-8') as fh:
            return json.load(fh).get('exemple', {}).get(
                'cas_ligne_produit', [])

    def test_cas_ligne_produit(self):
        section = self._section()
        self.assertTrue(
            section, 'classification_lignes.json ne porte pas la section '
            'exemple.cas_ligne_produit (AGNR2)')
        for c in section:
            for col in self.COLONNES:
                self.assertIn(col, c, '{} sans la colonne {}'.format(
                    c.get('designation'), col))
            d, nom = c['designation'], c['produit_nom']
            texte = texte_classement(d, nom)
            ligne = SimpleNamespace(
                designation=d, quantite=1,
                produit=(SimpleNamespace(nom=nom, fiche_technique=None)
                         if nom else None))
            nb, watt = panneaux_et_watt_lu([ligne])
            obtenu = {
                'panier_sans': blob_va_dans_sans(texte),
                'panier_avec': blob_va_dans_avec(texte),
                'kwh_batterie': (_parse_kwh(texte) if _is_battery(texte)
                                 else None),
                'provision_onduleur': _is_inverter(texte),
                'est_panneau': nb > 0,
                'watt_lu': watt,
            }
            for col, valeur in obtenu.items():
                with self.subTest(cas=d, produit=nom, colonne=col):
                    self.assertEqual(
                        valeur, c[col],
                        '« {} » + « {} » : {} attendu {} (contrat AGNR2), '
                        'obtenu {}'.format(d, nom, col, c[col], valeur))


class _FicheLue:
    """Fiche technique en doublure : un champ non posé vaut ``None`` (non publié)."""

    def __init__(self, type_fiche, **valeurs):
        self.type_fiche = type_fiche
        self._valeurs = valeurs

    def __getattr__(self, nom):
        return self.__dict__.get('_valeurs', {}).get(nom)


def _ligne_produit(designation, *, role=None, fiche=None, devis=None):
    """Une ligne LIÉE à un produit (``produit_id`` posé) : rôle et fiche au choix."""
    produit = SimpleNamespace(nom=designation, role_devis=role, fiche_technique=fiche)
    return SimpleNamespace(designation=designation, quantite=1, produit=produit,
                           produit_id=7, devis=devis)


class LecteursAvalRoleFicheTest(SimpleTestCase):
    """Lecteurs en aval (fondateur 24/11/2026, « un produit se reconnaît à son
    rôle et à sa fiche avant son nom ») — ``domain.classe_ligne``, lu par
    ``domain.lignes._classe_ligne``, le moteur PDF et le noyau des paniers."""

    #: Désignations RÉELLES de ``seed_catalogue`` (et le nom réel du 80 kW de Reda).
    DESIGNATIONS = (
        'Onduleur réseau Huawei 10kW Triphasé', 'Onduleur hybride Deye 10kW Monophasé',
        'Panneau Canadien Solar 710W', 'Panneau Jinko 710W', 'Batterie Dyness 10 kWh',
        'Batterie Dyness PowerBrick SC 16 kWh', 'Batterie Gel 2.2 kWh', 'Structures acier',
        'Câble solaire Nexans 6 mm² (au mètre)', 'Smart Meter', 'Deye off-Grid 6kw',
        'DEYE SUN-80K-SG02HP3-EU-EM6', 'Installation')
    PREDICATS = (_is_panel, _is_battery, _is_hybrid_inverter, _is_reseau_inverter,
                 _is_offgrid_inverter, _is_inverter)

    def test_sans_role_ni_fiche_le_verdict_d_hier(self):
        from apps.ventes.domain.lignes import _classe_ligne
        for designation in self.DESIGNATIONS:
            for predicat in self.PREDICATS:
                for ligne in (_ligne_produit(designation),
                              SimpleNamespace(designation=designation, produit=None, produit_id=None)):
                    with self.subTest(designation=designation, predicat=predicat.__name__):
                        self.assertEqual(_classe_ligne(ligne, predicat), bool(predicat(designation)))

    def test_le_role_passe_devant_le_nom(self):
        from apps.ventes.domain.lignes import _classe_ligne
        hybride = _ligne_produit('DEYE SUN-80K-SG02HP3-EU-EM6', role='onduleur_hybride')
        self.assertFalse(_is_hybrid_inverter('DEYE SUN-80K-SG02HP3-EU-EM6'))  # le nom ne le dit pas
        self.assertTrue(_classe_ligne(hybride, _is_hybrid_inverter))
        self.assertTrue(_classe_ligne(hybride, _is_inverter))
        self.assertFalse(_classe_ligne(hybride, _is_reseau_inverter))
        cable = _ligne_produit('Câble batterie 35 mm²', role='cable_dc')
        self.assertTrue(_is_battery('Câble batterie 35 mm²'))  # les mots-clés s'y trompent
        self.assertFalse(_classe_ligne(cable, _is_battery))

    def test_la_fiche_passe_devant_le_nom(self):
        from apps.ventes.domain.lignes import _classe_ligne
        nom = 'Canadian Solar TOPBiHiKu7 CS7N-715TB'
        self.assertFalse(_is_panel(nom))
        self.assertTrue(_classe_ligne(_ligne_produit(nom, fiche=_FicheLue('module')), _is_panel))
        self.assertTrue(_classe_ligne(_ligne_produit('Deye BOS-B Pro-A3', fiche=_FicheLue('batterie')),
                                      _is_battery))
        port = _FicheLue('onduleur', ond_bat_max_charge_kw=80, ond_bat_max_decharge_kw=80)
        self.assertTrue(_classe_ligne(_ligne_produit('DEYE SUN-80K-SG02HP3-EU-EM6', fiche=port),
                                      _is_hybrid_inverter))
        # Fiche onduleur sans port batterie : la famille reste celle du nom.
        reseau = _ligne_produit('Onduleur réseau Huawei 10kW Triphasé', fiche=_FicheLue('onduleur'))
        self.assertTrue(_classe_ligne(reseau, _is_reseau_inverter))
        self.assertFalse(_classe_ligne(reseau, _is_hybrid_inverter))
        self.assertFalse(_classe_ligne(reseau, _is_panel))

    def test_devis_envoye_avant_la_coupure_garde_les_mots_cles(self):
        from datetime import date, timedelta

        from apps.ventes.domain.lignes import _classe_ligne
        from apps.ventes.domain.regles_calcul import COUPURE_CLASSE_PAR_ROLE
        avant = SimpleNamespace(statut='envoye', regles_calcul=14,
                                date_envoi=date(*COUPURE_CLASSE_PAR_ROLE) - timedelta(days=1))
        apres = SimpleNamespace(statut='envoye', regles_calcul=14, date_envoi=date(*COUPURE_CLASSE_PAR_ROLE))
        nom = 'DEYE SUN-80K-SG02HP3-EU-EM6'
        self.assertFalse(_classe_ligne(_ligne_produit(nom, role='onduleur_hybride', devis=avant),
                                       _is_hybrid_inverter))
        self.assertTrue(_classe_ligne(_ligne_produit(nom, role='onduleur_hybride', devis=apres),
                                      _is_hybrid_inverter))

    def test_pdf_et_noyau_lisent_la_meme_famille(self):
        """La servabilité du PDF (``paires_portent``) et celle du noyau des
        paniers (``familles_des_lignes``) suivent le même rôle — sans la fiche."""
        from apps.ventes.domain.classe_ligne import paires_portent
        from apps.ventes.utils.options import familles_des_lignes
        lignes = [_ligne_produit('DEYE SUN-80K-SG02HP3-EU-EM6', role='onduleur_hybride'),
                  _ligne_produit('Deye BOS-B Pro-A3 16 kWh', role='batterie'),
                  _ligne_produit('Module CS7N-715TB', fiche=_FicheLue('module'))]
        paires = [(li, {'designation': li.designation, '_produit_nom': li.produit.nom,
                        'quantite': 1.0}) for li in lignes]
        familles = familles_des_lignes(lignes)
        self.assertEqual(familles, {'has_reseau': False, 'has_hybride': True,
                                    'has_offgrid': False, 'has_batterie': True})
        for cle, predicat in (('has_reseau', _is_reseau_inverter), ('has_hybride', _is_hybrid_inverter),
                              ('has_offgrid', _is_offgrid_inverter), ('has_batterie', _is_battery)):
            self.assertEqual(paires_portent(paires, predicat), familles[cle], cle)
        paires[0][1]['quantite'] = 0.0
        self.assertFalse(paires_portent(paires, _is_hybrid_inverter))
