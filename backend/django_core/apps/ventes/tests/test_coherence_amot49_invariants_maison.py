"""AMOT49 (C-AMOT-038) — règles nocturnes des invariants maison
``DOC_RENDU_SANS_MARGE`` et ``DOC_POMPAGE_SANS_ONDULEUR_BATTERIE``, plus le
tableau de gouvernance ``INVARIANTS_MAISON → règle`` testé.

Moteur réel (``build_quote_data`` via le contexte d'audit), registre réel.
Test-du-test : retirer ``DOC_RENDU_SANS_MARGE`` du registre ⇒
``test_gouvernance`` le nomme.
"""
import copy
from decimal import Decimal

from django.test import TestCase

from apps.ventes.coherence.moteur import _Ctx
from apps.ventes.coherence.registre import REGISTRE, charger_regles
from apps.ventes.coherence.regles_invariants import INVARIANTS_MAISON
from apps.ventes.models import Devis
from apps.ventes.quote_engine.builder import build_quote_data, clean_pdf_options
from apps.ventes.tests._quote_engine_common import (
    make_client, make_company, make_devis, make_user,
)


class InvariantsMaisonTests(TestCase):
    def setUp(self):
        charger_regles()
        self.company = make_company(slug='amot49-co', nom='AMOT49')
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        self.n = 0

    def _devis(self, lignes, mode='residentiel'):
        self.n += 1
        devis = make_devis(self.company, self.user, self.client_obj, lignes,
                           reference=f'DEV-AMOT49-{self.n}')
        Devis.objects.filter(pk=devis.pk).update(mode_installation=mode)
        devis.refresh_from_db()
        return devis

    @staticmethod
    def _run(rule_id, devis, ctx):
        r = REGISTRE[rule_id]
        return r.check(r, devis, ctx)

    def test_gouvernance(self):
        for invariant, cible in INVARIANTS_MAISON.items():
            with self.subTest(invariant=invariant):
                self.assertTrue(
                    cible in REGISTRE or str(cible).startswith('raison'),
                    f"invariant « {invariant} » sans règle ni raison écrite")

    def test_rendu_sans_marge(self):
        devis = self._devis([('Panneau mono 550W', '10', '1100'),
                             ('Onduleur réseau Huawei 5kW', '1', '8000')])
        self.assertEqual(
            self._run('DOC_RENDU_SANS_MARGE', devis, _Ctx(self.company)), [])
        data = copy.deepcopy(build_quote_data(devis, clean_pdf_options({})))
        data['all_items'][0]['prix_achat'] = 700.0
        ctx = _Ctx(self.company)
        ctx.injecter_donnees(devis, data)
        out = self._run('DOC_RENDU_SANS_MARGE', devis, ctx)
        self.assertTrue(any('prix_achat' in v.valeurs.get('cle', '')
                            for v in out))

    def test_valeur_egale_prix_achat(self):
        devis = self._devis([('Panneau mono 550W', '10', '1100')])
        ligne = devis.lignes.first()
        ligne.produit.prix_achat = Decimal('777')
        ligne.produit.save(update_fields=['prix_achat'])
        data = copy.deepcopy(build_quote_data(devis, clean_pdf_options({})))
        data['all_items'][0]['cout_revient'] = 777.0
        ctx = _Ctx(self.company)
        ctx.injecter_donnees(devis, data)
        self.assertTrue(self._run('DOC_RENDU_SANS_MARGE', devis, ctx))

    def test_pompage_sans_onduleur_batterie(self):
        propre = self._devis([('Pompe immergée OSP 30/8 10 CV', '1', '15000'),
                              ('Panneau mono 550W', '14', '1100')],
                             mode='agricole')
        self.assertEqual(self._run('DOC_POMPAGE_SANS_ONDULEUR_BATTERIE',
                                   propre, _Ctx(self.company)), [])
        fautif = self._devis([('Pompe immergée OSP 30/8 10 CV', '1', '15000'),
                              ('Onduleur hybride Deye 5kW', '1', '12000')],
                             mode='agricole')
        out = self._run('DOC_POMPAGE_SANS_ONDULEUR_BATTERIE', fautif,
                        _Ctx(self.company))
        self.assertTrue(out)
