"""CIQ628 — réserves de réception au niveau du chantier (bloquante ou non,
échéance, responsable), exigées par « conforme avec réserves ».
"""
import json
from pathlib import Path

from django.test import TestCase

from apps.installations.models import (
    Installation, Intervention, Reserve, StageModele,
)
from apps.installations.services import (
    ESSAIS_RECETTE, _gardes_ci, ensure_commissioning_record, seed_stages,
    stage_gate_status,
)
from apps.installations.tests_ch3_commissioning import (
    BASE, auth, make_company, make_installation, make_user,
)

TOUS_VRAIS = {champ: True for champ in ESSAIS_RECETTE}
_CONTRAT = (Path(__file__).resolve().parent / 'contract_samples'
            / 'recette_ci.json')


class ReservesChantierTests(TestCase):
    def setUp(self):
        self.company = make_company()
        seed_stages(self.company)
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.inst = make_installation(self.company)
        self.url = f'{BASE}/chantiers/{self.inst.id}/reserves/'

    def _ajouter(self, **corps):
        corps.setdefault('description', 'Étiquette manquante coffret AC')
        return self.api.post(self.url, corps, format='json')

    def _stage_remise(self):
        return StageModele.objects.get(company=self.company,
                                       cle='remise_client')

    def test_reserve_bloquante_ouverte_remise_refusee_puis_levee(self):
        r = self._ajouter(bloquante=True, origine='recette',
                          date_echeance='2026-10-26',
                          responsable='Équipe pose')
        self.assertEqual(r.status_code, 201, r.data)
        statut = stage_gate_status(self.inst, self._stage_remise())
        self.assertTrue(any('Étiquette manquante coffret AC' in raison
                            for raison in statut['raisons']), statut)
        r = self.api.post(f"{self.url}{r.data['id']}/lever/", {},
                          format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['statut'], 'resolue')
        self.assertIsNotNone(r.data['levee_le'])
        statut = stage_gate_status(self.inst, self._stage_remise())
        self.assertFalse(any('Réserve' in raison
                             for raison in statut['raisons']), statut)
        reserve = Reserve.objects.get(pk=r.data['id'])
        self.assertEqual(reserve.levee_par, self.user)

    def test_reserve_non_bloquante_listee_sans_bloquer(self):
        self._ajouter(bloquante=False, description='Nettoyage final')
        statut = stage_gate_status(self.inst, self._stage_remise())
        self.assertFalse(any('Nettoyage' in r for r in statut['raisons']))
        self.assertTrue(any('Nettoyage' in a
                            for a in statut['avertissements']))

    def test_conforme_avec_reserves_sans_reserve_400_fr(self):
        rec = ensure_commissioning_record(self.inst)
        url = f'{BASE}/recettes-commissioning/{rec.id}/'
        r = self.api.patch(url, dict(TOUS_VRAIS, resultat='reserves'),
                           format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('réserve de recette', str(r.data['resultat']))
        self._ajouter(origine='recette')
        r = self.api.patch(url, dict(TOUS_VRAIS, resultat='reserves'),
                           format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['resultat'], 'reserves')

    def test_reserve_d_une_autre_societe_404(self):
        autre = make_company()
        inst_autre = make_installation(autre)
        reserve = Reserve.objects.create(
            company=autre, installation=inst_autre, description='X',
            origine='recette')
        r = self.api.post(f'{self.url}{reserve.id}/lever/', {},
                          format='json')
        self.assertEqual(r.status_code, 404)
        r = self.api.get(f'{BASE}/chantiers/{inst_autre.id}/reserves/')
        self.assertEqual(r.status_code, 404)

    def test_company_jamais_prise_du_corps(self):
        autre = make_company()
        r = self._ajouter(company=autre.id)
        self.assertEqual(r.status_code, 201)
        self.assertEqual(Reserve.objects.get(pk=r.data['id']).company,
                         self.company)

    def test_reserves_d_intervention_inchangees_et_listees(self):
        interv = Intervention.objects.create(
            company=self.company, installation=self.inst)
        Reserve.objects.create(company=self.company, intervention=interv,
                               description='Reprise câble')
        r = self.api.get(self.url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual([x['origine'] for x in r.data], ['intervention'])

    def test_sortie_conforme_au_contrat(self):
        contrat = json.loads(_CONTRAT.read_text(encoding='utf-8'))
        modele = contrat['exemple']['reserves'][0]
        r = self._ajouter(origine='recette', date_echeance='2026-10-26')
        self.assertEqual(set(r.data), set(modele))
        ensure_commissioning_record(self.inst)
        r = self.api.get(f'{BASE}/chantiers/{self.inst.id}/recette/')
        self.assertEqual(set(r.data['reserves'][0]), set(modele))

    def test_gardes_ci_refuse_receptionne_avec_bloquante(self):
        self.inst.type_installation = 'industriel'
        self.inst.regime_8221 = 'declaration_bt'
        self.inst.statut = Installation.Statut.INSTALLE
        self.inst.save()
        Reserve.objects.create(company=self.company, installation=self.inst,
                               description='Garde-corps', bloquante=True,
                               origine='reception')
        raisons = _gardes_ci(self.inst, Installation.Statut.RECEPTIONNE)
        self.assertTrue(any('Garde-corps' in r for r in raisons), raisons)
