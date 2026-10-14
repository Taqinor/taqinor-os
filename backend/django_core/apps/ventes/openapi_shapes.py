"""ENF11 — formes OpenAPI EXACTES des vues-fonctions de ventes (``@api_view``).

Aucun comportement : ces sérialiseurs ne servent QU'À la description du schéma
(``@extend_schema``). Même esprit que ``views/openapi_docs.py`` (actions de
ViewSet), mais SANS import lourd (ni modèles ni sérialiseurs de l'app) pour
pouvoir être importé depuis n'importe quel module de premier niveau.

Règles : un champ que la vue peut omettre est ``required=False`` ; un champ
qu'elle peut servir à ``None`` est ``allow_null=True`` ; les blocs imbriqués
dont la forme est portée par un contrat dédié (``contract_samples/``) restent
des ``DictField``/``ListField(DictField)`` — leur contenu n'est pas redéfini ici.
"""
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import inline_serializer
from rest_framework import serializers as s

from core.openapi_erreurs import EXTENSION_CORPS_RESSERRE


def _ser(name, fields, **kwargs):
    return inline_serializer(name, fields, **kwargs)


# ----------------------------------------------------------------- erreurs
DetailResponse = _ser('VentesDetail', {'detail': s.CharField()})

# ------------------------------------------------------------ cash-flow
CashFlowResponse = _ser('CashFlowForecast', {
    'buckets': _ser('CashFlowBuckets', {
        cle: _ser('CashFlowBucket' + cle.title().replace('_', ''), {
            'montant': s.CharField(),
            'count': s.IntegerField(),
        }) for cle in (
            'en_retard', 'cette_semaine', 'semaine_suivante', 'ce_mois',
            'mois_suivant', 'au_dela', 'sans_echeance')
    }),
    'total_en_cours': s.CharField(),
    'rows': _ser('CashFlowRow', {
        'facture_reference': s.CharField(),
        'client': s.CharField(),
        'date_echeance': s.CharField(allow_null=True),
        'montant_du': s.CharField(),
        'jours_retard': s.IntegerField(),
        'bucket': s.CharField(),
    }, many=True),
})

AnalyseFacturationLigne = _ser('AnalyseFacturationLigne', {
    'mois': s.CharField(),
    'client_id': s.IntegerField(allow_null=True),
    'client_nom': s.CharField(allow_blank=True, allow_null=True),
    'statut': s.CharField(),
    'nb_factures': s.IntegerField(),
    'total_ht': s.CharField(),
    'total_tva': s.CharField(),
    'total_ttc': s.CharField(),
}, many=True)

# ------------------------------------------------------------- recouvrement
_NIVEAU_COURANT = _ser('RelanceNiveauCourant', {
    'ordre': s.IntegerField(),
    'nom': s.CharField(),
    'delai_jours': s.IntegerField(),
    'message': s.CharField(allow_blank=True),
    'penalite': s.CharField(required=False),
}, allow_null=True)
_NIVEAU_SUIVANT = _ser('RelanceNiveauSuivant', {
    'ordre': s.IntegerField(),
    'nom': s.CharField(),
    'delai_jours': s.IntegerField(),
}, allow_null=True)
_PROMESSE = _ser('RelancePromesse', {
    'id': s.IntegerField(),
    'statut': s.CharField(),
    'montant_promis': s.CharField(),
    'date_promise': s.CharField(),
}, allow_null=True)
RelancesListResponse = _ser('RelanceImpayeLigne', {
    'id': s.IntegerField(),
    'reference': s.CharField(),
    'client_id': s.IntegerField(allow_null=True),
    'client_nom': s.CharField(allow_blank=True),
    'client_telephone': s.CharField(allow_null=True, allow_blank=True),
    'date_echeance': s.CharField(allow_null=True),
    'montant_du': s.CharField(),
    'jours_retard': s.IntegerField(),
    'niveau': _NIVEAU_COURANT,
    'niveau_suivant': _NIVEAU_SUIVANT,
    'prochaine_relance': s.CharField(allow_null=True),
    'nb_relances': s.IntegerField(),
    'promesse': _PROMESSE,
    'score_comportement': s.CharField(),
    'relance_mode': s.CharField(),
    'relance_responsable_id': s.IntegerField(allow_null=True),
}, many=True)

