"""FG24 — export/import de la CONFIGURATION entre sociétés.

Distinct d'``ExportSauvegarde`` (données métier) : on n'exporte QUE de la
configuration reproductible — profil (réglages, jamais les secrets/clés/logo),
rôles personnalisés, modèles de message, règles d'automatisation (sans état
d'exécution), surcharges de statut, textes de documents. JAMAIS de données
métier (clients, devis, stock…), JAMAIS de secrets (RIB, providers OCR, etc.).

Import ADDITIF, admin uniquement, company-scopé (la cible est TOUJOURS la
société de l'appelant, jamais lue du corps). Deux modes :

* ``merge`` (défaut) — crée ce qui manque, NE touche PAS l'existant ;
* ``overwrite`` — crée le manquant ET met à jour l'existant (par clé naturelle).

Les types d'intervention / étapes de checklist (app ``installations``) sont
HORS périmètre de cet outil : ils ont leur propre amorçage et ne sont pas
touchés ici (on ne franchit pas la frontière d'une autre app pour les écrire).
"""
from django.db import transaction
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from authentication.permissions import IsAdminOrResponsableTier, IsAdminRole

from .models import CompanyProfile, MessageTemplate, SettingsAuditLog
from .models_documents import DEVIS_TEXT_KEYS, DocumentTemplates
from .models_email import EmailTemplate
from .models_statuses import StatutConfig

# Champs de profil EXPORTABLES — réglages métier reproductibles uniquement.
# Volontairement SANS : identité légale (ice/rc/cnss…), coordonnées, secrets
# (rib/banque/providers), clés d'objets (logo/signature), responsables par
# défaut (FK propres à la société source).
PROFILE_CONFIG_FIELDS = [
    'couleur_principale', 'payment_terms', 'quote_validity_days',
    'agricole_pump_hours',
    # AGR208 — repères énergie agricole datés et sourcés (ex-« bonbonne »).
    'reperes_energie_agricole',
    # AGR107 — réglages pompage société (nullable, sans défaut).
    'agricole_part_debit_forage_pct', 'agricole_marge_cable_descente_m',
    'agricole_salissure_supp_pct',
    # Q5 — délais commerciaux (texte libre court ; vide ⇒ délai non affiché).
    'delai_visite_technique', 'delai_installation',
    'doc_prefixes', 'doc_numbering',
    'tva_standard', 'tva_panneaux', 'onee_tarif_kwh', 'productible_kwh_kwc',
    'rendement_global', 'prix_cible_kwc_defaut',
    'remise_max_pct', 'discount_approval_threshold',
    # CIQ614 — SURCHARGES 82-21 de la société (NULL = seuil sourcé des
    # textes, exposé à part en lecture par ``seuils_sources``).
    'seuil_regime_declaration_kwc', 'seuil_regime_anre_kwc',
    # AGR606 — écart de recette pompage toléré (%), sans défaut.
    'recette_pompage_ecart_max_pct',
    # CIQ622 — réglages C&I de recette / suivi / garantie, sans défaut.
    'recette_ecart_pmax_pct', 'recette_echantillon_iv_pct',
    'recette_pr_seuil_interne', 'delai_intervention_suivi_heures',
    'delai_reception_definitive_mois',
    'securite_obligatoire_avant_demarrage',
    'garantie_production_autorisee', 'garantie_production_validation',
    'devise_defaut', 'lead_sla_hours', 'overage_seuil_pct',
    # MRY8 — fenêtres d'appel de la société (forme `fenetres_appel` du
    # contrat MRY25) : elles decident QUAND une touche de cadence tombe
    # et servent de base au KPI premier contact en minutes OUVRÉES.
    'message_heure_debut', 'appel_heure_debut', 'appel_heure_fin',
    'vendredi_pause_debut', 'vendredi_pause_fin',
    'ramadan_debut', 'ramadan_fin',
    'ramadan_appel_debut', 'ramadan_appel_fin',
    'premier_contact_objectif_min',
    # FG22 — politique de sécurité (réglages, pas de secret).
    'password_min_length', 'password_require_complexity',
    'lockout_max_attempts', 'lockout_duration_minutes', 'password_expiry_days',
]


