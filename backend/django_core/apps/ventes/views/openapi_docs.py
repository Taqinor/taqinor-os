"""ENF5 — formes OpenAPI EXACTES des actions ventes / facturation.

Aucun comportement : ces sérialiseurs ne servent QU'À la description du
schéma (``@extend_schema``). Corps optionnels = tous les champs
``required=False`` (drf-spectacular ne marque un corps requis que s'il porte
un champ requis). Le moteur de devis (règle #4) n'est pas touché.
"""
from decimal import Decimal

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field, inline_serializer
from rest_framework import serializers as s

from core.champs_stricts import BooleenStrict, ChaineStricte
from ..payments.providers import providers_lien_actifs
from ..serializers import (
    DevisSerializer, DevisWriteSerializer, PlanCommissionSerializer,
)
from ..serializers_facturation import (
    AvoirSerializer, FactureSerializer, NoteDebitSerializer,
    PaiementSerializer, RetenueSubieSerializer,
)


def _ser(name, fields, **kwargs):
    return inline_serializer(name, fields, **kwargs)


# ---------------------------------------------------------------- devis
GAMME_ENVOI = ChaineStricte(required=False, allow_blank=True)

_SECTIONS_LIEN = ('roof3d', 'sld', 'pdf', 'bankable', 'economies',
                  'jour_type', 'gammes', 'taille_eco', 'taille_max')
ShareLinkRequest = _ser('DevisShareLinkRequest', {
    'niveau': s.ChoiceField(choices=['standard', 'confiance'],
                            required=False),
    'otp_lecture': s.BooleanField(required=False),
    # Clés fermées (ShareLink.SECTIONS_CLES) : toute autre clé = 400.
    'sections': _ser('DevisShareLinkSections', {
        cle: s.BooleanField(required=False) for cle in _SECTIONS_LIEN},
        required=False),
    'gamme_envoi': GAMME_ENVOI,
    'envoi': s.BooleanField(required=False),
})
ShareLinkResponse = _ser('DevisShareLinkResponse', {
    'token': s.CharField(),
    'path': s.CharField(),
    'token_interne': s.CharField(),
    'path_interne': s.CharField(),
    'gamme': s.DictField(allow_null=True),
    'niveau': s.CharField(),
    'otp_lecture': s.BooleanField(),
    'sections': s.DictField(),
})

EnvoyerEmailRequest = _ser('DevisEnvoyerEmailRequest', {
    'to_email': ChaineStricte(required=False, allow_blank=True),
    'sujet': ChaineStricte(required=False, allow_blank=True),
    'corps': ChaineStricte(required=False, allow_blank=True),
    'pdf_mode': ChaineStricte(required=False, allow_blank=True),
    'gamme_envoi': GAMME_ENVOI,
})
EnvoyerEmailResponse = _ser('DevisEnvoyerEmailResponse', {
    'detail': s.CharField(),
    'log_id': s.IntegerField(),
    'email_statut': s.CharField(),
    'devis_statut': s.CharField(),
    'proposal_path': s.CharField(required=False, allow_null=True),
})
EnvoyerEmailEchec = _ser('DevisEnvoyerEmailEchec', {
    'detail': s.CharField(),
    'log_id': s.IntegerField(),
    'email_statut': s.CharField(),
    'devis_statut': s.CharField(),
})

WhatsappRequest = _ser('DevisWhatsappRequest', {
    'langue': ChaineStricte(required=False, allow_blank=True),
    'gamme_envoi': GAMME_ENVOI,
})
WhatsappResponse = _ser('DevisWhatsappResponse', {
    'wa_url': s.CharField(),
    'phone': s.CharField(),
    'message': s.CharField(),
    'url': s.CharField(),
    'devis_statut': s.CharField(),
})
WhatsappPreviewResponse = _ser('DevisWhatsappPreviewResponse', {
    'wa_url': s.CharField(),
    'phone': s.CharField(),
    'message': s.CharField(),
    'url': s.CharField(),
    'devis_statut': s.CharField(),
    'preview': s.BooleanField(),
    'gamme': s.DictField(allow_null=True),
})

PdfPartageResponse = _ser('DevisPdfPartageResponse', {
    'devis_statut': s.CharField(),
})
ContacterSuperieurRequest = _ser('DevisContacterSuperieurRequest', {
    'message': ChaineStricte(required=False, allow_blank=True),
})
ContacterSuperieurResponse = _ser('DevisContacterSuperieurResponse', {
    'detail': s.CharField(),
    'recipients': s.ListField(child=s.CharField()),
})
RevoquerLienPublicResponse = _ser('DevisRevoquerLienPublicResponse', {
    'revoques': s.IntegerField(),
    'revoque_le': s.DateTimeField(allow_null=True),
})

PdfTaskResponse = _ser('PdfTaskResponse', {
    'task_id': s.CharField(),
    'detail': s.CharField(),
})


class NombreStrict(s.FloatField):
    """Tour 3 M1 — nombre JSON réel : ``"0.8"``, ``true`` → 400 (``FloatField``
    les convertissait en silence : corps hors schéma accepté)."""

    def to_internal_value(self, data):
        if isinstance(data, bool) or not isinstance(data, (int, float)):
            self.fail('invalid')
        return super().to_internal_value(data)


# Échelle bornée (0,01 → ×10) : au-delà, ``Decimal(str(x)).quantize`` des
# quantités levait (500) sur un corps pourtant conforme.
DupliquerVarianteRequest = _ser('DevisDupliquerVarianteRequest', {
    'scales': s.ListField(child=NombreStrict(min_value=0.01, max_value=10),
                          required=False),
    'variante_pct': NombreStrict(required=False),
})
DupliquerVarianteGammeRequest = _ser('DevisDupliquerVarianteGammeRequest', {
    'nom': ChaineStricte(required=False, allow_blank=True),
    'nom_source': ChaineStricte(required=False, allow_blank=True),
    'recommandee': BooleenStrict(required=False),
})

PrefillSiteResponse = _ser('DevisPrefillSiteResponse', {
    'client': s.IntegerField(),
    'profil': s.DictField(allow_null=True),
})

