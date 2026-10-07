"""Écritures/orchestration du module « Visites terrain » (``apps.visites``).

VT3 — LE FEU VERT DU BUREAU D'ÉTUDES
------------------------------------
Deux transitions, deux notifications au COMMERCIAL de la visite (primitive
``apps.notifications`` existante — jamais un second système de messages) :
« validée » (feu vert, il peut passer au calepinage) et « à refaire » (une
action lui est demandée, avec le motif). Ces deux transitions ne portent
AUCUN jugement automatisé : c'est un humain qui décide, le code se contente
d'enregistrer sa décision et de la faire savoir.

FRONTIÈRE M3 — cette app n'importe JAMAIS ``apps.crm.models`` et n'écrit
JAMAIS sur ``crm.Lead`` :

* le FEU VERT est publié comme ÉVÉNEMENT ``visite_validee`` (bus
  ``core.events``, M6) ; c'est ``apps.crm.receivers`` qui décide ce qu'il
  inscrit sur la fiche lead. Le ``lead_id`` voyage en entier, le récap est
  pré-calculé par le selector de cette app ;
* le chatter des AUTRES moments (création / terminée / à refaire) passe par
  ``journaliser_visite`` ci-dessous, qui délègue au ``services.py`` du CRM en
  import paresseux — le journal d'un lead appartient au lead.
"""
import re
import unicodedata

# ERR-QAH-VISITES-COUVERTURE-ENUM-SANS-AFFORDANCE — mots vides qu'on retire
# d'une saisie libre AVANT de retenter la correspondance (« Bon état » →
# « bon », « État moyen » → « moyen »). Volontairement COURT : ce n'est pas un
# vocabulaire, juste le bruit que « libellé + état » ajoute autour du code.
_MOTS_VIDES_CHOIX = frozenset({'etat', 'de', 'du', 'la', 'le', 'les'})


def _jetons_normalises(texte):
    """Découpe ``texte`` en jetons minuscules SANS accents ni ponctuation.

    Règle fondateur « normaliser plutôt que refuser quand l'intention est
    claire » (08/09/2026) : un technicien qui tape « Tuile », « Bon état » ou
    « Tôle » exprime une intention limpide — le refuser sans lui dire quoi
    taper (avant cette correction, les deux champs étaient des champs texte
    libres SANS liste ni placeholder) est le bug lui-même.
    """
    sans_accents = unicodedata.normalize('NFKD', str(texte))
    sans_accents = ''.join(c for c in sans_accents if not unicodedata.combining(c))
    return [t for t in re.split(r'[^a-z0-9]+', sans_accents.lower()) if t]


def normaliser_choix(brute, choix):
    """Fait correspondre une saisie libre à UN code de ``choix``, ou ``None``.

    Toujours un MATCH EXPLICITE (jamais un « au plus proche ») : jetons
    normalisés strictement égaux à un code connu (« bac acier » ↔
    « bac_acier »), puis la même comparaison après avoir retiré les mots
    vides ``_MOTS_VIDES_CHOIX`` (« bon état » → « bon »). Une valeur qui ne
    matche toujours pas reste refusée — avec le message qui NOMME le champ
    (règle fondateur), jamais une normalisation silencieuse qui devinerait.
    """
    jetons = _jetons_normalises(brute)
    if not jetons:
        return None
    jetons_par_code = {code: _jetons_normalises(code) for code in choix}
    if jetons in jetons_par_code.values():
        for code, cle in jetons_par_code.items():
            if cle == jetons:
                return code
    filtres = [t for t in jetons if t not in _MOTS_VIDES_CHOIX]
    if filtres and filtres != jetons:
        for code, cle in jetons_par_code.items():
            if cle == filtres:
                return code
    return None


def _notifier_commercial_visite(visite, event_type, titre, corps):
    """Notifie le commercial de la visite. Best-effort, jamais bloquant."""
    destinataire = visite.commercial
    if destinataire is None:
        return None
    try:
        from apps.notifications.services import notify

        return notify(
            destinataire, event_type, titre, body=corps,
            link=f'/visites/{visite.pk}', company=visite.company)
    except Exception:  # pragma: no cover - défensif
        return None


def notifier_assignation(visite, acteur=None):
    """VTA7 — previent l'ASSIGNE qu'une visite l'attend.

    Appele a la creation ET a la reassignation : sans ce message, un commercial
    terrain ne decouvrait sa visite qu'en ouvrant l'app -- alors que sa journee
    vient justement de changer. Le lien pointe l'ecran de la visite dans l'app
    autonome (``/visites/<id>``).

    Trois prudences :

    * on ne notifie PAS l'acteur de sa propre assignation (s'assigner une
      visite ne merite pas une cloche) ;
    * pas de destinataire (visite non assignee) => rien a envoyer ;
    * best-effort -- la visite est deja creee/reassignee quand on arrive ici,
      une notification en echec ne doit pas defaire ce geste.

    La cloche elle-meme est ouverte a TOUT role (``apps.notifications`` la sert
    sous ``IsAnyRole``), donc un « Commercial terrain » -- qui n'a aucun droit
    CRM -- la recoit normalement.
    """
    destinataire = visite.commercial
    if destinataire is None:
        return None
    if acteur is not None and getattr(acteur, 'id', None) == destinataire.id:
        return None
    quand = ('' if visite.date_prevue is None
             else f" du {visite.date_prevue.strftime('%d/%m/%Y')}")
    return _notifier_commercial_visite(
        visite, 'visite_terrain_assignee',
        'Visite technique assignee',
        f'La visite{quand} chez « {visite.lead} » vous est assignee.')