def champs_textes_documents():
    """APAR30 — textes de documents exportés, DÉRIVÉS de la source
    (``DEVIS_TEXT_KEYS`` + ``cgv_par_mode``) : la liste tenue à la main
    oubliait ``bpa_mention``, ``acceptance_stamp`` et ``cgv_par_mode``."""
    return list(DEVIS_TEXT_KEYS) + ['cgv_par_mode']


#: Champs exportés d'un modèle de message (APAR30 — EN/AR compris).
MESSAGE_FIELDS = ('corps_fr', 'corps_darija', 'corps_en', 'corps_ar')
#: Champs exportés d'un modèle d'e-mail (APAR30).
EMAIL_FIELDS = ('sujet', 'corps', 'sujet_en', 'corps_en', 'sujet_ar',
                'corps_ar')

#: APAR30 — v2 ajoute ``email_templates``, les textes EN/AR des messages et
#: les textes de documents dérivés. Un bundle v1 reste lisible (clés absentes
#: ignorées).
CONFIG_VERSION = 2


def _serialize_profile(profile):
    if profile is None:
        return {}
    return {f: _jsonable(getattr(profile, f, None))
            for f in PROFILE_CONFIG_FIELDS}


def _serialize_document_templates(company):
    row = DocumentTemplates.objects.filter(company=company).first()
    if row is None:
        return {}
    return {f: _jsonable(getattr(row, f, None))
            for f in champs_textes_documents()}


def _jsonable(value):
    import datetime
    from decimal import Decimal
    if isinstance(value, Decimal):
        return str(value)
    # MRY8 — les fenêtres d'appel introduisent des TimeField/DateField dans le
    # paquet de configuration : on les sérialise en ISO (« 08:30:00 »), forme
    # que Django re-coerce telle quelle à la ré-import. Sans cela, la valeur
    # dépendrait du rendu JSON de l'appelant.
    if isinstance(value, (datetime.time, datetime.date, datetime.datetime)):
        return value.isoformat()
    return value


def _serialize_roles(company):
    from apps.roles.models import Role
    out = []
    for r in Role.objects.filter(company=company):
        out.append({
            'nom': r.nom,
            'permissions': list(r.permissions or []),
            'est_systeme': r.est_systeme,
        })
    return out


def _serialize_message_templates(company):
    return [
        dict({'cle': m.cle}, **{f: getattr(m, f, '') for f in MESSAGE_FIELDS})
        for m in MessageTemplate.objects.filter(company=company)
    ]


def _serialize_email_templates(company):
    return [
        dict({'cle': e.cle}, **{f: getattr(e, f, '') for f in EMAIL_FIELDS})
        for e in EmailTemplate.objects.filter(company=company)
    ]


def _serialize_automation_rules(company):
    from apps.automation.models import AutomationRule
    out = []
    for r in AutomationRule.objects.filter(company=company):
        out.append({
            'nom': r.nom,
            'enabled': r.enabled,
            'trigger_type': r.trigger_type,
            'trigger_config': r.trigger_config,
            'action_type': r.action_type,
            'action_config': r.action_config,
            'requires_approval': r.requires_approval,
            'approval_threshold': _jsonable(r.approval_threshold),
            'ordre': r.ordre,
        })
    return out


def _serialize_statuts(company):
    return [
        {'domaine': s.domaine, 'cle': s.cle, 'libelle': s.libelle,
         'ordre': s.ordre, 'actif': s.actif}
        for s in StatutConfig.objects.filter(company=company)
    ]


