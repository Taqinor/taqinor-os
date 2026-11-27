"""CALX141 — le contrat de la CASCADE de pertes tient ses quatre promesses.

Ce fichier garde un DOCUMENT, pas un service : `resultat['cascade']` n'a
encore aucun producteur (il arrive avec `services/chaine_pertes.py`,
CALX147). Ce qui peut être affirmé aujourd'hui — et qui compte, puisque deux
écrans et une vingtaine de modules d'étape vont brancher dessus — c'est que
l'exemple committé se relit, qu'il est CONTINU, qu'il n'a forfaitisé aucune
étape omise, et qu'il n'a pas dérivé de `calepinage_simulation.json` (CALX4).

Le quatrième contrôle est le plus important du lot : `resultat['pertes']`
reste une LISTE PLATE (D-CALX 11). Quatre lecteurs l'itèrent déjà comme telle ;
le jour où quelqu'un « unifierait » les deux blocs, ce test le dirait ici.

Aucune base de données, aucun réseau : trois fichiers JSON et des assertions.

Run :
    python manage.py test apps.calepinage.tests.test_calx141_contrat_cascade
"""
from __future__ import annotations

import json
import pathlib
import unittest

ECHANTILLONS = (pathlib.Path(__file__).resolve().parents[1]
                / 'contract_samples')


def charger(nom):
    return json.loads((ECHANTILLONS / nom).read_text(encoding='utf-8'))


CASCADE = charger('calepinage_pertes_cascade.json')
SIMULATION = charger('calepinage_simulation.json')
RESULTAT = charger('calepinage_resultat.json')

#: Les douze clés d'une étape — l'ordre n'a pas d'importance, la présence si.
CLES_ETAPE = {
    'rang', 'etape', 'libelle', 'kwh_avant', 'kwh_apres', 'perte_kwh',
    'perte_pct', 'gain', 'source', 'entree', 'reference', 'motif_omission',
}


class EnveloppeTest(unittest.TestCase):
    """L'échantillon se relit et porte l'enveloppe PACT10."""

    def test_enveloppe_complete(self):
        for cle in ('endpoint', 'pourquoi', 'exemple'):
            self.assertIn(cle, CASCADE)
        self.assertTrue(CASCADE['endpoint'].strip())
        self.assertIn('resultat/', CASCADE['endpoint'])

    def test_les_deux_etats_portent_la_meme_clef_et_les_memes_champs(self):
        for etat in ('exemple', 'exemple_vide'):
            bloc = CASCADE[etat]['cascade']
            # ACAL8 (contrat v2) : + etapes_omises,
            # irradiation_incidente_kwh_m2. ACAL695 : + postes_lisibles.
            # ACAL699 : + a_renseigner. ACAL749 : + limites_connues.
            self.assertEqual(
                sorted(bloc),
                ['a_renseigner', 'etapes', 'etapes_omises', 'hash_entree',
                 'irradiation_incidente_kwh_m2', 'limites_connues', 'ordre',
                 'plages',
                 'postes_lisibles', 'postes_non_sources', 'total_pct'],
                f'{etat} : les clés du bloc « cascade » ont bougé.')

    def test_vide_ne_publie_jamais_un_zero(self):
        bloc = CASCADE['exemple_vide']['cascade']
        self.assertEqual(bloc['etapes'], [])
        self.assertEqual(bloc['ordre'], [])
        self.assertIsNone(bloc['total_pct'],
                          'Un calepinage jamais simulé n’a pas 0 % de perte : '
                          'il n’a PAS de cascade.')


class FormeDesEtapesTest(unittest.TestCase):
    """Chaque étape porte les douze champs, et `ordre` les nomme toutes."""

    def setUp(self):
        self.etapes = CASCADE['exemple']['cascade']['etapes']

    def test_douze_champs_par_etape(self):
        for etape in self.etapes:
            self.assertEqual(set(etape), CLES_ETAPE,
                             f"étape « {etape.get('etape')} » : champs "
                             f"{sorted(set(etape) ^ CLES_ETAPE)} en écart.")

    def test_les_rangs_suivent_l_ordre_declare(self):
        self.assertEqual([e['rang'] for e in self.etapes],
                         list(range(1, len(self.etapes) + 1)))
        self.assertEqual(CASCADE['exemple']['cascade']['ordre'],
                         [e['etape'] for e in self.etapes],
                         '`ordre` doit nommer les étapes présentes, dans '
                         'leur ordre de rang.')


