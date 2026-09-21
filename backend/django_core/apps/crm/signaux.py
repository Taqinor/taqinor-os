"""CAD-K — CAD133 : ce que le client FAIT, à côté de ce qu'il a DIT.

Audit L3 du 21/09/2026, section CAD-K. ``compute_score`` additionne des
DÉCLARATIONS de capture (champs remplis, facture, canal, type d'installation,
ancienneté, questionnaire) et aucun COMPORTEMENT ; pire, la composante
fraîcheur comptait l'âge du LEAD, si bien qu'un prospect qui répond
aujourd'hui après quatre mois de silence recevait 1 point sur 12, comme un
dossier mort.

Ce module rassemble les signaux de comportement **déjà en base** — rien n'est
capté en plus, rien n'est inventé :

  * proposition OUVERTE, ROUVERTE, LUE EN DÉTAIL — lus par le point d'entrée
    cross-app ``apps.ventes.selectors.engagement_proposition_du_lead``
    (jamais ``ventes.models`` : frontière M3) ;
  * QUESTIONNAIRE répondu (``QuestionnaireLien.derniere_reponse_at``) ;
  * RAPPEL demandé (``Lead.contact_preference_set_at``) ;
  * une issue « joint » ou « intéressé » dans le chatter (même définition que
    ``kpi_cadences`` et CAD131 — deux KPI qui compteraient « joint »
    autrement seraient impossibles à confronter).

Il sert à DEUX choses dans ``scoring`` : la composante comportement, et la
FRAÎCHEUR, qui repart désormais de la DERNIÈRE interaction plutôt que de la
date de création.

Lecture seule, sans effet de bord, et tolérante : un signal illisible vaut
« absent », jamais une exception — un badge de score ne fait pas tomber une
fiche lead.
"""

#: Les issues qui valent « on a eu le client au bout du fil ». Reprises à
#: l'identique de ``mesure_cadence.ISSUES_JOINT``.
ISSUES_JOINT = ('joint', 'interesse')


def _engagement_proposition(lead):
    """L'engagement du client sur sa proposition, via ``ventes.selectors``."""
    vide = {'ouverte': False, 'vues': 0, 'lue_en_detail': False,
            'derniere_vue': None}
    try:
        from apps.ventes.selectors import engagement_proposition_du_lead
        return engagement_proposition_du_lead(
            getattr(lead, 'pk', None), getattr(lead, 'company', None))
    except Exception:  # noqa: BLE001 — un score ne fait jamais tomber un lead
        return vide


def _questionnaire_repondu_le(lead):
    """Instant de la dernière réponse au questionnaire, ou ``None``."""
    try:
        from django.db.models import Max

        from .models import QuestionnaireLien
        return (QuestionnaireLien.objects
                .filter(lead=lead)
                .aggregate(dernier=Max('derniere_reponse_at'))
                .get('dernier'))
    except Exception:  # noqa: BLE001
        return None


def _derniere_activite_le(lead, *, issues=None):
    """Instant de la dernière ligne de chatter, éventuellement filtrée."""
    try:
        from django.db.models import Max

        from .models import LeadActivity
        qs = LeadActivity.objects.filter(lead=lead)
        if issues is not None:
            qs = qs.filter(outcome__in=issues)
        return qs.aggregate(dernier=Max('created_at')).get('dernier')
    except Exception:  # noqa: BLE001
        return None


def signaux_comportement(lead):
    """Les signaux de comportement d'un lead, tous déjà en base.

    Renvoie ``{proposition_ouverte, proposition_rouverte, lue_en_detail,
    questionnaire_repondu, rappel_demande, client_joint}`` — des booléens,
    jamais des scores : la pondération vit dans ``scoring``, à un seul
    endroit.
    """
    if lead is None or getattr(lead, 'pk', None) is None:
        return {
            'proposition_ouverte': False, 'proposition_rouverte': False,
            'lue_en_detail': False, 'questionnaire_repondu': False,
            'rappel_demande': False, 'client_joint': False,
        }
    engagement = _engagement_proposition(lead)
    return {
        'proposition_ouverte': bool(engagement.get('ouverte')),
        # « Rouverte » = revenue DESSUS, pas juste ouverte une fois.
        'proposition_rouverte': int(engagement.get('vues') or 0) >= 2,
        'lue_en_detail': bool(engagement.get('lue_en_detail')),
        'questionnaire_repondu': _questionnaire_repondu_le(lead) is not None,
        'rappel_demande': getattr(
            lead, 'contact_preference_set_at', None) is not None,
        'client_joint': _derniere_activite_le(
            lead, issues=ISSUES_JOINT) is not None,
    }


def derniere_interaction(lead):
    """Le plus récent signe de vie du dossier, ou ``None``.

    C'est la base de la FRAÎCHEUR depuis CAD133 : un prospect qui répond
    aujourd'hui après quatre mois de silence n'est pas un dossier mort, et
    compter l'âge du LEAD le rangeait pourtant avec eux. On prend le plus
    récent de : dernière ligne de chatter, dernière consultation de la
    proposition, dernière réponse au questionnaire, pose de la préférence de
    contact. Aucun de ces instants n'existe ⇒ ``None``, et l'appelant retombe
    sur la date de création — c'est la vérité, pas un repli inventé.
    """
    if lead is None or getattr(lead, 'pk', None) is None:
        return None
    instants = [
        _derniere_activite_le(lead),
        _engagement_proposition(lead).get('derniere_vue'),
        _questionnaire_repondu_le(lead),
        getattr(lead, 'contact_preference_set_at', None),
    ]
    instants = [i for i in instants if i is not None]
    return max(instants) if instants else None
