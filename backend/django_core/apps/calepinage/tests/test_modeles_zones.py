"""CAL74 — servitudes et bandes coupe-feu : SOURCÉES, ou pas enregistrées.

LE POINT DE DÉPART, FACTUEL
---------------------------
Le dépôt ne contient AUCUN texte normatif marocain, et la doc du moteur l'écrit
noir sur blanc (pas de génération automatique d'exclusions réglementaires).
Inventer une bande coupe-feu « standard » parce que ça se fait ailleurs, ce
serait livrer un plan qu'aucun texte ne défend.

CE QUI EST PROUVÉ ICI
---------------------
* **UN GABARIT SANS SOURCE EST REFUSÉ**, avec un message français SOUS LE
  CHAMP fautif (``zones_types.<clé>.source``) — et rien n'est écrit en base ;
* **AUCUNE LARGEUR N'EST SUPPOSÉE** : une bande sans ``largeur_m`` saisie est
  refusée en nommant le champ, jamais complétée par un « standard » ;
* **LA SOURCE VOYAGE AVEC LA ZONE** : ``appliquer_modele`` rend une zone au
  format ``exclusionZones`` (CAL68) PORTANT sa clé ``source`` — c'est elle que
  la planche et le PDF citent à côté de la zone ;
* une zone sans source ne produit AUCUNE citation (chaîne vide) plutôt qu'une
  citation inventée ;
* **ÉQUIVALENCE** : une société sans gabarit garde ``zones_types: {}`` ;
* aucun nouveau modèle, aucune migration : tout vit dans la section
  ``zones_types`` de ``ParametresCalepinage`` (CAL45) ;
* l'isolation société tient.

Run :
    python manage.py test apps.calepinage.tests.test_modeles_zones -v2
"""
from django.test import SimpleTestCase, TestCase

from apps.calepinage.models import ParametresCalepinage
from apps.calepinage.selectors import parametres_de_societe
from apps.calepinage.services.parametres import (
    ReglageInvalide,
    enregistrer_parametres,
)
from apps.calepinage.services.zones import zones_moteur_depuis_layout
from apps.calepinage.services.zones_reglementaires import (
    COTES,
    GENRES,
    SECTION,
    appliquer_modele,
    normaliser_section_zones_types,
    source_de_zone,
)
from authentication.models import Company

SOURCE = "Arrêté préfectoral n° 2026-14, art. 7 — bande coupe-feu"

BANDE = {
    'libelle': 'Bande coupe-feu',
    'nature': 'INTERDITE',
    'genre': 'bande',
    'largeur_m': 1.2,
    'cote': 'nord',
    'source': SOURCE,
}

POLYGONE = {
    'libelle': 'Servitude de passage',
    'nature': 'INTERDITE',
    'genre': 'polygone',
    'sommets': [[0, 0], [3, 0], [3, 2], [0, 2]],
    'retrait_m': 0.5,
    'source': 'Convention de servitude du 03/02/2026, annexe 2',
}


class NormalisationTest(SimpleTestCase):
    """Ce qui est accepté est RANGÉ, et rien n'est supposé."""

    def test_bande_normalisee(self):
        section = normaliser_section_zones_types({'coupe_feu': BANDE})
        modele = section['coupe_feu']
        self.assertEqual(modele['largeur_m'], 1.2)
        self.assertEqual(modele['cote'], 'nord')
        self.assertEqual(modele['source'], SOURCE)
        self.assertEqual(modele['nature'], 'INTERDITE')
        self.assertEqual(modele['retrait_m'], 0.0)
        self.assertIsNone(modele['hauteur_m'])

    def test_polygone_normalise(self):
        modele = normaliser_section_zones_types(
            {'servitude': POLYGONE})['servitude']
        self.assertEqual(modele['sommets'],
                         [[0.0, 0.0], [3.0, 0.0], [3.0, 2.0], [0.0, 2.0]])
        self.assertEqual(modele['retrait_m'], 0.5)

    def test_cote_par_defaut_ne_restreint_rien(self):
        """« perimetre » est le seul repli qui ne restreint rien."""
        sans_cote = dict(BANDE)
        sans_cote.pop('cote')
        modele = normaliser_section_zones_types(
            {'coupe_feu': sans_cote})['coupe_feu']
        self.assertEqual(modele['cote'], 'perimetre')
        self.assertIn('perimetre', COTES)

    def test_section_vide_reste_vide(self):
        """ÉQUIVALENCE : sans gabarit, comportement d'aujourd'hui."""
        self.assertEqual(normaliser_section_zones_types({}), {})
        self.assertEqual(normaliser_section_zones_types(None), {})

    def test_les_genres_sont_bornes(self):
        self.assertEqual(GENRES, ('bande', 'polygone'))


