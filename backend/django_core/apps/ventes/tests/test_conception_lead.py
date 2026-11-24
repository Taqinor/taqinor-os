# -*- coding: utf-8 -*-
"""Le moteur unique (D-ACAL-97) — le résultat d'une conception rangé sur le lead.

Module neuf du paquet ``apps/ventes/conception/`` (conception :
``docs/audits/l5-calepinage/controles/C4-un-seul-moteur.md``, §4).

* ADEV129 — le CONTRAT ``contract_samples/conception_lead.json``, posé SEUL sur
  ``main`` avant le modèle, le moteur et la route (PACT10) : chaque clé du §4,
  la forme ACTUELLE des blocs d'étude du devis (jamais redéfinie ici : relue
  dans les contrats et le schéma existants), aucune clé d'achat ni de marge.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.ventes.tests.test_conception_lead"
"""
import json
from pathlib import Path

from django.test import SimpleTestCase

DOSSIER = Path(__file__).resolve().parents[1] / 'contract_samples'
CONTRAT = DOSSIER / 'conception_lead.json'

#: La sortie du moteur (§3) — aussi la réponse de l'aperçu, sans écriture.
CLES_RESULTAT = {
    'etat', 'refus', 'marche', 'option_retenue', 'valeurs', 'blocs',
    'suppositions', 'entrees_utilisees', 'empreinte', 'niveau_regles',
    'version_moteur',
}
#: Ce que la version RANGÉE ajoute (§4, §5).
CLES_RANGEES = {
    'declencheur', 'version', 'calcule_le', 'perimee', 'ecart_devis',
    'brouillons_a_mettre_a_jour',
}
CLES_VALEUR = {'valeur', 'unite', 'source'}
SOURCES_VALEUR = {'moteur', 'pose', 'impose', 'devis', 'defaut'}
SOURCES_ENTREE = {'lead', 'calepinage', 'reglage_societe', 'defaut'}
CLES_SUPPOSITION = {'code', 'champ', 'valeur', 'source', 'message'}
CLES_DECLENCHEUR = {'raison', 'champs', 'origine'}
CLES_CHAMP_MODIFIE = {'champ', 'avant', 'apres'}
ORIGINES = {'lead_entrees_modifiees', 'pose_enregistree', 'regles',
            'remplissage', 'manuel', 'filet'}
CLES_ECART = {'valeur', 'devis', 'conception', 'devis_ref',
              'reviser_possible', 'mise_a_jour_proposee'}
CLES_REFUS = {'code', 'champ', 'message'}
#: La table §2, par option (résidentiel, commercial, industriel).
VALEURS_SOLAIRES = {
    'nb_panneaux', 'puissance_kwc', 'module', 'onduleurs', 'nombre_onduleurs',
    'chaines', 'temperature_froid', 'tension_froid', 'ratio_dc_ac',
    'production_annuelle', 'production_mensuelle', 'autoconsommation',
    'couverture', 'economies_annuelles', 'payback', 'consommation_annuelle',
    'forme_horaire',
}
#: La table §2 en agricole (la pompe remplace taille / matériel / bilan).
VALEURS_POMPAGE = {'nb_panneaux', 'puissance_kwc', 'pompe', 'variateur', 'm3_jour'}
CLES_CORPS_APERCU = {'lead', 'calepinage', 'entrees', 'imposes'}
CLES_IMPOSES = {'nb_panneaux', 'module_id', 'onduleur_id', 'nombre_onduleurs',
                'batterie'}


def _lire(nom):
    return json.loads((DOSSIER / nom).read_text(encoding='utf-8'))


def _cles_interdites(noeud, chemin='$'):
    """Chemins de toute clé d'achat ou de marge, à toute profondeur."""
    trouves = []
    if isinstance(noeud, dict):
        for cle, valeur in noeud.items():
            if 'prix_achat' in cle or cle.startswith('marge'):
                trouves.append(f'{chemin}.{cle}')
            trouves += _cles_interdites(valeur, f'{chemin}.{cle}')
    elif isinstance(noeud, list):
        for i, valeur in enumerate(noeud):
            trouves += _cles_interdites(valeur, f'{chemin}[{i}]')
    return trouves