BalanceAgeeResponse = _ser('BalanceAgeeLigne', {
    'client_id': s.IntegerField(allow_null=True),
    'client_nom': s.CharField(allow_blank=True),
    'b0_30': s.CharField(),
    'b31_60': s.CharField(),
    'b61_90': s.CharField(),
    'b90_plus': s.CharField(),
    'total': s.CharField(),
    'score_comportement': s.CharField(),
}, many=True)

_RELEVE_PAIEMENT = _ser('ReleveClientPaiement', {
    'facture': s.CharField(),
    'date': s.CharField(allow_null=True),
    'mode': s.CharField(),
    'montant': s.CharField(),
    'type': s.CharField(),
    'libelle': s.CharField(),
    'reference_source': s.CharField(required=False),
}, many=True)
_RELEVE_AVOIR = _ser('ReleveClientAvoir', {
    'facture': s.CharField(),
    'reference': s.CharField(),
    'date': s.CharField(allow_null=True),
    'motif': s.CharField(allow_blank=True, allow_null=True),
    'total_ttc': s.CharField(),
}, many=True)
_RELEVE_LIGNE = _ser('ReleveClientLigne', {
    'reference': s.CharField(),
    'date': s.CharField(),
    'statut': s.CharField(),
    'total_ttc': s.CharField(),
    'notes_debit': s.CharField(),
    'paye': s.CharField(),
    'retenues': s.CharField(),
    'avoirs': s.CharField(),
    'abandons': s.CharField(),
    'du': s.CharField(),
}, many=True)
ReleveClientResponse = _ser('ReleveClient', {
    'client': _ser('ReleveClientIdentite', {
        'id': s.IntegerField(),
        'nom': s.CharField(allow_blank=True),
        'email': s.CharField(allow_null=True, allow_blank=True),
        'telephone': s.CharField(allow_null=True, allow_blank=True),
        'adresse': s.CharField(allow_null=True, allow_blank=True),
    }),
    'lignes': _RELEVE_LIGNE,
    'paiements': _RELEVE_PAIEMENT,
    'avoirs': _RELEVE_AVOIR,
    'totaux': _ser('ReleveClientTotaux', {
        'facture': s.CharField(),
        'notes_debit': s.CharField(),
        'paye': s.CharField(),
        'retenues': s.CharField(),
        'avoirs': s.CharField(),
        'abandons': s.CharField(),
        'du': s.CharField(),
    }),
})

ScoreComportementResponse = _ser('ClientScoreComportement', {
    'score': s.FloatField(),
    'lettre': s.CharField(),
    'retard_moyen_jours': s.FloatField(allow_null=True),
    'nb_factures_ouvertes': s.IntegerField(),
    'nb_factures_historique': s.IntegerField(),
    'used_fallback': s.BooleanField(),
})

# ------------------------------------------------------------- dashboard
DashboardQuoteToCashResponse = _ser('DashboardQuoteToCash', {
    'devis': _ser('DashboardDevis', {
        'total': s.IntegerField(),
        'envoyes': s.IntegerField(),
        'acceptes': s.IntegerField(),
        'refuses': s.IntegerField(),
        'expires': s.IntegerField(),
        'taux_acceptation_pct': s.FloatField(allow_null=True),
        'valeur_pipeline': s.CharField(),
    }),
    'factures': _ser('DashboardFactures', {
        'total': s.IntegerField(),
        'emises': s.IntegerField(),
        'payees': s.IntegerField(),
        'en_retard': s.IntegerField(),
        'annulees': s.IntegerField(),
        'montant_facture': s.CharField(),
        'montant_encaisse': s.CharField(),
    }),
    'conversion': _ser('DashboardConversion', {
        'devis_envoye_vers_accepte_pct': s.FloatField(allow_null=True),
        'devis_accepte_vers_facture_pct': s.FloatField(allow_null=True),
        'devis_envoye_vers_facture_pct': s.FloatField(allow_null=True),
    }),
    'dso_jours': s.FloatField(allow_null=True),
    'cycle_moyen_jours': s.FloatField(allow_null=True),
    'par_commercial': _ser('DashboardParCommercial', {
        'commercial': s.CharField(),
        'devis_actifs': s.IntegerField(),
        'valeur_pipeline': s.CharField(),
    }, many=True),
})