@api_view(['GET'])
@permission_classes([IsAdminOrResponsableTier])
def config_export(request):
    """Exporte la configuration de la société de l'appelant (JSON)."""
    company = request.user.company if request.user.company_id else None
    if company is None:
        return Response({'detail': 'Aucune société.'}, status=400)
    profile = CompanyProfile.objects.filter(company=company).first()
    bundle = {
        'version': CONFIG_VERSION,
        'profile': _serialize_profile(profile),
        'document_templates': _serialize_document_templates(company),
        'roles': _serialize_roles(company),
        'message_templates': _serialize_message_templates(company),
        'email_templates': _serialize_email_templates(company),
        'automation_rules': _serialize_automation_rules(company),
        'statuts': _serialize_statuts(company),
    }
    return Response(bundle)


def _log_config_import_change(company, user, field, field_label, old, new):
    """AUD808 — une ligne SettingsAuditLog par valeur réellement modifiée par
    ``config_import`` (section dédiée pour la distinguer des PATCH manuels du
    profil, qui restent en section 'profil'). Ignore les non-changements,
    comme ``_audit_profile_changes``."""
    if old == new:
        return
    SettingsAuditLog.log_change(
        company=company, user=user, section='config_import',
        field=field, field_label=field_label, old=old, new=new)


class ImportInvalide(Exception):
    """APAR29 — le bundle porte une valeur refusée par l'écran : l'import
    entier est annulé (tout-ou-rien) et l'appelant reçoit 400 nommant chaque
    champ."""

    def __init__(self, erreurs):
        super().__init__('Import de configuration invalide.')
        self.erreurs = erreurs


def _prefixer(prefixe, erreurs):
    return {f'{prefixe}.{champ}': msg for champ, msg in erreurs.items()}


def _import_profile(company, data, overwrite, user=None, request=None):
    from .serializers_company import CompanyProfileSerializer
    from .views_profile import _PROFILE_AUDIT_FIELDS
    # Politique simple : merge n'écrase JAMAIS un profil existant déjà créé ;
    # overwrite applique. Comme un profil existe toujours (get_or_create),
    # on n'applique le profil qu'en mode overwrite.
    if not overwrite:
        return 0
    profile = CompanyProfile.get(company)
    valeurs = {f: data[f] for f in PROFILE_CONFIG_FIELDS if f in data}
    if not valeurs:
        return 0
    # APAR29 — les MÊMES validations que ``PATCH /parametres/update/`` : une
    # TVA négative ou une remise à 900 % n'entre plus par l'import.
    ser = CompanyProfileSerializer(
        profile, data=valeurs, partial=True, context={'request': request})
    if not ser.is_valid():
        raise ImportInvalide(_prefixer('profile', ser.errors))
    changed = []
    for f, new in ser.validated_data.items():
        old = getattr(profile, f, None)
        _log_config_import_change(
            company, user, f, _PROFILE_AUDIT_FIELDS.get(f, f), old, new)
        setattr(profile, f, new)
        changed.append(f)
    if changed:
        profile.save()
    return len(changed)


def _import_document_templates(company, data, overwrite, user=None):
    from django.db.models import F

    from .serializers_documents import DocumentTemplatesSerializer
    if not data or not overwrite:
        return 0
    row, _ = DocumentTemplates.objects.get_or_create(company=company)
    valeurs = {f: data[f] for f in champs_textes_documents() if f in data}
    if not valeurs:
        return 0
    # APAR30 — mêmes validations que l'écran (``cgv_bullets`` liste,
    # ``cgv_par_mode`` forme fermée).
    ser = DocumentTemplatesSerializer(row, data=valeurs, partial=True)
    if not ser.is_valid():
        raise ImportInvalide(_prefixer('document_templates', ser.errors))
    changed = []
    for f, new in ser.validated_data.items():
        old = getattr(row, f, None)
        if old == new:
            continue
        _log_config_import_change(
            company, user, f'document_template.{f}',
            f'Modèle de document — {f}', old, new)
        setattr(row, f, new)
        changed.append(f)
    if changed:
        row.save(update_fields=changed)
        # APAR30 — nouvelle révision des textes, comme l'écran (N67).
        DocumentTemplates.objects.filter(pk=row.pk).update(
            version=F('version') + 1)
    return len(changed)


