"""AGR412 — gabarit « relevé du point d'eau » qui REMPLACE la checklist toiture
d'un lead agricole (D-AGR-4).

Contrat partagé : ``apps/visites/contract_samples/visite_terrain.json``
(``gabarit_point_eau``, ``exemple_point_eau`` ; l'``exemple`` toiture gagne la
seule clé ``gabarit``). Aucun seuil, aucun verdict : le module montre, le
bureau d'études juge.
"""
import datetime
import json
from pathlib import Path

from django.test import SimpleTestCase
from django.utils import timezone

from apps.crm.models import Lead
from apps.visites import selectors, services, visite_checklist as checklist
from apps.visites.models import VisiteTerrain
from apps.visites.tests.test_visite_terrain import VisiteTerrainBase

CONTRAT = json.loads(
    (Path(__file__).resolve().parent.parent / 'contract_samples'
     / 'visite_terrain.json').read_text(encoding='utf-8'))
EXEMPLE = CONTRAT['exemple_point_eau']

#: Les mesures de l'exemple du contrat, à saisir telles quelles.
MESURES_EXEMPLE = {
    cat: {code: val for code, val in valeurs.items() if val is not None}
    for cat, valeurs in EXEMPLE['mesures'].items()
}


class ChecklistPointEauDuContrat(SimpleTestCase):
    def test_les_categories_sont_celles_du_contrat(self):
        cats = [c['categorie'] for c in checklist.categories('point_eau')]
        self.assertEqual(cats, list(CONTRAT['gabarit_point_eau']))
        self.assertEqual(cats,
                         [b['categorie'] for b in EXEMPLE['checklist']])

    def test_mesures_et_requis_du_contrat(self):
        for cat, bloc in CONTRAT['gabarit_point_eau'].items():
            declarees = {m['code']: m for m in checklist.mesures(
                cat, 'point_eau')}
            self.assertEqual(sorted(declarees), sorted(bloc['mesures']), cat)
            for code, attendu in bloc['mesures'].items():
                self.assertEqual(declarees[code]['requis'], attendu['requis'],
                                 f'{cat}.{code}')
                self.assertEqual(declarees[code]['libelle'],
                                 attendu['libelle'], f'{cat}.{code}')
                self.assertEqual(declarees[code].get('sauf_si'),
                                 attendu.get('sauf_si'), f'{cat}.{code}')

    def test_aucune_mesure_de_toit_dans_le_point_eau(self):
        codes = {m['code'] for c in checklist.categories('point_eau')
                 for m in c['mesures']}
        for toit in ('longueur_m', 'pente_deg', 'orientation',
                     'calibre_disjoncteur_a', 'largeur_mur_cm'):
            self.assertNotIn(toit, codes)

    def test_le_toiture_reste_la_checklist_historique(self):
        self.assertIs(checklist.categories(), checklist.CATEGORIES)
        self.assertIs(checklist.categories('toiture'), checklist.CATEGORIES)

    def test_niveau_requis_sauf_non_mesurable(self):
        niveau = checklist.mesure('point_eau', 'niveau_statique_m',
                                  'point_eau')
        self.assertTrue(checklist.mesure_requise(niveau, {}))
        self.assertFalse(checklist.mesure_requise(
            niveau, {'niveau_non_mesurable': True}))

    def test_le_gabarit_suit_le_type_du_lead(self):
        self.assertEqual(services.gabarit_pour_lead(
            Lead(nom='x', type_installation='agricole')), 'point_eau')
        for autre in (None, '', 'residentiel', 'commercial', 'industriel'):
            self.assertEqual(services.gabarit_pour_lead(
                Lead(nom='x', type_installation=autre)), 'toiture')


