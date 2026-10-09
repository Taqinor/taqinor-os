"""ACHT39 (C-ACHT-036) — `interventions_actives` : LA notion « ressource
occupée » de la planification, lue par `conflits_affectation`,
`plan_de_charge_equipes` et `suggerer_creneau` ; une proposition de créneau
vaut sur `duree_jours` jours ouvrés.

Rejoue CINT-13 (conflit compté 2 pour deux annulées ; B proposé ; 1 jour =
3 jours).

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.installations.tests_acht_planification_occupation"
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company

from apps.installations import selectors
from apps.installations.models import Installation, Intervention

User = get_user_model()
LUNDI = datetime.date(2026, 11, 2)       # lundi
MARDI = datetime.date(2026, 11, 3)


class OccupationTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='co-acht39', defaults={'nom': 'Co ACHT39'})
        self.a = User.objects.create_user(
            username='tech-a-acht39', password='x', company=self.company,
            role_legacy='technicien')
        self.b = User.objects.create_user(
            username='tech-b-acht39', password='x', company=self.company,
            role_legacy='technicien')
        self.inst = Installation.objects.create(
            company=self.company, reference='CH-ACHT39')

    def _iv(self, tech, jour, annulee=False):
        return Intervention.objects.create(
            company=self.company, installation=self.inst,
            type_intervention='pose', technicien=tech, date_prevue=jour,
            annulee=annulee)

    def _planifier_cas(self):
        # A : deux interventions ANNULÉES le 02/11 ; B occupé le 03/11.
        self._iv(self.a, LUNDI, annulee=True)
        self._iv(self.a, LUNDI, annulee=True)
        self._iv(self.b, MARDI)

    def _propositions(self, duree):
        res = selectors.suggerer_creneau(
            self.company, chantier_id=self.inst.id, type_intervention='pose',
            duree_jours=duree, date_cible=LUNDI, n=50)
        return [(p['technicien_id'], p['date']) for p in res['propositions']]

    def test_annulees_hors_conflit(self):
        self._planifier_cas()
        res = selectors.conflits_affectation(
            self.company, LUNDI, LUNDI + datetime.timedelta(days=6))
        self.assertEqual(res['totaux']['nb_conflits'], 0, res)
        self.assertIn((self.a.id, LUNDI.isoformat()), self._propositions(1))

    def test_parite_trois_vues(self):
        self._planifier_cas()
        fin = LUNDI + datetime.timedelta(days=6)
        charge = selectors.plan_de_charge_equipes(self.company, LUNDI, fin)
        ids = {t['technicien_id'] for t in charge['techniciens']}
        self.assertEqual(ids, {self.b.id})   # A : annulées exclues partout
        self.assertEqual(
            selectors.interventions_actives(
                self.company, LUNDI, fin).count(), 1)

    def test_duree_jours_respectee(self):
        self._planifier_cas()
        un_jour = self._propositions(1)
        trois_jours = self._propositions(3)
        self.assertIn((self.a.id, LUNDI.isoformat()), trois_jours)
        # B est pris le 03/11 : proposé le 02/11 pour 1 jour, pas pour 3.
        self.assertIn((self.b.id, LUNDI.isoformat()), un_jour)
        self.assertNotIn((self.b.id, LUNDI.isoformat()), trois_jours)
        self.assertNotEqual(un_jour, trois_jours)
