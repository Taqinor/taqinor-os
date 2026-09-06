"""Vues du profil entreprise (lecture + mise à jour, avec audit N55).

Domaine « Société & identité / Devis & logique métier ». Extrait de l'ancien
``views.py`` sans aucun changement d'endpoint, de permission ni de
comportement."""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from authentication.permissions import IsAdminOrResponsableTier, IsAnyRole
from .models import CompanyProfile, SettingsAuditLog
from .serializers import CompanyProfileSerializer
from .views_common import _audit_company, _profile


# AUD807 — libellés FR pour les champs de profil audités. Cette table n'est
# PLUS la source de vérité de « qui est audité » (voir
# `_build_profile_audit_fields` plus bas, dérivé par introspection du
# modèle) : elle fournit seulement de jolis libellés pour les champs déjà
# habillés ; un champ non listé ici reçoit un libellé par défaut.
_PROFILE_FIELD_LABELS = {
    'nom': 'Nom',
    'adresse': 'Adresse',
    'email': 'Email',
    'telephone': 'Téléphone',
    'siret': 'SIRET',
    'tva_intra': 'TVA intra',
    'ice': 'ICE',
    'identifiant_fiscal': 'Identifiant fiscal',
    'rc': 'Registre de commerce',
    'patente': 'Patente',
    'cnss': 'CNSS',
    'rib': 'RIB',
    'banque': 'Banque',
    'instructions_paiement': 'Instructions de paiement',
    'conditions_generales': 'Conditions générales',
    'couleur_principale': 'Couleur principale',
    'responsable_defaut_leads': 'Responsable par défaut des leads',
    'default_installer': 'Installateur par défaut',
    'payment_terms': 'Échéancier de paiement',
    'quote_validity_days': 'Validité du devis (jours)',
    'agricole_pump_hours': 'Heures de pompage par défaut',
    'agricole_prix_bonbonne': 'Prix bonbonne butane 12 kg (agricole)',
    'agricole_cout_reel_bonbonne': 'Coût réel bonbonne butane 12 kg (agricole)',
    'delai_visite_technique': 'Délai de visite technique (indicatif)',
    'delai_installation': "Délai d'installation (indicatif)",
    'doc_prefixes': 'Préfixes de numérotation',
    'doc_numbering': 'Numérotation (largeur / réinitialisation)',
    'tva_standard': 'TVA standard',
    'tva_panneaux': 'TVA panneaux',
    'onee_tarif_kwh': 'Tarif ONEE (kWh)',
    'productible_kwh_kwc': 'Productible (kWh/kWc)',
    'discount_approval_threshold': "Seuil d'approbation de remise",
    'rendement_global': 'Rendement global',
    'prix_cible_kwc_defaut': 'Prix cible /kWc par défaut',
    'remise_max_pct': 'Limite de remise (%)',
    'commission_mode': 'Commission — mode',
    'commission_valeur': 'Commission — valeur',
    'referral_enabled': 'Parrainage activé',
    'referral_reward': 'Parrainage — récompense par défaut',
    # WR12 — flags exposés en Paramètres (FG28 SLA + N105 export DGI).
    'lead_sla_hours': 'SLA premier contact (heures)',
    # MRY8 — fenêtres d'appel (libellés FR de l'écran Paramètres).
    'appel_heure_debut': 'Début des appels',
    'appel_heure_fin': 'Fin des appels',
    'vendredi_pause_debut': 'Vendredi — début de pause',
    'vendredi_pause_fin': 'Vendredi — fin de pause',
    'ramadan_debut': 'Ramadan — début',
    'ramadan_fin': 'Ramadan — fin',
    'ramadan_appel_debut': 'Ramadan — début des appels',
    'ramadan_appel_fin': 'Ramadan — fin des appels',
    'premier_contact_objectif_min':
        'Objectif premier contact (minutes ouvrées)',
    'dgi_export_actif': 'Export DGI activé',
    # QG9 — pourcentage configurable des variantes de devis.
    'variante_pct': 'Pourcentage des variantes de devis',
    # Module d'exécution terrain (F9–F20) — interfaces swappables + seuil F12.
    'ocr_serie_provider': 'Fournisseur OCR n° de série (F9)',
    'transcription_provider': 'Fournisseur de transcription (F14)',
    'photo_qa_provider': 'Fournisseur QA photo IA (F20)',
    'overage_seuil_pct': 'Seuil de dépassement consommation (%) (F12)',
    # XFAC24 — immutabilité de la facture émise (opt-in, correction par avoir).
    'factures_immuables': 'Factures immuables après émission',
}