# -------------------------------------------------------------- facture
FactureAnnulerRequest = _ser('FactureAnnulerRequest', {
    'acompte': _ser('FactureAnnulerAcompte', {
        # VNT12 — ``garder_en_avance`` (contrat facture_annulation.json).
        'action': s.ChoiceField(
            choices=['transferer', 'rembourser', 'garder_en_avance'],
            required=False),
        'facture_cible': s.IntegerField(required=False),
    }, required=False),
})
ExclureRelanceRequest = _ser('FactureExclureRelanceRequest', {
    'exclu': s.BooleanField(required=False),
})
FactureWhatsappRequest = _ser('FactureWhatsappRequest', {
    'modele': s.ChoiceField(choices=['facture', 'relance'], required=False),
    'langue': ChaineStricte(required=False, allow_blank=True),
})
FactureWhatsappResponse = _ser('FactureWhatsappResponse', {
    'wa_url': s.CharField(),
    'phone': s.CharField(),
    'message': s.CharField(),
    'url': s.CharField(),
})
LienPaiementRequest = _ser('FactureLienPaiementRequest', {
    # Liste blanche des fournisseurs qui savent ouvrir un lien (AFAC21).
    'provider': s.ChoiceField(choices=providers_lien_actifs(),
                              required=False),
})
LienPaiementResponse = _ser('FactureLienPaiementResponse', {
    'token': s.CharField(),
    'statut': s.CharField(),
    'montant': s.CharField(),
    'montant_a_payer': s.CharField(),
    'provider': s.CharField(),
    'pay_url': s.CharField(allow_null=True),
    'expires_at': s.DateTimeField(),
})
RevoquerLienPaiementResponse = _ser('FactureRevoquerLienPaiementResponse', {
    'detail': s.CharField(),
    'revoque': s.BooleanField(),
    'token': s.CharField(required=False),
    'statut': s.CharField(required=False),
})
CreerNoteDebitRequest = _ser('FactureCreerNoteDebitRequest', {
    'motif': s.CharField(required=False, allow_blank=True),
    'lignes': s.ListField(child=s.DictField(), required=False),
})

# ------------------------------------------------------- relevé bancaire
ReleveDryRunRequest = _ser('ReleveImportDryRunRequest', {
    'file': s.FileField(),
})
ReleveCommitRequest = {
    'application/json': {
        'type': 'object',
        'required': ['token'],
        'properties': {
            'token': {'type': 'string'},
            # Numéros de ligne validés, ou `{ligne, facture_reference}` pour
            # une ligne ambiguë résolue (AFAC6).
            'lignes': {
                'type': 'array',
                'items': {
                    'oneOf': [
                        {'type': 'integer'},
                        {'type': 'object',
                         'required': ['ligne'],
                         'properties': {
                             'ligne': {'type': 'integer'},
                             'facture_reference': {'type': 'string'}}},
                    ],
                },
            },
        },
    },
}

ReleveDryRunResponse = _ser('ReleveImportDryRunResponse', {
    'token': s.CharField(),
    'columns': s.DictField(child=s.CharField()),
    'unmapped': s.ListField(child=s.CharField()),
    'total_rows': s.IntegerField(),
    'preview': s.ListField(child=s.DictField()),
    'revue': s.ListField(child=s.DictField()),
    'matched': s.IntegerField(),
    'ambigus': s.IntegerField(),
    'already_paid': s.IntegerField(),
    'deja_importe': s.BooleanField(),
})
ReleveCommitResponse = _ser('ReleveImportCommitResponse', {
    'token': s.CharField(required=False),
    'created': s.IntegerField(),
    'skipped': s.IntegerField(),
    'errors': s.IntegerField(),
    'results': s.ListField(child=s.DictField()),
})

# --------------------------------------------------------------- divers
ResoudrePlanResponse = _ser('PlanCommissionResoudreResponse', {
    'owner': s.IntegerField(allow_null=True),
    'source': s.CharField(),
    'plan': PlanCommissionSerializer(allow_null=True),
})

GammeResponse = _ser('DevisDupliquerVarianteGammeResponse', {
    'source': DevisSerializer(),
    'gamme': DevisSerializer(),
    'gammes': s.ListField(child=s.DictField()),
})

PrixApplicableResponse = _ser('PrixApplicableResponse', {
    'produit': s.IntegerField(),
    'quantite': s.CharField(),
    'prix': s.CharField(),
    'unite': s.CharField(),
    'source': s.CharField(),
    'liste_nom': s.CharField(allow_null=True),
    'remise_volume': s.DictField(),
})

VarianteConfigRequest = _ser('DevisVarianteConfigRequest', {
    # Strictement entre 0 et 100, deux décimales au plus.
    'variante_pct': s.DecimalField(max_digits=5, decimal_places=2,
                                   min_value=Decimal('0.01'),
                                   max_value=Decimal('99.99')),
})
VarianteConfigResponse = _ser('DevisVarianteConfigResponse', {
    'variante_pct': s.CharField(),
})

ConceptionElectriqueRequest = _ser('DevisConceptionElectriqueRequest', {
    cle: s.JSONField(required=False) for cle in (
        'dc_m', 'ac_m', 'phases', 'regime', 'batterie', 'zone_keraunique',
        'temp_froid_c', 'temp_chaud_c', 'longueur_chaine_forcee',
        'plafond_kwc_par_onduleur', 'inclure_prise_terre')
})

ConceptionElectriqueResponse = _ser('DevisConceptionElectriqueResponse', {
    'chaines': s.ListField(child=s.DictField()),
    'conformite': s.DictField(),
    'ratio_dc_ac': s.FloatField(allow_null=True),
    'ratio_ac_dc': s.FloatField(allow_null=True),
    'protections': s.ListField(child=s.DictField()),
    'cables': s.ListField(child=s.DictField()),
    'bom': s.ListField(child=s.DictField()),
    'note': s.ListField(child=s.CharField()),
    'parametres': s.DictField(),
    'materiel': s.DictField(required=False),
    'version_moteur': s.CharField(required=False),
    'schema_version': s.IntegerField(required=False),
    'source_entree': s.DictField(required=False),
})

