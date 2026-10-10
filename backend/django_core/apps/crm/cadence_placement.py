"""Placement des leads existants dans le plan de relance (SPL21, extrait de crm/services.py : déplacement pur).

Module de type (a) de la scission : il n'importe ni ``.services`` ni un
module racine ; ``services`` réexporte ce qu'il faut (façade).
"""
import datetime
import logging

from django.utils import timezone

from . import stages
from .cadence_plan import (
    CadenceActiveConflit,
    _q_plan_ouvert,
    _recaler_file,
    calculer_echeances_cadence,
    initialiser_plan_relance,
    sync_relance_activity,
)
from .cadence_reperes import _CLOTURE_TAGS
from .fiche_funnel import avancer_stage_lead_vers, poser_tag_lead
from .models import Lead, LeadActivity, RelanceEtape

logger = logging.getLogger(__name__)


#: Au-delà de ce silence, un dossier n'est plus « en cours » : lui envoyer la
#: touche J+1 d'une cadence positionnée serait un message hors sujet. Il part
#: en dormance (réveil), pas en relance.
PLACEMENT_FENETRE_JOURS = 14

#: Réveils démarrés par JOUR OUVRÉ. Lancer 200 réveils le même matin
#: saturerait la journée de Meryem et ferait partir 200 messages en rafale
#: depuis le même numéro — le meilleur moyen de se faire signaler comme spam.
PLACEMENT_REVEILS_PAR_JOUR = 8

