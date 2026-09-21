"""NTCON27 — archivage (jamais suppression) des réserves levées anciennes.

Ce que le test PROUVE :
  * le balayage marque ``archivee=True`` — la ligne EXISTE toujours, avec sa
    signature et son historique (aucune suppression physique) ;
  * il est IDEMPOTENT : un second passage n'archive rien de plus ;
  * les réserves archivées sortent des listes actives et restent accessibles
    par le filtre EXPLICITE ``?archivee=1`` ;
  * le seuil est un réglage PAR SOCIÉTÉ (défaut 24 mois) : deux sociétés aux
    réglages différents n'archivent pas les mêmes réserves ;
  * aucune réserve NON levée (ouverte/en cours/contestée) n'est jamais
    touchée, quelle que soit son ancienneté.
"""
from datetime import timedelta

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from rest_framework import status

from apps.btp_chantier import selectors, services
from apps.btp_chantier.models import (
    ParametresBtpChantier, ReserveChantier, ReserveChantierHistorique,
)

from .helpers import auth, make_chantier, make_company, make_user

RACINE = '/api/django/btp-chantier/reserves-chantier/'


def _ids(resp):
    """Identifiants d'une réponse de liste (paginée ou non)."""
    data = resp.data
    lignes = data['results'] if isinstance(data, dict) else data
    return {ligne['id'] for ligne in lignes}


