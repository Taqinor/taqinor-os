"""QX50 — Injection 82-21 (industriel/commercial) : constantes sourcées + bornes.

Le surplus injectable est plafonné à 20 % de la production et valorisé au tarif
ANRE NET des frais d'accès réseau. OFF par défaut ; la mention réglementaire
accompagne toujours la ligne. Le miroir JS est supprimé (CIQ228) : la valeur vient du serveur.

QXMT — couvre AUSSI le barème MOYENNE TENSION ONEE (``TARIF_MT_ONEE``) : valeurs
sourcées, omission plutôt qu'invention quand une donnée manque ; plus de
miroir ``solar.js`` (CIQ228).

Run:
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_qx50_injection_82_21 -v 2
"""
import os

from django.test import SimpleTestCase

from apps.ventes.quote_engine import constants_82_21 as c

_REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', '..'))
SOLAR_JS = os.path.join(
    _REPO_ROOT, 'frontend', 'src', 'features', 'ventes', 'solar.js')


def _plages_py(saisons):
    return [(b['saison'], p['poste'], p['de_h'], p['a_h'])
            for b in saisons for p in b['postes']]


class TestModuleSansNet(SimpleTestCase):
    """CIQ201 — aucune déduction TURD/TURT (ANRE 02/25 art. 8) : le « net »
    et les frais d'accès disparaissent du module (garde de grep)."""

    def test_frais_reseau_et_net_absents(self):
        with open(c.__file__, encoding='utf-8') as fh:
            src = fh.read()
        self.assertNotIn('FRAIS_RESEAU', src)
        self.assertNotIn('net_tarif_dh_kwh', src)
        self.assertFalse(hasattr(c, 'net_tarif_dh_kwh'))

    def test_tss_turd_turt_documentaires(self):
        self.assertEqual(c.TSS_C_KWH, 6.81)
        self.assertEqual(c.TURD_C_KWH, 6.07)
        self.assertEqual(c.TURT_C_KWH, 6.85)


class TestInjectionBornes(SimpleTestCase):
    def test_surplus_mt_valorise_au_brut_018(self):
        # prod 400000, autoconso 352000 → surplus 48000 (< plafond 80000)
        kwh, dh = c.injection_annuelle(400000, 352000)
        self.assertEqual(kwh, 48000)
        self.assertEqual(dh, round(48000 * 0.18))   # 8640, aucun net

    def test_capped_at_20pct(self):
        # prod 100000, autoconso 0 → surplus 100000 BORNÉ à 20 % = 20000
        kwh, dh = c.injection_annuelle(100000, 0)
        self.assertEqual(kwh, 20000)
        self.assertEqual(dh, 3600)          # 20000 × 0,18

    def test_pointe(self):
        self.assertEqual(c.injection_annuelle(100000, 0, pointe=True),
                         (20000, 4200))     # 20000 × 0,21

    def test_no_surplus(self):
        self.assertEqual(c.injection_annuelle(100000, 100000), (0, 0))

    def test_never_negative(self):
        # autoconso > prod ne donne jamais un surplus négatif
        self.assertEqual(c.injection_annuelle(100000, 150000), (0, 0))

    def test_defensive_on_bad_input(self):
        self.assertEqual(c.injection_annuelle(None, None), (0, 0))
        self.assertEqual(c.injection_annuelle("x", "y"), (0, 0))


