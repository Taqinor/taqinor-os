"""Écritures de l'API publique et notes externes (SPL25, extrait de crm/services.py : déplacement pur).

Module de type (a) de la scission : il n'importe ni ``.services`` ni un
module racine ; ``services`` réexporte ce qu'il faut (façade).
"""
from rest_framework.exceptions import ValidationError as DRFValidationError

from . import activity, stages
from .cadence_plan import demarrer_cadence_contact, sync_relance_activity
from .fiche_funnel import _bulk_stage_allowed, _emit_stage_changed
from .leads_premier_contact import maybe_set_first_contacted_at
from .leads_score import recompute_lead_score
from .models import Lead, LeadActivity


# ── XPLT5 — API publique en ÉCRITURE (leads:write / activities:write) ───────
# Point d'entrée cross-app sanctionné (services.py) pour `apps.publicapi` :
# la société vient TOUJOURS de l'appelant (résolue depuis la clé API, jamais
# du corps), jamais acceptée en argument depuis les données utilisateur.


PUBLIC_LEAD_WRITABLE_FIELDS = (
    'nom', 'prenom', 'societe', 'email', 'telephone', 'ville',
    'canal', 'priorite', 'type_installation', 'stage',
)


def create_lead_from_public_api(*, company, fields):
    """XPLT5 — crée un lead depuis l'API publique en écriture.

    ``fields`` est filtré à la liste blanche ``PUBLIC_LEAD_WRITABLE_FIELDS``
    (un champ non listé est silencieusement ignoré — jamais 500). ``stage``,
    s'il est fourni, doit être une clé canonique STAGES.py valide (sinon
    ``ValueError`` — jamais de nouvelle liste d'étapes, jamais hardcodée) ;
    absent, le lead prend le défaut du modèle (NEW). ``nom`` est obligatoire.
    Company forcée serveur, jamais du body. Journalise la création
    (``LeadActivity``, acteur système) comme tout autre point d'entrée."""
    clean = {k: v for k, v in (fields or {}).items()
             if k in PUBLIC_LEAD_WRITABLE_FIELDS and v not in (None, '')}
    nom = (clean.pop('nom', '') or '').strip()
    if not nom:
        raise ValueError("Le champ « nom » est obligatoire.")
    stage = clean.pop('stage', None)
    if stage is not None and stage not in stages.STAGES:
        raise ValueError(
            f'Étape inconnue : {stage!r} (STAGES.py = {stages.STAGES}).')
    lead = Lead.objects.create(
        company=company, nom=nom,
        stage=stage or stages.NEW,
        **clean,
    )
    activity.log_creation(lead, None)
    # MRY6 — l'API publique crée de VRAIES demandes (formulaire partenaire,
    # intégration) : elles entrent dans la cadence comme les autres.
    demarrer_cadence_contact(lead, origine='api_publique')
    return lead


#: CRX21 — colonnes DÉRIVÉES recalculées par ``Lead.save()`` (QW10). Sans
#: elles dans ``update_fields``, un changement de téléphone/email n'est PAS
#: répercuté sur les colonnes indexées de dédup : le lead reste trouvable par
#: son ANCIEN numéro et invisible sous le nouveau. Même table que
#: ``LeadViewSet.COLONNES_DERIVEES`` (views.py) — la parité est le sujet de la
#: tâche : l'API publique écrit les mêmes leads que l'écran.
PUBLIC_LEAD_COLONNES_DERIVEES = {'telephone': 'phone_normalise',
                                 'email': 'email_normalise'}


