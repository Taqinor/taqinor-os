"""ACAL2026 (D-ACAL-97, Q1 du 23/11 : « Same simulation, default roof ») — le plan par
défaut d'un lead sans toit tracé : un toit SUPPOSÉ (pente du lead ou 30°, plein sud, kWc
donné) simulé par LA cascade de la pose (``simulation.simuler_calepinage``), rien d'écrit.

Météo rejouée et matériel / réglages injectés (mêmes doubles que
``test_calx5_simulation``) : aucun réseau.

Run :
    python manage.py test apps.calepinage.tests.test_plan_par_defaut -v2
"""
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from apps.calepinage.models import Calepinage
from apps.calepinage.services import simulation
from apps.calepinage.services.plan_par_defaut import PENTE_SUPPOSEE_DEG, simuler_plan_par_defaut
from apps.calepinage.tests.test_calx5_simulation import MATERIEL, REGLAGES, _ClientRejoue
from authentication.models import Company

CASABLANCA = (33.5731, -7.5898)
#: La table société de l'échauffement (profil de départ, D-ACAL-84) : sans elle ni Uc / NOCT
#: sur la fiche, l'étape « Échauffement des modules » est omise et le plan la DIT (B1).
REGLAGES_THERMIQUE = {**REGLAGES, 'simulation': {**REGLAGES['simulation'], 'thermique_par_pose': {
    'source': 'profil de départ', 'valeur': {
        'pose_libre': {'uc_w_m2k': 29, 'uv_w_m3sk': 0, 'source': 'texte'},
        'dos_isole': {'uc_w_m2k': 15, 'uv_w_m3sk': 0, 'source': 'texte'}}}}}


