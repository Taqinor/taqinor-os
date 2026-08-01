# -*- coding: utf-8 -*-
"""Tests AOF110 — le formateur français UNIQUE des trois canaux du dossier.

Trois preuves, dans cet ordre d'importance :

1. **Égalité tri-canal** — le MÊME montant rendu pour HTML/PDF, XLSX et
   matplotlib donne la MÊME chaîne, y compris quand les canaux ont des
   couvertures de police divergentes (c'est là que trois formateurs
   improvisés produiraient trois rendus).
2. **Couverture de police WeasyPrint ET matplotlib** — le glyphe fin manquant
   est le piège classique : on prouve que la sonde lit vraiment la table de
   caractères (un point de code présent → ``True``, un point de code non
   assigné → ``False``), puis que chaque canal répond sans exploser.
3. **Chaînes dorées** — montants, unités (DH, kWc, kWh, m³/h, %) et dates
   jj/mm/aaaa, avec l'espace de groupement FORCÉ à l'appel : un test doré ne
   doit jamais dépendre des polices installées sur la machine qui l'exécute.

Aucune base de données, aucun accès réseau. Les tests qui font résoudre de
vraies polices (matplotlib construit son index au premier appel) sont
étiquetés ``@tag('slow')`` pour ne pas alourdir le gate par-merge.

Run :
    docker compose exec django_core python manage.py test \
        core.tests.test_formats_fr -v 2
"""
import datetime
from decimal import Decimal
from unittest import mock

from django.test import SimpleTestCase, tag

from core import formats_fr
from core.formats_fr import (
    CANAL_HTML,
    CANAL_MATPLOTLIB,
    CANAL_XLSX,
    CANAUX,
    CODEPOINT_ESPACE_FINE,
    ESPACE_FINE,
    ESPACE_INSECABLE,
    FORMAT_TEXTE_XLSX,
    couverture_fine,
    definir_espace_groupement,
    diagnostic_polices,
    espace_groupement,
    formater_date,
    formater_montant,
    formater_nombre,
    formater_pourcentage,
    formater_quantite,
    normaliser_unite,
    police_couvre_codepoint,
    polices_du_canal,
    reinitialiser_polices,
)

#: Un point de code NON ASSIGNÉ : aucune police ne peut le porter.
CODEPOINT_ABSENT = 0x0EFFFF


class BaseFormatsFrTests(SimpleTestCase):
    """Isole chaque test des caches de sonde et de tout forçage résiduel."""

    def setUp(self):
        reinitialiser_polices()
        definir_espace_groupement(None)
        self.addCleanup(definir_espace_groupement, None)
        self.addCleanup(reinitialiser_polices)


class ConstantesTypographiquesTests(BaseFormatsFrTests):
    """Les deux espaces sont INVISIBLES dans le source : on verrouille leur
    point de code, sinon un éditeur « nettoyeur d'espaces » les remplace par
    une espace ordinaire et tous les montants deviennent sécables."""

    def test_points_de_code(self):
        self.assertEqual(ord(ESPACE_FINE), 0x202F)
        self.assertEqual(ord(ESPACE_INSECABLE), 0x00A0)
        self.assertEqual(CODEPOINT_ESPACE_FINE, 0x202F)

    def test_les_deux_espaces_sont_distinctes(self):
        self.assertNotEqual(ESPACE_FINE, ESPACE_INSECABLE)
        self.assertNotEqual(ESPACE_FINE, ' ')
        self.assertNotEqual(ESPACE_INSECABLE, ' ')

    def test_format_texte_xlsx(self):
        # Le code « Texte » d'Excel : la chaîne déjà formatée n'est pas
        # re-parsée (et donc pas re-formatée selon la locale du lecteur).
        self.assertEqual(FORMAT_TEXTE_XLSX, '@')


