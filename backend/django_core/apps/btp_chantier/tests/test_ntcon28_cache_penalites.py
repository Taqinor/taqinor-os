"""NTCON28 — cache quotidien de l'exposition aux pénalités par lot.

Ce que le test PROUVE :
  * le balayage fige le résultat NTCON15 sur ``Lot.penalite_calculee_cache``
    (+ horodatage) — aucune SECONDE formule : le cache vaut exactement ce que
    ``selectors.penalites_retard_par_lot`` calcule ;
  * l'API sert le CACHE quand il est frais (``source='cache'``) et retombe sur
    le calcul quand il est absent ou vieux (``source='calcul'``) — jamais un
    chiffre périmé servi en silence ;
  * le périmètre par défaut se limite aux chantiers ayant un lot en retard
    ACTIF ; ``--tous`` force le balayage complet ;
  * un recalcul manuel forcé est possible (POST) ;
  * cross-tenant : le cache d'une société n'est jamais servi à une autre.
"""
from datetime import timedelta
from decimal import Decimal

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from rest_framework import status

from apps.btp_chantier import selectors, services
from apps.btp_chantier.models import Lot

from .helpers import auth, make_chantier, make_company, make_user


def _url(chantier_id):
    return f'/api/django/btp-chantier/chantiers/{chantier_id}/penalites-par-lot/'


