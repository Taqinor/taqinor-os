"""CAD74 — le réveil SAISONNIER (`reveil_b`, « la saison des factures d'été »).

Constat de l'audit L3 du 21/09/2026 : le texte `reveil_b` et sa clé existent
(`apps/parametres/models_messages.py`) mais la clé n'est dans AUCUN gabarit —
le grep du dépôt ne trouve aucun câblage, et après le réveil J60 plus rien ne
repart. Ce module est ce câblage, et il vit à part de `apps/crm/services.py`
pour rester lisible et ne pas élargir un fichier déjà partagé par 44 tâches.

**Ce n'est pas un barreau de la cadence de réveil.** Le protocole garde ses
DEUX réveils (J30 appel, J60 WhatsApp) : ni leur nombre, ni leur ordre, ni
leur J+N ne changent. `reveil_b` est une touche CALENDAIRE, posée une seule
fois, dans la fenêtre de la saison, aux dormants que la mécanique J30/J60 a
laissés hors de cette fenêtre.

Provenance de la saison (obligatoire — aucun chiffre sans source) : nouveau
record national de consommation à 8,4 GW le 06/07/2026 pendant une vague de
chaleur, à citer « ONEE, via presse économique, juillet 2026 » (Le360 du
28/07/2026, Consonews, FNH) — JAMAIS « communiqué ONEE » ni « MAP » : aucune
source primaire n'a pu être ouverte, et la page officielle du ministère
affiche encore 7 310 MW au 11/08/2023. C'est le moment où la facture ONEE
choque le foyer.

Garde-fou de coût (texte de la tâche) : UNE touche par an et par dormant,
plafonnée, jamais une vague trimestrielle — chaque réveil promet une vue 3D à
produire À LA MAIN, donc un coût de production par réponse positive. La
rentrée scolaire n'est PAS une fenêtre de réveil (CAD76).
"""
import logging

logger = logging.getLogger(__name__)

#: Clé du texte validé, déjà présent au catalogue des messages.
REVEIL_SAISON_CLE = 'reveil_b'

#: Libellé de la touche, tel qu'il s'affichera dans la frise du lead.
REVEIL_SAISON_LIBELLE = 'Réveil saisonnier — saison des factures'

#: Mois de la fenêtre (bornes INCLUSES), juin → septembre : la saison de
#: consommation décrite dans l'en-tête de ce module. Ces deux nombres sont des
#: MOIS, pas un seuil métier inventé — ils viennent du texte de la tâche.
REVEIL_SAISON_MOIS_DEBUT = 6
REVEIL_SAISON_MOIS_FIN = 9

#: Rang de la touche saisonnière dans la frise du lead. Les deux barreaux du
#: gabarit de réveil portent 1 et 2 ; la touche calendaire vient après, sans
#: jamais en renuméroter aucun.
REVEIL_SAISON_ORDRE = 3


def dans_la_fenetre_saison(jour):
    """La date est-elle dans la fenêtre saisonnière (juin → septembre) ?"""
    if jour is None:
        return False
    return REVEIL_SAISON_MOIS_DEBUT <= jour.month <= REVEIL_SAISON_MOIS_FIN


def _maintenant_local(maintenant=None):
    from django.utils import timezone

    from . import horaires

    instant = maintenant or timezone.now()
    if timezone.is_naive(instant):
        instant = timezone.make_aware(instant, horaires.CASABLANCA)
    return instant.astimezone(horaires.CASABLANCA)


