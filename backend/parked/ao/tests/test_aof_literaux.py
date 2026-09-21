"""AOF147 — détecteur de littéraux orphelins + MESURE de ses faux positifs.

Le corpus ci-dessous rejoue le dossier FRDISI : quinze passages LÉGITIMES
(montants du bordereau, quantités de calepinage, productible, normes, décret,
téléphone, code postal) et les quatre VESTIGES réels de la session —
5 143 680 tapé pour 5 413 680, « batteries 2 800 » contre un bordereau à
2 600, un bordereau frère périmé à 5 219 280, et la référence BOS-G survivante.

**Taux de faux positifs MESURÉ sur ce corpus : 0/19 = 0,00 %** (0 faux négatif).
C'est cette mesure, écrite ici, qui autorise le passage en mode bloquant — et
sans elle ``ConfigurationLiteraux.bloquante`` refuse de se construire. Un
détecteur bruyant est désactivé en trois dossiers ; la fatigue d'alerte tue
aussi les contrôles qui, eux, ne se trompent jamais.

Run :
    python manage.py test apps.ao.tests.test_aof_literaux -v2
"""
from decimal import Decimal

from django.test import SimpleTestCase

from apps.ao.fabrique.literaux import (
    MODE_AVERTISSEMENT, MODE_BLOQUANT, SEUIL_FAUX_POSITIFS,
    ConfigurationLiteraux, LiteralOrphelin, controler, detecter,
    mesurer_faux_positifs, valeurs_du_contexte,
)

#: Taux mesuré sur le corpus ci-dessous, publié AVANT toute activation.
TAUX_MESURE = Decimal('0.00')
CORPUS_MESURE = '19 passages du dossier FRDISI (15 légitimes, 4 vestiges)'


def contexte():
    return {
        'montants': {'total_ht': Decimal('4166600'),
                     'total_ttc': Decimal('4999920'),
                     'tva': Decimal('833320')},
        'sections': [{'code': 'A', 'total_ht': Decimal('1034100')},
                     {'code': 'B', 'total_ht': Decimal('744200')},
                     {'code': 'C', 'total_ht': Decimal('1511300')},
                     {'code': 'COM', 'total_ht': Decimal('877000')}],
        'equipements': [
            {'designation': 'Module JKM-625 625 Wc', 'reference': 'JKM-625',
             'prix_unitaire': Decimal('2950')},
            {'designation': 'Batterie BOS-B Pro-A3',
             'reference': 'BOS-B Pro-A3', 'prix_unitaire': Decimal('2600')},
            {'designation': 'Onduleur SUN-110K', 'reference': 'SUN-110K',
             'prix_unitaire': Decimal('78000')},
        ],
        'batiments': [{'code': 'A', 'modules': 152, 'kwc': Decimal('95.0')},
                      {'code': 'B', 'modules': 120, 'kwc': Decimal('75.0')},
                      {'code': 'C', 'modules': 288, 'kwc': Decimal('180.0')}],
        'site': {'productible': Decimal('1650'), 'ville': 'Fès'},
        'divers': {'etudes_execution': Decimal('262000'),
                   'ems': Decimal('200000'),
                   'genie_civil': Decimal('120000'),
                   'essais': Decimal('70000'),
                   'station_meteo': Decimal('50000'),
                   'afficheur': Decimal('39500'), 'tgpv': Decimal('15000'),
                   'coffret_dc': Decimal('4500'),
                   'coffret_ac': Decimal('8500')},
    }


CORPUS = [
    # (emplacement, texte, contient réellement un vestige ?)
    ('mémoire §1', "Le montant total de l'offre s'établit à 4 999 920 DH TTC.",
     False),
    ('mémoire §2', 'Batterie BOS-B Pro-A3, prix unitaire 2 600 DH HT/kWh.',
     False),
    ('mémoire §3', 'Le bâtiment C reçoit 288 modules pour 180,0 kWc.', False),
    ('mémoire §4', 'Productible retenu : 1 650 kWh/kWc/an sur le site de Fès.',
     False),
    ('mémoire §5', 'Conforme à la norme NF EN 62109 et à la CEI 61730.',
     False),
    ('mémoire §6', 'Application du décret n° 2-12-349 relatif aux marchés '
                   'publics.', False),
    ('mémoire §7', 'Tél : 0522000000 — Casablanca, code postal 20250.', False),
    ('mémoire §8', "Les études d'exécution sont chiffrées 262 000 DH HT.",
     False),
    ('mémoire §9', "Onduleur SUN-110K, 78 000 DH l'unité.", False),
    ('mémoire §10', 'Modules JKM-625 à 2 950 DH pièce.', False),
    ('mémoire §11', 'Sous-total bâtiment A : 1 034 100 DH HT.', False),
    ('mémoire §12', 'La TVA de 20 % représente 833 320 DH.', False),
    ('mémoire §13', 'Dossier remis le 15 septembre 2026 en 2 exemplaires.',
     False),
    ('mémoire §14', 'EMS supervisé : 200 000 DH HT.', False),
    ('mémoire §15', 'Génie civil 120 000 DH, essais et DOE 70 000 DH.', False),
    ('vestige 1', "Le montant total s'établit à 5 143 680 DH TTC.", True),
    ('vestige 2', '(batteries 2 800 DH HT/kWh, pose comprise)', True),
    ('vestige 3', 'Bordereau antérieur : 5 219 280 DH TTC.', True),
    ('vestige 4', 'Batterie BOS-G 16,08 kWh installée.', True),
]


def cas_annotes():
    return [{'emplacement': e, 'texte': t, 'attendu': a} for e, t, a in CORPUS]


