"""CALX259 — enregistrer une courbe IMPORTÉE comme profil société, avec sa
provenance de fichier (``services/profils_types.py::profil_depuis_import``).

``apercu_courbe_csv`` (``services/consommation.py``) sait déjà lire un CSV
et le ramener à l'heure, mais ne rend qu'un APERÇU : rien ne l'enregistrait.
Ce fichier tient deux paquets de preuves, comme sa tâche sœur CALX258
(``test_calx258_profils_segments.py``) :

PARTIE PURE (sans base — ``MoyenneParHeureTest``, ``CourbeDeBaseTest``,
``RefusSansBaseTest`` ci-dessous — EXÉCUTÉE localement) :
* les refus qui ne touchent JAMAIS la base (société absente, clé vide,
  provenance vide — ``ProfilInvalide.champ == 'provenance'`` — courbe
  importée vide, illisible ou entièrement nulle) ;
* ``_moyenne_par_heure`` : une série horaire quelconque (pas besoin d'un
  nombre entier de jours) se ramène à 24 moyennes, une par heure du jour ;
* ``_courbe_de_base`` : la saison ``annuel`` sert telle quelle si elle
  existe, sinon la moyenne des courbes disponibles — jamais un chiffre
  inventé.

PARTIE BASE (``DbImportPleinAnneeTest``, ``DbImportPartielTest`` ci-dessous —
ÉCRITE, NON EXÉCUTÉE localement, « CI validera » : elle crée des
``ProfilTypeConsommation`` et interroge l'ORM) :
* un CSV de 8 760 points (année pleine) s'enregistre, ``provenance``
  contenant le nom du fichier et « 8760 » ;
* le même import rejoué (même clé) ne crée qu'UN profil ;
* un CSV de 4 380 points (moitié d'année) se complète par le profil déjà
  saisi par la société pour le même segment, ``provenance`` portant
  « 50 % des heures complétées » et la clé de ce profil ;
* sans profil société pour compléter, l'import est refusé en le disant.

Run (base) :
    python manage.py test apps.calepinage.tests.test_calx259_import_profil -v2
"""
from __future__ import annotations

import unittest

from django.test import TestCase

from apps.calepinage.models import ProfilTypeConsommation
from apps.calepinage.services.profils_types import (
    HEURES_ANNEE_PLEINE, ProfilInvalide, _courbe_de_base, _moyenne_par_heure,
    profil_depuis_import,
)
from authentication.models import Company


#: Un « aperçu » minimal, comme le rendrait ``apercu_courbe_csv`` — une
#: série HORAIRE, sans autre métadonnée.
def apercu(valeurs, **kwargs):
    donnees = {'valeurs': list(valeurs)}
    donnees.update(kwargs)
    return donnees


#: Un placeholder truthy pour les tests de refus qui n'atteignent JAMAIS la
#: base (le paramètre ``company`` n'est comparé qu'à ``None`` avant ces
#: refus) — jamais une vraie ``Company``, qui exigerait la base.
SOCIETE_FACTICE = object()


class MoyenneParHeureTest(unittest.TestCase):
    """``_moyenne_par_heure`` — pure, sans base."""

    def test_une_annee_complete_rend_la_moyenne_de_chaque_heure(self):
        # 365 jours, chaque jour = [0, 1, …, 23] : la moyenne de l'heure h
        # est h, exactement (aucune dispersion entre les jours).
        annee = [float(h) for _ in range(365) for h in range(24)]
        moyenne = _moyenne_par_heure(annee)
        self.assertEqual(moyenne, [float(h) for h in range(24)])

    def test_une_serie_partielle_ne_couvre_que_ses_propres_heures(self):
        # 30 heures = 1 jour complet + 6 heures du lendemain (0..5) : ces
        # six heures-là ont deux valeurs, les 18 autres n'en ont qu'une.
        serie = [1.0] * 24 + [3.0] * 6
        moyenne = _moyenne_par_heure(serie)
        self.assertEqual(moyenne[0], 2.0)  # (1.0 + 3.0) / 2
        self.assertEqual(moyenne[23], 1.0)  # une seule valeur relevée

    def test_une_serie_vide_ne_leve_pas(self):
        self.assertEqual(_moyenne_par_heure([]), [0.0] * 24)


