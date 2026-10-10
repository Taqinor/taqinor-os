"""QJ6 + Lead → Client resolution.

QJ6 — recompute_lead_score(lead) persiste le score calculé sur le lead pour
permettre un tri pagination-safe (?ordering=-score). Appelé dans perform_create
et perform_update du LeadViewSet.

Lead → Client resolution (approach approved by the founder, 2026-06-12).

A quote always carries a Client; when it starts from a Lead the client is
resolved automatically, without ever creating duplicates:

  1. the lead is already linked to a client  → reuse that client;
  2. the lead has an email matching an existing client of the SAME company
     (case-insensitive)                      → link and reuse that client;
  3. otherwise                               → create a client from the lead's
     contact details and link it.

The resolved link is persisted on the lead, so every later quote from the
same lead reuses the same client. Everything stays tenant-scoped.
"""
import logging

from rest_framework.exceptions import ValidationError as DRFValidationError

# CRX26 — LA date MÉTIER (Africa/Casablanca), lue EXPLICITEMENT : elle ne dépend
# d'aucun réglage global. Avant AUD836, ``settings.TIME_ZONE`` valait ``'UTC'``
# et ``timezone.localdate()`` était en retard d'un jour entier une heure par
# nuit ; le réglage dit désormais la même chose, ce helper reste la garantie.

from . import activity, stages
from .models import Lead, LeadActivity

from .leads_socle import (  # noqa: F401 — façade
    _company_fallback_managers,
    lead_notification_recipients,
    motif_refus_valide,
    user_and_superior_recipients,
    visite_point_eau_requise,
    visite_pro_avant_devis,
)

from .leads_doublons import (  # noqa: F401 — façade
    find_duplicates_by_contact,
    is_strong_identity_match,
    normalize_email,
    normalize_phone,
)

from .leads_premier_contact import maybe_set_first_contacted_at

from .leads_consentement import enregistrer_consentements_intake_web  # noqa: F401 — façade

from .visites_rdv import public_booking_url, send_due_appointment_reminders  # noqa: F401 — façade

from .visites_retour_lead import journaliser_visite  # noqa: F401 — façade

from .cadence_messages import (  # noqa: F401 — façade
    _corps_pour_segment,
    _omettre_phrases_incompletes,
    message_pour_etape,
)

from .fiche_funnel import _bulk_stage_allowed, _emit_stage_changed
from .fiche_funnel import (  # noqa: F401 — façade
    _rang_funnel,
    ajuster_score_lead,
    appliquer_stage_lead,
    assigner_lead_a,
    avancer_stage_lead_vers,
    creer_relance_lead,
    poser_tag_lead,
    retirer_tag_lead,
)

from .cadence_plan import demarrer_cadence_contact, sync_relance_activity
from .cadence_plan import (  # noqa: F401 — façade
    _garde_cadence_contact,
    arreter_cadence,
    calculer_echeances_cadence,
    devis_envoyes_pour_relance,
)

from .clients_identite import (  # noqa: F401 — façade
    clients_par_ids,
    completer_client_depuis_acceptation,
    ecrire_identite_client,
    merge_clients,
    resolve_client_for_lead,
)

from .leads_score import recompute_lead_score
from .leads_score import maybe_assign_mql  # noqa: F401 — façade

from .leads_notifications import notify_devis_opened, notify_new_lead  # noqa: F401 — façade

from .cadence_signaux import (  # noqa: F401 — façade
    CALLBACK_REQUESTED_MARKER,
    SIGNAL_PROPOSITION_ROUVERTE,
    noter_version_remplacee_ouverte,
    notifier_signal_lecture,
    notify_client_contact_request,
    notify_lead_callback_requested,
    poser_touche_signal_du_lead_id,
)

from .devis_chatter import (  # noqa: F401 — façade
    noter_devis_corrige,
    noter_devis_envoye,
    noter_devis_ouvert,
    noter_devis_reouvert,
)

from .clients_pilotage import (  # noqa: F401 — façade
    ajouter_specialite_partenaire,
    handle_parrainage_signup,
    poser_compteur_deploiements,
    soumettre_lead_partenaire,
)

from .fiche_ecritures import (  # noqa: F401 — façade
    CHAMP_AUTO_CADENCE,
    CHAMP_AUTO_INCHANGE,
    CHAMP_AUTO_INVALIDE,
    appliquer_champ_automatique,
    noter_touche_marketing,
)

