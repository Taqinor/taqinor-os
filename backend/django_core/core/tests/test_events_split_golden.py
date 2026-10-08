"""SPL283 — golden du bus d'événements (core/events.py), AVANT tout découpage.

Capture seule : aucun code de production n'est modifié. Les 79 ``Signal`` de
``core.events`` sont figés par nom (plancher : un signal légitime ajouté plus
tard ne rougit pas ; jamais de retrait ni de non-``Signal``). Ces tests
servent de filet aux extractions SPL284-SPL290 : aucun signal, aucune
signature ne doit bouger.
"""
import ast
import importlib
import inspect
from pathlib import Path

import django.dispatch
from django.test import TestCase

from core import event_coverage, events

NOMS_79 = [
    'meta_lead_captured', 'lead_erased', 'lead_created', 'devis_accepted',
    'devis_sent', 'layout_finalise', 'visite_validee', 'visite_planifiee',
    'visite_terminee', 'devis_refused', 'devis_expired',
    'document_pdf_generated', 'payment_captured',
    'reception_fournisseur_confirmee', 'employe_sorti', 'conge_approuve',
    'contrat_signe', 'contrat_actif', 'contrat_resilie', 'document_produit',
    'intervention_completed', 'facture_paid', 'paiement_rejete',
    'facture_emise', 'facture_payee', 'facture_annulee', 'bon_commande_cree',
    'paiement_enregistre', 'avoir_cree', 'avoir_annule',
    'facture_fournisseur_creee', 'paiement_fournisseur_enregistre',
    'mouvement_stock_enregistre', 'produit_modifie', 'chantier_annule',
    'effet_rejete', 'abonnement_monitoring_resilie', 'chantier_receptionne',
    'ticket_resolu', 'lead_stage_changed', 'equipement_remplace',
    'projet_status_change', 'incident_declared', 'document_statut_change',
    'budget_cycle_clos', 'deal_commission_due', 'entite_created',
    'entite_deactivated', 'appointment_effectue',
    'cycle_sterilisation_non_conforme', 'record_soft_deleted', 'ao_depose',
    'ao_gagne', 'module_toggled', 'bulk_edit_applied',
    'salle_vente_signal_interet', 'lead_maturite_changee',
    'dossier_export_cloture', 'scm_rupture_imminente_detectee',
    'scm_cycle_sop_cloture', 'workflow_etape_activee',
    'dossier_juridique_clos', 'btp_reserve_levee', 'btp_rfi_repondu',
    'btp_visa_approuve', 'btp_dgd_finalise', 'saved_view_shared',
    'record_restored', 'dossier_echeance_depassee', 'demande_achat_approuvee',
    'rfq_attribuee', 'langue_changed', 'incident_opened', 'incident_resolved',
    'maintenance_window_announced', 'maintenance_window_created',
    'export_reversibilite_declenche', 'sla_credit_statut_change',
    'calepinage_simule',
]

SIGNATURES = {
    'emit_reliable': (
        "(event, *, sender=None, company=None, emitted_by=None, **kwargs)"),
    'subscribe_durable': (
        "(name, handler, *, rejouable=False, handler_name=None)"),
    'durable_handlers': "(name)",
    'clear_durable_handlers': "()",
    'emettre_langue_changed': (
        "(company, *, ancienne_langue, nouvelle_langue, portee='client', "
        "client_id=None, user=None, sender=None)"),
}

# Table remplie par chaque tâche d'extraction (SPL285-SPL290) :
# ``{'<module de core/events/>': ['<nom de signal>', ...]}``.
OWNER_MODULE = {
    # SPL285 — les 22 signaux des apps parquées (core/parked.py).
    'parked': [
        'employe_sorti', 'conge_approuve', 'contrat_signe', 'contrat_actif',
        'contrat_resilie', 'effet_rejete', 'abonnement_monitoring_resilie',
        'projet_status_change', 'incident_declared', 'budget_cycle_clos',
        'cycle_sterilisation_non_conforme', 'ao_depose', 'ao_gagne',
        'lead_maturite_changee', 'dossier_export_cloture',
        'scm_rupture_imminente_detectee', 'scm_cycle_sop_cloture',
        'dossier_juridique_clos', 'btp_reserve_levee', 'btp_rfi_repondu',
        'btp_visa_approuve', 'btp_dgd_finalise',
    ],
    # SPL286 — chaîne facture → compta/chantier (propriétaire facturation).
    'facturation': [
        'payment_captured', 'document_produit', 'facture_paid',
        'paiement_rejete', 'facture_emise', 'facture_payee',
        'facture_annulee', 'bon_commande_cree', 'paiement_enregistre',
        'avoir_cree', 'avoir_annule',
    ],
    # SPL287 — cycle de vie du devis (propriétaire devis). ``devis_revise``
    # (ACAL91, postérieur au plan) suit son émetteur ventes/domain/revision.py.
    'devis': [
        'devis_accepted', 'devis_sent', 'layout_finalise', 'devis_revise',
        'devis_refused', 'devis_expired', 'document_pdf_generated',
        # Décision fondateur 08/10/2026 — dés-acceptation (lead sorti de
        # « Signé »), émetteur ventes/domain/cycle_vie.annuler_acceptation.
        'devis_acceptation_annulee',
    ],
    # SPL288 — stock / achats. ``reception_fournisseur_annulee`` (ASTK55,
    # postérieur au plan) suit son émetteur stock/services.py.
    'stock': [
        'reception_fournisseur_confirmee', 'reception_fournisseur_annulee',
        'facture_fournisseur_creee', 'paiement_fournisseur_enregistre',
        'mouvement_stock_enregistre', 'produit_modifie',
        'demande_achat_approuvee', 'rfq_attribuee',
    ],
    # SPL289 — lead / visites (propriétaire lead).
    'lead': [
        'lead_erased', 'lead_created', 'visite_validee', 'visite_planifiee',
        'visite_terminee', 'lead_stage_changed', 'deal_commission_due',
        'appointment_effectue', 'salle_vente_signal_interet',
    ],
    # SPL289 — acquisition (émetteur crm/webhooks.py, D-EV-3).
    # ``lead_trace_toit_recu`` (ACAL189, postérieur au plan) suit le même
    # émetteur.
    'acquisition': ['meta_lead_captured', 'lead_trace_toit_recu'],
    # SPL290 — chantiers, sav, calepinage.
    'chantiers': [
        'intervention_completed', 'chantier_annule', 'chantier_receptionne',
    ],
    'sav': ['ticket_resolu', 'equipement_remplace'],
    'calepinage': ['calepinage_simule'],
}