PdfOptionsRequest = _ser('DevisPdfOptionsRequest', {
    'pdf_mode': s.ChoiceField(choices=['full', 'onepage'], required=False),
    'show_monthly': s.BooleanField(required=False),
    'devis_final': s.BooleanField(required=False),
    'include_etude': s.BooleanField(required=False),
    'include_calepinage': s.BooleanField(required=False, allow_null=True),
    'include_note_calcul': s.BooleanField(required=False),
    'kit_agrege': s.BooleanField(required=False),
    'variante_option': s.CharField(required=False),
    'include_annexe_technique': s.JSONField(required=False),
    'langue_sortie': s.CharField(required=False),
})

EnregistrerAvanceRequest = _ser('PaiementEnregistrerAvanceRequest', {
    'client': s.IntegerField(),
    'montant': s.DecimalField(max_digits=12, decimal_places=2),
    'date_paiement': s.DateField(required=False),
    'mode': s.CharField(required=False),
    'reference': s.CharField(required=False, allow_blank=True),
    'note': s.CharField(required=False, allow_blank=True),
})
VentilerRequest = _ser('PaiementVentilerRequest', {
    'facture': s.IntegerField(),
    'montant': s.DecimalField(max_digits=12, decimal_places=2),
})


# =============================================================== ENF11 — devis
# Corps et réponses RÉELS des actions de ``DevisViewSet`` que le fuzz a prises
# en défaut : sans déclaration, le schéma leur prêtait le sérialiseur du
# viewset (``Devis``) en entrée COMME en sortie.
#: Jeton d'édition optimiste (QJR545), optionnel sur toute écriture.
_JETON = s.CharField(required=False, allow_blank=True, allow_null=True)

ErreurDetail = _ser('DevisErreurDetail', {'detail': s.CharField()})
ErreurDevisFige = _ser('DevisErreurFige', {
    'detail': s.CharField(),
    'code': s.CharField(required=False),
})
ErreurGarde = _ser('DevisErreurGarde', {
    'detail': s.CharField(),
    'champ': s.CharField(required=False),
    'credit_hold': s.BooleanField(required=False),
    'sale_warning': s.BooleanField(required=False),
})

# -------------------------------------------------- composition / auto / layout
CompositionRequest = {
    'application/json': {
        'type': 'object',
        'description': (
            'Une puissance (`kwc`) OU un nombre de panneaux (`nb_panneaux`) '
            'est requis(e), strictement positif(ve).'),
        'properties': {
            'kwc': {'type': 'number', 'exclusiveMinimum': True,
                    'minimum': 0},
            'nb_panneaux': {'type': 'integer', 'minimum': 1},
            'panel_watt': {'type': 'number', 'exclusiveMinimum': True,
                           'minimum': 0},
            'scenario': {'type': 'string'},
            'structure_produit_id': {'type': 'integer', 'nullable': True},
            'structure_type': {'type': 'string'},
            'taux_tva': {'type': 'number', 'minimum': 0, 'maximum': 100},
            'mppt_paires': {'type': 'integer', 'minimum': 1},
            'hors_reseau': {'type': 'boolean'},
            'lead': {'type': 'integer', 'nullable': True},
            'dimensionnement_avec': {
                'type': 'object',
                'properties': {
                    'nb_panneaux': {'type': 'number'},
                    'kwc': {'type': 'number'},
                    'batterie_kwh': {'type': 'number'},
                },
            },
        },
        'anyOf': [{'required': ['kwc']}, {'required': ['nb_panneaux']}],
    },
}
CompositionResponse = _ser('DevisCompositionResponse', {
    'lignes': s.ListField(child=s.DictField()),
    'scenario': s.CharField(allow_null=True),
    'nb_panneaux': s.IntegerField(),
    'panel_watt': s.FloatField(),
    'kwc_reel': s.FloatField(),
    'blocs': s.IntegerField(required=False),
    'variantes': s.BooleanField(required=False),
    'nb_panneaux_avec': s.IntegerField(required=False, allow_null=True),
    'kwc_reel_avec': s.FloatField(required=False, allow_null=True),
    'avertissements': s.ListField(child=s.CharField(), required=False),
    'marques_manquantes': s.ListField(child=s.CharField(), required=False),
})
ErreurComposition = _ser('DevisErreurComposition', {
    'detail': s.CharField(),
    'field': s.CharField(required=False, allow_null=True),
})

AutoDevisRequest = _ser('DevisAutoRequest', {
    'lead': s.IntegerField(required=False, allow_null=True),
    'client': s.IntegerField(required=False, allow_null=True),
    'target_kwc': s.FloatField(required=False, allow_null=True),
    'scenario': s.CharField(required=False, allow_blank=True,
                            allow_null=True),
    'etude_params': s.DictField(required=False, allow_null=True),
    'taux_tva': s.FloatField(required=False, allow_null=True),
    'remise_globale': s.FloatField(required=False, allow_null=True),
    'structure_produit_id': s.IntegerField(required=False, allow_null=True),
    'structure_type': s.CharField(required=False, allow_blank=True,
                                  allow_null=True),
})
AutoDevisResponse = _ser('DevisAutoResponse', {
    'id': s.IntegerField(),
    'reference': s.CharField(),
    'statut': s.CharField(),
    'kwc': s.FloatField(allow_null=True),
    'nb_lignes': s.IntegerField(),
    'proposal_token': s.CharField(),
    'proposal_path': s.CharField(),
    'alertes': s.ListField(child=s.JSONField()),
})

FromLayoutRequest = _ser('DevisFromLayoutRequest', {
    'layout': s.DictField(),
    'lead': s.IntegerField(required=False, allow_null=True),
    'client': s.IntegerField(required=False, allow_null=True),
    'taux_tva': s.FloatField(required=False, allow_null=True),
    'remise_globale': s.FloatField(required=False, allow_null=True),
    'structure_produit_id': s.IntegerField(required=False, allow_null=True),
    'structure_type': s.CharField(required=False, allow_blank=True,
                                  allow_null=True),
    'calepinage': s.IntegerField(required=False, allow_null=True),
})
FromLayoutResponse = _ser('DevisFromLayoutResponse', {
    'id': s.IntegerField(),
    'reference': s.CharField(),
    'statut': s.CharField(),
    'proposal_token': s.CharField(),
    'proposal_path': s.CharField(),
    'avertissements': s.ListField(child=s.CharField()),
    'marques_manquantes': s.ListField(child=s.CharField()),
    'deduplicated': s.BooleanField(required=False),
})
ErreurFromLayout = _ser('DevisErreurFromLayout', {
    'detail': s.CharField(required=False),
    'errors': s.ListField(child=s.CharField(), required=False),
    'champ': s.CharField(required=False),
})