class CourbeDeBaseTest(unittest.TestCase):
    """``_courbe_de_base`` — la base de complétion, jamais inventée."""

    def test_la_saison_annuelle_sert_telle_quelle(self):
        annuel = [1 / 24.0] * 24
        profil = {'courbes': {'annuel': annuel,
                              'ete': [1 / 12.0] * 12 + [0.0] * 12}}
        self.assertEqual(_courbe_de_base(profil), annuel)

    def test_sans_saison_annuelle_la_moyenne_des_courbes_disponibles_sert(self):
        hiver = [0.0] * 12 + [1 / 12.0] * 12
        ete = [1 / 12.0] * 12 + [0.0] * 12
        profil = {'courbes': {'hiver': hiver, 'ete': ete}}
        attendue = [(h + e) / 2 for h, e in zip(hiver, ete)]
        self.assertEqual(_courbe_de_base(profil), attendue)

    def test_une_courbe_segmentee_calx258_entre_dans_la_moyenne(self):
        ouvre = [1.0 / 24] * 24
        weekend = [1.0 / 12] * 12 + [0.0] * 12
        profil = {'courbes': {'ete': {'ouvre': ouvre, 'weekend': weekend}}}
        attendue = [(o + w) / 2 for o, w in zip(ouvre, weekend)]
        self.assertEqual(_courbe_de_base(profil), attendue)

    def test_un_profil_sans_aucune_courbe_exploitable_rend_none(self):
        self.assertIsNone(_courbe_de_base({'courbes': {}}))
        self.assertIsNone(_courbe_de_base(None))


class RefusSansBaseTest(unittest.TestCase):
    """Les refus de ``profil_depuis_import`` qui n'atteignent JAMAIS la
    base — ils sont tous posés AVANT la moindre requête ORM."""

    def annee_pleine(self):
        return [1.0] * HEURES_ANNEE_PLEINE

    def test_aucune_societe_est_refuse_en_le_nommant(self):
        with self.assertRaises(ProfilInvalide) as refus:
            profil_depuis_import(
                None, apercu(self.annee_pleine()), cle='pompage-forage-1',
                libelle='Forage 1', famille='pompage', origine='export.csv')
        self.assertEqual(refus.exception.champ, 'company')

    def test_une_cle_vide_est_refusee_en_la_nommant(self):
        with self.assertRaises(ProfilInvalide) as refus:
            profil_depuis_import(
                SOCIETE_FACTICE, apercu(self.annee_pleine()), cle='   ',
                libelle='Forage 1', famille='pompage', origine='export.csv')
        self.assertEqual(refus.exception.champ, 'cle')

    def test_une_origine_vide_est_refusee_en_nommant_provenance(self):
        """Done CALX259 : ``ProfilInvalide.champ == 'provenance'``."""
        for vide in ('', '   ', None):
            with self.subTest(origine=repr(vide)):
                with self.assertRaises(ProfilInvalide) as refus:
                    profil_depuis_import(
                        SOCIETE_FACTICE, apercu(self.annee_pleine()),
                        cle='pompage-forage-1', libelle='Forage 1',
                        famille='pompage', origine=vide)
                self.assertEqual(refus.exception.champ, 'provenance')

    def test_un_apercu_sans_valeurs_est_refuse(self):
        with self.assertRaises(ProfilInvalide) as refus:
            profil_depuis_import(
                SOCIETE_FACTICE, apercu([]), cle='pompage-forage-1',
                libelle='Forage 1', famille='pompage', origine='export.csv')
        self.assertEqual(refus.exception.champ, 'apercu')

    def test_une_valeur_illisible_est_refusee(self):
        with self.assertRaises(ProfilInvalide) as refus:
            profil_depuis_import(
                SOCIETE_FACTICE, apercu([1.0, 'illisible', 2.0]),
                cle='pompage-forage-1', libelle='Forage 1',
                famille='pompage', origine='export.csv')
        self.assertEqual(refus.exception.champ, 'apercu')

    def test_une_courbe_entierement_nulle_est_refusee(self):
        with self.assertRaises(ProfilInvalide) as refus:
            profil_depuis_import(
                SOCIETE_FACTICE, apercu([0.0] * HEURES_ANNEE_PLEINE),
                cle='pompage-forage-1', libelle='Forage 1',
                famille='pompage', origine='export.csv')
        self.assertEqual(refus.exception.champ, 'courbe')


