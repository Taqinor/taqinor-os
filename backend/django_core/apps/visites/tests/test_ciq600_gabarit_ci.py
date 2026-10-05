"""CIQ600 — gabarit de visite ``ci`` (socle commun + BT) pour un lead
commercial ou industriel (D-CIQ-5).

Contrat partagé : ``apps/visites/contract_samples/visite_terrain.json``
(``gabarit_ci``, ``exemple_ci``). Aucun seuil, aucun verdict.
"""
import datetime
import json
from pathlib import Path

from django.test import SimpleTestCase
from django.utils import timezone

from apps.crm.models import Lead
from apps.visites import services, visite_checklist as checklist
from apps.visites.models import VisiteTerrain
from apps.visites.tests.test_visite_terrain import VisiteTerrainBase

CONTRAT = json.loads(
    (Path(__file__).resolve().parent.parent / 'contract_samples'
     / 'visite_terrain.json').read_text(encoding='utf-8'))
GABARIT_CONTRAT = CONTRAT['gabarit_ci']
EXEMPLE = CONTRAT['exemple_ci']

#: Catégories du socle commun servies par CIQ600 (les zones de toiture
#: arrivent avec CIQ602).
SOCLE = ['tableau_general', 'comptage', 'cheminement', 'acces_securite',
         'autres_autorisations', 'general']

PHOTOS_REQUISES = ['tgbt_ouvert', 'comptage_plaque', 'acces_toiture',
                   'general_facade']

MESURES_CI = {
    'tableau_general': {'calibre_a': 250, 'depart_disponible': True},
    'comptage': {'type_compteur': 'électronique triphasé',
                 'niveau_tension_constate': 'bt'},
    'cheminement': {'trajets': [
        {'libelle': 'toiture → local onduleurs', 'longueur_dc_m': 45},
        {'libelle': 'local onduleurs → TGBT', 'longueur_ac_m': 30}]},
}


class ChecklistCiDuContrat(SimpleTestCase):
    def test_les_categories_du_socle_sont_celles_du_contrat(self):
        cats = [c['categorie'] for c in checklist.categories('ci')]
        self.assertEqual(cats, [c for c in GABARIT_CONTRAT if c in SOCLE])

    def test_mesures_requis_et_libelles_du_contrat(self):
        for cat in SOCLE:
            bloc = GABARIT_CONTRAT[cat]
            declarees = {m['code']: m for m in checklist.mesures(cat, 'ci')}
            self.assertEqual(sorted(declarees), sorted(bloc['mesures']), cat)
            for code, attendu in bloc['mesures'].items():
                self.assertEqual(declarees[code]['requis'], attendu['requis'],
                                 f'{cat}.{code}')
                self.assertEqual(declarees[code]['libelle'],
                                 attendu['libelle'], f'{cat}.{code}')

    def test_photos_requises_ou_facultatives_du_contrat(self):
        for cat in SOCLE:
            attendues = GABARIT_CONTRAT[cat]['photos']
            declarees = {s['code']: s['requis']
                         for s in next(c for c in checklist.categories('ci')
                                       if c['categorie'] == cat)['slots']}
            self.assertEqual(
                declarees,
                {code: (v == 'requise') for code, v in attendues.items()},
                cat)

    def test_aucune_mesure_residentielle_dans_le_ci(self):
        codes = {m['code'] for c in checklist.categories('ci')
                 for m in c['mesures']}
        for residentiel in ('toit_plat', 'largeur_mur_cm',
                            'calibre_disjoncteur_a', 'longueur_estimee_m'):
            self.assertNotIn(residentiel, codes)

    def test_le_residentiel_reste_la_checklist_historique(self):
        self.assertIs(checklist.categories('toiture'), checklist.CATEGORIES)
        self.assertIs(checklist.categories(), checklist.CATEGORIES)

    def test_le_niveau_ne_change_pas_le_socle_bt(self):
        for niveau in (None, 'bt', 'inconnu'):
            self.assertIs(checklist.categories('ci', niveau),
                          checklist.categories('ci'))

    def test_le_gabarit_suit_le_type_du_lead(self):
        for pro in ('commercial', 'industriel'):
            self.assertEqual(services.gabarit_pour_lead(
                Lead(nom='x', type_installation=pro)), 'ci')
        self.assertEqual(services.gabarit_pour_lead(
            Lead(nom='x', type_installation='residentiel')), 'toiture')