def notifier_valideurs_visite(visite, acteur=None):
    """VISITE-CADENCE — prévient ceux qui peuvent VALIDER qu'une visite attend.

    Jusqu'ici, ``terminer`` ne prévenait personne : le bureau d'études
    découvrait une visite finie en ouvrant sa liste, et une visite pouvait
    dormir des jours entre le retour du technicien et le feu vert — alors que
    le client, lui, attend une réponse.

    Destinataires : les porteurs du code ``visites_valider`` de la SOCIÉTÉ de
    la visite. Ils sont énumérés comme ailleurs dans le dépôt
    (``crm.services.pick_round_robin_owner``) : rôle fin portant le code, OU
    compte SANS rôle fin au palier responsable/admin (le repli historique de
    ``_user_has_or_legacy``). Le fan-out est donc borné au palier responsable —
    jamais « tous les utilisateurs actifs ».

    Ni l'ACTEUR (il vient de terminer la visite, il sait), ni un doublon :
    best-effort intégral — la visite est DÉJÀ terminée quand on arrive ici.
    """
    try:
        from django.contrib.auth import get_user_model
        from django.db.models import Q

        from apps.notifications.services import notify_many

        User = get_user_model()
        destinataires = (
            User.objects
            .filter(company=visite.company, is_active=True)
            .filter(Q(role__permissions__contains=['visites_valider'])
                    | Q(role__isnull=True,
                        role_legacy__in=['admin', 'responsable']))
            .distinct())
        if acteur is not None and getattr(acteur, 'id', None):
            destinataires = destinataires.exclude(pk=acteur.id)
        return notify_many(
            list(destinataires), 'visite_terrain_a_valider',
            'Visite technique à valider',
            body=(f'La visite chez « {visite.lead} » est terminée : elle '
                  "attend le feu vert du bureau d'études."),
            link=f'/visites/{visite.pk}', company=visite.company)
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        return []


def _commercial_nom(visite):
    """Le nom AFFICHABLE de l'assigné, composé ICI (jamais chez l'abonné).

    Le CRM reçoit une CHAÎNE : il n'a aucun utilisateur à aller relire, et la
    règle « aucun prénom codé en dur » reste tenue d'un seul côté. Visite non
    assignée → chaîne vide, et la phrase qui en dépend s'adapte."""
    commercial = visite.commercial
    if commercial is None:
        return ''
    return (commercial.get_full_name() or commercial.username or '')


def emettre_visite_planifiee(visite, user):
    """Publie ``visite_planifiee`` — la date prévue vient d'être posée/changée.

    Best-effort : la visite est DÉJÀ enregistrée quand on arrive ici ; un
    abonné CRM en échec ne doit pas défaire la planification. Sans date prévue,
    rien n'est émis — « planifiée » sans date ne veut rien dire.
    """
    from core.events import visite_planifiee

    from .models import VisiteTerrain

    if visite.date_prevue is None:
        return None
    try:
        visite_planifiee.send(
            sender=VisiteTerrain, visite=visite, lead_id=visite.lead_id,
            user=user, date_prevue=visite.date_prevue,
            commercial_nom=_commercial_nom(visite))
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        return None
    return visite


def emettre_visite_terminee(visite, user):
    """Publie ``visite_terminee`` avec le RETOUR TERRAIN pré-composé.

    Le récap de ``visite_validee`` ne porte que des MESURES : les remarques
    libres du technicien (« le tableau est saturé », « accès par le garage »)
    n'atteignaient donc jamais l'historique du lead. Elles voyagent ici, dans
    ``retour``, composées par le selector de cette app — source unique.

    ``qualification`` voyage À CÔTÉ du retour, pas dedans : ce n'est pas du
    texte de terrain mais une LECTURE COMMERCIALE à vocabulaire fermé, que le
    CRM rend en une phrase. ``None`` quand le terrain n'a rien saisi — jamais
    un dict de défauts qui ferait croire à une qualification faite.

    Best-effort : la visite est DÉJÀ terminée ; un abonné en échec ne doit
    jamais faire échouer le geste du terrain.
    """
    from core.events import visite_terminee

    from . import selectors
    from .models import VisiteTerrain

    try:
        visite_terminee.send(
            sender=VisiteTerrain, visite=visite, lead_id=visite.lead_id,
            user=user, retour=selectors.retour_visite(visite),
            qualification=visite.qualification)
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        return None
    return visite


def enregistrer_qualification(visite, valeurs):
    """VISITE-CADENCE — POSE la qualification de fin de visite.

    Renvoie ``(visite, erreurs)`` — même forme que ``enregistrer_mesures`` :
    ``erreurs`` est le dict ``{champ: [message FR]}`` servi tel quel en 400, et
    chaque message NOMME son champ. Le vocabulaire et la validation vivent dans
    ``visites.qualification`` (source unique) : cette fonction ne fait
    qu'ÉCRIRE le résultat.

    Last-write-wins, comme la saisie de mesures : la qualification POSE des
    valeurs, jamais un incrément — rejouer deux fois la même saisie donne
    exactement le même état.
    """
    from . import qualification as vocabulaire

    propre, erreurs = vocabulaire.valider(valeurs)
    if erreurs:
        return None, erreurs
    visite.qualification = propre
    visite.save(update_fields=['qualification'])
    marquer_en_cours(visite)
    return visite, {}