from .fiche_archivage import delete_leads_for_company  # noqa: F401 — façade

from .leads_meta import (  # noqa: F401 — façade
    _apply_meta_form_extras,
    _meta_type_installation,
    _parse_meta_form_extras,
    backfill_meta_lead_attribution,
    create_lead_from_meta_lead_ads,
    create_minimal_lead_from_ctwa,
    fetch_meta_lead_node,
    import_external_notes_for_contact,
)

from .leads_intake import (  # noqa: F401 — façade
    create_draft_lead_from_ocr,
    create_lead_depuis_ticket,
    create_lead_from_evenement_marketing,
    finaliser_lead_importe,
    find_lead_by_email,
    find_lead_by_phone,
    reactivate_lead_on_new_touch,
    resolve_or_create_lead_from_whatsapp,
)

from .leads_attribution import default_responsable_for  # noqa: F401 — façade

# T-TRACE — le traçage des visiteurs externes vit dans son propre module
# (``apps/crm/visites.py``) pour ne pas gonfler ce fichier déjà très long,
# mais il est RÉEXPORTÉ ici : `services` reste la porte d'entrée unique des
# écritures CRM (les accroches n'importent jamais `visites` directement).
from .visites import (  # noqa: F401 — réexport public délibéré
    COOKIE_APPAREIL,
    COOKIE_EQUIPE,
    alerter_appareil_partage,
    appareil_de_requete,
    appareils_equipe_ids,
    avec_direction,
    detecter_concurrent,
    domaine_cookies_equipe,
    enregistrer_appareil_equipe,
    enregistrer_visite_externe,
    est_appareil_equipe,
    historique_appareil,
    ip_de_requete,
    rattacher_visites_au_lead,
    requete_marquee_equipe,
    resume_historique_fr,
    tracer_et_correler,
    user_agent_de_requete,
    utilisateurs_direction,
)

logger = logging.getLogger(__name__)


# ── YLEAD11 — Réactivation d'un lead perdu/COLD sur nouvelle touche entrante ──


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


# CAD72 (21/09/2026) — le SECOND catalogue « parrainage » de YSERV11 a
# disparu d'ici. Un dictionnaire de textes par défaut + un générateur
# `get_or_create_*` vivaient ici, semant une SECONDE ligne
# `crm.MessageTemplate` au premier usage — texte FR promettant une
# récompense FERME, et texte darija TRANSCRIT EN ALPHABET LATIN (chiffres
# pour des lettres arabes — « 3 »/« 9 »), alors que le catalogue darija
# validé (`parametres.MESSAGE_TEMPLATE_DEFAULTS_DARIJA`) est écrit en
# arabe, relu par un natif le 04/09/2026. Leur seul appelant vivait dans
# `apps/compta/services.py` (flux NPS), retiré quand `compta` a été mis en
# coquille par le drain SOLMVP (`apps/compta/` n'a plus de `services.py`) —
# plus aucun appelant (grep sur tout le backend). Le catalogue UNIQUE pour
# les messages client est désormais `parametres.MessageTemplate` (clé
# `parrainage`, déjà validée dans `docs/crm/messages_meryem.md`, rendue par
# `message_pour_etape` comme n'importe quelle autre touche) — voir
# `tests_cad72_parrainage_catalogue_unique.py`.


# ─────────────────────────────────────────────────────────────────────────────
# QX42 — Rétention PII des copies brutes d'intake (registre YOPSB10, core.retention)
#
# `WebsiteLeadPayload` (PII brute + IP) et `ChatSessionPublique`
# s'accumulaient INDÉFINIMENT. ACRM19 — l'effacement d'un lead
# (`dsr_provider.anonymiser_lead`, DSR ET rétention) caviarde désormais LUI-MÊME
# ces copies brutes : les purges par âge ci-dessous ne sont plus le seul
# rempart, seulement le ménage de fond. Le framework générique existe (`core.retention`)
# mais son registre est VIDE — aucune app n'y enregistre de politique. Ceci
# enregistre la politique CRM (voir `CrmConfig.ready()`), fenêtre par défaut
# 180 jours, override founder via `WEBSITE_LEAD_PAYLOAD_RETENTION_DAYS` /
# `CHAT_SESSION_RETENTION_DAYS` (settings/.env — même patron que les autres
# constantes founder-configurables de ce module, ex.
# `WEBSITE_LEAD_WEBHOOK_SECRET`). 0/négatif désactive la purge (conservation
# illimitée, comportement actuel inchangé).


