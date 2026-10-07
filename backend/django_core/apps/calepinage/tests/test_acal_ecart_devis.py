"""ACAL104 (C-ACAL-101, D-ACAL-6) — le résultat du calepinage et le rapport
d'étude publient l'écart entre la production du DEVIS (moteur devis, imprimée
au client) et le P50 de l'étude technique — jamais l'inverse.

* ``resultat.ecart_devis`` = ``{devis, reference, production_devis_kwh,
  p50_calepinage_kwh, ecart_pct, mention}`` (contrat
  ``calepinage_resultat.json``, ``exemple_ecart_devis``) ; la production du
  devis est LUE par ``apps.ventes.selectors.production_attendue_pour_devis``
  (figure recalée, ACAL101) ;
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

from apps.calepinage.models import Calepinage
from apps.calepinage.services.electrique import (
    BLOCS_SIMULATION, CLE_SIMULATION, MENTION_ECART_DEVIS,
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

    def test_rapport_etude_imprime_ecart(self):
        exemple = CONTRAT['exemple_ecart_devis']
        html = html_de_section({'resultat': exemple})
        ecart = exemple['ecart_devis']
        self.assertIn('production-ecart-devis', html)
        self.assertIn(ecart['reference'], html)
        self.assertIn('12600,0', html)   # production du devis, telle quelle
        self.assertIn('13000,0', html)   # P50 de l'étude
        self.assertIn('+3,2 %', html)
        self.assertIn('moteur du devis', html)
        # Sans écart servi : aucun bloc.
        sans = dict(exemple, ecart_devis=None)
        self.assertNotIn('production-ecart-devis',
                         html_de_section({'resultat': sans}))
        # Les MÊMES valeurs que le JSON servi, sur un vrai calepinage.
        servi = resultat_calepinage(self._calepinage(), materiel=MATERIEL)
        html = html_de_section({'resultat': servi})
        self.assertIn('10340,0', html)
        self.assertIn('15606,0', html)
        self.assertIn('+50,9 %', html)
        self.assertEqual(Decimal('50.9'),
                         Decimal(str(servi['ecart_devis']['ecart_pct'])))
