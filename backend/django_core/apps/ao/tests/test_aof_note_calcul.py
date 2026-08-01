"""AOF134 — la note de calcul recalcule ses bilans, elle ne les recopie pas.

Le cas reproduit est celui du dossier réel du 27/07 : trois bâtiments
(A 95,0 kWc · B 75,0 kWc · C 180,0 kWc), un banc de stockage de 3 piles de
6 packs, et une bascule d'équipement qui doit faire bouger les bilans SANS
qu'un humain ne retape quoi que ce soit.

Ce que ces tests verrouillent :
  1. les bilans sont dérivés du contexte (production = kWc × productible) ;
  2. changer l'équipement (donc le contexte) change la note — sans édition ;
  3. une grandeur absente fait ÉCHOUER le rendu au lieu de sortir un zéro ;
  4. le gabarit ne contient AUCUN chiffre métier littéral ;
  5. étanchéité (ratchet AOF129) : aucune grandeur de coût ne peut traverser.

Run :
    python manage.py test apps.ao.tests.test_aof_note_calcul -v2
"""
import re
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

from apps.ao.fabrique.rendus.note_calcul import (
    construire_note_calcul, rendre_note_calcul_html,
)

GABARIT = Path(settings.BASE_DIR) / 'templates' / 'ao' / 'note_calcul.html'


def contexte_frdisi(**surcharges):
    """Contexte de dossier MINIMAL mais réaliste (patron AOF111)."""
    contexte = {
        'version': 1,
        'empreinte': 'a' * 64,
        'identite': {'raison_sociale': 'ACCORDIA TECH'},
        'marche': {'reference': 'AO-FRDISI-01', 'objet': 'Centrale PV'},
        'site': {
            'productible': {
                'valeur': Decimal('1650'),
                'unite': 'kWh/kWc/an',
                'ville': 'Fès',
                'source': 'table canonique du dépôt (productible par ville)',
                'date': '2026-01-15',
            },
        },
        'batiments': [
            {'code': 'A', 'libelle': 'Bâtiment A', 'kwc': Decimal('95.0'),
             'modules_engages': 152, 'puissance_module_wc': Decimal('625')},
            {'code': 'B', 'libelle': 'Bâtiment B', 'kwc': Decimal('75.0'),
             'modules_engages': 120, 'puissance_module_wc': Decimal('625')},
            {'code': 'C', 'libelle': 'Bâtiment C', 'kwc': Decimal('180.0'),
             'modules_engages': 288, 'puissance_module_wc': Decimal('625')},
        ],
        'derivations': {
            'chaines': [
                {'batiment': 'A', 'modules_par_chaine': 16, 'nombre': 9,
                 'observation': ''},
            ],
            'onduleurs': {
                'unites': [{'repere': 'OND-1', 'designation': 'Onduleur 110 kW',
                            'quantite': 3,
                            'puissance_ac_kw': Decimal('110')}],
                'puissance_ac_kw': Decimal('330'),
                'ratio_dc_ac': Decimal('1.061'),
                'conforme_cps': True,
                'motifs': [],
            },
            'stockage': {
                'kwh_installes': Decimal('289.44'),
                'nb_packs': 18,
                'tension_banc_v': Decimal('307.2'),
                'besoin_nocturne_kwh': Decimal('284.5'),
                'couverture_nocturne_pct': Decimal('100.0'),
                'marge_kwh': Decimal('4.94'),
            },
            'liaison_inter_sites': {
                'nature': 'liaison enterrée AC',
                'longueur_m': Decimal('420'),
                'section_mm2': Decimal('95'),
                'chute_tension_pct': Decimal('0.85'),
            },
        },
        'cotes_a_confirmer': [],
    }
    contexte.update(surcharges)
    return contexte


class BilansDerivesTest(SimpleTestCase):
    def test_production_est_le_produit_kwc_par_productible(self):
        note = construire_note_calcul(contexte_frdisi())
        par_code = {ligne['code']: ligne for ligne in note['batiments']}
        self.assertEqual(par_code['C']['production_annuelle_kwh'],
                         Decimal('180.0') * Decimal('1650'))
        self.assertEqual(note['total']['kwc'], Decimal('350.0'))
        self.assertEqual(note['total']['modules'], 560)
        self.assertEqual(note['total']['production_annuelle_kwh'],
                         Decimal('350.0') * Decimal('1650'))

    def test_la_provenance_du_productible_est_portee_par_la_piece(self):
        note = construire_note_calcul(contexte_frdisi())
        self.assertIn('table canonique', note['productible']['source'])
        self.assertEqual(note['productible']['date'], '2026-01-15')
        html = rendre_note_calcul_html(contexte_frdisi())
        self.assertIn('table canonique', html)
        self.assertIn('2026-01-15', html)

    def test_un_changement_d_equipement_change_les_bilans_sans_intervention(self):
        avant = construire_note_calcul(contexte_frdisi())
        # Bascule batterie : le contexte change, PERSONNE n'édite la note.
        apres_ctx = contexte_frdisi()
        apres_ctx['derivations']['stockage'] = {
            'kwh_installes': Decimal('322.56'),
            'nb_packs': 20,
            'tension_banc_v': Decimal('341.3'),
            'besoin_nocturne_kwh': Decimal('284.5'),
            'couverture_nocturne_pct': Decimal('100.0'),
            'marge_kwh': Decimal('38.06'),
        }
        apres = construire_note_calcul(apres_ctx)
        self.assertNotEqual(avant['stockage']['kwh_installes'],
                            apres['stockage']['kwh_installes'])
        self.assertEqual(apres['stockage']['nb_packs'], 20)

    def test_un_changement_de_calepinage_change_les_bilans(self):
        ctx = contexte_frdisi()
        ctx['batiments'][2]['modules_engages'] = 314
        ctx['batiments'][2]['kwc'] = Decimal('196.25')
        note = construire_note_calcul(ctx)
        self.assertEqual(note['total']['modules'], 586)
        self.assertEqual(note['total']['kwc'], Decimal('366.25'))