def _build_profile_audit_fields():
    """Dérive par introspection les champs de profil suivis par l'audit N55.

    AUD807 — l'ancienne liste tenue à la main ne couvrait que 47/102 champs
    réels de `CompanyProfile` ; les 55 muets incluaient TOUTE la politique de
    sécurité (`password_min_length`, `lockout_max_attempts`…) et
    `audit_retention_days` (le levier de purge du journal lui-même). Un champ
    est audité PAR DÉFAUT dès qu'il est concret sur le modèle, sauf s'il est
    déjà en lecture seule côté serializer (`company`/`plan`/`nb_sieges_max`/…
    — non modifiables par ce endpoint) ou le `id` technique. Aucun opt-out
    manuel additionnel aujourd'hui : tout champ concret restant DOIT être
    audité."""
    read_only = set(CompanyProfileSerializer.Meta.read_only_fields)
    excluded = read_only | {'id'}
    fields = {}
    for f in CompanyProfile._meta.concrete_fields:
        if f.name in excluded:
            continue
        label = _PROFILE_FIELD_LABELS.get(f.name)
        if not label:
            label = str(f.verbose_name).capitalize()
        fields[f.name] = label
    return fields


# Champs du profil entreprise suivis par l'audit (N55) : libellé FR par champ.
# Calculé une fois à l'import — dérivé du modèle, jamais une liste manuelle.
_PROFILE_AUDIT_FIELDS = _build_profile_audit_fields()


def _audit_profile_changes(request, profile, before):
    """Écrit une ligne SettingsAuditLog par champ de profil modifié.

    `before` est un dict {field: valeur} capturé AVANT save ; on compare aux
    valeurs APRÈS save et on journalise chaque écart (ancien→nouveau)."""
    company = _audit_company(request)
    for field, label in _PROFILE_AUDIT_FIELDS.items():
        old = before.get(field)
        new = getattr(profile, field, None)
        if old == new:
            continue
        SettingsAuditLog.log_change(
            company=company, user=request.user, section='profil',
            field=field, field_label=label, old=old, new=new,
        )


@api_view(['GET'])
@permission_classes([IsAnyRole])
def get_profile(request):
    profile = _profile(request)
    return Response(CompanyProfileSerializer(profile).data)


@api_view(['PUT', 'PATCH'])
@permission_classes([IsAdminOrResponsableTier])
def update_profile(request):
    profile = _profile(request)
    partial = request.method == 'PATCH'
    # Capture l'état AVANT save pour l'audit (N55).
    before = {f: getattr(profile, f, None) for f in _PROFILE_AUDIT_FIELDS}
    serializer = CompanyProfileSerializer(
        profile, data=request.data, partial=partial,
        context={'request': request},
    )
    serializer.is_valid(raise_exception=True)
    updated = serializer.save()
    _audit_profile_changes(request, updated, before)
    # SCA46 — consentement au benchmarking anonymisé : le champ vit sur
    # ``authentication.Company`` (donnée du tenant). Posé côté serveur sur la
    # société de l'APPELANT uniquement (jamais un id de société du corps),
    # audité comme les autres champs. Absent du corps = inchangé.
    if 'benchmarking_opt_in' in request.data:
        company = getattr(request.user, 'company', None)
        if company is not None:
            nouveau = bool(request.data.get('benchmarking_opt_in'))
            ancien = bool(company.benchmarking_opt_in)
            if nouveau != ancien:
                company.benchmarking_opt_in = nouveau
                company.save(update_fields=['benchmarking_opt_in'])
                SettingsAuditLog.log_change(
                    company=company, user=request.user, section='profil',
                    field='benchmarking_opt_in',
                    field_label='Consentement benchmarking anonymisé',
                    old=ancien, new=nouveau,
                )
    return Response(CompanyProfileSerializer(updated).data)
