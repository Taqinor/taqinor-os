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


class PlanParDefautTest(TestCase):
    """Plan virtuel 21,6 kWc à Casablanca : production par la cascade, pente supposée dite, 0 écriture."""

    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='Plan par défaut')

    def _plan(self, client=None, **kwargs):
        return simuler_plan_par_defaut(self.company, *CASABLANCA, 21.6, materiel=MATERIEL, reglages=REGLAGES,
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
            enregistrer=False, materiel=MATERIEL, reglages=REGLAGES, client=_ClientRejoue())
        total = pose['blocs']['production']['total']
        self.assertGreater(plan['production_annuelle'], 0)
        self.assertEqual(plan['production_annuelle'], total['p50_kwh'])
        self.assertEqual(plan['production_mensuelle'],
                         [m.get('p50_kwh') for m in pose['blocs']['production']['mensuel']])
        self.assertEqual(plan['version_moteur'], simulation._version_moteur())
        # Rappeler rend le même résultat.
        self.assertEqual(self._plan()['production_annuelle'], plan['production_annuelle'])

    def test_pente_non_declaree_supposee_et_dite_pente_declaree_respectee(self):
        suppose = self._plan()
        self.assertEqual(suppose['pente_deg'], PENTE_SUPPOSEE_DEG)
        self.assertEqual(PENTE_SUPPOSEE_DEG, 30.0)
        self.assertEqual([s['champ'] for s in suppose['suppositions']], ['inclinaison_deg'])
        self.assertIn('30°', suppose['suppositions'][0]['message'])

        client = _ClientRejoue()
        declaree = self._plan(pente=18, client=client)
        self.assertEqual(declaree['pente_deg'], 18.0)
        self.assertEqual(declaree['suppositions'], [])
        self.assertEqual(declaree['document']['zones'][0]['geometry']['tiltDeg'], 18.0)
        # La météo est DEMANDÉE au plan déclaré (la réponse rejouée, elle, ne dépend pas de l'angle ;
        # 0° = la demande horizontale que la cascade fait aussi pour tout plan).
        self.assertEqual({demande['inclinaison_deg'] for demande in client.demandes} - {0.0}, {18.0})