class CachePenalitesLotsTests(TestCase):
    def setUp(self):
        self.co = make_company()
        self.chantier = make_chantier(self.co)
        self.user = make_user(self.co, role='responsable')
        self.aujourdhui = timezone.localdate()

    def _lot(self, *, retard_jours=12, chantier=None, company=None,
             statut=Lot.Statut.EN_COURS, nom='Gros œuvre'):
        return Lot.objects.create(
            company=company or self.co, chantier=chantier or self.chantier,
            nom=nom, jalon_contractuel=True,
            date_debut_prevue=self.aujourdhui - timedelta(days=90),
            date_fin_prevue=self.aujourdhui - timedelta(days=retard_jours),
            montant_ht=Decimal('250000.00'),
            taux_penalite_retard_pmil=Decimal('1.000'),
            plafond_penalite_pct=Decimal('5.00'),
            statut=statut)

    # ── le balayage fige exactement le calcul NTCON15 ───────────────────────
    def test_cache_egal_au_calcul_ntcon15(self):
        lot = self._lot()
        attendu = selectors.penalites_retard_par_lot(self.chantier)
        ligne_attendue = attendu['lots'][0]

        services.recalculer_penalites_lots()
        lot.refresh_from_db()

        self.assertIsNotNone(lot.penalite_calculee_cache)
        self.assertIsNotNone(lot.penalite_calculee_le)
        cache = lot.penalite_calculee_cache
        self.assertEqual(cache['lot_id'], lot.id)
        self.assertEqual(
            cache['jours_depassement'], ligne_attendue['jours_depassement'])
        # Montants stockés en CHAÎNE (jamais en float — pas de centime perdu).
        self.assertEqual(cache['exposition'], str(ligne_attendue['exposition']))
        self.assertIsInstance(cache['exposition'], str)
        self.assertTrue(cache['applicable'])

    def test_perimetre_par_defaut_limite_aux_lots_en_retard(self):
        autre_chantier = make_chantier(self.co)
        en_retard = self._lot()
        a_lheure = Lot.objects.create(
            company=self.co, chantier=autre_chantier, nom='Peinture',
            jalon_contractuel=True,
            date_fin_prevue=self.aujourdhui + timedelta(days=30),
            montant_ht=Decimal('10000.00'),
            taux_penalite_retard_pmil=Decimal('1.000'))
        resultat = services.recalculer_penalites_lots()
        en_retard.refresh_from_db()
        a_lheure.refresh_from_db()
        self.assertEqual(resultat['chantiers'], 1)
        self.assertIsNotNone(en_retard.penalite_calculee_cache)
        self.assertIsNone(a_lheure.penalite_calculee_cache)

    def test_option_tous_balaye_meme_sans_retard(self):
        autre_chantier = make_chantier(self.co)
        a_lheure = Lot.objects.create(
            company=self.co, chantier=autre_chantier, nom='Peinture',
            jalon_contractuel=True,
            date_fin_prevue=self.aujourdhui + timedelta(days=30),
            montant_ht=Decimal('10000.00'),
            taux_penalite_retard_pmil=Decimal('1.000'))
        services.recalculer_penalites_lots(tous=True)
        a_lheure.refresh_from_db()
        self.assertIsNotNone(a_lheure.penalite_calculee_cache)
        self.assertEqual(a_lheure.penalite_calculee_cache['jours_depassement'], 0)

    def test_lot_termine_fige_son_retard(self):
        """Non-régression NTCON15 : un lot terminé ne court plus."""
        lot = self._lot(statut=Lot.Statut.TERMINE)
        lot.date_fin_reelle = self.aujourdhui - timedelta(days=10)
        lot.save(update_fields=['date_fin_reelle'])
        services.recalculer_penalites_lots(tous=True)
        lot.refresh_from_db()
        self.assertEqual(lot.penalite_calculee_cache['jours_depassement'], 2)

    def test_commande_de_gestion(self):
        lot = self._lot()
        call_command('recalculer_penalites_lots')
        lot.refresh_from_db()
        self.assertIsNotNone(lot.penalite_calculee_cache)

    def test_commande_un_seul_chantier(self):
        autre_chantier = make_chantier(self.co)
        mien = self._lot()
        sien = self._lot(chantier=autre_chantier, nom='Charpente')
        call_command('recalculer_penalites_lots',
                     f'--chantier={self.chantier.id}')
        mien.refresh_from_db()
        sien.refresh_from_db()
        self.assertIsNotNone(mien.penalite_calculee_cache)
        self.assertIsNone(sien.penalite_calculee_cache)

    # ── lecture : cache frais vs cache périmé ──────────────────────────────
    def test_api_sert_le_cache_quand_frais(self):
        self._lot()
        services.recalculer_penalites_lots()
        resp = auth(self.user).get(_url(self.chantier.id))
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)
        self.assertEqual(resp.data['source'], 'cache')
        self.assertEqual(len(resp.data['lots']), 1)
        self.assertIsNotNone(resp.data['calcule_le'])

    def test_api_recalcule_si_cache_absent(self):
        self._lot()
        resp = auth(self.user).get(_url(self.chantier.id))
        self.assertEqual(resp.data['source'], 'calcul')
        self.assertEqual(len(resp.data['lots']), 1)

    def test_api_recalcule_si_cache_perime(self):
        lot = self._lot()
        services.recalculer_penalites_lots()
        Lot.objects.filter(pk=lot.pk).update(
            penalite_calculee_le=timezone.now() - timedelta(hours=48))
        resp = auth(self.user).get(_url(self.chantier.id))
        self.assertEqual(resp.data['source'], 'calcul')

    def test_parametre_frais_ignore_le_cache(self):
        self._lot()
        services.recalculer_penalites_lots()
        resp = auth(self.user).get(_url(self.chantier.id), {'frais': '1'})
        self.assertEqual(resp.data['source'], 'calcul')

    def test_recalcul_manuel_force_par_post(self):
        lot = self._lot()
        resp = auth(self.user).post(_url(self.chantier.id), {}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)
        self.assertEqual(resp.data['source'], 'cache')
        lot.refresh_from_db()
        self.assertIsNotNone(lot.penalite_calculee_cache)

    def test_total_du_cache_coherent_avec_le_calcul(self):
        self._lot()
        self._lot(nom='Charpente', retard_jours=5)
        attendu = selectors.penalites_retard_par_lot(self.chantier)
        services.recalculer_penalites_lots()
        resp = auth(self.user).get(_url(self.chantier.id))
        self.assertEqual(resp.data['source'], 'cache')
        self.assertEqual(
            Decimal(str(resp.data['total_exposition'])),
            attendu['total_exposition'])

    # ── multi-tenant ───────────────────────────────────────────────────────
    def test_cross_tenant_404(self):
        autre = make_company()
        chantier_autre = make_chantier(autre)
        self._lot(company=autre, chantier=chantier_autre)
        services.recalculer_penalites_lots()
        resp = auth(self.user).get(_url(chantier_autre.id))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_balayage_par_societe(self):
        autre = make_company()
        chantier_autre = make_chantier(autre)
        mien = self._lot()
        sien = self._lot(company=autre, chantier=chantier_autre)
        services.recalculer_penalites_lots(company=self.co)
        mien.refresh_from_db()
        sien.refresh_from_db()
        self.assertIsNotNone(mien.penalite_calculee_cache)
        self.assertIsNone(sien.penalite_calculee_cache)
