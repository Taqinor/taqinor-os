"""Tests NTCON25 — Réglages BTP par tenant.

Couvre : singleton par société créé à la demande avec les défauts du module,
écriture réservée aux ADMINISTRATEURS, EFFET IMMÉDIAT sur les guards NTCON16
(PPSPS) et NTCON19 (checklist de lot), validation des lots types, et isolation
STRICTE entre sociétés (un réglage d'une société n'affecte jamais l'autre).
"""
from django.core.exceptions import PermissionDenied
from django.test import TestCase
from rest_framework import status

from apps.btp_chantier import services
from apps.btp_chantier.models import (
    Lot, LotChecklistItem, LOTS_TYPES_DEFAUT, ParametresBtpChantier,
    PPSPSChantier,
)

from .helpers import (
    auth, make_chantier, make_company, make_fournisseur, make_lot,
    make_ordre_sous_traitance, make_user,
)

PARAMETRES = '/api/django/btp-chantier/parametres/'


class ParametresBtpApiTests(TestCase):
    def setUp(self):
        self.co = make_company()
        self.admin = make_user(self.co, role='admin')
        self.responsable = make_user(self.co, role='responsable')

    def test_get_cree_le_singleton_avec_les_defauts(self):
        resp = auth(self.responsable).get(PARAMETRES)
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertTrue(resp.data['guard_ppsps_bloquant'])
        self.assertTrue(resp.data['guard_checklist_lot_bloquant'])
        self.assertEqual(resp.data['delai_reponse_rfi_defaut_jours'], 5)
        self.assertEqual(resp.data['lots_types_defaut'], LOTS_TYPES_DEFAUT)
        self.assertEqual(
            ParametresBtpChantier.objects.filter(company=self.co).count(), 1)

    def test_get_est_idempotent(self):
        api = auth(self.responsable)
        api.get(PARAMETRES)
        api.get(PARAMETRES)
        self.assertEqual(
            ParametresBtpChantier.objects.filter(company=self.co).count(), 1)

    def test_ecriture_reservee_aux_administrateurs(self):
        resp = auth(self.responsable).patch(
            PARAMETRES, {'guard_ppsps_bloquant': False}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_modifie_les_reglages(self):
        resp = auth(self.admin).patch(PARAMETRES, {
            'guard_ppsps_bloquant': False,
            'delai_revue_visa_defaut_jours': 15,
            'taux_penalite_retard_defaut_pmil': '1.500',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertFalse(resp.data['guard_ppsps_bloquant'])
        self.assertEqual(resp.data['delai_revue_visa_defaut_jours'], 15)

    def test_lots_types_invalides_refuses(self):
        resp = auth(self.admin).patch(
            PARAMETRES, {'lots_types_defaut': ['Gros-œuvre', '  ']},
            format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('lots_types_defaut', resp.data)

    def test_taux_negatif_refuse(self):
        resp = auth(self.admin).patch(
            PARAMETRES, {'taux_penalite_retard_defaut_pmil': '-1.000'},
            format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('taux_penalite_retard_defaut_pmil', resp.data)


class EffetImmediatDesGuardsTests(TestCase):
    """Modifier un réglage change le comportement du guard IMMÉDIATEMENT."""

    def setUp(self):
        self.co = make_company()
        self.admin = make_user(self.co, role='admin')
        self.chantier = make_chantier(self.co)

    def test_guard_ppsps_desactive_laisse_demarrer(self):
        PPSPSChantier.objects.create(
            company=self.co, chantier=self.chantier,
            date_validation='2026-01-01')
        fournisseur = make_fournisseur(self.co)
        ordre = make_ordre_sous_traitance(
            self.co, self.chantier, fournisseur)

        # Par défaut : bloquant.
        ordre.statut = 'en_cours'
        with self.assertRaises(PermissionDenied):
            ordre.save()

        auth(self.admin).patch(
            PARAMETRES, {'guard_ppsps_bloquant': False}, format='json')

        ordre.refresh_from_db()
        ordre.statut = 'en_cours'
        ordre.save()
        ordre.refresh_from_db()
        self.assertEqual(ordre.statut, 'en_cours')

    def test_guard_checklist_desactive_laisse_receptionner(self):
        lot = make_lot(self.co, self.chantier, nom='Gros-œuvre')
        services.definir_checklist_lot(lot)
        with self.assertRaises(services.TransitionInvalide):
            services.terminer_lot(lot, user=self.admin)

        auth(self.admin).patch(
            PARAMETRES, {'guard_checklist_lot_bloquant': False},
            format='json')

        lot.refresh_from_db()
        services.terminer_lot(lot, user=self.admin)
        lot.refresh_from_db()
        self.assertEqual(lot.statut, Lot.Statut.TERMINE)
        # La checklist reste en place : on l'a seulement rendue non bloquante.
        self.assertTrue(LotChecklistItem.objects.filter(lot=lot).exists())

    def test_reglage_d_une_societe_n_affecte_pas_l_autre(self):
        autre = make_company()
        autre_admin = make_user(autre, role='admin')
        auth(autre_admin).patch(
            PARAMETRES, {'guard_checklist_lot_bloquant': False},
            format='json')

        # Ma société garde le guard BLOQUANT (défaut).
        lot = make_lot(self.co, self.chantier, nom='Électricité')
        services.definir_checklist_lot(lot)
        with self.assertRaises(services.TransitionInvalide):
            services.terminer_lot(lot, user=self.admin)
        self.assertTrue(
            services.config_btp(self.co)['guard_checklist_lot_bloquant'])
        self.assertFalse(
            services.config_btp(autre)['guard_checklist_lot_bloquant'])

    def test_config_btp_sans_ligne_renvoie_les_defauts(self):
        vierge = make_company()
        config = services.config_btp(vierge)
        self.assertEqual(config, services.CONFIG_BTP_DEFAUTS)
        self.assertFalse(
            ParametresBtpChantier.objects.filter(company=vierge).exists())
