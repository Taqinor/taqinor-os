"""CAL46 — le contrat « site & imagerie » est GARDÉ, pas seulement publié.

POURQUOI CE FICHIER EXISTE (PACT10)
-----------------------------------
Un échantillon de contrat qui n'est vérifié par personne pourrit dans son coin :
il devient un document que deux lanes citent et qu'aucune ne respecte —
exactement l'incident du 03/08/2026 (« AO — Tableau de bord », zéro clé sur six
concordante), mais avec un fichier en plus pour se donner bonne conscience.

Ces tests sont donc la moitié VÉRIFIANTE de CAL46, et ils tiennent AVANT que la
moitié serveur (CAL47) n'existe : ils prouvent que le document publié est
cohérent avec lui-même et avec le contrat parent des sept sections
(``parametres_calepinage.json``, CAL45). Ce qui est prouvé ici :

* l'échantillon est un JSON lisible, portant ``endpoint`` + ``exemple`` (la
  forme qu'exige ``scripts/check_api_shapes.py``) ;
* il vise la MÊME route que le contrat parent et déclare la MÊME section
  qu'il documente, et cette section est une section ADMISE du modèle
  (``ParametresCalepinage.SECTIONS``) — on ne range pas un réglage dans un
  tiroir qui n'existe pas ;
* ses trois états (`exemple`, `exemple_vide`,
  `exemple_section_declaree_sans_valeur`) portent les SEPT mêmes sections :
  un état de serveur, jamais une autre FORME ;
* la section ``imagerie`` décrite a TOUTES ses clés dans les deux états où elle
  est réglée, et chaque clé est DOCUMENTÉE dans le bloc ``cles`` — une clé sans
  documentation est une clé que l'écran devinera ;
* ÉQUIVALENCE : l'état « jamais réglé » rend ``imagerie: {}`` — le comportement
  d'aujourd'hui, strictement inchangé, et AUCUNE valeur par défaut inventée ;
* ZÉRO CHIFFRE INVENTÉ : dans l'état « section déclarée, rien de connu »,
  ``altitude_m`` vaut ``null`` et jamais ``0`` — publier un zéro ferait lire
  « site au niveau de la mer » là où rien n'a été mesuré ;
* ``google_solar`` n'est PAS proposé par l'échantillon : il est gaté par CAL51.

Aucune moitié d'écran, aucune vue, aucun modèle n'est livré par CAL46 : ce
fichier et l'échantillon partent SEULS.

Run :
    python manage.py test apps.calepinage.tests.test_contracts -v2
"""
import json
import pathlib

from django.test import SimpleTestCase

from apps.calepinage.models import ParametresCalepinage

ECHANTILLONS = (pathlib.Path(__file__).resolve().parents[1]
                / 'contract_samples')

SITE = json.loads((ECHANTILLONS / 'site_imagerie.json')
                  .read_text(encoding='utf-8'))
PARAMETRES = json.loads((ECHANTILLONS / 'parametres_calepinage.json')
                        .read_text(encoding='utf-8'))

#: Les états de serveur publiés par l'échantillon (`exemple*`), dans l'ordre.
ETATS = ('exemple', 'exemple_vide', 'exemple_section_declaree_sans_valeur')

#: Les états où la section `imagerie` est RÉGLÉE (donc complète).
ETATS_REGLES = ('exemple', 'exemple_section_declaree_sans_valeur')

#: Les huit clés de la section, telles que CAL46 les fige. Les six premières
#: sont celles nommées par la tâche ; `fournisseurs_autorises` et
#: `attribution` sont exigées par CAL47 (liste ordonnée des fournisseurs
#: admis) et par la mention légale obligatoire de l'IGN.
CLES_IMAGERIE = (
    'pays',
    'fournisseur_imagerie',
    'fournisseurs_autorises',
    'calques_optionnels',
    'attribution',
    'altitude_m',
    'source_altitude',
    'fuseau',
)


