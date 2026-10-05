"""CIQ602 — zones de toiture répétables du gabarit ci (structure, étanchéité,
accès, drapeau fibrociment, charge admissible DÉCLARÉE avec sa pièce).

Contrat : ``visite_terrain.json`` → ``gabarit_ci.toiture_ci`` et
``exemple_ci.mesures.toiture_ci``. Aucun verdict : la charge n'est jamais
jugée « suffisante ».
"""
import json
import re
from pathlib import Path

from django.test import SimpleTestCase

from apps.visites import selectors, visite_checklist as checklist
from apps.visites.models import VisiteTerrain
from apps.visites.tests.test_ciq600_gabarit_ci import (
    MESURES_CI, PHOTOS_REQUISES, ZONE_COMPLETE)
from apps.visites.tests.test_visite_terrain import VisiteTerrainBase

CONTRAT = json.loads(
    (Path(__file__).resolve().parent.parent / 'contract_samples'
     / 'visite_terrain.json').read_text(encoding='utf-8'))
ZONE_EXEMPLE = CONTRAT['exemple_ci']['mesures']['toiture_ci'][
    'zones_toiture'][0]
FORME_CONTRAT = CONTRAT['gabarit_ci']['toiture_ci']['mesures'][
    'zones_toiture']['forme']


class ZonesDuContrat(SimpleTestCase):
    def _zones(self):
        return checklist.mesure('toiture_ci', 'zones_toiture', 'ci')

    def test_la_forme_d_une_zone_est_celle_du_contrat(self):
        codes = ['id'] + [s['code'] for s in self._zones()['forme']]
        # ``id`` est posé par le serveur ; tous les autres champs du contrat.
        self.assertEqual(sorted(set(FORME_CONTRAT) - {'id'}),
                         sorted(codes[1:]))
        etancheite = next(s for s in self._zones()['forme']
                          if s['code'] == 'etancheite')
        self.assertEqual(sorted(s['code'] for s in etancheite['forme']),
                         sorted(FORME_CONTRAT['etancheite']))

    def test_aucune_valeur_numerique_dans_les_libelles_de_toiture(self):
        textes = []
        cat = checklist.categorie('toiture_ci', 'ci')
        for slot in cat['slots']:
            textes += [slot['libelle'], slot['guide']]
        zones = self._zones()
        textes.append(zones['libelle'])
        for sous in zones['forme']:
            textes.append(sous['libelle'])
            for sub in sous.get('forme', []):
                textes.append(sub['libelle'])
        for texte in textes:
            self.assertIsNone(re.search(r'[0-9]', texte), texte)

    def test_la_liste_est_repetable_et_requise(self):
        self.assertEqual(self._zones()['nature'], checklist.LISTE)
        self.assertTrue(self._zones()['requis'])
        self.assertEqual(checklist.liste_manquants(self._zones(), []),
                         [('zones_toiture',
                           'Zones de toiture (une par pan / bâtiment)')])

    def test_la_charge_n_a_aucun_seuil(self):
        # La checklist ne déclare QUE des champs de saisie : ni seuil ni verdict.
        for sous in self._zones()['forme']:
            self.assertNotIn('seuil', sous)
            self.assertNotIn('max', sous)


