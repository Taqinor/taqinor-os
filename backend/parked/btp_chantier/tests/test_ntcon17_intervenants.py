"""Tests NTCON17 — Registre des intervenants chantier (coordination SPS).

Couvre : agrégation d'un chantier multi-sous-traitants (ordres actifs FG305 +
attestations FG307 + PPSPS signé NTCON16), effectifs du jour (dernier
``JournalChantier`` NTCON6), titres RH à risque (FG170/173/174), signalement
explicite d'une attestation EXPIRÉE, et isolation multi-société.
Lecture seule : la vue n'écrit jamais.
"""
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework import status

from apps.btp_chantier import services
from apps.btp_chantier.models import JournalChantier, PPSPSChantier

from .helpers import (
    auth, make_attestation_sous_traitant, make_chantier, make_company,
    make_employe, make_fournisseur, make_habilitation,
    make_ordre_sous_traitance, make_presence_chantier, make_user,
)

INTERVENANTS = '/api/django/btp-chantier/chantiers/{}/intervenants/'


class RegistreIntervenantsTests(TestCase):
    def setUp(self):
        self.co = make_company()
        self.user = make_user(self.co)
        self.chantier = make_chantier(self.co)
        self.jour = timezone.localdate()
        self.api = auth(self.user)

        # Deux sous-traitants : l'un à jour, l'autre avec une pièce expirée.
        self.st_ok = make_fournisseur(self.co)
        self.st_expire = make_fournisseur(self.co)
        make_attestation_sous_traitant(
            self.co, self.st_ok, type_piece='cnss', obligatoire=True,
            date_expiration=self.jour + timedelta(days=90))
        make_attestation_sous_traitant(
            self.co, self.st_expire, type_piece='cnss', obligatoire=True,
            date_expiration=self.jour - timedelta(days=5))
        self.ordre_ok = make_ordre_sous_traitance(
            self.co, self.chantier, self.st_ok, statut='emis')
        self.ordre_expire = make_ordre_sous_traitance(
            self.co, self.chantier, self.st_expire, statut='emis')
        # Un ordre CLOS ne fait plus partie des intervenants actifs.
        st_clos = make_fournisseur(self.co)
        make_ordre_sous_traitance(
            self.co, self.chantier, st_clos, statut='clos')

        JournalChantier.objects.create(
            company=self.co, chantier=self.chantier, date=self.jour,
            effectif_interne={'macon': 4, 'electricien': 2},
            effectif_sous_traitant={'1': 3})

    def test_liste_les_sous_traitants_actifs_seulement(self):
        resp = self.api.get(INTERVENANTS.format(self.chantier.id))
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        ids = {s['ordre_id'] for s in resp.data['sous_traitants']}
        self.assertEqual(ids, {self.ordre_ok.id, self.ordre_expire.id})

    def test_attestation_expiree_signalee(self):
        resp = self.api.get(INTERVENANTS.format(self.chantier.id))
        par_ordre = {
            s['ordre_id']: s for s in resp.data['sous_traitants']}
        self.assertTrue(par_ordre[self.ordre_ok.id]['attestations_a_jour'])
        self.assertFalse(par_ordre[self.ordre_expire.id]['attestations_a_jour'])
        self.assertEqual(
            par_ordre[self.ordre_expire.id]['attestations_manquantes'][0]
            ['type_piece'], 'cnss')
        self.assertTrue(any(
            'expirée' in a for a in resp.data['alertes']))

    def test_effectifs_du_jour_depuis_le_journal(self):
        resp = self.api.get(INTERVENANTS.format(self.chantier.id))
        effectifs = resp.data['effectifs_du_jour']
        self.assertEqual(effectifs['total_interne'], 6)
        self.assertEqual(effectifs['effectif_interne']['macon'], 4)

    def test_ppsps_non_signe_remonte_en_alerte(self):
        ppsps = PPSPSChantier.objects.create(
            company=self.co, chantier=self.chantier,
            date_validation=self.jour)
        services.signer_ppsps(
            ppsps, sous_traitant=self.st_ok, signataire_nom='M. Alaoui')
        resp = self.api.get(INTERVENANTS.format(self.chantier.id))
        par_ordre = {s['ordre_id']: s for s in resp.data['sous_traitants']}
        self.assertTrue(par_ordre[self.ordre_ok.id]['ppsps_signe'])
        self.assertFalse(par_ordre[self.ordre_expire.id]['ppsps_signe'])
        self.assertTrue(any(
            'PPSPS du chantier' in a for a in resp.data['alertes']))

    def test_personnel_interne_et_titre_expire(self):
        employe = make_employe(self.co)
        make_presence_chantier(self.co, employe, self.chantier, self.jour)
        make_habilitation(
            self.co, employe, type_habilitation='b1v',
            date_validite=self.jour - timedelta(days=1))
        resp = self.api.get(INTERVENANTS.format(self.chantier.id))
        personnel = resp.data['personnel_interne']
        self.assertEqual(len(personnel), 1)
        self.assertEqual(personnel[0]['employe_id'], employe.id)
        titres = personnel[0]['titres_a_risque']
        self.assertEqual(len(titres), 1)
        self.assertTrue(titres[0]['expiree'])
        # L'alerte SPS nomme le titre échu (libellé NF C 18-510).
        self.assertTrue(any('B1V' in a for a in resp.data['alertes']))

    def test_cross_tenant_refuse(self):
        autre = make_company()
        chantier_autre = make_chantier(autre)
        resp = self.api.get(INTERVENANTS.format(chantier_autre.id))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
