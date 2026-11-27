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

from django.test import SimpleTestCase, TestCase

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


#: Un brouillon jamais envoyé : la règle du rôle rangé s'applique.
_BROUILLON = SimpleNamespace(statut='brouillon', date_envoi=None, regles_calcul=14)


def _ligne(designation, *, role=None, devis=_BROUILLON, produit=None, quantite=1, variante=''):
    """Une ligne de devis en doublure : son rôle RANGÉ (``role_devis``) et son devis."""
    return SimpleNamespace(designation=designation, quantite=quantite, role_devis=role,
                           produit=produit, produit_id=None if produit is None else 7,
                           devis=devis, variante=variante, type_ligne='produit',
                           optionnelle=False)


def _item(ligne):
    """L'item du moteur PDF de ``ligne`` (``_line_to_item`` transporte ``role_devis``)."""
    return {'designation': ligne.designation, 'quantite': float(ligne.quantite),
            '_produit_nom': getattr(ligne.produit, 'nom', '') or '', 'role_devis': ligne.role_devis}


class _Lignes:
    def __init__(self, lignes):
        self._lignes = lignes

    def all(self):
        return list(self._lignes)


class LecteursAvalRoleRangeTest(SimpleTestCase):
    """Lecteurs en aval (fondateur 24/11/2026) — la classe d'une ligne est
    décidée à son ÉCRITURE et RANGÉE (``LigneDevis.role_devis``) ; tous les
    lecteurs aval lisent ce rôle rangé, puis les mots-clés d'aujourd'hui
    (``domain.classe_ligne``). Aucun ne relit le produit vivant."""

    #: Désignations RÉELLES de ``seed_catalogue`` (et le nom réel du 80 kW de Reda).
    DESIGNATIONS = (
        'Onduleur réseau Huawei 10kW Triphasé', 'Onduleur hybride Deye 10kW Monophasé',
        'Panneau Canadien Solar 710W', 'Panneau Jinko 710W', 'Batterie Dyness 10 kWh',
        'Batterie Dyness PowerBrick SC 16 kWh', 'Batterie Gel 2.2 kWh', 'Structures acier',
        'Câble solaire Nexans 6 mm² (au mètre)', 'Smart Meter', 'Deye off-Grid 6kw',
        'DEYE SUN-80K-SG02HP3-EU-EM6', 'Installation')
    PREDICATS = (_is_panel, _is_battery, _is_hybrid_inverter, _is_reseau_inverter,
                 _is_offgrid_inverter, _is_inverter)

    def test_sans_role_range_le_verdict_d_hier(self):
        from apps.ventes.domain.lignes import _classe_ligne
        for designation in self.DESIGNATIONS:
            for predicat in self.PREDICATS:
                for ligne in (_ligne(designation), _ligne(designation, devis=None),
                              _ligne(designation, produit=SimpleNamespace(nom=designation))):
                    with self.subTest(designation=designation, predicat=predicat.__name__):
                        self.assertEqual(_classe_ligne(ligne, predicat), bool(predicat(designation)))

    def test_le_role_range_passe_devant_le_nom(self):
        from apps.ventes.domain.lignes import _classe_ligne
        hybride = _ligne('DEYE SUN-80K-SG02HP3-EU-EM6', role='onduleur_hybride')
        self.assertFalse(_is_hybrid_inverter('DEYE SUN-80K-SG02HP3-EU-EM6'))  # le nom ne le dit pas
        self.assertTrue(_classe_ligne(hybride, _is_hybrid_inverter))
        self.assertTrue(_classe_ligne(hybride, _is_inverter))
        self.assertFalse(_classe_ligne(hybride, _is_reseau_inverter))
        cable = _ligne('Câble batterie 35 mm²', role='cable_dc')
        self.assertTrue(_is_battery('Câble batterie 35 mm²'))  # les mots-clés s'y trompent
        self.assertFalse(_classe_ligne(cable, _is_battery))

    def test_une_retouche_du_catalogue_apres_l_ecriture_ne_change_rien(self):
        """Le produit déclare DEPUIS un rôle et une fiche : la ligne, écrite sans
        rôle, garde le verdict d'hier — aucun lecteur ne relit le produit."""
        from apps.ventes.domain.lignes import _classe_ligne
        from apps.ventes.utils.options import familles_des_lignes
        produit = SimpleNamespace(nom='DEYE SUN-80K-SG02HP3-EU-EM6', role_devis='onduleur_hybride',
                                  fiche_technique=_FicheLue('onduleur', ond_bat_max_charge_kw=80))
        ligne = _ligne('DEYE SUN-80K-SG02HP3-EU-EM6', produit=produit)
        self.assertFalse(_classe_ligne(ligne, _is_hybrid_inverter))
        self.assertFalse(familles_des_lignes([ligne])['has_hybride'])

    def test_devis_envoye_avant_la_coupure_ou_inconnu_garde_les_mots_cles(self):
        from datetime import date, timedelta

        from apps.ventes.domain.lignes import _classe_ligne
        from apps.ventes.domain.regles_calcul import COUPURE_CLASSE_PAR_ROLE
        avant = SimpleNamespace(statut='envoye', regles_calcul=14,
                                date_envoi=date(*COUPURE_CLASSE_PAR_ROLE) - timedelta(days=1))
        apres = SimpleNamespace(statut='envoye', regles_calcul=14, date_envoi=date(*COUPURE_CLASSE_PAR_ROLE))
        nom = 'DEYE SUN-80K-SG02HP3-EU-EM6'
        for devis, attendu in ((avant, False), (None, False), (apres, True), (_BROUILLON, True)):
            with self.subTest(devis=devis):
                self.assertEqual(_classe_ligne(_ligne(nom, role='onduleur_hybride', devis=devis),
                                               _is_hybrid_inverter), attendu)

    def test_cas_a_batterie_rangee_tous_les_lecteurs_d_accord(self):
        """Cas A — batterie au nom muet (« Deye BOS-B Pro-A3 16 kWh ») rangée
        ``batterie`` à l'écriture : servabilité du PDF, familles du noyau,
        paniers, ``_classe_ligne``, kWh du PDF, capacité horaire : la MÊME
        batterie, dans la seule option « avec »."""
        from apps.ventes.domain.classe_ligne import paires_portent
        from apps.ventes.domain.lignes import _classe_ligne
        from apps.ventes.horaire.batterie_lignes import capacite_batterie_du_devis
        from apps.ventes.quote_engine.lignes_classement import _battery_kwh_from_items
        from apps.ventes.utils.options import (
            AVEC_BATTERIE, SANS_BATTERIE, familles_des_lignes, filter_lines_for_option)
        devis = SimpleNamespace(statut='brouillon', date_envoi=None, regles_calcul=14)
        batterie = _ligne('Deye BOS-B Pro-A3 16 kWh', role='batterie', devis=devis)
        lignes = [_ligne('Panneau Jinko 710W', role='panneau', devis=devis, quantite=20),
                  _ligne('DEYE SUN-80K-SG02HP3-EU-EM6', role='onduleur_hybride', devis=devis),
                  _ligne('Onduleur réseau Huawei 10kW Triphasé', role='onduleur_reseau', devis=devis),
                  batterie]
        devis.lignes = _Lignes(lignes)
        self.assertFalse(_is_battery(batterie.designation))  # les mots-clés ne la voient pas
        paires = [(li, _item(li)) for li in lignes]
        self.assertEqual(familles_des_lignes(lignes), {'has_reseau': True, 'has_hybride': True,
                                                       'has_offgrid': False, 'has_batterie': True})
        for cle, predicat in (('has_reseau', _is_reseau_inverter), ('has_hybride', _is_hybrid_inverter),
                              ('has_batterie', _is_battery)):
            self.assertTrue(paires_portent(paires, predicat, devis), cle)
        self.assertTrue(_classe_ligne(batterie, _is_battery))
        self.assertIn(batterie, filter_lines_for_option(lignes, AVEC_BATTERIE, devis=devis))
        self.assertNotIn(batterie, filter_lines_for_option(lignes, SANS_BATTERIE, devis=devis))
        self.assertEqual(_battery_kwh_from_items([_item(batterie)], devis=devis), 16.0)
        self.assertEqual(capacite_batterie_du_devis(devis), 16.0)
        # Le même devis envoyé avant la coupure : les mots-clés d'hier partout.
        self.assertEqual(_battery_kwh_from_items([_item(batterie)]), 0.0)

    def test_cas_b_panneaux_ranges_tous_les_comptes_d_accord(self):
        """Cas B — « Canadian Solar TOPBiHiKu7 CS7N-715TB » ×30 rangé ``panneau`` :
        compte du PDF (``panneaux_et_watt_lu``), paires kWc, compte du re-tarif
        (``retarifer`` : ``_comptes_panneaux`` sur ``devis.lignes``), compte
        CAPTURÉ avant un geste (``comptes_panneaux_du_devis``, relu EN BASE),
        compte de la garde (``comptes_panneaux_valides``) et dimensionnement
        public : 30 partout.

        Constat 3 — sur le CHEMIN RÉEL : des ``LigneDevis`` (pas des doublures,
        qui ont toujours leur devis « chargé »). Les lignes de ``devis.lignes``
        portent leur devis ; celles que ``comptes_panneaux_du_devis`` relit par
        ``LigneDevis.objects.filter(devis_id=…)`` ne le portent PAS — seul le
        devis transmis ouvre alors la lecture par rôle. Avant le correctif, le
        compte capturé valait 0 face aux 30 du re-tarif : un écart que la garde
        des devis envoyés lit comme un changement de compte."""
        from datetime import date, timedelta
        from decimal import Decimal
        from unittest import mock

        from apps.stock.models import FicheTechnique, Produit
        from apps.ventes.domain.dimensionnement_devis import comptes_panneaux_valides
        from apps.ventes.domain.lignes import _comptes_panneaux, comptes_panneaux_du_devis
        from apps.ventes.domain.regles_calcul import COUPURE_CLASSE_PAR_ROLE
        from apps.ventes.models import Devis, LigneDevis
        from apps.ventes.public.payload_horaire import _dimensionnement_option_depuis_items
        from apps.ventes.quote_engine.lignes_classement import (
            paires_panneaux_lues, panneaux_et_watt_lu)
        nom = 'Canadian Solar TOPBiHiKu7 CS7N-715TB'
        self.assertFalse(_is_panel(nom))
        produit = Produit(nom=nom)
        FicheTechnique(produit=produit, type_fiche='module', pmax_wc=Decimal('715'))

        def ligne(role, devis=None):
            champs = dict(designation=nom, role_devis=role, type_ligne='produit', produit=produit,
                          quantite=Decimal('30'), prix_unitaire=Decimal('1200'), remise=Decimal('0'))
            return LigneDevis(devis=devis, **champs) if devis is not None else LigneDevis(**champs)

        def capture(devis, lignes_en_base):
            requete = mock.Mock()
            requete.filter.return_value.select_related.return_value = lignes_en_base
            with mock.patch.object(LigneDevis, 'objects', requete):
                return comptes_panneaux_du_devis(devis)

        reel = Devis(pk=41, statut='brouillon', date_envoi=None, regles_calcul=14)
        panneau = ligne('panneau', reel)  # telle que la rend ``devis.lignes.all()``
        devis = SimpleNamespace(pk=41, statut='brouillon', date_envoi=None, regles_calcul=14,
                                lignes=_Lignes([panneau]))
        self.assertEqual(panneaux_et_watt_lu([panneau]), (30, 715))
        self.assertEqual(paires_panneaux_lues([panneau]), [(30, 715)])
        self.assertEqual(_comptes_panneaux([panneau])[''], 30)
        self.assertEqual(capture(devis, [ligne('panneau')])[''], 30)
        self.assertEqual(comptes_panneaux_valides(devis), {30})
        self.assertEqual(_dimensionnement_option_depuis_items([_item(panneau)], devis)['nb_panneaux'], 30)
        # Envoyé avant la coupure : 0 des DEUX côtés, le verdict d'hier, aucun écart.
        avant = SimpleNamespace(pk=41, statut='envoye', regles_calcul=14,
                                date_envoi=date(*COUPURE_CLASSE_PAR_ROLE) - timedelta(days=1))
        self.assertEqual(capture(avant, [ligne('panneau')])[''], 0)
        self.assertEqual(_comptes_panneaux([ligne('panneau')], devis=avant)[''], 0)
        # Sans rôle rangé : 0 partout, le verdict d'hier.
        muet = ligne(None, reel)
        self.assertEqual(panneaux_et_watt_lu([muet])[0], 0)
        self.assertEqual(_comptes_panneaux([muet])[''], 0)
        self.assertEqual(capture(devis, [ligne(None)])[''], 0)

    def test_le_scenario_de_l_etude_lit_les_roles_emis_par_la_composition(self):
        """Constat 2 — ``cles_etude_de_composition`` (étape 6 du pipeline et
        moteur de conception) dérive le scénario servable des rôles ÉMIS par la
        composition (``composition.roles``), plus des mots-clés : cas B + C + A
        (aucun nom ne porte de mot-clé) composés « avec » rangent « Avec
        batterie », pas « Sans batterie »."""
        from datetime import date, timedelta

        from apps.ventes.domain.composition import CompositionLignes
        from apps.ventes.domain.pipeline import cles_etude_de_composition
        from apps.ventes.domain.regles_calcul import COUPURE_CLASSE_PAR_ROLE
        from apps.ventes.domain.scenario import SCENARIO_AVEC_BATTERIE, SCENARIO_SANS_BATTERIE

        def kit(nom, quantite):
            return SimpleNamespace(designation=nom, produit=None, quantite=quantite,
                                   prix_unitaire=1000, variante='')
        composition = CompositionLignes([kit('Canadian Solar TOPBiHiKu7 CS7N-715TB', 30),
                                         kit('DEYE SUN-80K-SG02HP3-EU-EM6', 1),
                                         kit('Deye BOS-B Pro-A3 16 kWh', 2)])
        composition.roles = ['panneau', 'onduleur_hybride', 'batterie']
        intention = SimpleNamespace(scenario='', layout={}, mode_installation='residentiel')
        avant = SimpleNamespace(statut='envoye', regles_calcul=14,
                                date_envoi=date(*COUPURE_CLASSE_PAR_ROLE) - timedelta(days=1))
        for devis, attendu in ((_BROUILLON, SCENARIO_AVEC_BATTERIE),
                               (avant, SCENARIO_SANS_BATTERIE)):
            with self.subTest(devis=devis):
                self.assertEqual(cles_etude_de_composition(devis, intention, composition)['scenario'],
                                 attendu)
        # Sans rôle émis : les mots-clés d'hier, même sur un brouillon.
        composition.roles = ()
        self.assertEqual(cles_etude_de_composition(_BROUILLON, intention, composition)['scenario'],
                         SCENARIO_SANS_BATTERIE)

    def test_les_autos_du_registre_lisent_le_role_range(self):
        """Constat 2 (suite) — le bloc ``auto`` du registre (``overrides``) :
        scénario servable (``_auto_scenario``) et banque de batterie
        (``_autos_banque_batterie``) lisent le rôle RANGÉ des lignes réelles
        (devis NON chargé sur la ligne), puis les mots-clés d'hier."""
        from datetime import date, timedelta
        from decimal import Decimal

        from apps.ventes.domain.overrides import _auto_scenario, _autos_banque_batterie
        from apps.ventes.domain.regles_calcul import COUPURE_CLASSE_PAR_ROLE
        from apps.ventes.domain.scenario import SCENARIO_AVEC_BATTERIE, SCENARIO_SANS_BATTERIE
        from apps.ventes.models import LigneDevis
        from apps.stock.models import Produit

        class _Requete(_Lignes):
            def select_related(self, *_champs):
                return self

        def ligne(nom, role, quantite):
            return LigneDevis(designation=nom, role_devis=role, type_ligne='produit',
                              quantite=Decimal(quantite), prix_unitaire=Decimal('1000'),
                              remise=Decimal('0'), produit=Produit(nom=nom))

        def devis(**etat):
            lignes = [ligne('Canadian Solar TOPBiHiKu7 CS7N-715TB', 'panneau', '30'),
                      ligne('DEYE SUN-80K-SG02HP3-EU-EM6', 'onduleur_hybride', '1'),
                      ligne('Deye BOS-B Pro-A3 16 kWh', 'batterie', '2')]
            return SimpleNamespace(regles_calcul=14, etude_params={}, overrides={},
                                   lignes=_Requete(lignes), **etat)
        ouvert = devis(statut='brouillon', date_envoi=None)
        self.assertEqual(_auto_scenario(ouvert), SCENARIO_AVEC_BATTERIE)
        self.assertEqual(_autos_banque_batterie(ouvert).get('taille.batterie_nb_modules'), 2)
        avant = devis(statut='envoye', date_envoi=date(*COUPURE_CLASSE_PAR_ROLE) - timedelta(days=1))
        self.assertEqual(_auto_scenario(avant), SCENARIO_SANS_BATTERIE)
        self.assertEqual(_autos_banque_batterie(avant), {})