class DefautsReelsTest(SimpleTestCase):
    def test_le_defaut_2800_contre_2600_est_detecte(self):
        orphelins = detecter(
            [{'emplacement': 'Word ACCORDIA — justification',
              'texte': "Le total s'établit à 4 999 920 DH TTC "
                       '(batteries 2 800 DH HT/kWh, pose comprise).'}],
            contexte())
        valeurs = [o['valeur'] for o in orphelins]
        self.assertEqual(len(orphelins), 1, orphelins)
        self.assertIn('800', valeurs[0])
        # Le montant cascadé, lui, est expliqué par le contexte : pas d'alerte.
        self.assertFalse(any('999' in v for v in valeurs))

    def test_les_trois_autres_vestiges_sont_detectes(self):
        for emplacement, texte, attendu in CORPUS:
            trouve = bool(detecter(
                [{'emplacement': emplacement, 'texte': texte}], contexte()))
            self.assertEqual(trouve, attendu,
                             '{} → {}'.format(emplacement, texte))

    def test_la_reference_survivante_bos_g_est_detectee(self):
        orphelins = detecter(
            [{'emplacement': 'mémoire §7', 'texte': 'Packs BOS-G maintenus.'}],
            contexte())
        self.assertEqual([o['nature'] for o in orphelins], ['reference'])
        self.assertEqual(orphelins[0]['valeur'], 'BOS-G')


class MesureDesFauxPositifsTest(SimpleTestCase):
    """La mesure EST le livrable : sans elle, pas d'activation bloquante."""

    def test_le_taux_mesure_est_celui_publie_dans_ce_fichier(self):
        mesure = mesurer_faux_positifs(cas_annotes(), contexte())
        self.assertEqual(mesure['total'], 19)
        self.assertEqual(mesure['faux_positifs'], 0)
        self.assertEqual(mesure['faux_negatifs'], 0)
        self.assertEqual(mesure['taux'], TAUX_MESURE)
        self.assertLessEqual(mesure['taux'], SEUIL_FAUX_POSITIFS)

    def test_les_exceptions_ne_produisent_aucun_faux_positif(self):
        """Millésimes, normes, décret, téléphone, code postal, page."""
        for texte in ('Conforme à la norme NF EN 62109.',
                      'Décret n° 2-12-349 du 20 mars 2013.',
                      'Tél : 0522000000.',
                      'Code postal 20250.',
                      'Voir page 1240 du CPS.',
                      'ICE 001234567000012.',
                      'Exercice 2026 et exercice 1998.'):
            self.assertEqual(
                detecter([{'emplacement': 'x', 'texte': texte}], contexte()),
                [], texte)


class ModeParDefautTest(SimpleTestCase):
    def test_le_detecteur_demarre_en_avertissement(self):
        configuration = ConfigurationLiteraux()
        self.assertEqual(configuration.mode, MODE_AVERTISSEMENT)
        self.assertFalse(configuration.bloque)
        orphelins = controler(
            [{'emplacement': 'x', 'texte': 'batteries 2 800 DH'}], contexte())
        self.assertTrue(orphelins)  # signalé…
        # …mais rien n'a été levé : le rendu peut sortir.

    def test_en_mode_bloquant_le_rendu_est_refuse(self):
        configuration = ConfigurationLiteraux.bloquante(
            taux_faux_positifs=TAUX_MESURE,
            motif='mesure {} : 0 faux positif'.format(CORPUS_MESURE),
            auteur='fondateur', date='2026-08-01')
        self.assertEqual(configuration.mode, MODE_BLOQUANT)
        with self.assertRaises(LiteralOrphelin) as capture:
            controler([{'emplacement': 'annexe',
                        'texte': 'batteries 2 800 DH'}],
                      contexte(), configuration=configuration)
        self.assertIn('annexe', str(capture.exception))
        self.assertIn('800', str(capture.exception))


class ActivationTraceeTest(SimpleTestCase):
    """Le passage en bloquant est une décision, pas un réglage par défaut."""

    def test_sans_taux_mesure_l_activation_est_refusee(self):
        with self.assertRaises(ValueError) as capture:
            ConfigurationLiteraux.bloquante(
                taux_faux_positifs=None, motif='parce que', auteur='x',
                date='2026-08-01')
        self.assertIn('MESURÉ', str(capture.exception))

    def test_au_dessus_du_seuil_l_activation_est_refusee(self):
        with self.assertRaises(ValueError) as capture:
            ConfigurationLiteraux.bloquante(
                taux_faux_positifs=Decimal('0.30'), motif='m', auteur='x',
                date='2026-08-01')
        self.assertIn('bruyant', str(capture.exception))

    def test_sans_motif_auteur_date_l_activation_est_refusee(self):
        for manquant in ('motif', 'auteur', 'date'):
            arguments = {'motif': 'm', 'auteur': 'x', 'date': '2026-08-01'}
            arguments[manquant] = ''
            with self.assertRaises(ValueError, msg=manquant):
                ConfigurationLiteraux.bloquante(
                    taux_faux_positifs=TAUX_MESURE, **arguments)

    def test_un_mode_inconnu_est_refuse(self):
        with self.assertRaises(ValueError):
            ConfigurationLiteraux('silencieux')


class ContexteAplatiTest(SimpleTestCase):
    def test_les_nombres_sont_collectes_a_toute_profondeur(self):
        nombres, references = valeurs_du_contexte(contexte())
        self.assertIn(Decimal('4999920'), nombres)
        self.assertIn(Decimal('1511300'), nombres)
        self.assertIn(Decimal('2600'), nombres)
        self.assertTrue(any('jkm 625' in r for r in references))

    def test_les_booleens_ne_deviennent_pas_des_nombres(self):
        nombres, _ = valeurs_du_contexte({'actif': True, 'archive': False})
        self.assertNotIn(Decimal('1'), nombres)
        self.assertNotIn(Decimal('0'), nombres)