class TestSourcedConstants(SimpleTestCase):
    def test_tarifs_anre_04_26(self):
        self.assertEqual(c.ANRE_TARIF_HORS_POINTE, 0.18)
        self.assertEqual(c.ANRE_TARIF_POINTE, 0.21)
        self.assertIn('04/26', c.ANRE_TARIF_SOURCE)
        self.assertIn('MT/HT/THT', c.ANRE_TARIF_SOURCE)

    def test_mention_sourcee(self):
        self.assertIn('décision 04/26', c.MENTION_82_21)
        self.assertIn('loi 82-21, art. 12', c.MENTION_82_21)
        self.assertNotIn('en révision', c.MENTION_82_21)
        self.assertIn('art. 13', c.MENTION_ART13)
        self.assertIn('non incluse', c.MENTION_ART13)
        self.assertIn('basse tension', c.MENTION_BT)

    def test_cap_is_20_loi_art12(self):
        self.assertEqual(c.PLAFOND_INJECTION_PCT, 20)
        self.assertIn('loi 82-21 art. 12', c.PLAFOND_INJECTION_SOURCE)

    def test_entete_loi_decret_decision(self):
        doc = c.__doc__ or ''
        self.assertIn('loi n° 82-21', doc)
        self.assertIn('décret n° 2.25.100', doc)
        self.assertIn('décision ANRE n° 04/26', doc)
        self.assertNotIn('décret 82-21', doc)


class TestTarifExcedentEnVigueur(SimpleTestCase):
    def test_dans_la_periode(self):
        tarif, motif = c.tarif_excedent_en_vigueur('2026-10-05')
        self.assertIsNone(motif)
        self.assertEqual(tarif['hors_pointe'], 0.18)

    def test_apres_fevrier_2027_none_et_motif(self):
        tarif, motif = c.tarif_excedent_en_vigueur('2027-03-01')
        self.assertIsNone(tarif)
        self.assertIn('28/02/2027', motif)


class TestRegimeReexporte(SimpleTestCase):
    def test_seuils_sont_ceux_du_noyau(self):
        from core.reglementaire import regime_8221 as noyau
        self.assertIs(c.SEUIL_DECLARATION_KW, noyau.SEUIL_DECLARATION_KW)
        self.assertIs(c.SEUIL_AUTORISATION_KW, noyau.SEUIL_AUTORISATION_KW)
        self.assertIs(c.regime_8221_suggere, noyau.regime_8221_suggere)


class TestTarifMtSource(SimpleTestCase):
    """QXMT — barème ONEE « Tarif Général (MT) » (one.org.ma, 18/08/2026)."""

    def test_postes_horaires_sources(self):
        self.assertAlmostEqual(c.TARIF_MT_ONEE['POINTE'], 1.4157, places=4)
        self.assertAlmostEqual(c.TARIF_MT_ONEE['PLEINES'], 1.0101, places=4)
        self.assertAlmostEqual(c.TARIF_MT_ONEE['CREUSES'], 0.7398, places=4)

    def test_ordre_des_postes(self):
        # Garde-fou métier : pointe > pleines > creuses, toujours.
        self.assertGreater(c.TARIF_MT_ONEE['POINTE'], c.TARIF_MT_ONEE['PLEINES'])
        self.assertGreater(c.TARIF_MT_ONEE['PLEINES'], c.TARIF_MT_ONEE['CREUSES'])

    def test_prime_puissance_sourcee(self):
        self.assertAlmostEqual(
            c.TARIF_MT_ONEE['PRIME_PUISSANCE_DH_KVA_AN'], 512.62, places=2)

    def test_tva_libelle_page_n_est_plus_une_cle(self):
        # CIQ202 : le libellé « TVA 18 % » de la page est périmé (taux légal
        # 2026 : 20 %) ; il n'est plus une clé du barème.
        self.assertNotIn('TVA_INCLUSE_PCT', c.TARIF_MT_ONEE)
        self.assertIn('taux légal 2026 : 20 %', c.MENTION_MT)

    def test_plages_horaires_sourcees(self):
        # CIQ202 : les plages sont PUBLIÉES (schéma one.org.ma/images/horr.jpg,
        # page bi-horaire, décision ANRE 04/26 art. 7) — plus jamais ``None``.
        plages = _plages_py(c.TARIF_MT_ONEE['PLAGES_H'])
        self.assertIn(('hiver', 'pointe', 17, 22), plages)
        self.assertIn(('ete', 'pointe', 18, 23), plages)
        self.assertEqual(c.poste_horaire(12, 18), 'pointe')

    def test_mention_porte_la_source_et_la_date(self):
        self.assertIn('Tarif Général (MT)', c.MENTION_MT)
        self.assertIn('one.org.ma', c.MENTION_MT)
        self.assertIn('03/10/2026', c.MENTION_MT)

    def test_bareme_disponible(self):
        self.assertTrue(c.tarif_mt_disponible())


