"""NTCON34 — les quatre KPI BTP dans le reporting transverse.

Ce que le test PROUVE :
  * les 4 clés sont au catalogue fermé ``KpiAlerte.Kpi`` ET branchées à un
    calculateur (``_KPI_COMPUTERS``) — une clé sans calculateur serait une
    tuile morte ;
  * elles apparaissent dans le picker de tuiles (``kpis_disponibles``) ;
  * une alerte se déclenche au franchissement du seuil configuré ;
  * une société SANS objet BTP renvoie ``None`` (KPI ignoré) et JAMAIS 0 — un
    0 affirmerait « rien en retard » là où la vraie réponse est « ce module
    n'est pas utilisé ici » ;
  * les valeurs réutilisent les sélecteurs EXISTANTS (aucune 2ᵉ formule) ;
  * cross-tenant : les objets d'une autre société ne comptent jamais.
"""
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.btp_chantier import selectors, services
from apps.btp_chantier.models import (
    RFI, Lot, ReserveChantier, VisaDocument,
)
from apps.reporting.kpi_alertes import (
    _KPI_COMPUTERS, evaluate_kpi_alerte, kpis_disponibles,
)
from apps.reporting.models import KpiAlerte

from .helpers import make_chantier, make_company, make_user

CLES = (
    'btp_reserves_ouvertes',
    'btp_rfi_en_retard',
    'btp_visas_en_attente',
    'btp_penalites_cumulees_periode',
)


