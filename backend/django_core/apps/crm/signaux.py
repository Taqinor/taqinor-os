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

#: Marqueur « ce lead ne porte PAS l'annotation » — distinct d'une annotation
#: présente qui vaut ``None`` (le fait existe, il est simplement vide).
_ABSENT = object()


def _annotation(lead, nom):
    """Valeur d'une annotation de :func:`annotations_signaux`, ou ``_ABSENT``.

    Un lead servi par ``LeadViewSet`` porte ces attributs (posés en SQL avec
    la ligne elle-même) ; un lead construit ailleurs (service, import, test)
    ne les porte pas et chaque fait est alors relu par sa propre requête —
    comportement d'avant, inchangé.
    """
    return getattr(lead, nom, _ABSENT)


def _engagement_proposition(lead):
    """L'engagement du client sur sa proposition, via ``ventes.selectors``."""
    vide = {'ouverte': False, 'vues': 0, 'lue_en_detail': False,
            'derniere_vue': None}
    vues = _annotation(lead, 'sig_vues_proposition')
    if vues is not _ABSENT:
        premiere = getattr(lead, 'sig_premiere_vue_proposition', None)
        profond = getattr(lead, 'sig_lecture_profonde_at', None)
        vues = int(vues or 0)
        instants = [i for i in (premiere, profond) if i is not None]
        return {
            'ouverte': premiere is not None or vues > 0,
            'vues': vues,
            'lue_en_detail': profond is not None,
            'derniere_vue': max(instants) if instants else None,
        }
    try:
        from apps.ventes.selectors import engagement_proposition_du_lead
        return engagement_proposition_du_lead(
            getattr(lead, 'pk', None), getattr(lead, 'company', None))
    except Exception:  # noqa: BLE001 — un score ne fait jamais tomber un lead
        return vide


def _questionnaire_repondu_le(lead):
    """Instant de la dernière réponse au questionnaire, ou ``None``."""
    depuis_annotation = _annotation(lead, 'sig_questionnaire_repondu_le')
    if depuis_annotation is not _ABSENT:
        return depuis_annotation
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
    depuis_annotation = _annotation(
        lead,
        'sig_derniere_activite_jointe' if issues else 'sig_derniere_activite')
    if depuis_annotation is not _ABSENT:
        return depuis_annotation
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


# ── CAD-K ── CAD133 (budget de requêtes) ────────────────────────────────────
def annotations_signaux():
    """Les cinq faits de ce module, posés en ANNOTATIONS sur un queryset.

    LE BUG QUE CECI CORRIGE. Les signaux ci-dessus sont lus PAR LEAD par
    ``scoring`` (fraîcheur + comportement), lui-même appelé par
    ``LeadSerializer`` pour chaque ligne : la liste des leads exécutait 16
    requêtes PAR LIGNE (415 requêtes pour 25 leads au lieu d'un budget fixe),
    et la fiche 16 de plus. Rien de ce que ces signaux LISENT n'a changé —
    seulement le nombre d'allers-retours : les agrégats deviennent des
    sous-requêtes corrélées, calculées avec la ligne du lead.

    Les faits ``ShareLink`` viennent de ``apps.ventes.selectors`` (frontière
    M3 : jamais ``ventes.models`` depuis ``apps.crm``). Un lead qui ne porte
    pas ces attributs retombe sur la lecture requête-par-requête d'avant.
    """
    from django.db.models import DateTimeField, Max, OuterRef, Q, Subquery

    from .models import LeadActivity, QuestionnaireLien

    activites = (LeadActivity.objects
                 .filter(lead=OuterRef('pk'))
                 .order_by()
                 .values('lead'))
    questionnaires = (QuestionnaireLien.objects
                      .filter(lead=OuterRef('pk'))
                      .order_by()
                      .values('lead'))
    annotations = {
        'sig_derniere_activite': Subquery(
            activites.annotate(
                valeur=Max('created_at')).values('valeur')[:1],
            output_field=DateTimeField()),
        'sig_derniere_activite_jointe': Subquery(
            activites.annotate(
                valeur=Max('created_at',
                           filter=Q(outcome__in=ISSUES_JOINT))
            ).values('valeur')[:1],
            output_field=DateTimeField()),
        'sig_questionnaire_repondu_le': Subquery(
            questionnaires.annotate(
                valeur=Max('derniere_reponse_at')).values('valeur')[:1],
            output_field=DateTimeField()),
    }
    try:
        from apps.ventes.selectors import annotations_engagement_proposition
        annotations.update(annotations_engagement_proposition())
    except Exception:  # noqa: BLE001 — un score ne fait jamais tomber une liste
        pass
    return annotations
