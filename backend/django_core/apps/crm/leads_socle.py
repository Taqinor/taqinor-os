"""Noms partagés sans dépendance des leads : destinataires de notification,
prédicats de visite, garde « cadence active », motif de refus (SPL311, extrait de crm/services.py : déplacement pur).

Module de type (a) de la scission : il n'importe ni ``.services`` ni un
module racine ; ``services`` réexporte ce qu'il faut (façade).
"""
from .models import RelanceEtape


def _company_fallback_managers(company):
    """QJ27 — Managers de repli d'une société : utilisateurs actifs portant le
    rôle fin « Commercial responsable » ou « Directeur ».

    Sert quand un lead n'a pas de responsable, ou quand le responsable n'a pas
    de supérieur direct (``supervisor``). Liste éventuellement vide — jamais
    d'exception. La société est toujours résolue côté serveur."""
    if company is None:
        return []
    try:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        return list(User.objects.filter(
            company=company, is_active=True,
            role__nom__in=('Commercial responsable', 'Directeur'),
        ).order_by('id'))
    except Exception:  # noqa: BLE001 — best-effort
        return []


def user_and_superior_recipients(user, company):
    """QJ27 — Destinataires « handler + supérieur » pour une notification.

    Renvoie une liste dédupliquée (ordre préservé) :
      - le handler (``user``) s'il est renseigné ;
      - son ``supervisor`` direct s'il existe, SINON les managers de repli de
        la société (« Commercial responsable » / « Directeur ») ;
      - handler absent → uniquement les managers de repli.

    Peut renvoyer une liste vide (aucun destinataire résolvable)."""
    recipients = []
    if user is not None:
        recipients.append(user)
        superior = getattr(user, 'supervisor', None)
        if superior is not None and getattr(superior, 'is_active', True):
            recipients.append(superior)
        else:
            recipients.extend(_company_fallback_managers(company))
    else:
        recipients.extend(_company_fallback_managers(company))
    seen, out = set(), []
    for u in recipients:
        pk = getattr(u, 'pk', None)
        if pk is not None and pk not in seen:
            seen.add(pk)
            out.append(u)
    return out


def lead_notification_recipients(lead):
    """QJ27 — Destinataires des notifications d'un lead : owner + supérieur
    (repli managers société quand l'un des deux manque)."""
    return user_and_superior_recipients(
        getattr(lead, 'owner', None), getattr(lead, 'company', None))


def visite_pro_avant_devis(lead):
    """CIQ411 — ``devis_auto.visite_avant_devis(lead)`` (CIQ404) : le bloc
    {requise, motifs} d'un lead commercial/industriel, ``None`` ailleurs."""
    from .devis_auto import visite_avant_devis
    if lead is None:
        return None
    bloc = visite_avant_devis(lead)
    return bloc if bloc and bloc.get('requise') else None


def visite_point_eau_requise(lead):
    """AGR408 — ``visite_point_eau_avant_devis(lead).requise`` (AGR403) :
    vrai seulement pour un lead AGRICOLE au point d'eau inconnu."""
    from .devis_auto import visite_point_eau_avant_devis
    if lead is None:
        return False
    bloc = visite_point_eau_avant_devis(lead)
    return bool(bloc and bloc['requise'])


# ── CAD-D ── CAD49 — la relance en masse ne double plus le moteur ────────────
#
#: CAD49 — la raison NOMMÉE d'un refus de « définir/effacer la relance » en
#: masse. Le chemin de la FICHE passe par le moteur
#: (``reporter_prochaine_touche``) ; l'action en masse, elle, écrivait
#: directement ``Lead.relance_date`` sans rien lui dire : la fiche affichait
#: une date, la frise une autre, et au premier geste de cadence le serveur
#: réécrivait la date depuis la touche. C'était le « second système de rappel
#: concurrent » que tout le reste du code s'interdit.
#:
#: Pourquoi REFUSER plutôt que passer N plans par ``reporter_prochaine_touche``
#: en masse : décaler des centaines de plans d'un clic — avec leurs touches
#: suivantes et leurs ancres — est plus dangereux que le mal soigné.
MOTIF_BULK_CADENCE_ACTIVE = (
    'cadence de relance active — la date vient de la prochaine touche du '
    'plan ; ouvrez la fiche et utilisez « Reporter » sur cette touche'
)


def leads_avec_cadence_active(company, lead_ids):
    """CAD49 — le sous-ensemble de ``lead_ids`` portant AU MOINS une touche de
    relance encore À FAIRE. Renvoie un ``set`` d'identifiants.

    EN LOT, comme ``leads_avec_devis_accepte`` : une action en masse porte sur
    des centaines de dossiers, une requête par lead serait un N+1 assumé. Le
    filtre société est POSÉ ICI.
    """
    ids = list(lead_ids or [])
    if not ids:
        return set()
    return set(RelanceEtape.objects.filter(
        company=company, lead_id__in=ids,
        statut=RelanceEtape.Statut.A_FAIRE,
    ).values_list('lead_id', flat=True))


def motif_refus_valide(company, nom):
    """Le libellé EXACT du motif de perte ``nom`` de ``company`` (actif,
    comparaison sans casse), ou ``None`` s'il n'existe pas. Filtre société
    posé ICI."""
    from .models import MotifPerte

    nom = (nom or '').strip()
    if not nom or company is None:
        return None
    return (MotifPerte.objects
            .filter(company=company, archived=False, nom__iexact=nom)
            .values_list('nom', flat=True).first())