class ContinuiteTest(unittest.TestCase):
    """`kwh_avant` d'une étape est le `kwh_apres` de la précédente.

    Une étape OMISE laisse la série inchangée : son `kwh_apres` vaut ``null``
    et la suivante repart du DERNIER `kwh_apres` connu. On ne remplace jamais
    un ``null`` par un chiffre pour faire tenir la chaîne.
    """

    def test_la_chaine_est_continue_sur_toute_la_liste(self):
        etapes = CASCADE['exemple']['cascade']['etapes']
        self.assertGreater(len(etapes), 1)
        dernier_connu = etapes[0]['kwh_avant']
        for precedente, etape in zip(etapes, etapes[1:]):
            self.assertEqual(
                etape['kwh_avant'], dernier_connu,
                f"étape « {etape['etape']} » (rang {etape['rang']}) : son "
                f"kwh_avant ({etape['kwh_avant']}) n'est pas l'énergie qui "
                f"sort de « {precedente['etape']} » ({dernier_connu}).")
            if etape['kwh_apres'] is not None:
                dernier_connu = etape['kwh_apres']

    def test_total_pct_est_celui_de_la_cascade_elle_meme(self):
        bloc = CASCADE['exemple']['cascade']
        etapes = bloc['etapes']
        entree = etapes[0]['kwh_avant']
        sorties = [e['kwh_apres'] for e in etapes
                   if e['kwh_apres'] is not None]
        attendu = round(100.0 * (1.0 - sorties[-1] / entree), 1)
        self.assertEqual(bloc['total_pct'], attendu,
                         '`total_pct` se déduit des deux bouts de la '
                         'cascade ; il ne recopie pas la perte passée à '
                         'PVGIS (CAL238).')

    def test_une_perte_est_positive_et_un_gain_est_signale(self):
        for etape in CASCADE['exemple']['cascade']['etapes']:
            if etape['perte_kwh'] is None:
                continue
            if etape['gain']:
                self.assertLessEqual(etape['perte_kwh'], 0.0, etape['etape'])
                self.assertLessEqual(etape['perte_pct'], 0.0, etape['etape'])
            else:
                self.assertGreaterEqual(etape['perte_kwh'], 0.0,
                                        etape['etape'])
                self.assertGreaterEqual(etape['perte_pct'], 0.0,
                                        etape['etape'])


class OmissionTest(unittest.TestCase):
    """Une étape omise se DIT — elle ne se forfaitise pas en 0 %."""

    def test_motif_present_impose_des_null_jamais_des_zeros(self):
        omises = [e for e in CASCADE['exemple']['cascade']['etapes']
                  if (e['motif_omission'] or '').strip()]
        self.assertTrue(omises, "L'exemple doit montrer au moins une étape "
                                'omise : c’est la moitié du contrat.')
        for etape in omises:
            for champ in ('kwh_apres', 'perte_kwh', 'perte_pct'):
                self.assertIsNone(
                    etape[champ],
                    f"étape « {etape['etape']} » : {champ} vaut "
                    f"{etape[champ]!r} alors que l'étape est OMISE. Un 0 se "
                    f"lirait « cette étape ne coûte rien ».")
            self.assertIsNone(etape['source'])

    def test_une_etape_calculee_n_a_aucun_motif(self):
        for etape in CASCADE['exemple']['cascade']['etapes']:
            if etape['kwh_apres'] is None:
                continue
            self.assertEqual(etape['motif_omission'], '', etape['etape'])
            self.assertIsNotNone(etape['source'],
                                 f"étape « {etape['etape']} » : une étape "
                                 'appliquée nomme la source de son entrée.')