class RefusTest(SimpleTestCase):
    """Chaque refus nomme SON champ, gabarit compris."""

    def _refus(self, section, champ):
        with self.assertRaises(ReglageInvalide) as capture:
            normaliser_section_zones_types(section)
        self.assertEqual(capture.exception.champ, champ,
                         str(capture.exception))
        return capture.exception

    def test_sans_source_refuse_sous_le_champ(self):
        """LA règle de la tâche."""
        sans_source = dict(BANDE)
        sans_source.pop('source')
        erreur = self._refus({'coupe_feu': sans_source},
                             'zones_types.coupe_feu.source')
        self.assertIn('SOURCE', str(erreur))
        self.assertIn('coupe_feu', str(erreur))

    def test_source_blanche_refusee(self):
        self._refus({'coupe_feu': dict(BANDE, source='   ')},
                    'zones_types.coupe_feu.source')

    def test_largeur_manquante_refusee(self):
        sans_largeur = dict(BANDE)
        sans_largeur.pop('largeur_m')
        erreur = self._refus({'coupe_feu': sans_largeur},
                             'zones_types.coupe_feu.largeur_m')
        self.assertIn('aucune valeur par défaut', str(erreur))

    def test_largeur_nulle_refusee(self):
        self._refus({'coupe_feu': dict(BANDE, largeur_m=0)},
                    'zones_types.coupe_feu.largeur_m')

    def test_nature_inconnue_refusee(self):
        self._refus({'coupe_feu': dict(BANDE, nature='SERVITUDE')},
                    'zones_types.coupe_feu.nature')

    def test_genre_inconnu_refuse(self):
        self._refus({'coupe_feu': dict(BANDE, genre='cercle')},
                    'zones_types.coupe_feu.genre')

    def test_cote_inconnu_refuse(self):
        self._refus({'coupe_feu': dict(BANDE, cote='nord-ouest')},
                    'zones_types.coupe_feu.cote')

    def test_cle_inconnue_refusee(self):
        self._refus({'coupe_feu': dict(BANDE, couleur='rouge')},
                    'zones_types.coupe_feu.couleur')

    def test_polygone_a_deux_sommets_refuse(self):
        self._refus(
            {'servitude': dict(POLYGONE, sommets=[[0, 0], [1, 0]])},
            'zones_types.servitude.sommets')

    def test_gabarit_qui_n_est_pas_un_objet(self):
        self._refus({'coupe_feu': 'bande de 1,2 m'}, 'zones_types.coupe_feu')

    def test_section_qui_n_est_pas_un_objet(self):
        self._refus(['coupe_feu'], SECTION)


