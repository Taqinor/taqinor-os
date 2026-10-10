# -*- coding: utf-8 -*-
"""ACAL243 — les SAISIES électriques voyagent dans le fichier de projet.

LE CONSTAT (C-ACAL-137)
-----------------------
``export-projet.json`` puis ``import-projet`` restituaient la conception, les
postes de pertes et les variantes — mais PAS l'entrée électrique (températures,
longueurs, phases, protections, régime, transformateur, batterie, hors
réseau…), ni la saisie de raccordement, ni l'édition du schéma : le
calepinage importé repartait d'une entrée vide.

Ce qui est prouvé ici :

* format 3 : le bloc ``saisies`` est construit depuis
  ``electrique.CHAMPS_ENTREE`` (jamais une liste recopiée) — toute clé non
  portable est NOMMÉE dans ``CLES_NON_PORTABLES`` ;
* export → import → export : le bloc ``saisies`` est IDENTIQUE, écrit par les
  VRAIS écrivains (``enregistrer_entree``, ``POST raccordement/``,
  ``POST schema-unifilaire/``) et relu par ``GET entree-electrique/`` ;
* un produit désigné absent de la société d'arrivée n'est pas repris et est
  NOMMÉ dans ``ignores`` (``saisies.produits``) ;
* les dérogations (gestes) ne sont jamais exportées ;
* une saisie invalide est refusée au chemin ``saisies.<clé>`` ;
* les formats 1 et 2 restent importables.

Run :
    python manage.py test apps.calepinage.tests.test_acal_export_projet_saisies -v2
"""
from __future__ import annotations

import copy
import json
import pathlib
import unittest
from types import SimpleNamespace

from apps.calepinage.services import export_projet as ep
from apps.calepinage.services.electrique import CHAMPS_ENTREE
from apps.calepinage.services.export_projet import (
    BLOC_PRODUITS_IGNORES, CLES_ENTREE_PORTABLES, CLES_NON_PORTABLES,
    ImportProjetRefuse, _analyser_projet, importer_projet,
)

from .test_acal_sld_conception_reelle import BaseConceptionReelle, url_schema
from .test_api_liste import url_detail

ECHANTILLONS = pathlib.Path(__file__).resolve().parents[1] / 'contract_samples'
EXPORT = json.loads((ECHANTILLONS / 'export_projet.json')
                    .read_text(encoding='utf-8'))

#: ACAL151 — un transformateur déclaré, chaque grandeur SOURCÉE.
TRANSFORMATEUR = {
    'declare': True,
    'perte_a_vide_kw': {'valeur': 1.2, 'source': 'fiche',
                        'reference': 'Fiche transformateur 630 kVA'},
    'perte_en_charge_kw_nominale': {'valeur': 8.0, 'source': 'fiche',
                                    'reference': 'Fiche transformateur'},
    'puissance_nominale_kw': {'valeur': 630.0, 'source': 'saisie',
                              'reference': 'Plaque signalétique'},
}

#: Les quatre clés ÉTENDUES de CHAMPS_ENTREE (ACAL151, 152, 166) + saisies.
ENTREE = {
    'dc_m': 25.0, 'ac_m': 12.0, 'inclure_prise_terre': True,
    'transformateur': TRANSFORMATEUR,
    'regime': 'TN',
    'batterie': {'strategie': 'autoconso', 'packs': 2},
    'hors_reseau': {'actif': False},
}

RACCORDEMENT = {'puissance_souscrite_kva': 12.0, 'phases': 3,
                'tension_nominale_v': 400.0, 'cos_phi_impose': 0.9,
                'source_cos_phi': 'saisie — contrat de raccordement'}


def fichier(**remplacements):
    document = copy.deepcopy(EXPORT['exemple'])
    document.update(remplacements)
    return document


def refus(document):
    with unittest.TestCase().assertRaises(ImportProjetRefuse) as capture:
        _analyser_projet(document)
    return capture.exception


def saisies(**blocs):
    document = fichier()
    document['saisies'].update(blocs)
    return document


# ═══════════════════════════════════════════════════════════════════════════
# 1. SANS BASE — le registre, les gestes, les refus nommés, les formats
# ═══════════════════════════════════════════════════════════════════════════

