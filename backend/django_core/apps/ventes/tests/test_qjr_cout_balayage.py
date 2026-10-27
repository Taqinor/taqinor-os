"""QJR112 — le coût du balayage par appel : la MESURE, et le résidu assumé.

CE QUE CE MODULE TIENT. L'empreinte (QJR43/QJR44/QJR47) supprime les balayages
INUTILES ; elle ne rend pas le balayage NÉCESSAIRE moins cher. QJR112 a
tranché : le coût reste un **résidu assumé**, documenté dans
``docs/audit-parcours-devis-surfaces-non-auditees.md`` (section « Résidu assumé
— le coût du balayage par appel »), et gardé ici.

CE QUI EST MESURÉ, ET CE QUI NE L'EST PAS. Ce module mesure le **volume
d'appels** d'un balayage — le nombre de tailles candidates, et le nombre de
compositions et de journées simulées qu'il entraîne. Il ne mesure AUCUNE durée
en secondes : la mesurer demande une base (le catalogue est lu en base), et un
wall-clock inventé serait un chiffre inventé. Le volume, lui, se dérive d'une
fonction PURE (:func:`~apps.ventes.dimensionnement.bornes_candidates`) — ces
tests ne touchent donc NI base, NI réseau, NI catalogue.

CE QUE CES TESTS FONT ROUGIR :

1. un profil résidentiel typique qui se mettrait à balayer beaucoup plus de
   tailles (une borne relâchée, une parité mal calculée) ;
2. le garde-fou de saisie aberrante (une facture avec un zéro de trop) qui
   cesserait de plafonner ;
3. le partage du parcours des douze jours types entre toutes les capacités —
   la propriété qui divise le coût par dix-sept, et que le constat d'origine
   ignorait ;
4. **la NOTE DE RÉSIDU qui dériverait du code** : le bloc ``QJR112-CHIFFRES``
   de l'audit est relu ici et comparé aux constantes vivantes. Une note qui
   pourrit dans son coin serait pire que pas de note du tout — c'est le même
   raisonnement que PACT10 sur les échantillons de contrat.

Lancer :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_qjr_cout_balayage -v 2
"""
import math
import re
from pathlib import Path

from django.test import SimpleTestCase

from apps.ventes import balayage_adaptatif as B
from apps.ventes import dimensionnement as D

#: Les deux choisisseurs que le balayage adaptatif reçoit en argument.
CHOISIRS = (D.choisir_recommandation, D.choisir_recommandation_avec)

#: La note de résidu, et le bloc machine qu'elle porte. ``parents[5]`` est la
#: racine du dépôt : tests → ventes → apps → django_core → backend → racine.
NOTE = (Path(__file__).resolve().parents[5] / 'docs'
        / 'audit-parcours-devis-surfaces-non-auditees.md')
_BLOC = re.compile(r"<!--\s*QJR112-CHIFFRES(?P<corps>.*?)-->", re.S)
_LIGNE = re.compile(r"^(?P<clef>[A-Z0-9_]+)=(?P<valeur>\S+)$")

#: Productible et wattage de référence des mesures ci-dessous — les deux
#: entrées de ``bornes_candidates`` qui ne dépendent pas du client. 1 650
#: kWh/kWc est l'ordre de grandeur marocain ; 550 W le panneau de référence du
#: catalogue. Ce ne sont pas des chiffres publiés au client : ce sont les
#: paramètres de LA MESURE, et ils sont écrits pour qu'elle soit rejouable.
PRODUCTIBLE_KWH_KWC = 1650
PANEL_WATT = 550

#: Les trois profils mesurés, et leur consommation annuelle. Chaque nombre est
#: un ordre de grandeur de facture résidentielle marocaine, pas une donnée
#: client.
PROFILS = (
    ('TAILLES_PETIT', 4800),
    ('TAILLES_MEDIAN', 9600),
    ('TAILLES_GROS', 19000),
)