class MotifServiLisibleTest(unittest.TestCase):
    """ACAL1323 — le motif servi à l'écran dit le champ en intitulé de métier ;
    le chemin reste la donnée stockée relue par ``a_renseigner``."""

    def test_motif_d_omission_lisible_champ_conserve_aucun_chemin(self):
        import copy
        import re

        from apps.calepinage.services import a_renseigner
        from apps.calepinage.services.etapes import etape_omise
        from apps.calepinage.services.rapport.champs_lisibles import (
            avec_motifs_lisibles,
        )

        etape = dict(etape_omise('Ombrage proche', 'Aucune matrice.',
                                 champ='ombrage.shading12x24'),
                     etape='ombrage_proche')
        cascade = {'etapes': [etape]}
        cascade['a_renseigner'] = a_renseigner.construire(
            cascade, ['ombrage_proche'])
        stocke = {'cascade': cascade, 'autoconsommation': {
            'motif_absence': 'Absent. Champ manquant : « ombrage.solarAccess ».'}}
        avant = copy.deepcopy(stocke)
        servi = avec_motifs_lisibles(stocke)
        self.assertEqual(
            servi['cascade']['etapes'][0]['motif_omission'],
            "Aucune matrice. Champ manquant : « matrice d'ombrage 12 mois "
            "× 24 heures ».")
        hors = servi['cascade']['a_renseigner']['non_localisables'][0]
        self.assertEqual(hors['champ'], 'ombrage.shading12x24')
        self.assertEqual(stocke, avant, 'le résultat stocké ne bouge pas')

        def textes(noeud, cle=''):
            if isinstance(noeud, str) and cle != 'champ':
                yield noeud
            for c, v in (noeud.items() if isinstance(noeud, dict) else
                         enumerate(noeud) if isinstance(noeud, list) else ()):
                yield from textes(v, c)

        chemin = re.compile(r'[A-Za-z_]\w*\.[A-Za-z_]\w+|[\[\]]')
        for texte in textes(servi):
            self.assertIsNone(chemin.search(texte), texte)

    def test_acal1654_aucun_code_servi_source_lisible_motif_unique(self):
        # Ni « (CALX170) » ni « core.calepinage.soleil (CALX146) », la source
        # « texte » se lit « page publiée », une phrase n'est servie qu'une
        # fois ; le stocké ne bouge pas. Mutant : code servi ⇒ échec.
        import copy
        import re

        from apps.calepinage.services.rapport.champs_lisibles import (
            avec_motifs_lisibles,
        )

        phrase = 'Aucune fiche thermique publiée (CALX170).'
        stocke = {'cascade': {'etapes': [
            {'etape': 'thermique', 'motif_omission': ' '.join([phrase] * 5),
             'source': None},
            {'etape': 'horizon', 'motif_omission': '', 'source': 'texte',
             'reference': 'core.calepinage.soleil (CALX146)'},
            {'etape': 'iam', 'motif_omission': '', 'source': 'fiche',
             'reference': 'https://www.pvsyst.com/help/iam.html'}]}}
        avant = copy.deepcopy(stocke)
        thermique, horizon, iam = avec_motifs_lisibles(stocke)['cascade']['etapes']
        self.assertEqual(thermique['motif_lisible'], 'Aucune fiche thermique publiée.')
        # Revue lot 6 — le code est servi tel quel : l'écran le nomme par SA
        # table (« Page publiée », DiagrammePertes.jsx::SOURCE_LABELS).
        self.assertEqual(horizon['source'], 'texte')
        self.assertEqual(horizon['reference'], 'position du soleil')
        self.assertEqual((iam['source'], iam['reference']),
                         ('fiche', 'https://www.pvsyst.com/help/iam.html'))
        for etape in (thermique, horizon):
            self.assertIsNone(re.search(r'CALX\d+', str(etape)), etape)
        self.assertEqual(stocke, avant, 'le résultat stocké ne bouge pas')


class MotifsEnFrancaisDeMetierTest(unittest.TestCase):
    """ACAL1655 — aucun motif d'omission de la vraie cascade ne parle le
    jargon de développeur (« v1 », « PV*SOL assume », « littéral de code »,
    « n'est pas dérate », « fiche de le module », majuscules d'insistance)."""

    SERIE = {'pas_minutes': 60, 'colonne_energie': 'p_w', 'points': [{
        'annee': 2020, 'mois': 6, 'jour': 21, 'heure': 11,
        'gb_i_w_m2': 800.0, 'gd_i_w_m2': 150.0, 'gr_i_w_m2': 50.0,
        'gi_w_m2': 1000.0, 'p_w': 4000.0}]}

    ACRONYMES = {'STC', 'MPPT', 'PVGIS', 'LID', 'IAM', 'NOCT', 'TRI', 'DEM'}

    def test_les_motifs_de_la_cascade_reelle_sont_du_francais_de_metier(self):
        import re

        from apps.calepinage.services.chaine_pertes import appliquer_chaine

        _serie, cascade = appliquer_chaine(self.SERIE, {})
        motifs = [(e['etape'], e['motif_omission'])
                  for e in cascade['etapes'] if e['motif_omission']]
        self.assertGreater(len(motifs), 5)  # le cas porte bien des omissions
        for etape, motif in motifs:
            for interdit in ('en v1', 'PV*SOL', 'littéral', "n'est pas dérate",
                             'silence est explicite', 'fiche de le ',
                             'TOUJOURS_OMISES', 'DÉJÀ'):
                self.assertNotIn(interdit, motif, etape)
            criees = [m for m in re.findall(r'\b[A-ZÀ-Ý]{4,}\b', motif)
                      if m not in self.ACRONYMES]
            self.assertEqual(criees, [], (etape, motif))