#: ``roof_layout`` : document de conception 3D (AreaRecord[] + result +
#: renderPlan) — objet libre à clés non préfixées ``_`` (cf.
#: ``resynchronisation._sans_cles_privees``).
LayoutRequest = {'application/json': {'type': 'object',
                                      'additionalProperties': True}}
LayoutResponse = _ser('DevisLayoutResponse', {
    'roof_layout': s.JSONField(allow_null=True),
})
SyncLayoutResponse = _ser('DevisSyncLayoutResponse', {
    'inchange': s.BooleanField(required=False),
    'panneaux': s.IntegerField(required=False),
    'kwc': s.FloatField(required=False),
    'scenario': s.CharField(required=False),
    'batterie': s.BooleanField(required=False),
    'lignes_modifiees': s.IntegerField(required=False),
    'lignes_ajoutees': s.IntegerField(required=False),
    'avertissements': s.ListField(child=s.CharField(), required=False),
    'electrique': s.DictField(required=False, allow_null=True),
})
ErreurSyncLayout = _ser('DevisErreurSyncLayout', {
    'detail': s.CharField(required=False),
    'revision_possible': s.BooleanField(required=False),
})

DesignContextResponse = _ser('DevisDesignContext', {
    'devis': s.DictField(),
    'geometrie': s.DictField(),
    'cible': s.DictField(),
    'cible_avec': s.DictField(required=False, allow_null=True),
    'carte': s.DictField(),
    'modifiable': s.BooleanField(),
    'raison_lecture_seule': s.CharField(allow_blank=True, allow_null=True),
    'avertissements': s.ListField(child=s.CharField()),
    'zones_types': s.DictField(required=False),
    'degagements': s.DictField(required=False),
})

RoofImageRequest = {
    'multipart/form-data': {
        'type': 'object',
        'properties': {'image': {'type': 'string', 'format': 'binary'}},
        'required': ['image'],
    },
}
RoofImageResponse = _ser('DevisRoofImageResponse', {
    'roof_image': s.CharField(),
    'url': s.CharField(),
})

SimulerRequest = _ser('DevisSimulerRequest', {
    'force_refresh': s.BooleanField(required=False),
})
SimulerResponse = _ser('DevisSimulerResponse', {
    'detail': s.CharField(),
    'job_id': s.CharField(),
    'status': s.CharField(),
    'zones': s.IntegerField(),
    'status_url': s.CharField(),
})

# ------------------------------------------------------------ atomic / lignes


class DevisAtomic(DevisWriteSerializer):
    """Corps de ``POST /devis/atomic/`` : les champs d'en-tête du devis (comme
    ``POST /devis/``) + ``lignes`` (au moins une) + ``etude_params`` (écrit
    par l'écrivain unique d'étude, pas par le sérialiseur d'en-tête)."""
    lignes = s.ListField(child=s.DictField(), min_length=1)
    etude_params = s.DictField(required=False, allow_null=True)

    class Meta(DevisWriteSerializer.Meta):
        fields = list(DevisWriteSerializer.Meta.fields) + ['lignes']


ReplaceLinesRequest = _ser('DevisReplaceLinesRequest', {
    'lignes': s.ListField(child=s.DictField(), min_length=1),
    'entete': s.DictField(required=False, allow_null=True),
    'etude_params': s.DictField(required=False, allow_null=True),
    'expected_updated_at': _JETON,
})

# --------------------------------------------------------------- cycle de vie
DeriveResponse = _ser('DevisDeriveResponse', {
    'devis': DevisSerializer(),
    'champs_repris': s.ListField(child=s.CharField()),
    'corrige_apres_envoi': s.BooleanField(),
    'avertissements': s.ListField(child=s.CharField()),
})

AccepterRequest = _ser('DevisAccepterRequest', {
    'nom': ChaineStricte(required=False, allow_blank=True),
    'date': ChaineStricte(required=False, allow_blank=True),
    'option': ChaineStricte(required=False, allow_blank=True),
    'entreprise': s.DictField(required=False, allow_null=True),
    'override_credit': BooleenStrict(required=False),
    'override_avertissement': BooleenStrict(required=False),
})
RefuserRequest = _ser('DevisRefuserRequest', {
    'motif': ChaineStricte(required=False, allow_blank=True),
    'note': ChaineStricte(required=False, allow_blank=True),
    'date': ChaineStricte(required=False, allow_blank=True),
    'marquer_lead_perdu': BooleenStrict(required=False),
})
#: Au moins un caractère non blanc (le serveur ``strip()`` puis refuse le vide).
_NON_BLANC = r'\S'
NoterRequest = _ser('DevisNoterRequest', {
    'body': s.RegexField(_NON_BLANC),
})
SavePresetRequest = _ser('DevisSavePresetRequest', {
    'nom': s.RegexField(_NON_BLANC, max_length=150),
    'description': s.CharField(required=False, allow_blank=True),
})

LotCreationRequest = _ser('DevisLotCreationRequest', {
    'nom_lot': s.CharField(),
    'adresse_site': s.CharField(required=False, allow_blank=True),
    'ordre': s.IntegerField(required=False),
    'lignes': s.ListField(child=s.IntegerField(), required=False),
})
LotsResponse = _ser('DevisLotsResponse', {
    'lots': s.ListField(child=s.DictField()),
    'hors_lot': s.JSONField(allow_null=True),
    'total_consolide': s.JSONField(allow_null=True),
})

HistoriqueConfigurationResponse = _ser('DevisHistoriqueConfiguration', {
    'snapshots': _ser('DevisConfigSnapshot', {
        'id': s.IntegerField(),
        'date': s.CharField(),
        'auteur': s.CharField(allow_null=True),
        'nb_lignes': s.IntegerField(),
        'contenu': s.DictField(),
    }, many=True),
    'diff': s.DictField(required=False),
})

