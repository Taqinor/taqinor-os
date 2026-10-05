"""CIQ606 — relevé C&I : déclaré / constaté / écart, sans seconde saisie.

Le sélecteur testé n'est JAMAIS mocké : le déclaré est lu par
``crm.selectors.releve_declare_ci`` sur un vrai lead. Contrat partagé :
``visite_terrain.json`` → ``exemple_ci.releve_ci``.
"""
import json
from decimal import Decimal
from pathlib import Path

from apps.crm import selectors as crm_selectors
from apps.visites import selectors
from apps.visites.models import VisiteTerrain
from apps.visites.tests.test_visite_terrain import VisiteTerrainBase

CONTRAT = json.loads(
    (Path(__file__).resolve().parent.parent / 'contract_samples'
     / 'visite_terrain.json').read_text(encoding='utf-8'))
RELEVE_CONTRAT = CONTRAT['exemple_ci']['releve_ci']
CHAMPS = ('niveau_tension', 'puissance_souscrite_kva', 'type_toiture',
          'surface_utile', 'statut_occupation')

ZONE = {'id': 'z1', 'libelle': 'Atelier nord', 'longueur_m': 40,
        'largeur_m': 18, 'pente_deg': 8, 'orientation': 'sud',
        'couverture': 'bac_acier', 'structure': 'portique',
        'surface_utile_m2': None}


