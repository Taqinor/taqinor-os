"""ENF5 — formes OpenAPI EXACTES des actions ventes / facturation.

Aucun comportement : ces sérialiseurs ne servent QU'À la description du
schéma (``@extend_schema``). Corps optionnels = tous les champs
``required=False`` (drf-spectacular ne marque un corps requis que s'il porte
un champ requis). Le moteur de devis (règle #4) n'est pas touché.
"""
from decimal import Decimal

from django.core.exceptions import ValidationError as _ErreurDjango
from django.core.validators import RegexValidator as _RegexValidator
from drf_spectacular.drainage import set_override
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field, inline_serializer
from rest_framework import serializers as s

from core.champs_stricts import (
    BooleenStrict, ChaineStricte, ChaineUneLigne, DateStricte, DecimalSouple, DecimalStricte,
    EntierStrict, MOTIF_NON_BLANC_SANS_NUL, MOTIF_SANS_NUL,
)
from core.openapi_erreurs import EXTENSION_CORPS_RESSERRE
from core.parseurs import ChoixDocumente
from ..domain.bornes import MOTIF_MONTANT_POSITIF
from ..models import Devis, Paiement, ROLES_AUTO_COMPOSITION
from ..payments.providers import providers_lien_actifs
from ..serializers import (
    DevisSerializer, DevisWriteSerializer, PlanCommissionSerializer,
)
from ..serializers_facturation import (
    AvoirSerializer, FactureListeSerializer, FactureWriteSerializer,
    NoteDebitSerializer, PaiementSerializer, RetenueSubieSerializer,
)


def _ser(name, fields, **kwargs):
    return inline_serializer(name, fields, **kwargs)


class _MotifEntier(_RegexValidator):
    """CI #997 fuzz — ``RegexValidator`` PUBLIÉ tel quel mais appliqué en
    ``fullmatch`` : ``$`` laisserait passer un saut de ligne final."""

    def __call__(self, value):
        if not isinstance(value, str) or not self.regex.fullmatch(value):
            raise _ErreurDjango(self.message, code=self.code)


# ---------------------------------------------------------------- devis
# api-fuzz (24/10/2026) — vocabulaire FERMÉ (``domain.gammes.GAMME_ENVOIS``),
# vide ou absent = mode déjà posé ; tout autre texte est refusé 400 nommé.
GAMME_ENVOI = s.ChoiceField(choices=['seule', 'les_deux'], required=False,
                            allow_blank=True, allow_null=True)

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
    # api-fuzz : une adresse mal formée atteignait le SMTP (« Invalid address »
    # → 502) ; elle est refusée 400 et publiée ``format: email``.
    'to_email': s.EmailField(required=False, allow_blank=True),
    'sujet': ChaineUneLigne(required=False, allow_blank=True),  # en-tête d'email : sans CR/LF
    'corps': ChaineStricte(required=False, allow_blank=True),
    'pdf_mode': ChaineStricte(required=False, allow_blank=True),
    'gamme_envoi': GAMME_ENVOI,
})
EnvoyerEmailResponse = _ser('DevisEnvoyerEmailResponse', {
    'detail': s.CharField(),
    'log_id': s.IntegerField(required=False, allow_null=True),
    'email_statut': s.CharField(),
    'devis_statut': s.CharField(),
    'proposal_path': s.CharField(required=False, allow_null=True),
})
EnvoyerEmailEchec = _ser('DevisEnvoyerEmailEchec', {
    'detail': s.CharField(),
    'log_id': s.IntegerField(required=False, allow_null=True),
    'email_statut': s.CharField(),
    'devis_statut': s.CharField(),
})

