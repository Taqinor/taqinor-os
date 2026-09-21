"""NTJUR19 — approbation d'un engagement de dépenses juridiques.

Critère d'acceptation : « un mandat à 150 000 MAD au-dessus du seuil reste
bloqué en attente d'approbation avant activation ».
"""
from datetime import date
from decimal import Decimal

from django.test import TestCase

from apps.juridique import services
from apps.juridique.models import (
    CabinetAvocat, DossierJuridique, EtapeApprobationJuridique, MandatAvocat,
    RegleApprobationJuridique,
)

from ._base import auth, make_admin, make_company

DOSSIERS = '/api/django/juridique/dossiers/'
MANDATS = '/api/django/juridique/mandats/'


class ApprobationMandatTests(TestCase):
    def setUp(self):
        self.company = make_company('jur-a19-co', 'Juridique A19')
        self.autre = make_company('jur-a19-autre', 'Juridique A19 Autre')
        self.admin = make_admin(self.company, 'jur-a19-admin')
        self.api = auth(self.admin)
        self.dossier = DossierJuridique.objects.create(
            company=self.company, reference='JUR-2026-0001',
            titre='Contentieux fournisseur', date_ouverture=date(2026, 2, 1),
            nature=DossierJuridique.Nature.CONTENTIEUX)
        self.cabinet = CabinetAvocat.objects.create(
            company=self.company, nom='Cabinet Bennani')
        # Seuil : tout engagement >= 100 000 MAD exige 2 approbations.
        self.regle = RegleApprobationJuridique.objects.create(
            company=self.company, libelle='Engagement > 100 000',
            montant_min=Decimal('100000'), nombre_approbateurs=2)

    def _mandat(self, montant='150000.00'):
        return MandatAvocat.objects.create(
            company=self.company, dossier=self.dossier, cabinet=self.cabinet,
            date_mandat=date(2026, 2, 2),
            mode_facturation=MandatAvocat.ModeFacturation.FORFAIT,
            montant_forfait=Decimal(montant))

    def test_mandat_au_dessus_du_seuil_reste_bloque_avant_activation(self):
        mandat = self._mandat('150000.00')
        resp = self.api.post(f'{MANDATS}{mandat.id}/activer/', {},
                             format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('statut', resp.data)
        mandat.refresh_from_db()
        self.assertEqual(mandat.statut, MandatAvocat.Statut.BROUILLON)

    def test_parcours_complet_lancement_approbations_activation(self):
        mandat = self._mandat('150000.00')
        lance = self.api.post(
            f'{DOSSIERS}{self.dossier.id}/lancer-approbation-mandat/',
            {'mandat': mandat.id}, format='json')
        self.assertEqual(lance.status_code, 201, lance.data)
        self.assertEqual(len(lance.data), 2)
        mandat.refresh_from_db()
        self.assertEqual(mandat.statut, MandatAvocat.Statut.EN_APPROBATION)

        etapes = list(mandat.etapes_approbation.order_by('niveau'))
        # Sauter l'étape 1 est refusé (ordre garanti).
        saut = self.api.post(
            f'{DOSSIERS}{self.dossier.id}/approuver-etape/',
            {'etape': etapes[1].id}, format='json')
        self.assertEqual(saut.status_code, 400, saut.data)

        for etape in etapes:
            ok = self.api.post(
                f'{DOSSIERS}{self.dossier.id}/approuver-etape/',
                {'etape': etape.id}, format='json')
            self.assertEqual(ok.status_code, 200, ok.data)

        # Une étape déjà décidée ne se re-décide pas.
        rejeu = self.api.post(
            f'{DOSSIERS}{self.dossier.id}/approuver-etape/',
            {'etape': etapes[0].id}, format='json')
        self.assertEqual(rejeu.status_code, 400, rejeu.data)

        activ = self.api.post(f'{MANDATS}{mandat.id}/activer/', {},
                              format='json')
        self.assertEqual(activ.status_code, 200, activ.data)
        mandat.refresh_from_db()
        self.assertEqual(mandat.statut, MandatAvocat.Statut.ACTIF)

    def test_rejet_ramene_le_mandat_en_brouillon_et_bloque_l_activation(self):
        mandat = self._mandat('150000.00')
        services.lancer_approbation_mandat(mandat)
        etape = mandat.etapes_approbation.order_by('niveau').first()
        resp = self.api.post(
            f'{DOSSIERS}{self.dossier.id}/rejeter-etape/',
            {'etape': etape.id, 'commentaire': 'Trop cher'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        etape.refresh_from_db()
        self.assertEqual(etape.statut,
                         EtapeApprobationJuridique.Statut.REJETE)
        self.assertEqual(etape.commentaire, 'Trop cher')
        mandat.refresh_from_db()
        self.assertEqual(mandat.statut, MandatAvocat.Statut.BROUILLON)
        blocage = self.api.post(f'{MANDATS}{mandat.id}/activer/', {},
                                format='json')
        self.assertEqual(blocage.status_code, 400, blocage.data)

    def test_mandat_sous_le_seuil_s_active_directement(self):
        mandat = self._mandat('20000.00')
        resp = self.api.post(f'{MANDATS}{mandat.id}/activer/', {},
                             format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        mandat.refresh_from_db()
        self.assertEqual(mandat.statut, MandatAvocat.Statut.ACTIF)

    def test_montant_engage_horaire_compte_les_heures_estimees(self):
        mandat = MandatAvocat.objects.create(
            company=self.company, dossier=self.dossier, cabinet=self.cabinet,
            date_mandat=date(2026, 2, 2),
            mode_facturation=MandatAvocat.ModeFacturation.HORAIRE,
            taux_horaire=Decimal('1500'), heures_estimees=100)
        self.assertEqual(mandat.montant_engage, Decimal('150000'))
        self.assertIsNotNone(services.approbation_requise(mandat))

    def test_la_regle_d_une_autre_societe_ne_s_applique_jamais(self):
        RegleApprobationJuridique.objects.filter(pk=self.regle.pk).delete()
        RegleApprobationJuridique.objects.create(
            company=self.autre, libelle='Seuil voisin',
            montant_min=Decimal('1'), nombre_approbateurs=1)
        mandat = self._mandat('150000.00')
        self.assertIsNone(services.approbation_requise(mandat))

    def test_mandat_d_un_autre_dossier_est_refuse_sur_l_action(self):
        autre_dossier = DossierJuridique.objects.create(
            company=self.company, reference='JUR-2026-0002',
            titre='Autre', date_ouverture=date(2026, 2, 3))
        mandat = self._mandat('150000.00')
        resp = self.api.post(
            f'{DOSSIERS}{autre_dossier.id}/lancer-approbation-mandat/',
            {'mandat': mandat.id}, format='json')
        self.assertEqual(resp.status_code, 404, resp.data)

    def test_statut_du_mandat_non_posable_par_patch(self):
        mandat = self._mandat('150000.00')
        resp = self.api.patch(f'{MANDATS}{mandat.id}/',
                              {'statut': MandatAvocat.Statut.ACTIF},
                              format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        mandat.refresh_from_db()
        self.assertEqual(mandat.statut, MandatAvocat.Statut.BROUILLON)