def _import_roles(company, rows, overwrite, user=None):
    from apps.roles.models import Role
    created = updated = 0
    for r in rows or []:
        nom = (r.get('nom') or '').strip()
        if not nom:
            continue
        # On ne réécrit JAMAIS les rôles système (perms canoniques gérées par
        # init_roles) — on n'importe que des rôles personnalisés.
        if r.get('est_systeme'):
            continue
        existing = Role.objects.filter(company=company, nom=nom).first()
        if existing is None:
            Role.objects.create(
                company=company, nom=nom,
                permissions=list(r.get('permissions') or []),
                est_systeme=False)
            _log_config_import_change(  # APAR29 — créations journalisées
                company, user, f'role.{nom}', f'Rôle « {nom} » — créé',
                None, list(r.get('permissions') or []))
            created += 1
        elif overwrite and not existing.est_systeme:
            new_permissions = list(r.get('permissions') or [])
            _log_config_import_change(
                company, user, f'role.{nom}.permissions',
                f'Rôle « {nom} » — permissions',
                list(existing.permissions or []), new_permissions)
            existing.permissions = new_permissions
            existing.save(update_fields=['permissions'])
            updated += 1
    return created, updated


def _import_message_templates(company, rows, overwrite, user=None):
    from .views_messages import _unknown_placeholders, placeholders_autorises
    valid = {c.value for c in MessageTemplate.Cle}
    created = updated = 0
    for i, r in enumerate(rows or []):
        cle = r.get('cle')
        if cle not in valid:
            continue
        # APAR30 — même liste blanche que l'écran Messages (APAR12).
        for champ in MESSAGE_FIELDS:
            inconnus = _unknown_placeholders(r.get(champ) or '', cle)
            if inconnus:
                raise ImportInvalide({
                    f'message_templates[{i}].{champ}': [
                        f'Placeholder non supporté : {", ".join(inconnus)}. '
                        f'Placeholders autorisés : '
                        f'{" ".join(placeholders_autorises(cle)) or "aucun"}.']})
        existing = MessageTemplate.objects.filter(
            company=company, cle=cle).first()
        if existing is None:
            MessageTemplate.objects.create(
                company=company, cle=cle,
                **{f: r.get(f, '') or '' for f in MESSAGE_FIELDS})
            _log_config_import_change(  # APAR29 — créations journalisées
                company, user, f'message_template.{cle}',
                f'Modèle de message « {cle} » — créé', None,
                r.get('corps_fr', '') or '')
            created += 1
        elif overwrite:
            new_fr = r.get('corps_fr', '') or ''
            new_darija = r.get('corps_darija', '') or ''
            _log_config_import_change(
                company, user, f'message_template.{cle}.corps_fr',
                f'Modèle de message « {cle} » — corps FR',
                existing.corps_fr, new_fr)
            _log_config_import_change(
                company, user, f'message_template.{cle}.corps_darija',
                f'Modèle de message « {cle} » — corps Darija',
                existing.corps_darija, new_darija)
            existing.corps_fr = new_fr
            existing.corps_darija = new_darija
            for f in ('corps_en', 'corps_ar'):  # APAR30 — EN/AR aussi
                if f in r:
                    nouveau = r.get(f) or ''
                    _log_config_import_change(
                        company, user, f'message_template.{cle}.{f}',
                        f'Modèle de message « {cle} » — {f}',
                        getattr(existing, f, ''), nouveau)
                    setattr(existing, f, nouveau)
            existing.save(update_fields=list(MESSAGE_FIELDS))
            updated += 1
    return created, updated