class PlanParDefautTest(TestCase):
    """Plan virtuel 21,6 kWc à Casablanca : production par la cascade, pente supposée dite, 0 écriture."""

    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='Plan par défaut')

    def _plan(self, client=None, kwc=21.6, materiel=MATERIEL, reglages=REGLAGES_THERMIQUE, **kwargs):
        return simuler_plan_par_defaut(self.company, *CASABLANCA, kwc, materiel=materiel, reglages=reglages,
                                       client=client or _ClientRejoue(), **kwargs)

    def test_production_par_la_cascade_de_la_pose_et_rien_d_ecrit(self):
        avant = Calepinage.objects.count()
        with CaptureQueriesContext(connection) as requetes:
            plan = self._plan()
        ecritures = [q['sql'] for q in requetes.captured_queries
                     if q['sql'].lstrip().upper().startswith(('INSERT', 'UPDATE', 'DELETE'))]
        self.assertEqual(ecritures, [])
        self.assertEqual(Calepinage.objects.count(), avant)

        # 21,6 kWc de modules 710 Wc : 30 modules, posés sur UN pan plein sud.
        self.assertEqual(plan['nb_panneaux'], 30)
        self.assertAlmostEqual(plan['kwc'], 21.3, places=3)
        self.assertEqual(plan['azimut_deg'], 180.0)
        # LA cascade de la pose : la même simulation sur le même toit rend le même chiffre.
        pose = simulation.simuler_calepinage(
            Calepinage(company=self.company, roof_layout=plan['document'], pertes=[]), forcer=True,
            enregistrer=False, materiel=MATERIEL, reglages=REGLAGES_THERMIQUE, client=_ClientRejoue())
        total = pose['blocs']['production']['total']
        self.assertGreater(plan['production_annuelle'], 0)
        self.assertEqual(plan['production_annuelle'], total['p50_kwh'])
        self.assertEqual(plan['production_mensuelle'],
                         [m.get('p50_kwh') for m in pose['blocs']['production']['mensuel']])
        self.assertEqual(plan['version_moteur'], simulation._version_moteur())
        # ADEV155 — la complétude du total de la cascade, lue telle quelle (jamais recalculée).
        self.assertIs(plan['complete'], total['complete'] is True)
        # Rappeler rend le même résultat.
        self.assertEqual(self._plan()['production_annuelle'], plan['production_annuelle'])

    def test_pente_non_declaree_supposee_et_dite_pente_declaree_respectee(self):
        suppose = self._plan()
        self.assertEqual(suppose['pente_deg'], PENTE_SUPPOSEE_DEG)
        self.assertEqual(PENTE_SUPPOSEE_DEG, 30.0)
        # (B1 — les manques de la fiche d'essai, dits à part, ne sont pas le sujet de ce test.)
        self.assertEqual([s['champ'] for s in suppose['suppositions'] if s['code'] != 'fiche_module_incomplete'],
                         ['inclinaison_deg', 'type_toiture'])
        self.assertIn('30°', suppose['suppositions'][0]['message'])

        client = _ClientRejoue()
        declaree = self._plan(pente=18, client=client)
        self.assertEqual(declaree['pente_deg'], 18.0)
        # ACAL2045 — la pose reste supposée (dite), la pente non.
        self.assertEqual([s['code'] for s in declaree['suppositions'] if s['code'] != 'fiche_module_incomplete'],
                         ['pose_supposee'])
        self.assertEqual(declaree['document']['zones'][0]['geometry']['tiltDeg'], 18.0)
        # La météo est DEMANDÉE au plan déclaré (la réponse rejouée, elle, ne dépend pas de l'angle ;
        # 0° = la demande horizontale que la cascade fait aussi pour tout plan).
        self.assertEqual({demande['inclinaison_deg'] for demande in client.demandes} - {0.0}, {18.0})

    def test_fiche_sans_puissance_simule_a_la_taille_de_la_conception(self):
        """Correction d'ACAL2026 — la fiche du module ne porte AUCUNE puissance (« Panneau mono
        550W » de la production) : le plan prend le compte et la puissance unitaire de la
        conception (22 kWc ÷ 40 panneaux), portés dans le document comme une pose réelle
        (``modules[].pmaxWc``), et DIT ce que la fiche vide fait supposer."""
        materiel = dict(MATERIEL, module={}, designations={'module': 'Panneau mono 550W', 'onduleur': '',
                                                           'optimiseur': ''})
        plan = self._plan(materiel=materiel, nb_panneaux=40, kwc=22.0)
        self.assertEqual(plan['nb_panneaux'], 40)
        self.assertAlmostEqual(plan['kwc'], 22.0, places=3)
        self.assertGreater(plan['production_annuelle'], 0)
        # LE chemin d'une pose réelle : le même document simulé tel quel rend le même chiffre.
        self.assertEqual(plan['document']['modules'][0]['pmaxWc'], 550.0)
        pose = simulation.simuler_calepinage(
            Calepinage(company=self.company, roof_layout=plan['document'], pertes=[]), forcer=True,
            enregistrer=False, materiel=materiel, reglages=REGLAGES_THERMIQUE, client=_ClientRejoue())
        self.assertEqual(plan['production_annuelle'], pose['blocs']['production']['total']['p50_kwh'])
        # Rien d'inventé : la puissance prise de la conception et chaque étape que la fiche vide
        # empêche sont dites, le produit nommé, le champ à remplir = sa fiche technique.
        fiches = [s for s in plan['suppositions'] if s['champ'] == 'fiche_technique']
        self.assertTrue(fiches)
        self.assertEqual(fiches[0]['code'], 'puissance_module_de_la_conception')
        self.assertTrue(all('Panneau mono 550W' in s['message'] for s in fiches))
        self.assertIn('fiche_module_incomplete', {s['code'] for s in fiches})

    def test_toit_suppose_echauffement_applique_et_pose_supposee_dite(self):
        """ACAL2045 — le document du toit supposé DIT sa pose (``flush``, comme une pose réelle) :
        l'étape « Échauffement des modules » est appliquée par la table société (affleurant ⇒
        « dos isolé », châssis ⇒ « pose libre ») au lieu d'être omise, et ``suppositions`` dit la
        pose supposée avec le champ du lead à renseigner. Mutant « retirer la pose du document »
        ⇒ l'étape est omise : rouge."""
        reglages = REGLAGES_THERMIQUE

        def plan(**lead):
            rendu = simuler_plan_par_defaut(self.company, *CASABLANCA, 21.6, materiel=MATERIEL, reglages=reglages,
                                            client=_ClientRejoue(), pente=30, **lead)
            pose = simulation.simuler_calepinage(
                Calepinage(company=self.company, roof_layout=rendu['document'], pertes=[]), forcer=True,
                enregistrer=False, materiel=MATERIEL, reglages=reglages, client=_ClientRejoue())
            etapes = pose['blocs']['cascade']['etapes']
            return rendu, next(e for e in etapes if e.get('libelle') == 'Échauffement des modules')

        residentiel, etape_r = plan(type_installation='residentiel', type_toiture='tuiles')
        terrasse, etape_t = plan(type_installation='residentiel', type_toiture='terrasse_beton')
        industriel, _etape_i = plan(type_installation='industriel')
        inconnu, _etape_x = plan()
        self.assertTrue(residentiel['document']['zones'][0]['geometry']['flush'])
        self.assertFalse(terrasse['document']['zones'][0]['geometry']['flush'])
        self.assertFalse(industriel['document']['zones'][0]['geometry']['flush'])
        self.assertTrue(inconnu['document']['zones'][0]['geometry']['flush'])
        for etape in (etape_r, etape_t):
            self.assertFalse(etape.get('motif_omission'), etape)
        # Affleurant (dos isolé, Uc 15) chauffe plus que châssis (pose libre, Uc 29) : moins de production.
        self.assertLess(residentiel['production_annuelle'], terrasse['production_annuelle'])
        dites = {nom: [s for s in r['suppositions'] if s['code'] == 'pose_supposee']
                 for nom, r in (('r', residentiel), ('t', terrasse), ('i', industriel), ('x', inconnu))}
        self.assertEqual({nom: [(s['champ'], s['valeur']) for s in d] for nom, d in dites.items()},
                         {'r': [('type_toiture', 'affleurante')], 't': [('type_toiture', 'sur châssis')],
                          'i': [('type_installation', 'sur châssis')], 'x': [('type_toiture', 'affleurante')]})
        self.assertIn('Type de toiture', dites['r'][0]['message'])
        self.assertIn('calepinage', dites['t'][0]['message'])

    def test_fiche_a_puissance_sans_coefficient_de_temperature_echauffement_omis_dit(self):
        """B1 (relecture lot 5) — la fiche porte ``pmax_wc`` mais pas ``temp_coeff_pmax_pct_c`` :
        l'échauffement est omis ; le plan le DIT (``fiche_module_incomplete``, champ nommé) même
        sans puissance prise de la conception. Mutant « ne scanner que si la fiche n'a pas de
        puissance » ⇒ aucune supposition : rouge."""
        module = {cle: valeur for cle, valeur in MATERIEL['module'].items() if cle != 'temp_coeff_pmax_pct_c'}
        plan = self._plan(materiel=dict(MATERIEL, module=module))
        self.assertNotIn('puissance_module_de_la_conception', [s['code'] for s in plan['suppositions']])
        manques = [s for s in plan['suppositions'] if s['code'] == 'fiche_module_incomplete'
                   and 'Échauffement' in s['message']]
        self.assertEqual(len(manques), 1, plan['suppositions'])
        self.assertEqual(manques[0]['valeur'], 'fiche_module.temp_coeff_pmax_pct_c')
        self.assertIn('temp_coeff_pmax_pct_c', manques[0]['message'])
        # La fiche complète (table société de l'échauffement) : l'étape n'est pas dite manquante.
        self.assertFalse([s for s in self._plan()['suppositions'] if 'Échauffement' in s.get('message', '')])

    def test_fiche_sans_puissance_sans_compte_de_conception_refuse_comme_avant(self):
        materiel = dict(MATERIEL, module={})
        with self.assertRaises(simulation.SimulationRefusee):
            self._plan(materiel=materiel)