# --------------------------------------------------- calendrier réglementaire
CalendrierReglementaireResponse = _ser('CalendrierReglementaire', {
    'today': s.CharField(),
    'seuil_imminent_jours': s.IntegerField(),
    'validite_accord_jours': s.IntegerField(allow_null=True),
    'echeances': _ser('CalendrierEcheance', {
        'type': s.CharField(),
        'sous_type': s.CharField(allow_blank=True, allow_null=True),
        'dossier_id': s.IntegerField(allow_null=True),
        'libelle': s.CharField(),
        'date_echeance': s.CharField(),
        'statut_alerte': s.CharField(),
        'jours_restants': s.IntegerField(allow_null=True),
        'relance_due': s.BooleanField(),
    }, many=True),
    'resume': _ser('CalendrierResume', {
        'expire': s.IntegerField(),
        'imminent': s.IntegerField(),
        'a_venir': s.IntegerField(),
        'sans_echeance': s.IntegerField(),
    }),
})

# ---------------------------------------------- déclaration de raccordement
DeclarationRaccordementResponse = _ser('DeclarationRaccordement', {
    'devis_reference': s.CharField(allow_blank=True),
    'client': _ser('DeclarationRaccordementClient', {
        'nom': s.CharField(allow_blank=True),
        'adresse': s.CharField(allow_blank=True),
        'telephone': s.CharField(allow_blank=True),
        'email': s.CharField(allow_blank=True),
        'ice': s.CharField(allow_blank=True),
    }),
    'site': _ser('DeclarationRaccordementSite', {
        'reference': s.CharField(allow_blank=True),
        'gps_lat': s.FloatField(allow_null=True),
        'gps_lng': s.FloatField(allow_null=True),
        'date_mise_en_service': s.DateField(allow_null=True),
    }),
    'systeme': _ser('DeclarationRaccordementSysteme', {
        'kwc': s.FloatField(allow_null=True),
        'n_panneaux': s.IntegerField(),
        'puissance_panneau_wc': s.IntegerField(),
        'onduleur': s.CharField(allow_blank=True),
        'puissance_onduleur_kw': s.FloatField(),
        'phases': s.IntegerField(),
        'injection': s.BooleanField(),
        'has_battery': s.BooleanField(),
    }),
    'raccordement': s.CharField(allow_blank=True, allow_null=True),
    'regime_8221': s.CharField(allow_blank=True),
    'regime_label': s.CharField(allow_blank=True),
    'pieces': s.ListField(child=s.DictField()),
    'motif_pieces': s.CharField(required=False, allow_blank=True),
})

# ----------------------------------------------------------- e-mail / config
EmailConfigResponse = _ser('VentesEmailConfig', {
    'configured': s.BooleanField(),
    'from_email': s.CharField(allow_blank=True),
    'inbound_configured': s.BooleanField(),
})

RoofConfigResponse = _ser('VentesRoofConfig', {
    'available': s.BooleanField(),
    'maptilerKey': s.CharField(allow_blank=True),
    'mapboxToken': s.CharField(allow_null=True),
})

# ---------------------------------------------------------------- exports
ExportAsyncResponse = _ser('VentesExportAsync', {
    'detail': s.CharField(),
    'job_id': s.CharField(),
    'status': s.CharField(),
    'rows': s.IntegerField(),
    'status_url': s.CharField(),
})
ExportStatusResponse = _ser('VentesExportStatus', {
    'status': s.ChoiceField(choices=['pending', 'ready', 'error']),
    'download_url': s.CharField(required=False),
    'filename': s.CharField(required=False, allow_null=True),
    'detail': s.CharField(required=False),
})

XLSX = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

# ------------------------------------------------------------ numérotation
_GROUPE_NUMEROTATION = _ser('NumerotationGroupe', {
    'radical': s.CharField(),
    'manquants': s.ListField(child=s.IntegerField()),
    'doublons': s.ListField(child=s.IntegerField()),
}, many=True)
NumerotationAuditResponse = _ser('NumerotationAudit', {
    'devis': _GROUPE_NUMEROTATION,
    'facture': _GROUPE_NUMEROTATION,
    'avoir': _GROUPE_NUMEROTATION,
    'bon_commande': _GROUPE_NUMEROTATION,
    'total_manquants': s.IntegerField(),
    'total_doublons': s.IntegerField(),
    'conforme': s.BooleanField(),
})
NumerotationPreviewResponse = _ser('NumerotationPreview', {
    'devis': s.CharField(),
    'facture': s.CharField(),
    'avoir': s.CharField(),
    'bon_commande': s.CharField(),
})