def _import_email_templates(company, rows, overwrite, user=None):
    """APAR30 — modèles d'e-mail (absents de l'export jusqu'ici), validés
    comme l'écran : liste blanche de placeholders ET rendu (APAR13)."""
    from .models_email import erreur_de_rendu
    from .serializers_email import (
        EMAIL_TEMPLATE_PLACEHOLDERS, _unknown_placeholders,
    )
    valid = {c.value for c in EmailTemplate.Cle}
    created = updated = 0
    for i, r in enumerate(rows or []):
        cle = r.get('cle')
        if cle not in valid:
            continue
        for champ in EMAIL_FIELDS:
            texte = r.get(champ) or ''
            erreur = erreur_de_rendu(texte)
            inconnus = _unknown_placeholders(texte, cle)
            if erreur or inconnus:
                autorises = ' '.join(
                    EMAIL_TEMPLATE_PLACEHOLDERS.get(cle, [])) or 'aucun'
                raise ImportInvalide({f'email_templates[{i}].{champ}': [
                    erreur or (f'Placeholder non supporté : '
                               f'{", ".join(inconnus)}. Placeholders '
                               f'autorisés : {autorises}.')]})
        valeurs = {f: r.get(f, '') or '' for f in EMAIL_FIELDS if f in r}
        existing = EmailTemplate.objects.filter(
            company=company, cle=cle).first()
        if existing is None:
            EmailTemplate.objects.create(company=company, cle=cle, **valeurs)
            _log_config_import_change(
                company, user, f'email_template.{cle}',
                f"Modèle d'e-mail « {cle} » — créé", None,
                valeurs.get('sujet', ''))
            created += 1
        elif overwrite:
            for f, v in valeurs.items():
                _log_config_import_change(
                    company, user, f'email_template.{cle}.{f}',
                    f"Modèle d'e-mail « {cle} » — {f}",
                    getattr(existing, f, ''), v)
                setattr(existing, f, v)
            existing.save()
            updated += 1
    return created, updated


def _import_automation_rules(company, rows, overwrite, user=None):
    from apps.automation.models import AutomationRule, ActionType, TriggerType
    valid_trig = {c.value for c in TriggerType}
    valid_act = {c.value for c in ActionType}
    created = updated = 0
    for r in rows or []:
        nom = (r.get('nom') or '').strip()
        trig = r.get('trigger_type')
        act = r.get('action_type')
        if not nom or trig not in valid_trig or act not in valid_act:
            continue
        existing = AutomationRule.objects.filter(
            company=company, nom=nom).first()
        payload = dict(
            enabled=bool(r.get('enabled', True)),
            trigger_type=trig,
            trigger_config=r.get('trigger_config') or {},
            action_type=act,
            action_config=r.get('action_config') or {},
            requires_approval=bool(r.get('requires_approval', False)),
            approval_threshold=r.get('approval_threshold'),
            ordre=r.get('ordre') or 0,
        )
        if existing is None:
            AutomationRule.objects.create(company=company, nom=nom, **payload)
            _log_config_import_change(  # APAR29 — créations journalisées
                company, user, f'automation_rule.{nom}',
                f'Règle « {nom} » — créée', None, f'{trig} → {act}')
            created += 1
        elif overwrite:
            for k, v in payload.items():
                _log_config_import_change(
                    company, user, f'automation_rule.{nom}.{k}',
                    f'Règle « {nom} » — {k}', getattr(existing, k, None), v)
                setattr(existing, k, v)
            existing.save()
            updated += 1
    return created, updated