# ─────────────────────────────────────────────────────────────────────────────
# YOPSB11 — Archivage par lots de `LeadActivity` (chatter à forte croissance)
#
# Le chatter (`LeadActivity`) est append-only et grossit sans borne, alourdissant
# le chemin chaud. `archiver_anciens(now, jours)` DÉPLACE les entrées plus
# vieilles que `jours` vers la table froide `LeadActivityArchive` (par lots de
# 5 000, un commit par lot — jamais de transaction géante) puis les supprime de
# la table vive. Fenêtre par défaut 0 = OFF (aucun archivage, comportement
# inchangé) ; réglage via `CRM_LEADACTIVITY_ARCHIVE_DAYS`. La politique est
# enregistrée dans le registre partagé YOPSB10 depuis `CrmConfig.ready()`.


# ── NTMIG28 — miroir du compteur de déploiements d'un partenaire ────────────


# ---------------------------------------------------------------------------
# AUD518 — Effets de CRÉATION d'un lead importé (dataimport)
# ---------------------------------------------------------------------------


# ── MRY30 — PLACEMENT DES ANCIENS LEADS DANS LES CADENCES DU MOTEUR ──────────
#
# Le moteur de relances ne démarre que sur les leads qui ARRIVENT. Le
# portefeuille déjà présent — plusieurs centaines de dossiers, dont les 930
# leads du miroir Odoo — resterait donc sans aucune cadence, et le bénéfice
# n'arriverait qu'au fil des semaines. Décision fondateur du 06/09/2026 :
# « tous les anciens leads non Froid sont traités ; le moteur décide à quelle
# étape des six appels chacun se trouve ».
#
# Trois différences assumées avec la reprise MRY23
# (`demarrer_cadences_existantes`, qui reste en place et ne change pas) :
#
#   1. le MIROIR ODOO EST INCLUS. `_garde_cadence_contact` refuse
#      `source == ODOO_IMPORT_TEST` — garde juste pour un démarrage AUTOMATIQUE
#      à la création (elle empêche un import de 930 lignes d'inonder la file),
#      fausse pour un placement DEMANDÉ à la main sur ce même portefeuille.
#      C'est pourquoi ce service appelle `initialiser_plan_relance`
#      directement et JAMAIS `demarrer_cadence_contact` ;
#   2. il n'y a pas de fenêtre d'éligibilité qui laisse des leads de côté :
#      un dossier trop ancien pour être relancé n'est pas ignoré, il est mis
#      en DORMANCE explicite (Froid + étiquette + réveil étalé) ;
#   3. l'aperçu et l'application partagent LE MÊME CALCUL — sans partager
#      les écritures. L'aperçu était une exécution complète dans une
#      transaction annulée : fidèle, mais il matérialisait les touches des
#      277 candidats pour les jeter aussitôt, soit plus de 20 s pendant
#      lesquelles le navigateur abandonnait (deux 499 dans nginx le
#      07/09/2026, sur le clic « Aperçu » du Cockpit). Il est désormais un
#      CALCUL PUR : mêmes décisions, mêmes créneaux, mêmes dates — obtenus
#      par `calculer_echeances_cadence`, la fonction que l'application
#      utilise elle aussi pour créer les touches. Un dry-run qui recalcule
#      « à côté » finit toujours par annoncer autre chose que ce que --apply
#      fait ; partager la FONCTION donne la même garantie que partager
#      l'exécution, pour le prix d'un calcul ;
#   4. l'application se fait PAR LOTS de `limite` leads (défaut 40), l'écran
#      rappelant tant que `restants > 0`. Écrire 277 dossiers d'un trait
#      dépassait le délai du navigateur exactement comme l'aperçu.