# SPL290 — le socle du bus : ces 17 signaux restent DÉFINIS dans
# ``core/events/__init__.py`` (avec la machinerie emit_reliable & co.).
SOCLE_17 = [
    'document_statut_change', 'entite_created', 'entite_deactivated',
    'record_soft_deleted', 'module_toggled', 'bulk_edit_applied',
    'workflow_etape_activee', 'saved_view_shared', 'record_restored',
    'dossier_echeance_depassee', 'langue_changed', 'incident_opened',
    'incident_resolved', 'maintenance_window_announced',
    'maintenance_window_created', 'export_reversibilite_declenche',
    'sla_credit_statut_change',
]

INIT_EVENTS = Path(__file__).resolve().parents[1] / 'events' / '__init__.py'


def _affectations_top_level(chemin):
    arbre = ast.parse(chemin.read_text(encoding='utf-8'))
    noms = set()
    for noeud in arbre.body:
        if isinstance(noeud, ast.Assign):
            noms.update(t.id for t in noeud.targets
                        if isinstance(t, ast.Name))
    return noms


class EventsSplitGoldenTests(TestCase):
    def test_79_noms_et_ce_sont_des_signaux(self):
        self.assertEqual(len(NOMS_79), 79)
        self.assertEqual(len(set(NOMS_79)), 79)
        manquants = [n for n in NOMS_79 if n not in vars(events)]
        self.assertEqual(manquants, [])
        pas_signal = [n for n in NOMS_79
                      if not isinstance(getattr(events, n),
                                        django.dispatch.Signal)]
        self.assertEqual(pas_signal, [])

    def test_emit_reliable_pour_les_79_noms(self):
        from core.models import OutboxEvent
        for nom in NOMS_79:
            with self.subTest(signal=nom):
                ligne = events.emit_reliable(nom, company=None, x=1)
                self.assertIsInstance(ligne, OutboxEvent)
                self.assertEqual(ligne.event_name, nom)

    def test_signatures_figees(self):
        for nom, attendue in SIGNATURES.items():
            with self.subTest(fonction=nom):
                self.assertEqual(
                    str(inspect.signature(getattr(events, nom))), attendue)
        self.assertEqual(events.PORTEE_LANGUE_CLIENT, 'client')
        self.assertEqual(events.PORTEE_LANGUE_SOCIETE, 'societe')

    def test_event_coverage_declared_signals(self):
        declares = set(event_coverage.declared_signals())
        self.assertEqual([n for n in NOMS_79 if n not in declares], [])

    def test_owner_module_table(self):
        for module, noms in OWNER_MODULE.items():
            sous = importlib.import_module('core.events.' + module)
            tout = set(getattr(sous, '__all__', ()))
            for nom in noms:
                with self.subTest(module=module, signal=nom):
                    self.assertIs(getattr(events, nom), getattr(sous, nom))
                    self.assertIn(nom, tout)
                    if INIT_EVENTS.exists():
                        self.assertNotIn(
                            nom, _affectations_top_level(INIT_EVENTS),
                            'jumeau : affectation top-level restée dans '
                            'core/events/__init__.py')

    def test_socle_reste_dans_init_et_couverture_complete(self):
        init = _affectations_top_level(INIT_EVENTS)
        self.assertEqual([n for n in SOCLE_17 if n not in init], [])
        # Chaque signal des 79 est soit du socle, soit rangé chez un
        # propriétaire : aucun oubli, aucun doublon entre modules.
        ranges = [n for noms in OWNER_MODULE.values() for n in noms]
        self.assertEqual(len(ranges), len(set(ranges)))
        self.assertEqual(set(ranges) & set(SOCLE_17), set())
        self.assertEqual(
            [n for n in NOMS_79 if n not in ranges and n not in SOCLE_17],
            [])
        self.assertTrue(set(NOMS_79) <= set(vars(events)))
        # La machinerie ne quitte jamais __init__.py (emit_reliable résout
        # les noms par globals()).
        arbre = ast.parse(INIT_EVENTS.read_text(encoding='utf-8'))
        fonctions = {n.name for n in arbre.body
                     if isinstance(n, ast.FunctionDef)}
        for nom in ('subscribe_durable', 'durable_handlers',
                    'clear_durable_handlers', '_jsonify', '_resolve_company',
                    'emit_reliable', 'emettre_langue_changed'):
            self.assertIn(nom, fonctions)