class ReleveCiTests(VisiteTerrainBase):
    def setUp(self):
        super().setUp()
        self.lead.type_installation = 'industriel'
        self.lead.tension_raccordement = 'bt'
        self.lead.compteur_puissance_kva = Decimal('80')
        self.lead.type_toiture = 'terrasse_beton'
        self.lead.surface_toiture_m2 = Decimal('650')
        self.lead.ownership = 'proprietaire'
        self.lead.save()

    def _visite(self, statut=VisiteTerrain.Statut.VALIDEE, mesures=None,
                gabarit='ci'):
        base = {
            'comptage': {'type_compteur': 'triphasé',
                         'niveau_tension_constate': 'bt',
                         'puissance_souscrite_kva_constatee': 100},
            'toiture_ci': {'zones_toiture': [ZONE]},
            'cheminement': {'trajets': [
                {'libelle': 'a', 'longueur_dc_m': 45, 'longueur_ac_m': None}]},
        }
        base.update(mesures or {})
        return VisiteTerrain.objects.create(
            company=self.company, lead=self.lead, gabarit=gabarit,
            statut=statut, mesures=base)

    def test_declare_80_constate_100_donne_un_ecart_different(self):
        self._visite()
        releve = selectors.releve_ci_pour_lead(self.lead)
        bloc = releve['puissance_souscrite_kva']
        self.assertEqual(bloc, {'declare': 80.0, 'constate': 100.0,
                                'ecart': True})

    def test_egal_et_non_comparable(self):
        self._visite()
        releve = selectors.releve_ci_pour_lead(self.lead)
        self.assertEqual(releve['niveau_tension'],
                         {'declare': 'bt', 'constate': 'bt', 'ecart': False})
        # Aucune mesure ne porte le statut d'occupation : non comparable.
        self.assertEqual(releve['statut_occupation'],
                         {'declare': 'proprietaire', 'constate': None,
                          'ecart': None})

    def test_type_de_toiture_compare_via_la_table_ciq603(self):
        self._visite()
        releve = selectors.releve_ci_pour_lead(self.lead)
        self.assertEqual(releve['type_toiture'],
                         {'declare': 'terrasse_beton',
                          'constate': 'bac_acier', 'ecart': True})
        self.lead.type_toiture = 'bac_acier'
        self.lead.save(update_fields=['type_toiture'])
        releve = selectors.releve_ci_pour_lead(self.lead)
        self.assertIs(releve['type_toiture']['ecart'], False)

    def test_surface_somme_des_zones(self):
        zone_b = dict(ZONE, id='z2', libelle='Entrepôt', longueur_m=None,
                      largeur_m=None, surface_utile_m2=100)
        self._visite(mesures={'toiture_ci': {'zones_toiture': [ZONE, zone_b]}})
        releve = selectors.releve_ci_pour_lead(self.lead)
        self.assertEqual(releve['surface_utile'],
                         {'declare': 650.0, 'constate': 820.0, 'ecart': True})

    def test_plusieurs_couvertures_ou_zone_sans_surface_non_comparable(self):
        zone_b = dict(ZONE, id='z2', couverture='tole', longueur_m=None)
        self._visite(mesures={'toiture_ci': {'zones_toiture': [ZONE, zone_b]}})
        releve = selectors.releve_ci_pour_lead(self.lead)
        self.assertIsNone(releve['type_toiture']['constate'])
        self.assertIsNone(releve['type_toiture']['ecart'])
        self.assertIsNone(releve['surface_utile']['constate'])
        self.assertIsNone(releve['surface_utile']['ecart'])
        # Les zones restent exposées telles que saisies.
        self.assertEqual(len(releve['zones_toiture']), 2)

    def test_visite_non_validee_ou_residentielle_donne_none(self):
        for statut in (VisiteTerrain.Statut.BROUILLON,
                       VisiteTerrain.Statut.EN_COURS,
                       VisiteTerrain.Statut.TERMINEE,
                       VisiteTerrain.Statut.A_REFAIRE):
            visite = self._visite(statut=statut)
            self.assertIsNone(selectors.releve_ci_pour_lead(self.lead))
            visite.delete()
        self._visite(gabarit='toiture')
        self.assertIsNone(selectors.releve_ci_pour_lead(self.lead))
        self.assertIsNone(selectors.releve_ci_pour_lead(None))

    def test_une_mesure_non_relevee_donne_constate_null_et_motif(self):
        self._visite(mesures={'comptage': {
            'type_compteur': 'triphasé', 'niveau_tension_constate': 'bt',
            'puissance_souscrite_kva_constatee': None,
            '_non_releves': {
                'puissance_souscrite_kva_constatee':
                    'a_faire_par_electricien'}}})
        releve = selectors.releve_ci_pour_lead(self.lead)
        self.assertEqual(
            releve['puissance_souscrite_kva'],
            {'declare': 80.0, 'constate': None, 'ecart': None,
             'non_releve': 'a_faire_par_electricien'})
        self.assertEqual(releve['non_releves'], {
            'comptage.puissance_souscrite_kva_constatee':
                'a_faire_par_electricien'})

    def test_declare_non_renseigne_donne_none_sans_defaut(self):
        autre = type(self.lead).objects.create(
            company=self.company, nom='Vide', type_installation='industriel')
        VisiteTerrain.objects.create(
            company=self.company, lead=autre, gabarit='ci',
            statut=VisiteTerrain.Statut.VALIDEE,
            mesures={'comptage': {'niveau_tension_constate': 'mt'}})
        releve = selectors.releve_ci_pour_lead(autre)
        for champ in CHAMPS:
            self.assertIsNone(releve[champ]['declare'], champ)
            self.assertIsNone(releve[champ]['ecart'], champ)
        self.assertEqual(releve['niveau_tension']['constate'], 'mt')

    def test_tension_ne_sait_pas_vaut_inconnu_non_comparable(self):
        self.lead.tension_raccordement = 'ne_sait_pas'
        self.lead.save(update_fields=['tension_raccordement'])
        self._visite()
        bloc = selectors.releve_ci_pour_lead(self.lead)['niveau_tension']
        self.assertEqual(bloc, {'declare': 'inconnu', 'constate': 'bt',
                                'ecart': None})

    def test_la_forme_est_celle_du_contrat(self):
        self._visite()
        releve = selectors.releve_ci_pour_lead(self.lead)
        # Toutes les clés du contrat, avec leurs sous-clés.
        for cle, attendu in RELEVE_CONTRAT.items():
            self.assertIn(cle, releve)
            if isinstance(attendu, dict):
                self.assertEqual(sorted(releve[cle]), sorted(attendu), cle)
        # La date de validation vient de la visite, jamais d'ailleurs.
        visite = VisiteTerrain.objects.get(pk=releve['visite_id'])
        self.assertIsNone(releve['validee_le'])
        self.assertIsNone(visite.validee_le)

    def test_le_meme_bloc_est_servi_dans_le_contexte_de_revue(self):
        visite = self._visite(statut=VisiteTerrain.Statut.TERMINEE)
        contexte = selectors.contexte_visite_terrain(visite)
        self.assertEqual(contexte['releve_ci'],
                         selectors.releve_ci_de_visite(visite))
        self.assertEqual(contexte['releve_ci']['puissance_souscrite_kva'][
            'ecart'], True)
        # Un gabarit non ci ne porte pas le bloc.
        residentielle = self._visite(gabarit='toiture')
        self.assertNotIn('releve_ci',
                         selectors.contexte_visite_terrain(residentielle))

    def test_le_declare_vient_de_crm_selectors(self):
        declare = crm_selectors.releve_declare_ci(self.lead)
        self.assertEqual(declare, {
            'niveau_tension': 'bt', 'puissance_souscrite_kva': 80.0,
            'type_toiture': 'terrasse_beton', 'surface_utile': 650.0,
            'statut_occupation': 'proprietaire'})

    def test_la_lecture_n_ecrit_rien_et_ne_change_pas_le_lead(self):
        self._visite()
        selectors.releve_ci_pour_lead(self.lead)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.compteur_puissance_kva, Decimal('80'))
        self.assertEqual(self.lead.type_installation, 'industriel')

    def test_la_societe_vient_du_lead(self):
        VisiteTerrain.objects.create(
            company=self.autre, lead=self.lead, gabarit='ci',
            statut=VisiteTerrain.Statut.VALIDEE,
            mesures={'comptage': {'niveau_tension_constate': 'mt'}})
        self.assertIsNone(selectors.releve_ci_pour_lead(self.lead))