def update_lead_from_public_api(*, company, lead_id, fields):
    """XPLT5 — met à jour un lead EXISTANT DE CETTE SOCIÉTÉ depuis l'API
    publique en écriture. Lève ``Lead.DoesNotExist`` si le lead n'appartient
    pas (ou plus) à ``company`` — jamais de fuite cross-tenant. Champs
    filtrés à la même liste blanche que la création ; ``stage`` validé contre
    STAGES.py. Journalise chaque champ changé (chatter, acteur système).

    CRX21 — PARITÉ avec le PATCH de l'écran (``LeadViewSet.perform_update``),
    qui manquait entièrement à ce chemin :

    * **verrou du lead perdu** — un lead marqué perdu ne change pas d'étape,
      pas même par une intégration (le ``LeadSerializer`` refuse déjà, et ce
      verrou PRÉCÈDE toute échappatoire) ;
    * **garde funnel** ``_bulk_stage_allowed`` — une intégration ne recule ni
      ne rouvre un pipeline. Il n'y a PAS ici l'échappatoire ``confirme_recul``
      de l'écran : elle suppose une confirmation HUMAINE devant un lead nommé,
      qu'aucun appel machine ne peut donner ;
    * **les 4 effets internes** de ``perform_update`` : émission de
      ``lead_stage_changed``, ``first_contacted_at`` (FG28), recalcul du score
      (QJ6) et synchronisation de l'activité de relance ;
    * **colonnes dérivées** (``phone_normalise``/``email_normalise``) ajoutées
      à ``update_fields`` quand leur source change — sinon la dédup indexée
      devient aveugle après un changement de téléphone (chemins publicapi bulk
      ET PATCH unitaire).

    Lève ``ValueError`` (traduit en 400 par les vues publiques) sur une étape
    inconnue, un lead perdu, ou un recul de funnel.
    """
    lead = Lead.objects.get(company=company, pk=lead_id)
    clean = {k: v for k, v in (fields or {}).items()
             if k in PUBLIC_LEAD_WRITABLE_FIELDS}
    stage = clean.get('stage')
    # ACRM58 — ``stage`` présent mais vide (null comme '') : erreur SOUS LE
    # CHAMP (400 ``{stage: [...]}``), jamais un IntegrityError (500). Une
    # ValidationError DRF (pas un ValueError) pour que la vue publique la
    # rende telle quelle, champ nommé ; l'import en masse l'inscrit en ligne
    # en erreur.
    if 'stage' in clean and stage in (None, ''):
        raise DRFValidationError(
            {'stage': ["L'étape ne peut pas être vide."]})
    if stage is not None and stage not in stages.STAGES:
        raise ValueError(
            f'Étape inconnue : {stage!r} (STAGES.py = {stages.STAGES}).')
    if stage is not None and stage != lead.stage:
        if lead.perdu:
            raise ValueError('Lead perdu — étape non modifiable.')
        if not _bulk_stage_allowed(lead.stage, stage):
            raise ValueError("On ne recule pas une étape.")
    old = Lead.objects.get(pk=lead.pk)
    changed_fields = []
    for field, value in clean.items():
        if value in (None, '') and field != 'stage':
            continue
        if getattr(lead, field) != value:
            setattr(lead, field, value)
            changed_fields.append(field)
    if changed_fields:
        ecrits = list(changed_fields)
        for source, derivee in PUBLIC_LEAD_COLONNES_DERIVEES.items():
            if source in changed_fields:
                ecrits.append(derivee)
        lead.save(update_fields=ecrits)
        activity.log_changes(old, lead, None)
        # Les 4 effets du PATCH de l'écran, dans le même ordre. Tous sont
        # best-effort par construction (chacun catche pour son compte) : une
        # intégration ne doit jamais échouer sur un effet secondaire.
        sync_relance_activity(lead, None)
        maybe_set_first_contacted_at(old, lead)
        recompute_lead_score(lead)
        _emit_stage_changed(lead, old.stage, lead.stage, user=None)
    return lead


def create_activity_from_public_api(*, company, lead_id, body):
    """XPLT5 — ajoute une note (activité chatter) sur un lead DE CETTE
    SOCIÉTÉ depuis l'API publique en écriture. Lève ``Lead.DoesNotExist`` si
    hors société (jamais de fuite cross-tenant). ``body`` ne peut être vide."""
    lead = Lead.objects.get(company=company, pk=lead_id)
    body = (body or '').strip()
    if not body:
        raise ValueError("Le champ « body » est obligatoire.")
    return activity.log_note(lead, None, body)


def ajouter_note_lead(*, company, lead_id, user, body):
    """NTMOB1 — ajoute une note (activité chatter) sur un lead DE CETTE
    SOCIÉTÉ, avec l'utilisateur ACTEUR (contrairement à
    ``create_activity_from_public_api``, qui journalise sans acteur).

    Point d'entrée cross-app pour rejouer une note posée hors-ligne sans
    importer ``apps.crm.models``/``views``. Lève ``Lead.DoesNotExist`` hors
    société (jamais de fuite cross-tenant) et ``ValueError`` sur un corps vide.
    """
    lead = Lead.objects.get(company=company, pk=lead_id)
    body = (body or '').strip()
    if not body:
        raise ValueError("Le champ « body » est obligatoire.")
    return activity.log_note(lead, user, body)


def ajouter_note_lead_si_nouvelle(*, company, lead_id, user, body):
    """Comme :func:`ajouter_note_lead`, mais SANS RÉPÉTER un corps identique.

    Rend l'activité créée, ou ``None`` si le lead porte DÉJÀ une note au corps
    exactement identique.

    POURQUOI ELLE EXISTE (F6, 29/08/2026). L'auto-pipeline du tunnel doit
    laisser une trace quand le moteur REFUSE de chiffrer un lead — sans quoi le
    commercial constate seulement que « hier ces leads recevaient un devis ».
    Mais le refus RELÂCHE la marque de dédup (une donnée manquante aujourd'hui
    ne doit pas fermer le lead pour toujours) : chaque nouvelle livraison du
    webhook rejoue donc le même refus, et une note par rejeu ensevelirait
    l'historique du lead sous le même paragraphe. La note est donc posée une
    fois par MOTIF : le motif change ⇒ une nouvelle note ; le motif se répète
    ⇒ silence.

    La comparaison porte sur le CORPS et rien d'autre — c'est lui que le
    commercial lit, et c'est lui qui nomme le champ manquant.
    """
    lead = Lead.objects.get(company=company, pk=lead_id)
    body = (body or '').strip()
    if not body:
        raise ValueError("Le champ « body » est obligatoire.")
    deja = LeadActivity.objects.filter(
        company=company, lead=lead, kind=LeadActivity.Kind.NOTE,
        body=body).exists()
    if deja:
        return None
    return activity.log_note(lead, user, body)
