"""COP2-C — LE chemin de création d'un lead saisi par une personne.

Deux entrées, UN seul chemin :

  * l'écran « nouveau lead » (``LeadViewSet.perform_create``) ;
  * l'assistant (``POST /api/django/crm/assistant/leads/creer/``).

``creer_lead_saisi`` est le corps, DÉPLACÉ SANS CHANGEMENT de logique ni
d'ordre, de l'ancien ``LeadViewSet.perform_create`` : enregistrement par le
``LeadSerializer`` (``validate()``, ``saisies_humaines``, héritage de
l'opposition de ``Lead.save()``), journal de création, base légale du registre
de consentement, ligne de relance, score, cadence de contact (best-effort).
Une porte de création de plus ne s'ajoute donc jamais : la garde PA1 (13 portes)
compte les appels ``Lead(...)``, et il n'y en a aucun ici.

Société, responsable, étape et source ne viennent JAMAIS du corps : la société
est celle de l'appelant, le responsable le défaut de la société (ou
l'appelant lui-même s'il ne voit que les siens), l'étape ``NEW`` et la source
``OS_NATIVE`` sont les défauts du modèle.
"""
from rest_framework.exceptions import ValidationError

from . import activity
from .leads_attribution import default_responsable_for

#: Coordonnées dont la saisie exige ``client_pii_voir`` (un rôle sans ce droit
#: ne les voit pas : le sérialiseur les ignorerait en silence, donc un lead
#: serait créé SANS son numéro — refusé en 400 à la place).
CHAMPS_CONTACT = ('telephone', 'whatsapp', 'email')


def creer_lead_saisi(serializer, user):
    """Enregistre le lead d'un ``LeadSerializer`` VALIDÉ et déroule tout ce qui
    suit une création manuelle. Rend le lead créé.

    Ordre inchangé (ancien ``LeadViewSet.perform_create``) : sauvegarde,
    journal de création, base légale, ligne de relance, score, cadence."""
    # Société toujours côté serveur (TenantMixin). Si aucun responsable
    # n'est choisi à la création, on applique le responsable par défaut
    # de la société (Paramètres). Un responsable explicite est respecté.
    extra = {'company': user.company}
    if not serializer.validated_data.get('owner'):
        # Un utilisateur à portée restreinte (Feature F) garde la propriété
        # de ce qu'il crée — sinon il perdrait de vue son propre lead. Les
        # comptes « voit tout » conservent l'assignation au responsable par
        # défaut de la société (comportement historique).
        if user.record_scope() != 'all':
            extra['owner'] = user
        else:
            # NTCRM1 — territoire consulté en premier, repli XSAL11.
            default = default_responsable_for(
                user.company, lead_attrs=serializer.validated_data)
            if default is not None:
                extra['owner'] = default
    serializer.save(**extra)
    activity.log_creation(serializer.instance, user)
    from .leads_score import recompute_lead_score
    from .cadence_plan import demarrer_cadence_contact, sync_relance_activity
    # CAD90 — un lead saisi à la main entre dans la cadence comme ceux du
    # site : il doit donc, comme eux, exister au registre de consentement.
    # La personne a elle-même sollicité le contact (appel entrant,
    # message reçu, demande au salon) : c'est la base légale tracée ici.
    from .leads_consentement import (
        BASE_LEGALE_SOLLICITATION,
        CONSENT_SOURCE_SAISIE_MANUELLE,
        enregistrer_base_legale_lead,
    )
    enregistrer_base_legale_lead(
        serializer.instance, source=CONSENT_SOURCE_SAISIE_MANUELLE,
        base_legale=BASE_LEGALE_SOLLICITATION)
    sync_relance_activity(serializer.instance, user)
    recompute_lead_score(serializer.instance)
    # MRY6 — un lead saisi à la main est une demande réelle : il entre
    # dans la cadence comme ceux du site. Best-effort intégral — la
    # création répond 201 même si la cadence échoue.
    demarrer_cadence_contact(
        serializer.instance, user=user, origine='saisie manuelle')
    return serializer.instance