class EgaliteTriCanalTests(BaseFormatsFrTests):
    """LE test de la tâche : un montant, trois canaux, une seule chaîne."""

    MONTANTS = (
        Decimal('4999920'), Decimal('4166600.00'), Decimal('5413680.55'),
        Decimal('0'), Decimal('-1234.5'), Decimal('999.994'), 80, 1000000,
    )

    def _rendus(self, valeur):
        return [formater_montant(valeur, canal=canal) for canal in CANAUX]

    def test_un_montant_rendu_dans_les_trois_canaux_donne_la_meme_chaine(self):
        for valeur in self.MONTANTS:
            rendus = self._rendus(valeur)
            self.assertEqual(
                len(set(rendus)), 1,
                f'{valeur} rendu différemment selon le canal : {rendus}')

    def test_egalite_meme_quand_les_canaux_divergent_sur_la_police(self):
        # Le cas RÉEL : la police du PDF porte U+202F, celle du cartouche non.
        # Un formateur par canal produirait deux chaînes ; celui-ci résout
        # l'espace pour TOUT le dossier et reste donc identique partout.
        couvertures = {CANAL_HTML: True, CANAL_XLSX: None,
                       CANAL_MATPLOTLIB: False}
        with mock.patch.object(formats_fr, 'couverture_fine',
                               side_effect=lambda canal, familles=None:
                               couvertures[canal]):
            reinitialiser_polices()
            rendus = self._rendus(Decimal('4999920'))
            self.assertEqual(len(set(rendus)), 1, rendus)
            # …et c'est le plus petit dénominateur commun qui gagne.
            self.assertEqual(
                rendus[0],
                f'4{ESPACE_INSECABLE}999{ESPACE_INSECABLE}920,00'
                f'{ESPACE_INSECABLE}DH')

    def test_egalite_tri_canal_sur_les_quantites_et_pourcentages(self):
        for canal in CANAUX:
            self.assertEqual(formater_quantite(15000, 'kWh', canal=canal),
                             formater_quantite(15000, 'kWh'))
            self.assertEqual(formater_pourcentage(12.45, canal=canal),
                             formater_pourcentage(12.45))
            self.assertEqual(formater_date(datetime.date(2026, 8, 1),
                                           canal=canal),
                             '01/08/2026')

    def test_canal_inconnu_refuse(self):
        for appel in (lambda: formater_nombre(1, canal='pdf'),
                      lambda: formater_date(None, canal='pdf'),
                      lambda: couverture_fine('pdf'),
                      lambda: polices_du_canal('pdf')):
            with self.assertRaises(ValueError):
                appel()


class ResolutionEspaceGroupementTests(BaseFormatsFrTests):
    """La règle de repli : seul un glyphe PROUVÉ manquant fait basculer."""

    def _avec_couvertures(self, **par_canal):
        return mock.patch.object(
            formats_fr, 'couverture_fine',
            side_effect=lambda canal, familles=None: par_canal.get(canal))

    def test_fine_quand_tous_les_canaux_la_portent(self):
        with self._avec_couvertures(html=True, xlsx=True, matplotlib=True):
            reinitialiser_polices()
            self.assertEqual(espace_groupement(), ESPACE_FINE)

    def test_fine_quand_la_couverture_est_inconnue(self):
        # « Inconnu » n'est pas « absent » : sans preuve d'absence, on garde la
        # fine (la typographie correcte est le comportement par défaut).
        with self._avec_couvertures(html=None, xlsx=None, matplotlib=None):
            reinitialiser_polices()
            self.assertEqual(espace_groupement(), ESPACE_FINE)

    def test_repli_des_qu_un_seul_canal_est_prouve_depourvu(self):
        for absent in CANAUX:
            couvertures = {canal: True for canal in CANAUX}
            couvertures[absent] = False
            with self._avec_couvertures(**couvertures):
                reinitialiser_polices()
                self.assertEqual(
                    espace_groupement(), ESPACE_INSECABLE,
                    f'{absent} sans le glyphe fin doit faire basculer TOUT '
                    f'le dossier sur U+00A0')

    def test_forcage_explicite(self):
        definir_espace_groupement(ESPACE_INSECABLE)
        self.assertEqual(espace_groupement(), ESPACE_INSECABLE)
        self.assertEqual(formater_montant(1000),
                         f'1{ESPACE_INSECABLE}000,00{ESPACE_INSECABLE}DH')
        definir_espace_groupement(ESPACE_FINE)
        self.assertEqual(formater_montant(1000),
                         f'1{ESPACE_FINE}000,00{ESPACE_INSECABLE}DH')

    def test_forcage_invalide_refuse(self):
        with self.assertRaises(ValueError):
            definir_espace_groupement(' ')

    def test_espace_toujours_insecable(self):
        # Quel que soit le verdict, le montant ne doit JAMAIS pouvoir se
        # couper en fin de ligne : les deux valeurs possibles sont insécables.
        self.assertIn(espace_groupement(), (ESPACE_FINE, ESPACE_INSECABLE))
        self.assertNotIn(' ', formater_montant(1234567))