def motif_de_refus(lead, *, maintenant=None):
    """Pourquoi ce lead ne reçoit PAS le réveil saisonnier — ou ``None``.

    Renvoyer le MOTIF plutôt qu'un booléen : l'écran qui proposera un jour ce
    geste doit pouvoir dire au commercial POURQUOI le bouton ne fait rien,
    exactement comme une erreur nomme son champ (règle fondateur 08/09).
    """
    from . import stages
    from .models import RelanceEtape

    local = _maintenant_local(maintenant)
    if not dans_la_fenetre_saison(local.date()):
        return ('Hors saison : le réveil saisonnier ne se pose qu’entre juin '
                'et septembre.')
    if getattr(lead, 'is_archived', False):
        return 'Le lead est archivé.'
    if getattr(lead, 'perdu', False):
        return 'Le lead est perdu — le réveil ne s’applique pas.'
    if lead.stage != stages.COLD:
        return ('Le lead n’est pas au Froid : le réveil saisonnier ne '
                's’adresse qu’aux dormants.')

    touches = RelanceEtape.objects.filter(company=lead.company, lead=lead)
    # Plafond : UNE par an et par dormant.
    if touches.filter(template_cle=REVEIL_SAISON_CLE,
                      due_date__year=local.year).exists():
        return ('Ce dormant a déjà reçu son réveil saisonnier cette année '
                '(une seule par an).')
    # Ne jamais empiler une touche sur une touche encore ouverte : le dormant
    # a déjà quelque chose à l’écran de la commerciale.
    if touches.filter(statut=RelanceEtape.Statut.A_FAIRE).exists():
        return ('Une touche est encore ouverte sur ce dormant : rien ne '
                's’empile par-dessus.')
    # « pour les dormants qui retombent HORS de cette fenêtre » : celui dont
    # le réveil J60 est déjà tombé en pleine saison a eu son message au bon
    # moment — lui en poser un second serait la vague trimestrielle écartée.
    dernier = (touches.filter(cadence='reveil')
               .order_by('-due_date', '-ordre').first())
    if dernier is not None and dans_la_fenetre_saison(dernier.due_date):
        return ('Le réveil de ce dormant est déjà tombé pendant la saison : '
                'on n’en ajoute pas un second.')
    return None


def poser_reveil_saisonnier(lead, user=None, *, maintenant=None):
    """Pose LA touche `reveil_b` sur un dormant, ou renvoie ``None``.

    Idempotent par construction : le plafond « une par an et par dormant » de
    ``motif_de_refus`` est relu à chaque appel, donc deux passages dans la
    même saison ne créent jamais deux touches.

    N'écrit RIEN d'autre : ni étape de pipeline, ni étiquette, ni message
    envoyé. Le WhatsApp part à la main, comme tous les autres (décision
    fondateur du 08/09 — aucun envoi automatique).
    """
    from apps.parametres.models_relance import CanalRelance

    from . import horaires
    from .models import RelanceEtape

    if motif_de_refus(lead, maintenant=maintenant) is not None:
        return None

    local = _maintenant_local(maintenant)
    echeance = horaires.prochain_creneau_appel(
        local, lead.company, canal='whatsapp')
    jour = echeance.astimezone(horaires.CASABLANCA).date()
    # Une touche posée en toute fin de fenêtre ne doit pas déborder sur
    # octobre : hors saison, on ne la pose pas du tout.
    if not dans_la_fenetre_saison(jour):
        return None

    return RelanceEtape.objects.create(
        company=lead.company, lead=lead, cadence='reveil',
        ordre=REVEIL_SAISON_ORDRE, due_at=echeance, due_date=jour,
        canal=CanalRelance.WHATSAPP, libelle=REVEIL_SAISON_LIBELLE,
        template_cle=REVEIL_SAISON_CLE, cadence_depart=local,
        statut=RelanceEtape.Statut.A_FAIRE)


def poser_reveils_saisonniers(company, user=None, *, maintenant=None,
                              limite=200):
    """Passe la fenêtre sur les dormants d'une société : renvoie les touches
    posées. Best-effort lead par lead — un dormant en échec n'arrête pas les
    autres. Destinée au crochet planifié (qui n'existe pas encore : voir le
    rapport de la tâche), jamais déclenchée à l'insu de la commerciale.
    """
    from . import stages
    from .models import Lead

    local = _maintenant_local(maintenant)
    if not dans_la_fenetre_saison(local.date()):
        return []
    plafond = max(int(limite or 0), 0)
    if not plafond:
        return []
    dormants = (Lead.objects
                .filter(company=company, stage=stages.COLD,
                        is_archived=False, perdu=False)
                .order_by('id')[:plafond])
    posees = []
    for lead in dormants:
        try:
            etape = poser_reveil_saisonnier(lead, user, maintenant=maintenant)
        except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
            logger.warning(
                'CAD74 : réveil saisonnier impossible (lead #%s)',
                getattr(lead, 'pk', '?'), exc_info=True)
            continue
        if etape is not None:
            posees.append(etape)
    return posees