class AdressesPublieesIntactesTest(unittest.TestCase):
    """Revue lot 6 (ACAL1654/1656) — une adresse publiée citée comme source
    ressort de ``motif_lisible`` EXACTE (« array-incidence-loss-iam.html »
    devenait « array-incidence-loss-une donnée »). Les adresses sont relevées
    dans les VALEURS des modules qui les publient (modules importés, leurs
    constantes parcourues — aucun fichier source lu, ATST53) : une adresse
    ajoutée à une référence est couverte."""

    def test_toute_adresse_des_etapes_ressort_telle_quelle(self):
        import importlib
        import pkgutil
        import re

        from apps.calepinage.services import etapes
        from apps.calepinage.services.rapport.champs_lisibles import motif_lisible

        noms = (['apps.calepinage.services.etapes.' + m.name
                 for m in pkgutil.iter_modules(etapes.__path__)]
                + ['apps.calepinage.services.etapes', 'apps.calepinage.services.chaine_pertes',
                   'apps.calepinage.services.transposition', 'apps.calepinage.services.pvgis_serie'])
        textes = []

        def recueillir(valeur, profondeur=0):
            if isinstance(valeur, str):
                textes.append(valeur)
            elif isinstance(valeur, dict) and profondeur < 4:
                for v in valeur.values():
                    recueillir(v, profondeur + 1)
            elif isinstance(valeur, (list, tuple, set, frozenset)) and profondeur < 4:
                for v in valeur:
                    recueillir(v, profondeur + 1)

        for nom in noms:
            module = importlib.import_module(nom)
            recueillir(module.__doc__ or '')
            for valeur in vars(module).values():
                recueillir(valeur)
        adresses = {a.rstrip('.,;:') for texte in textes
                    for a in re.findall(r'https?://[^\s\'"»)<>]+', texte)}
        self.assertGreater(len(adresses), 20)
        for adresse in sorted(adresses):
            with self.subTest(adresse=adresse):
                self.assertEqual(motif_lisible(adresse), adresse)
                phrase = 'PVsyst (CALX146) — %s.' % adresse
                self.assertEqual(motif_lisible(phrase), 'PVsyst — %s.' % adresse)


class PasDeDeriveTest(unittest.TestCase):
    """Le bloc détaillé ici reste celui que CALX4 annonce, et `pertes` reste
    une LISTE (D-CALX 11)."""

    def test_memes_clefs_que_le_bloc_cascade_de_calx4(self):
        for etat, jumeau in (('exemple', 'exemple'),
                             ('exemple_vide', 'exemple_vide')):
            self.assertEqual(
                sorted(CASCADE[etat]['cascade']),
                sorted(SIMULATION[jumeau]['cascade']),
                f'{etat} : les clés du bloc ont divergé de '
                'calepinage_simulation.json (CALX4).')
        self.assertEqual(
            set(SIMULATION['exemple']['cascade']['etapes'][0]), CLES_ETAPE)

    def test_pertes_reste_une_liste_plate_partout(self):
        for document, nom in ((SIMULATION, 'calepinage_simulation.json'),
                              (RESULTAT, 'calepinage_resultat.json')):
            for etat in document:
                if not etat.startswith('exemple'):
                    continue
                if 'pertes' not in document[etat]:
                    continue
                self.assertIsInstance(
                    document[etat]['pertes'], list,
                    f"{nom} ({etat}) : « pertes » doit rester une LISTE "
                    'plate — quatre lecteurs l’itèrent déjà (D-CALX 11).')