class DoublonLead(Exception):
    """Un lead de la PORTÉE de l'appelant porte déjà ce téléphone, ce WhatsApp
    ou cet e-mail : rien n'est créé. ``lead`` = le lead existant, ``par`` = ce
    qui coïncide (``'numero'`` ou ``'email'``)."""

    def __init__(self, lead, par):
        super().__init__(f'doublon lead {lead.pk} ({par})')
        self.lead = lead
        self.par = par


def lead_doublon_en_portee(user, *, telephone=None, whatsapp=None, email=None):
    """``(lead, par)`` : le lead de la PORTÉE de ``user`` (société + visibilité
    de son rôle) qui partage un téléphone, un WhatsApp ou un e-mail normalisé
    avec les valeurs données, et ce qui coïncide (``'numero'`` ou
    ``'email'``) ; ``(None, None)`` sans doublon. Un lead hors portée compte
    comme ABSENT (D-ACRM-1 : rien n'en est dit). Les archivés sont inclus (le
    retrouver évite de recréer un dossier mis de côté) ; les vivants passent
    avant, puis le plus récent."""
    from .leads_doublons import (
        find_duplicates_by_contact, normalize_email, normalize_phone)
    from .portee_selectors import leads_en_portee

    cles = {normalize_phone(telephone), normalize_phone(whatsapp)} - {''}
    if not cles and not normalize_email(email):
        return None, None
    trouves = find_duplicates_by_contact(
        user.company, phone=telephone, whatsapp=whatsapp, email=email,
        queryset=leads_en_portee(user))
    if not trouves:
        return None, None
    trouves.sort(key=lambda x: x.pk, reverse=True)
    trouves.sort(key=lambda x: x.is_archived)
    lead = trouves[0]
    cles_du_lead = {normalize_phone(lead.telephone),
                    normalize_phone(lead.whatsapp)} - {''}
    return lead, ('numero' if cles & cles_du_lead else 'email')


def creer_lead_pour_assistant(request, donnees, *, note='',
                              creer_quand_meme=False):
    """Crée un lead depuis ce qu'une demande de client contient (``donnees`` =
    corps DÉJÀ validé par la vue, sans société/responsable/étape/source).

    * un rôle sans ``client_pii_voir`` qui envoie téléphone, WhatsApp ou e-mail
      reçoit un 400 qui nomme le champ ;
    * un doublon de la portée lève ``DoublonLead`` (rien n'est écrit) sauf
      ``creer_quand_meme`` (D-ACVI-5 : une seconde demande délibérée est
      permise, jamais silencieuse) ;
    * la création passe par ``creer_lead_saisi`` (le chemin de l'écran) avec le
      contexte de la requête ;
    * ``note`` devient une note du fil du lead (interne, jamais envoyée) — sans
      valoir « premier contact » : c'est la demande du client, pas une prise de
      contact de l'équipe.
    """
    from .serializers import LeadSerializer, pii_masquee_pour

    user = request.user
    if pii_masquee_pour(user):
        erreurs = {c: ['Votre rôle ne permet pas de saisir cette coordonnée '
                       '(droit « voir les coordonnées clients » manquant).']
                   for c in CHAMPS_CONTACT if donnees.get(c)}
        if erreurs:
            raise ValidationError(erreurs)
    if not creer_quand_meme:
        lead, par = lead_doublon_en_portee(
            user, telephone=donnees.get('telephone'),
            whatsapp=donnees.get('whatsapp'), email=donnees.get('email'))
        if lead is not None:
            raise DoublonLead(lead, par)
    serializer = LeadSerializer(
        data={cle: valeur for cle, valeur in donnees.items()
              if valeur not in (None, '')},
        context={'request': request})
    serializer.is_valid(raise_exception=True)
    lead = creer_lead_saisi(serializer, user)
    if note:
        activity.log_note(lead, user, note)
    return lead
