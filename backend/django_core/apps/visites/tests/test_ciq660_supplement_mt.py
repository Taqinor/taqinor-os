"""CIQ660 — supplément MT du gabarit de visite ``ci``.

Contrat partagé : ``visite_terrain.json`` → ``gabarit_ci_supplement_mt`` et
``exemple_ci_mt``. Servi quand ``comptage.niveau_tension_constate`` vaut
``mt`` ; ``bt`` / ``inconnu`` = socle commun. Que des faits : aucun seuil,
aucun verdict, aucune alerte cos φ.
"""
import copy

from django.test import SimpleTestCase

from apps.visites import visite_checklist as checklist
from apps.visites.tests.test_ciq600_gabarit_ci import (
    CONTRAT, MESURES_CI, PHOTOS_REQUISES, SOCLE)
from apps.visites.tests.test_visite_terrain import VisiteTerrainBase

SUPPLEMENT = CONTRAT['gabarit_ci_supplement_mt']
EXEMPLE = CONTRAT['exemple_ci_mt']

PHOTOS_MT = [('cellule_mt', 1), ('transformateur_plaque', 1),
             ('factures_mt', 1)]

MESURES_MT = {
    'poste_mt': {'cellule_protection': 'cellule disjoncteur',
                 'transformateurs': [{'nb': 1, 'kva': 400}]},
}


class SupplementMtDuContrat(SimpleTestCase):
    def test_les_categories_mt_sont_celles_du_contrat_dans_l_ordre(self):
        cats = [c['categorie']
                for c in checklist.categories('ci', niveau='mt')]
        self.assertEqual(cats, SOCLE + list(SUPPLEMENT))

    def test_mesures_requis_et_libelles_du_contrat(self):
        for cat, bloc in SUPPLEMENT.items():
            declarees = {m['code']: m
                         for m in checklist.mesures(cat, 'ci', niveau='mt')}
            self.assertEqual(sorted(declarees), sorted(bloc['mesures']), cat)
            for code, attendu in bloc['mesures'].items():
                self.assertEqual(declarees[code]['libelle'],
                                 attendu['libelle'], f'{cat}.{code}')
                self.assertEqual(declarees[code]['requis'],
                                 attendu['requis'], f'{cat}.{code}')

    def test_photos_requises_du_contrat(self):
        for cat, bloc in SUPPLEMENT.items():
            declarees = {s['code']: s['requis'] for s in next(
                c for c in checklist.categories('ci', niveau='mt')
                if c['categorie'] == cat)['slots']}
            self.assertEqual(
                declarees,
                {code: (v == 'requise') for code, v in bloc['photos'].items()},
                cat)

    def test_bt_inconnu_ou_sans_niveau_servent_le_socle(self):
        for niveau in (None, 'bt', 'inconnu'):
            self.assertIs(checklist.categories('ci', niveau),
                          checklist.CATEGORIES_CI)

    def test_aucun_seuil_dans_le_supplement(self):
        interdits = ('seuil', 'min_', 'max_', 'limite', 'alerte')
        for cat in checklist.CATEGORIES_CI_MT:
            for champ in cat['mesures']:
                for cle in champ:
                    self.assertFalse(
                        any(cle.startswith(i) for i in interdits),
                        f"{cat['categorie']}.{champ['code']}.{cle}")

    def test_l_exemple_ne_porte_que_des_categories_connues(self):
        for cat in SUPPLEMENT:
            self.assertEqual(
                sorted(EXEMPLE['mesures'][cat]),
                sorted(SUPPLEMENT[cat]['mesures']), cat)


