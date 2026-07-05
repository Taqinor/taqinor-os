"""Services du module Marketing (``apps.marketing``).

ODX10 — ré-export TRANSITOIRE des fonctions de service marketing qui vivent
encore physiquement dans ``apps.compta.services`` (elles y étaient interleavées
avec la logique comptable ; les extraire du fichier de 500 Ko en un seul move
serait un risque de régression non vérifiable hors suite complète). Ce module
donne au reste du code (receivers marketing, urls, appelants cross-app) un point
d'accès ``apps.marketing.services`` stable ; ODX22 re-logera le corps des
fonctions ici et retirera ce shim.

``marketing`` ne lit crm/ventes QUE via leurs selectors/services ou par
référence opaque — jamais leurs ``models`` (invariant CLAUDE.md déjà tenu par
les fonctions ré-exportées, qui référencent lead_id/devis_id opaques).
"""

from apps.compta.services import (  # noqa: F401
    annuler_campagne,
    appliquer_mouvement_fidelite,
    approuver_envoi_campagne,
    campagnes_par_statut,
    clics_par_lien,
    compteurs_par_etape,
    cout_total_campagne,
    creer_enquete,
    decider_gagnant_ab,
    demander_ou_envoyer_campagne,
    dupliquer_campagne,
    enregistrer_relance_devis_abandonne,
    envelopper_liens_campagne,
    envoyer_campagne,
    envoyer_campagnes_planifiees,
    envoyer_enquete_nps,
    envoyer_test_campagne,
    executer_etapes_dues,
    inscrire_lead_sequence,
    leads_source_roi,
    nb_participants_actifs,
    participants_sequence,
    planifier_campagne,
    planifier_etapes_sequence,
    pousser_avis_google,
    precheck_sante_campagne,
    questions_visibles,
    recalculer_compteurs_campagne,
    rejeter_envoi_campagne,
    rendre_pour_lead,
    renvoyer_echecs_campagne,
    reporting_campagnes,
    repondre_enquete_nps,
    roi_campagne,
    score_nps,
    sortir_inscription,
    sortir_inscriptions_pour_lead,
    suggestions_upsell,
    traces_sequence,
    valider_questions_enquete,
    variante_pour_langue,
    webhook_brevo_evenement,
)