class SondeCouverturePoliceTests(BaseFormatsFrTests):
    """La sonde lit-elle VRAIMENT la table de caractères ?"""

    def _une_police(self):
        for canal in (CANAL_MATPLOTLIB, CANAL_HTML):
            chemins = polices_du_canal(canal)
            if chemins:
                return chemins[0]
        self.skipTest('aucune police résoluble sur cette machine')

    @tag('slow')
    def test_detecte_un_glyphe_present_et_un_glyphe_absent(self):
        chemin = self._une_police()
        if police_couvre_codepoint(chemin, ord('A')) is None:
            self.skipTest('fontTools indisponible : sonde non exerçable')
        # Le « A » est dans toute police latine…
        self.assertIs(police_couvre_codepoint(chemin, ord('A')), True)
        # …un point de code NON ASSIGNÉ n'y est dans aucune : si la sonde
        # répondait True ici, elle ne lirait pas la cmap.
        self.assertIs(police_couvre_codepoint(chemin, CODEPOINT_ABSENT), False)

    def test_fichier_illisible_repond_inconnu_sans_exploser(self):
        # Une police absente ne doit jamais faire tomber un rendu de dossier.
        self.assertIsNone(
            police_couvre_codepoint('/introuvable/aucune-police.ttf'))
        self.assertIsNone(police_couvre_codepoint(None))

    @tag('slow')
    def test_couverture_des_deux_canaux_de_rendu(self):
        # WeasyPrint (HTML/PDF) ET matplotlib : les deux canaux exigés par la
        # tâche. Le verdict dépend des polices installées (Liberation/Noto en
        # production, DejaVu ailleurs) — on vérifie donc la FORME de la
        # réponse et l'absence d'exception, jamais une valeur d'environnement.
        for canal in (CANAL_HTML, CANAL_MATPLOTLIB):
            verdict = couverture_fine(canal)
            self.assertIn(verdict, (True, False, None),
                          f'{canal} : verdict de couverture invalide')
            for chemin in polices_du_canal(canal):
                self.assertIsInstance(chemin, str)

    def test_canal_xlsx_est_une_couverture_inconnue_par_defaut(self):
        # La police du tableur appartient au LECTEUR : on ne peut pas la
        # sonder, donc on ne prétend pas qu'elle manque.
        self.assertEqual(polices_du_canal(CANAL_XLSX), [])
        self.assertIsNone(couverture_fine(CANAL_XLSX))

    @tag('slow')
    def test_diagnostic_polices(self):
        rapport = diagnostic_polices()
        self.assertEqual(set(rapport), set(CANAUX))
        for canal, detail in rapport.items():
            self.assertIsInstance(detail['polices'], list)
            self.assertIn(detail['couverture_fine'], (True, False, None))

    def test_les_sondes_sont_mises_en_cache(self):
        with mock.patch.object(formats_fr, '_polices_matplotlib',
                               return_value=[]) as sonde:
            polices_du_canal(CANAL_MATPLOTLIB)
            polices_du_canal(CANAL_MATPLOTLIB)
            self.assertEqual(sonde.call_count, 1)