class ArchivageReservesLeveesTests(TestCase):
    def setUp(self):
        self.co = make_company()
        self.chantier = make_chantier(self.co)
        self.user = make_user(self.co, role='responsable')
        self.maintenant = timezone.now()

    def _reserve(self, *, statut=ReserveChantier.Statut.LEVEE, mois=30,
                 company=None, chantier=None):
        """Réserve dont ``date_levee`` remonte à ``mois`` mois."""
        company = company or self.co
        reserve = ReserveChantier.objects.create(
            company=company, chantier=chantier or self.chantier,
            lot='électricité',
            localisation_plan={'document_ged_id': 1, 'x': 0.1, 'y': 0.2},
            description='Prise à reprendre', gravite='majeure', statut=statut,
            created_by=self.user)
        quand = self.maintenant - timedelta(days=30 * mois)
        ReserveChantier.objects.filter(pk=reserve.pk).update(
            date_levee=quand if statut == ReserveChantier.Statut.LEVEE
            else None,
            updated_at=quand)
        reserve.refresh_from_db()
        return reserve

    # ── comportement du balayage ───────────────────────────────────────────
    def test_archive_une_reserve_levee_ancienne(self):
        vieille = self._reserve(mois=30)
        resultat = services.archiver_reserves_levees(
            maintenant=self.maintenant)
        self.assertEqual(resultat['archivees'], 1)
        vieille.refresh_from_db()
        self.assertTrue(vieille.archivee)
        self.assertIsNotNone(vieille.archivee_le)

    def test_jamais_de_suppression_physique(self):
        """La ligne, son historique et son statut survivent à l'archivage."""
        vieille = self._reserve(mois=36)
        ReserveChantierHistorique.objects.create(
            company=self.co, reserve=vieille, ancien_statut='ouverte',
            nouveau_statut='levee', auteur=self.user)
        services.archiver_reserves_levees(maintenant=self.maintenant)
        vieille.refresh_from_db()
        self.assertEqual(ReserveChantier.objects.filter(pk=vieille.pk).count(), 1)
        self.assertEqual(vieille.statut, ReserveChantier.Statut.LEVEE)
        self.assertEqual(
            ReserveChantierHistorique.objects.filter(reserve=vieille).count(), 1)

    def test_recente_non_archivee(self):
        recente = self._reserve(mois=6)
        services.archiver_reserves_levees(maintenant=self.maintenant)
        recente.refresh_from_db()
        self.assertFalse(recente.archivee)

    def test_reserve_non_levee_jamais_archivee(self):
        for statut in (ReserveChantier.Statut.OUVERTE,
                       ReserveChantier.Statut.EN_COURS,
                       ReserveChantier.Statut.CONTESTEE):
            with self.subTest(statut=statut):
                ouverte = self._reserve(statut=statut, mois=60)
                services.archiver_reserves_levees(maintenant=self.maintenant)
                ouverte.refresh_from_db()
                self.assertFalse(ouverte.archivee)

    def test_sweep_idempotent(self):
        self._reserve(mois=30)
        premier = services.archiver_reserves_levees(maintenant=self.maintenant)
        second = services.archiver_reserves_levees(maintenant=self.maintenant)
        self.assertEqual(premier['archivees'], 1)
        self.assertEqual(second['archivees'], 0)
        self.assertEqual(second['examines'], 0)

    def test_seuil_par_societe(self):
        """Deux sociétés, deux réglages : le seuil global serait faux."""
        autre = make_company()
        autre_chantier = make_chantier(autre)
        autre_user = make_user(autre, role='responsable')
        ParametresBtpChantier.objects.create(
            company=autre, delai_archivage_reserves_levees_mois=6)
        # 12 mois : sous le défaut de 24 (société 1), au-dessus de 6 (société 2)
        chez_nous = self._reserve(mois=12)
        chez_eux = ReserveChantier.objects.create(
            company=autre, chantier=autre_chantier, lot='CVC',
            localisation_plan={'document_ged_id': 3, 'x': 0.4, 'y': 0.4},
            description='Gaine', gravite='mineure',
            statut=ReserveChantier.Statut.LEVEE, created_by=autre_user)
        ReserveChantier.objects.filter(pk=chez_eux.pk).update(
            date_levee=self.maintenant - timedelta(days=360))

        services.archiver_reserves_levees(maintenant=self.maintenant)
        chez_nous.refresh_from_db()
        chez_eux.refresh_from_db()
        self.assertFalse(chez_nous.archivee)
        self.assertTrue(chez_eux.archivee)

    def test_limite_a_une_societe_quand_demande(self):
        autre = make_company()
        autre_chantier = make_chantier(autre)
        mienne = self._reserve(mois=30)
        sienne = self._reserve(mois=30, company=autre, chantier=autre_chantier)
        services.archiver_reserves_levees(
            company=self.co, maintenant=self.maintenant)
        mienne.refresh_from_db()
        sienne.refresh_from_db()
        self.assertTrue(mienne.archivee)
        self.assertFalse(sienne.archivee)

    # ── commande de gestion ────────────────────────────────────────────────
    def test_commande_de_gestion(self):
        vieille = self._reserve(mois=30)
        call_command('archiver_reserves_levees')
        vieille.refresh_from_db()
        self.assertTrue(vieille.archivee)

    # ── listes actives ─────────────────────────────────────────────────────
    def test_sortie_des_listes_actives_mais_toujours_accessible(self):
        vieille = self._reserve(mois=30)
        active = self._reserve(statut=ReserveChantier.Statut.OUVERTE, mois=1)
        services.archiver_reserves_levees(maintenant=self.maintenant)

        api = auth(self.user)
        ids_defaut = _ids(api.get(RACINE))
        self.assertIn(active.id, ids_defaut)
        self.assertNotIn(vieille.id, ids_defaut)

        ids_archivees = _ids(api.get(RACINE, {'archivee': '1'}))
        self.assertEqual(ids_archivees, {vieille.id})

        ids_toutes = _ids(api.get(RACINE, {'archivee': 'all'}))
        self.assertTrue({vieille.id, active.id}.issubset(ids_toutes))

        # La fiche reste consultable au détail (rien n'est supprimé).
        self.assertEqual(
            api.get(f'{RACINE}{vieille.id}/').status_code, status.HTTP_200_OK)

    def test_selecteur_filtre_par_defaut(self):
        vieille = self._reserve(mois=30)
        services.archiver_reserves_levees(maintenant=self.maintenant)
        qs = ReserveChantier.objects.filter(company=self.co)
        self.assertNotIn(
            vieille.pk,
            selectors.reserves_filtrees(qs).values_list('pk', flat=True))
        self.assertIn(
            vieille.pk,
            selectors.reserves_filtrees(
                qs, archivee=True).values_list('pk', flat=True))