def visite_en_attente(lead):
    """SUIVI E5 — LE rendez-vous encore EN ATTENTE du lead : une visite au
    statut BROUILLON, jamais commencée (ni départ ni arrivée pointés), avec
    une date prévue — la plus récente. ``None`` s'il n'y en a aucune.

    La société est celle du LEAD (jamais d'un corps de requête)."""
    from .models import VisiteTerrain

    return (VisiteTerrain.objects
            .filter(company_id=lead.company_id, lead=lead,
                    statut=VisiteTerrain.Statut.BROUILLON,
                    en_route_le__isnull=True, arrivee_le__isnull=True,
                    date_prevue__isnull=False)
            .order_by('-date_prevue', '-id').first())


def gabarit_pour_lead(lead):
    """AGR412 (D-AGR-4) — le gabarit d'une visite d'après le TYPE du lead que
    le CRM passe (l'objet lead lui-même : aucun import de ``apps.crm``) :
    ``point_eau`` pour un lead agricole, ``ci`` (CIQ600, D-CIQ-5) pour un lead
    commercial ou industriel, ``toiture`` sinon."""
    from .models import VisiteTerrain

    type_lead = getattr(lead, 'type_installation', None) or ''
    if type_lead == 'agricole':
        return VisiteTerrain.Gabarit.POINT_EAU
    if type_lead in ('commercial', 'industriel'):
        return VisiteTerrain.Gabarit.CI
    return VisiteTerrain.Gabarit.TOITURE


def recaler_gabarit(visite):
    """AGR412 — recale le gabarit sur le type ACTUEL du lead tant que la
    visite est BROUILLON (rien n'a encore été saisi sur le terrain) ; jamais
    après. Mute ``visite`` sans l'enregistrer ; renvoie True si changé."""
    from .models import VisiteTerrain

    if visite.statut != VisiteTerrain.Statut.BROUILLON:
        return False
    cible = gabarit_pour_lead(visite.lead)
    if visite.gabarit == cible:
        return False
    visite.gabarit = cible
    return True


def _deplacer_visite(visite, user, date_prevue, commercial, notes):
    """SUIVI E5 — DÉPLACE le rendez-vous existant (jamais une seconde
    visite) : nouvelle date, nouvel assigné s'il est fourni, notes
    complétées (une ligne dit d'où la visite a été déplacée). L'assigné est
    prévenu quand l'assigné OU la date change (primitive VTA7 existante), et
    ``visite_planifiee`` est publié : le CRM recale confirmation et débrief."""
    ancienne_date = visite.date_prevue
    champs = []
    if recaler_gabarit(visite):
        champs.append('gabarit')
    if ancienne_date != date_prevue:
        visite.date_prevue = date_prevue
        champs.append('date_prevue')
    if commercial is not None and visite.commercial_id != commercial.pk:
        visite.commercial = commercial
        champs.append('commercial')
    lignes = []
    if 'date_prevue' in champs and ancienne_date is not None:
        lignes.append(f'Rendez-vous du {ancienne_date:%d/%m/%Y} déplacé au '
                      f'{date_prevue:%d/%m/%Y}.')
    if (notes or '').strip():
        lignes.append(notes.strip())
    if lignes:
        existantes = (visite.notes or '').strip()
        visite.notes = '\n'.join(([existantes] if existantes else []) + lignes)
        champs.append('notes')
    if champs:
        visite.save(update_fields=champs)
    if 'commercial' in champs or 'date_prevue' in champs:
        notifier_assignation(visite, acteur=user)
    emettre_visite_planifiee(visite, user)
    return visite


def annuler_rendez_vous(lead, user, motif=''):
    """SUIVI E4 (30/09/2026) — le client ne veut plus de la visite (ou le
    dossier s'arrête) : ses rendez-vous EN ATTENTE sont ANNULÉS.

    C'est la porte que le CRM appelle (frontière M3 : il n'importe jamais
    ``apps.visites.models``). Sont visées les visites du lead au statut
    BROUILLON, jamais commencées (ni départ ni arrivée pointés), à date prévue
    non passée. Pour chacune : ``date_prevue`` vidée, UNE ligne ajoutée aux
    notes (« Rendez-vous du JJ/MM/AAAA annulé à la demande du client. » — ou,
    avec un ``motif``, « Rendez-vous du JJ/MM/AAAA annulé — <motif>. »), et
    l'assigné prévenu par la primitive de notification EXISTANTE (clé
    ``visite_terrain_assignee`` : c'est le canal de SA journée ; aucun nouveau
    type d'événement — le registre est fermé). AUCUNE suppression de ligne —
    la visite reste consultable.

    Renvoie le nombre de rendez-vous annulés."""
    from core.dates import aujourd_hui_local

    from .models import VisiteTerrain

    visites = list(VisiteTerrain.objects.filter(
        company_id=lead.company_id, lead=lead,
        statut=VisiteTerrain.Statut.BROUILLON,
        en_route_le__isnull=True, arrivee_le__isnull=True,
        date_prevue__gte=aujourd_hui_local()))
    precision = (motif or '').strip().rstrip('.')
    for visite in visites:
        jour = f'{visite.date_prevue:%d/%m/%Y}'
        raison = (f'— {precision}.' if precision
                  else 'à la demande du client.')
        ligne = f'Rendez-vous du {jour} annulé {raison}'
        existantes = (visite.notes or '').strip()
        visite.notes = f'{existantes}\n{ligne}' if existantes else ligne
        visite.date_prevue = None
        visite.save(update_fields=['date_prevue', 'notes'])
        if visite.commercial_id is not None and (
                user is None
                or visite.commercial_id != getattr(user, 'id', None)):
            _notifier_commercial_visite(
                visite, 'visite_terrain_assignee',
                'Visite technique annulée',
                f'Le rendez-vous du {jour} chez « {visite.lead} » est '
                f'annulé {raison}')
    return len(visites)