class RegistreDesSaisiesTest(unittest.TestCase):
    def test_champs_entree_inclus_dans_portables_ou_non_portables(self):
        # Une clé ajoutée demain à CHAMPS_ENTREE ne peut pas être oubliée en
        # silence : elle est portable, ou nommée non portable.
        self.assertLessEqual(set(CHAMPS_ENTREE),
                             set(CLES_ENTREE_PORTABLES)
                             | set(CLES_NON_PORTABLES))
        for cle in ('transformateur', 'regime', 'batterie', 'hors_reseau'):
            self.assertIn(cle, CLES_ENTREE_PORTABLES)
        self.assertNotIn('derogations', CLES_ENTREE_PORTABLES)

    def test_derogations_jamais_exportees(self):
        pivot = SimpleNamespace(
            pk=1, company=None, client_id=None, lead_id=None, devis_id=None,
            titre='T', roof_layout=None, layout_hash='', version_moteur='',
            pertes=[], resultat={
                'entree_electrique': {
                    'dc_m': 3.0, 'module_produit': 7,
                    'derogations': [{'code': 'X', 'motif': 'm'}]},
                'journal_derogations': [{'code': 'X', 'auteur': 'A'}],
            })
        document = ep.document_de_projet(
            pivot, site={'adresse': None, 'ville': None, 'pin': None,
                         'outline': None, 'source': None}, equipements={})
        self.assertEqual(document['format_version'], 3)
        bloc = document['saisies']
        self.assertEqual(bloc['entree_electrique'], {'dc_m': 3.0})
        self.assertEqual(bloc['produits_designes'],
                         {'module_produit': 7, 'onduleur_produit': None,
                          'optimiseur_produit': None})
        self.assertNotIn('derogations', json.dumps(bloc))
        self.assertNotIn('journal_derogations', json.dumps(document))
        # Réimportée, une dérogation glissée dans le fichier est REFUSÉE.
        geste = saisies(entree_electrique={'derogations': []})
        self.assertEqual(refus(geste).champ,
                         'saisies.entree_electrique.derogations')

    def test_saisie_invalide_refusee_au_chemin_saisies(self):
        cas = (
            (saisies(raccordement_saisie={'phases': 2}),
             'saisies.raccordement_saisie.phases'),
            (saisies(sld_edition={'libelles': {'champ': 12}}),
             'saisies.sld_edition.libelles.champ'),
            (saisies(sld_edition={'positions': {'champ': 'x'}}),
             'saisies.sld_edition.positions.champ'),
            (saisies(sld_edition={'couleurs': {}}),
             'saisies.sld_edition.couleurs'),
            (saisies(produits_designes={'module_produit': 'abc'}),
             'saisies.produits_designes.module_produit'),
            (saisies(entree_electrique={'inconnue': 1}),
             'saisies.entree_electrique.inconnue'),
            (saisies(entree_electrique=[1]), 'saisies.entree_electrique'),
            (saisies(autre={}), 'saisies.autre'),
            (fichier(saisies='x'), 'saisies'),
        )
        for document, chemin in cas:
            with self.subTest(chemin=chemin):
                self.assertEqual(refus(document).champ, chemin)

    def test_format_2_reste_importable(self):
        ancien = fichier(format_version=2)
        ancien.pop('saisies')
        plan = _analyser_projet(ancien)
        self.assertEqual(plan['saisies']['entree_electrique'], {})
        self.assertIsNone(plan['saisies']['raccordement_saisie'])
        # Un bloc ``saisies`` dans un fichier de format 2 n'est pas lu.
        plan = _analyser_projet(fichier(format_version=2))
        self.assertEqual(plan['saisies']['entree_electrique'], {})
        apercu = importer_projet(ancien, None, lead_id=1, apercu=True)
        self.assertEqual(apercu['format_version'], 2)
        self.assertNotIn(BLOC_PRODUITS_IGNORES,
                         [i['bloc'] for i in apercu['ignores']])

    def test_l_apercu_nomme_les_blocs_repris_et_les_produits_ignores(self):
        apercu = importer_projet(fichier(), None, lead_id=1, apercu=True)
        self.assertIn('saisies', apercu['repris'])
        ignore = apercu['ignores'][-1]
        self.assertEqual(ignore['bloc'], BLOC_PRODUITS_IGNORES)
        self.assertEqual(ignore['ids'], [4112, 901])
        self.assertIsNone(apercu['ouvrir'])