class VisiteZonesTests(VisiteTerrainBase):
    def setUp(self):
        super().setUp()
        self.lead.type_installation = 'industriel'
        self.lead.save(update_fields=['type_installation'])

    def _mesures(self, visite_id, categorie, valeurs):
        return self.api.patch(
            f'/api/django/visites/visites/{visite_id}/mesures/',
            {'categorie': categorie, 'valeurs': valeurs}, format='json')

    def _terminer(self, visite_id):
        return self.api.post(
            f'/api/django/visites/visites/{visite_id}/terminer/', {},
            format='json')

    def _visite_prete(self, zones):
        """Une visite ci complète, avec ``zones`` comme zones de toiture."""
        visite_id = self.creer_visite()
        for slot, combien in PHOTOS_REQUISES:
            for index in range(combien):
                self.assertEqual(
                    self.poster_photo(visite_id, slot,
                                      nom=f'{slot}-{index}.png').status_code,
                    200)
        for categorie, valeurs in MESURES_CI.items():
            if categorie == 'toiture_ci':
                valeurs = {'zones_toiture': zones}
            resp = self._mesures(visite_id, categorie, valeurs)
            self.assertEqual(resp.status_code, 200, resp.data)
        return visite_id

    def test_deux_zones_completes_laissent_terminer(self):
        zone_b = dict(ZONE_COMPLETE, libelle='Entrepôt sud', batiment='B',
                      surface_utile_m2=300, longueur_m=None, largeur_m=None)
        visite_id = self._visite_prete([ZONE_COMPLETE, zone_b])
        resp = self._terminer(visite_id)
        self.assertEqual(resp.status_code, 200, resp.data)
        zones = resp.data['mesures']['toiture_ci']['zones_toiture']
        self.assertEqual([z['id'] for z in zones], ['z1', 'z2'])

    def test_une_zone_incomplete_bloque_terminer_en_la_nommant(self):
        incomplete = {'libelle': 'Hangar est', 'longueur_m': 20,
                      'largeur_m': 10, 'couverture': 'bac_acier'}
        visite_id = self._visite_prete([ZONE_COMPLETE, incomplete])
        resp = self._terminer(visite_id)
        self.assertEqual(resp.status_code, 400, resp.data)
        manquants = resp.data['manquants']
        self.assertEqual(
            {m['code'] for m in manquants},
            {'zones_toiture[z2].pente_deg', 'zones_toiture[z2].orientation',
             'zones_toiture[z2].structure'})
        for manquant in manquants:
            self.assertIn('Hangar est', manquant['libelle'])
        # La zone complète n'apparaît nulle part dans les manquants.
        self.assertFalse(any('Atelier nord' in m['libelle']
                             for m in manquants))

    def test_il_faut_une_surface_ou_longueur_et_largeur(self):
        sans_surface = dict(ZONE_COMPLETE, longueur_m=None)
        visite_id = self._visite_prete([sans_surface])
        resp = self._terminer(visite_id)
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertEqual({m['code'] for m in resp.data['manquants']},
                         {'zones_toiture[z1].surface_utile_m2'})

    def test_aucune_zone_bloque_terminer(self):
        visite_id = self._visite_prete([])
        resp = self._terminer(visite_id)
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('zones_toiture',
                      {m['code'] for m in resp.data['manquants']})

    def test_le_fibrociment_pose_le_drapeau_dans_le_recap(self):
        zone = dict(ZONE_COMPLETE, couverture='fibrociment')
        visite_id = self._visite_prete([zone])
        detail = self.api.get(
            f'/api/django/visites/visites/{visite_id}/').data
        stockee = detail['mesures']['toiture_ci']['zones_toiture'][0]
        # Le drapeau est posé par le serveur, même non coché par le technicien.
        self.assertIs(stockee['fibrociment'], True)
        visite = VisiteTerrain.objects.get(pk=visite_id)
        recap = selectors.recap_visite_terrain(visite)
        self.assertIn('amiante possible — diagnostic requis', recap)
        self.assertIn('Atelier nord', recap)

    def test_sans_fibrociment_pas_de_drapeau(self):
        visite_id = self._visite_prete([ZONE_COMPLETE])
        visite = VisiteTerrain.objects.get(pk=visite_id)
        self.assertNotIn('amiante', selectors.recap_visite_terrain(visite))

    def test_une_charge_declaree_exige_sa_piece(self):
        zone = dict(ZONE_COMPLETE, charge_admissible_declaree_kg_m2=25)
        visite_id = self._visite_prete([zone])
        resp = self._terminer(visite_id)
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertEqual(
            {m['code'] for m in resp.data['manquants']},
            {'zones_toiture[z1].charge_admissible_piece'})
        zone['charge_admissible_piece'] = 'rapport bureau de contrôle'
        self._mesures(visite_id, 'toiture_ci', {'zones_toiture': [zone]})
        self.assertEqual(self._terminer(visite_id).status_code, 200)

    def test_la_charge_non_relevee_avec_motif_est_traitee(self):
        zone = dict(ZONE_COMPLETE, charge_admissible_declaree_kg_m2=25)
        visite_id = self._visite_prete([zone])
        resp = self._mesures(visite_id, 'toiture_ci', {'_non_releves': {
            'zones_toiture[z1].charge_admissible_piece': 'non_applicable'}})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['_non_releves'], {
            'toiture_ci.zones_toiture[z1].charge_admissible_piece':
                'non_applicable'})
        self.assertEqual(self._terminer(visite_id).status_code, 200)

    def test_la_zone_de_l_exemple_du_contrat_est_acceptee_telle_quelle(self):
        visite_id = self.creer_visite()
        resp = self._mesures(visite_id, 'toiture_ci',
                             {'zones_toiture': [ZONE_EXEMPLE]})
        self.assertEqual(resp.status_code, 200, resp.data)
        zones = resp.data['mesures']['toiture_ci']['zones_toiture']
        self.assertEqual(zones, [ZONE_EXEMPLE])

    def test_des_valeurs_invalides_sont_refusees_en_nommant_la_zone(self):
        visite_id = self.creer_visite()
        cas = [
            dict(ZONE_COMPLETE, pente_deg='raide'),
            dict(ZONE_COMPLETE, age_ans=1.5),
            dict(ZONE_COMPLETE, orientation='haut'),
            dict(ZONE_COMPLETE, etancheite='aucune'),
            dict(ZONE_COMPLETE, etancheite={'age_ans': 'vieux'}),
            dict(ZONE_COMPLETE, inconnu=1),
        ]
        for zone in cas:
            resp = self._mesures(visite_id, 'toiture_ci',
                                 {'zones_toiture': [zone]})
            self.assertEqual(resp.status_code, 400, zone)
            self.assertIn('élément 1', str(resp.data), zone)

    def test_des_identifiants_en_double_sont_refuses(self):
        visite_id = self.creer_visite()
        resp = self._mesures(visite_id, 'toiture_ci', {'zones_toiture': [
            dict(ZONE_COMPLETE, id='z1'), dict(ZONE_COMPLETE, id='z1')]})
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_le_releve_pour_calepinage_expose_les_zones_d_une_visite_ci(self):
        visite_id = self._visite_prete([ZONE_COMPLETE])
        self.assertEqual(self._terminer(visite_id).status_code, 200)
        visite = VisiteTerrain.objects.get(pk=visite_id)
        visite.statut = VisiteTerrain.Statut.VALIDEE
        visite.save(update_fields=['statut'])
        releve = selectors.releve_pour_calepinage(self.lead)
        self.assertEqual(releve['visite_id'], visite_id)
        self.assertEqual([z['libelle'] for z in releve['zones_toiture']],
                         ['Atelier nord'])

    def test_le_releve_residentiel_garde_exactement_ses_cles(self):
        self.lead.type_installation = 'residentiel'
        self.lead.save(update_fields=['type_installation'])
        VisiteTerrain.objects.create(
            company=self.company, lead=self.lead, gabarit='toiture',
            statut=VisiteTerrain.Statut.VALIDEE)
        releve = selectors.releve_pour_calepinage(self.lead)
        self.assertEqual(
            sorted(releve),
            ['mesures', 'motif_absence', 'photos', 'validee_le', 'visite_id'])