def planifier_visite(lead, user, date_prevue, commercial=None, notes='',
                     replanifier=False):
    """VISITE-CADENCE — POSE un rendez-vous de visite technique sur un lead.

    C'est la porte que le CRM appelle depuis la fiche lead (frontière M3 : il
    n'importe jamais ``apps.visites.models``). Doctrine fondateur : la visite
    se place, selon le segment du lead (D-CIQ-5) : résidentiel, APRÈS l'envoi
    du devis, comme outil de closing ; site professionnel (commercial ou
    industriel), AVANT le devis final si le site est MT ou si tension,
    puissance souscrite ou toit restent inconnus après l'appel. Planifier est
    un GESTE COMMERCIAL, pas une opération d'administration du planning
    terrain. Le gabarit de la visite (``toiture`` / ``point_eau`` / ``ci``)
    suit le type du lead, recalculé tant que la visite est brouillon.

    Renvoie ``(visite, erreurs)`` — même forme que ``enregistrer_mesures`` :
    ``erreurs`` est le dict ``{champ: [messages FR]}`` servi tel quel en 400,
    et chaque message NOMME son champ (règle fondateur 08/09/2026).

    Deux gardes, et elles refusent AVANT d'écrire quoi que ce soit :

    * ``date_prevue`` est obligatoire et ne peut pas être dans le PASSÉ —
      « planifier » hier n'est pas un rendez-vous, c'est une saisie fautive
      (la date du jour reste acceptée : on planifie souvent pour l'après-midi) ;
    * ``commercial``, s'il est fourni, doit être un compte ACTIF de la MÊME
      société — sinon assigner une visite serait un moyen détourné de désigner
      l'utilisateur d'un autre locataire.

    La société vient du LEAD, jamais d'un corps de requête ; ``statut`` naît
    BROUILLON (le terrain le fera passer « en cours » à sa première
    contribution). L'assigné est prévenu par la primitive existante (VTA7) et
    l'événement ``visite_planifiee`` laisse le CRM recaler son suivi.

    SUIVI E5 (30/09/2026) — ``replanifier=True`` : « la visite est reportée
    à une autre date » DÉPLACE le rendez-vous en attente du lead
    (``visite_en_attente``) au lieu d'en créer un second ; mêmes gardes. S'il
    n'y en a aucun, la visite est créée comme d'habitude.
    """
    from django.utils import timezone

    from .models import VisiteTerrain

    erreurs = {}
    if date_prevue is None:
        erreurs['date_prevue'] = ['Date de visite obligatoire (AAAA-MM-JJ).']
    elif date_prevue < timezone.localdate():
        erreurs['date_prevue'] = [
            'La visite ne peut pas être planifiée dans le passé : choisir '
            "aujourd'hui ou une date à venir."]
    if commercial is not None:
        if (getattr(commercial, 'company_id', None) != lead.company_id
                or not getattr(commercial, 'is_active', False)):
            erreurs['commercial'] = [
                'Ce commercial n’appartient pas à votre société (ou son '
                'compte est désactivé).']
    if erreurs:
        return None, erreurs

    if replanifier:
        en_attente = visite_en_attente(lead)
        if en_attente is not None:
            return (_deplacer_visite(en_attente, user, date_prevue,
                                     commercial, notes), {})

    visite = VisiteTerrain.objects.create(
        company=lead.company, lead=lead, commercial=commercial,
        statut=VisiteTerrain.Statut.BROUILLON, date_prevue=date_prevue,
        notes=(notes or '').strip(), gabarit=gabarit_pour_lead(lead))
    # PAS de ``journaliser_visite(..., 'creation')`` ici : l'abonné CRM de
    # ``visite_planifiee`` pose une note qui dit TOUT (la date ET l'assigné).
    # Les deux ensemble empileraient « Visite technique créée. » juste
    # au-dessus de « Visite technique planifiée le … » — deux lignes pour un
    # seul geste dans un historique qu'un humain doit pouvoir lire.
    notifier_assignation(visite, acteur=user)
    emettre_visite_planifiee(visite, user)
    return visite, {}


def journaliser_visite(visite, user, moment, detail=''):
    """Pose la note de chatter du ``moment`` sur le LEAD de la visite.

    Le chatter d'un lead (``crm.LeadActivity``) est le journal COMMUN de tout
    ce qui lui arrive : la visite y écrit ses moments plutôt que d'ouvrir un
    second historique (la dette des 13 chatters hand-rollés). L'écriture
    appartient donc au CRM et passe par SON ``services.py`` (frontière M3,
    import paresseux) ; cette app n'importe jamais ``apps.crm.models``.

    Best-effort côté CRM : un chatter indisponible ne fait jamais échouer la
    transition métier qui vient d'aboutir.
    """
    from apps.crm import services as crm_services

    return crm_services.journaliser_visite(visite, user, moment, detail=detail)