class ChainesDoreesTests(BaseFormatsFrTests):
    """Chaînes attendues, espace de groupement FORCÉ (test indépendant des
    polices de la machine d'exécution)."""

    def rendu(self, *args, **kwargs):
        kwargs.setdefault('espace', ESPACE_FINE)
        return formater_montant(*args, **kwargs)

    def test_montants_du_dossier(self):
        self.assertEqual(
            self.rendu(4999920),
            f'4{ESPACE_FINE}999{ESPACE_FINE}920,00{ESPACE_INSECABLE}DH')
        self.assertEqual(
            self.rendu(Decimal('4166600')),
            f'4{ESPACE_FINE}166{ESPACE_FINE}600,00{ESPACE_INSECABLE}DH')
        self.assertEqual(self.rendu(Decimal('80')),
                         f'80,00{ESPACE_INSECABLE}DH')
        self.assertEqual(self.rendu(Decimal('0')),
                         f'0,00{ESPACE_INSECABLE}DH')

    def test_groupement_par_trois_a_partir_de_mille(self):
        for valeur, attendu in (
            (1, '1,00'), (999, '999,00'),
            (1000, f'1{ESPACE_FINE}000,00'),
            (10000, f'10{ESPACE_FINE}000,00'),
            (100000, f'100{ESPACE_FINE}000,00'),
            (1000000, f'1{ESPACE_FINE}000{ESPACE_FINE}000,00'),
            (1234567890, f'1{ESPACE_FINE}234{ESPACE_FINE}567'
                         f'{ESPACE_FINE}890,00'),
        ):
            self.assertEqual(
                formater_nombre(valeur, espace=ESPACE_FINE), attendu)

    def test_virgule_decimale_et_zero_significatif(self):
        self.assertEqual(formater_nombre(Decimal('12.5'), espace=ESPACE_FINE),
                         '12,50')
        self.assertEqual(formater_nombre(12.5, decimales=0), '13')
        self.assertEqual(formater_nombre(Decimal('0.5'), decimales=0), '1')
        self.assertNotIn('.', formater_nombre(Decimal('1234.56'),
                                              espace=ESPACE_FINE))

    def test_arrondi_moitie_vers_le_haut(self):
        self.assertEqual(formater_nombre(Decimal('2.675'), decimales=2), '2,68')
        self.assertEqual(formater_nombre(Decimal('999.994'), decimales=2,
                                         espace=ESPACE_FINE), '999,99')
        self.assertEqual(formater_nombre(Decimal('999.995'), decimales=2,
                                         espace=ESPACE_FINE), '1' +
                         ESPACE_FINE + '000,00')

    def test_meme_arrondi_que_la_comptabilite(self):
        # Non-divergence avec la politique monétaire du socle : un rendu qui
        # arrondit autrement que la compta qui l'alimente est un écart
        # d'un centime sur un document contractuel.
        from core.money import quantize_mad
        for valeur in ('2.675', '0.005', '1234.565', '-2.675', '999.994'):
            attendu = formater_nombre(quantize_mad(Decimal(valeur)),
                                      decimales=2, espace=ESPACE_FINE)
            self.assertEqual(
                formater_nombre(Decimal(valeur), decimales=2,
                                espace=ESPACE_FINE), attendu, valeur)

    def test_negatifs(self):
        self.assertEqual(
            formater_nombre(Decimal('-1234.567'), espace=ESPACE_FINE),
            f'-1{ESPACE_FINE}234,57')
        # Pas de « -0,00 » : un arrondi qui annule la valeur annule le signe.
        self.assertEqual(
            formater_nombre(Decimal('-0.001'), espace=ESPACE_FINE), '0,00')

    def test_sans_groupement(self):
        # Une année ou un numéro ne se groupe pas.
        self.assertEqual(formater_nombre(2026, decimales=0, grouper=False),
                         '2026')

    def test_accepte_int_float_decimal_et_chaine(self):
        attendu = f'1{ESPACE_FINE}234,50'
        for valeur in (1234.5, Decimal('1234.5'), '1234.50'):
            self.assertEqual(
                formater_nombre(valeur, espace=ESPACE_FINE), attendu)
        self.assertEqual(formater_nombre(1234, espace=ESPACE_FINE),
                         f'1{ESPACE_FINE}234,00')


