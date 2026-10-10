"""Attribution des leads (round-robin, responsable par défaut) (SPL6, extrait de crm/services.py : déplacement pur).

Module de type (a) de la scission : il n'importe ni ``.services`` ni un
module racine ; ``services`` réexporte ce qu'il faut (façade).
"""
from . import stages
from .models import Lead


def _leads_ouverts_count(commercial):
    """XSAL11 — Nombre de leads OUVERTS assignés à un commercial : stage NON
    SIGNED/COLD (clés STAGES.py — jamais codées en dur) et jamais perdu. Sert
    de plafond de saturation pour la rotation round-robin équilibrée."""
    return Lead.objects.filter(
        owner=commercial, perdu=False,
    ).exclude(stage__in=[stages.SIGNED, stages.COLD]).count()


def _next_balanced_round_robin_commercial(company, plafond):
    """XSAL11 — Round-robin ÉQUILIBRÉ : parmi les commerciaux actifs de la
    société (rôle « Commercial » — pas de territoire câblé dans ce dépôt,
    voir FG236), affecte au prochain dans la rotation (moins de leads
    OUVERTS d'abord, départage par id) EN SAUTANT quiconque a atteint/dépassé
    ``plafond`` leads ouverts. Renvoie None si TOUS les commerciaux actifs
    sont saturés (l'appelant retombe alors sur ``responsable_defaut_leads``)
    ou s'il n'y a aucun commercial actif du tout."""
    from django.contrib.auth import get_user_model

    User = get_user_model()
    candidats = list(
        User.objects.filter(
            company=company, is_active=True, role__nom='Commercial',
        ).order_by('id')
    )
    if not candidats:
        return None
    eligibles = [
        c for c in candidats if _leads_ouverts_count(c) < plafond
    ]
    if not eligibles:
        return None  # tous saturés — fallback à l'appelant
    eligibles.sort(key=lambda c: (_leads_ouverts_count(c), c.id))
    return eligibles[0]


def default_responsable_for(company, lead_attrs=None):
    """Responsable assigné par défaut aux nouveaux leads d'une société.

    NTCRM1 — le moteur de territoires (module ``territoires``) qui consultait
    ``lead_attrs`` (dict brut : ville/type_installation/montant_estime/canal)
    EN PREMIER a été retiré (SOLMVP10, app sortie) : le comportement round-
    robin XSAL11 ci-dessous — déjà le repli historique — est désormais le
    SEUL chemin, ``lead_attrs`` n'étant plus consulté.

    XSAL11 — quand ``CompanyProfile.round_robin_leads_actif`` est ON, la
    rotation ÉQUILIBRÉE (en sautant les commerciaux saturés — plafond
    ``round_robin_plafond_leads_ouverts``) est tentée EN PREMIER ; si tous
    sont saturés, replie sur le responsable par défaut explicite. OFF
    (défaut) = comportement byte-identique à avant XSAL11 : le profil
    entreprise (Paramètres → « Responsable par défaut ») prime, et QW6 replie
    sur un round-robin simple (par charge totale) si ce réglage est vide.
    None si aucune société ou aucun commercial actif (comportement inchangé
    dans ce cas — un lead sans owner reste possible).
    """
    if company is None:
        return None
    from apps.parametres.models import CompanyProfile
    profile = CompanyProfile.objects.filter(company=company).first()
    explicit = profile.responsable_defaut_leads if profile else None

    # CIQ416 (D-CIQ-20) — un lead COMMERCIAL ou INDUSTRIEL va au responsable
    # des leads pro quand il est désigné (et actif), AVANT le round-robin et
    # le défaut. Réglage vide, ou autre segment : comportement identique à
    # l'octet. Le routage n'est pas un rythme (CAD52/CAD124 tiennent).
    responsable_pro = responsable_leads_pro(profile, lead_attrs)
    if responsable_pro is not None:
        return responsable_pro

    if profile is not None and profile.round_robin_leads_actif:
        balanced = _next_balanced_round_robin_commercial(
            company, profile.round_robin_plafond_leads_ouverts)
        if balanced is not None:
            return balanced
        # Tous saturés (ou aucun commercial actif) — fallback explicite.
        return explicit

    if explicit is not None:
        return explicit
    return pick_round_robin_owner(company)


def _type_des_attrs(lead_attrs):
    if not lead_attrs:
        return None
    if isinstance(lead_attrs, dict):
        return lead_attrs.get('type_installation')
    return getattr(lead_attrs, 'type_installation', None)


def responsable_leads_pro(profile, lead_attrs=None):
    """CIQ416 — le responsable des leads pro (``CompanyProfile.
    responsable_leads_pro``, CIQ415) quand ``lead_attrs`` désigne un lead
    commercial ou industriel et que ce responsable est actif ; sinon None."""
    if profile is None or _type_des_attrs(lead_attrs) not in (
            Lead.TypeInstallation.COMMERCIAL,
            Lead.TypeInstallation.INDUSTRIEL):
        return None
    responsable = getattr(profile, 'responsable_leads_pro', None)
    if responsable is None or not getattr(responsable, 'is_active', True):
        return None
    return responsable


def pick_round_robin_owner(company):
    """QW6 — Choisit un propriétaire par ROUND-ROBIN parmi les utilisateurs
    commerciaux actifs de la société (permission ``crm_creer``), pour qu'un
    lead ne reste JAMAIS sans responsable quand aucun « responsable par
    défaut » n'est configuré. Sans état dédié à maintenir : le tour revient à
    l'utilisateur ayant le MOINS de leads assignés (ties départagés par id,
    ordre stable) — équivalent d'une rotation, sans compteur externe. None si
    la société n'a aucun utilisateur commercial actif."""
    from django.contrib.auth import get_user_model
    from django.db.models import Count, Q

    User = get_user_model()
    candidates = list(
        User.objects.filter(
            company=company, is_active=True,
        ).filter(
            Q(role__permissions__contains=['crm_creer'])
            | Q(role__isnull=True, role_legacy__in=['admin', 'responsable']),
        ).annotate(
            nb_leads=Count('leads_assignes'),
        ).order_by('nb_leads', 'pk').distinct()
    )
    return candidates[0] if candidates else None