# --------------------------------------------------------- charge de toiture
RoofLoadRequest = _ser('RoofLoadRequest', {
    'charge_admissible_kg_m2': s.FloatField(required=False, allow_null=True),
    'charge_admissible_source': s.CharField(
        required=False, allow_blank=True, allow_null=True),
    'struct_masse_kg_m2': s.FloatField(required=False, allow_null=True),
    'poids_module_kg': s.FloatField(required=False, allow_null=True),
    'aire_module_m2': s.FloatField(required=False, allow_null=True),
    'masse_layout_kg_m2': s.FloatField(required=False, allow_null=True),
    'couverture': s.CharField(required=False, allow_blank=True,
                              allow_null=True),
    'coefficient_securite': s.FloatField(required=False, allow_null=True),
    'coefficient_source': s.CharField(
        required=False, allow_blank=True, allow_null=True),
})


def _valeur_avec_sa_source(champ, source):
    """CI #997 — ``champ`` (nombre ≥ 0) ne s'applique qu'avec ``source``
    non blanche (``roof_load.ChargeNonSourcee``) : absent, null ou négatif
    (ignoré par le calcul), sinon la source est requise."""
    return {'anyOf': [
        {'not': {'required': [champ]}},
        {'properties': {champ: {'type': 'number', 'nullable': True,
                                'maximum': 0, 'exclusiveMaximum': True}}},
        {'required': [source],
         'properties': {source: {'type': 'string', 'pattern': r'\S'}}},
    ]}


#: Règle publiée en ``allOf`` au corps (``x-corps-resserre``) : une requête
#: conforme n'est plus refusée « … exige sa source ».
ROOF_LOAD_SOURCES = {EXTENSION_CORPS_RESSERRE: {'allOf': [
    _valeur_avec_sa_source('charge_admissible_kg_m2',
                           'charge_admissible_source'),
    _valeur_avec_sa_source('coefficient_securite', 'coefficient_source'),
]}}
RoofLoadResponse = _ser('RoofLoadVerdict', {
    'capacite_kg_m2': s.FloatField(allow_null=True),
    'capacite_source': s.CharField(allow_null=True),
    'masse_ajoutee_kg_m2': s.FloatField(allow_null=True),
    'masse_provenance': s.CharField(allow_null=True),
    'detail_masse': _ser('RoofLoadDetailMasse', {
        'struct_masse_kg_m2': s.FloatField(allow_null=True),
        'module_kg_m2': s.FloatField(allow_null=True),
        'masse_layout_kg_m2': s.FloatField(allow_null=True),
    }),
    'coefficient': _ser('RoofLoadCoefficient', {
        'valeur': s.FloatField(),
        'source': s.CharField(allow_blank=True),
    }, allow_null=True),
    'marge_kg_m2': s.FloatField(allow_null=True),
    'verdict': s.CharField(allow_null=True),
    'message': s.CharField(allow_null=True),
    'alertes': s.ListField(child=s.DictField()),
    'interne': s.BooleanField(),
})

# ------------------------------------------------------ schéma unifilaire
SchemaUnifilaireRequest = _ser('SchemaUnifilaireRequest', {
    'n_panneaux': s.IntegerField(required=False),
    'puissance_panneau_wc': s.IntegerField(required=False),
    'n_strings': s.IntegerField(required=False),
    'onduleur': s.CharField(required=False, allow_blank=True),
    'puissance_onduleur_kw': s.FloatField(required=False),
    'phases': s.IntegerField(required=False),
    'has_battery': s.BooleanField(required=False),
    'injection': s.BooleanField(required=False),
    'titre': s.CharField(required=False, allow_blank=True),
    'etage_mt': s.DictField(required=False, allow_null=True),
})
SchemaUnifilaireJson = _ser('SchemaUnifilaireJson', {
    'params': s.DictField(),
    'svg': s.CharField(),
})
SCHEMA_UNIFILAIRE_RESPONSES = {
    (200, 'application/json'): SchemaUnifilaireJson,
    (200, 'image/svg+xml'): OpenApiTypes.STR,
    (200, 'application/pdf'): OpenApiTypes.BINARY,
}


# =============================================================== pages publiques
# Vues AllowAny derrière un jeton ShareLink / PaymentLink (aucune
# authentification : seuls les statuts propres à ces vues sont déclarés ici,
# le crochet ENF2 ajoute 400/404/409/429/500).
def _souple(**kw):
    """Champ servi à ``None`` ou absent selon le devis."""
    return dict(required=False, allow_null=True, **kw)


OtpRequis = _ser('PublicOtpRequis', {'detail': s.CharField()})

PublicDocumentResponses = {
    (200, 'application/pdf'): OpenApiTypes.BINARY,
    403: OtpRequis,
}

PublicBcfResponses = {(200, 'application/pdf'): OpenApiTypes.BINARY}