class LecteursAvalComptesEnBaseTest(TestCase):
    """Constat 3 — EN BASE (CI) : le compte capturé avant un geste
    (``comptes_panneaux_du_devis``, lignes relues SANS leur devis) égale le
    compte du re-tarif (``devis.lignes``) pour le cas B rangé ``panneau``."""

    def test_cas_b_compte_capture_egal_au_compte_du_retarif(self):
        from decimal import Decimal

        from authentication.models import Company

        from apps.crm.models import Client
        from apps.stock.models import Produit
        from apps.ventes.domain.lignes import _comptes_panneaux, _lignes_produit, comptes_panneaux_du_devis
        from apps.ventes.models import Devis, LigneDevis
        company = Company.objects.create(slug='lav-comptes-b', nom='lav-comptes-b')
        client_obj = Client.objects.create(company=company, nom='Client cas B')
        devis = Devis.objects.create(company=company, reference='DEV-LAV-B-01', client=client_obj,
                                     statut='brouillon', taux_tva=Decimal('20'),
                                     mode_installation='residentiel')
        nom = 'Canadian Solar TOPBiHiKu7 CS7N-715TB'
        produit = Produit.objects.create(company=company, nom=nom, prix_vente=1200, quantite_stock=50)
        LigneDevis.objects.create(devis=devis, produit=produit, designation=nom, role_devis='panneau',
                                  quantite=Decimal('30'), prix_unitaire=Decimal('1200'),
                                  remise=Decimal('0'))
        devis = Devis.objects.get(pk=devis.pk)
        capture = comptes_panneaux_du_devis(devis)
        self.assertEqual(capture[''], 30)
        self.assertEqual(capture, _comptes_panneaux(_lignes_produit(devis), devis))