class KpiBtpTests(TestCase):
    def setUp(self):
        self.co = make_company()
        self.chantier = make_chantier(self.co)
        self.user = make_user(self.co, role='responsable')
        self.aujourdhui = timezone.localdate()

    # ── catalogue & câblage ────────────────────────────────────────────────
    def test_les_quatre_cles_sont_au_catalogue_et_cablees(self):
        catalogue = {valeur for valeur, _ in KpiAlerte.Kpi.choices}
        for cle in CLES:
            with self.subTest(cle=cle):
                self.assertIn(cle, catalogue)
                self.assertIn(cle, _KPI_COMPUTERS)

    def test_les_quatre_cles_dans_le_picker_de_tuiles(self):
        proposees = kpis_disponibles(self.co)
        for cle in CLES:
            with self.subTest(cle=cle):
                self.assertIn(cle, proposees)

    # ── valeurs ────────────────────────────────────────────────────────────
    def test_societe_sans_btp_renvoie_none_jamais_zero(self):
        valeurs = selectors.kpis_btp(self.co)
        for cle in CLES:
            with self.subTest(cle=cle):
                self.assertIsNone(valeurs[cle])

    def test_reserves_ouvertes(self):
        for statut in (ReserveChantier.Statut.OUVERTE,
                       ReserveChantier.Statut.EN_COURS,
                       ReserveChantier.Statut.CONTESTEE,
                       ReserveChantier.Statut.LEVEE):
            ReserveChantier.objects.create(
                company=self.co, chantier=self.chantier, lot='x',
                localisation_plan={}, description=statut, gravite='mineure',
                statut=statut, created_by=self.user)
        self.assertEqual(
            selectors.kpis_btp(self.co)['btp_reserves_ouvertes'], 3)

    def test_reserve_archivee_ne_compte_plus(self):
        reserve = ReserveChantier.objects.create(
            company=self.co, chantier=self.chantier, lot='x',
            localisation_plan={}, description='vieille', gravite='mineure',
            statut=ReserveChantier.Statut.OUVERTE, created_by=self.user)
        self.assertEqual(
            selectors.kpis_btp(self.co)['btp_reserves_ouvertes'], 1)
        ReserveChantier.objects.filter(pk=reserve.pk).update(archivee=True)
        self.assertEqual(
            selectors.kpis_btp(self.co)['btp_reserves_ouvertes'], 0)

    def test_rfi_en_retard_reutilise_le_selecteur_ntcon3(self):
        a_lheure = services.creer_rfi(
            company=self.co, chantier=self.chantier, pose_par=self.user,
            question='à l\'heure')
        en_retard = services.creer_rfi(
            company=self.co, chantier=self.chantier, pose_par=self.user,
            question='en retard')
        RFI.objects.filter(pk=en_retard.pk).update(
            date_limite_reponse=self.aujourdhui - timedelta(days=3))
        self.assertEqual(selectors.kpis_btp(self.co)['btp_rfi_en_retard'], 1)
        # Même chiffre que le sélecteur d'origine : aucune 2ᵉ formule.
        self.assertEqual(
            selectors.rfi_en_retard(self.co).count(), 1)
        self.assertNotIn(
            a_lheure.pk,
            selectors.rfi_en_retard(self.co).values_list('pk', flat=True))

    def test_visas_en_attente(self):
        for statut in (VisaDocument.Statut.SOUMIS,
                       VisaDocument.Statut.EN_REVUE,
                       VisaDocument.Statut.REFUSE):
            VisaDocument.objects.create(
                company=self.co, chantier=self.chantier, document_ged_id=1,
                reference=f'VIS-{statut}', statut=statut,
                delai_revue_jours=7)
        self.assertEqual(
            selectors.kpis_btp(self.co)['btp_visas_en_attente'], 2)

    def test_penalites_cumulees_egales_au_selecteur_ntcon15(self):
        Lot.objects.create(
            company=self.co, chantier=self.chantier, nom='Gros œuvre',
            jalon_contractuel=True,
            date_fin_prevue=self.aujourdhui - timedelta(days=10),
            montant_ht=Decimal('100000.00'),
            taux_penalite_retard_pmil=Decimal('1.000'))
        attendu = selectors.penalites_retard_par_lot(
            self.chantier)['total_exposition']
        self.assertEqual(
            selectors.kpis_btp(self.co)['btp_penalites_cumulees_periode'],
            attendu)
        self.assertGreater(attendu, 0)

    # ── alerte au franchissement ───────────────────────────────────────────
    def test_alerte_se_declenche_au_franchissement(self):
        for _ in range(3):
            ReserveChantier.objects.create(
                company=self.co, chantier=self.chantier, lot='x',
                localisation_plan={}, description='ouverte',
                gravite='mineure', created_by=self.user)
        alerte = KpiAlerte.objects.create(
            company=self.co, nom='Trop de réserves ouvertes',
            kpi=KpiAlerte.Kpi.BTP_RESERVES_OUVERTES,
            operateur=KpiAlerte.Operateur.SUP, seuil=Decimal('2'),
            actif=True)
        valeur, franchi, _notifie = evaluate_kpi_alerte(alerte)
        alerte.refresh_from_db()
        self.assertEqual(valeur, Decimal('3'))
        self.assertTrue(franchi)
        self.assertEqual(alerte.derniere_valeur, Decimal('3'))
        self.assertTrue(alerte.deja_notifie)

    def test_pas_d_alerte_sous_le_seuil(self):
        ReserveChantier.objects.create(
            company=self.co, chantier=self.chantier, lot='x',
            localisation_plan={}, description='ouverte', gravite='mineure',
            created_by=self.user)
        alerte = KpiAlerte.objects.create(
            company=self.co, nom='Trop de réserves',
            kpi=KpiAlerte.Kpi.BTP_RESERVES_OUVERTES,
            operateur=KpiAlerte.Operateur.SUP, seuil=Decimal('5'),
            actif=True)
        _valeur, franchi, _notifie = evaluate_kpi_alerte(alerte)
        alerte.refresh_from_db()
        self.assertFalse(franchi)
        self.assertFalse(alerte.deja_notifie)

    # ── multi-tenant ───────────────────────────────────────────────────────
    def test_cross_tenant(self):
        autre = make_company()
        autre_chantier = make_chantier(autre)
        ReserveChantier.objects.create(
            company=autre, chantier=autre_chantier, lot='x',
            localisation_plan={}, description='chez le voisin',
            gravite='mineure')
        self.assertIsNone(
            selectors.kpis_btp(self.co)['btp_reserves_ouvertes'])
        self.assertEqual(
            selectors.kpis_btp(autre)['btp_reserves_ouvertes'], 1)
