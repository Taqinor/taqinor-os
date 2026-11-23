"""ACAL104 (C-ACAL-101, D-ACAL-6) — le résultat du calepinage et le rapport
d'étude publient l'écart entre la production du DEVIS (moteur devis, imprimée
au client) et le P50 de l'étude technique — jamais l'inverse.

* ``resultat.ecart_devis`` = ``{devis, reference, production_devis_kwh,
  p50_calepinage_kwh, ecart_pct, mention}`` (contrat
  ``calepinage_resultat.json``, ``exemple_ecart_devis``) ; la production du
  devis est LUE par ``apps.ventes.selectors.production_attendue_pour_devis``
  (figure recalée, ACAL101) — jamais un RENDU du devis : le rendu relit ce
  résultat (ombrage servi, D-RES-2710-1) et crée le profil société (ACON87) ;
* ``null`` sans devis lié, sans simulation, ou simulation périmée ;
* la section « Production » du rapport d'étude imprime les deux chiffres et
  l'écart (mêmes valeurs que le JSON).

``resultat_calepinage`` RÉEL (matériel injecté par son seam de test, comme
CALX70) ; sélecteur ventes RÉEL sur un devis en base.

Run :
    python manage.py test apps.calepinage.tests.test_acal_ecart_devis -v2
"""
import copy
import json
import pathlib
from decimal import Decimal
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from apps.calepinage.models import Calepinage
from apps.calepinage.services.electrique import (
    BLOCS_SIMULATION, CLE_SIMULATION, MENTION_ECART_DEVIS, _ecart_devis,
    resultat_calepinage,
)
from apps.calepinage.services.rapport.production import html_de_section
from apps.ventes.models import Devis

from .test_api_liste import BaseApiCalepinage
from .test_calx70_resultat_sert_la_simulation import (
    LAYOUT, LAYOUT_MODIFIE, MATERIEL, SIMULATION,
)

ECHANTILLONS = (pathlib.Path(__file__).resolve().parents[1]
                / 'contract_samples')
CONTRAT = json.loads(
    (ECHANTILLONS / 'calepinage_resultat.json').read_text(encoding='utf-8'))

P50 = 15606.0
PRODUCTION_DEVIS = 10340


def _simulation(empreinte):
    depose = {CLE_SIMULATION: {'hash_entree': empreinte,
                               'version_moteur': 'essai',
                               'calcule_le': '2026-10-01T09:00:00Z',
                               'duree_s': 3.0}}
    for cle in BLOCS_SIMULATION:
        depose[cle] = copy.deepcopy(SIMULATION['exemple'][cle])
    depose['production']['total']['p50_kwh'] = P50
    return depose