# ── ALEA6 — LA TABLE DES TRANSITIONS DE STATUT (appliquée par le SERVEUR) ────
#
# Avant ALEA6, seul le bouton de l'écran bureau d'études empêchait de valider
# un brouillon vide : un POST direct sur ``valider`` posait le feu vert sur 20
# éléments manquants. UNE table dit, pour chaque geste de transition, depuis
# quels statuts il est permis ; toute autre paire est refusée en NOMMANT
# ``statut``. ``terminer`` garde sa propre porte (complétude + idempotence).

#: Statuts de DÉPART autorisés, par action de transition.
TRANSITIONS = {
    'valider': frozenset({'terminee'}),
    'renvoyer': frozenset({'validee', 'terminee'}),
}

#: Le message (FR) qui explique un refus de statut, par action.
MESSAGES_TRANSITION = {
    'valider': 'La visite doit être terminée avant validation.',
    'renvoyer': ('Seule une visite terminée ou validée peut être renvoyée '
                 'au commercial.'),
}


def _corps_refus_statut(message):
    """Le corps 400 qui NOMME ``statut`` — liste DRF + forme maison."""
    return {'statut': [message], 'erreurs': {'statut': message}}


def refus_transition(visite, action):
    """ALEA6 — ``None`` si ``action`` est permise sur ``visite``, sinon le
    CORPS de la réponse 400 :

    * statut de départ hors ``TRANSITIONS`` → ``{'statut': [message]}``
      (doublé de la forme maison ``{'erreurs': {'statut': message}}``) ;
    * ``valider`` d'une visite terminée mais redevenue incomplète (photo
      retirée après « terminer ») → ``{'manquants': [...]}``, la liste exacte
      de ``visite_terrain_manquants`` — le feu vert ne se donne jamais sur un
      dossier incomplet.

    Une action absente de la table n'est pas une transition gérée ici
    (``None``) : la table ne s'applique qu'aux gestes qu'elle déclare.
    """
    permis = TRANSITIONS.get(action)
    if permis is None:
        return None
    if visite.statut not in permis:
        message = MESSAGES_TRANSITION[action]
        if action == 'valider' and visite.statut == 'validee':
            message = 'Cette visite est déjà validée.'
        return _corps_refus_statut(message)
    if action == 'valider':
        from . import selectors

        manquants = selectors.visite_terrain_manquants(visite)
        if manquants:
            return {
                'manquants': manquants,
                'message': (
                    'La visite ne peut pas être validée : '
                    f'{len(manquants)} élément(s) manquent encore.'),
            }
    return None


def valider_visite(visite, user):
    """Feu vert calepinage : la visite passe VALIDÉE et devient lecture seule.

    VTA5 — le retour vers le lead se fait par ÉVÉNEMENT (``visite_validee``,
    bus ``core.events``), plus par un appel direct : c'est ``apps.crm`` qui
    décide, dans SON ``receivers.py``, ce qu'il inscrit sur la fiche. Le récap
    est PRÉ-CALCULÉ ici (le selector de cette app en est la source de vérité)
    et le ``lead_id`` voyage en ENTIER — l'app visites ne fait plus aucun écrit
    sur ``crm.Lead``.
    """
    from core.events import visite_validee

    from . import selectors
    from .models import VisiteTerrain

    from django.utils import timezone

    # CIQ604 — date et auteur du feu vert, posés SERVEUR (jamais lus d'un
    # corps de requête) : « vérifié par visite le … » a une date honnête.
    visite.statut = VisiteTerrain.Statut.VALIDEE
    visite.validee_le = timezone.now()
    visite.validee_par = (user if getattr(user, 'pk', None) is not None
                          else None)
    visite.save(update_fields=['statut', 'validee_le', 'validee_par'])
    # AGR413 — les mesures du point d'eau voyagent avec l'événement (vides
    # pour une visite toiture) : c'est le CRM qui décide de les recopier.
    # CIQ607 — le relevé C&I voyage aussi (vide hors gabarit ``ci``) : le
    # CRM décide de recopier la mesure sur les colonnes du lead.
    releve_ci = (selectors.releve_ci_de_visite(visite)
                 if visite.gabarit == VisiteTerrain.Gabarit.CI else {})
    visite_validee.send(
        sender=VisiteTerrain, visite=visite, lead_id=visite.lead_id,
        user=user, recap=selectors.recap_visite_terrain(visite),
        mesures_point_eau=selectors.mesures_point_eau_pour_lead(visite),
        releve_ci=releve_ci)
    _notifier_commercial_visite(
        visite, 'visite_terrain_validee',
        'Visite technique validée',
        f'La visite du lead « {visite.lead} » a reçu le feu vert du bureau '
        "d'études.")
    return visite


