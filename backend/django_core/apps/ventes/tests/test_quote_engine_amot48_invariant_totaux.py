"""AMOT48 — garde de classe « aucun dirham ne s'évapore entre le devis et son
PDF » : Σ lignes imprimées = total imprimé = totaux du noyau de l'option
effective (et ``display_total == totaux_all.ttc`` pour une option).

Parcourt les branches de ``build_quote_data`` (mono-option réseau + batterie,
deux options, variante après signature, remise, arrondi) sur le moteur RÉEL
et le noyau RÉEL (``domain.argent.totaux``). Test-du-test : remettre
``_all_rows = sans_items`` (défaut AMOT8) ⇒ la garde nomme
``display_total_vs_noyau`` / ``somme_lignes_vs_ht_brut``
(``test_defaut_amot8_nomme``) ; la règle nocturne
``DOC_TOTAL_IMPRIME_NE_NOYAU`` le signale.
"""
import copy

from django.test import TestCase

from apps.ventes.coherence.moteur import _Ctx
from apps.ventes.coherence.registre import REGISTRE, charger_regles
from apps.ventes.domain.argent import Vue, totaux
from apps.ventes.models import Devis
from apps.ventes.quote_engine.builder import (
    build_quote_data, clean_pdf_options, ecarts_totaux_imprimes,
)
from apps.ventes.tests._quote_engine_common import (
    DEUX_OPTIONS, make_client, make_company, make_devis, make_user,
)
from apps.ventes.utils.options import SANS_BATTERIE

_RESEAU_BATTERIE = [
    ('Panneau mono 550W', '10', '1100'),
    ('Onduleur réseau Huawei 5kW', '1', '8000'),
    ('Batterie Dyness 5kWh', '1', '20000'),
]
_DEUX = [
    ('Panneau mono 550W', '10', '1100'),
    ('Onduleur réseau Huawei 5kW', '1', '8000'),
    ('Onduleur hybride Deye 5kW', '1', '15000'),
    ('Batterie Dyness 5kWh', '1', '20000'),
]


class InvariantTotauxTests(TestCase):
    def setUp(self):
        charger_regles()
        self.company = make_company(slug='amot48-co', nom='AMOT48')
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        self.n = 0

    def _devis(self, lignes, etude=None, remise='0'):
        self.n += 1
        return make_devis(self.company, self.user, self.client_obj, lignes,
                          remise_globale=remise,
                          reference=f'DEV-AMOT48-{self.n}',
                          etude_params=etude)

    @staticmethod
    def _noyau(devis):
        return float(totaux(devis, vue=Vue.NET, unitaire=True).ttc)

    def _cas(self):
        signe = self._devis(_DEUX, dict(DEUX_OPTIONS))
        Devis.objects.filter(pk=signe.pk).update(option_acceptee=SANS_BATTERIE)
        signe.refresh_from_db()
        return [
            ('mono_reseau_batterie', self._devis(_RESEAU_BATTERIE), {}),
            ('deux_options', self._devis(_DEUX, dict(DEUX_OPTIONS)), {}),
            ('signe_sans', signe, {}),
            ('remise', self._devis(_DEUX, dict(DEUX_OPTIONS), remise='7.5'),
             {}),
            ('arrondi', self._devis([
                ('Panneau mono 550W', '9', '1133.33'),
                ('Onduleur réseau Huawei 5kW', '1', '7999.99')]), {}),
            ('onepage', self._devis(_DEUX, dict(DEUX_OPTIONS)),
             {'pdf_mode': 'onepage'}),
        ]

    def test_invariant_tient_sur_les_branches(self):
        for nom, devis, opts in self._cas():
            with self.subTest(cas=nom):
                data = build_quote_data(devis, clean_pdf_options(opts))
                self.assertEqual(
                    ecarts_totaux_imprimes(data, self._noyau(devis)), [])
                self.assertFalse(any(
                    'total imprimé incohérent' in a
                    for a in data.get('avertissements_internes', [])))

    def test_variante_apres_signature_sans_comparaison_noyau(self):
        devis = self._cas()[2][1]
        data = build_quote_data(devis, clean_pdf_options(
            {'variante_option': 'avec'}))
        self.assertFalse(any('total imprimé incohérent' in a
                             for a in data.get('avertissements_internes', [])))

    def test_defaut_amot8_nomme(self):
        """Réintroduire le défaut AMOT8 (batterie retirée des lignes, total
        de l'option sans) : la garde le nomme."""
        devis = self._devis(_RESEAU_BATTERIE)
        data = copy.deepcopy(build_quote_data(
            devis, clean_pdf_options({'pdf_mode': 'full'})))
        data['all_items'] = [it for it in data['all_items']
                             if 'Batterie' not in it['designation']]
        data['display_total'] = 9999.0
        etages = {e['etage'] for e in ecarts_totaux_imprimes(
            data, self._noyau(devis))}
        self.assertIn('display_total_vs_noyau', etages)
        self.assertIn('somme_lignes_vs_ht_brut', etages)
        self.assertIn('display_total_vs_totaux_all', etages)

    def test_regle_nocturne(self):
        r = REGISTRE['DOC_TOTAL_IMPRIME_NE_NOYAU']
        devis = self._devis(_RESEAU_BATTERIE)
        ctx = _Ctx(self.company)
        self.assertEqual(r.check(r, devis, ctx), [])
        data = copy.deepcopy(build_quote_data(devis, clean_pdf_options({})))
        data['display_total'] = 9999.0
        ctx2 = _Ctx(self.company)
        ctx2.injecter_donnees(devis, data)
        out = r.check(r, devis, ctx2)
        self.assertTrue(any(v.cle.get('etage') == 'display_total_vs_noyau'
                            for v in out))