class LimitesConnuesTest(unittest.TestCase):
    """ACAL749 — chaque limite servie est VRAIE contre le code."""

    def test_chaque_limite_est_vraie_contre_le_code(self):
        import re

        from apps.calepinage.services.chaine_pertes import ORDRE_ETAPES
        from apps.calepinage.services.export_csv import (
            PAS_DISPONIBLES, ExportImpossible, _valider_pas)
        from apps.calepinage.services.limites_connues import limites_connues

        servies = limites_connues(ORDRE_ETAPES)
        codes = [limite['code'] for limite in servies]
        self.assertEqual(codes, ['pas_horaire', 'suiveurs', 'courbe_iv',
                                 'charges_structure'])
        # pas_horaire ⇔ l'export refuse le pas du quart d'heure.
        self.assertIn('15min', PAS_DISPONIBLES)
        with self.assertRaises(ExportImpossible) as refus:
            _valider_pas('15min')
        self.assertEqual(refus.exception.champ, 'pas')
        # suiveurs ⇔ aucune étape « tracker » dans la chaîne.
        self.assertFalse([nom for nom in ORDRE_ETAPES if 'tracker' in nom
                          or 'suiveur' in nom])
        # ombrage_diffus ⇔ absent d'ORDRE_ETAPES (livré par ACAL461).
        self.assertIn('ombrage_diffus', ORDRE_ETAPES)
        sans = tuple(nom for nom in ORDRE_ETAPES if nom != 'ombrage_diffus')
        self.assertEqual(limites_connues(sans)[-1]['code'], 'ombrage_diffus')
        for limite in servies + limites_connues(sans):
            self.assertEqual(sorted(limite), ['code', 'texte_en', 'texte_fr'])
            for texte in (limite['texte_fr'], limite['texte_en']):
                self.assertIsNone(re.search(r'\d', texte), texte)

    def test_le_contrat_porte_la_liste_servie(self):
        from apps.calepinage.services.chaine_pertes import ORDRE_ETAPES
        from apps.calepinage.services.limites_connues import limites_connues

        self.assertEqual(CASCADE['exemple']['cascade']['limites_connues'],
                         limites_connues(ORDRE_ETAPES))
        self.assertEqual(CASCADE['exemple_vide']['cascade']['limites_connues'],
                         [])


class OmbrageChainesTest(unittest.TestCase):
    """ACAL711/713 — la variante `exemple_ombrage_chaines` (deux pans)."""

    def test_les_chaines_des_deux_pans_et_leurs_bornes(self):
        etape = CASCADE['exemple_ombrage_chaines']['cascade']['etapes'][0]
        self.assertEqual(set(etape), CLES_ETAPE)
        self.assertEqual(etape['etape'], 'mismatch_ombrage')
        entree = etape['entree']
        self.assertEqual(entree['pans'], ['P1', 'P2'])
        self.assertIsNone(entree['bornes'])
        self.assertTrue(entree['bornes_motif'])
        for chaine in entree['chaines']:
            for cle in ('bornes', 'ecart_bornes_pct', 'modules_ombres',
                        'module_le_plus_ombre'):
                self.assertIn(cle, chaine)
        self.assertEqual(sorted(entree['hypothese_orientation']),
                         ['orientation', 'texte'])


