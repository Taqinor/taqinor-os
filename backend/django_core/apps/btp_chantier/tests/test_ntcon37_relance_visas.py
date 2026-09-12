"""NTCON37 — relance quotidienne des visas en attente de revue.

Ce que le test PROUVE :
  * le revuseur désigné ET son manager hiérarchique (lu via ``rh.selectors``,
    jamais ``rh.models``) reçoivent la relance ;
  * le sweep est IDEMPOTENT : deux passages le même jour = une seule relance ;
  * un visa DÉJÀ DÉCIDÉ (approuvé/refusé) n'est jamais relancé — la relance
    s'arrête d'elle-même à la décision ;
  * un visa encore dans les temps n'est pas relancé ;
  * sans revuseur désigné, la relance est routée à l'équipe (NTCON33) plutôt
    que perdue ;
  * l'absence de fiche RH ou de manager ne casse rien (relance au seul
    revuseur).
"""
from datetime import timedelta

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from apps.btp_chantier import selectors, services
from apps.btp_chantier.models import VisaDocument
from apps.notifications.models import EventType, Notification

from .helpers import make_chantier, make_company, make_user


def _relances(user):
    return Notification.objects.filter(
        recipient=user, event_type=EventType.APPROVAL_REMINDER)


class RelanceVisasTests(TestCase):
    def setUp(self):
        self.co = make_company()
        self.chantier = make_chantier(self.co)
        self.aujourdhui = timezone.localdate()
        self.soumetteur = make_user(self.co, role='normal',
                                    username='ntcon37-soumetteur')
        self.revuseur = make_user(self.co, role='responsable',
                                  username='ntcon37-revuseur')
        self.manager = make_user(self.co, role='admin',
                                 username='ntcon37-manager')

    def _lier_hierarchie(self):
        """``revuseur`` → ``manager`` dans l'organigramme RH."""
        from apps.rh.models import DossierEmploye
        dossier_manager = DossierEmploye.objects.create(
            company=self.co, matricule='M-001', nom='Manager', prenom='Le',
            user=self.manager)
        DossierEmploye.objects.create(
            company=self.co, matricule='R-001', nom='Revuseur', prenom='Le',
            user=self.revuseur, manager=dossier_manager)

    def _visa(self, *, retard_jours=3, statut=VisaDocument.Statut.SOUMIS,
              revu_par=True, reference='VIS-1'):
        return VisaDocument.objects.create(
            company=self.co, chantier=self.chantier, document_ged_id=7,
            reference=reference, statut=statut,
            soumis_par=self.soumetteur,
            revu_par=self.revuseur if revu_par else None,
            delai_revue_jours=10,
            date_limite=self.aujourdhui - timedelta(days=retard_jours))

    # ── sélecteur ──────────────────────────────────────────────────────────
    def test_selecteur_ne_retient_que_les_statuts_ouverts(self):
        self._visa(reference='VIS-soumis')
        self._visa(reference='VIS-revue', statut=VisaDocument.Statut.EN_REVUE)
        self._visa(reference='VIS-approuve',
                   statut=VisaDocument.Statut.APPROUVE_SANS_RESERVE)
        self._visa(reference='VIS-refuse', statut=VisaDocument.Statut.REFUSE)
        refs = set(selectors.visas_en_retard(self.co).values_list(
            'reference', flat=True))
        self.assertEqual(refs, {'VIS-soumis', 'VIS-revue'})

    def test_visa_dans_les_temps_non_retenu(self):
        self._visa(retard_jours=-5)
        self.assertEqual(selectors.visas_en_retard(self.co).count(), 0)

    # ── sweep ──────────────────────────────────────────────────────────────
    def test_relance_le_revuseur(self):
        visa = self._visa()
        resultat = services.alerter_visas_en_attente()
        self.assertEqual(resultat['alertes_envoyees'], 1)
        self.assertEqual(_relances(self.revuseur).count(), 1)
        visa.refresh_from_db()
        self.assertEqual(visa.derniere_relance_retard, self.aujourdhui)

    def test_relance_aussi_le_manager(self):
        self._lier_hierarchie()
        self._visa()
        services.alerter_visas_en_attente()
        self.assertEqual(_relances(self.revuseur).count(), 1)
        self.assertEqual(_relances(self.manager).count(), 1)

    def test_sans_fiche_rh_seul_le_revuseur_est_relance(self):
        self._visa()
        services.alerter_visas_en_attente()
        self.assertEqual(_relances(self.revuseur).count(), 1)
        self.assertEqual(_relances(self.manager).count(), 0)

    def test_sweep_idempotent(self):
        self._visa()
        premier = services.alerter_visas_en_attente()
        second = services.alerter_visas_en_attente()
        self.assertEqual(premier['alertes_envoyees'], 1)
        self.assertEqual(second['alertes_envoyees'], 0)
        self.assertEqual(second['examines'], 1)
        self.assertEqual(_relances(self.revuseur).count(), 1)

    def test_relance_a_nouveau_le_lendemain(self):
        visa = self._visa()
        services.alerter_visas_en_attente()
        demain = self.aujourdhui + timedelta(days=1)
        resultat = services.alerter_visas_en_attente(aujourdhui=demain)
        self.assertEqual(resultat['alertes_envoyees'], 1)
        visa.refresh_from_db()
        self.assertEqual(visa.derniere_relance_retard, demain)

    def test_visa_decide_jamais_relance(self):
        self._visa(statut=VisaDocument.Statut.APPROUVE_AVEC_OBSERVATIONS)
        resultat = services.alerter_visas_en_attente()
        self.assertEqual(resultat['examines'], 0)
        self.assertEqual(_relances(self.revuseur).count(), 0)

    def test_approbation_arrete_la_relance(self):
        visa = self._visa()
        services.alerter_visas_en_attente()
        services.approuver_visa(visa, user=self.revuseur)
        demain = self.aujourdhui + timedelta(days=1)
        resultat = services.alerter_visas_en_attente(aujourdhui=demain)
        self.assertEqual(resultat['examines'], 0)

    def test_sans_revuseur_la_relance_va_a_l_equipe(self):
        self._visa(revu_par=False)
        resultat = services.alerter_visas_en_attente()
        self.assertEqual(resultat['alertes_envoyees'], 1)
        # Repli resolve_recipients : les managers actifs de la société.
        self.assertEqual(_relances(self.manager).count(), 1)

    def test_commande_de_gestion(self):
        visa = self._visa()
        call_command('alertes_visas_en_attente')
        visa.refresh_from_db()
        self.assertEqual(visa.derniere_relance_retard, self.aujourdhui)

    # ── multi-tenant ───────────────────────────────────────────────────────
    def test_le_sweep_global_ne_melange_pas_les_societes(self):
        autre = make_company()
        autre_chantier = make_chantier(autre)
        voisin = make_user(autre, role='responsable', username='ntcon37-voisin')
        VisaDocument.objects.create(
            company=autre, chantier=autre_chantier, document_ged_id=1,
            reference='VIS-X', statut=VisaDocument.Statut.SOUMIS,
            revu_par=voisin, delai_revue_jours=10,
            date_limite=self.aujourdhui - timedelta(days=2))
        self._visa()
        services.alerter_visas_en_attente()
        self.assertEqual(_relances(self.revuseur).count(), 1)
        self.assertEqual(_relances(voisin).count(), 1)
        # Chaque notification porte la société de SON visa.
        self.assertEqual(
            _relances(self.revuseur).first().company_id, self.co.id)
        self.assertEqual(_relances(voisin).first().company_id, autre.id)
