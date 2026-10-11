"""Sélecteurs LECTURE SEULE du domaine CRM exposés aux AUTRES apps.

Point d'entrée cross-app : les autres apps lisent les clients à travers ces
fonctions plutôt qu'en important `apps.crm.models` directement (voir CLAUDE.md,
règle de modularité). Comportement strictement identique aux requêtes inline
d'origine.
"""
import datetime  # noqa: F401 — façade : `datetime` reste exposé (golden SPL70)
from .portee_selectors import (  # noqa: F401
    MOTIF_CONTACT_REFUSE, peut_contacter, portee_leads, leads_visibles,
    leads_en_portee, lead_signe_q, est_lead_signe, cles_numeros_lead,
    lead_ids_du_responsable, lead_ids_anonymises, client_ids_anonymises,
)
from .cadence_selectors import (  # noqa: F401
    JOURS_OUVRES_JOINDRE, _minutes_ouvrees_de_5_jours, kpi_cadences,
    _STATUTS_CLOS_HUMAIN, LEADS_SANS_TOUCHE_MAX, _lundi, _pct, _mediane_decimale,
    _a_lheure, _a_lheure_ou_excusee, _conversion_par_stage,
    CHAINE_COMMERCIALE_LIMITE, _chaine_bloc, _chaine_identite,
    _chaine_devis_partis, chaine_commerciale, _assigne_de_la_visite, SERIE_JOURS_MAX,
    _serie_jours_sans_retard, _mediane, relances_du_jour, relance_etapes_dues,
    file_du_cockpit, STATUT_EN_RETARD, STATUTS_SUIVI, SUIVI_JOURS_MAX,
    relance_etapes_periode, JOURNAL_TYPES, _JOURNAL_FENETRE, _JOURNAL_PREFIXES,
    _journal_cause_apres_deux_points, journal_relance, _journal_phrase,
    prochaine_touche_par_lead, devis_a_cadence_active, leads_chauds_non_contactes,
    devis_expirant_bientot, leads_rappel_demande, ma_file_commercial_items,
    CADENCES_CLOTURABLES, cadences_echues_a_clore, mesure_cadence, PRIORITE_RANG_FILE,
    PRIORITE_RANG_DEFAUT, trier_file_du_jour,
)
from .leads_selectors import (  # noqa: F401
    normalize_phone_key, normalize_email_key, normalize_name_key,
    find_lead_id_by_phone, leads_sla_depasse, CANAL_RAPPEL_SLA,
    leads_callback_sla_depasse, leads_meta_sla_depasse, leads_response_time_rows,
    HEURE_RAPPEL_DU_MATIN, _limite_rappel_du_matin, kpi_premier_contact,
    _objectif_premier_contact, lead_merge_fields, lead_contact_identifiers,
    existing_lead_emails, _PROGRESSIVE_PROFILING_STANDARD_FIELDS,
    lead_known_field_codes, lead_ids_by_contact, lead_ids_par_identifiant,
    doublons_foyer_probables,
)
from .clients_selectors import (  # noqa: F401
    client_base_qs, find_client_by_email, clients_pour_controle_ice,
    find_client_by_ice_or_libelle, find_client_by_phone, client_credit_warning,
    credit_hold_check, get_company_client, client_label, get_latest_lead_for_client,
    compute_attainment, _lignes_pipeline_ouvertes, _valeur_ponderee_leads,
    _activites_en_retard, _devis_compte_comme_signe, _ca_signe_mois, ca_signe_periode,
    nb_devis_envoyes_periode, stats_equipe, delai_paiement_client,
    clients_contact_identifiers, _tous_descendants, consolidation_client,
    forecast_rollup, revenu_pipeline_pondere_par_mois, resume_portail_partenaire,
    soumissions_partenaire_portail, partenaire_peut_soumettre,
    releve_commissions_partenaire, pipeline_pondere_par_entite,
    partenaire_pour_certification, partenaires_certifies_qs,
    specialites_partenaire_cles, certifications_expirantes, _as_date,
    portefeuille_commercial, comptes_dormants, salle_vente_analytics,
    salle_vente_summary_for_lead, _metric_count_for_owner, classement_defi,
    metrique_pipeline_pondere, register_metric_adapters, client_ids_par_identifiant,
)
from .devis_selectors import (  # noqa: F401
    lead_du_devis, ville_effective, _srm_deduite, lead_bills_for_devis,
    SITE_PROFILE_FIELDS, ALIAS_DEPRECIE_CV_ACTUELLE, site_profile_for_client,
    ENTREES_POMPAGE_CIBLES, _ENTREES_POMPAGE_SOURCES, _ENTREES_POMPAGE_INFORMATION,
    _LIBELLE_HEURES_ACTUELLES, FORMULE_VOLUME_DECLARE, _entree_valeur, _entree_vide,
    entrees_pompage_du_lead, entrees_pompage_pour_lead_id, _CI_DETAIL_SOURCE,
    _CI_COLONNE_SOURCE, _CI_INFORMATIONS, _CI_PHASES, _CI_REGISTRES_MT, _ci_nombre,
    entrees_ci_du_lead, entrees_ci_pour_lead_id, releve_declare_ci,
    site_location_for_devis, PROFILS_ACTIVITE, profil_activite_pour_devis,
    occupation_jour_pour_devis, equipements_pour_lead, equipements_pour_devis,
    lead_devis_ids_by_id, _kwh_positif, SEGMENTS_REPLI_KWH_SITE,
    conso_mensuelle_kwh_pour_devis,
)
from .roof_selectors import (  # noqa: F401
    conception_3d_du_lead, REPERE_SOURCE_ROOF_POINT, REPERE_SOURCE_GPS,
    _REPERE_TOLERANCE_DEG, _repere_nombre, _repere_pin, _repere_anneau,
    _repere_dans_anneau, repere_toit,
)
from .stock_selectors import (  # noqa: F401
    leads_utilisant_produit,
)
from .attribution_selectors import (  # noqa: F401
    signed_lead_phone_keys, signed_leads_for_campaigns, attribution_lead_rows,
    lead_appointment_stats, lead_touchpoints_attribution, attribution_leads,
    leads_ville_rows, revenu_attribue_campagne, leads_source_campagne,
    reconciliation_lead_rows, _META_LEAD_ADS_SYSTEM, lead_capi_identifiers,
    meta_lead_match_coverage, reporting_lead_rows, objection_mining_rows,
    organic_referral_lead_series, COLD_AGE_BUCKETS, MIN_SAMPLE_COLD_BUCKET,
    cold_reactivation_by_age_bucket, new_leads_by_mode_meta, ATTRIBUTION_MODELES,
    _ATTRIBUTION_DEMI_VIE_JOURS, _attribution_part, _repartir_attribution,
    attribution_comparaison_devis,
)
from .fiche_selectors import (  # noqa: F401
    get_company_lead, get_company_leads_by_ids, rechercher_leads_minimal, lead_card,
    _VALEUR_CHATTER_VIDE, provenance_site, LEAD_PROVENANCE_FIELDS,
    _LEAD_PROVENANCE_MARQUEURS, _RAISON_LU_EN_DIRECT, _RAISON_PROFIL_APPEL,
    _RAISON_QUALIFICATION, _RAISON_TRANCHE, _RAISON_POMPAGE_AGR, _RAISON_PRO_CIQ,
    LEAD_PROVENANCE_EXCLUSIONS, _lead_champs_concrets,
    lead_provenance_champs_energie_toit, lead_provenance_omissions,
    _lead_provenance_valeurs, lead_provenance_stamp, lead_values_changed_since,
    LEAD_SEGMENT_FIELDS, leads_matching_regles, lead_chatter_envelope,
    _KIND_DEVIS_VERS_CHATTER, lead_jalons_devis, pipeline_stage_order,
    lead_current_stage, lead_criteria_for_territoire, leads_recents_pour_couverture,
    leads_export_rows, dernier_contact_lead, leads_signes_sans_devis_accepte,
    champs_devis_auto_manquants, lead_en_attente_ou_veille,
)
