"""AUDV25 (DRAFT165-6) — action `reserves-chantier/bloquantes/`.

`selectors.reserves_actives_bloquantes` existait déjà (gravité BLOQUANTE +
statut OUVERTE/EN_COURS) mais aucune action ne l'exposait : un simple filtre
``?statut=`` à valeur unique du ViewSet existant ne peut PAS exprimer un OR
sur deux statuts — le widget « réserves bloquantes actives » du tableau de
bord chantier n'avait donc aucun endpoint à appeler.

Run:
    python manage.py test apps.btp_chantier.tests.test_audv25_reserves_bloquantes -v 2
"""
from django.test import TestCase
from rest_framework import status

from apps.btp_chantier.models import ReserveChantier

from .helpers import auth, make_chantier, make_company, make_user

BASE = '/api/django/btp-chantier/reserves-chantier/bloquantes/'


def _reserve(company, chantier, gravite, statut, **kwargs):
    return ReserveChantier.objects.create(
        company=company, chantier=chantier, gravite=gravite, statut=statut,
        description=kwargs.pop('description', 'X'), **kwargs)


class ReservesBloquantesActionTests(TestCase):
    def setUp(self):
        self.co = make_company()
        self.user = make_user(self.co)
        self.chantier = make_chantier(self.co)

    def test_combine_gravite_bloquante_et_statuts_ouverts(self):
        bloquante_ouverte = _reserve(
            self.co, self.chantier, ReserveChantier.Gravite.BLOQUANTE,
            ReserveChantier.Statut.OUVERTE)
        bloquante_en_cours = _reserve(
            self.co, self.chantier, ReserveChantier.Gravite.BLOQUANTE,
            ReserveChantier.Statut.EN_COURS)
        # Bruit qui ne doit JAMAIS apparaître :
        _reserve(self.co, self.chantier, ReserveChantier.Gravite.MAJEURE,
                 ReserveChantier.Statut.OUVERTE)  # pas bloquante
        _reserve(self.co, self.chantier, ReserveChantier.Gravite.BLOQUANTE,
                 ReserveChantier.Statut.LEVEE)  # bloquante mais levée

        resp = auth(self.user).get(BASE, {'chantier': self.chantier.id})
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        ids = {r['id'] for r in resp.data}
        self.assertEqual(ids, {bloquante_ouverte.id, bloquante_en_cours.id})

    def test_sans_chantier_toute_la_societe(self):
        autre_chantier = make_chantier(self.co)
        r1 = _reserve(self.co, self.chantier, ReserveChantier.Gravite.BLOQUANTE,
                      ReserveChantier.Statut.OUVERTE)
        r2 = _reserve(self.co, autre_chantier, ReserveChantier.Gravite.BLOQUANTE,
                      ReserveChantier.Statut.EN_COURS)
        resp = auth(self.user).get(BASE)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        ids = {r['id'] for r in resp.data}
        self.assertEqual(ids, {r1.id, r2.id})

    def test_aucune_reserve_bloquante_liste_vide(self):
        _reserve(self.co, self.chantier, ReserveChantier.Gravite.MINEURE,
                 ReserveChantier.Statut.OUVERTE)
        resp = auth(self.user).get(BASE, {'chantier': self.chantier.id})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data, [])

    def test_chantier_d_une_autre_societe_liste_vide(self):
        autre_co = make_company()
        autre_chantier = make_chantier(autre_co)
        _reserve(autre_co, autre_chantier, ReserveChantier.Gravite.BLOQUANTE,
                 ReserveChantier.Statut.OUVERTE)
        resp = auth(self.user).get(BASE, {'chantier': autre_chantier.id})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data, [])

    def test_isolation_societe_sans_filtre_chantier(self):
        autre_co = make_company()
        autre_chantier = make_chantier(autre_co)
        _reserve(autre_co, autre_chantier, ReserveChantier.Gravite.BLOQUANTE,
                 ReserveChantier.Statut.OUVERTE)
        resp = auth(self.user).get(BASE)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data, [])