# ── VISITE-CADENCE — LE SUIVI COMMERCIAL RÉAGIT À LA VISITE ──────────────────
#
# Ordre fondateur du 15/09/2026. La visite technique se place APRÈS l'envoi du
# devis, comme outil de closing. Trois conséquences, et elles vivent ICI (pas
# dans les récepteurs, qui restent minces et se contentent d'appeler) :
#
#   * quand un RENDEZ-VOUS est pris, les messages génériques de relance se
#     TAISENT jusqu'après la visite — continuer à demander « le PDF s'ouvre
#     bien ? » à quelqu'un qui reçoit le technicien jeudi est le genre de
#     faute qui décrédibilise tout le suivi — et deux gestes utiles les
#     remplacent en attendant ;
#
#     AMENDEMENT FONDATEUR (15/09/2026) — ils se TAISENT, ils ne MEURENT PAS.
#     La première écriture de ce lot ANNULAIT la cadence après-devis : le lead
#     perdait sa place dans le protocole, et une visite qui n'aboutit pas
#     laissait un dossier sans suivi (ou, pire, exigeait un REDÉMARRAGE de
#     cadence — un client reprenant le plan au barreau 1 après avoir déjà reçu
#     neuf messages). On DÉCALE désormais : la touche pendante, tout ce qui la
#     suit, ET l'ancre de la cadence glissent jusqu'après le débrief. Le lead
#     garde sa POSITION EXACTE (même ordre, même libellé, même reste de plan) ;
#     si la visite ne donne rien, le suivi reprend tout seul là où il en était.
#     Aucun `initialiser_plan_relance` n'est appelé sur un lead qui a déjà des
#     étapes après-devis : il n'y a JAMAIS de restart.
#   * quand le technicien repart, le RESPONSABLE doit rappeler sous 24-48 h,
#     tant que la visite est fraîche ;
#   * le TEXTE LIBRE du terrain entre dans l'historique du lead : c'est
#     souvent la seule trace de ce que le client a dit sur place.
#
# Aucune de ces fonctions ne touche ``Lead.stage`` : le statut d'une visite est
# un layer DOCUMENT, jamais une étape de funnel (``STAGES.py`` intact).


# ── VT1 — CHATTER AUTOMATIQUE DE LA VISITE TECHNIQUE TERRAIN ─────────────────
#
# Le chatter du lead (``LeadActivity``) est le journal COMMUN de tout ce qui
# arrive à un lead : la visite technique y écrit ses quatre moments — création,
# terminaison, feu vert, renvoi — plutôt que d'ouvrir un second historique.
# L'auteur et la société viennent TOUJOURS du serveur (jamais du corps de
# requête), comme le reste du chatter.


# ── AGR522 — DOSSIER DE SUBVENTION FDA : LE RAPPEL DES 3 MOIS ───────────────
#
# Guide FDA 2024 (p.22-23, tableau « Délais ») : « Demande de subvention —
# 3 mois à compter de la date de l'approbation préalable », après la
# RÉALISATION. Au passage à « accordé », une étape MANUELLE datée est posée
# pour le lendemain (filet hors gabarit — jamais une touche de cadence,
# CAD124). Ce délai n'est JAMAIS écrit au client.


# ── NTDATA18 — FUSION SUPERVISÉE DE CLIENTS ─────────────────────────────────
#
# Sur le modèle de `merge_leads` ci-dessus, mais pour `Client` : le détecteur
# (`dataquality.services.doublons_clients`) PROPOSE, un humain DÉCIDE, et cette
# fonction exécute. Jamais de fusion automatique.
#
# TROIS GARANTIES DURES :
#
# 1. AUCUNE SUPPRESSION. Le doublon n'est jamais effacé : il est NEUTRALISÉ.
#    `Client` ne porte pas (encore) de drapeau d'archivage — ajouter une
#    colonne supposerait une migration `crm`, hors du périmètre de cette
#    tâche. On utilise donc le mécanisme EXISTANT prévu pour ça :
#    `avertissement_bloquant` (une garde serveur refuse dès lors l'acceptation
#    et la facturation d'un devis pour ce client, patron XFAC28) + un
#    avertissement lisible, + un marqueur `custom_data['fusionne_dans']` qui
#    trace la cible et la date. La fiche reste consultable, son historique
#    intact, et la fusion est intégralement réversible à la main.
#
# 2. AUCUN ORPHELIN. Tout ce qui pointait le doublon pointe le survivant —
#    non pas une liste de quatre modèles écrite à la main (le dépôt compte
#    plus de trente FK vers `Client`), mais le parcours des relations inverses
#    déclarées par Django (`core.merge.repointer_relations`, la MÊME mécanique
#    que la fusion fournisseur/produit de `stock` — jamais une seconde
#    implémentation). Chaque relation est repointée dans son PROPRE point de
#    sauvegarde : une contrainte d'unicité qui refuse (le survivant a déjà sa
#    limite de crédit, par exemple) annule CETTE relation seule et le rapport
#    la NOMME, au lieu de faire échouer toute la fusion en silence.
#
# 3. AUCUN IMPORT D'APP ÉTRANGÈRE. Le parcours passe par l'API `_meta` de
#    Django, donc `crm` n'importe ni `ventes`, ni `facturation`, ni
#    `installations`, ni `sav`.