class PlagesTest(unittest.TestCase):
    """ACAL702 — la pastille se calcule à partir de bandes écrites ICI
    (nombres INVENTÉS pour le test, jamais le fichier réel)."""

    BANDES = {'bandes': [
        {'etape': 'thermique', 'min': 5.0, 'max': 9.0, 'unite': '%',
         'url': 'https://exemple.invalid/thermique',
         'date_lecture': '2026-11-21', 'citation': 'phrase de test'},
        {'etape': 'ohmique_dc', 'min': 0.2, 'max': 0.5, 'unite': '%',
         'url': 'https://exemple.invalid/dc', 'date_lecture': '2026-11-21',
         'citation': 'phrase de test'},
        {'etape': 'bifacial', 'min': 0.0, 'max': 1.0, 'unite': '%',
         'url': 'https://exemple.invalid/bif', 'date_lecture': '2026-11-21',
         'citation': 'phrase de test'},
    ], 'total': {'min': 1.0, 'max': 5.0, 'unite': '%',
                 'url': 'https://exemple.invalid/total',
                 'date_lecture': '2026-11-21', 'citation': 'phrase de test'}}

    def _attendu(self, valeur, bas, haut):
        return 'dans_la_plage' if bas <= valeur <= haut else 'inhabituel'

    def test_dans_la_plage_au_dessus_et_sans_bande(self):
        from apps.calepinage.services.plages_usuelles import evaluer

        cascade = CASCADE['exemple']['cascade']
        plages = evaluer(cascade, self.BANDES)
        par_nom = {e['etape']: e for e in cascade['etapes']}
        # thermique 8,0 dans [5 ; 9] ; ohmique_dc 0,8 au-dessus de 0,5.
        self.assertEqual(plages['etapes']['thermique']['statut'],
                         self._attendu(par_nom['thermique']['perte_pct'],
                                       5.0, 9.0))
        self.assertEqual(plages['etapes']['thermique']['statut'],
                         'dans_la_plage')
        self.assertEqual(plages['etapes']['ohmique_dc']['statut'],
                         'inhabituel')
        # un gain, une étape omise ou sans bande : ABSENTS.
        for absente in ('bifacial', 'spectral', 'indisponibilite',
                        'irradiation_plan'):
            self.assertNotIn(absente, plages['etapes'])
        self.assertEqual(plages['total']['statut'], 'inhabituel')
        self.assertEqual(plages['etapes']['thermique']['url'],
                         'https://exemple.invalid/thermique')

    def test_acal1625_une_bande_servie_porte_url_et_citation(self):
        # Le FICHIER réel porte au moins une bande citée mot pour mot (LID,
        # PVsyst) ; servie, elle dit son url et sa phrase. Mutant : une bande
        # sans citation n'est pas lue (aucune pastille, motif d'absence).
        from apps.calepinage.services.plages_usuelles import charger, evaluer

        bandes = charger()['bandes']
        self.assertTrue(bandes)
        for bande in bandes:
            self.assertTrue(bande['url'].startswith('https://'), bande['etape'])
            self.assertTrue(bande['citation'].strip(), bande['etape'])
        lid = next(b for b in bandes if b['etape'] == 'lid')
        self.assertIn('typically ranges from 1% to 3%', lid['citation'])
        # La valeur jugée est tirée de la bande elle-même (milieu, puis moitié du
        # minimum) : aucune perte chiffrée en dur (garde CAL238).
        milieu = (lid['min'] + lid['max']) / 2
        cascade = {'etapes': [{'etape': 'lid', 'perte_pct': milieu, 'motif_omission': '',
                               'gain': False, 'entree': {'ligne_retenue': 'perc'}}],
                   'total_pct': None}
        plages = evaluer(cascade)
        self.assertEqual(plages['etapes']['lid']['statut'], 'dans_la_plage')
        self.assertEqual(plages['etapes']['lid']['url'], lid['url'])
        self.assertEqual(plages['etapes']['lid']['citation'], lid['citation'])
        self.assertEqual(plages['motif_absence'], '')
        # Revue lot 6 — la bande ne juge que la ligne où sa source s'applique :
        # un module de type n (TOPCon) à 0,5 % n'est PAS « inhabituel ».
        for ligne in ('topcon', 'hjt', 'inconnue', None):
            with self.subTest(ligne=ligne):
                type_n = {'etapes': [dict(cascade['etapes'][0], perte_pct=lid['min'] / 2,
                                          entree={'ligne_retenue': ligne})], 'total_pct': None}
                self.assertNotIn('lid', evaluer(type_n)['etapes'])
        sans_citation = {'bandes': [dict(lid, citation='')]}
        plages = evaluer(cascade, sans_citation)
        self.assertEqual(plages['etapes'], {})
        self.assertEqual(plages['motif_absence'], 'aucune bande sourcée')

    def test_fichier_vide_aucune_pastille(self):
        from apps.calepinage.services.plages_usuelles import evaluer

        plages = evaluer(CASCADE['exemple']['cascade'], {})
        self.assertEqual(plages['etapes'], {})
        self.assertIsNone(plages['total'])
        self.assertEqual(plages['motif_absence'], 'aucune bande sourcée')

    def test_echantillons_portent_les_plages(self):
        for etat in ('exemple', 'exemple_vide'):
            bloc = CASCADE[etat]['cascade']['plages']
            self.assertEqual(sorted(bloc),
                             ['etapes', 'motif_absence', 'total'])
            self.assertTrue(set(bloc['etapes']) <= set(
                e['etape'] for e in CASCADE[etat]['cascade']['etapes']))


if __name__ == '__main__':
    unittest.main()