def renvoyer_visite(visite, user, *, photos=None, mesures=None, motif=''):
    """Renvoie la visite au commercial avec le détail EXACT de ce qu'il refaire.

    ``photos`` — ids de ``VisiteMedia`` à reprendre ; ``mesures`` — liste de
    ``{'categorie': ..., 'code': ...}`` à re-relever. Le ``motif`` est
    obligatoire (validé côté sérialiseur) et il est recopié sur CHAQUE élément
    marqué, pour que la tuile porte elle-même son explication.

    Renvoie un message d'erreur FR si un id de photo ne correspond à rien sur
    cette visite (l'erreur NOMME ce qui cloche), sinon ``''``.
    """
    from . import visite_checklist as checklist
    from .models import VisiteTerrain

    ids = [int(pk) for pk in (photos or [])]
    medias = list(visite.medias.filter(pk__in=ids)) if ids else []
    if len(medias) != len(set(ids)):
        connus = sorted(str(media.pk) for media in medias)
        return ('Une ou plusieurs photos demandées n’appartiennent pas à cette '
                'visite. Photos reconnues : '
                + (', '.join(connus) if connus else 'aucune') + '.')

    for media in medias:
        media.a_refaire = True
        media.motif_refaire = motif
        media.save(update_fields=['a_refaire', 'motif_refaire'])

    # Une mesure « à refaire » est une mesure à RE-RELEVER : on la vide, donc
    # la complétude serveur la redemande d'elle-même — aucun second registre
    # d'état à tenir synchrone.
    from . import selectors

    contexte = selectors.contexte_checklist(visite)
    stockees = dict(visite.mesures if isinstance(visite.mesures, dict) else {})
    touchee = False
    for demande in (mesures or []):
        categorie = (demande or {}).get('categorie')
        code = (demande or {}).get('code')
        if checklist.mesure(categorie, code, visite.gabarit,
                            **contexte) is None:
            continue
        bloc = dict(stockees.get(categorie) or {})
        if code in bloc:
            bloc[code] = None
            stockees[categorie] = bloc
            touchee = True
    if touchee:
        visite.mesures = stockees

    visite.statut = VisiteTerrain.Statut.A_REFAIRE
    champs = ['statut', 'mesures'] if touchee else ['statut']
    if visite.validee_le is not None or visite.validee_par_id is not None:
        # CIQ604 — un feu vert retiré n'a plus de date : elle ne survit pas à
        # la réouverture (le prochain feu vert en posera une nouvelle).
        visite.validee_le = None
        visite.validee_par = None
        champs += ['validee_le', 'validee_par']
    visite.save(update_fields=champs)
    journaliser_visite(visite, user, 'a_refaire', detail=f'Motif : {motif}')
    _notifier_commercial_visite(
        visite, 'visite_terrain_a_refaire',
        'Visite technique à refaire',
        f'La visite du lead « {visite.lead} » revient à refaire. '
        f'Motif : {motif}')
    return ''


# ── VTA10 — LA SAISIE DES MESURES, UNE SEULE FOIS ────────────────────────────
#
# La validation ET l'écriture des mesures vivent ICI, pas dans la vue : le même
# geste arrive par DEUX portes — le PATCH en ligne
# (``/visites/visites/<id>/mesures/``) et le REJEU hors-ligne du moteur
# ``apps.offlinesync`` (op ``visite.mesures``). Deux copies de ces règles
# seraient deux vérités : la vue et le handler appellent la même fonction.
#
# L'écriture est « last-write-wins » (elle POSE des valeurs, jamais un
# incrément) : rejouer deux fois la même opération donne exactement le même
# état — c'est ce que le moteur hors-ligne exige de tout handler.

def valeur_liste(declaration, brute):
    """CIQ600 — valide une mesure ``LISTE`` (liste d'objets dont les champs
    sont ceux de ``declaration['forme']``). Renvoie ``(elements, message)`` :
    chaque élément porte TOUS les champs de la forme (``None`` si non saisi),
    un champ inconnu est refusé en le nommant, et la valeur d'un champ passe
    par ``valeur_mesure`` (nature, positivité)."""
    if not isinstance(brute, list):
        return None, (f"« {declaration['libelle']} » attend une liste "
                      "d'éléments.")
    prefixe = declaration.get('id_prefixe')
    propres = []
    ids = set()
    for index, element in enumerate(brute, start=1):
        propre, message = _valeur_objet(
            declaration['forme'], element,
            f"« {declaration['libelle']} » (élément {index})")
        if message:
            return None, message
        if prefixe:
            ident = str(element.get('id') or '').strip() or f'{prefixe}{index}'
            if ident in ids:
                return None, (f"« {declaration['libelle']} » : identifiant "
                              f'« {ident} » en double.')
            ids.add(ident)
            propre = dict({'id': ident}, **propre)
        # Une couverture fibrociment pose TOUJOURS le drapeau amiante
        # (précaution — le technicien ne peut pas l'oublier ni l'effacer).
        if propre.get('couverture') == 'fibrociment' and 'fibrociment' in propre:
            propre['fibrociment'] = True
        propres.append(propre)
    return propres, None


def _valeur_objet(forme, brute, contexte):
    """Valide UN objet de ``forme`` (liste de déclarations) : renvoie
    ``(objet complet, message)`` ; tous les champs de la forme sortent
    (``None`` si non saisis) et un champ inconnu est refusé en le nommant."""
    if not isinstance(brute, dict):
        return None, f'{contexte} doit être un objet.'
    formes = {sous['code']: sous for sous in forme}
    propre = {}
    for code, sous in formes.items():
        valeur, message = valeur_mesure(sous, brute.get(code))
        if message:
            return None, f'{contexte} : {message}'
        propre[code] = valeur
    inconnus = [c for c in brute if c not in formes and c != 'id']
    if inconnus:
        return None, f'{contexte} : champ inconnu « {inconnus[0]} ».'
    return propre, None