class ContratConceptionLeadTests(SimpleTestCase):
    """ADEV129 — l'échantillon porte chaque clé du §4 et aucune clé interdite."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.doc = json.loads(CONTRAT.read_text(encoding='utf-8'))
        cls.exemples = {k: v for k, v in cls.doc.items()
                        if k.startswith('exemple')}

    def test_route_et_exemples(self):
        self.assertEqual(self.doc['endpoint'],
                         'GET /api/django/ventes/conception/<int:lead_id>/')
        self.assertIn('exemple', self.exemples)
        self.assertGreaterEqual(len(self.exemples), 3)

    def test_chaque_cle_du_resultat_range(self):
        for nom, ex in self.exemples.items():
            with self.subTest(exemple=nom):
                self.assertEqual(set(ex), CLES_RESULTAT | CLES_RANGEES)
                self.assertIn(ex['etat'], {'complet', 'refus'})
                self.assertEqual(len(ex['empreinte']), 64)
                int(ex['empreinte'], 16)
                self.assertIsInstance(ex['niveau_regles'], int)
                self.assertIsInstance(ex['version'], int)
                self.assertIsInstance(ex['perimee'], bool)
                if ex['etat'] == 'refus':
                    self.assertEqual(set(ex['refus']), CLES_REFUS)
                    self.assertEqual(ex['valeurs'], {})
                else:
                    self.assertIsNone(ex['refus'])
                    self.assertIn(ex['option_retenue'], ex['valeurs'])

    def test_valeurs_par_option(self):
        for nom, ex in self.exemples.items():
            attendues = (VALEURS_POMPAGE if ex['marche'] == 'agricole'
                         else VALEURS_SOLAIRES)
            for option, valeurs in ex['valeurs'].items():
                with self.subTest(exemple=nom, option=option):
                    self.assertIn(option, {'sans', 'avec'})
                    self.assertEqual(set(valeurs), attendues)
                    for cle, valeur in valeurs.items():
                        self.assertEqual(set(valeur), CLES_VALEUR, cle)
                        self.assertIn(valeur['source'], SOURCES_VALEUR, cle)

    def test_suppositions_entrees_et_declencheur(self):
        for nom, ex in self.exemples.items():
            with self.subTest(exemple=nom):
                for sup in ex['suppositions']:
                    self.assertEqual(set(sup), CLES_SUPPOSITION)
                for champ, entree in ex['entrees_utilisees'].items():
                    self.assertEqual(set(entree), {'valeur', 'source'}, champ)
                    self.assertIn(entree['source'], SOURCES_ENTREE, champ)
                dec = ex['declencheur']
                self.assertEqual(set(dec), CLES_DECLENCHEUR)
                self.assertIn(dec['origine'], ORIGINES)
                for modif in dec['champs']:
                    self.assertEqual(set(modif), CLES_CHAMP_MODIFIE)
                for ecart in ex['ecart_devis']:
                    self.assertEqual(set(ecart), CLES_ECART)
                    self.assertIn(ecart['valeur'], VALEURS_SOLAIRES | VALEURS_POMPAGE)
                for brouillon in ex['brouillons_a_mettre_a_jour']:
                    self.assertEqual(set(brouillon), {'devis', 'reference', 'motif'})
        self.assertTrue(self.doc['exemple']['ecart_devis'])
        self.assertTrue(self.doc['exemple']['declencheur']['champs'])

    def test_apercu_sans_ecriture(self):
        apercu = self.doc['apercu']
        self.assertEqual(apercu['endpoint'],
                         'POST /api/django/ventes/conception/apercu/')
        self.assertEqual(set(apercu['corps']), CLES_CORPS_APERCU)
        self.assertEqual(set(apercu['corps']['imposes']), CLES_IMPOSES)
        self.assertEqual(set(apercu['reponse']), CLES_RESULTAT)
        # Une valeur tapée et non enregistrée n'est jamais dite « du lead ».
        for champ, entree in apercu['reponse']['entrees_utilisees'].items():
            self.assertIn(entree['source'], SOURCES_ENTREE | {'saisie'}, champ)

    def test_blocs_forme_actuelle_du_devis(self):
        """Les blocs sont ceux que le devis porte AUJOURD'HUI dans
        ``etude_params`` : clés dérivées du schéma, sous-clés relues dans les
        contrats existants (jamais une seconde définition)."""
        from apps.ventes.domain import etude_schema as es

        moteurs = {es.MOTEUR_HORAIRE, es.MOTEUR_DIMENSIONNEMENT, es.MOTEUR_CI,
                   es.MOTEUR_POMPAGE}
        horaire = _lire('etude_horaire.json')['exemple']
        ci = _lire('etude_ci_preview.json')['cles_etude_params_ci_v2']
        pompage = _lire('etude_pompage_preview.json')['cles_etude_params_v2']
        sous_cles = {
            'etude_horaire': set(horaire['etude']) | {'_empreinte_entrees'},
            'etude_horaire_sans': set(horaire['etude']) | {'_empreinte_entrees'},
            'dimensionnement': (set(horaire['dimensionnement'])
                                | {'_empreinte_entrees'}),
            'etude_ci': set(next(d['contient'] for d in ci['derivees']
                                 if d['cle'] == 'etude_ci')),
        }
        derivees_pompage = {d['cle'] for d in pompage['derivees']}
        vus = set()
        for nom, ex in [*self.exemples.items(),
                        ('apercu', self.doc['apercu']['reponse'])]:
            for cle, bloc in ex['blocs'].items():
                with self.subTest(exemple=nom, bloc=cle):
                    regle = es.SCHEMA.get(cle)
                    self.assertIsNotNone(regle, cle)
                    self.assertEqual(regle['nature'], es.DERIVEE)
                    self.assertIn(regle['proprietaire'], moteurs)
                    if regle['proprietaire'] == es.MOTEUR_POMPAGE:
                        self.assertTrue(cle in derivees_pompage
                                        or not isinstance(bloc, dict), cle)
                    if cle in sous_cles:
                        self.assertLessEqual(set(bloc), sous_cles[cle])
                    vus.add(cle)
        self.assertLessEqual({'etude_horaire', 'dimensionnement', 'etude_ci'}, vus)

    def test_aucune_cle_d_achat_ni_de_marge(self):
        self.assertEqual(_cles_interdites(self.doc), [])
        # Le parcours détecte bien une clé interdite enfouie.
        self.assertEqual(_cles_interdites({'a': [{'b': {'prix_achat_ht': 1}}]}),
                         ['$.a[0].b.prix_achat_ht'])