def chiffres_de_la_note():
    """``{clef: texte}`` du bloc ``QJR112-CHIFFRES`` de l'audit."""
    bloc = _BLOC.search(NOTE.read_text(encoding='utf-8'))
    if bloc is None:
        return {}
    valeurs = {}
    for ligne in bloc.group('corps').splitlines():
        trouve = _LIGNE.match(ligne.strip())
        if trouve:
            valeurs[trouve.group('clef')] = trouve.group('valeur')
    return valeurs


def tailles_balayees(conso_annuelle_kwh):
    """Le nombre de tailles qu'un balayage explore pour cette consommation.

    Lecture PURE de ``bornes_candidates`` — sans ``sonde_residuel``, donc sans
    l'extension « chasse à la falaise » (celle-ci ne s'active que lorsque
    l'appelant fournit une cible ET une sonde).
    """
    mini, maxi = D.bornes_candidates(
        conso_annuelle_kwh=conso_annuelle_kwh,
        productible_annuel_kwh_kwc=PRODUCTIBLE_KWH_KWC,
        panel_watt=PANEL_WATT)
    return maxi - mini + 1


class VolumeDuBalayageTests(SimpleTestCase):
    """La mesure elle-même — aucune base, aucun catalogue."""

    def test_un_profil_residentiel_typique_balaie_7_a_22_tailles(self):
        mesures = {clef: tailles_balayees(conso) for clef, conso in PROFILS}
        self.assertEqual(mesures, {'TAILLES_PETIT': 7, 'TAILLES_MEDIAN': 12,
                                   'TAILLES_GROS': 22},
                         'le volume d\'un balayage résidentiel a CHANGÉ : '
                         'mettre à jour le bloc QJR112-CHIFFRES de '
                         'docs/audit-parcours-devis-surfaces-non-auditees.md '
                         'dans le MÊME commit, et relire la note de résidu.')
        # Le pire cas absolu n'est PAS une charge normale : c'est le garde-fou.
        # 23/10/2026 — et un profil résidentiel typique reste sous le seuil du
        # balayage DENSE : il est évalué taille par taille, byte-identique.
        for valeur in mesures.values():
            self.assertLess(valeur, D.MAX_PANNEAUX_BALAYAGE)
            self.assertLessEqual(valeur, B.SEUIL_BALAYAGE_DENSE)

    def test_le_zero_de_trop_est_signale_puis_plafonne(self):
        """Décision fondateur du 23/10/2026 : un gros profil n'est plus REFUSÉ
        à 120 panneaux — il est SIGNALÉ (``SEUIL_PANNEAUX_RESIDENTIEL``) et
        dimensionné par la grille grossière ; seul le plafond dur
        (``MAX_PANNEAUX_BALAYAGE``, 2 000 panneaux) tronque encore. Un zéro de
        trop sur une facture MÉDIANE (107 tailles) reste sous le seuil ; sur
        une GROSSE facture (222 à 200 000 kWh/an) il passe le seuil sans
        toucher le plafond ; deux zéros de trop (2 000 000 kWh/an) touchent le
        plafond. La note de résidu porte ces trois volumes.
        """
        note = chiffres_de_la_note()
        self.assertEqual(tailles_balayees(96000),
                         int(note['TAILLES_ZERO_DE_TROP']))
        self.assertLessEqual(tailles_balayees(96000),
                             B.SEUIL_PANNEAUX_RESIDENTIEL)
        self.assertEqual(tailles_balayees(200000),
                         int(note['TAILLES_200000']))
        self.assertGreater(tailles_balayees(200000),
                           B.SEUIL_PANNEAUX_RESIDENTIEL)
        self.assertLessEqual(tailles_balayees(200000), D.MAX_PANNEAUX_BALAYAGE)
        self.assertGreater(tailles_balayees(2000000), D.MAX_PANNEAUX_BALAYAGE)

    def test_une_entree_absente_ne_balaie_rien(self):
        """« On ne balaie pas dans le vide » — 0 taille, jamais un défaut."""
        for conso in (0, None, -1):
            with self.subTest(conso=conso):
                self.assertEqual(
                    D.bornes_candidates(
                        conso_annuelle_kwh=conso,
                        productible_annuel_kwh_kwc=PRODUCTIBLE_KWH_KWC,
                        panel_watt=PANEL_WATT), (0, 0))

    def test_le_cout_par_taille_est_borne_par_les_constantes_nommees(self):
        """Une composition SANS batterie + au plus MAX_PALIERS_STOCKAGE AVEC."""
        self.assertIsInstance(D.MAX_PALIERS_STOCKAGE, int)
        self.assertGreater(D.MAX_PALIERS_STOCKAGE, 0)
        # 23/10/2026 — le pire cas n'est plus « plafond × paliers » : la grille
        # grossière borne le nombre de tailles ÉVALUÉES quel que soit le
        # plafond (``tailles_max_evaluees``), chacune avec une composition sans
        # batterie et au plus MAX_PALIERS_STOCKAGE paliers.
        note = chiffres_de_la_note()
        self.assertEqual(B.tailles_max_evaluees(D.MAX_PANNEAUX_BALAYAGE),
                         int(note['TAILLES_MAX_EVALUEES']),
                         'le pire cas du balayage a bougé : la note de résidu '
                         'le chiffre, elle doit bouger aussi.')
        pire_cas = B.tailles_max_evaluees(D.MAX_PANNEAUX_BALAYAGE) * (1 + D.MAX_PALIERS_STOCKAGE)
        self.assertEqual(pire_cas, 237 * 17)

    def test_les_douze_jours_types_sont_PARTAGES_entre_les_capacites(self):
        """LA propriété qui divise le coût par dix-sept.

        Le constat d'origine annonçait « 12 jours × 17 capacités PAR taille ».
        C'est faux et c'est écrit dans le moteur : un SEUL parcours des douze
        jours types sert TOUTES les capacités. Si cette phrase disparaît de la
        docstring, c'est que quelqu'un a touché à la boucle — et le chiffre du
        résidu est alors à refaire.
        """
        from apps.ventes.etude_horaire import balayer_stockage_horaire
        docstring = (balayer_stockage_horaire.__doc__ or '')
        self.assertIn('UN SEUL parcours des douze jours types', docstring)
        self.assertIn('TOUTES les capacités', docstring)