class VisitePointEauTests(VisiteTerrainBase):
    def setUp(self):
        super().setUp()
        self.lead.type_installation = 'agricole'
        self.lead.save(update_fields=['type_installation'])

    def _detail(self, visite_id):
        return self.api.get(f'/api/django/visites/visites/{visite_id}/').data

    def _mesures(self, visite_id, categorie, valeurs):
        return self.api.patch(
            f'/api/django/visites/visites/{visite_id}/mesures/',
            {'categorie': categorie, 'valeurs': valeurs}, format='json')

    def _remplir_point_eau(self, visite_id, sans_niveau=False):
        for slot, combien in (('point_eau_tete_forage', 1),
                              ('site_pv_emplacement', 2),
                              ('general_exploitation', 1)):
            for index in range(combien):
                resp = self.poster_photo(visite_id, slot,
                                         nom=f'{slot}-{index}.png')
                self.assertEqual(resp.status_code, 200, resp.data)
        valeurs = {
            'point_eau': {'source_eau': 'forage', 'niveau_statique_m': 32,
                          'debit_mesure_m3h': 34},
            'pompe_existante': {'pompe_presente': False},
            'electricite': {'electricite_sur_place': 'aucune'},
            'site_pv': {'distance_forage_champ_m': 25},
            'administratif': {'autorisation_prelevement': 'en_cours',
                              'compteur_eau': False},
        }
        if sans_niveau:
            valeurs['point_eau'].pop('niveau_statique_m')
            valeurs['point_eau']['niveau_non_mesurable'] = True
        for categorie, champs in valeurs.items():
            resp = self._mesures(visite_id, categorie, champs)
            self.assertEqual(resp.status_code, 200, resp.data)

    def test_la_creation_pose_le_gabarit_point_eau(self):
        visite_id = self.creer_visite()
        detail = self._detail(visite_id)
        self.assertEqual(detail['gabarit'], 'point_eau')
        self.assertIsNone(detail['photo_toit'])
        self.assertEqual([b['categorie'] for b in detail['checklist']],
                         [b['categorie'] for b in EXEMPLE['checklist']])

    def test_une_visite_point_eau_se_termine_sans_mesure_de_toit(self):
        visite_id = self.creer_visite()
        self._remplir_point_eau(visite_id)
        resp = self.api.post(
            f'/api/django/visites/visites/{visite_id}/terminer/', {},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['statut'], VisiteTerrain.Statut.TERMINEE)

    def test_le_niveau_est_requis_sauf_non_mesurable(self):
        visite_id = self.creer_visite()
        resp = self._mesures(visite_id, 'point_eau', {'source_eau': 'puits'})
        codes = {m['code'] for m in resp.data['completude']['manquants']}
        self.assertIn('niveau_statique_m', codes)
        resp = self._mesures(visite_id, 'point_eau',
                             {'niveau_non_mesurable': True})
        codes = {m['code'] for m in resp.data['completude']['manquants']}
        self.assertNotIn('niveau_statique_m', codes)

    def test_un_slot_de_toit_est_refuse_sur_un_point_eau(self):
        visite_id = self.creer_visite()
        resp = self.poster_photo(visite_id, 'toiture_vue_generale')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('slot_code', resp.data['erreurs'])

    def test_l_agregat_egale_l_exemple_point_eau_du_contrat(self):
        visite_id = self.creer_visite()
        self.assertEqual(
            self.poster_photo(visite_id, 'point_eau_tete_forage').status_code,
            200)
        for categorie, valeurs in MESURES_EXEMPLE.items():
            resp = self._mesures(visite_id, categorie, valeurs)
            self.assertEqual(resp.status_code, 200, resp.data)
        detail = self._detail(visite_id)
        self.assertEqual(sorted(detail), sorted(EXEMPLE))
        self.assertEqual(detail['gabarit'], EXEMPLE['gabarit'])
        # Une saisie texte VIDE (« ») est stockée « non relevée » (None) par
        # la règle VT2 existante : c'est la seule normalisation appliquée.
        attendues = {
            cat: {code: (None if val == '' else val)
                  for code, val in valeurs.items()}
            for cat, valeurs in EXEMPLE['mesures'].items()}
        self.assertEqual(detail['mesures'], attendues)
        self.assertEqual(detail['completude'], EXEMPLE['completude'])
        for bloc, attendu in zip(detail['checklist'], EXEMPLE['checklist']):
            sans_photos = [{k: v for k, v in s.items() if k != 'photos'}
                           for s in bloc['slots']]
            attendus = [{k: v for k, v in s.items() if k != 'photos'}
                        for s in attendu['slots']]
            self.assertEqual(sans_photos, attendus, bloc['categorie'])

    def test_le_recap_point_eau_n_ecrit_que_les_valeurs_saisies(self):
        visite = VisiteTerrain.objects.create(
            company=self.company, lead=self.lead, gabarit='point_eau',
            mesures={'point_eau': {'source_eau': 'forage',
                                   'niveau_statique_m': 32}})
        recap = selectors.recap_visite_terrain(visite)
        self.assertIn('niveau statique 32 m', recap)
        self.assertNotIn('débit', recap)
        self.assertNotIn('pente', recap)

    def test_le_gabarit_suit_le_segment_tant_que_brouillon_et_plus_apres(self):
        demain = timezone.localdate() + datetime.timedelta(days=1)
        residentiel = Lead.objects.create(
            company=self.company, nom='Maison', type_installation='residentiel')
        visite, erreurs = services.planifier_visite(
            residentiel, self.commercial, demain)
        self.assertEqual(erreurs, {})
        self.assertEqual(visite.gabarit, 'toiture')
        residentiel.type_installation = 'agricole'
        residentiel.save(update_fields=['type_installation'])
        visite, _ = services.planifier_visite(
            residentiel, self.commercial,
            demain + datetime.timedelta(days=1), replanifier=True)
        visite.refresh_from_db()
        self.assertEqual(visite.gabarit, 'point_eau')
        # Une fois commencée, la visite garde son gabarit.
        services.marquer_en_cours(visite)
        residentiel.type_installation = 'residentiel'
        residentiel.save(update_fields=['type_installation'])
        services.planifier_visite(
            residentiel, self.commercial,
            demain + datetime.timedelta(days=2), replanifier=True)
        visite.refresh_from_db()
        self.assertEqual(visite.gabarit, 'point_eau')


class VisiteToitureInchangeeTests(VisiteTerrainBase):
    def test_une_visite_toiture_garde_sa_checklist_et_le_contrat(self):
        visite_id = self.creer_visite()
        detail = self.api.get(f'/api/django/visites/visites/{visite_id}/').data
        self.assertEqual(detail['gabarit'], 'toiture')
        self.assertEqual(sorted(detail), sorted(CONTRAT['exemple']))
        self.assertIsNotNone(detail['photo_toit'])
        self.assertEqual([b['categorie'] for b in detail['checklist']],
                         [b['categorie'] for b in CONTRAT['exemple']['checklist']])