class TestTarifMtMoyen(SimpleTestCase):
    def test_repartition_normalisee_a_100(self):
        parts = c.normaliser_repartition_mt(
            {'pointe': 10, 'pleines': 20, 'creuses': 20})
        self.assertEqual(parts, {'pointe': 20.0, 'pleines': 40.0, 'creuses': 40.0})

    def test_repartition_absente_rend_none(self):
        # AUCUNE répartition par défaut n'est inventée (plages MT non publiées).
        self.assertIsNone(c.normaliser_repartition_mt(None))
        self.assertIsNone(c.normaliser_repartition_mt({}))
        self.assertIsNone(c.normaliser_repartition_mt(
            {'pointe': 0, 'pleines': 0, 'creuses': 0}))
        self.assertIsNone(c.normaliser_repartition_mt(
            {'pointe': 'x', 'pleines': None, 'creuses': -5}))

    def test_moyenne_ponderee(self):
        # 20 % pointe / 40 % pleines / 40 % creuses
        # = 0,2×1,4157 + 0,4×1,0101 + 0,4×0,7398 = 0,98310
        moyen = c.tarif_mt_moyen({'pointe': 10, 'pleines': 20, 'creuses': 20})
        self.assertAlmostEqual(moyen, 0.98310, places=5)

    def test_poste_unique(self):
        self.assertAlmostEqual(
            c.tarif_mt_moyen({'creuses': 100}), 0.7398, places=4)

    def test_sans_repartition_pas_de_tarif_de_repli(self):
        # Le point CENTRAL de la règle « zéro chiffre inventé » : pas de prix
        # moyen par défaut, pas de retour silencieux au tarif BT.
        self.assertIsNone(c.tarif_mt_moyen(None))
        self.assertIsNone(c.tarif_mt_moyen({}))


class TestTarifMtSansJumeauJs(SimpleTestCase):
    """CIQ228 — UNE source : parametres/tarifs_officiels ↔ constants_82_21.
    Le miroir JS (`TARIF_MT_ONEE`, `tarifMtMoyen`, `netTarif8221`,
    `INJECTION_82_21`) est SUPPRIMÉ de solar.js : la parité est remplacée par
    la preuve de son ABSENCE (la valeur vient d'`economie_ci`)."""

    def test_constants_lit_la_fondation(self):
        from apps.parametres import tarifs_officiels as t
        self.assertEqual(c.TARIF_MT_ONEE['POINTE'], t.MT_GENERAL['pointe']['valeur'])
        self.assertEqual(c.TARIF_MT_ONEE['PLEINES'], t.MT_GENERAL['pleines']['valeur'])
        self.assertEqual(c.TARIF_MT_ONEE['CREUSES'], t.MT_GENERAL['creuses']['valeur'])
        self.assertEqual(c.TARIF_MT_ONEE['PRIME_PUISSANCE_DH_KVA_AN'],
                         t.MT_GENERAL['prime_fixe_kva_an']['valeur'])
        self.assertIs(c.TARIF_MT_ONEE['PLAGES_H'], t.POSTES_MT)

    def test_solar_js_sans_symboles_de_valorisation_ci(self):
        with open(SOLAR_JS, encoding='utf-8') as fh:
            src = fh.read()
        for symbole in ('TARIF_MT_ONEE', 'tarifMtMoyen', 'netTarif8221',
                        'INJECTION_82_21'):
            self.assertNotIn(symbole, src, symbole)

    def test_mention_serveur(self):
        for fragment in ('Tarif Général (MT)', 'one.org.ma', '03/10/2026',
                         'taux légal'):
            self.assertIn(fragment, c.MENTION_MT)