# ------------------------------------------------------------ études / lecture
OverridesPatchRequest = {
    'application/json': {
        'type': 'object',
        'description': (
            'Carte `{chemin: valeur}` ou `{chemin: {valeur, origine?}}` '
            'fusionnée dans le registre. Liste blanche fermée (D12).'),
        'minProperties': 1,
        'additionalProperties': False,
        'properties': {
            chemin: {} for chemin in (
                'taille.nb_panneaux', 'taille.panel_watt', 'taille.kwc',
                'scenario', 'recommended_option', 'etude.jour_reference')
        },
    },
}
OverridesResponse = _ser('DevisOverridesResponse', {
    'overrides': s.DictField(),
    'effectif': s.DictField(),
    'lignes': s.DictField(),
    'updated_at': s.CharField(required=False, allow_null=True),
})
EtudeParamsGetResponse = _ser('DevisEtudeParamsResponse', {
    'etude_params': s.DictField(),
    'updated_at': s.CharField(required=False, allow_null=True),
})
EtudeParamsPatchRequest = {
    'application/json': {
        'type': 'object',
        'description': (
            "Clés d'étude à fusionner (une valeur `null` retire la clé) ; "
            '`expected_updated_at` : jeton optimiste optionnel.'),
        'minProperties': 1,
        'additionalProperties': True,
    },
}
OffresTaillesResponse = _ser('DevisOffresTailles', {
    'offres_tailles': s.DictField(allow_null=True),
    'editable': s.BooleanField(),
    'raison_non_editable': s.CharField(required=False),
    'applique': s.DictField(required=False),
    'updated_at': s.CharField(required=False, allow_null=True),
})
LectureClientResponse = _ser('DevisLectureClient', {
    'sections': s.DictField(),
    'friction': s.JSONField(allow_null=True),
})
SuperiorContactStatusResponse = _ser('DevisSuperiorContactStatus', {
    'requested': s.BooleanField(),
    'seen': s.BooleanField(required=False),
    'seen_by': s.ListField(child=s.CharField(), required=False),
    'requested_at': s.DateTimeField(required=False),
})
EtatPdfResponse = _ser('DevisEtatPdf', {
    'devis': s.IntegerField(),
    'statut': s.ChoiceField(choices=['pret', 'en_cours', 'echec']),
    'fichier_pdf': s.BooleanField(),
    'erreur': s.CharField(allow_null=True),
    'date': s.JSONField(allow_null=True),
})

EconomieResponse = _ser('DevisEconomie', {
    'horizon_ans': s.IntegerField(allow_null=True),
    'flux': s.ListField(child=s.DictField()),
    'van_mad': s.FloatField(allow_null=True),
    'tri_pct': s.FloatField(allow_null=True),
    'lcoe_mad_kwh': s.FloatField(allow_null=True),
    'retour_ans': s.FloatField(allow_null=True),
    'retour_actualise_ans': s.FloatField(allow_null=True),
    'hypotheses': s.ListField(child=s.DictField()),
    'omissions': s.ListField(child=s.DictField()),
})
_BLOC = dict(required=False, allow_null=True)
EconomieCiResponse = _ser('DevisEconomieCi', {
    'statut': s.CharField(),
    'motifs_omission': s.ListField(child=s.CharField()),
    'base': s.CharField(**_BLOC),
    'motif_base': s.CharField(**_BLOC),
    'tarif': s.DictField(**_BLOC),
    'economie_annee1': s.DictField(**_BLOC),
    'facture_avant': s.DictField(**_BLOC),
    'facture_apres': s.DictField(**_BLOC),
    'revente': s.DictField(**_BLOC),
    'flux_ht': s.DictField(**_BLOC),
    'flux_ttc': s.DictField(**_BLOC),
    'jalons': s.ListField(child=s.DictField(), **_BLOC),
    'jalons_ttc': s.ListField(child=s.DictField(), **_BLOC),
    'indicateurs': s.DictField(**_BLOC),
    'remplacements': s.ListField(child=s.DictField(), **_BLOC),
    'om': s.DictField(**_BLOC),
    'sensibilites': s.ListField(child=s.DictField(), **_BLOC),
    'financement': s.DictField(**_BLOC),
    'hypotheses': s.ListField(child=s.DictField(), **_BLOC),
    'omissions': s.ListField(child=s.DictField(), **_BLOC),
    'alertes_internes': s.ListField(child=s.DictField(), **_BLOC),
    'vue_interne': s.DictField(**_BLOC),
})
EconomiePompageResponse = _ser('DevisEconomiePompage', {
    'statut': s.CharField(),
    'publiable_client': s.BooleanField(),
    'motifs_non_publiable': s.ListField(child=s.CharField()),
    'cas': s.CharField(**_BLOC),
    'entrees_declarees': s.ListField(child=s.DictField(), **_BLOC),
    'depense_actuelle': s.DictField(**_BLOC),
    'charges_solaires': s.DictField(**_BLOC),
    'remplacements': s.ListField(child=s.DictField(), **_BLOC),
    'economie': s.DictField(**_BLOC),
    'couverture': s.DictField(**_BLOC),
    'mad_par_m3': s.DictField(**_BLOC),
    'sensibilite_carburant': s.ListField(child=s.DictField(), **_BLOC),
    'seuil_rentabilite_carburant': s.DictField(**_BLOC),
    'financement': s.DictField(**_BLOC),
    'coherence': s.ListField(child=s.DictField(), **_BLOC),
    'reperes_affiches': s.ListField(child=s.DictField(), **_BLOC),
    'omissions': s.ListField(child=s.DictField(), **_BLOC),
    'vue_interne': s.DictField(**_BLOC),
})
ErreurEconomie = _ser('DevisErreurEconomie', {
    'detail': s.CharField(),
    'champ': s.CharField(required=False, allow_null=True),
})

