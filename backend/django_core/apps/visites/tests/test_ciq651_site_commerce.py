"""CIQ651 — catégorie « site commerce » du gabarit de visite ``ci``.

Contrat partagé : ``visite_terrain.json`` → ``gabarit_ci_site_commerce`` et
``exemple_ci_commerce``. Requise pour un lead ``commercial``, facultative pour
un ``industriel`` ; la pièce « accord du propriétaire » n'est servie que pour un
lead locataire (lu par ``crm.selectors``, jamais ressaisi). Aucun verdict.
"""
import copy

from django.test import SimpleTestCase

from apps.crm.models import Lead
from apps.visites import visite_checklist as checklist
from apps.visites.tests.test_ciq600_gabarit_ci import (
    CONTRAT, MESURES_CI, PHOTOS_REQUISES)
from apps.visites.tests.test_visite_terrain import VisiteTerrainBase

BLOC = CONTRAT['gabarit_ci_site_commerce']['site_commerce']
EXEMPLE = CONTRAT['exemple_ci_commerce']
SITE_EXEMPLE = EXEMPLE['mesures']['site_commerce']


class ContratSiteCommerce(SimpleTestCase):
    def test_les_categories_sont_celles_du_moteur(self):
        self.assertEqual(
            checklist.CATEGORIES_COMMERCIALES,
            [valeur for valeur, _ in Lead.CategorieCommerciale.choices])

    def test_mesures_requis_et_libelles_du_contrat(self):
        declarees = {m['code']: m for m in checklist.mesures(
            'site_commerce', 'ci', type_lead='commercial')}
        self.assertEqual(sorted(declarees), sorted(BLOC['mesures']))
        for code, attendu in BLOC['mesures'].items():
            self.assertEqual(declarees[code]['requis'], attendu['requis'],
                             code)
            self.assertEqual(declarees[code]['libelle'], attendu['libelle'],
                             code)
        self.assertEqual(declarees['categorie']['choix'],
                         BLOC['mesures']['categorie']['choix'])
        self.assertEqual(sorted(SITE_EXEMPLE), sorted(BLOC['mesures']))

    def test_facultative_pour_un_industriel(self):
        for type_lead in ('industriel', 'agricole'):
            champs = checklist.mesures('site_commerce', 'ci',
                                       type_lead=type_lead)
            self.assertTrue(champs)
            self.assertFalse([c for c in champs if c['requis']], type_lead)

    def test_absente_sans_type_de_lead(self):
        self.assertIs(checklist.categories('ci'), checklist.CATEGORIES_CI)
        self.assertIsNone(checklist.categorie('site_commerce', 'ci'))
        self.assertIsNone(checklist.categorie(
            'site_commerce', 'toiture', type_lead='commercial'))

    def test_l_accord_du_proprietaire_suit_le_statut_d_occupation(self):
        avec = checklist.codes_slots('ci', type_lead='commercial',
                                     locataire=True)
        sans = checklist.codes_slots('ci', type_lead='commercial')
        self.assertIn('accord_proprietaire', avec)
        self.assertNotIn('accord_proprietaire', sans)
        self.assertIn('secours_existant', sans)
        # La pièce ne se lit pas comme un libellé de photo orpheline.
        self.assertIsNotNone(checklist.slot('accord_proprietaire'))