class NoteDeResiduTests(SimpleTestCase):
    """La note et le code ne peuvent pas diverger."""

    def test_la_note_de_residu_existe_et_porte_son_bloc_machine(self):
        self.assertTrue(NOTE.is_file(), f'note introuvable : {NOTE}')
        texte = NOTE.read_text(encoding='utf-8')
        self.assertIn('Résidu assumé — le coût du balayage par appel', texte)
        self.assertTrue(chiffres_de_la_note(),
                        'le bloc QJR112-CHIFFRES a disparu de la note')

    def test_les_constantes_de_la_note_sont_celles_du_code(self):
        note = chiffres_de_la_note()
        self.assertEqual(int(note['MAX_PANNEAUX_BALAYAGE']),
                         D.MAX_PANNEAUX_BALAYAGE)
        self.assertEqual(int(note['SEUIL_PANNEAUX_RESIDENTIEL']),
                         B.SEUIL_PANNEAUX_RESIDENTIEL)
        self.assertEqual(int(note['SEUIL_BALAYAGE_DENSE']),
                         B.SEUIL_BALAYAGE_DENSE)
        self.assertEqual(int(note['POINTS_GRILLE_GROSSIERE']),
                         B.POINTS_GRILLE_GROSSIERE)
        self.assertEqual(int(note['MAX_PALIERS_STOCKAGE']),
                         D.MAX_PALIERS_STOCKAGE)
        self.assertEqual(float(note['FACTEUR_MAX_FALAISE']),
                         float(D.FACTEUR_MAX_FALAISE))

    def test_les_volumes_de_la_note_sont_ceux_qu_on_mesure(self):
        note = chiffres_de_la_note()
        for clef, conso in PROFILS:
            with self.subTest(profil=clef):
                self.assertEqual(int(note[clef]), tailles_balayees(conso),
                                 f'{clef} : la note et la mesure divergent')

    def test_le_plafond_de_falaise_de_la_note_se_recalcule(self):
        """La colonne « plafond si la chasse à la falaise s'étend »."""
        note = chiffres_de_la_note()
        parite = math.ceil((19000 / PRODUCTIBLE_KWH_KWC) * 1000.0 / PANEL_WATT)
        plafond = min(D.MAX_PANNEAUX_BALAYAGE,
                      math.ceil(parite * float(note['FACTEUR_MAX_FALAISE'])))
        self.assertEqual(plafond, 42)