#: Les huit créneaux du matin, 20 minutes d'écart (10 h 00 → 12 h 20). Chacun
#: passe ensuite par `horaires.prochain_creneau_appel` au canal `whatsapp`
#: (une cadence de réveil s'ouvre par un message) : un créneau hors fenêtre
#: est recalé, jamais gardé tel quel. La pause du vendredi ne le concerne pas
#: — elle ne vaut que pour les appels (07/09/2026).
PLACEMENT_CRENEAUX = tuple(
    datetime.time(10 + (rang * 20) // 60, (rang * 20) % 60)
    for rang in range(PLACEMENT_REVEILS_PAR_JOUR))

#: Délai (jours) de la PREMIÈRE touche de réveil, quand la société n'a pas
#: encore de gabarit `reveil` en base. Le créneau étalé est la date visée pour
#: cette première touche : `depart = créneau − ce délai`.
PLACEMENT_REVEIL_DELAI_JOURS = 30

#: MRY30 — l'étiquette du dormant JAMAIS CHIFFRÉ. Le pendant « Devis sans
#: suite » existe déjà (`_CLOTURE_TAGS['apres_devis']`) : on le RÉUTILISE
#: plutôt que d'écrire un second libellé qui divergerait.
_PLACEMENT_TAG_JAMAIS_CHIFFRE = 'Jamais chiffré'

#: MRY30 — pour un dormant « devis sans suite », les deux touches de réveil
#: DOIVENT parler d'une proposition reçue (A1 puis A3) : ces leads ont bien
#: reçu un devis — dans Odoo — même sans devis ERP, et
#: `_adapter_gabarits_reveil` (qui ne lit que les devis ERP) choisirait
#: sinon le message « jamais chiffré », faux pour eux.
_PLACEMENT_CLES_REVEIL_DEVIS = ('reveil_a1', 'reveil_a3')

#: MRY30 — marque de la note chatter. Elle NOMME la décision fondateur du
#: 06/09/2026 qui a créé ce placement ; ce n'est pas la date d'exécution (déjà
#: portée par l'horodatage de l'activité) — un texte fixe, donc lisible et
#: vérifiable à l'identique quel que soit le jour du passage.
PLACEMENT_MARQUEUR = 'moteur, 06/09/2026'

#: Les cinq décisions possibles, DANS L'ORDRE du contrat
#: `contract_samples/placement_anciens_leads.json` : (code, libellé, cadence).
PLACEMENT_DECISIONS = (
    ('contact_complete',
     "Contact — depuis la première touche (Message d'identité)", 'contact'),
    ('contact_positionne',
     "Contact — positionné selon l'ancienneté, touches passées sautées",
     'contact'),
    ('apres_devis_positionne',
     'Après devis — positionné depuis l\'envoi, touches passées sautées',
     'apres_devis'),
    ('dormant_devis',
     'Dormant — Froid, tag « Devis sans suite », réveil étalé', 'reveil'),
    ('dormant_jamais_chiffre',
     'Dormant — Froid, tag « Jamais chiffré », réveil étalé', 'reveil'),
)

_PLACEMENT_CADENCES = {code: cadence for code, _, cadence in PLACEMENT_DECISIONS}

#: Le code de dormance de CHAQUE famille : c'est le repli d'une cadence
#: positionnée dont TOUTES les touches sont déjà passées (rien à faire demain
#: = un dossier dormant, pas une cadence vide).
_PLACEMENT_REPLI_DORMANT = {
    'contact_positionne': 'dormant_jamais_chiffre',
    'apres_devis_positionne': 'dormant_devis',
}

#: L'étiquette posée par chaque code de dormance.
_PLACEMENT_TAGS = {
    'dormant_devis': _CLOTURE_TAGS['apres_devis'],
    'dormant_jamais_chiffre': _PLACEMENT_TAG_JAMAIS_CHIFFRE,
}

#: Note portée par une touche déjà échue au moment du placement. La REJOUER
#: enverrait aujourd'hui le message du J+1 d'il y a dix jours.
PLACEMENT_NOTE_PASSEE = 'passée avant le moteur'

#: Leads placés PAR APPEL d'application. 277 dossiers d'un trait, c'est
#: plusieurs milliers d'écritures dans une seule requête HTTP — au-delà du
#: délai du navigateur (20 s côté axios), donc un 499 et un placement dont
#: personne ne sait ce qu'il a fait. L'écran rappelle jusqu'à `restants == 0`.
PLACEMENT_LOT_DEFAUT = 40

#: Borne haute de `limite` : au-delà, on retombe dans le cas qui a produit le
#: 499. Ce n'est pas un réglage de confort, c'est la garde.
PLACEMENT_LOT_MAX = 200

#: Lignes détaillées du rapport. Ce sont les SEULES à être datées : calculer
#: l'échéance des 270 autres coûterait le prix qu'on vient justement de
#: supprimer, pour un écran qui n'en montre que vingt.
PLACEMENT_APERCU_MAX = 20


#: ACRM47/ACRM61 — message de la réponse 503 ``{detail}`` (contrat
#: ``placement_anciens_leads.json``, ``exemple_erreur``).
PLACEMENT_DEVIS_ILLISIBLES = (
    "Lecture des devis acceptés indisponible : placement suspendu, rien "
    "n'a été appliqué")


class PlacementImpossible(Exception):
    """Un lead retenu n'a finalement pas pu être placé (cadence vide, gabarit
    absent…). Comptée dans ``erreurs`` du rapport, jamais propagée : le
    placement est best-effort LEAD PAR LEAD — un dossier bancal n'empêche
    jamais les 276 autres d'être traités."""


def _placement_moment(valeur):
    """Normalise une ancre en datetime AWARE (une ``date`` comparée à un
    datetime lèverait ``TypeError`` au premier lead)."""
    from . import horaires

    if valeur is None:
        return None
    if not isinstance(valeur, datetime.datetime):
        return datetime.datetime.combine(
            valeur, datetime.time(0, 0), tzinfo=horaires.CASABLANCA)
    if timezone.is_naive(valeur):
        return timezone.make_aware(valeur, datetime.timezone.utc)
    return valeur


def _placement_derniers_par_lead(qs):
    """``{lead_id: created_at}`` du plus récent de chaque lead — UNE requête."""
    from django.db.models import Max
    return {
        ligne['lead_id']: ligne['dernier']
        for ligne in qs.values('lead_id').annotate(dernier=Max('created_at'))
    }


def _placement_devis_du_lot(company, lead_ids):
    """Les deux lectures cross-app du placement, via ``ventes.selectors``
    (jamais ``ventes.models`` — frontière M3) : les leads à devis ACCEPTÉ (à
    écarter) et le dernier devis ENVOYÉ de chacun (qui date la cadence).

    ACRM47 — échoue FERMÉ : si ``ventes`` est illisible, la garde « devis
    accepté » ne peut plus écarter les signés — continuer enverrait au Froid
    un client qui a dit oui. ``PlacementImpossible`` (message français) est
    levée AVANT toute écriture : la vue répond 503 ``{detail}``, la commande
    sort en erreur, rien n'est appliqué."""
    try:
        from apps.ventes.selectors import (
            dernier_devis_envoye_par_lead, leads_avec_devis_accepte)
        return (leads_avec_devis_accepte(company, lead_ids),
                dernier_devis_envoye_par_lead(company, lead_ids))
    except Exception as exc:  # noqa: BLE001 — journalisé puis échec fermé
        logger.warning(
            'MRY30: devis illisibles (société %s)',
            getattr(company, 'pk', '?'), exc_info=True)
        raise PlacementImpossible(PLACEMENT_DEVIS_ILLISIBLES) from exc


def _decider_placements(company, maintenant, gabarits=None,
                        leads_en_portee=None):
    """Phase de DÉCISION : QUI est candidat, QUI est écarté, QUELLE décision
    s'applique à chacun — et, pour les cadences positionnées, s'il leur reste
    seulement une touche à faire (sinon elles basculent en dormance ici même,
    cf. ``_trancher_cadence_positionnee``).

    N'écrit AUCUNE donnée métier — pas une touche, pas une étiquette, pas un
    changement d'étape. Seule exception, pré-existante et assumée :
    ``CadenceRelanceEtape.cadence_pour`` seede le GABARIT d'une société qui
    n'en a pas encore (un référentiel de paramètres, jamais un dossier).

    Renvoie ``(decisions, ignores, total_candidats)``. Chaque décision est un
    dictionnaire de travail que l'étalement puis l'exécution complètent
    (``creneau``…) — jamais un modèle enregistré."""
    gabarits = gabarits or _placement_gabarits(company)
    base = Lead.objects.filter(
        company=company, is_archived=False, perdu=False,
        ne_plus_contacter=False,
    ).exclude(stage__in=[stages.COLD, stages.SIGNED])
    # ALEA25 — appelé depuis l'API, le placement est BORNÉ par la portée de
    # l'utilisateur (``LeadViewSet._leads_en_portee``) : un Commercial ne
    # voit ni ne place les leads d'un collègue hors équipe. ``None`` (la
    # commande de gestion) = toute la société, comme avant.
    if leads_en_portee is not None:
        base = base.filter(pk__in=leads_en_portee.values('pk'))
    candidats = list(base.order_by('pk'))
    total = len(candidats)
    # ACRM61/ACRM20 — ``rappel_manuel_a_venir`` : entier, jamais null.
    ignores = {'deja_en_cadence': 0, 'devis_accepte_non_signe': 0,
               'rappel_manuel_a_venir': 0}
    if not candidats:
        return [], ignores, total
    # ACRM20 — date LOCALE du jour (Africa/Casablanca) du moment de décision.
    aujourdhui = timezone.localtime(maintenant).date()

    ids = [lead.pk for lead in candidats]
    # Le moteur TIENT déjà ces dossiers : une seconde cadence dessus, ce sont
    # deux séries de messages parallèles à la même personne.
    # ACRM46 — seul un plan OUVERT (touche À FAIRE, prédicat partagé avec
    # ``initialiser_plan_relance``) tient le lead : des touches toutes closes
    # (faites/sautées/annulées) le rendent candidat au placement.
    deja = set(RelanceEtape.objects.filter(
        _q_plan_ouvert(), company=company, lead_id__in=ids)
        .values_list('lead_id', flat=True))
    acceptes, envoyes = _placement_devis_du_lot(company, ids)

    humaines = _placement_derniers_par_lead(
        LeadActivity.objects.filter(lead_id__in=ids, user__isnull=False)
        .exclude(kind__in=[LeadActivity.Kind.CREATION,
                           LeadActivity.Kind.MODIFICATION]))
    etapes_stage = _placement_derniers_par_lead(
        LeadActivity.objects.filter(lead_id__in=ids, field='stage'))

    decisions = []
    for lead in candidats:
        if lead.pk in deja:
            ignores['deja_en_cadence'] += 1
            continue
        if lead.pk in acceptes:
            # Un devis accepté attend un passage en Signé À LA MAIN, pas une
            # relance : demander « alors, ce devis ? » à quelqu'un qui a dit
            # oui est le pire message du portefeuille.
            ignores['devis_accepte_non_signe'] += 1
            continue
        if lead.relance_date is not None and lead.relance_date >= aujourdhui:
            # ACRM20 — un rappel MANUEL à venir (posé par la commerciale) tient
            # le lead hors dormance : jamais de Froid, d'étiquette ni de
            # Réveil, et sa ``relance_date`` n'est jamais remplacée.
            ignores['rappel_manuel_a_venir'] += 1
            continue
        devis = envoyes.get(lead.pk)
        # L'ANCRE : le dernier signe de vie du dossier, quelle qu'en soit la
        # nature. La seule date de création ferait passer pour dormant un lead
        # rappelé hier ; la seule dernière activité raterait un devis parti
        # sans qu'on note rien.
        ancre = _placement_moment(lead.date_creation)
        for candidate in (humaines.get(lead.pk), etapes_stage.get(lead.pk),
                          getattr(devis, 'date_envoi', None)):
            candidate = _placement_moment(candidate)
            if candidate is not None and (ancre is None or candidate > ancre):
                ancre = candidate
        ancre = ancre or maintenant
        jours = (maintenant - ancre).days
        recent = jours <= PLACEMENT_FENETRE_JOURS

        if devis is not None:
            # Un devis ERP ENVOYÉ date la cadence, quel que soit son âge : le
            # suivi part de l'envoi RÉEL et les touches déjà passées seront
            # sautées. S'il n'en reste aucune, le repli dormant s'en charge.
            code, depart = 'apres_devis_positionne', devis.date_envoi
        elif lead.stage in (stages.QUOTE_SENT, stages.FOLLOW_UP):
            code, depart = (('apres_devis_positionne', ancre) if recent
                            else ('dormant_devis', None))
        elif lead.stage == stages.CONTACTED:
            code, depart = (('contact_positionne', ancre) if recent
                            else ('dormant_jamais_chiffre', None))
        else:  # NEW — le seul restant (Froid et Signé sont exclus en amont).
            code, depart = (('contact_complete', maintenant) if recent
                            else ('dormant_jamais_chiffre', None))

        entree = {
            'lead': lead,
            'code': code,
            'cadence': _PLACEMENT_CADENCES[code],
            'depart': _placement_moment(depart),
            'devis': devis if code == 'apres_devis_positionne' else None,
            'positionne': code in _PLACEMENT_REPLI_DORMANT,
            'ancre': ancre,
            'jours': jours,
            'nom': f'{lead.nom} {lead.prenom or ""}'.strip(),
            'stage_libelle': stages.STAGE_LABELS.get(lead.stage, lead.stage),
            'source': lead.source or '',
            'creneau': None,
            'prochaine_touche': '',
            'prochaine_le': None,
        }
        if entree['positionne']:
            _trancher_cadence_positionnee(entree, maintenant, gabarits)
        decisions.append(entree)
    return decisions, ignores, total


def _echeances_best_effort(lead, cadence, depart, gabarits):
    """``calculer_echeances_cadence`` en mode best-effort : une liste vide au
    lieu d'une exception.

    Le placement est best-effort LEAD PAR LEAD (`PlacementImpossible`) : un
    dossier dont les horaires ou le gabarit se lisent mal ne doit pas faire
    tomber l'aperçu des 276 autres — c'est-à-dire toute la carte."""
    try:
        return calculer_echeances_cadence(lead, cadence, depart,
                                          gabarits=gabarits(cadence))
    except Exception:  # noqa: BLE001 — un dossier bancal n'arrête rien
        logger.warning('MRY30: échéances illisibles (lead #%s, cadence %s)',
                       getattr(lead, 'pk', '?'), cadence, exc_info=True)
        return []


def _trancher_cadence_positionnee(entree, maintenant, gabarits):
    """Date une cadence positionnée — ou la BASCULE en dormance.

    Une cadence positionnée dont TOUTES les touches sont déjà échues ne
    relancerait personne : elle bascule sur la dormance de sa famille. Cette
    bascule change un CHIFFRE que la carte affiche (`par_etape`), elle
    appartient donc à la DÉCISION, pas à l'exécution — sinon l'aperçu
    annoncerait « après devis : 30 » là où l'application écrirait « dormants :
    30 », et le second clic montrerait autre chose que le premier. C'est la
    leçon de MRY23, tirée un cran plus tôt.

    C'est le SEUL calcul d'échéances mené pour toute une famille — et il ne
    concerne que les positionnés (42 sur 270 en production) : une cadence
    complète part de maintenant et un dormant de son créneau, ni l'une ni
    l'autre n'a de touche passée à examiner."""
    echeances = _echeances_best_effort(
        entree['lead'], entree['cadence'], entree['depart'], gabarits)
    if not echeances:
        # Gabarit vide ou illisible : la cadence n'est pas « intégralement
        # passée », elle est INCONNUE. Basculer tout un portefeuille au froid
        # sur un référentiel absent serait la pire lecture de ce silence ;
        # l'exécution comptera ces leads en `erreurs`, ce qui est la vérité.
        return
    futures = [(echeance, gabarit.ordre, gabarit)
               for gabarit, echeance in echeances if echeance >= maintenant]
    if futures:
        echeance, _, gabarit = min(futures, key=lambda ligne: ligne[:2])
        entree['prochaine_touche'] = gabarit.libelle or ''
        entree['prochaine_le'] = echeance
        return
    entree.update(code=_PLACEMENT_REPLI_DORMANT[entree['code']],
                  cadence='reveil', positionne=False, devis=None, depart=None)


def _placement_gabarits(company):
    """``cadence -> gabarit`` mémorisé pour la durée d'UN placement.

    Sans cette mémoire, chaque lead relisait (et seedait) sa cadence : 270
    allers-retours pour trois réponses possibles."""
    cache = {}

    def lire(cadence):
        if cadence not in cache:
            try:
                from apps.parametres.models_relance import CadenceRelanceEtape
                cache[cadence] = CadenceRelanceEtape.cadence_pour(
                    company, cadence)
            except Exception:  # noqa: BLE001 — jamais bloquant
                logger.warning('MRY30: gabarit « %s » illisible', cadence,
                               exc_info=True)
                cache[cadence] = []
        return cache[cadence]

    return lire


def _placement_gabarit_reveil(company, gabarits=None):
    """Le PREMIER barreau actif du gabarit « réveil » de la société.

    Trois réponses d'une seule lecture : son ``delai_jours`` (pour remonter le
    départ jusqu'au créneau visé), son ``ordre`` (pour reconnaître les réveils
    DÉJÀ posés, cf. `_placement_occupation_reveils`) et son ``libelle`` (la
    touche que l'aperçu annonce pour un dormant, « Réveil J30 » par défaut).
    ``None`` si le gabarit est illisible — le placement continue alors sur les
    valeurs de repli plutôt que d'échouer en bloc."""
    lire = gabarits or _placement_gabarits(company)
    barreaux = lire('reveil')
    return barreaux[0] if barreaux else None


def _placement_occupation_reveils(company, jour_zero, gabarit):
    """``{jour local: premières touches de réveil DÉJÀ posées}``, à partir de
    ``jour_zero``.

    Sans elle, chaque lot d'application recommencerait la file au premier
    créneau : le lot 2 poserait ses huit réveils SUR ceux du lot 1 — seize
    messages le même matin depuis le même numéro, précisément ce que
    l'étalement existe pour empêcher. Et l'aperçu lancé entre deux lots
    annoncerait des créneaux déjà pris.

    Ne compte que le PREMIER barreau (``ordre``) : c'est lui qu'on étale ; le
    J60 suit mécaniquement."""
    from collections import Counter

    ordre = getattr(gabarit, 'ordre', None)
    if ordre is None:
        return Counter()
    return Counter(
        RelanceEtape.objects.filter(
            company=company, cadence='reveil', ordre=ordre,
            statut=RelanceEtape.Statut.A_FAIRE, due_date__gte=jour_zero,
        ).values_list('due_date', flat=True))


def _etaler_reveils(dormants, company, maintenant, *, gabarit=None):
    """Pose ``creneau`` (et le ``depart`` qui en découle) sur chaque dormant,
    8 par jour ouvré, LES ANCRES LES PLUS RÉCENTES D'ABORD.

    L'ordre n'est pas cosmétique : le dossier dont on a eu des nouvelles la
    semaine dernière a bien plus de chances de répondre que celui qui dort
    depuis huit mois — c'est lui qui doit occuper les premiers créneaux.

    Le premier jour est AUJOURD'HUI si la fenêtre d'appel n'est pas déjà
    close, sinon le prochain jour ouvré : ``prochain_creneau_appel`` répond
    exactement à cette question. Les jours déjà PLEINS (réveils posés par un
    lot précédent) sont sautés, et un jour partiellement occupé reprend au
    créneau suivant : la file se PROLONGE, elle ne recommence jamais.

    N'écrit rien : renvoie les dormants DANS L'ORDRE d'étalement."""
    from apps.notifications.calendar_utils import ajouter_jours_ouvres

    from . import horaires

    if not dormants:
        return []
    if gabarit is None:
        gabarit = _placement_gabarit_reveil(company)
    delai = (getattr(gabarit, 'delai_jours', None)
             or PLACEMENT_REVEIL_DELAI_JOURS)
    # Une cadence « réveil » commence par un MESSAGE WhatsApp : sa fenêtre est
    # celle des messages (08:30), pas celle des appels (09:00) — 07/09/2026.
    base = horaires.prochain_creneau_appel(
        maintenant, company, canal='whatsapp')
    base_locale = base.astimezone(horaires.CASABLANCA)
    jour_zero = base_locale.date()
    if base_locale.time() > PLACEMENT_CRENEAUX[0]:
        # Les créneaux du jour (10 h-12 h 20) sont déjà derrière nous : un
        # placement lancé l'après-midi commence le PROCHAIN jour ouvré, jamais
        # avec des touches « en retard » à la seconde où elles naissent.
        jour_zero = ajouter_jours_ouvres(jour_zero, 1, company)
    occupation = _placement_occupation_reveils(company, jour_zero, gabarit)
    ordonnes = sorted(dormants,
                      key=lambda e: (e['ancre'], e['lead'].pk), reverse=True)
    jour = jour_zero
    for entree in ordonnes:
        while occupation[jour] >= PLACEMENT_REVEILS_PAR_JOUR:
            jour = ajouter_jours_ouvres(jour, 1, company)
        rang = occupation[jour]
        occupation[jour] += 1
        creneau = horaires.prochain_creneau_appel(
            datetime.datetime.combine(
                jour, PLACEMENT_CRENEAUX[rang], tzinfo=horaires.CASABLANCA),
            company, canal='whatsapp')
        entree['creneau'] = creneau
        # La cadence « réveil » place sa première touche à J+`delai` : on
        # remonte donc le départ d'autant pour qu'elle tombe SUR le créneau.
        entree['depart'] = creneau - datetime.timedelta(days=delai)
    return ordonnes


def _placement_touches_creees(lead, cadence, devis=None):
    """Les touches de CETTE cadence, relues triées par échéance."""
    from django.db.models import F
    qs = lead.relance_etapes.filter(cadence=cadence)
    if devis is not None:
        qs = qs.filter(devis=devis)
    return list(qs.order_by(F('due_at').asc(nulls_last=True), 'due_date',
                            'ordre'))


def _placer_cadence_positionnee(entree, *, user, maintenant):
    """Cadence `contact`/`apres_devis` datée depuis l'ancre (ou l'envoi du
    devis), touches déjà échues ANNULÉES (CKP1 — c'est le MOTEUR qui les
    retire, pas un commercial : ``traite_par`` reste NULL).

    Les touches passées sont annulées par un UPDATE direct, jamais par
    ``marquer_etape_relance`` : celui-ci journalise une ligne de chatter par
    touche (dix lignes « touche sautée » sur un dossier qu'on vient à peine de
    reprendre) et, sur la DERNIÈRE, déclencherait ``cloturer_cadence`` — le
    lead partirait au froid étiqueté « injoignable » à la seconde même où on
    l'inscrit dans la cadence.

    Renvoie ``True`` si une touche reste À FAIRE, ``False`` si la cadence est
    intégralement passée. Ce second cas est désormais TRANCHÉ EN AMONT par
    ``_trancher_cadence_positionnee`` (l'aperçu doit annoncer la bascule) : le
    voir ici est une anomalie, que l'appelant compte en ``erreurs``. La remise
    en état reste néanmoins écrite, parce qu'elle doit être exacte le jour où
    elle sert."""
    lead = entree['lead']
    # Photo d'AVANT : de quoi défaire proprement si la cadence s'avère
    # intégralement passée (voir plus bas). Un rappel posé à la main par un
    # commercial ne doit pas disparaître dans l'opération.
    relance_avant = lead.relance_date
    activites_avant = set(lead.activites.values_list('pk', flat=True))

    try:
        etapes = initialiser_plan_relance(
            lead, user, cadence=entree['cadence'], depart=entree['depart'],
            devis=entree['devis'])
    except CadenceActiveConflit as exc:
        raise PlacementImpossible(str(exc))
    if not etapes:
        raise PlacementImpossible(
            f'aucune touche créée (cadence {entree["cadence"]})')
    if not entree['positionne']:
        return True

    passees = [e.pk for e in etapes
               if e.due_at is not None and e.due_at < maintenant]
    if passees:
        RelanceEtape.objects.filter(
            pk__in=passees, statut=RelanceEtape.Statut.A_FAIRE,
        ).update(statut=RelanceEtape.Statut.ANNULEE,
                 note=PLACEMENT_NOTE_PASSEE, traite_par=None,
                 traite_le=maintenant)
    if len(passees) >= len(etapes):
        # Rien ne reste à faire : cette cadence ne relancerait personne. On
        # défait TOUT ce qu'on vient de créer — touches, note « Plan de
        # relance initialisé » (elle annoncerait un plan qui n'existe plus) et
        # `relance_date` — puis l'appelant compte l'anomalie. Sans cette
        # remise en état, le lead gardait une échéance de relance pointant sur
        # une touche supprimée : un rappel fantôme, en retard pour toujours.
        RelanceEtape.objects.filter(pk__in=[e.pk for e in etapes]).delete()
        lead.activites.exclude(pk__in=activites_avant).delete()
        lead.relance_date = relance_avant
        lead.save(update_fields=['relance_date'])
        sync_relance_activity(lead, user)
        return False

    # `initialiser_plan_relance` a pointé `relance_date` sur la PREMIÈRE
    # touche — celle qu'on vient peut-être de sauter. On la recale sur la
    # prochaine réellement à faire, exactement comme `marquer_etape_relance`.
    # ACRM37 — par LE recalage unique (une touche au moins reste ouverte ici).
    _recaler_file(lead, user)
    return True


def _placer_dormant(entree, *, user):
    """Dormance explicite : Froid + étiquette qui dit POURQUOI + cadence de
    réveil posée sur le créneau étalé.

    Froid est un PARKING, pas une perte (même garantie que ``cloturer_cadence``
    MRY11) : aucun motif de perte n'est posé, ``Lead.perdu`` n'est jamais
    touché."""
    lead = entree['lead']
    avancer_stage_lead_vers(lead, user, stages.COLD)
    tag = _PLACEMENT_TAGS.get(entree['code'])
    if tag:
        poser_tag_lead(lead, user, tag)
    try:
        etapes = initialiser_plan_relance(
            lead, user, cadence='reveil', depart=entree['depart'])
    except CadenceActiveConflit as exc:
        raise PlacementImpossible(str(exc))
    if not etapes:
        raise PlacementImpossible('aucune touche de réveil créée')
    if entree['code'] == 'dormant_devis':
        for etape, cle in zip(sorted(etapes, key=lambda e: e.ordre),
                              _PLACEMENT_CLES_REVEIL_DEVIS):
            if etape.template_cle != cle:
                etape.template_cle = cle
                etape.save(update_fields=['template_cle'])
    return True


def _placer_un(entree, *, user, maintenant):
    """Place UN lead, puis journalise la touche qui l'attend."""
    if entree['cadence'] != 'reveil':
        if not _placer_cadence_positionnee(
                entree, user=user, maintenant=maintenant):
            # La DÉCISION a déjà vérifié qu'une touche restait à faire
            # (`_trancher_cadence_positionnee`) : si la matérialisation dit le
            # contraire, c'est une anomalie — comptée, jamais silencieuse.
            raise PlacementImpossible(
                'cadence intégralement passée après décision')
    else:
        _placer_dormant(entree, user=user)

    lead = entree['lead']
    touches = _placement_touches_creees(
        lead, entree['cadence'], devis=entree['devis'])
    a_faire = [e for e in touches if e.statut == RelanceEtape.Statut.A_FAIRE]
    reference = (a_faire or touches or [None])[0]
    # Le libellé est relu sur la touche RÉELLEMENT créée : la décision ne date
    # que les vingt lignes de l'aperçu, et cette note doit nommer la bonne
    # touche pour les 250 autres aussi.
    libelle = (getattr(reference, 'libelle', '') or ''
               or entree['prochaine_touche'])
    # FG28/MRY19 — note SYSTÈME (``user=None``), JAMAIS l'utilisateur qui a
    # lancé le placement. Le récepteur QJ7 (`_avancer_stage_on_contact_
    # activity`) fait avancer NEW → CONTACTED et stampe `first_contacted_at`
    # sur toute note portant un `user` : posée avec l'acteur, cette ligne
    # aurait déclaré « contactés » les leads NEW qu'on vient justement
    # d'inscrire dans la cadence de PREMIER contact — 270 dossiers marqués
    # joints sans qu'un humain ait décroché, et le KPI de premier contact
    # faussé du même coup. Même choix, trois lignes plus haut, que la note de
    # `initialiser_plan_relance`. QUI a lancé le placement reste tracé : par
    # les lignes de modification (étape, étiquette), qui portent l'acteur.
    LeadActivity.objects.create(
        company=lead.company, lead=lead, user=None,
        kind=LeadActivity.Kind.NOTE,
        body=f'Placé dans la cadence {entree["cadence"]} à la touche '
             f'« {libelle} » ({PLACEMENT_MARQUEUR}).')
    return True


def _placement_ordre(decisions, company, maintenant, *, gabarit=None):
    """L'ordre de traitement d'un lot : les cadences vivantes (les dossiers
    les plus RÉCENTS d'abord), puis les dormants dans leur ordre d'étalement.

    L'étalement est calculé ICI, pour tout le monde et dans les deux modes :
    c'est lui qui donne son créneau à chaque dormant, donc `reveils_jusqu_au`
    et la date affichée par l'aperçu. Borner le lot APRÈS cet ordre garantit
    que le lot 1 prend bien les premiers créneaux et le lot 2 les suivants."""
    dormants = _etaler_reveils(
        [e for e in decisions if e['cadence'] == 'reveil'], company,
        maintenant, gabarit=gabarit)
    vivants = sorted([e for e in decisions if e['cadence'] != 'reveil'],
                     key=lambda e: (e['jours'], e['lead'].pk))
    return vivants + dormants


def _dater_apercu(decisions, maintenant, *, gabarits, gabarit_reveil):
    """Donne sa touche et sa date à CHACUNE des vingt lignes de l'aperçu —
    et à elles seules.

    C'est le cœur de la correction du 07/09 : dater les 270 décisions
    revenait à matérialiser 270 cadences (le dry-run en transaction annulée),
    alors que le rapport n'en montre que vingt. Les positionnées sont déjà
    datées par la décision (elle devait, de toute façon, savoir s'il leur
    restait une touche) ; restent les cadences complètes, calculées ici, et
    les dormants, dont la date EST leur créneau étalé."""
    for entree in sorted(
            decisions,
            key=lambda e: (e['jours'], e['lead'].pk))[:PLACEMENT_APERCU_MAX]:
        if entree['prochaine_le'] is not None:
            continue
        if entree['cadence'] == 'reveil':
            entree['prochaine_touche'] = (
                getattr(gabarit_reveil, 'libelle', '') or '')
            entree['prochaine_le'] = entree['creneau']
            continue
        echeances = _echeances_best_effort(
            entree['lead'], entree['cadence'], entree['depart'], gabarits)
        futures = [(echeance, gabarit.ordre, gabarit)
                   for gabarit, echeance in echeances
                   if echeance >= maintenant]
        if futures:
            echeance, _, gabarit = min(futures, key=lambda ligne: ligne[:2])
            entree['prochaine_touche'] = gabarit.libelle or ''
            entree['prochaine_le'] = echeance


def _executer_placements(entrees, *, user, maintenant):
    """Exécute les décisions du LOT, lead par lead, best-effort.

    ``entrees`` arrive déjà ordonné et borné (`_placement_ordre`, `limite`) :
    cette fonction ne décide plus rien — elle pose ce que la décision a
    tranché. Renvoie ``(applique, erreurs)``."""
    from django.db import transaction

    applique = erreurs = 0
    for entree in entrees:
        try:
            with transaction.atomic():
                _placer_un(entree, user=user, maintenant=maintenant)
        except Exception:  # noqa: BLE001 — un dossier bancal n'arrête rien
            logger.warning(
                'MRY30: placement échoué (lead #%s, code %s)',
                entree['lead'].pk, entree['code'], exc_info=True)
            erreurs += 1
            continue
        applique += 1
    return applique, erreurs


def _rapport_placement(decisions, ignores, total, *, apply, applique, erreurs,
                       restants):
    """Le rapport, forme ``contract_samples/placement_anciens_leads.json``."""
    from . import horaires

    par_code = {}
    for entree in decisions:
        par_code[entree['code']] = par_code.get(entree['code'], 0) + 1
    par_etape = [
        {'code': code, 'libelle': libelle, 'cadence': cadence,
         'nombre': par_code[code]}
        for code, libelle, cadence in PLACEMENT_DECISIONS if code in par_code
    ]
    apercu = [
        {
            'lead': entree['lead'].pk,
            'nom': entree['nom'],
            'stage_libelle': entree['stage_libelle'],
            'source': entree['source'],
            'ancre': entree['ancre'].astimezone(
                horaires.CASABLANCA).date().isoformat(),
            'jours': entree['jours'],
            'code': entree['code'],
            'cadence': entree['cadence'],
            'prochaine_touche': entree['prochaine_touche'],
            'prochaine_le': (
                entree['prochaine_le'].astimezone(
                    horaires.CASABLANCA).isoformat()
                if entree['prochaine_le'] is not None else None),
        }
        for entree in sorted(
            decisions,
            key=lambda e: (e['jours'], e['lead'].pk))[:PLACEMENT_APERCU_MAX]
    ]
    creneaux = [e['creneau'] for e in decisions if e['creneau'] is not None]
    return {
        'apply': bool(apply),
        'total_candidats': total,
        'a_placer': len(decisions),
        'ignores': ignores,
        'par_etape': par_etape,
        'apercu': apercu,
        'reveils_jusqu_au': (
            max(creneaux).astimezone(horaires.CASABLANCA).date().isoformat()
            if creneaux else None),
        'applique': applique,
        'erreurs': erreurs,
        'restants': restants,
    }


def _placement_limite(limite):
    """``limite`` bornée à [1, PLACEMENT_LOT_MAX] (défaut PLACEMENT_LOT_DEFAUT).

    La vue REFUSE une valeur hors bornes (400) : ce garde-fou-ci protège les
    appelants internes (commande, tâche) d'un lot de 100 000 leads."""
    if limite is None:
        return PLACEMENT_LOT_DEFAUT
    return max(1, min(int(limite), PLACEMENT_LOT_MAX))


def placer_anciens_leads(company, user, *, apply=False, maintenant=None,
                         limite=None, leads_en_portee=None):
    """Enveloppe de `_placer_anciens_leads_sans_cache` sous `horaires.cache_local()` :
    profil société et jours ouvrés lus UNE fois pour toute l'opération. Sans
    cela, dater les touches de 272 leads coûtait ~7 000 requêtes et 24 s en
    production (07/09/2026), au-delà du délai du navigateur."""
    from . import horaires
    with horaires.cache_local():
        return _placer_anciens_leads_sans_cache(
            company, user, apply=apply, maintenant=maintenant, limite=limite,
            leads_en_portee=leads_en_portee)


def _placer_anciens_leads_sans_cache(company, user, *, apply=False,
                                     maintenant=None, limite=None,
                                     leads_en_portee=None):
    """MRY30 — Place les anciens leads d'une société dans les cadences du
    moteur de relances. Rapport = ``contract_samples/placement_anciens_leads``.

    ``apply=False`` (défaut) est un CALCUL PUR : aucune écriture, aucune
    transaction, aucun rollback. L'aperçu partage le CALCUL de l'application
    — ``calculer_echeances_cadence`` pour les dates, ``_etaler_reveils`` pour
    les créneaux, ``_decider_placements`` pour les codes — et c'est ce partage
    qui le rend fidèle, comme l'était l'ancienne exécution en transaction
    annulée. Celle-ci matérialisait en revanche les touches des 277 candidats
    pour les jeter aussitôt : plus de 20 s, donc un 499 (le navigateur
    abandonne à 20 s) et un écran qui n'affichait jamais rien — l'incident du
    07/09/2026. Les vingt lignes de l'aperçu sont les seules datées.

    ``apply=True`` place AU PLUS ``limite`` leads (défaut 40), dans l'ordre
    d'`_placement_ordre` : les cadences vivantes des dossiers les plus récents
    d'abord, puis les dormants dans leur ordre d'étalement. Chaque lead est
    posé sous son propre ``transaction.atomic`` : son échec est journalisé et
    compté dans ``erreurs``, il n'annule jamais les autres. La réponse porte
    ``restants`` ; l'écran (et la commande) rappellent jusqu'à ce qu'il tombe
    à zéro. IDEMPOTENT : les leads du lot précédent reviennent en
    ``deja_en_cadence``, et l'étalement REPREND à la suite des réveils déjà
    posés — jamais au premier créneau du jour.

    ``par_etape``, ``apercu`` et ``reveils_jusqu_au`` décrivent l'ensemble
    RESTANT au DÉBUT de l'appel : ce qu'un aperçu montrerait à cette seconde,
    dans les deux modes."""
    maintenant = maintenant or timezone.now()
    gabarits = _placement_gabarits(company)
    decisions, ignores, total = _decider_placements(
        company, maintenant, gabarits, leads_en_portee=leads_en_portee)
    # Lu SEULEMENT s'il y a un dormant : `cadence_pour` seede la cadence
    # absente, et une société sans aucun dormant n'a aucune raison de voir
    # naître un gabarit de réveil au passage d'un aperçu.
    gabarit_reveil = (
        _placement_gabarit_reveil(company, gabarits)
        if any(e['cadence'] == 'reveil' for e in decisions) else None)
    ordre = _placement_ordre(decisions, company, maintenant,
                             gabarit=gabarit_reveil)
    _dater_apercu(decisions, maintenant, gabarits=gabarits,
                  gabarit_reveil=gabarit_reveil)
    rapport = _rapport_placement(
        decisions, ignores, total, apply=apply, applique=0, erreurs=0,
        restants=len(decisions))
    if not apply:
        return rapport
    applique, erreurs = _executer_placements(
        ordre[:_placement_limite(limite)], user=user, maintenant=maintenant)
    rapport['applique'] = applique
    rapport['erreurs'] = erreurs
    rapport['restants'] = max(0, len(decisions) - applique - erreurs)
    return rapport