# --------------------------------------------------------------- facturation
FacturerCompletRequest = _ser('DevisFacturerCompletRequest', {
    'paiements': s.ListField(child=s.DictField(), required=False,
                             max_length=5),
    'override_credit': BooleenStrict(required=False),
    'override_avertissement': BooleenStrict(required=False),
})
FacturerCompletResponse = _ser('DevisFacturerCompletResponse', {
    'facture_id': s.IntegerField(),
    'facture_reference': s.CharField(),
    'statut': s.CharField(),
    'total_ttc': s.CharField(),
    'montant_paye': s.CharField(),
    'montant_du': s.CharField(),
    'paiements': _ser('DevisFacturerCompletPaiement', {
        'id': s.IntegerField(),
        'montant': s.CharField(),
        'date_paiement': s.CharField(),
        'mode_paiement': s.CharField(),
        'reference': s.CharField(allow_blank=True),
    }, many=True),
})
# VNT31 — « Facturer la vente » (contrat ``devis_facturer.json``) : montants
# en TEXTE décimal, natures = ``Facture.TypeFacture``.
FacturerVenteRequest = _ser('DevisFacturerVenteRequest', {
    # acompte | intermediaire | solde | complete (validée par le service).
    'nature': ChaineStricte(),
    'montant_ttc': ChaineStricte(required=False, allow_null=True,
                                 allow_blank=True),
    'pourcentage': ChaineStricte(required=False, allow_null=True,
                                 allow_blank=True),
    'cle_attendue': ChaineStricte(required=False, allow_null=True,
                                  allow_blank=True),
    'libelle': ChaineStricte(required=False, allow_null=True,
                             allow_blank=True),
    'emettre': BooleenStrict(required=False),
    'paiements': s.ListField(child=s.DictField(), required=False,
                             max_length=5),
    'remplacer_brouillons': BooleenStrict(required=False),
    'utiliser_avances': BooleenStrict(required=False),
    'override_avertissement': BooleenStrict(required=False),
    # XFAC28 — responsable/admin : passe outre le blocage crédit à
    # l'émission (comme ``generer-facture``), journalisé.
    'override_credit': BooleenStrict(required=False),
})
FacturerVenteMontants = _ser('DevisFacturerVenteMontants', {
    cle: s.CharField() for cle in (
        'prix_convenu_ttc', 'emis_ttc', 'brouillons_ttc', 'paye_ttc',
        'reste_a_facturer_ttc', 'reste_a_payer_ttc')})
FacturerVenteResponse = _ser('DevisFacturerVenteResponse', {
    'facture': _ser('DevisFacturerVenteFacture', {
        'id': s.IntegerField(), 'reference': s.CharField(),
        'statut': s.CharField(), 'total_ttc': s.CharField(),
        'nature': s.CharField()}),
    'vente': FacturerVenteMontants,
})
FacturerVenteApercu = _ser('DevisFacturerVenteApercu', {
    'plan': _ser('DevisFacturerVentePlanLigne', {
        cle: s.CharField() for cle in (
            'cle', 'libelle', 'unite', 'valeur', 'montant_ttc', 'statut')},
        many=True),
    'prochaine': _ser('DevisFacturerVenteProchaine', {
        cle: s.CharField() for cle in ('cle', 'libelle', 'montant_ttc')},
        allow_null=True),
    'acompte_propose': s.CharField(),
    'vente': FacturerVenteMontants,
})
ErreurFacturerVente = _ser('DevisFacturerVenteErreur', {
    'detail': s.CharField(),
    'code': s.CharField(required=False),
})
GenererFactureRequest = _ser('DevisGenererFactureRequest', {
    'override_credit': s.BooleanField(required=False),
    'override_avertissement': s.BooleanField(required=False),
})


# ========================================================= ENF11 — facturation
# Bons de commande, factures, paiements, avoirs : corps et réponses RÉELS.
LigneLivraison = _ser('BonCommandeLigneLivraison', {
    'ligne_devis': s.IntegerField(),
    'quantite': s.DecimalField(max_digits=12, decimal_places=2,
                               min_value=Decimal('0.01')),
})
LivrerPartielRequest = _ser('BonCommandeLivrerPartielRequest', {
    'lignes': s.ListField(child=LigneLivraison, min_length=1),
    'date_livraison': s.DateField(required=False, allow_null=True),
    'note': s.CharField(required=False, allow_blank=True, max_length=255),
})
MarquerLivreJson = _ser('BonCommandeMarquerLivreJson', {
    'signataire': s.CharField(required=False, allow_blank=True),
    'note_pv': s.CharField(required=False, allow_blank=True),
})
MarquerLivreRequest = {
    'application/json': MarquerLivreJson,
    'multipart/form-data': {
        'type': 'object',
        'properties': {
            'signataire': {'type': 'string'},
            'note_pv': {'type': 'string'},
            'pv': {'type': 'string', 'format': 'binary'},
        },
    },
}

_MOTIFS_ABANDON = ['irrecouvrable', 'geste_commercial', 'ecart_reglement',
                   'liquidation', 'arrondi_caisse']


class FactureAbandonnee(FactureSerializer):
    """Réponse de ``abandonner-solde`` : la facture + le montant soldé."""
    montant_abandonne = s.FloatField()


class FactureAbandonRepris(FactureSerializer):
    """Réponse de ``reprendre-abandon`` : la facture + l'abandon repris."""
    abandon_repris = s.IntegerField()
    montant_repris = s.CharField()


class FactureRelancee(FactureSerializer):
    """Réponse de ``relancer`` : la facture + l'e-mail éventuellement parti."""
    email_log_id = s.IntegerField(allow_null=True)


class FactureEmise(FactureSerializer):
    """Réponse de ``emettre`` : la facture + les anomalies légales éventuelles."""
    anomalies = s.ListField(child=s.CharField(), required=False)


class FactureCreeeDepuisBc(FactureSerializer):
    """Réponse de ``creer-facture`` : la facture + l'avertissement doux."""
    warnings = s.ListField(child=s.CharField(), required=False)


class FactureAnnulee(FactureSerializer):
    """Réponse de ``annuler`` (VNT4, ``facture_annulation.json``) : la
    facture + l'avoir de contre-passation (``null`` pour un brouillon)."""
    avoir = _ser('FactureAnnulationAvoir', {
        'id': s.IntegerField(), 'reference': s.CharField(),
        'montant': s.CharField()}, allow_null=True)


#: VNT14 — DELETE d'une facture refusé (409, ENF11 ConflitEtat) : pas un brouillon, ou
#: ``code: reference_legale`` (numéro légal remis en brouillon).
ErreurSuppressionFacture = _ser('FactureErreurSuppression', {
    'detail': s.CharField(), 'code': s.CharField(required=False)})