# ── CAD-G ── CAD74 — réveil saisonnier (`reveil_b`) ────────────────────────
# Le câblage vit dans `apps/crm/cadence_reveil_saison.py` (module autonome —
# ce fichier est partagé par des dizaines de tâches). Ces deux passe-plats
# sont le point d'entrée attendu par les appelants de `services` ; ils ne
# dupliquent aucune logique. Crochet planifié : AUCUN aujourd'hui — la pose
# se déclenche par un appel explicite, jamais à l'insu de la commerciale.


# ── CAD-I ── CAD90 — le registre couvre TOUTES les créations de lead ────────
#
# Audit L3 du 21/09/2026. ``enregistrer_consentement_lead`` n'était appelée
# que depuis le webhook du formulaire du site : un lead créé à la main par la
# commerciale (appel entrant, WhatsApp reçu au salon), un lead Meta Lead Ads
# ou un lead venu d'un document n'écrivaient RIEN au registre
# ``core.ConsentRecord`` — alors que la cadence démarre quand même et que sa
# touche n°1 est un WhatsApp, le canal le plus encadré.
#
# CE QUE ``granted`` VEUT DIRE ICI, ET CE QU'IL NE VEUT PAS DIRE. Il dit
# seulement si un CONSENTEMENT A ÉTÉ RECUEILLI — jamais si le traitement est
# licite. Sur ces chemins, aucune case n'a été cochée par la personne : la
# licéité vient de la BASE LÉGALE, tracée dans ``source``. Écrire
# ``granted=True`` pour faire joli fabriquerait une preuve fausse, ce qui est
# pire qu'une preuve absente (même raison que ``ip_confirmation`` laissée
# vide par l'intake web).
#
# LES DEUX BASES, SUR TEXTE PRIMAIRE (extraction du round 2 de l'audit, PDF
# adala.justice.gov.ma) :
#   * données NON collectées auprès de la personne (Meta, import, document) —
#     loi 09-08 art. 5 §3, avec l'information due « par tous moyens » de
#     l'art. 34 du décret 2-09-165 ;
#   * la personne a elle-même SOLLICITÉ le contact (appel entrant, message
#     WhatsApp, demande au salon) — relation précontractuelle à sa demande,
#     loi 09-08 art. 5. Le CNDP distingue les deux, le registre aussi.


# ── CAD-K ── CAD129 — « rappelez-moi » entre dans la FILE, pas dans la cloche ─
#
# Audit L3 du 21/09/2026. Un clic « rappelez-moi » écrivait une note, notifiait
# le responsable et son supérieur, et posait la préférence « joignable par
# téléphone » — mais ne créait AUCUNE touche. Si la notification est noyée dans
# la cloche, la demande la plus forte qu'un prospect puisse faire disparaît.
#
# LA RÈGLE : décaler, jamais redémarrer. Quand le lead a déjà un plan en cours,
# on RAMÈNE sa prochaine touche au prochain créneau d'appel et tout le reste du
# plan glisse du MÊME delta (``reporter_prochaine_touche`` le fait déjà, ancre
# comprise) : le lead garde sa position dans le protocole, on ne fabrique pas un
# second plan concurrent. Quand il n'a plus aucune touche ouverte (cadence
# terminée ou arrêtée), on pose UNE touche — une seule, jamais un plan.


# ── CAD164 — le LOCATAIRE : demander le propriétaire, sinon « Perdu — Locataire »
#
# Décision fondateur du 21/09/2026 : on demande le propriétaire ; s'il est
# joignable, on crée SA fiche, LIÉE à celle du locataire (le locataire reste le
# prescripteur : son prénom passe par la variable `{prescripteur}` du texte
# d'origine « recommandation », CAD127 — jamais en dur) ; sinon on clôt avec
# le motif EXISTANT « Locataire ». Aucune valeur d'énumération neuve : le motif
# existe (`MotifPerte`), le canal « Référence » aussi, et le lien entre les deux
# fiches est une NOTE d'historique de chaque côté — jamais une fusion
# automatique (conduite `FLUX_LOCATAIRE` du script d'appel).