class RefusPlutotQueZeroTest(SimpleTestCase):
    def test_grandeur_absente_leve_au_lieu_de_rendre_zero(self):
        ctx = contexte_frdisi()
        del ctx['derivations']['stockage']
        with self.assertRaises(ValueError) as capture:
            construire_note_calcul(ctx)
        self.assertIn('stockage', str(capture.exception))

    def test_productible_absent_leve(self):
        ctx = contexte_frdisi()
        del ctx['site']['productible']['source']
        with self.assertRaises(ValueError) as capture:
            construire_note_calcul(ctx)
        self.assertIn('productible', str(capture.exception))

    def test_grandeur_a_none_leve(self):
        ctx = contexte_frdisi()
        ctx['derivations']['onduleurs'] = None
        with self.assertRaises(ValueError):
            construire_note_calcul(ctx)

    def test_aucun_batiment_leve(self):
        ctx = contexte_frdisi()
        ctx['batiments'] = []
        with self.assertRaises(ValueError):
            construire_note_calcul(ctx)


class MentionAConfirmerTest(SimpleTestCase):
    def test_les_cotes_a_confirmer_sont_signalees(self):
        ctx = contexte_frdisi(cotes_a_confirmer=[
            {'batiment': 'C', 'repere': 'C-7',
             'libelle': 'acrotère nord non relevé'},
        ])
        note = construire_note_calcul(ctx)
        self.assertTrue(note['mention_a_confirmer'])
        html = rendre_note_calcul_html(ctx)
        self.assertIn('acrotère nord non relevé', html)
        self.assertIn('confirmer à l', html)

    def test_sans_cote_douteuse_aucune_mention(self):
        note = construire_note_calcul(contexte_frdisi())
        self.assertFalse(note['mention_a_confirmer'])
        self.assertNotIn('acrotère', rendre_note_calcul_html(contexte_frdisi()))


class GabaritSansLitteralTest(SimpleTestCase):
    """Détecteur de littéraux appliqué au GABARIT lui-même.

    Un nombre de 4 chiffres et plus dans le corps du gabarit serait un bilan
    gravé — exactement le défaut « la pièce la plus lue est la plus fausse ».
    Le bloc <style> est exclu : ses valeurs sont typographiques, pas métier.
    """

    def test_aucun_nombre_de_quatre_chiffres_hors_style(self):
        source = GABARIT.read_text(encoding='utf-8')
        corps = re.sub(r'<style>.*?</style>', '', source, flags=re.S)
        corps = re.sub(r'\{%\s*comment\s*%\}.*?\{%\s*endcomment\s*%\}', '',
                       corps, flags=re.S)
        restants = re.findall(r'(?<![\w.-])\d{4,}(?![\w-])', corps)
        self.assertEqual(restants, [], "Chiffres gravés dans le gabarit : {}"
                         .format(restants))


class EtancheiteNoteTest(SimpleTestCase):
    """Ratchet AOF129 appliqué à CETTE pièce (elle est remise au client)."""

    def test_une_cle_de_cout_dans_le_contexte_fait_echouer_le_rendu(self):
        for cle in ('prix_achat', 'cout_revient', 'marge', 'benefice_net',
                    'maximum_posable'):
            ctx = contexte_frdisi()
            ctx['batiments'][0][cle] = Decimal('1')
            with self.assertRaises(ValueError, msg=cle) as capture:
                construire_note_calcul(ctx)
            self.assertIn(cle, str(capture.exception))

    def test_aucun_mot_de_cout_dans_le_rendu(self):
        html = rendre_note_calcul_html(contexte_frdisi()).lower()
        for interdit in ("prix d'achat", 'coût de revient', 'marge',
                         'bénéfice', 'maximum posable'):
            self.assertNotIn(interdit, html)