def valeur_non_releves(connus, brute):
    """CIQ601 — valide ``_non_releves`` = ``{clé: motif}``. Renvoie
    ``(etats, erreurs)``. Chaque clé désigne une mesure de la catégorie
    (``calibre_a``) ou un champ d'une liste (``trajets.longueur_dc_m``,
    ``zones_toiture[z1].charge_admissible_declaree_kg_m2``) ; le motif est à
    VOCABULAIRE FERMÉ. Chaque message NOMME le champ fautif."""
    from . import visite_checklist as checklist

    cle_erreur = checklist.CLE_NON_RELEVES
    if not isinstance(brute, dict):
        return None, {cle_erreur: ('« Non relevé » attend un objet '
                                   '{mesure: motif}.')}
    etats = {}
    erreurs = {}
    for cle, motif in brute.items():
        libelle = checklist.libelle_cle_non_releve(connus, cle)
        if libelle is None:
            erreurs[f'{cle_erreur}.{cle}'] = (
                f'Champ inconnu « {cle} » : on ne peut pas le déclarer non '
                'relevé.')
            continue
        motif = (motif or '').strip() if isinstance(motif, str) else ''
        if not motif:
            erreurs[f'{cle_erreur}.{cle}'] = f'Motif requis pour {libelle}.'
        elif motif not in checklist.MOTIFS_NON_RELEVE:
            erreurs[f'{cle_erreur}.{cle}'] = (
                f'Motif « {motif} » inconnu pour {libelle}. Choix possibles : '
                + ', '.join(checklist.MOTIFS_NON_RELEVE) + '.')
        else:
            etats[cle] = motif
    return etats, erreurs


def valeur_mesure(declaration, brute):
    """Convertit/valide UNE valeur de mesure. Renvoie ``(valeur, message)``.

    ``message`` NOMME le champ fautif en français (règle maison) ; il vaut
    ``None`` quand la valeur est acceptée. Aucun SEUIL technique n'est jugé
    ici : on vérifie la NATURE d'une mesure, jamais si elle est « suffisante ».
    """
    from decimal import Decimal, InvalidOperation

    from . import visite_checklist as checklist

    if brute is None or brute == '':
        return None, None
    nature = declaration['nature']
    if nature == checklist.LISTE:
        return valeur_liste(declaration, brute)
    if nature == checklist.OBJET:
        return _valeur_objet(declaration['forme'], brute,
                             f"« {declaration['libelle']} »")
    if nature == checklist.ENTIER:
        try:
            nombre = Decimal(str(brute))
        except (InvalidOperation, ValueError, TypeError):
            nombre = None
        if nombre is None or nombre != nombre.to_integral_value():
            return None, (f"« {declaration['libelle']} » attend un entier "
                          f'(reçu : {brute!r}).')
        if nombre < 0:
            return None, (f"« {declaration['libelle']} » ne peut pas être "
                          'négatif.')
        return int(nombre), None
    if nature == checklist.DATE:
        import datetime

        try:
            jour = datetime.date.fromisoformat(str(brute).strip())
        except ValueError:
            return None, (f"« {declaration['libelle']} » attend une date "
                          f'AAAA-MM-JJ (reçu : {brute!r}).')
        return jour.isoformat(), None
    if nature == checklist.PIECE:
        # Référence d'une pièce jointe (identifiant) ou texte libre.
        if isinstance(brute, bool) or not isinstance(brute, (int, str)):
            return None, (f"« {declaration['libelle']} » attend une pièce "
                          'jointe (identifiant) ou une référence.')
        return brute, None
    if nature == checklist.NOMBRE:
        try:
            nombre = Decimal(str(brute))
        except (InvalidOperation, ValueError, TypeError):
            return None, (f"« {declaration['libelle']} » attend un nombre "
                          f'(reçu : {brute!r}).')
        if nombre < 0:
            return None, (f"« {declaration['libelle']} » ne peut pas être "
                          'négatif.')
        return float(nombre), None
    if nature == checklist.BOOLEEN:
        if isinstance(brute, bool):
            return brute, None
        texte = str(brute).strip().lower()
        if texte in ('true', '1', 'oui'):
            return True, None
        if texte in ('false', '0', 'non'):
            return False, None
        return None, f"« {declaration['libelle']} » attend oui ou non."
    if nature == checklist.CHOIX:
        texte = str(brute).strip()
        # ERR-QAH-VISITES-COUVERTURE-ENUM-SANS-AFFORDANCE — un code interne
        # déjà exact passe direct ; sinon on normalise (« Tuile » → tuile,
        # « Bon état » → bon…) avant de refuser.
        if texte in declaration['choix']:
            return texte, None
        candidat = normaliser_choix(texte, declaration['choix'])
        if candidat is not None:
            return candidat, None
        options = ', '.join(declaration['choix'])
        return None, (f"« {declaration['libelle']} » : valeur inconnue "
                      f'« {texte} ». Choix possibles : {options}.')
    return str(brute), None