class VisiteSupplementMt(VisiteTerrainBase):
    def setUp(self):
        super().setUp()
        self.lead.type_installation = 'industriel'
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

    def _photos(self, visite_id, liste):
        for slot, combien in liste:
            for index in range(combien):
                resp = self.poster_photo(visite_id, slot,
                                         nom=f'{slot}-{index}.png')
                self.assertEqual(resp.status_code, 200, resp.data)

    def _socle(self, visite_id, niveau):
        self._photos(visite_id, PHOTOS_REQUISES)
        for categorie, valeurs in MESURES_CI.items():
            valeurs = copy.deepcopy(valeurs)
            if categorie == 'comptage':
                valeurs['niveau_tension_constate'] = niveau
            resp = self._mesures(visite_id, categorie, valeurs)
            self.assertEqual(resp.status_code, 200, resp.data)

    def _categories(self, visite_id):
        return [b['categorie'] for b in self._detail(visite_id)['checklist']]

    def test_mt_le_supplement_est_servi_et_requis(self):
        visite_id = self.creer_visite()
        self.assertNotIn('poste_mt', self._categories(visite_id))
        self._socle(visite_id, 'mt')
        self.assertEqual(
            [c for c in self._categories(visite_id) if c in SUPPLEMENT],
            list(SUPPLEMENT))
        detail = self._detail(visite_id)
        for cat in SUPPLEMENT:
            self.assertEqual(sorted(detail['mesures'][cat]),
                             sorted(SUPPLEMENT[cat]['mesures']), cat)
        resp = self._terminer(visite_id)
        self.assertEqual(resp.status_code, 400, resp.data)
        manquants = {(m['categorie'], m['code'])
                     for m in resp.data['manquants']}
        self.assertEqual(manquants, {
            ('poste_mt', 'cellule_mt'), ('poste_mt', 'transformateur_plaque'),
            ('poste_mt', 'cellule_protection'),
            ('poste_mt', 'transformateurs'), ('factures_mt', 'factures_mt')})

    def test_mt_complet_se_termine(self):
        visite_id = self.creer_visite()
        self._socle(visite_id, 'mt')
        self._photos(visite_id, PHOTOS_MT)
        for categorie, valeurs in MESURES_MT.items():
            resp = self._mesures(visite_id, categorie, valeurs)
            self.assertEqual(resp.status_code, 200, resp.data)
        resp = self._terminer(visite_id)
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_bt_le_supplement_est_absent_et_refuse(self):
        visite_id = self.creer_visite()
        self._socle(visite_id, 'bt')
        for cat in SUPPLEMENT:
            self.assertNotIn(cat, self._categories(visite_id))
            self.assertNotIn(cat, self._detail(visite_id)['mesures'])
        resp = self._mesures(visite_id, 'poste_mt', MESURES_MT['poste_mt'])
        self.assertEqual(resp.status_code, 400, resp.data)
        resp = self.poster_photo(visite_id, 'cellule_mt')
        self.assertEqual(resp.status_code, 400, resp.data)
        resp = self._terminer(visite_id)
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_cos_phi_sans_source_est_refuse_en_nommant_le_champ(self):
        visite_id = self.creer_visite()
        self._socle(visite_id, 'mt')
        resp = self._mesures(visite_id, 'factures_mt',
                             {'cos_phi_constate': 0.82})
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('source_cos_phi', resp.data['erreurs'])
        self.assertIn('Source du cos φ', resp.data['erreurs']['source_cos_phi'])
        resp = self._mesures(visite_id, 'factures_mt', {
            'cos_phi_constate': 0.82, 'source_cos_phi': 'facture'})
        self.assertEqual(resp.status_code, 200, resp.data)
        # Rien d'inventé : la valeur est rendue telle que saisie, aucun
        # verdict ni alerte.
        bloc = self._detail(visite_id)['mesures']['factures_mt']
        self.assertEqual(bloc['cos_phi_constate'], 0.82)
        self.assertEqual(sorted(bloc), sorted(
            SUPPLEMENT['factures_mt']['mesures']))

    def test_cos_phi_d_un_precedent_enregistrement_garde_sa_source(self):
        visite_id = self.creer_visite()
        self._socle(visite_id, 'mt')
        self._mesures(visite_id, 'factures_mt', {
            'cos_phi_constate': 0.9, 'source_cos_phi': 'mesure'})
        resp = self._mesures(visite_id, 'factures_mt',
                             {'cos_phi_constate': 0.95})
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_source_inconnue_est_une_source_valide_et_choix_ferme(self):
        visite_id = self.creer_visite()
        self._socle(visite_id, 'mt')
        resp = self._mesures(visite_id, 'factures_mt', {
            'cos_phi_constate': 0.9, 'source_cos_phi': 'inconnu'})
        self.assertEqual(resp.status_code, 200, resp.data)
        resp = self._mesures(visite_id, 'factures_mt', {
            'cos_phi_constate': 0.9, 'source_cos_phi': 'devine'})
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('source_cos_phi', resp.data['erreurs'])

    def test_les_mesures_de_l_exemple_sont_acceptees_telles_quelles(self):
        visite_id = self.creer_visite()
        self._socle(visite_id, 'mt')
        for cat in SUPPLEMENT:
            valeurs = copy.deepcopy(EXEMPLE['mesures'][cat])
            resp = self._mesures(visite_id, cat, valeurs)
            self.assertEqual(resp.status_code, 200, (cat, resp.data))
            # Un texte vide est rendu ``None`` (valeur non saisie).
            attendu = {k: (None if v == '' else v)
                       for k, v in valeurs.items()}
            self.assertEqual(self._detail(visite_id)['mesures'][cat],
                             attendu, cat)

    def test_non_releve_et_motif_sur_une_cellule_du_supplement(self):
        visite_id = self.creer_visite()
        self._socle(visite_id, 'mt')
        resp = self._mesures(visite_id, 'reactif_secours', {
            '_non_releves': {'condensateurs_kvar': 'acces_refuse'}})
        self.assertEqual(resp.status_code, 200, resp.data)
        plats = self._detail(visite_id)['_non_releves']
        self.assertEqual(plats['reactif_secours.condensateurs_kvar'],
                         'acces_refuse')

    def test_une_date_de_consultation_invalide_est_refusee(self):
        visite_id = self.creer_visite()
        self._socle(visite_id, 'mt')
        resp = self._mesures(visite_id, 'reseau_assurance', {
            'capacite_consultee_le': 'hier'})
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('capacite_consultee_le', resp.data['erreurs'])
        resp = self._mesures(visite_id, 'reseau_assurance', {
            'capacite_consultee_le': '2026-10-02'})
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_une_charge_sans_libelle_bloque_terminer(self):
        visite_id = self.creer_visite()
        self._socle(visite_id, 'mt')
        self._photos(visite_id, PHOTOS_MT)
        self._mesures(visite_id, 'poste_mt', MESURES_MT['poste_mt'])
        resp = self._mesures(visite_id, 'charges_principales', {
            'charges': [{'puissance_kw': 30}]})
        self.assertEqual(resp.status_code, 200, resp.data)
        resp = self._terminer(visite_id)
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertEqual([m['code'] for m in resp.data['manquants']],
                         ['charges[1].libelle'])