class VisiteCiTests(VisiteTerrainBase):
    def setUp(self):
        super().setUp()
        self.lead.type_installation = 'commercial'
        self.lead.save(update_fields=['type_installation'])

    def _detail(self, visite_id):
        return self.api.get(f'/api/django/visites/visites/{visite_id}/').data

    def _mesures(self, visite_id, categorie, valeurs):
        return self.api.patch(
            f'/api/django/visites/visites/{visite_id}/mesures/',
            {'categorie': categorie, 'valeurs': valeurs}, format='json')

    def _terminer(self, visite_id):
        return self.api.post(
            f'/api/django/visites/visites/{visite_id}/terminer/', {},
            format='json')

    def _remplir(self, visite_id, avec_cheminement=True):
        for slot in PHOTOS_REQUISES:
            resp = self.poster_photo(visite_id, slot, nom=f'{slot}.png')
            self.assertEqual(resp.status_code, 200, resp.data)
        for categorie, valeurs in MESURES_CI.items():
            if categorie == 'cheminement' and not avec_cheminement:
                continue
            resp = self._mesures(visite_id, categorie, valeurs)
            self.assertEqual(resp.status_code, 200, resp.data)

    def test_la_creation_pose_le_gabarit_ci(self):
        visite_id = self.creer_visite()
        detail = self._detail(visite_id)
        self.assertEqual(detail['gabarit'], 'ci')
        self.assertIsNone(detail['photo_toit'])
        self.assertEqual([b['categorie'] for b in detail['checklist']], SOCLE)

    def test_une_visite_ci_se_termine_sans_mesure_residentielle(self):
        visite_id = self.creer_visite()
        self._remplir(visite_id)
        resp = self._terminer(visite_id)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['statut'], VisiteTerrain.Statut.TERMINEE)
        self.assertTrue(resp.data['completude']['complet'])

    def test_terminer_est_refuse_sans_longueurs_de_cheminement(self):
        visite_id = self.creer_visite()
        self._remplir(visite_id, avec_cheminement=False)
        resp = self._terminer(visite_id)
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('trajets',
                      {m['code'] for m in resp.data['manquants']})
        # Des trajets sans longueur AC : l'AC reste requise.
        self._mesures(visite_id, 'cheminement', {'trajets': [
            {'libelle': 'a', 'longueur_dc_m': 45}]})
        resp = self._terminer(visite_id)
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertEqual(
            {m['code'] for m in resp.data['manquants']},
            {'trajets.longueur_ac_m'})

    def test_aucun_champ_de_toit_residentiel_n_est_exige(self):
        visite_id = self.creer_visite()
        resp = self._terminer(visite_id)
        codes = {m['code'] for m in resp.data['manquants']}
        for residentiel in ('toit_plat', 'pente_deg', 'largeur_mur_cm',
                            'toiture_vue_generale', 'onduleur_mur'):
            self.assertNotIn(residentiel, codes)

    def test_un_slot_residentiel_est_refuse_sur_une_visite_ci(self):
        visite_id = self.creer_visite()
        resp = self.poster_photo(visite_id, 'onduleur_mur')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('slot_code', resp.data['erreurs'])

    def test_une_liste_invalide_est_refusee_en_nommant_le_champ(self):
        visite_id = self.creer_visite()
        resp = self._mesures(visite_id, 'cheminement', {'trajets': 'abc'})
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('trajets', str(resp.data))
        resp = self._mesures(visite_id, 'cheminement', {'trajets': [
            {'libelle': 'x', 'longueur_dc_m': 'beaucoup'}]})
        self.assertEqual(resp.status_code, 400, resp.data)
        resp = self._mesures(visite_id, 'cheminement', {'trajets': [
            {'libelle': 'x', 'longueur_dc_m': -3}]})
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_l_agregat_ci_a_la_forme_de_l_exemple_du_contrat(self):
        visite_id = self.creer_visite()
        detail = self._detail(visite_id)
        self.assertEqual(sorted(detail), sorted(EXEMPLE))
        self.assertEqual(detail['gabarit'], EXEMPLE['gabarit'])
        for cat in SOCLE:
            self.assertEqual(
                sorted(detail['mesures'][cat]),
                sorted(EXEMPLE['mesures'][cat]), cat)
        # Les blocs de checklist exposent les mêmes clés de slot.
        attendu = sorted(EXEMPLE['checklist'][0]['slots'][0])
        for bloc in detail['checklist']:
            for slot in bloc['slots']:
                self.assertEqual(sorted(slot), attendu)

    def test_les_trajets_de_l_exemple_sont_acceptes_tels_quels(self):
        visite_id = self.creer_visite()
        trajets = EXEMPLE['mesures']['cheminement']['trajets']
        resp = self._mesures(visite_id, 'cheminement', {'trajets': trajets})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(self._detail(visite_id)['mesures']['cheminement'],
                         {'trajets': trajets})

    def test_le_gabarit_est_fige_hors_brouillon(self):
        demain = timezone.localdate() + datetime.timedelta(days=1)
        visite, erreurs = services.planifier_visite(
            self.lead, self.commercial, demain)
        self.assertEqual(erreurs, {})
        self.assertEqual(visite.gabarit, 'ci')
        # Brouillon : le type change → le gabarit suit.
        self.lead.type_installation = 'agricole'
        self.lead.save(update_fields=['type_installation'])
        self.assertTrue(services.recaler_gabarit(visite))
        self.assertEqual(visite.gabarit, 'point_eau')
        self.lead.type_installation = 'industriel'
        self.lead.save(update_fields=['type_installation'])
        self.assertTrue(services.recaler_gabarit(visite))
        self.assertEqual(visite.gabarit, 'ci')
        # Hors brouillon : figé, quoi que dise le lead.
        visite.statut = VisiteTerrain.Statut.EN_COURS
        self.lead.type_installation = 'residentiel'
        self.lead.save(update_fields=['type_installation'])
        self.assertFalse(services.recaler_gabarit(visite))
        self.assertEqual(visite.gabarit, 'ci')

    def test_un_lead_residentiel_garde_le_gabarit_toiture(self):
        self.lead.type_installation = 'residentiel'
        self.lead.save(update_fields=['type_installation'])
        visite_id = self.creer_visite()
        detail = self._detail(visite_id)
        self.assertEqual(detail['gabarit'], 'toiture')
        self.assertEqual(
            [b['categorie'] for b in detail['checklist']],
            [c['categorie'] for c in checklist.CATEGORIES])
        self.assertNotIn('trajets', detail['mesures'].get('cheminement', {}))