def marquer_en_cours(visite):
    """Un brouillon (ou une visite à refaire) devient « en cours ».

    Déclenché par la première contribution réelle du terrain — photo, mesure
    ou pointage d'arrivée.
    """
    from .models import VisiteTerrain

    if visite.statut in (VisiteTerrain.Statut.BROUILLON,
                         VisiteTerrain.Statut.A_REFAIRE):
        visite.statut = VisiteTerrain.Statut.EN_COURS
        visite.save(update_fields=['statut'])
    return visite


def enregistrer_mesures(visite, categorie, valeurs):
    """POSE les mesures d'UNE catégorie. Renvoie ``(visite, erreurs)``.

    ``erreurs`` est le dict ``{champ: message FR}`` servi tel quel en 400 par
    la vue — chaque message NOMME son champ. Rien n'est écrit dès qu'une seule
    valeur est refusée : la catégorie part entière ou pas du tout.
    """
    from . import visite_checklist as checklist

    from . import selectors

    declaration = checklist.categorie(
        categorie, visite.gabarit, **selectors.contexte_checklist(visite))
    if declaration is None or not declaration['mesures']:
        return None, {'categorie': ('Catégorie de mesures inconnue '
                                    f'« {categorie} ».')}
    if not isinstance(valeurs, dict):
        return None, {'valeurs': ('Les valeurs doivent être un objet '
                                  '{champ: valeur}.')}

    connus = {champ['code']: champ for champ in declaration['mesures']}
    erreurs = {}
    propres = {}
    non_releves = None
    for code, brute in valeurs.items():
        if code == checklist.CLE_NON_RELEVES:
            # CIQ601 — « non relevé + motif » : gabarit ``ci`` seulement.
            if visite.gabarit != checklist.GABARIT_CI:
                erreurs[code] = ('« Non relevé » n’existe que pour une '
                                 'visite de site professionnel.')
            else:
                non_releves, messages = valeur_non_releves(connus, brute)
                erreurs.update(messages)
            continue
        champ = connus.get(code)
        if champ is None:
            erreurs[code] = (f'Champ inconnu dans la catégorie '
                             f'« {declaration["libelle"]} ».')
            continue
        valeur, message = valeur_mesure(champ, brute)
        if message:
            erreurs[code] = message
        else:
            propres[code] = valeur
    stockees = visite.mesures if isinstance(visite.mesures, dict) else {}
    bloc = dict(stockees.get(categorie) or {})
    bloc.update(propres)
    # CIQ660 — une mesure ``requis_si`` (un cos φ exige sa source) est refusée
    # en NOMMANT le champ quand l'autre est saisi sans elle.
    for champ in declaration['mesures']:
        lie = champ.get('requis_si')
        if (lie and champ['code'] not in erreurs
                and bloc.get(lie) not in (None, '')
                and bloc.get(champ['code']) in (None, '')):
            erreurs[champ['code']] = (
                f"« {champ['libelle']} » est obligatoire dès que "
                f"« {connus[lie]['libelle']} » est saisi.")
    if erreurs:
        return None, erreurs

    if visite.gabarit == checklist.GABARIT_CI:
        etats = dict(bloc.get(checklist.CLE_NON_RELEVES) or {})
        # Saisir ensuite une valeur EFFACE l'état « non relevé ».
        for cle in list(etats):
            if checklist.etat_obsolete(cle, propres):
                del etats[cle]
        etats.update(non_releves or {})
        if etats:
            bloc[checklist.CLE_NON_RELEVES] = etats
        else:
            bloc.pop(checklist.CLE_NON_RELEVES, None)
    stockees = dict(stockees)
    stockees[categorie] = bloc
    visite.mesures = stockees
    visite.save(update_fields=['mesures'])
    marquer_en_cours(visite)
    return visite, {}


def appliquer_mesures_hors_ligne(company, user, visite_id, categorie, valeurs):
    """Rejeu HORS-LIGNE de la saisie de mesures — ``(resultat, motif)``.

    C'est la porte d'entrée que ``apps.offlinesync`` appelle (jamais les
    modèles de cette app). Elle refait, dans l'ordre, TOUTES les gardes de la
    route en ligne — sinon la file hors-ligne serait un contournement de
    permission :

    1. la SOCIÉTÉ : la visite est cherchée bornée ``company`` (posée serveur),
       donc l'id d'un autre locataire est indiscernable d'un id inconnu ;
    2. la portée dure « mes visites » (VTA6) : sans ``visites_valider``, on ne
       peut écrire que sur SA visite ;
    3. le gel VT3 : une visite validée reste en lecture seule.

    ``motif`` est un message FR prêt à afficher, ``None`` en cas de succès.
    """
    from core.permissions import _user_has_or_legacy

    from .models import VisiteTerrain

    visite = (VisiteTerrain.objects
              .filter(company=company, pk=visite_id).first())
    if visite is None:
        return None, 'Visite inconnue.'
    if (visite.commercial_id != getattr(user, 'id', None)
            and not _user_has_or_legacy(user, 'visites_valider')):
        return None, ('Cette visite est assignée à un autre commercial : '
                      'vous ne pouvez pas saisir ses mesures.')
    if not visite.modifiable:
        return None, visite.raison_lecture_seule

    visite, erreurs = enregistrer_mesures(visite, categorie, valeurs)
    if erreurs:
        return None, ' '.join(str(message) for message in erreurs.values())
    return {'visite': visite.id, 'categorie': categorie,
            'mesures': visite.mesures.get(categorie, {})}, None