class ApplicationTest(SimpleTestCase):
    """La source voyage avec la zone, jusqu'à la planche."""

    def setUp(self):
        self.modele = normaliser_section_zones_types(
            {'coupe_feu': BANDE})['coupe_feu']

    def test_zone_appliquee_porte_sa_source(self):
        zone = appliquer_modele(self.modele, cle='coupe_feu',
                                sommets=[[0, 0], [10, 0], [10, 1.2],
                                         [0, 1.2]])
        self.assertEqual(zone['source'], SOURCE)
        self.assertEqual(source_de_zone(zone), SOURCE)
        self.assertEqual(zone['nature'], 'INTERDITE')
        self.assertEqual(zone['id'], 'coupe_feu')

    def test_zone_appliquee_est_traduisible_par_cal68(self):
        """Le format rendu EST celui de `exclusionZones` (CAL68)."""
        zone = appliquer_modele(self.modele, repere='CF-1',
                                sommets=[[0, 0], [10, 0], [10, 1.2],
                                         [0, 1.2]])
        traduite = zones_moteur_depuis_layout({'exclusionZones': [zone]})
        self.assertEqual(len(traduite), 1)
        self.assertEqual(traduite[0]['repere'], 'CF-1')
        self.assertEqual(traduite[0]['nature'], 'INTERDITE')

    def test_polygone_porte_deja_son_contour(self):
        modele = normaliser_section_zones_types(
            {'servitude': POLYGONE})['servitude']
        zone = appliquer_modele(modele, cle='servitude')
        self.assertEqual(zone['vertices'],
                         [[0.0, 0.0], [3.0, 0.0], [3.0, 2.0], [0.0, 2.0]])
        self.assertEqual(zone['setbackM'], 0.5)

    def test_bande_sans_contour_reel_refusee(self):
        with self.assertRaises(ReglageInvalide) as capture:
            appliquer_modele(self.modele, cle='coupe_feu')
        self.assertEqual(capture.exception.champ, 'sommets')

    def test_gabarit_sans_source_ne_s_applique_pas(self):
        with self.assertRaises(ReglageInvalide) as capture:
            appliquer_modele(dict(self.modele, source=''), cle='coupe_feu',
                             sommets=[[0, 0], [1, 0], [1, 1]])
        self.assertEqual(capture.exception.champ, 'source')

    def test_zone_sans_source_ne_cite_rien(self):
        """Pas de citation inventée — une chaîne vide, et la planche se tait."""
        self.assertEqual(source_de_zone({'id': 'X'}), '')
        self.assertEqual(source_de_zone(None), '')


class EnregistrementTest(TestCase):
    """Bout en bout : la section vit dans les réglages société (CAL45)."""

    def setUp(self):
        self.company = Company.objects.create(nom='Zones Co',
                                              slug='zones-co-74')
        self.autre = Company.objects.create(nom='Voisine Zones',
                                            slug='voisine-zones-74')

    def test_aucun_nouveau_modele(self):
        """CAL45 : une base, sept extensions — `zones_types` en est une."""
        self.assertIn(SECTION, ParametresCalepinage.SECTIONS)

    def test_enregistrement_et_relecture(self):
        rendu = enregistrer_parametres(self.company,
                                       {SECTION: {'coupe_feu': BANDE}})
        self.assertEqual(rendu[SECTION]['coupe_feu']['source'], SOURCE)
        self.assertEqual(
            parametres_de_societe(self.company)[SECTION]['coupe_feu']
            ['largeur_m'], 1.2)

    def test_sans_source_rien_n_est_ecrit(self):
        sans_source = dict(BANDE)
        sans_source.pop('source')
        with self.assertRaises(ReglageInvalide) as capture:
            enregistrer_parametres(self.company,
                                   {SECTION: {'coupe_feu': sans_source}})
        self.assertEqual(capture.exception.champ,
                         'zones_types.coupe_feu.source')
        self.assertEqual(
            ParametresCalepinage.objects.filter(company=self.company).count(),
            0)

    def test_societe_sans_gabarit_inchangee(self):
        self.assertEqual(parametres_de_societe(self.company)[SECTION], {})

    def test_isolation_societe(self):
        enregistrer_parametres(self.company, {SECTION: {'coupe_feu': BANDE}})
        self.assertEqual(parametres_de_societe(self.autre)[SECTION], {})