#: CI VALIDERA — les classes ci-dessous exigent l'ORM/la base (création de
#: ``Company``/``ProfilTypeConsommation``, requêtes) : ÉCRITES, NON EXÉCUTÉES
#: localement (patron de lane : pas de docker/test-DB/``manage.py test`` ici).
class DbImportPleinAnneeTest(TestCase):
    """Un CSV de 8 760 points (année pleine) — Done CALX259."""

    def setUp(self):
        self.company = Company.objects.create(nom='Pompage Co',
                                              slug='pompage-co-259')

    def test_import_publie_le_fichier_et_le_nombre_de_points(self):
        valeurs = [1.0 + (h % 24) for h in range(HEURES_ANNEE_PLEINE)]
        profil = profil_depuis_import(
            self.company,
            apercu(valeurs, points_lus=HEURES_ANNEE_PLEINE, pas_minutes=60),
            cle='pompage-forage-1', libelle='Forage 1', famille='pompage',
            origine='export_onee_2025.csv')
        self.assertIn('export_onee_2025.csv', profil['provenance'])
        self.assertIn('8760', profil['provenance'])
        # Année pleine : rien à compléter, donc aucune mention de complétion.
        self.assertNotIn('complétées', profil['provenance'])

    def test_le_meme_import_rejoue_ne_cree_qu_un_profil(self):
        valeurs = [1.0 + (h % 24) for h in range(HEURES_ANNEE_PLEINE)]
        for _ in range(2):
            profil_depuis_import(
                self.company, apercu(valeurs), cle='pompage-forage-1',
                libelle='Forage 1', famille='pompage',
                origine='export_onee_2025.csv')
        self.assertEqual(
            ProfilTypeConsommation.objects
            .filter(company=self.company, cle='pompage-forage-1').count(),
            1)


class DbImportPartielTest(TestCase):
    """Un CSV de 4 380 points (demi-année) — complété par le profil société
    déjà saisi pour le même segment (jamais par un autre foyer)."""

    def setUp(self):
        self.company = Company.objects.create(nom='Pompage Co 2',
                                              slug='pompage-co-259b')
        # Le profil DÉJÀ SAISI par la société pour le même segment
        # (« pompage ») — c'est LUI qui complète, jamais un repli.
        ProfilTypeConsommation.objects.create(
            company=self.company, cle='pompage-existant',
            libelle='Pompage — existant', famille='pompage',
            courbe={'annuel': [1.0] * 24},
            provenance='Comptage du forage voisin, 2024.')

    def test_import_partiel_se_complete_et_le_publie(self):
        valeurs = [2.0] * (HEURES_ANNEE_PLEINE // 2)  # 4 380 points.
        profil = profil_depuis_import(
            self.company, apercu(valeurs), cle='pompage-forage-2',
            libelle='Forage 2', famille='pompage',
            origine='export_partiel.csv')
        self.assertIn('50 % des heures complétées', profil['provenance'])
        self.assertIn('pompage-existant', profil['provenance'])

    def test_sans_profil_societe_l_import_partiel_est_refuse(self):
        autre = Company.objects.create(nom='Sans profil pompage',
                                       slug='sans-profil-pompage-259')
        valeurs = [2.0] * (HEURES_ANNEE_PLEINE // 2)
        with self.assertRaises(ProfilInvalide) as refus:
            profil_depuis_import(
                autre, apercu(valeurs), cle='pompage-forage-3',
                libelle='Forage 3', famille='pompage',
                origine='export_partiel.csv')
        # « nommant le manque » : le segment sans profil société est cité.
        self.assertIn('pompage', refus.exception.motif)
        self.assertIn('Aucun', refus.exception.motif)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