class FormeEchantillonTest(SimpleTestCase):
    """La forme qu'exige `scripts/check_api_shapes.py`."""

    def test_endpoint_et_exemple_presents(self):
        self.assertTrue(str(SITE.get('endpoint', '')).startswith('GET /api/'),
                        SITE.get('endpoint'))
        self.assertIsInstance(SITE.get('exemple'), dict)

    def test_meme_route_que_le_contrat_parent(self):
        """La section vit DANS les réglages : même route, pas une seconde."""
        self.assertEqual(SITE['endpoint'], PARAMETRES['endpoint'])

    def test_forme_serveur_declaree_partielle(self):
        """Deux échantillons d'une même route : celui-ci ne porte qu'une
        section, il ne prétend donc pas à la carte complète (QJR228)."""
        self.assertEqual(SITE.get('forme_serveur'), 'partielle')

    def test_section_visee_est_une_section_admise(self):
        self.assertEqual(SITE.get('section'), 'imagerie')
        self.assertIn(SITE['section'], ParametresCalepinage.SECTIONS)

    def test_tous_les_etats_portent_les_memes_sections(self):
        from apps.calepinage.selectors import SECTIONS_LECTURE_SEULE
        attendu = sorted(k for k in PARAMETRES['exemple']
                         if k not in SECTIONS_LECTURE_SEULE)
        for etat in ETATS:
            self.assertEqual(sorted(SITE[etat]), attendu, etat)

    def test_chaque_section_est_un_objet(self):
        for etat in ETATS:
            for section, valeur in SITE[etat].items():
                self.assertIsInstance(valeur, dict, f'{etat}.{section}')


class SectionImagerieTest(SimpleTestCase):
    """Les huit clés, toujours présentes dès que la section existe."""

    def test_les_huit_cles_dans_les_etats_regles(self):
        for etat in ETATS_REGLES:
            self.assertEqual(sorted(SITE[etat]['imagerie']),
                             sorted(CLES_IMAGERIE), etat)

    def test_chaque_cle_est_documentee(self):
        self.assertEqual(sorted(SITE.get('cles', {})),
                         sorted(CLES_IMAGERIE))
        for cle, texte in SITE['cles'].items():
            self.assertTrue(str(texte).strip(), cle)

    def test_listes_et_scalaires_gardent_leur_nature(self):
        """Une liste reste une liste dans TOUS les états réglés."""
        listes = ('fournisseurs_autorises', 'calques_optionnels')
        for etat in ETATS_REGLES:
            for cle in listes:
                self.assertIsInstance(SITE[etat]['imagerie'][cle], list,
                                      f'{etat}.{cle}')

    def test_google_solar_n_est_pas_propose(self):
        """CAL51 garde Google Solar : aucun ÉTAT publié ne le propose.

        La prose (`pourquoi`) le NOMME au contraire, pour dire qu'il est gaté :
        seuls les états de serveur sont contrôlés ici.
        """
        for etat in ETATS_REGLES:
            section = SITE[etat]['imagerie']
            self.assertNotEqual(section['fournisseur_imagerie'],
                                'google_solar', etat)
            self.assertNotIn('google_solar', section['fournisseurs_autorises'],
                             etat)


class EquivalenceEtZeroInventeTest(SimpleTestCase):
    """Rien n'est deviné : ni un défaut, ni une altitude."""

    def test_jamais_regle_rend_une_section_vide(self):
        """« Comportement d'aujourd'hui, strictement inchangé. »"""
        self.assertEqual(SITE['exemple_vide']['imagerie'], {})

    def test_section_declaree_sans_valeur_est_toute_nulle(self):
        section = SITE['exemple_section_declaree_sans_valeur']['imagerie']
        for cle in ('pays', 'fournisseur_imagerie', 'attribution',
                    'altitude_m', 'source_altitude', 'fuseau'):
            self.assertIsNone(section[cle], cle)
        for cle in ('fournisseurs_autorises', 'calques_optionnels'):
            self.assertEqual(section[cle], [], cle)

    def test_altitude_inconnue_est_nulle_jamais_zero(self):
        """Un zéro publié ferait lire « niveau de la mer » — rien n'est mesuré."""
        section = SITE['exemple_section_declaree_sans_valeur']['imagerie']
        self.assertIsNone(section['altitude_m'])
        self.assertIsNone(section['source_altitude'])

    def test_une_altitude_renseignee_porte_sa_source(self):
        section = SITE['exemple']['imagerie']
        self.assertIsInstance(section['altitude_m'], (int, float))
        self.assertTrue(str(section['source_altitude']).strip())

    def test_le_fournisseur_actif_est_dans_la_liste_autorisee(self):
        section = SITE['exemple']['imagerie']
        self.assertIn(section['fournisseur_imagerie'],
                      section['fournisseurs_autorises'])

    def test_l_imagerie_ign_porte_son_attribution(self):
        """L'IGN impose sa mention : elle est STOCKÉE, jamais reconstruite."""
        section = SITE['exemple']['imagerie']
        self.assertEqual(section['fournisseur_imagerie'], 'ign_bd_ortho')
        self.assertIn('IGN', section['attribution'])
