"""CIQ601 — « non relevé + motif » au lieu d'un chiffre inventé (gabarit ci).

Contrat : ``visite_terrain.json`` → ``non_releves_motifs`` et
``exemple_ci._non_releves``. Gabarits toiture et point_eau inchangés.
"""
import json
from pathlib import Path

from django.test import SimpleTestCase

from apps.visites import selectors, services, visite_checklist as checklist
from apps.visites.models import VisiteTerrain
from apps.visites.tests.test_ciq600_gabarit_ci import (
    MESURES_CI, PHOTOS_REQUISES)
from apps.visites.tests.test_visite_terrain import VisiteTerrainBase

CONTRAT = json.loads(
    (Path(__file__).resolve().parent.parent / 'contract_samples'
     / 'visite_terrain.json').read_text(encoding='utf-8'))


class MotifsDuContrat(SimpleTestCase):
    def test_les_motifs_sont_ceux_du_contrat(self):
        self.assertEqual(list(checklist.MOTIFS_NON_RELEVE),
                         CONTRAT['non_releves_motifs'])


class NonReleveTests(VisiteTerrainBase):
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

    def _visite_sans_calibre(self):
        """Une visite ci complète SAUF le calibre de l'appareil de tête."""
        visite_id = self.creer_visite()
        for slot, combien in PHOTOS_REQUISES:
            for index in range(combien):
                self.assertEqual(
                    self.poster_photo(visite_id, slot,
                                      nom=f'{slot}-{index}.png').status_code,
                    200)
        for categorie, valeurs in MESURES_CI.items():
            valeurs = dict(valeurs)
            if categorie == 'tableau_general':
                valeurs.pop('calibre_a')
            self.assertEqual(
                self._mesures(visite_id, categorie, valeurs).status_code, 200)
        return visite_id

    def test_une_mesure_requise_non_relevee_avec_motif_laisse_terminer(self):
        visite_id = self._visite_sans_calibre()
        self.assertEqual(self._terminer(visite_id).status_code, 400)
        resp = self._mesures(visite_id, 'tableau_general',
                             {'_non_releves': {'calibre_a': 'dangereux'}})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['_non_releves'],
                         {'tableau_general.calibre_a': 'dangereux'})
        # Jamais une valeur par défaut : la mesure reste vide.
        self.assertIsNone(resp.data['mesures']['tableau_general']['calibre_a'])
        self.assertNotIn('_non_releves', resp.data['mesures']['tableau_general'])
        resp = self._terminer(visite_id)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['statut'], VisiteTerrain.Statut.TERMINEE)

    def test_sans_motif_400_qui_nomme_le_champ(self):
        visite_id = self._visite_sans_calibre()
        for vide in ('', None, '   '):
            resp = self._mesures(visite_id, 'tableau_general',
                                 {'_non_releves': {'calibre_a': vide}})
            self.assertEqual(resp.status_code, 400, resp.data)
            self.assertIn(
                "Motif requis pour Calibre de l'appareil de tête (A)",
                str(resp.data))
        visite = VisiteTerrain.objects.get(pk=visite_id)
        self.assertNotIn(checklist.CLE_NON_RELEVES,
                         visite.mesures['tableau_general'])

    def test_un_motif_hors_liste_est_refuse(self):
        visite_id = self._visite_sans_calibre()
        resp = self._mesures(visite_id, 'tableau_general',
                             {'_non_releves': {'calibre_a': 'flemme'}})
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('_non_releves.calibre_a', resp.data['erreurs'])
        self.assertIn('flemme', str(resp.data))

    def test_une_mesure_inconnue_est_refusee(self):
        visite_id = self._visite_sans_calibre()
        resp = self._mesures(visite_id, 'tableau_general',
                             {'_non_releves': {'toit_plat': 'dangereux'}})
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_saisir_ensuite_une_valeur_efface_l_etat(self):
        visite_id = self._visite_sans_calibre()
        self._mesures(visite_id, 'tableau_general',
                      {'_non_releves': {'calibre_a': 'site_ferme'}})
        resp = self._mesures(visite_id, 'tableau_general', {'calibre_a': 250})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['_non_releves'], {})
        self.assertEqual(
            resp.data['mesures']['tableau_general']['calibre_a'], 250)

    def test_un_champ_de_liste_non_releve_est_traite(self):
        visite_id = self._visite_sans_calibre()
        self._mesures(visite_id, 'tableau_general', {'calibre_a': 100})
        self._mesures(visite_id, 'cheminement', {'trajets': [
            {'libelle': 'a', 'longueur_dc_m': 45}]})
        self.assertEqual(self._terminer(visite_id).status_code, 400)
        resp = self._mesures(
            visite_id, 'cheminement',
            {'_non_releves': {'trajets.longueur_ac_m': 'acces_refuse'}})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(self._terminer(visite_id).status_code, 200)

    def test_enregistrer_rouvrir_enregistrer_est_identique(self):
        visite_id = self._visite_sans_calibre()
        corps = {'_non_releves': {'calibre_a': 'dangereux'}}
        self._mesures(visite_id, 'tableau_general', corps)
        avant = VisiteTerrain.objects.get(pk=visite_id).mesures
        self._mesures(visite_id, 'tableau_general', corps)
        apres = VisiteTerrain.objects.get(pk=visite_id).mesures
        self.assertEqual(avant, apres)
        # Rouvrir : ré-enregistrer les valeurs rendues (None) ne touche à rien.
        url = f'/api/django/visites/visites/{visite_id}/'
        rendu = self.api.get(url).data
        self._mesures(visite_id, 'tableau_general',
                      rendu['mesures']['tableau_general'])
        rendu_apres = self.api.get(url).data
        self.assertEqual(rendu_apres['mesures'], rendu['mesures'])
        self.assertEqual(rendu_apres['_non_releves'], rendu['_non_releves'])
        self.assertEqual(VisiteTerrain.objects.get(pk=visite_id).mesures[
            'tableau_general'][checklist.CLE_NON_RELEVES],
            avant['tableau_general'][checklist.CLE_NON_RELEVES])

    def test_le_recap_dit_non_verifie_avec_le_motif(self):
        visite_id = self._visite_sans_calibre()
        self._mesures(visite_id, 'tableau_general',
                      {'_non_releves': {'calibre_a': 'dangereux'}})
        visite = VisiteTerrain.objects.get(pk=visite_id)
        recap = selectors.recap_visite_terrain(visite)
        self.assertIn('non vérifié (dangereux)', recap)
        self.assertNotIn('appareil de tête 0', recap)

    def test_non_releve_refuse_hors_gabarit_ci(self):
        self.lead.type_installation = 'residentiel'
        self.lead.save(update_fields=['type_installation'])
        visite_id = self.creer_visite()
        resp = self._mesures(visite_id, 'toiture',
                             {'_non_releves': {'longueur_m': 'dangereux'}})
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn(checklist.CLE_NON_RELEVES, resp.data['erreurs'])

    def test_l_etat_ne_fuit_pas_dans_un_gabarit_non_ci(self):
        visite = VisiteTerrain.objects.create(
            company=self.company, lead=self.lead, gabarit='toiture',
            mesures={'toiture': {'_non_releves': {'longueur_m': 'dangereux'}}})
        self.assertEqual(selectors._non_releves_plats(visite), {})
        self.assertNotIn('_non_releves',
                         selectors.contexte_visite_terrain(visite))

    def test_la_validation_du_motif_est_pure(self):
        connus = {m['code']: m for m in checklist.mesures(
            'tableau_general', 'ci')}
        etats, erreurs = services.valeur_non_releves(
            connus, {'calibre_a': 'dangereux'})
        self.assertEqual((etats, erreurs), ({'calibre_a': 'dangereux'}, {}))