ProposalDataResponse = _ser('PublicProposalData', {
    'remplace_par': s.DictField(**_souple()),
    'note_client': s.CharField(**_souple(allow_blank=True)),
    'niveau': s.CharField(required=False),
    'apercu_interne': s.BooleanField(required=False),
    'reference': s.CharField(required=False),
    'date': s.CharField(**_souple()),
    'client_name': s.CharField(**_souple(allow_blank=True)),
    'statut': s.CharField(required=False),
    'quote': s.DictField(**_souple()),
    'mode_installation': s.CharField(**_souple(allow_blank=True)),
    'categorie_commerciale': s.CharField(**_souple(allow_blank=True)),
    'mode_kpis': s.DictField(**_souple()),
    'roof_image_url': s.CharField(**_souple(allow_blank=True)),
    'roof_layout': s.DictField(**_souple()),
    'layout_stale': s.BooleanField(required=False),
    'layout_nb_panneaux': s.IntegerField(**_souple()),
    'sld_svg': s.CharField(**_souple(allow_blank=True)),
    'conception_electrique': s.DictField(**_souple()),
    'option_totals': s.DictField(**_souple()),
    'variantes_servables': s.ListField(child=s.CharField(), required=False),
    'accepted': s.BooleanField(required=False),
    'accepte_par_nom': s.CharField(**_souple(allow_blank=True)),
    'date_acceptation': s.CharField(**_souple(allow_blank=True)),
    'monthly_production': s.ListField(child=s.FloatField(), **_souple()),
    'monthly_consumption': s.ListField(child=s.FloatField(), **_souple()),
    'savings_method': s.DictField(**_souple()),
    'hypotheses': s.DictField(**_souple()),
    'savings_model': s.CharField(**_souple(allow_blank=True)),
    'facture_sans_solaire': s.FloatField(**_souple()),
    'facture_avec_solaire_s': s.FloatField(**_souple()),
    'facture_avec_solaire_a': s.FloatField(**_souple()),
    'pct_cut': s.FloatField(**_souple()),
    'annual_before': s.FloatField(**_souple()),
    'annual_after': s.FloatField(**_souple()),
    'coverage_pct': s.FloatField(**_souple()),
    'coverage_estimated': s.BooleanField(**_souple()),
    'nombre_proprietes': s.IntegerField(**_souple()),
    'display_total_multi': s.FloatField(**_souple()),
    'totaux_multi': s.JSONField(**_souple()),
    'multi_villa': s.JSONField(**_souple()),
    'variants': s.ListField(child=s.DictField(), **_souple()),
    'gammes': s.JSONField(**_souple()),
    'resync_apres_envoi': s.JSONField(**_souple()),
    'options_proposees': s.ListField(child=s.DictField(), **_souple()),
    'lignes_structure': s.ListField(child=s.DictField(), **_souple()),
    'niveau_masque': s.ListField(child=s.CharField(), **_souple()),
    'bankable': s.DictField(**_souple()),
    'economies_cumul_25_ans': s.DictField(**_souple()),
    'empreinte_contenu': s.CharField(required=False),
    'offre_expiree': s.BooleanField(required=False),
    'date_expiration': s.CharField(required=False),
    'pdf_disponible': s.BooleanField(required=False),
    'courbes_journalieres': s.DictField(**_souple()),
    'economies_mensuelles': s.DictField(**_souple()),
    'tranche_tarifaire': s.DictField(**_souple()),
    'batterie_regime': s.DictField(**_souple()),
    'balayage_stockage': s.DictField(**_souple()),
    'profils_comparatifs': s.DictField(**_souple()),
    'economies_periodes': s.DictField(**_souple()),
    'estimation_conso': s.DictField(**_souple()),
    'jours_types': s.DictField(**_souple()),
    'dimensionnement_options': s.DictField(**_souple()),
    'production_par_option': s.DictField(**_souple()),
    'paliers_batterie': s.ListField(child=s.DictField(), **_souple()),
    'couverture_batterie': s.DictField(**_souple()),
    'fiche_batterie': s.DictField(**_souple()),
    'offres_tailles': s.DictField(**_souple()),
    'calepinage_options': s.DictField(**_souple()),
    'parametres_site': s.DictField(**_souple()),
    'acompte': s.DictField(**_souple()),
    'date_validite': s.CharField(**_souple(allow_blank=True)),
    'conditions': s.ListField(child=s.DictField(), **_souple()),
    'conditions_titre': s.CharField(**_souple(allow_blank=True)),
    'paiement_moyens': s.ListField(child=s.JSONField(), **_souple()),
    'confirmation_email': s.BooleanField(required=False),
    'synthese_agricole': s.DictField(**_souple()),
    'synthese_ci': s.DictField(**_souple()),
    'signature_entreprise': s.DictField(**_souple()),
})

