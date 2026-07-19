"""NTSEC20 — Séparation des tâches (SoD) : violations, alertes, blocage.

Un utilisateur viole une règle SoD s'il CUMULE (via son rôle) les deux
permissions déclarées incompatibles. Ce module fournit :
  * ``sod_violations(company)`` — sélecteur read-only des cumuls interdits ;
  * ``would_cumulate_critical(user, role)`` — le rôle candidat créerait-il un
    cumul CRITIQUE (utilisé par ``roles.services`` pour bloquer) ;
  * ``raise_sod_alerts(company)`` — journalise une ``SECURITY_ALERT`` par
    violation (best-effort) ;
  * ``STANDARD_SOD_RULES`` + ``seed_standard_sod_rules(company)`` — jeu finance/
    achats standard, idempotent.
Tout est scopé société ; aucune app métier n'est importée.
"""
from __future__ import annotations

# Jeu standard finance/ventes. WIR11 — les codes doivent EXISTER dans le
# catalogue `roles.ALL_PERMISSIONS` (codes UNDERSCORE) : les anciens codes
# POINTÉS (`facture.saisir`…) n'y figuraient pas, si bien que `sod_violations`
# et `would_cumulate_critical` ne matchaient JAMAIS (SoD silencieusement no-op).
# Chaque paire est une incompatibilité RÉELLE de séparation des tâches sur des
# codes déclarés (compta_saisir/valider/cloturer = COMPTA40 ; ventes_creer/
# valider = flux devis/ventes).
STANDARD_SOD_RULES = [
    # Comptabilité (COMPTA40) — le saisisseur d'une écriture ne doit ni la
    # valider (second regard) ni clôturer sa période. Le cumul saisie+validation
    # est CRITIQUE : il bloque l'attribution du rôle qui le créerait.
    ('compta_saisir', 'compta_valider', 'critique',
     "Saisie et validation d'écritures comptables"),
    ('compta_saisir', 'compta_cloturer', 'warning',
     'Saisie et clôture comptable'),
    ('compta_valider', 'compta_cloturer', 'warning',
     'Validation et clôture comptable'),
    # Ventes — le créateur d'un devis/commande ne doit pas le valider lui-même.
    ('ventes_creer', 'ventes_valider', 'warning',
     'Création et validation de devis/ventes'),
]


def _user_permissions(user):
    """Ensemble des permissions portées par le rôle de ``user`` (ou vide)."""
    role = getattr(user, 'role', None)
    if role is None:
        return set()
    return set(role.permissions or [])


def _permissions_after(user, role):
    """Permissions de ``user`` SI ``role`` lui était attribué (remplacement)."""
    return set((role.permissions or []) if role is not None else [])


def sod_violations(company):
    """Liste des cumuls SoD interdits dans la société.

    Renvoie une liste de dicts ``{user_id, username, permission_a,
    permission_b, severite, libelle}``. Company-scopé : ne regarde que les
    comptes et règles de ``company``."""
    if company is None:
        return []
    from authentication.models import CustomUser

    from .models import SodRule

    rules = list(SodRule.objects.filter(company=company))
    if not rules:
        return []
    violations = []
    users = CustomUser.objects.filter(
        company=company, is_active=True).select_related('role')
    for user in users:
        perms = _user_permissions(user)
        if not perms:
            continue
        for rule in rules:
            if rule.permission_a in perms and rule.permission_b in perms:
                violations.append({
                    'user_id': user.pk,
                    'username': user.username,
                    'permission_a': rule.permission_a,
                    'permission_b': rule.permission_b,
                    'severite': rule.severite,
                    'libelle': rule.libelle,
                })
    return violations


def would_cumulate_critical(user, role):
    """Vrai si attribuer ``role`` à ``user`` créerait un cumul SoD CRITIQUE.

    Le modèle ``CustomUser`` ne porte qu'UN rôle : l'attribution REMPLACE les
    permissions, donc on évalue les permissions du rôle candidat seul. Best-
    effort, FAIL-OPEN : toute erreur → ``False`` (ne bloque jamais par accident).
    """
    try:
        if user is None or role is None:
            return False
        from .models import SodRule
        perms = _permissions_after(user, role)
        if not perms:
            return False
        crit = SodRule.objects.filter(
            company_id=getattr(user, 'company_id', None),
            severite=SodRule.Severite.CRITIQUE)
        for rule in crit:
            if rule.permission_a in perms and rule.permission_b in perms:
                return True
        return False
    except Exception:
        return False


def raise_sod_alerts(company):
    """Journalise une ``SECURITY_ALERT`` par violation (best-effort).

    Renvoie le nombre d'alertes émises."""
    violations = sod_violations(company)
    n = 0
    for v in violations:
        try:
            from apps.audit.recorder import record
            from apps.audit.models import AuditLog
            record(AuditLog.Action.SECURITY_ALERT, user=None, company=company,
                   detail=('SoD (%s) : %s cumule %s + %s' % (
                       v['severite'], v['username'],
                       v['permission_a'], v['permission_b'])))
            n += 1
        except Exception:
            pass
    return n


def seed_standard_sod_rules(company):
    """Sème le jeu SoD standard finance/achats (idempotent, additif)."""
    from .models import SodRule
    created = 0
    for perm_a, perm_b, severite, libelle in STANDARD_SOD_RULES:
        _, was_created = SodRule.objects.get_or_create(
            company=company, permission_a=perm_a, permission_b=perm_b,
            defaults={'severite': severite, 'libelle': libelle})
        if was_created:
            created += 1
    return created