MarquerPayeeRequest = _ser('FactureMarquerPayeeRequest', {
    'motif': s.RegexField(_NON_BLANC),
})
AbandonnerSoldeRequest = _ser('FactureAbandonnerSoldeRequest', {
    'motif': s.ChoiceField(choices=_MOTIFS_ABANDON),
})
ReprendreAbandonRequest = _ser('FactureReprendreAbandonRequest', {
    'motif': s.RegexField(_NON_BLANC),
    'abandon': s.IntegerField(required=False, allow_null=True),
})
LibererRetenueRequest = _ser('FactureLibererRetenueRequest', {
    'date': s.DateField(),
})
ErreurRetenue = _ser('FactureErreurChamp', {
    'detail': s.CharField(),
    'champ': s.CharField(required=False),
    'code': s.CharField(required=False),
    'action_attendue': s.CharField(required=False),
})
EnvoyerEmailFactureRequest = _ser('FactureEnvoyerEmailRequest', {
    'to_email': ChaineStricte(required=False, allow_blank=True),
    'sujet': ChaineStricte(required=False, allow_blank=True),
    'corps': ChaineStricte(required=False, allow_blank=True),
    'attach_pdf': BooleenStrict(required=False),
})
EnvoyerEmailFactureResponse = _ser('FactureEnvoyerEmailResponse', {
    'detail': s.CharField(),
    'email_log_id': s.IntegerField(),
    'to_email': s.CharField(allow_blank=True, allow_null=True),
})
#: 400 de l'envoi : échec d'envoi (``detail`` + ``email_log_id``) OU corps
#: invalide (erreurs par champ de l'enveloppe commune) — d'où des clés toutes
#: facultatives, les autres clés (champs, ``error``) restant admises.
ErreurEnvoiEmail = _ser('FactureErreurEnvoiEmail', {
    'detail': s.CharField(required=False),
    'email_log_id': s.IntegerField(required=False),
})

# Tour 3 M1 — bornes = celles de ``_montants_ligne_corrective`` (vue
# facture), publiées DANS le motif du décimal-chaîne (drf-spectacular n'émet
# ni minimum ni maximum pour une chaîne) : un corps conforme au schéma n'est
# plus refusé en 400, un corps hors bornes l'est par le sérialiseur.
_MONTANT_LIGNE_MAX = Decimal('99999999.99')
_MOTIF_STRICT_POSITIF = r'^0*(?:[1-9]\d{0,7}(?:\.\d{0,2})?|\.(?:[1-9]\d?|0[1-9]))$'
_MOTIF_POSITIF = r'^(?:\d{1,8}(?:\.\d{0,2})?|\.\d{1,2})$'
_MOTIF_POURCENT = r'^(?:100(?:\.0{0,2})?|\d{1,2}(?:\.\d{0,2})?|\.\d{1,2})$'


def _decimal_publie(motif):
    """Classe ``DecimalField`` dont le schéma publié est ``motif``."""
    return extend_schema_field(
        {'type': 'string', 'format': 'decimal', 'pattern': motif})(
        type('DecimalBorne', (s.DecimalField,), {}))


_QuantiteLigne = _decimal_publie(_MOTIF_STRICT_POSITIF)
_MontantLigne = _decimal_publie(_MOTIF_POSITIF)
_PourcentLigne = _decimal_publie(_MOTIF_POURCENT)
LigneAvoirCorrective = _ser('FactureLigneAvoirCorrective', {
    'produit': s.IntegerField(),
    'designation': s.CharField(),
    'quantite': _QuantiteLigne(max_digits=12, decimal_places=2,
                               min_value=Decimal('0.01'),
                               max_value=_MONTANT_LIGNE_MAX),
    'prix_unitaire': _MontantLigne(max_digits=12, decimal_places=2,
                                   min_value=Decimal('0'),
                                   max_value=_MONTANT_LIGNE_MAX),
    'remise': _PourcentLigne(max_digits=5, decimal_places=2,
                             min_value=Decimal('0'),
                             max_value=Decimal('100'), required=False),
    'taux_tva': _PourcentLigne(max_digits=5, decimal_places=2,
                               min_value=Decimal('0'),
                               max_value=Decimal('100'),
                               required=False, allow_null=True),
})
CreerAvoirRequest = _ser('FactureCreerAvoirRequest', {
    'mode': s.ChoiceField(choices=['correction', 'contre_passation'],
                          required=False),
    'motif': s.CharField(required=False, allow_blank=True),
    'type': s.ChoiceField(
        choices=['correction', 'geste_commercial', 'retour'],
        required=False),
    'lignes': s.ListField(child=LigneAvoirCorrective, required=False,
                          allow_null=True),
})
LigneRetour = _ser('FactureLigneRetour', {
    'produit': s.IntegerField(),
    'quantite': s.DecimalField(max_digits=12, decimal_places=2),
})
RetourClientRequest = _ser('FactureRetourClientRequest', {
    'motif': s.RegexField(_NON_BLANC),
    'lignes': s.ListField(child=LigneRetour, min_length=1),
    'restocker': s.BooleanField(required=False),
})