class VisiteSiteCommerce(VisiteTerrainBase):
    def _lead(self, type_installation='commercial', ownership=None):
        self.lead.type_installation = type_installation
        self.lead.ownership = ownership
        self.lead.save(update_fields=['type_installation', 'ownership'])

    def _detail(self, visite_id):
        return self.api.get(f'/api/django/visites/visites/{visite_id}/').data

    def _slots(self, visite_id):
        return {slot['code'] for bloc in self._detail(visite_id)['checklist']
                for slot in bloc['slots']}

    def _mesures(self, visite_id, categorie, valeurs):
        return self.api.patch(
            f'/api/django/visites/visites/{visite_id}/mesures/',
            {'categorie': categorie, 'valeurs': valeurs}, format='json')

    def _terminer(self, visite_id):
        return self.api.post(
            f'/api/django/visites/visites/{visite_id}/terminer/', {},
            format='json')

    def _remplir(self, visite_id, avec_site=True):
        for slot, combien in PHOTOS_REQUISES:
            for index in range(combien):
                resp = self.poster_photo(visite_id, slot,
                                         nom=f'{slot}-{index}.png')
                self.assertEqual(resp.status_code, 200, resp.data)
        for categorie, valeurs in MESURES_CI.items():
            if categorie == 'site_commerce' and not avec_site:
                continue
            resp = self._mesures(visite_id, categorie, valeurs)
            self.assertEqual(resp.status_code, 200, resp.data)

    def test_lead_locataire_le_slot_accord_est_present(self):
        self._lead(ownership='locataire')
        visite_id = self.creer_visite()
        self.assertIn('accord_proprietaire', self._slots(visite_id))
        resp = self.poster_photo(visite_id, 'accord_proprietaire')
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_lead_proprietaire_ou_inconnu_le_slot_accord_est_absent(self):
        for ownership in ('proprietaire', None):
            self._lead(ownership=ownership)
            visite_id = self.creer_visite()
            self.assertNotIn('accord_proprietaire', self._slots(visite_id))
            resp = self.poster_photo(visite_id, 'accord_proprietaire')
            self.assertEqual(resp.status_code, 400, resp.data)
            self.assertIn('slot_code', resp.data['erreurs'])

    def test_le_statut_est_relu_du_lead_pas_fige(self):
        self._lead(ownership='proprietaire')
        visite_id = self.creer_visite()
        self.assertNotIn('accord_proprietaire', self._slots(visite_id))
        self._lead(ownership='locataire')
        self.assertIn('accord_proprietaire', self._slots(visite_id))

    def test_visite_commerciale_sans_site_commerce_est_refusee(self):
        self._lead()
        visite_id = self.creer_visite()
        self._remplir(visite_id, avec_site=False)
        resp = self._terminer(visite_id)
        self.assertEqual(resp.status_code, 400, resp.data)
        manquants = {m['code'] for m in resp.data['manquants']}
        self.assertEqual(manquants, {'categorie', 'horaires_constates',
                                     'besoin_continuite_service'})
        self.assertTrue(all(m['categorie'] == 'site_commerce'
                            for m in resp.data['manquants']))

    def test_visite_commerciale_avec_site_commerce_se_termine(self):
        self._lead()
        visite_id = self.creer_visite()
        self._remplir(visite_id)
        resp = self._terminer(visite_id)
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_site_commerce_facultatif_pour_un_industriel(self):
        self._lead('industriel')
        visite_id = self.creer_visite()
        self.assertEqual(
            self._detail(visite_id)['checklist'][0]['categorie'],
            'site_commerce')
        self._remplir(visite_id, avec_site=False)
        resp = self._terminer(visite_id)
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_l_exemple_du_contrat_est_accepte_tel_quel(self):
        self._lead()
        visite_id = self.creer_visite()
        resp = self._mesures(visite_id, 'site_commerce',
                             copy.deepcopy(SITE_EXEMPLE))
        self.assertEqual(resp.status_code, 200, resp.data)
        detail = self._detail(visite_id)
        self.assertEqual(detail['mesures']['site_commerce'], SITE_EXEMPLE)
        self.assertEqual(sorted(detail), sorted(EXEMPLE))

    def test_un_circuit_inconnu_est_refuse_en_nommant_le_champ(self):
        self._lead()
        visite_id = self.creer_visite()
        resp = self._mesures(visite_id, 'site_commerce', {
            'circuits_critiques': [{'circuit': 'piscine'}]})
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('circuits_critiques', resp.data['erreurs'])
        self.assertIn('Circuit critique', str(resp.data))

    def test_la_categorie_inconnue_est_refusee(self):
        self._lead()
        visite_id = self.creer_visite()
        resp = self._mesures(visite_id, 'site_commerce',
                             {'categorie': 'casino'})
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('categorie', resp.data['erreurs'])

    def test_un_lead_residentiel_n_a_pas_de_site_commerce(self):
        self._lead('residentiel')
        visite_id = self.creer_visite()
        self.assertNotIn('site_commerce',
                         self._detail(visite_id)['mesures'])
