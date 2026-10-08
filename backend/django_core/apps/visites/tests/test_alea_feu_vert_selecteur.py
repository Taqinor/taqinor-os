"""ALEA5 — sélecteur public ``visite_feu_vert(company_id, lead_id)``.

Le feu vert n'existe que si la visite LA PLUS RÉCENTE du lead est VALIDÉE ;
le parcours est joué par le vrai viewset HTTP (aucun mock).
"""
from apps.crm.models import Lead
from apps.visites import selectors
from apps.visites.models import VisiteTerrain
from apps.visites.tests.test_visite_terrain import VisiteTerrainBase, auth


class FeuVertSelecteurTests(VisiteTerrainBase):
    def setUp(self):
        super().setUp()
        self.api_bureau = auth(self.bureau)

    def _terminer(self, visite_id):
        self.remplir(visite_id)
        resp = self.api.post(
            f'/api/django/visites/visites/{visite_id}/terminer/', {},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)

    def _valider(self, visite_id):
        resp = self.api_bureau.post(
            f'/api/django/visites/visites/{visite_id}/valider/', {},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)

    def _renvoyer(self, visite_id):
        resp = self.api_bureau.post(
            f'/api/django/visites/visites/{visite_id}/renvoyer/',
            {'photos': [], 'mesures': [], 'motif': 'Reprendre la toiture.'},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)

    def _feu_vert(self):
        return selectors.visite_feu_vert(self.company.id, self.lead.id)

    def test_none_sans_visite(self):
        self.assertIsNone(self._feu_vert())

    def test_none_apres_terminer(self):
        visite_id = self.creer_visite()
        self._terminer(visite_id)
        self.assertIsNone(self._feu_vert())
        # Persistance : lecture pure, même résultat après rechargement.
        VisiteTerrain.objects.get(pk=visite_id).refresh_from_db()
        self.lead.refresh_from_db()
        self.assertIsNone(self._feu_vert())

    def test_dict_apres_valider(self):
        visite_id = self.creer_visite()
        self._terminer(visite_id)
        self._valider(visite_id)
        visite = VisiteTerrain.objects.get(pk=visite_id)
        self.assertIsNotNone(visite.validee_le)
        attendu = {
            'visite_id': visite.id,
            'validee_le': visite.validee_le,
            'validee_par_id': self.bureau.id,
        }
        self.assertEqual(self._feu_vert(), attendu)
        visite.refresh_from_db()
        self.lead.refresh_from_db()
        self.assertEqual(self._feu_vert(), attendu)
        # Lecture pure : la visite n'a pas bougé.
        visite.refresh_from_db()
        self.assertEqual(visite.statut, VisiteTerrain.Statut.VALIDEE)

    def test_none_apres_renvoyer(self):
        visite_id = self.creer_visite()
        self._terminer(visite_id)
        self._valider(visite_id)
        self._renvoyer(visite_id)
        self.assertIsNone(self._feu_vert())

    def test_none_quand_la_plus_recente_n_est_pas_validee(self):
        """Lead à deux visites : l'ancienne VALIDÉE, la plus récente
        renvoyée — le feu vert de l'ancienne ne survit pas."""
        VisiteTerrain.objects.create(
            company=self.company, lead=self.lead,
            statut=VisiteTerrain.Statut.VALIDEE)
        VisiteTerrain.objects.create(
            company=self.company, lead=self.lead,
            statut=VisiteTerrain.Statut.A_REFAIRE)
        self.assertIsNone(self._feu_vert())

    def test_borne_societe(self):
        visite_id = self.creer_visite()
        self._terminer(visite_id)
        self._valider(visite_id)
        self.assertIsNotNone(self._feu_vert())
        # Le lead de A interrogé au nom de la société B : rien.
        self.assertIsNone(
            selectors.visite_feu_vert(self.autre.id, self.lead.id))
        # Un lead de B, même validé, n'est pas vu depuis A.
        VisiteTerrain.objects.create(
            company=self.autre, lead=self.lead_etranger,
            statut=VisiteTerrain.Statut.VALIDEE)
        self.assertIsNone(
            selectors.visite_feu_vert(self.company.id, self.lead_etranger.id))
        self.assertIsNotNone(
            selectors.visite_feu_vert(self.autre.id, self.lead_etranger.id))

    def test_ne_lit_pas_visite_effectuee(self):
        Lead.objects.filter(pk=self.lead.pk).update(visite_effectuee=True)
        self.assertIsNone(self._feu_vert())