def _ligne_factice(panneaux):
    """Une ligne de tableau FABRIQUÉE (même forme minimale que
    ``test_qjr411_plafond_message_honnete._ligne_tableau``) dont l'économie
    est concave : le meilleur payback tombe vers 300 panneaux, puis chaque
    panneau de plus rapporte moins — la montée s'arrête d'elle-même."""
    cout = 4000.0 * panneaux
    economie = 1200.0 * panneaux * max(0.0, 1.0 - panneaux / 1500.0) + 200.0
    payback = D._payback(cout, economie)
    return {
        'panneaux': panneaux, 'kwc': round(panneaux * 0.71, 3),
        'composable': True,
        'payback_sans_annees': None if payback is None else round(payback, 2),
        'cout_sans_ttc': cout, 'economie_sans_mad': economie,
        'couverture_sans': min(1.0, panneaux / 700.0),
        'verdicts_bloquants_sans': [], 'verdicts_bloquants_avec': [],
        'batterie_disponible': False, 'payback_avec_annees': None,
        'residuel_kwh_mois': 400.0, 'batterie_kwh': 0.0,
        'balayage_stockage': [], 'avertissements': [],
    }


class BalayageAdaptatifTests(SimpleTestCase):
    """Décision fondateur du 23/10/2026 — « adaptive sweep » : les fonctions
    PURES de la grille, et le volume d'évaluations qu'elle garantit."""

    def test_le_pas_vaut_1_sous_le_seuil_dense_puis_environ_40_points(self):
        for fin in (1, 7, 22, 39, B.SEUIL_BALAYAGE_DENSE):
            self.assertEqual(B.pas_balayage(fin), 1, fin)
        self.assertEqual(B.pas_balayage(B.SEUIL_BALAYAGE_DENSE + 1), 2)
        self.assertEqual(B.pas_balayage(660), 17)
        self.assertEqual(B.pas_balayage(D.MAX_PANNEAUX_BALAYAGE), 50)
        for fin in (61, 140, 660, 2000):
            with self.subTest(fin=fin):
                self.assertLessEqual(
                    len(B.tailles_grille(1, fin, B.pas_balayage(fin))),
                    B.POINTS_GRILLE_GROSSIERE + 1)

    def test_la_grille_dense_est_byte_identique_a_l_intervalle(self):
        for debut, fin in ((1, 39), (3, 3), (1, 60)):
            with self.subTest(debut=debut, fin=fin):
                self.assertEqual(B.tailles_grille(debut, fin, 1),
                                 list(range(debut, fin + 1)))
        self.assertEqual(B.tailles_grille(5, 4, 1), [])

    def test_la_grille_grossiere_inclut_toujours_les_deux_bornes(self):
        grille = B.tailles_grille(1, 660, 17)
        self.assertEqual(grille[0], 1)
        self.assertEqual(grille[-1], 660)
        self.assertEqual(grille, sorted(set(grille)))

    def test_le_raffinement_ajoute_les_voisins_bornes_sans_doublon(self):
        grille = B.tailles_grille(1, 660, 17)
        tailles = B.tailles_raffinees(grille, [290, 660], 17, 1, 660)
        self.assertEqual(tailles, sorted(set(tailles)))
        self.assertTrue(set(range(274, 307)).issubset(tailles))
        self.assertTrue(set(range(644, 661)).issubset(tailles))
        self.assertEqual(tailles[-1], 660)
        self.assertLessEqual(len(tailles), len(grille) + 2 * (2 * 17 - 2))

    def test_le_tableau_adaptatif_est_exact_au_panneau_pour_un_volume_borne(self):
        """Sur 660 tailles candidates, la grille (≤ 41) plus le raffinement
        autour de la recommandation : moins de 41 + 2 × (2 × 17 − 2)
        évaluations, et la taille retenue est entourée de ses voisines
        immédiates — elle est exacte au panneau, pas à la grille."""
        appels = []

        def evaluer(panneaux):
            appels.append(panneaux)
            return _ligne_factice(panneaux)

        pas = B.pas_balayage(660)
        tableau = B.tableau_adaptatif(evaluer, 1, 660, False, CHOISIRS)
        self.assertLessEqual(len(set(appels)), 41 + 2 * (2 * pas - 2))
        reco, motivation = D.choisir_recommandation(tableau)
        self.assertIsNotNone(reco)
        tailles = {ligne['panneaux'] for ligne in tableau}
        self.assertIn(reco['panneaux'] - 1, tailles)
        self.assertIn(reco['panneaux'] + 1, tailles)
        # Toute ligne porte le pas ; celles au-dessus du seuil sont SIGNALÉES
        # et la recommandation (> 120) porte le signal dans sa motivation.
        self.assertTrue(all(ligne['pas_balayage'] == pas for ligne in tableau))
        for ligne in tableau:
            self.assertEqual(
                ligne.get('hors_residentiel', False),
                ligne['panneaux'] > B.SEUIL_PANNEAUX_RESIDENTIEL)
        self.assertGreater(reco['panneaux'], B.SEUIL_PANNEAUX_RESIDENTIEL)
        self.assertIn('étude sur mesure conseillée', motivation)

    def test_rsiz9_le_raffinement_se_reprend_quand_l_optimum_bouge(self):
        """Des creux cachés hors de la grille, chacun à 16 panneaux (un
        voisinage de raffinement) du précédent : chaque passe en révèle un
        de plus, et il y en a AU PLUS MAX_RAFFINEMENTS."""
        self.assertEqual(B.MAX_RAFFINEMENTS, 3)
        pas = B.pas_balayage(660)
        self.assertEqual(pas, 17)
        creux = {314: 1.0, 330: 2.0, 346: 3.0, 362: 4.0}   # grille = 1 + 17 k

        def evaluer(panneaux):
            ligne = _ligne_factice(panneaux)
            ligne['payback_annees'] = (
                5.0 + abs(panneaux - 300) * 0.01 - creux.get(panneaux, 0.0))
            return ligne

        def choisir(tableau):
            return min(tableau, key=lambda l: l['payback_annees']), ''

        appels = []

        def evaluer_compte(panneaux):
            appels.append(panneaux)
            return evaluer(panneaux)

        tableau = B.tableau_adaptatif(
            evaluer_compte, 1, 660, False, (choisir, choisir))
        retenu, _ = choisir(tableau)
        self.assertEqual(retenu['panneaux'], 346)   # 3 passes, pas la 4e
        self.assertNotIn(362, {ligne['panneaux'] for ligne in tableau})
        self.assertLessEqual(len(set(appels)),
                             41 + B.MAX_RAFFINEMENTS * 2 * (2 * pas - 2))

    def test_un_balayage_dense_ne_porte_aucune_cle_nouvelle(self):
        """Sous le seuil dense, les lignes ont EXACTEMENT la forme d'hier :
        ni ``pas_balayage`` ni ``hors_residentiel``, motivation inchangée."""
        tableau = B.tableau_adaptatif(_ligne_factice, 1, 39, False, CHOISIRS)
        self.assertEqual([ligne['panneaux'] for ligne in tableau],
                         list(range(1, 40)))
        for ligne in tableau:
            self.assertNotIn('pas_balayage', ligne)
            self.assertNotIn('hors_residentiel', ligne)
        reco, motivation = D.choisir_recommandation(tableau)
        self.assertIsNotNone(reco)
        self.assertNotIn('étude sur mesure', motivation)