def _import_statuts(company, rows, overwrite, user=None):
    from .serializers_statuses import StatutConfigSerializer
    from .statuses_defaults import VALID_DOMAINES, default_keys
    created = updated = 0
    for i, r in enumerate(rows or []):
        domaine = r.get('domaine')
        cle = r.get('cle')
        if domaine not in VALID_DOMAINES or cle not in default_keys(domaine):
            continue
        existing = StatutConfig.objects.filter(
            company=company, domaine=domaine, cle=cle).first()
        if existing is not None and not overwrite:
            continue
        # APAR29 — mêmes validations que l'écran (libellé ≤ 120…) ; une
        # ligne refusée annule TOUT l'import.
        ser = StatutConfigSerializer(data={
            'domaine': domaine, 'cle': cle,
            'libelle': r.get('libelle', '') or '',
            'ordre': r.get('ordre') or 0,
            'actif': bool(r.get('actif', True))})
        if not ser.is_valid():
            raise ImportInvalide(_prefixer(f'statuts[{i}]', ser.errors))
        if existing is None:
            StatutConfig.objects.create(
                company=company, domaine=domaine, cle=cle,
                libelle=ser.validated_data.get('libelle', ''),
                ordre=ser.validated_data.get('ordre', 0),
                actif=ser.validated_data.get('actif', True))
            _log_config_import_change(  # APAR29 — créations journalisées
                company, user, f'statut.{domaine}.{cle}',
                f'Statut « {domaine}/{cle} » — créé', None,
                ser.validated_data.get('libelle', ''))
            created += 1
        else:
            new_vals = {
                'libelle': ser.validated_data.get('libelle', ''),
                'ordre': ser.validated_data.get('ordre', 0),
                'actif': ser.validated_data.get('actif', True),
            }
            for k, v in new_vals.items():
                _log_config_import_change(
                    company, user, f'statut.{domaine}.{cle}.{k}',
                    f'Statut « {domaine}/{cle} » — {k}',
                    getattr(existing, k, None), v)
                setattr(existing, k, v)
            existing.save(update_fields=['libelle', 'ordre', 'actif'])
            updated += 1
    return created, updated


@api_view(['POST'])
@permission_classes([IsAdminRole])
def config_import(request):
    """Importe une configuration dans la société de l'appelant (additif).

    Corps : le bundle exporté. ``?mode=merge`` (défaut) ou ``?mode=overwrite``.
    La société cible est TOUJOURS celle de l'appelant (jamais lue du corps)."""
    company = request.user.company if request.user.company_id else None
    if company is None:
        return Response({'detail': 'Aucune société.'}, status=400)
    data = request.data if isinstance(request.data, dict) else {}
    overwrite = request.query_params.get('mode') == 'overwrite'

    user = request.user
    # APAR29 — TOUT-OU-RIEN : une valeur refusée annule l'import entier
    # (transaction), et la réponse nomme chaque champ fautif.
    try:
        with transaction.atomic():
            roles_c, roles_u = _import_roles(
                company, data.get('roles'), overwrite, user=user)
            msg_c, msg_u = _import_message_templates(
                company, data.get('message_templates'), overwrite, user=user)
            mail_c, mail_u = _import_email_templates(
                company, data.get('email_templates'), overwrite, user=user)
            rule_c, rule_u = _import_automation_rules(
                company, data.get('automation_rules'), overwrite, user=user)
            stat_c, stat_u = _import_statuts(
                company, data.get('statuts'), overwrite, user=user)
            profile_changed = _import_profile(
                company, data.get('profile') or {}, overwrite, user=user,
                request=request)
            doc_changed = _import_document_templates(
                company, data.get('document_templates') or {}, overwrite,
                user=user)
    except ImportInvalide as exc:
        return Response(exc.erreurs, status=400)

    return Response({
        'mode': 'overwrite' if overwrite else 'merge',
        'roles': {'created': roles_c, 'updated': roles_u},
        'message_templates': {'created': msg_c, 'updated': msg_u},
        'email_templates': {'created': mail_c, 'updated': mail_u},
        'automation_rules': {'created': rule_c, 'updated': rule_u},
        'statuts': {'created': stat_c, 'updated': stat_u},
        'profile_fields_changed': profile_changed,
        'document_template_fields_changed': doc_changed,
    })