# ═══════════════════════════════════════════════════════════════════════════
# 2. EN BASE (CI) — l'aller-retour par les vrais écrivains
# ═══════════════════════════════════════════════════════════════════════════

class AllerRetourDesSaisiesTest(BaseConceptionReelle):
    """Conception réelle (module + onduleur en base), saisies réelles."""

    def setUp(self):
        super().setUp()
        from apps.calepinage.services.electrique import enregistrer_entree

        self._norme_francaise()
        enregistrer_entree(self.calepinage, copy.deepcopy(ENTREE))
        reponse = self.api.post(url_detail(self.calepinage.pk)
                                + 'raccordement/', RACCORDEMENT,
                                format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        reponse = self.api.post(url_schema(self.calepinage.pk),
                                {'libelles': {'champ': 'Champ PV'}},
                                format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.calepinage.refresh_from_db()

    def _exporter(self, calepinage):
        document = ep.document_de_projet(calepinage)
        return json.loads(ep._octets_de_projet(document))

    def test_aller_retour_export_import_export_restitue_les_saisies(self):
        from apps.calepinage.models import Calepinage

        premier = self._exporter(self.calepinage)
        bloc = premier['saisies']
        for cle, valeur in ENTREE.items():
            self.assertEqual(bloc['entree_electrique'][cle], valeur, cle)
        self.assertEqual(bloc['produits_designes']['module_produit'],
                         self.module.pk)
        self.assertEqual(bloc['raccordement_saisie']['phases'], 3)
        self.assertEqual(bloc['sld_edition']['libelles'],
                         {'champ': 'Champ PV'})

        resume = importer_projet(premier, self.company, user=self.user,
                                 lead_id=self.lead.pk)
        self.assertTrue(resume['ecrit'])
        self.assertIn('saisies', resume['repris'])
        self.assertNotIn(BLOC_PRODUITS_IGNORES,
                         [i['bloc'] for i in resume['ignores']])
        self.assertEqual(resume['ouvrir'],
                         '/calepinage/%d' % resume['calepinage'])
        copie = Calepinage.objects.get(pk=resume['calepinage'])

        second = self._exporter(copie)
        self.assertEqual(second['saisies'], premier['saisies'])

        lu = self.api.get(url_detail(copie.pk) + 'entree-electrique/')
        self.assertEqual(lu.status_code, 200, lu.data)
        self.assertEqual(lu.data['entree']['dc_m'], 25.0)
        self.assertEqual(lu.data['entree']['transformateur'], TRANSFORMATEUR)

    def test_produit_absent_de_la_societe_d_arrivee_est_ignore_et_nomme(self):
        from apps.calepinage.models import Calepinage
        from apps.crm.models import Client

        document = self._exporter(self.calepinage)
        client = Client.objects.create(company=self.autre, nom='Arrivée')
        resume = importer_projet(document, self.autre, client_id=client.pk)
        ignore = [i for i in resume['ignores']
                  if i['bloc'] == BLOC_PRODUITS_IGNORES]
        self.assertEqual(len(ignore), 1)
        self.assertEqual(ignore[0]['ids'],
                         [self.module.pk, self.onduleur.pk])
        copie = Calepinage.objects.get(pk=resume['calepinage'])
        self.assertEqual(copie.company_id, self.autre.pk)
        entree = copie.resultat['entree_electrique']
        for cle in ('module_produit', 'onduleur_produit'):
            self.assertNotIn(cle, entree)
        self.assertEqual(entree['dc_m'], 25.0)
        self.assertEqual(entree['regime'], 'TN')
        self.assertEqual(copie.resultat['sld_edition']['libelles'],
                         {'champ': 'Champ PV'})

    def test_saisie_invalide_au_reimport_n_ecrit_rien(self):
        from apps.calepinage.models import Calepinage

        document = self._exporter(self.calepinage)
        document['saisies']['entree_electrique']['dc_m'] = -1
        avant = Calepinage.objects.count()
        with self.assertRaises(ImportProjetRefuse) as capture:
            importer_projet(document, self.company, lead_id=self.lead.pk)
        self.assertEqual(capture.exception.champ,
                         'saisies.entree_electrique.dc_m')
        self.assertEqual(Calepinage.objects.count(), avant)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
