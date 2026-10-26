"""APRF41 (C-APRF-023) — la replanification en masse charge les ressources de la
fenêtre UNE fois pour le lot (`suggerer_creneaux_lot`) : 2 puis 6 interventions
à replanifier coûtent le même nombre de requêtes à l'aperçu, et chaque
proposition est égale à celle de `suggerer_creneau` unitaire.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.installations.tests_aprf41_replanification_lot"
"""
import datetime

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from apps.installations import selectors, services
from apps.installations.models import Installation, Intervention
from apps.installations.models_indispo import IndisponibiliteRessource

User = get_user_model()


class ReplanificationLotTests(TestCase):
    def setUp(self):
        from authentication.models import Company
        self.company, _ = Company.objects.get_or_create(
            slug='co-aprf41', defaults={'nom': 'Co APRF41'})
        self.jour = datetime.date.today() + datetime.timedelta(days=3)
        self.absent = self._user('absent')
        self.libres = [self._user(f'libre{i}') for i in range(3)]
        self.inst = Installation.objects.create(
            company=self.company, reference='APRF41-0',
            statut=Installation.Statut.EN_COURS)
        # Les techniciens libres sont « éligibles » (déjà affectés) avec des
        # charges variées, hors du jour à replanifier.
        for k, tech in enumerate(self.libres):
            for d in range(k + 1):
                self._interv(self.inst, tech,
                             self.jour + datetime.timedelta(days=5 + d))
        IndisponibiliteRessource.objects.create(
            company=self.company, technicien=self.libres[0],
            date_debut=datetime.date.today() + datetime.timedelta(days=1),
            date_fin=datetime.date.today() + datetime.timedelta(days=2))
        self.n = 0

    def _user(self, nom):
        return User.objects.create_user(
            username=f'{nom}-aprf41', password='x', company=self.company,
            role_legacy='technicien')

    def _interv(self, inst, tech, jour):
        return Intervention.objects.create(
            company=self.company, installation=inst,
            type_intervention=Intervention.Type.POSE,
            statut=Intervention.Statut.PRETE, technicien=tech,
            date_prevue=jour)

    def _a_replanifier(self, nb):
        for _ in range(nb):
            self.n += 1
            inst = Installation.objects.create(
                company=self.company, reference=f'APRF41-{self.n}',
                statut=Installation.Statut.EN_COURS)
            self._interv(inst, self.absent, self.jour)

    def _apercu(self):
        with CaptureQueriesContext(connection) as ctx:
            res = services.previsualiser_replanification_masse(
                self.company, jour=self.jour, technicien_id=self.absent.id)
        return len(ctx.captured_queries), res

    def test_apercu_requetes_identiques_a_deux_tailles(self):
        self._a_replanifier(2)
        n2, res2 = self._apercu()
        self._a_replanifier(4)
        n6, res6 = self._apercu()
        self.assertEqual((len(res2['propositions']), len(res6['propositions'])),
                         (2, 6))
        self.assertEqual(n2, n6, (n2, n6))

    def test_lot_egal_a_l_unitaire(self):
        self._a_replanifier(3)
        chantiers = list(Installation.objects.filter(
            company=self.company).values_list('id', flat=True))
        lot = selectors.suggerer_creneaux_lot(self.company, chantiers, n=10)
        for cid in chantiers:
            unitaire = selectors.suggerer_creneau(
                self.company, chantier_id=cid,
                type_intervention=Intervention.Type.POSE, n=10)
            self.assertEqual(lot[cid], unitaire, cid)
        # Le technicien en congé n'est proposé aucun des jours de congé.
        conge = {str(datetime.date.today() + datetime.timedelta(days=d))
                 for d in (1, 2)}
        for cid in chantiers:
            for p in lot[cid]['propositions']:
                if p['technicien_id'] == self.libres[0].id:
                    self.assertNotIn(p['date'], conge)

    def test_appliquer_persiste_le_creneau_choisi(self):
        self._a_replanifier(3)
        apercu = services.previsualiser_replanification_masse(
            self.company, jour=self.jour, technicien_id=self.absent.id)
        attendu = {p['intervention_id']: p['proposition']
                   for p in apercu['propositions']}
        res = services.appliquer_replanification_masse(
            self.company, jour=self.jour, motif='absence', user=self.libres[0],
            technicien_id=self.absent.id)
        self.assertEqual(len(res['deplacees']) + len(res['non_resolues']), 3)
        for d in res['deplacees']:
            iv = Intervention.objects.get(id=d['intervention_id'])
            prop = attendu[iv.id]
            self.assertEqual(iv.technicien_id, prop['technicien_id'])
            self.assertEqual(str(iv.date_prevue), prop['date'])