class EcartDevisTest(BaseApiCalepinage):
    def setUp(self):
        super().setUp()
        self.devis = Devis.objects.create(
            company=self.company, client=self.client_a,
            reference='DEV-202610-0648', statut='brouillon',
            etude_params={'production_annuelle': PRODUCTION_DEVIS,
                          'production_source': 'saisie'})

    def _calepinage(self, *, devis=True, layout=LAYOUT, simule=True):
        calepinage = Calepinage.objects.create(
            company=self.company, client=self.client_a,
            devis=self.devis if devis else None, titre='ACAL104',
            roof_layout=copy.deepcopy(LAYOUT))
        if simule:
            empreinte = resultat_calepinage(
                calepinage, materiel=MATERIEL)['hash_entree']
            calepinage.resultat = _simulation(empreinte)
        calepinage.roof_layout = copy.deepcopy(layout)
        calepinage.save()
        return calepinage

    def test_resultat_publie_ecart_devis(self):
        resultat = resultat_calepinage(self._calepinage(), materiel=MATERIEL)
        self.assertTrue(resultat['simule'])
        self.assertEqual(resultat['ecart_devis'], {
            'devis': self.devis.pk,
            'reference': 'DEV-202610-0648',
            'production_devis_kwh': float(PRODUCTION_DEVIS),
            'p50_calepinage_kwh': P50,
            'ecart_pct': 50.9,
            'mention': MENTION_ECART_DEVIS,
        })
        # Même forme (mêmes clés) que l'échantillon du contrat partagé.
        self.assertEqual(set(resultat['ecart_devis']),
                         set(CONTRAT['exemple_ecart_devis']['ecart_devis']))
        self.assertEqual(MENTION_ECART_DEVIS,
                         CONTRAT['exemple_ecart_devis']['ecart_devis'][
                             'mention'])
        # D-ACAL-6 — le devis ne lit JAMAIS le P50 : sa production est
        # inchangée après la lecture du résultat.
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.etude_params['production_annuelle'],
                         PRODUCTION_DEVIS)

    def test_ecart_null_sans_devis_ou_perime(self):
        sans_devis = self._calepinage(devis=False)
        self.assertIsNone(resultat_calepinage(
            sans_devis, materiel=MATERIEL)['ecart_devis'])
        sans_devis.delete()
        non_simule = self._calepinage(simule=False)
        self.assertIsNone(resultat_calepinage(
            non_simule, materiel=MATERIEL)['ecart_devis'])
        non_simule.delete()
        perime = self._calepinage(layout=LAYOUT_MODIFIE)
        resultat = resultat_calepinage(perime, materiel=MATERIEL)
        self.assertTrue(resultat['simulation_perimee'])
        self.assertIsNone(resultat['ecart_devis'])
        # Devis sans production : rien à comparer.
        Devis.objects.filter(pk=self.devis.pk).update(etude_params={})
        perime.delete()
        frais = self._calepinage()
        self.assertIsNone(resultat_calepinage(
            frais, materiel=MATERIEL)['ecart_devis'])

    def test_figure_non_imprimee_jamais_dite_imprimee(self):
        """ACAL1274 (T2-F2-RESU-024) — la figure POSÉE par le calepinage
        (``production_source='calepinage'``) n'est plus imprimée par le PDF
        aux règles corrigées (AMOT15 : le moteur du devis la recalcule), ni
        une figure C&I (le PDF imprime le moteur C&I) : aucun écart « imprimé
        au client » n'est servi. Règles d'origine : le PDF imprime la figure
        stockée, l'écart est servi."""
        calepinage = self._calepinage()
        cas = (({'production_source': 'calepinage'}, {}, False),
               ({'production_source': 'saisie'}, {'mode_installation': 'commercial'}, False),
               ({'production_source': 'calepinage'}, {'regles_calcul': 1}, True))
        for source, champs, servi in cas:
            Devis.objects.filter(pk=self.devis.pk).update(
                etude_params=dict(source, production_annuelle=PRODUCTION_DEVIS),
                mode_installation=champs.get('mode_installation', 'residentiel'),
                regles_calcul=champs.get('regles_calcul', 14))
            ecart = resultat_calepinage(calepinage, materiel=MATERIEL)['ecart_devis']
            self.assertEqual(ecart is not None, servi, (source, champs))

    def test_devis_d_une_autre_conception_sans_ecart(self):
        """ACON27 (C-ACON-137) — le devis imprime une AUTRE conception (12
        modules, H1) que le calepinage (20 modules, H2) : aucun écart servi ni
        imprimé ; empreintes égales : écart servi ; empreinte inconnue : servi."""
        calepinage = self._calepinage()
        h1, h2 = 'a' * 64, 'b' * 64
        Calepinage.objects.filter(pk=calepinage.pk).update(layout_hash=h2)
        calepinage.refresh_from_db()
        for empreinte_devis, servi in ((h1, False), (h2, True), (None, True)):
            Devis.objects.filter(pk=self.devis.pk).update(layout_hash=empreinte_devis)
            resultat = resultat_calepinage(calepinage, materiel=MATERIEL)
            with self.subTest(empreinte_devis=empreinte_devis):
                self.assertEqual(resultat['ecart_devis'] is not None, servi)
                self.assertEqual('production-ecart-devis' in html_de_section({'resultat': resultat}), servi)

    def test_rapport_etude_imprime_ecart(self):
        exemple = CONTRAT['exemple_ecart_devis']
        html = html_de_section({'resultat': exemple})
        ecart = exemple['ecart_devis']
        self.assertIn('production-ecart-devis', html)
        self.assertIn(ecart['reference'], html)
        self.assertIn('12\u202f600,0', html)   # production du devis, telle quelle
        self.assertIn('13\u202f000,0', html)   # P50 de l'étude
        self.assertIn('+3,2 %', html)
        self.assertIn('moteur du devis', html)
        # Sans écart servi : aucun bloc.
        sans = dict(exemple, ecart_devis=None)
        self.assertNotIn('production-ecart-devis',
                         html_de_section({'resultat': sans}))
        # Les MÊMES valeurs que le JSON servi, sur un vrai calepinage.
        servi = resultat_calepinage(self._calepinage(), materiel=MATERIEL)
        html = html_de_section({'resultat': servi})
        self.assertIn('10\u202f340,0', html)
        self.assertIn('15\u202f606,0', html)
        self.assertIn('+50,9 %', html)
        self.assertEqual(Decimal('50.9'),
                         Decimal(str(servi['ecart_devis']['ecart_pct'])))


class EcartDevisSansRenduTest(SimpleTestCase):
    """L'écart de l'atelier lit la figure du devis par le sélecteur YSERV8,
    jamais par un rendu ``build_quote_data`` : le rendu d'un devis brouillon
    relit ``resultat_calepinage`` (ombrage servi, D-RES-2710-1 — boucle) et
    crée le profil société absent, qui périme la simulation (ACON87). Sans
    base : devis et sélecteurs sont des doublures."""

    def _ecart(self, production):
        devis = SimpleNamespace(pk=71, company_id=3, reference='DEV-202611-0071', roof_layout={})
        calepinage = SimpleNamespace(devis_id=71, company_id=3)
        with mock.patch('apps.ventes.selectors.get_devis_by_pk', return_value=devis), \
                mock.patch('apps.ventes.selectors_calepinage._conception_a_jour', return_value=True), \
                mock.patch('apps.ventes.selectors.production_attendue_pour_devis',
                           return_value=production) as lue, \
                mock.patch('apps.ventes.quote_engine.builder.build_quote_data') as rendu:
            ecart = _ecart_devis(calepinage, 4808.0)
        rendu.assert_not_called()
        lue.assert_called_once_with(71)
        return ecart

    def test_la_phrase_porte_la_figure_du_devis_sans_rendu(self):
        ecart = self._ecart(Decimal('3628'))
        self.assertEqual(ecart['production_devis_kwh'], 3628.0)
        self.assertEqual(ecart['ecart_pct'], round((4808 - 3628) / 3628 * 100, 1))
        self.assertIn('3\u202f628,0', html_de_section({'resultat': {'ecart_devis': ecart}}))

    def test_sans_production_aucune_phrase(self):
        """Pompage : aucune production au devis ⇒ aucun écart, jamais un 0."""
        self.assertIsNone(self._ecart(None))
        self.assertEqual(html_de_section({'resultat': {'ecart_devis': None}}).count('production-ecart-devis'), 0)
