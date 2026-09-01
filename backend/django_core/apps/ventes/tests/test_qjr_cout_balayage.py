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

from apps.ventes import dimensionnement as D

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
        for valeur in mesures.values():
            self.assertLess(valeur, D.MAX_PANNEAUX_BALAYAGE)

    def test_le_garde_fou_ne_couvre_PAS_la_borne_de_parite(self):
        """LE POINT OUVERT TROUVÉ EN MESURANT, épinglé tel qu'il EST.

        ``MAX_PANNEAUX_BALAYAGE`` se décrit comme le garde-fou contre « une
        facture saisie avec un zéro de trop ». Mesuré : il ne s'applique qu'à
        l'EXTENSION « chasse à la falaise », pas à la borne de parité du chemin
        par défaut. Un zéro de trop sur une facture MÉDIANE reste sous le
        plafond (107) ; sur une GROSSE facture il l'explose (222 à 200 000
        kWh/an). Ce test épingle le comportement RÉEL — il n'affirme pas que
        c'est bien. Le jour où la borne de parité sera plafonnée (décision de
        moteur, hors périmètre de QJR112), il rougira et la note se corrigera
        avec lui.
        """
        note = chiffres_de_la_note()
        self.assertEqual(tailles_balayees(96000),
                         int(note['TAILLES_ZERO_DE_TROP']))
        self.assertLessEqual(tailles_balayees(96000), D.MAX_PANNEAUX_BALAYAGE)
        self.assertEqual(tailles_balayees(200000),
                         int(note['TAILLES_200000']))
        self.assertGreater(tailles_balayees(200000), D.MAX_PANNEAUX_BALAYAGE)

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
        pire_cas = D.MAX_PANNEAUX_BALAYAGE * (1 + D.MAX_PALIERS_STOCKAGE)
        self.assertEqual(pire_cas, 2040,
                         'le pire cas du balayage a bougé : la note de résidu '
                         'le chiffre, elle doit bouger aussi.')

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