RelanceApercuResponse = _ser('FactureRelanceApercu', {
    'facture_id': s.IntegerField(),
    'facture_reference': s.CharField(),
    'montant_du': s.CharField(),
    'jours_retard': s.IntegerField(),
    'niveaux': s.ListField(child=s.DictField()),
    'niveau_suivant': s.DictField(allow_null=True),
    'deja_tous_envoyes': s.BooleanField(),
    'relances_envoyees': s.IntegerField(),
    'email_client': s.CharField(allow_blank=True, allow_null=True),
    'peut_envoyer_email': s.BooleanField(),
    'sujet': s.CharField(allow_blank=True),
    'message': s.CharField(allow_blank=True),
})
ArrondiCaisseResponse = _ser('FactureArrondiCaisse', {
    'applicable': s.BooleanField(),
    'montant_du': s.CharField(),
    'montant_arrondi': s.CharField(),
    'ecart': s.CharField(),
    'pas': s.CharField(),
})
ConsoliderRequest = _ser('FactureConsoliderRequest', {
    'devis_ids': s.ListField(child=s.IntegerField(), min_length=2),
})
EncaissementGroupeRequest = _ser('FactureEncaissementGroupeRequest', {
    'client': s.IntegerField(min_value=1),
    # Montant STRICTEMENT positif, 2 décimales : le motif exclut "" et "0",
    # que le décimal générique du schéma laisserait passer.
    'montant': s.RegexField(
        r'^(?:[1-9][0-9]{0,9}(?:\.[0-9]{1,2})?|0\.(?:0[1-9]|[1-9][0-9]?))$'),
    'factures': s.ListField(child=s.IntegerField(min_value=1), min_length=1),
    'mode': s.ChoiceField(
        choices=['especes', 'virement', 'cheque', 'carte', 'prelevement',
                 'autre'], required=False),
    'date': s.DateField(required=False),
    'reference': s.CharField(required=False, allow_blank=True,
                             max_length=120),
    'repartition': s.DictField(child=s.DecimalField(
        max_digits=12, decimal_places=2), required=False, allow_null=True),
})
BulkRequest = _ser('FactureBulkRequest', {
    'action': s.ChoiceField(
        choices=['emettre', 'envoyer-email', 'generer-pdf', 'relancer']),
    'ids': s.ListField(child=s.IntegerField()),
})
BulkResponse = {
    200: {
        'type': 'object',
        'description': 'Résultat par id de facture : `{id: {ok, detail}}`.',
        'additionalProperties': {
            'type': 'object',
            'properties': {
                'ok': {'type': 'boolean'},
                'detail': {'type': 'string'},
                'reference': {'type': 'string'},
                'task_id': {'type': 'string'},
            },
            'required': ['ok', 'detail'],
        },
    },
}
UblXml = {(200, 'application/xml'): OpenApiTypes.BINARY}
PdfBinaire = {(200, 'application/pdf'): OpenApiTypes.BINARY}
DgiConformiteResponse = _ser('FactureDgiConformite', {
    'conforme': s.BooleanField(),
    'problemes': s.ListField(child=s.JSONField()),
})
DgiTransmissionResponse = _ser('FactureDgiTransmission', {
    'dgi_statut': s.CharField(allow_blank=True, allow_null=True),
    'dgi_reference': s.CharField(allow_blank=True, allow_null=True),
    'dgi_motif_rejet': s.CharField(allow_blank=True, allow_null=True),
})


# ---------------------------------------------------------------- paiements
PaiementAvecRetenueResponse = _ser('PaiementAvecRetenueResponse', {
    'paiement': PaiementSerializer(),
    'retenue': RetenueSubieSerializer(),
    'facture': FactureSerializer(),
})
AttestationRecueRequest = _ser('PaiementAttestationRecueRequest', {
    'attestation_date': s.DateField(required=False),
    'attestation_fichier': s.CharField(required=False, allow_blank=True,
                                       max_length=500),
})
EnvoyerRecuRequest = _ser('PaiementEnvoyerRecuRequest', {
    'to_email': s.CharField(required=False, allow_blank=True,
                            allow_null=True),
})
EnvoyerRecuResponse = _ser('PaiementEnvoyerRecuResponse', {
    'statut': s.CharField(),
    'to_email': s.CharField(allow_blank=True, allow_null=True),
    'erreur': s.CharField(allow_blank=True, allow_null=True),
})
RejeterPaiementRequest = _ser('PaiementRejeterRequest', {
    'motif': s.RegexField(_NON_BLANC),
    'frais': s.DecimalField(max_digits=10, decimal_places=2, required=False,
                            allow_null=True),
    'date_rejet': s.DateField(required=False, allow_null=True),
})
AnnulerSaisieRequest = _ser('PaiementAnnulerSaisieRequest', {
    'motif': s.RegexField(_NON_BLANC),
})
ReaffecterRequest = _ser('PaiementReaffecterRequest', {
    'facture_cible': s.IntegerField(),
})
_FACTURE_RESUME = _ser('PaiementReaffecterFacture', {
    'id': s.IntegerField(),
    'reference': s.CharField(),
    'montant_du': s.CharField(),
    'statut': s.CharField(),
})
ReaffecterResponse = _ser('PaiementReaffecterResponse', {
    'paiement': PaiementSerializer(),
    'facture_source': _FACTURE_RESUME,
    'facture_cible': _FACTURE_RESUME,
})
ErreurCode = _ser('PaiementErreurCode', {
    'detail': s.CharField(),
    'code': s.CharField(required=False),
})
NoteDebitAnnuleeResponse = _ser('NoteDebitAnnulationResponse', {
    'note_debit': NoteDebitSerializer(),
    'avoir': AvoirSerializer(),
    'cree': s.BooleanField(),
})

# --------------------------------------------------------- offres de tailles
OffreTailleCleRequest = _ser('DevisOffreTailleCleRequest', {
    'cle': s.ChoiceField(choices=['eco', 'recommande', 'max']),
    'expected_updated_at': _JETON,
})
OffreTailleConfigRequest = {
    'application/json': {
        'type': 'object',
        'required': ['cle', 'config'],
        'properties': {
            'cle': {'type': 'string', 'enum': ['eco', 'recommande', 'max']},
            # ENTRÉES seulement : tout nombre dérivé ou clé inconnue = 400.
            'config': {
                'type': 'object',
                'minProperties': 1,
                'additionalProperties': False,
                'properties': {
                    'nb_panneaux': {'type': 'integer', 'minimum': 1,
                                    'maximum': 500},
                    'batterie_nb_modules': {'type': 'integer', 'minimum': 0,
                                            'maximum': 100},
                    'equipements': {'type': 'object',
                                    'additionalProperties': {
                                        'type': 'integer'}},
                },
            },
        },
    },
}

# ---------------------------------------------------------- plafond de crédit
CreditWarningResponse = _ser('ClientCreditWarning', {
    'plafond': s.CharField(allow_null=True),
    'encours': s.CharField(),
    'encours_avec_nouveau': s.CharField(allow_null=True),
    'depasse': s.BooleanField(),
    'depassera': s.BooleanField(allow_null=True),
    'message': s.CharField(allow_blank=True, allow_null=True),
    'recouvrement': _ser('ClientCreditWarningRecouvrement', {
        'a_jour': s.BooleanField(),
        'retard_max_jours': s.IntegerField(),
        'niveau_relance': s.DictField(allow_null=True),
        'encours_echu': s.CharField(),
    }),
})