#: ENF11 — aucune adresse (ni ``to_email`` ni e-mail du client) : refus d'état.
EnvoyerEmailSansDestinataire = _ser('DevisEnvoyerEmailSansDestinataire', {
    'detail': s.CharField(),
    'log_id': s.IntegerField(required=False, allow_null=True),
    'statut': s.CharField(),
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


@extend_schema_field({'type': 'integer', 'nullable': True,
                      'not': {'type': 'integer'}})
class _DevisNul(s.IntegerField):
    """``devis`` d'une facture NEUVE : toujours nul (VNT89)."""


class FactureCreationSerializer(FactureWriteSerializer):
    """CI #997 (2) — corps PUBLIÉ de ``POST factures/`` : une facture de
    devis ne naît que par « Facturer la vente » (VNT89, 400
    ``facture_de_devis``) — le schéma de création dit donc ``devis`` nul ;
    l'écriture reste ``FactureWriteSerializer`` (schéma seul)."""
    same_company_fields = tuple(
        c for c in FactureWriteSerializer.same_company_fields if c != 'devis')
    devis = _DevisNul(required=False, allow_null=True)


FactureAnnulerRequest = _ser('FactureAnnulerRequest', {
    'acompte': _ser('FactureAnnulerAcompte', {
        # VNT12 — ``garder_en_avance`` (contrat facture_annulation.json).
        'action': s.ChoiceField(
            choices=['transferer', 'rembourser', 'garder_en_avance'],
            required=False),
        'facture_cible': s.IntegerField(required=False),
    }, required=False),
})
#: ENF11 — « transferer » exige ``facture_cible`` (sinon 400 « La facture
#: cible est requise. ») ; les deux autres actions n'en portent pas.
CORPS_ANNULER_CIBLE_SI_TRANSFERT = {EXTENSION_CORPS_RESSERRE: {'properties': {
    'acompte': {'anyOf': [
        {'properties': {'action': {'enum': ['rembourser',
                                            'garder_en_avance']}}},
        {'not': {'required': ['action']}},
        {'required': ['facture_cible'],
         'properties': {'facture_cible': {'type': 'integer',
                                          'minimum': 1}}},
    ]}}}}
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

# ------------------------------------------------------- relevé bancaire
ReleveDryRunRequest = _ser('ReleveImportDryRunRequest', {
    'file': s.FileField(),
})
#: ENF11 — ``token`` requis (le serializer déclaré rend le CORPS requis au
#: schéma : sans lui un client conforme pouvait n'envoyer aucun corps) ; les
#: éléments de ``lignes`` sont resserrés par ``CORPS_RELEVE_LIGNES``.
ReleveCommitRequest = _ser('ReleveImportCommitRequest', {
    'token': ChaineStricte(),
    'lignes': s.ListField(child=s.JSONField(), required=False),
})
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
    # Strictement entre 0 et 100, deux décimales au plus — ENF11 : publié
    # DANS le motif (drf-spectacular n'émet aucune borne pour un
    # décimal-chaîne : « 0 » était conforme puis refusé).
    'variante_pct': s.RegexField(
        r'^0*(?:[1-9]\d?(?:\.\d{0,2})?|\.(?:[1-9]\d?|0[1-9]))$'),
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

#: CI #997 — VALIDÉ par ``generer-pdf`` (``corps_valide``) : drapeaux
#: booléens JSON stricts, textes non blancs (``langue_sortie: ""`` passait).
PdfOptionsRequest = _ser('DevisPdfOptionsRequest', {
    'pdf_mode': s.ChoiceField(choices=['full', 'onepage'], required=False),
    'show_monthly': BooleenStrict(required=False),
    'devis_final': BooleenStrict(required=False),
    'include_etude': BooleenStrict(required=False),
    'include_calepinage': BooleenStrict(required=False, allow_null=True),
    'include_note_calcul': BooleenStrict(required=False),
    'kit_agrege': BooleenStrict(required=False),
    'variante_option': ChaineStricte(required=False),
    # Tri-état du moteur : ``null`` = auto (``clean_pdf_options``).
    'include_annexe_technique': s.JSONField(required=False, allow_null=True),
    'langue_sortie': ChaineStricte(required=False),
})

#: ENF11 — ``MOTIF_MONTANT_POSITIF`` (montant d'encaissement STRICTEMENT
#: positif) vit dans le domaine (``domain/bornes``), partagé avec les
#: sérialiseurs d'entrée ; importé en tête de module.


def corps_resserre(regle):
    """Extension d'opération ``x-corps-resserre`` (``core.openapi_erreurs``) :
    ``regle`` est combinée en ``allOf`` au corps publié de CETTE opération."""
    return {EXTENSION_CORPS_RESSERRE: regle}


#: Numéros de ligne validés, ou `{ligne, facture_reference}` pour une ligne
#: ambiguë résolue (AFAC6).
CORPS_RELEVE_LIGNES = corps_resserre({
    'required': ['token'],
    'properties': {'lignes': {'items': {'oneOf': [
        {'type': 'integer'},
        {'type': 'object', 'required': ['ligne'],
         'properties': {'ligne': {'type': 'integer'},
                        'facture_reference': {'type': 'string'}}},
    ]}}}})


#: Le ``montant`` d'un encaissement est requis et strictement positif.
CORPS_MONTANT_POSITIF = corps_resserre({
    'required': ['montant'],
    'properties': {'montant': {'type': 'string',
                               'pattern': MOTIF_MONTANT_POSITIF}}})

#: AFAC32 — une note de débit porte des ``lignes`` (au moins une) OU un
#: ``montant`` HT strictement positif ; ``{}`` était « conforme » puis refusé
#: « Saisissez les lignes ou le montant de la note de débit. ».
#: CI #1000 — UN SEUL prédicat pour le ``montant`` HT et le ``taux_tva`` saisis :
#: la vue (``_montant_note_debit``) les applique en ``fullmatch`` sur la chaîne
#: BRUTE, ce motif est publié tel quel. ``Decimal(str)`` acceptait en plus
#: ``"1e1"``, ``"1_000"``, des blancs de bord et des chiffres non ASCII, que le
#: schéma déclarait invalides (« accepted schema-violating request »).
#: ``[0-9]`` et non ``\d`` : ``\d`` Python couvre aussi les chiffres Unicode.
MOTIF_MONTANT_NOTE_DEBIT = (r'^0*(?:[1-9][0-9]{0,7}(?:\.[0-9]{0,2})?'
                            r'|\.(?:[1-9][0-9]?|0[1-9]))$')
MOTIF_TAUX_NOTE_DEBIT = (r'^(?:|100(?:\.0{0,2})?'
                         r'|[0-9]{1,2}(?:\.[0-9]{0,2})?'
                         r'|\.[0-9]{1,2})$')
CORPS_NOTE_DEBIT_LIGNES_OU_MONTANT = corps_resserre({'anyOf': [
    {'required': ['lignes'],
     'properties': {'lignes': {'type': 'array', 'minItems': 1}}},
    {'required': ['montant'],
     'properties': {'montant': {'type': 'string',
                                'pattern': MOTIF_MONTANT_NOTE_DEBIT},
                    'taux_tva': {'type': 'string',
                                 'pattern': MOTIF_TAUX_NOTE_DEBIT}}},
]})

EnregistrerAvanceRequest = _ser('PaiementEnregistrerAvanceRequest', {
    'client': s.IntegerField(),
    'montant': s.RegexField(MOTIF_MONTANT_POSITIF),
    'date_paiement': s.DateField(required=False),
    # ENF11 — ce que la vue accepte : un mode de ``Paiement.Mode`` (sinon
    # 400 « Mode de paiement inconnu. »), une référence de 120 caractères.
    'mode': s.ChoiceField(choices=Paiement.Mode.choices, required=False),
    # api-fuzz-full 27/10 (ENF11) — textes STRICTS : motif « sans NUL » publié
    # (un ``\u0000`` dans ``note`` était conforme puis 500 à l'INSERT).
    'reference': ChaineStricte(required=False, allow_blank=True,
                               max_length=120),
    'note': ChaineStricte(required=False, allow_blank=True),
})


# =============================================================== ENF11 — devis
# Corps et réponses RÉELS des actions de ``DevisViewSet`` que le fuzz a prises
# en défaut : sans déclaration, le schéma leur prêtait le sérialiseur du
# viewset (``Devis``) en entrée COMME en sortie.
#: Jeton d'édition optimiste (QJR545), optionnel sur toute écriture.
_JETON = s.CharField(required=False, allow_blank=True, allow_null=True)

ErreurDetail = _ser('DevisErreurDetail', {'detail': s.CharField()})
# CI #997 fuzz (24/10) : un 400 de VALIDATION du corps (``valider_corps``) est
# rendu par champ (``{"nature": [...]}``) et ne porte pas ``detail`` : seuls les
# refus d'état (409) et de garde le portent toujours.
ErreurDevisFige = _ser('DevisErreurFige', {
    'detail': s.CharField(required=False),
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
            # CI #997 fuzz (24/10) — bornes PUBLIÉES et appliquées par
            # ``valider_corps_schema`` : ``1.2e308`` kWc débordait le calcul
            # (500) ; un parc > 100 MWc, un module hors 1-5000 Wc ou plus d'un
            # million de panneaux ne sont pas des devis résidentiels.
            'kwc': {'type': 'number', 'minimum': 0.01, 'maximum': 100000},
            'nb_panneaux': {'type': 'integer', 'minimum': 1,
                            'maximum': 1000000},
            'panel_watt': {'type': 'number', 'minimum': 1, 'maximum': 5000},
            # CI #997 fuzz — les scénarios que la composition sait servir
            # (``creation_auto.SCENARIOS_DEMANDABLES`` ; vide = les deux) :
            # un autre texte était « conforme » puis refusé en 422.
            'scenario': {'type': 'string',
                         'enum': ['', 'sans', 'avec', 'les_deux']},
            'structure_produit_id': {'type': 'integer', 'nullable': True,
                                     'minimum': 1, 'maximum': 2147483647},
            'structure_type': {'type': 'string',
                               'pattern': r'^[^\u0000]*$'},
            'taux_tva': {'type': 'number', 'minimum': 0, 'maximum': 100},
            'mppt_paires': {'type': 'integer', 'minimum': 1, 'maximum': 1000},
            'hors_reseau': {'type': 'boolean'},
            'lead': {'type': 'integer', 'nullable': True, 'minimum': 1,
                     'maximum': 2147483647},
            'dimensionnement_avec': {
                'type': 'object',
                'properties': {
                    'nb_panneaux': {'type': 'number', 'minimum': 0,
                                    'maximum': 1000000},
                    'kwc': {'type': 'number', 'minimum': 0, 'maximum': 100000},
                    'batterie_kwh': {'type': 'number', 'minimum': 0,
                                     'maximum': 1000000},
                },
            },
        },
        'anyOf': [{'required': ['kwc']}, {'required': ['nb_panneaux']}],
    },
}


class _LigneEntree(s.DictField):
    """api-fuzz (24/10/2026, replace-lines / atomic) — une ligne de devis telle
    que ``domain/lignes.remplacer_lignes`` la lit : soit une ligne PRODUIT
    (``produit`` entier ≥ 1 obligatoire ; un id bien formé mais inconnu répond
    404), soit une ligne de SECTION / NOTE (``type_ligne`` + ``designation``
    non blanche). Seules les clés que le serveur VALIDE sont typées ; les
    autres (quantité, prix, remise, ordre…) restent libres (le serveur les lit
    avec tolérance) — ni « rejected schema-compliant » ni « accepted
    schema-violating »."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        produit = {
            'type': 'object', 'required': ['produit'],
            'properties': {
                'produit': {'type': 'integer', 'minimum': 1},
                'type_ligne': {'not': {'enum': ['section', 'note']}},
            },
        }
        section = {
            'type': 'object', 'required': ['type_ligne', 'designation'],
            'properties': {
                'type_ligne': {'type': 'string', 'enum': ['section', 'note']},
                'designation': {'type': 'string', 'minLength': 1,
                                'pattern': r'\S'},
            },
        }
        set_override(self, 'field', {'oneOf': [produit, section]})


#: api-fuzz — « une puissance OU un nombre de panneaux » rend le CORPS
#: obligatoire (drf-spectacular ne pose ``required: true`` que sur un
#: sérialiseur à champ requis, jamais sur un ``request`` en dict) : le fuzz
#: envoyait un corps ABSENT, « conforme », puis refusé en 400.
CORPS_KWC_OU_PANNEAUX = corps_resserre({'anyOf': [
    {'required': ['kwc']}, {'required': ['nb_panneaux']}]})
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
    # Objets {role, marque, libelle_role} (lus ainsi par l'écran :
    # `m.marque`, `m.role`) — jamais des chaînes (fuzz nocturne ENF11).
    'marques_manquantes': s.ListField(child=_ser('DevisMarqueManquante', {
        'role': s.CharField(),
        'marque': s.CharField(),
        'libelle_role': s.CharField(),
    }), required=False),
})
ErreurComposition = _ser('DevisErreurComposition', {
    'detail': s.CharField(),
    'field': s.CharField(required=False, allow_null=True),
})


class NombreStrict(s.FloatField):
    """CI #997 fuzz — nombre JSON RÉEL (``"5"`` et ``true`` étaient lus par
    ``float()``), fini."""

    def to_internal_value(self, data):
        if isinstance(data, bool) or not isinstance(data, (int, float)):
            self.fail('invalid')
        return super().to_internal_value(data)


def _pourcent_souple(**kwargs):
    """Pourcentage 0-100 à 2 décimales, CHAÎNE (l'écran envoie ``"0"``) ou
    NOMBRE JSON arrondi au centième (``DecimalSouple``), publié par LE motif
    de la remise d'en-tête (``conditions_ci.MOTIF_REMISE``, ``-0`` compris) :
    la règle de ``domain/bornes.pourcentage_saisi``, enfin publiée."""
    from ..domain.conditions_ci import MOTIF_REMISE, _decimal_borne
    classe = extend_schema_field(_decimal_borne(
        MOTIF_REMISE, 100, nullable=True))(
        type('PourcentSouple', (DecimalSouple,), {}))
    return classe(max_digits=5, decimal_places=2,
                  min_value=Decimal('0'), max_value=Decimal('100'),
                  required=False, allow_null=True, **kwargs)


#: api-fuzz — plafond publié ET appliqué de la puissance cible d'un devis
#: automatique (10 MWc). Le schéma annonçait tout flottant : ``2.27e16`` kWc
#: composait des quantités qui débordent ``DecimalField(10, 2)`` à l'écriture
#: des lignes (``DataError`` → 500).
TARGET_KWC_MAX = 10_000

AutoDevisRequest = _ser('DevisAutoRequest', {
    # CI #997 fuzz — corps validé tel que publié (la vue le relisait à la
    # main) ; « un lead OU un client » publié (``CORPS_LEAD_OU_CLIENT``).
    'lead': EntierStrict(required=False, allow_null=True, min_value=1),
    'client': EntierStrict(required=False, allow_null=True, min_value=1),
    'target_kwc': NombreStrict(required=False, allow_null=True,
                               max_value=TARGET_KWC_MAX),
    'scenario': ChaineStricte(required=False, allow_blank=True,
                              allow_null=True),
    'etude_params': s.DictField(required=False, allow_null=True),
    'taux_tva': _pourcent_souple(),
    'remise_globale': _pourcent_souple(),
    'structure_produit_id': EntierStrict(required=False, allow_null=True),
    'structure_type': ChaineStricte(required=False, allow_blank=True,
                                    allow_null=True),
})
#: CI #997 fuzz — un devis naît d'un LEAD ou d'un CLIENT (« Un client ou un
#: lead est requis. ») : règle publiée sur ``POST devis/`` et ``devis/auto/``.
CORPS_LEAD_OU_CLIENT = corps_resserre({'anyOf': [
    {'required': ['lead'], 'properties': {'lead': {'type': 'integer'}}},
    {'required': ['client'], 'properties': {'client': {'type': 'integer'}}},
]})
AutoDevisResponse = _ser('DevisAutoResponse', {
    'id': s.IntegerField(),
    'reference': s.CharField(),
    'statut': s.CharField(),
    'kwc': s.FloatField(allow_null=True),
    'nb_lignes': s.IntegerField(),
    'proposal_token': s.CharField(),
    'proposal_path': s.CharField(),
    'alertes': s.ListField(child=s.JSONField()),
    # ALEA51 — le retour pour la bannière de succès (lu du devis créé).
    'total_ttc': s.FloatField(allow_null=True),
    'economie_an_1_ht': s.FloatField(allow_null=True),
    'retour_ans': s.FloatField(allow_null=True),
    'postes_apres_visite': s.ListField(child=s.CharField()),
})

FromLayoutRequest = _ser('DevisFromLayoutRequest', {
    'layout': s.DictField(),
    'lead': s.IntegerField(required=False, allow_null=True),
    'client': s.IntegerField(required=False, allow_null=True),
    # api-fuzz — la règle de ``domain/bornes.pourcentage_saisi`` : chaîne au
    # motif 0-100 à 2 décimales OU nombre 0-100 (arrondi au centième).
    'taux_tva': _pourcent_souple(),
    'remise_globale': _pourcent_souple(),
    'structure_produit_id': s.IntegerField(required=False, allow_null=True),
    'structure_type': s.CharField(required=False, allow_blank=True,
                                  allow_null=True),
    'calepinage': s.IntegerField(required=False, allow_null=True),
})
#: ENF11 fuzz — ``from-layout`` : un layout VIDE (``{}``) n'est pas un layout
#: (« Layout manquant ou invalide. ») et un devis naît d'un lead OU d'un
#: client : les deux règles sont PUBLIÉES sur cette opération seulement.
CORPS_FROM_LAYOUT = corps_resserre({
    'type': 'object',
    # CI #997 fuzz (24/10) : taux de TVA et remise globale en pourcentage
    # 0-100 (``-5.9e103`` répondait 400 « doit être compris entre 0 et 100 »).
    'properties': {
        'layout': {'type': 'object', 'minProperties': 1},
        'taux_tva': {'type': 'number', 'nullable': True, 'minimum': 0,
                     'maximum': 100},
        'remise_globale': {'type': 'number', 'nullable': True, 'minimum': 0,
                           'maximum': 100},
    },
    'anyOf': [
        {'required': ['lead'],
         'properties': {'lead': {'type': 'integer', 'minimum': 1}}},
        {'required': ['client'],
         'properties': {'client': {'type': 'integer', 'minimum': 1}}},
    ],
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
#: Refus d'ÉTAT (409, ENF11 ConflitEtat) : composition/catalogue qui s'oppose,
#: calepinage à chiffrer par « Générer le devis » — jamais un 422.
ErreurFromLayout = _ser('DevisErreurFromLayout', {
    'detail': s.CharField(required=False),
    'errors': s.ListField(child=s.CharField(), required=False),
    'champ': s.CharField(required=False),
})

#: ``roof_layout`` : document de conception 3D (AreaRecord[] + result +
#: renderPlan) — objet libre à clés non préfixées ``_`` (cf.
#: ``resynchronisation._sans_cles_privees``).
#: CI #997 fuzz — un layout VIDE (``{}``) n'est pas un layout (« Layout
#: manquant ») : au moins une clé, publiée.
LayoutRequest = {'application/json': {'type': 'object', 'minProperties': 1,
                                      'additionalProperties': True}}
#: CI #997 fuzz (24/10) : `sections` n'accepte QUE les clés de la liste fermée
#: (toute autre = 400 « clés inconnues ») — un `inline_serializer` ne ferme pas
#: l'objet ; les propriétés sont restatées car `additionalProperties: false`
#: ne regarde que les `properties` de SON sous-schéma `allOf`.
CORPS_SHARE_LINK = corps_resserre({'properties': {'sections': {
    'properties': {cle: {} for cle in _SECTIONS_LIEN},
    'additionalProperties': False}}})
#: CI #997 fuzz (24/10) : un layout est un corps OBLIGATOIRE — un `request` en
#: dict ne rend jamais le corps obligatoire (le fuzz l'omettait : « Layout
#: manquant ou invalide. » = 400 sur un envoi « conforme »). `anyOf` à une
#: branche, au sens de ``minProperties``, le rend obligatoire.
CORPS_LAYOUT_OBLIGATOIRE = corps_resserre({'anyOf': [
    {'type': 'object', 'minProperties': 1}]})
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
#: PV47 — réponse de ``ajouter-boq-electrique`` (``domain/bordereau``) :
#: ``{creees, lignes, manques, deja_presentes}``, clés toujours présentes.
AjouterBoqResponse = _ser('DevisAjouterBoqResponse', {
    'creees': s.IntegerField(),
    'lignes': s.ListField(child=_ser('DevisBoqLigneCreee', {
        'designation': s.CharField(),
        'produit': s.IntegerField(allow_null=True),
        'quantite': s.FloatField(allow_null=True),
        'type_ligne': s.CharField(),
        'a_chiffrer': s.BooleanField(),
    })),
    'manques': s.ListField(child=_ser('DevisBoqManque', {
        'designation': s.CharField(),
        'quantite': s.FloatField(),
        'spec': s.JSONField(),
    })),
    'deja_presentes': s.ListField(child=s.CharField()),
})
RoofImageResponse = _ser('DevisRoofImageResponse', {
    'roof_image': s.CharField(),
    'url': s.CharField(),
})

SimulerRequest = _ser('DevisSimulerRequest', {
    'force_refresh': BooleenStrict(required=False),
})
SimulerResponse = _ser('DevisSimulerResponse', {
    'detail': s.CharField(),
    'job_id': s.CharField(),
    'status': s.CharField(),
    'zones': s.IntegerField(),
    'status_url': s.CharField(),
})

# ------------------------------------------------------------ atomic / lignes


def _proprietes_etude_params(avec_jeton=True):
    """CI #1001 (merge group) — le corps PATCH publie EXACTEMENT les clés que
    ``domain/etude_schema.SCHEMA`` accepte de l'écran : les ENTRÉES non
    exclusives, typées d'après ``type_attendu`` et nullables (``null`` retire la
    clé). Une clé inconnue, dérivée, exclusive ou retirée est donc hors schéma
    (400 attendu) — plus jamais « rejected schema-compliant ».

    api-fuzz — un type ``(int,)`` seul se publie ``integer`` (le serveur refuse
    ``2.5``) ; ``(int, float)`` reste ``number``. ``avec_jeton=False`` : le
    jeton optimiste n'est pas une clé d'étude (il vit en tête du corps de
    ``replace-lines``, jamais DANS ``etude_params``).
    """
    from ..domain import etude_schema as _es
    _json = {str: {'type': 'string'}, int: {'type': 'number'}, float: {'type': 'number'},
             bool: {'type': 'boolean'}, dict: {'type': 'object'}, list: {'type': 'array'}}
    props = {}
    for cle, regle in _es.SCHEMA.items():
        if regle['nature'] != _es.ENTREE or regle['exclusif']:
            continue
        formes = []
        for t in regle['type']:
            f = dict(_json[t])
            if t is int and float not in regle['type']:
                f = {'type': 'integer'}
            if f not in formes:
                formes.append(f)
        forme = formes[0] if len(formes) == 1 else {'anyOf': formes}
        props[cle] = {**forme, 'nullable': True}
    if avec_jeton:
        props['expected_updated_at'] = {'type': 'string', 'nullable': True}
    return props


#: api-fuzz — ``etude_params`` d'un corps de devis (``replace-lines``,
#: ``atomic``) : la MÊME liste de clés que le PATCH ``etude-params``, fermée
#: (``_valider_etude_ecran`` → ``etude_schema.valider`` refuse toute autre clé
#: en 400 : « le schéma est la seule porte »).
EtudeParamsEcran = extend_schema_field({
    'type': 'object', 'nullable': True, 'additionalProperties': False,
    'properties': _proprietes_etude_params(avec_jeton=False)})(
    type('EtudeParamsEcran', (s.DictField,), {}))


class DevisAtomic(DevisWriteSerializer):
    """Corps de ``POST /devis/atomic/`` : les champs d'en-tête du devis (comme
    ``POST /devis/``) + ``lignes`` (au moins une) + ``etude_params`` (écrit
    par l'écrivain unique d'étude, pas par le sérialiseur d'en-tête)."""
    lignes = s.ListField(child=_LigneEntree(), min_length=1)
    etude_params = EtudeParamsEcran(required=False, allow_null=True)

    class Meta(DevisWriteSerializer.Meta):
        fields = list(DevisWriteSerializer.Meta.fields) + ['lignes']


ReplaceLinesRequest = _ser('DevisReplaceLinesRequest', {
    'lignes': s.ListField(child=_LigneEntree(), min_length=1),
    'entete': s.DictField(required=False, allow_null=True),
    'etude_params': EtudeParamsEcran(required=False, allow_null=True),
    'expected_updated_at': _JETON,
})
#: CI #997 fuzz (24/10) : ce que l'écrivain de lignes (``domain/lignes``) exige
#: de CHAQUE ligne — une section / note porte un intitulé, toute autre ligne un
#: produit (« Ligne sans produit valide. » = 400 sur un `DictField` libre).
CORPS_REPLACE_LINES = corps_resserre({'properties': {'lignes': {'items': {
    'type': 'object',
    'anyOf': [
        {'required': ['type_ligne', 'designation'],
         'properties': {
             'type_ligne': {'type': 'string', 'enum': ['section', 'note']},
             'designation': {'type': 'string',
                             'pattern': MOTIF_NON_BLANC_SANS_NUL},
             'groupe_label': {'type': 'string', 'pattern': MOTIF_SANS_NUL}}},
        {'required': ['produit'],
         'properties': {
             'type_ligne': {'type': 'string', 'enum': ['produit']},
             'produit': {'type': 'integer', 'minimum': 1},
             'designation': {'type': 'string', 'pattern': MOTIF_SANS_NUL},
             'groupe_label': {'type': 'string', 'pattern': MOTIF_SANS_NUL},
             'tva_base_legale': {'type': 'string',
                                 'pattern': MOTIF_SANS_NUL}}},
    ]}}}})

# --------------------------------------------------------------- cycle de vie
DeriveResponse = _ser('DevisDeriveResponse', {
    'devis': DevisSerializer(),
    'champs_repris': s.ListField(child=s.CharField()),
    'corrige_apres_envoi': s.BooleanField(),
    'avertissements': s.ListField(child=s.CharField()),
})

AccepterRequest = _ser('DevisAccepterRequest', {
    'nom': ChaineStricte(required=False, allow_blank=True),
    # ENF11 — date d'acceptation AAAA-MM-JJ (``format: date`` publié) ; la vue
    # relisait une chaîne libre puis répondait « Date invalide » en 400.
    'date': DateStricte(required=False),
    # api-fuzz-full 24/10 — la vue n'accepte que vide ou une option du devis : motif
    # (et non une énumération : `OptionAccepteeEnum` porte déjà ces valeurs, un 2e nom
    # pour le même jeu est un avertissement drf-spectacular).
    'option': ChaineStricte(required=False, allow_blank=True, validators=[_RegexValidator(
        '^(?:' + '|'.join(Devis.OptionAcceptee.values) + ')?$')]),
    'entreprise': s.DictField(required=False, allow_null=True),
    'override_credit': BooleenStrict(required=False),
    'override_avertissement': BooleenStrict(required=False),
})
#: ENF11 — « Prix négocié » : le corps tel que la vue l'applique
#: (``utils.corps.valider_corps_schema`` lit CE dict). Un prix TTC non nul OU
#: une remise 0..100 (virgule ou point), exactement un des deux ; le reste
#: (montant rond, au-dessus du prix actuel…) dépend du devis = 409.
MOTIF_PRIX_NEGOCIE = r'^(?![0.,]*$)[0-9]{1,12}(?:[.,][0-9]{0,6})?$'
MOTIF_REMISE_NEGOCIEE = r'^(?:100(?:[.,]0{0,6})?|[0-9]{1,2}(?:[.,][0-9]{0,6})?)$'
PrixNegocieRequest = {
    'application/json': {
        'type': 'object',
        'description': (
            'Indiquez le prix TTC OU la remise en pourcentage (un seul des '
            'deux), en texte décimal.'),
        'properties': {
            'prix_ttc': {'type': 'string', 'pattern': MOTIF_PRIX_NEGOCIE},
            'remise_pct': {'type': 'string',
                           'pattern': MOTIF_REMISE_NEGOCIEE},
            'mode': {'type': 'string', 'enum': ['apercu', 'appliquer']},
            'confirmer_avoir': {'type': 'boolean'},
        },
        'oneOf': [{'required': ['prix_ttc']}, {'required': ['remise_pct']}],
    },
}


def _schema_tranche_put():
    """Une tranche du ``PUT devis/<id>/echeancier/`` : la forme PUBLIÉE de
    ``Devis.echeancier`` (``utils.echeancier.schema_echeancier``, jumelle du
    contrôle ``forme_tranche_ecriture``) acceptée aussi sous la forme du
    contrat ``{cle, libelle, unite, valeur}`` (``valeur`` = ``pct_or_montant``)."""
    import copy
    from ..utils.echeancier import schema_echeancier
    tranche = copy.deepcopy(schema_echeancier()['anyOf'][0]['items'])
    tranche['properties']['valeur'] = copy.deepcopy(
        tranche['properties']['pct_or_montant'])
    tranche['properties']['cle'] = {'type': 'string',
                                    'pattern': MOTIF_SANS_NUL}
    tranche.pop('required', None)
    tranche['anyOf'] = [{'required': ['pct_or_montant']},
                        {'required': ['valeur']}]
    return tranche


#: ENF11 — le plan de tranches est requis et non vide (``minItems: 1``).
EcheancierRequest = {
    'application/json': {
        'type': 'object',
        'required': ['tranches'],
        'properties': {'tranches': {
            'type': 'array', 'minItems': 1, 'items': _schema_tranche_put()}},
    },
}


RefuserRequest = _ser('DevisRefuserRequest', {
    'motif': ChaineStricte(required=False, allow_blank=True),
    'note': ChaineStricte(required=False, allow_blank=True),
    'date': ChaineStricte(required=False, allow_blank=True),
    'marquer_lead_perdu': BooleenStrict(required=False),
})
#: Au moins un caractère non blanc (le serveur ``strip()`` puis refuse le vide), sans
#: NUL (refusé par DRF — api-fuzz-full 24/10, ``marquer-payee``).
_NON_BLANC = MOTIF_NON_BLANC_SANS_NUL
NoterRequest = _ser('DevisNoterRequest', {
    'body': s.RegexField(_NON_BLANC),
})
SavePresetRequest = _ser('DevisSavePresetRequest', {
    'nom': ChaineStricte(max_length=150),
    'description': ChaineStricte(required=False, allow_blank=True),
})

#: Plus grande valeur d'un entier PostgreSQL 32 bits (``ordre``, clés).
ENTIER_32_MAX = 2147483647
#: api-fuzz — MIROIR de ``devis_cycle._LotCreationSerializer`` (qui valide ce
#: corps) : mêmes types stricts, mêmes bornes (nom non blanc de 150 signes,
#: adresse de 255, ``ordre`` et identifiants de ligne dans un entier 32 bits).
LotCreationRequest = _ser('DevisLotCreationRequest', {
    'nom_lot': ChaineStricte(max_length=150),
    'adresse_site': ChaineStricte(max_length=255, required=False,
                                  allow_blank=True, allow_null=True),
    'ordre': EntierStrict(min_value=0, max_value=ENTIER_32_MAX,
                          required=False, allow_null=True),
    'lignes': s.ListField(
        child=EntierStrict(min_value=1, max_value=ENTIER_32_MAX),
        required=False, allow_null=True),
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
        'properties': _proprietes_etude_params(),
        'additionalProperties': False,
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
#: CI #997 fuzz — un paiement DÉJÀ reçu (« Facturer », 0 à 5) publié tel que
#: ``domain/facturation_ops.valider_paiements_saisis`` le lit : montant
#: décimal-chaîne > 0 à 2 décimales au plus (10 chiffres entiers, colonne
#: 12,2), date ``AAAA-MM-JJ``, mode connu, référence de 120 signes au plus.
#: Une date FUTURE est un refus d'état (dépend du jour) : 409.
MOTIF_MONTANT_SAISI = (
    r'^(?:[1-9][0-9]{0,9}(?:\.[0-9]{0,2})?|0?\.(?:0[1-9]|[1-9][0-9]?))$')


def _paiement_deja_recu(nom):
    """Un paiement déjà reçu — instance NEUVE à chaque appel (un sérialiseur
    n'est l'enfant que d'un seul ``ListField``), sous un nom de composant
    propre : « Facturer » complet ET « Facturer la vente » (même lecteur,
    ``valider_paiements_saisis``)."""
    return _ser(nom, {
        'montant': ChaineStricte(trim_whitespace=False, validators=[
            _MotifEntier(MOTIF_MONTANT_SAISI, message='Montant invalide.')]),
        'date_paiement': DateStricte(),
        'mode_paiement': ChoixDocumente(choices=[
            'especes', 'virement', 'cheque', 'carte', 'prelevement',
            'autre']),
        'reference': ChaineStricte(required=False, allow_blank=True,
                                   allow_null=True, max_length=120),
    })


PaiementDejaRecu = _paiement_deja_recu('DevisFacturerCompletPaiementSaisi')
FacturerCompletRequest = _ser('DevisFacturerCompletRequest', {
    'paiements': s.ListField(child=PaiementDejaRecu, required=False,
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
    # ENF11 — énumération PUBLIÉE (= ``facturation_vente.NATURES``, gardée par
    # un test) : une nature hors liste est un refus de forme, pas du service.
    'nature': ChoixDocumente(choices=[
        'acompte', 'intermediaire', 'solde', 'complete']),
    'montant_ttc': ChaineStricte(required=False, allow_null=True,
                                 allow_blank=True),
    'pourcentage': ChaineStricte(required=False, allow_null=True,
                                 allow_blank=True),
    'cle_attendue': ChaineStricte(required=False, allow_null=True,
                                  allow_blank=True),
    'libelle': ChaineStricte(required=False, allow_null=True,
                             allow_blank=True),
    'emettre': BooleenStrict(required=False),
    # api-fuzz-full 27/10 (ENF11) — publié tel que ``valider_paiements_saisis``
    # le lit (un ``{}`` sans ``montant`` était « conforme » puis refusé 400
    # « Paiement n°1 : montant invalide. ») : la forme du paiement de
    # « Facturer » complet, validée ici par le même sérialiseur.
    'paiements': s.ListField(
        child=_paiement_deja_recu('DevisFacturerVentePaiementSaisi'),
        required=False, max_length=5),
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
    'detail': s.CharField(required=False),
    'code': s.CharField(required=False),
})
GenererFactureRequest = _ser('DevisGenererFactureRequest', {
    # CI #997 fuzz — booléens STRICTS (``0`` était lu « faux » et accepté).
    'override_credit': BooleenStrict(required=False),
    'override_avertissement': BooleenStrict(required=False),
})


# ========================================================= ENF11 — facturation
# Bons de commande, factures, paiements, avoirs : corps et réponses RÉELS.
@extend_schema_field({'anyOf': [
    {'type': 'string', 'format': 'decimal', 'pattern': MOTIF_MONTANT_SAISI},
    {'type': 'number', 'minimum': 0.01, 'maximum': 9999999999.99}]})
class _QuantiteLivree(s.DecimalField):
    """CI #997 fuzz (24/10) — quantité livrée STRICTEMENT positive, 2 décimales
    au plus, en chaîne ou en nombre : la règle réellement appliquée par
    ``bon_commande._erreur_lignes_livraison`` (le schéma annonçait tout
    décimal et ``"-36.2"`` répondait 400)."""


LigneLivraison = _ser('BonCommandeLigneLivraison', {
    'ligne_devis': s.IntegerField(min_value=1, max_value=2147483647),
    'quantite': _QuantiteLivree(max_digits=12, decimal_places=2,
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


# CI #997 (5) — réponses d'ACTION : `FactureSerializer.to_representation` retire
# `situation_vente` / `prochaines_echeances` hors du détail (`_vente_pdf` → None) ;
# le schéma publié part donc de la forme LISTE (sans ces deux clés), jamais du détail.
class FactureAbandonnee(FactureListeSerializer):
    """Réponse de ``abandonner-solde`` : la facture + le montant soldé."""
    montant_abandonne = s.FloatField()


class FactureAbandonRepris(FactureListeSerializer):
    """Réponse de ``reprendre-abandon`` : la facture + l'abandon repris."""
    abandon_repris = s.IntegerField()
    montant_repris = s.CharField()


class FactureRelancee(FactureListeSerializer):
    """Réponse de ``relancer`` : la facture + l'e-mail éventuellement parti."""
    email_log_id = s.IntegerField(allow_null=True)


class FactureEmise(FactureListeSerializer):
    """Réponse de ``emettre`` : la facture + les anomalies légales éventuelles."""
    anomalies = s.ListField(child=s.CharField(), required=False)


class FactureCreeeDepuisBc(FactureListeSerializer):
    """Réponse de ``creer-facture`` : la facture + l'avertissement doux."""
    warnings = s.ListField(child=s.CharField(), required=False)


class FactureAnnulee(FactureListeSerializer):
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
    'abandon': s.IntegerField(required=False, allow_null=True, min_value=1,
                              max_value=2 ** 31 - 1),
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
    # CI #997 fuzz (24/10) : une adresse (ou vide = celle du client) — publiée
    # `format: email` ; ``"û"`` était « conforme » puis refusé à l'envoi (400).
    'to_email': s.EmailField(required=False, allow_blank=True),
    'sujet': ChaineUneLigne(required=False, allow_blank=True),  # en-tête d'email : sans CR/LF
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
#: ENF11 — une ligne de facture saisie porte une quantité et un prix ≥ 0
#: (« La quantité ne peut pas être négative. », garde ``domain/bornes``) :
#: publiés sur les écritures de ``factures-lignes`` (le composant de la
#: réponse, partagé, ne change pas).
CORPS_LIGNE_FACTURE_POSITIVE = corps_resserre({'properties': {
    **{champ: {'type': 'string', 'pattern': _MOTIF_POSITIF}
       for champ in ('quantite', 'prix_unitaire')},
    # « La remise doit être comprise entre 0 et 100 %. »
    'remise': {'type': 'string', 'pattern': _MOTIF_POURCENT}}})
_MontantLigne = _decimal_publie(_MOTIF_POSITIF)
_PourcentLigne = _decimal_publie(_MOTIF_POURCENT)

#: ENF11 — règles d'ÉCRITURE d'une ligne de devis
#: (``LigneDevisSerializer.validate`` + garde ``domain/bornes``) publiées sur
#: ``devis-lignes`` : quantité / prix >= 0, remise 0-100, et un taux de TVA à
#: 0 % porte sa base légale (AGR217).
#: ``-0`` / ``-0.00`` valent zéro pour le serveur (``Decimal('-0') == 0``) : le
#: signe est dans le motif, sinon ``"-0"`` était publié « taux non nul » (pas de
#: base légale requise) puis refusé en 400 (api-fuzz, PATCH devis-lignes).
_ZERO_DECIMAL = r'^-?0*(?:\.0*)?$'
_REGLES_LIGNE_DEVIS = {
    'properties': {
        'quantite': {'type': 'string', 'pattern': _MOTIF_POSITIF},
        'prix_unitaire': {'type': 'string', 'pattern': _MOTIF_POSITIF},
        'remise': {'type': 'string', 'pattern': _MOTIF_POURCENT}},
    'anyOf': [
        {'properties': {'taux_tva': {'not': {'pattern': _ZERO_DECIMAL}}}},
        {'required': ['tva_base_legale'],
         'properties': {'tva_base_legale': {'type': 'string',
                                            'pattern': r'\S'}}},
    ],
}
CORPS_LIGNE_DEVIS_MODIF = corps_resserre(_REGLES_LIGNE_DEVIS)
#: Création / PUT : une ligne PRODUIT (type par défaut) référence un produit ;
#: une section ou une note porte un intitulé.
CORPS_LIGNE_DEVIS_ECRITURE = corps_resserre({'allOf': [
    _REGLES_LIGNE_DEVIS,
    {'anyOf': [
        {'required': ['type_ligne', 'designation'],
         'properties': {'type_ligne': {'enum': ['section', 'note']},
                        'designation': {'type': 'string', 'pattern': r'\S'}}},
        {'required': ['produit'],
         'properties': {'type_ligne': {'enum': ['produit']},
                        'produit': {'type': 'integer'}}},
    ]},
]})


def _ligne_corrective(nom):
    """Une ligne saisie d'avoir / de note de débit — instance NEUVE à chaque
    appel (un sérialiseur n'est l'enfant que d'un seul ``ListField``), sous
    un nom de composant propre (deux composants homonymes = avertissement)."""
    return _ser(nom, {
        'produit': EntierStrict(),
        'designation': ChaineStricte(),
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


LigneAvoirCorrective = _ligne_corrective('FactureLigneAvoirCorrective')
CreerAvoirRequest = _ser('FactureCreerAvoirRequest', {
    'mode': s.ChoiceField(choices=['correction', 'contre_passation'],
                          required=False),
    'motif': ChaineStricte(required=False, allow_blank=True),
    'type': s.ChoiceField(
        choices=['correction', 'geste_commercial', 'retour'],
        required=False),
    'lignes': s.ListField(child=LigneAvoirCorrective, required=False,
                          allow_null=True),
})
CreerNoteDebitRequest = _ser('FactureCreerNoteDebitRequest', {
    # CI #1000 — textes STRICTS comme pour l'avoir : ``taux_tva: null`` (ou un
    # nombre) était « hors schéma » et pourtant accepté (201).
    'motif': ChaineStricte(required=False, allow_blank=True),
    # ENF11 — une ligne de note de débit est validée par
    # ``_montants_ligne_corrective`` comme une ligne d'avoir (désignation,
    # produit, bornes) : même forme publiée.
    'lignes': s.ListField(child=_ligne_corrective('FactureLigneNoteDebit'),
                          required=False),
    # AFAC32 — sans ``lignes`` : un montant HT + un taux (défaut : celui de
    # la facture). Publiés pour que la règle « lignes OU montant » le soit.
    'montant': ChaineStricte(required=False),
    'taux_tva': ChaineStricte(required=False, allow_blank=True),
})
LigneRetour = _ser('FactureLigneRetour', {
    # CI #997 fuzz — un id de produit (≥ 1, entier JSON) : ``0`` était
    # conforme puis refusé « produit requis ».
    'produit': EntierStrict(min_value=1),
    # ENF11 — « Ligne 1 : quantité > 0 requise. » : publiée > 0.
    'quantite': _QuantiteLigne(max_digits=12, decimal_places=2,
                               min_value=Decimal('0.01'),
                               max_value=_MONTANT_LIGNE_MAX),
})
RetourClientRequest = _ser('FactureRetourClientRequest', {
    # CI #997 fuzz — texte et booléen STRICTS (``"motif": 0``,
    # ``"restocker": 0`` étaient convertis) ; « non blanc » publié au sens
    # de DRF (``ChaineStricte``), plus le ``\S`` que la regex du schéma lit
    # autrement que ``str.strip``.
    'motif': ChaineStricte(),
    'lignes': s.ListField(child=LigneRetour, min_length=1),
    'restocker': BooleenStrict(required=False),
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
    # CI #997 fuzz — ids entiers JSON (``"5"`` était relu par ``int()``).
    'devis_ids': s.ListField(child=EntierStrict(min_value=1),
                             min_length=2),
})
#: ENF11 — ``[5, 5]`` consolidait deux fois le même devis : ids DISTINCTS.
CORPS_DEVIS_IDS_UNIQUES = corps_resserre({
    'properties': {'devis_ids': {'type': 'array', 'uniqueItems': True}}})
#: CI #997 fuzz — montant encaissé tel que la vue l'ARRONDIT (au centime,
#: moitié vers le haut, ``quantize_mad``) : décimal-chaîne strictement
#: positif APRÈS arrondi (``0.005`` → 0,01 ; ``0.0049`` → 0 refusé), 9
#: chiffres entiers avec décimales libres (le total pré-rempli par l'écran
#: porte du bruit flottant) ou 10 chiffres et 2 décimales au plus (colonne
#: 12,2). Validé par ce MÊME motif, en entier et sans rognage.
MOTIF_MONTANT_ENCAISSE = (
    r'^(?:[1-9][0-9]{0,8}(?:\.[0-9]*)?|[1-9][0-9]{9}(?:\.[0-9]{0,2})?'
    r'|0?\.(?:0[1-9]|[1-9])[0-9]*|0?\.00[5-9][0-9]*)$')


EncaissementGroupeRequest = _ser('FactureEncaissementGroupeRequest', {
    # CI #997 fuzz — la vue lit ce corps VALIDÉ (elle le relisait à la main,
    # plus souplement que publié) : entiers, texte, date et décimaux STRICTS.
    'client': EntierStrict(min_value=1),
    'montant': ChaineStricte(trim_whitespace=False, validators=[_MotifEntier(
        MOTIF_MONTANT_ENCAISSE, message='Montant invalide.')]),
    'factures': s.ListField(child=EntierStrict(min_value=1), min_length=1),
    'mode': s.ChoiceField(
        choices=['especes', 'virement', 'cheque', 'carte', 'prelevement',
                 'autre'], required=False),
    'date': DateStricte(required=False),
    'reference': ChaineStricte(required=False, allow_blank=True,
                               max_length=120),
    # Clé = id d'une facture du lot (sinon 409), part en décimal-chaîne ;
    # une part ≤ 0 est ignorée.
    'repartition': s.DictField(child=DecimalStricte(
        max_digits=12, decimal_places=2), required=False, allow_null=True),
})
BulkRequest = _ser('FactureBulkRequest', {
    'action': s.ChoiceField(
        choices=['emettre', 'envoyer-email', 'generer-pdf', 'relancer']),
    # ENF11 — « La liste `ids` est requise et doit être non vide. »
    'ids': s.ListField(child=s.IntegerField(), min_length=1),
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
# api-fuzz — la facture rendue ici n'a pas de contexte de vue : comme toute
# réponse d'action elle part de la forme LISTE (sans ``situation_vente`` ni
# ``prochaines_echeances``, que seul le détail sert).
PaiementAvecRetenueResponse = _ser('PaiementAvecRetenueResponse', {
    'paiement': PaiementSerializer(),
    'retenue': RetenueSubieSerializer(),
    'facture': FactureListeSerializer(),
})
AttestationRecueRequest = _ser('PaiementAttestationRecueRequest', {
    'attestation_date': s.DateField(required=False),
    'attestation_fichier': s.CharField(required=False, allow_blank=True,
                                       max_length=500),
})
EnvoyerRecuResponse = _ser('PaiementEnvoyerRecuResponse', {
    'statut': s.CharField(),
    'to_email': s.CharField(allow_blank=True, allow_null=True),
    'erreur': s.CharField(allow_blank=True, allow_null=True),
})
# CI #997 (2) — corps VALIDÉS par la vue (``corps_valide``) : texte, date et
# entier STRICTS (``motif: [null]`` → 500, ``date_rejet: ""`` → aujourd'hui).
RejeterPaiementRequest = _ser('PaiementRejeterRequest', {
    'motif': ChaineStricte(),
    # ENF11 nocturne - contrainte SQL frais_rejet >= 0 : un frais negatif
    # levait IntegrityError (500) -> borne basse 0 publiee ET validee.
    'frais': DecimalSouple(max_digits=10, decimal_places=2, required=False,
                           allow_null=True, min_value=Decimal('0')),
    'date_rejet': DateStricte(required=False, allow_null=True),
})
AnnulerSaisieRequest = _ser('PaiementAnnulerSaisieRequest', {
    'motif': ChaineStricte(),
})
ReaffecterRequest = _ser('PaiementReaffecterRequest', {
    'facture_cible': EntierStrict(min_value=1),
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
#: CI #997 fuzz — ``offres-tailles/appliquer`` : SEULE « Recommandé »
#: s'applique au devis (Éco et Max étaient « conformes » puis TOUJOURS
#: refusées) ; jeton en texte STRICT (``0`` était relu « 0 »). Validé par la
#: vue avant toute autre garde.
OffreTailleAppliquerRequest = _ser('DevisOffreTailleAppliquerRequest', {
    'cle': ChoixDocumente(choices=['recommande'], error_messages={
        'invalid_choice': 'Seule la taille « Recommandé » s\'applique au '
                          'devis : « {input} » est une taille d\'exploration, '
                          'montrée au client à côté de l\'offre officielle.'}),
    'expected_updated_at': ChaineStricte(required=False, allow_blank=True,
                                         allow_null=True),
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
                    # CI #997 fuzz (24/10) : les rôles de composition connus,
                    # rien d'autre (« Rôle de composition inconnu. » = 400
                    # sur une clé pourtant conforme à un `additionalProperties`
                    # libre) ; le produit est une clé primaire (>= 1).
                    'equipements': {
                        'type': 'object',
                        'additionalProperties': False,
                        'properties': {
                            role: {'type': 'integer', 'minimum': 1}
                            for role in ROLES_AUTO_COMPOSITION},
                    },
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
