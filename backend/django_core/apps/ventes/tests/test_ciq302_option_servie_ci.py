"""CIQ302 — devis C&I à deux options : l'offre RÉSEAU seule est l'offre
principale ; la batterie est une option qui ne montre que la valeur chiffrée
par le moteur.

Avant : ``builder`` faisait de l'option AVEC le tableau, les totaux et
``display_total`` dès qu'il y avait deux options, pendant que la couverture
C&I imprimait l'économie de l'option SANS — couverture et page 3 se
contredisaient (C3-05, C3-VA-03). Le noyau (``option_effective``) suivait la
même règle AVEC.

Après (convention 5) : commercial / industriel → ``option_servie = 'sans'`` ;
``all_items`` / ``totaux_all`` / ``display_total`` décrivent l'offre réseau ;
``option_effective`` = SANS dans le MÊME commit (jumeau, leçon QJR400) ; le
panier batterie part dans ``option_batterie``. L'option acceptée et un
scénario mono déclaré gardent la priorité. Le résidentiel ne bouge pas.

Run:
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_ciq302_option_servie_ci -v 2
"""
from decimal import Decimal

from django.test import SimpleTestCase, TestCase

from apps.ventes.utils import options as opts_mod

LIGNES_DEUX_OPTIONS = [
    ('Onduleur réseau Huawei 10kW Triphasé', '1', '11700'),
    ('Onduleur hybride Deye 10kW Triphasé', '1', '24000'),
    ('Panneau Canadien Solar 710W', '14', '1100'),
    ('Batterie Dyness 10 kWh', '1', '14000'),
    ('Structures acier', '14', '375'),
    ('Installation', '1', '4000'),
]


class _Devis:
    def __init__(self, mode):
        self.mode_installation = mode


class TestRegleDuNoyau(SimpleTestCase):
    """La règle partagée moteur ↔ noyau (aucune BD)."""

    def test_ci_met_en_avant_l_offre_reseau(self):
        for mode in ('commercial', 'industriel', ' Industriel '):
            with self.subTest(mode=mode):
                self.assertEqual(opts_mod.option_mise_en_avant(_Devis(mode)),
                                 opts_mod.SANS_BATTERIE)

    def test_residentiel_et_autres_gardent_avec(self):
        for mode in ('residentiel', 'agricole', '', None):
            with self.subTest(mode=mode):
                self.assertEqual(opts_mod.option_mise_en_avant(_Devis(mode)),
                                 opts_mod.AVEC_BATTERIE)


class TestOptionServieCI(TestCase):
    """``build_quote_data`` RÉEL (jamais mocké) + noyau monnaie."""

    def setUp(self):
        from apps.ventes.tests._quote_engine_common import (
            make_client, make_company, make_user)
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)

    def _devis(self, mode, reference, etude=None):
        from apps.ventes.tests._quote_engine_common import (
            DEUX_OPTIONS, make_devis)
        devis = make_devis(self.company, self.user, self.client_obj,
                           LIGNES_DEUX_OPTIONS, reference=reference,
                           etude_params=dict(etude or DEUX_OPTIONS))
        devis.mode_installation = mode
        devis.save(update_fields=['mode_installation'])
        return devis

    def _data(self, devis):
        from apps.ventes.models import Devis
        from apps.ventes.quote_engine.builder import build_quote_data
        return build_quote_data(Devis.objects.get(pk=devis.pk),
                                {'pdf_mode': 'full'})

    @staticmethod
    def _designations(rows):
        return sorted(r['designation'] for r in rows)

    def test_ci_deux_options_sert_le_reseau_seul(self):
        from apps.ventes.models import Devis
        for mode in ('commercial', 'industriel'):
            with self.subTest(mode=mode):
                devis = self._devis(mode, f'DEV-CIQ302-{mode[:3].upper()}')
                data = self._data(devis)
                self.assertTrue(data['deux_options'])
                self.assertEqual(data['option_servie'], 'sans')
                self.assertEqual(data['display_total'],
                                 data['totaux_sans']['ttc'])
                self.assertEqual(data['totaux_all']['ttc'],
                                 data['totaux_sans']['ttc'])
                self.assertEqual(self._designations(data['all_items']),
                                 self._designations(data['sans_items']))
                self.assertFalse(any('Batterie' in r['designation']
                                     for r in data['all_items']))
                ob = data['option_batterie']
                self.assertEqual(ob['totaux'], data['totaux_avec'])
                self.assertTrue(any('Batterie' in r['designation']
                                    for r in ob['lignes']))
                self.assertIsNone(ob['valeur_chiffree'])
                self.assertTrue(ob['motif'])
                # Noyau monnaie : la MÊME option, le MÊME nombre.
                frais = Devis.objects.get(pk=devis.pk)
                self.assertEqual(opts_mod.option_effective(frais),
                                 opts_mod.SANS_BATTERIE)
                self.assertEqual(Decimal(str(frais.total_ttc)),
                                 Decimal(str(data['display_total'])))

    def test_ci_accepte_sur_avec_garde_avec(self):
        from apps.ventes.models import Devis
        devis = self._devis('industriel', 'DEV-CIQ302-ACC')
        Devis.objects.filter(pk=devis.pk).update(
            option_acceptee=opts_mod.AVEC_BATTERIE)
        frais = Devis.objects.get(pk=devis.pk)
        self.assertEqual(opts_mod.option_effective(frais),
                         opts_mod.AVEC_BATTERIE)
        data = self._data(devis)
        self.assertEqual(data['option_servie'], 'avec')
        self.assertEqual(data['display_total'], data['totaux_avec']['ttc'])
        self.assertNotIn('option_batterie', data)

    def test_ci_scenario_mono_avec_garde_la_priorite(self):
        from apps.ventes.models import Devis
        devis = self._devis('commercial', 'DEV-CIQ302-MONO',
                            {'scenario': 'Avec batterie'})
        frais = Devis.objects.get(pk=devis.pk)
        # Le scénario mono décide (QJR400) : jamais l'offre réseau imposée.
        self.assertNotEqual(opts_mod.option_effective(frais),
                            opts_mod.SANS_BATTERIE)
        data = self._data(devis)
        self.assertNotIn('option_servie', data)
        self.assertEqual(data['display_total'], data['totaux_avec']['ttc'])

    def test_residentiel_deux_options_inchange(self):
        """Non-régression : un résidentiel à deux options titre AVEC."""
        from apps.ventes.models import Devis
        devis = self._devis('residentiel', 'DEV-CIQ302-RES')
        data = self._data(devis)
        self.assertTrue(data['deux_options'])
        self.assertNotIn('option_servie', data)
        self.assertNotIn('option_batterie', data)
        self.assertEqual(data['display_total'], data['totaux_avec']['ttc'])
        self.assertEqual(
            opts_mod.option_effective(Devis.objects.get(pk=devis.pk)),
            opts_mod.AVEC_BATTERIE)

    def test_repli_sans_moteur_suit_la_meme_regle(self):
        devis = self._devis('commercial', 'DEV-CIQ302-REPLI')
        data = self._data(devis)
        repli = opts_mod.totaux_affichage_repli(devis)
        self.assertEqual(repli['nb_options'], 2)
        self.assertAlmostEqual(repli['total'],
                               float(data['totaux_sans']['ttc']), places=2)

    def test_echappement_option_batterie_un_seul(self):
        from apps.ventes.quote_engine.builder import echapper_textes_client
        devis = self._devis('industriel', 'DEV-CIQ302-ESC')
        sortie = echapper_textes_client(self._data(devis))
        self.assertIs(sortie['option_batterie']['lignes'],
                      sortie['avec_items'])