SuiviPublicResponse = _ser('PublicSuiviPost', {
    'reference': s.CharField(),
    'generated_at': s.CharField(),
    'mis_a_jour_le': s.CharField(allow_null=True),
    'milestones': s.ListField(child=s.DictField()),
})

ContactRequest = _ser('PublicContactRequest', {
    'channel': s.CharField(required=False, allow_blank=True),
    'canal': s.CharField(required=False, allow_blank=True),
    'message': s.CharField(required=False, allow_blank=True),
    'revision_kind': s.CharField(required=False, allow_blank=True),
})
ContactResponse = _ser('PublicContactResponse', {
    'detail': s.CharField(),
    'already_sent': s.BooleanField(),
})
ContactResponses = {200: ContactResponse, 403: DetailResponse}

OtpEnvoye = _ser('PublicOtpEnvoye', {'detail': s.CharField()})
OtpAucunCanal = _ser('PublicOtpAucunCanal', {
    'detail': s.CharField(),
    'code': s.CharField(),
})

AcceptRequest = _ser('PublicAcceptRequest', {
    'nom': s.CharField(required=False, allow_blank=True),
    'name': s.CharField(required=False, allow_blank=True),
    'option': s.CharField(required=False, allow_blank=True),
    'consent_esign': s.BooleanField(required=False),
    'consentement': s.BooleanField(required=False),
    'signature_data_url': s.CharField(required=False, allow_blank=True),
    'signed_at_client': s.CharField(required=False, allow_blank=True),
    'on_behalf_of': s.CharField(required=False, allow_blank=True),
    'otp_code': s.CharField(required=False, allow_blank=True),
    'empreinte_contenu': s.CharField(required=False, allow_blank=True),
    'entreprise': s.DictField(required=False, allow_null=True),
})
AcceptResponse = _ser('PublicAcceptResponse', {
    'detail': s.CharField(),
    'reference': s.CharField(),
    'statut': s.CharField(),
    'accepte_par_nom': s.CharField(allow_blank=True),
    'paiement': _ser('PublicAcomptePaiement', {
        'acompte_ttc': s.CharField(allow_null=True),
        'pourcentage': s.JSONField(allow_null=True),
        'rib': s.CharField(allow_blank=True),
        'message': s.CharField(allow_blank=True),
        'declare_url': s.CharField(),
        'card_payment_url': s.CharField(allow_null=True),
    }),
    'entreprise': _ser('PublicAcceptEntreprise', {
        'raison_sociale': s.CharField(allow_blank=True),
        'signataire_qualite': s.CharField(allow_blank=True),
        'ice': s.CharField(allow_blank=True),
    }, allow_null=True),
})
AcceptRefus = _ser('PublicAcceptRefus', {
    'detail': s.CharField(),
    'code': s.CharField(required=False),
    'champ': s.CharField(required=False),
})

ActivateOptionRequest = _ser('PublicActivateOptionRequest', {
    'ligne_id': s.IntegerField(),
})
ActivateOptionResponse = _ser('PublicActivateOptionResponse', {
    'detail': s.CharField(),
    'ligne_id': s.IntegerField(),
    'designation': s.CharField(allow_blank=True),
})

EngagementRequest = _ser('PublicEngagementRequest', {
    'section': s.CharField(),
    'seconds': s.FloatField(),
    'visit_id': s.CharField(required=False, allow_blank=True),
})

VirementDeclareResponse = _ser('PublicVirementDeclare', {
    'detail': s.CharField(),
    'already': s.BooleanField(required=False),
})

PayPageResponse = _ser('PublicPayPage', {
    'reference': s.CharField(),
    'client_name': s.CharField(allow_blank=True),
    'montant': s.CharField(),
    'montant_initial': s.CharField(),
    'devise': s.CharField(),
    'statut': s.CharField(),
    'paye': s.BooleanField(),
    'expire': s.BooleanField(),
    'rib': s.CharField(allow_null=True, allow_blank=True),
})
PayWebhookResponse = _ser('PublicPayWebhook', {
    'detail': s.CharField(),
    'reference': s.CharField(),
    'montant': s.CharField(),
    'statut': s.CharField(),
})