class UnitesTests(BaseFormatsFrTests):
    """DH, kWc, kWh, m³/h, % — et l'espace insécable qui les précède."""

    def test_les_cinq_unites_de_la_tache(self):
        self.assertEqual(
            formater_montant(4999920, espace=ESPACE_FINE),
            f'4{ESPACE_FINE}999{ESPACE_FINE}920,00{ESPACE_INSECABLE}DH')
        self.assertEqual(formater_quantite(Decimal('12.5'), 'kWc'),
                         f'12,50{ESPACE_INSECABLE}kWc')
        self.assertEqual(
            formater_quantite(15000, 'kWh', espace=ESPACE_FINE),
            f'15{ESPACE_FINE}000{ESPACE_INSECABLE}kWh')
        self.assertEqual(formater_quantite(Decimal('45'), 'm³/h'),
                         f'45,0{ESPACE_INSECABLE}m³/h')
        self.assertEqual(formater_pourcentage(Decimal('12.45')),
                         f'12,5{ESPACE_INSECABLE}%')

    def test_l_espace_avant_l_unite_est_toujours_la_pleine(self):
        # La fine est réservée au groupement : même quand elle est active,
        # l'unité reste collée par une U+00A0 (règle SI/Imprimerie nationale).
        definir_espace_groupement(ESPACE_FINE)
        rendu = formater_montant(1234567)
        self.assertTrue(rendu.endswith(ESPACE_INSECABLE + 'DH'), repr(rendu))
        self.assertNotIn(ESPACE_FINE + 'DH', rendu)

    def test_decimales_par_defaut_par_unite(self):
        self.assertEqual(formater_quantite(7, 'kWh'),
                         f'7{ESPACE_INSECABLE}kWh')                 # 0 déc.
        self.assertEqual(formater_quantite(7, 'kWc'),
                         f'7,00{ESPACE_INSECABLE}kWc')              # 2 déc.
        self.assertEqual(formater_quantite(7, 'm³/h'),
                         f'7,0{ESPACE_INSECABLE}m³/h')              # 1 déc.
        # …surchargeable à l'appel.
        self.assertEqual(formater_quantite(7, 'kWh', decimales=2),
                         f'7,00{ESPACE_INSECABLE}kWh')

    def test_normalisation_des_alias(self):
        self.assertEqual(normaliser_unite('kwc'), 'kWc')
        self.assertEqual(normaliser_unite(' KWH '), 'kWh')
        self.assertEqual(normaliser_unite('m3/h'), 'm³/h')
        self.assertEqual(normaliser_unite('dirhams'), 'DH')
        self.assertEqual(normaliser_unite(None), '')
        # Une unité inconnue passe telle quelle (le formateur ne connaît pas
        # tout le SI et n'a pas à refuser un rendu pour ça).
        self.assertEqual(normaliser_unite('daN'), 'daN')
        self.assertEqual(formater_quantite(3, 'daN'),
                         f'3,00{ESPACE_INSECABLE}daN')

    def test_sans_unite(self):
        self.assertEqual(formater_quantite(3, None), '3,00')
        self.assertEqual(formater_quantite(3, ''), '3,00')

    def test_devise_alternative(self):
        self.assertEqual(formater_montant(1250, devise='MAD'),
                         f'1{espace_groupement()}250,00{ESPACE_INSECABLE}MAD')


class DatesTests(BaseFormatsFrTests):
    """jj/mm/aaaa — jamais l'ISO ni le format américain."""

    def test_objets_date_et_datetime(self):
        self.assertEqual(formater_date(datetime.date(2026, 8, 1)),
                         '01/08/2026')
        self.assertEqual(
            formater_date(datetime.datetime(2026, 12, 31, 23, 59)),
            '31/12/2026')

    def test_chaine_iso(self):
        self.assertEqual(formater_date('2026-08-01'), '01/08/2026')
        self.assertEqual(formater_date('2026-08-01T09:30:00'), '01/08/2026')

    def test_vide(self):
        self.assertEqual(formater_date(None), '')
        self.assertEqual(formater_date(''), '')

    def test_date_illisible_refusee(self):
        with self.assertRaises(ValueError):
            formater_date('01/08/2026')
