"""Suivi déclenché par la visite : suspension, reprise, retour de visite (SPL15, extrait de crm/services.py : déplacement pur).

Module RACINE de la scission : il importe ``.services`` au niveau module ;
aucun module de type (a) ne l'importe et ``services`` ne le réexporte pas.
"""
import datetime
import logging

from django.utils import timezone

from core.dates import aujourd_hui_local

from apps.parametres import models_relance as gabarit_relance

from . import activity, cadence_config
from .cadence_config import (
    CLE_CONFIRMATION,
    CLE_DEBRIEF,
    CLE_DEVIS,
    CLE_DEVIS_MODIFIE,
    CLE_PLANIFIER,
    cle_de,
    est_etape,
    q_etape,
)
from .cadence_filet import (
    _config_visite,
    _etape_visite_ouverte,
    _lead_relancable,
    _poser_etape_visite,
    _suivi_de_proposition_existe,
)
from .cadence_plan import _recaler_file, reporter_prochaine_touche
from .cadence_reperes import (
    FILET_JOINT_LIBELLE,
    OUTCOME_VISITE_ACCEPTEE,
    VISITE_CADENCE,
    VISITE_ORDRE_CONFIRMATION,
    VISITE_ORDRE_DEBRIEF,
    _CLES_DEBRIEF,
    q_visite,
)
from .cadence_touche import marquer_etape_relance
from .leads_socle import visite_point_eau_requise, visite_pro_avant_devis
from .models import LeadActivity, RelanceEtape
from .services import poser_etape_preparer_devis
from .visites_retour_lead import ecrire_retour_lead_visite

logger = logging.getLogger(__name__)


#: Combien de jours après la visite le plan de relance REPREND. Deux : le
#: débrief est à J+1, la relance générique ne doit pas tomber le même jour que
#: l'appel de débrief (deux sollicitations le même jour pour un client qu'on
#: vient de voir chez lui). Ce n'est pas un délai « commercial » inventé, c'est
#: la place du débrief plus un jour.
#: PARAM-CADENCE (25/09/2026) — reste une CONSTANTE, pas un barreau de
#: Paramètres : ce n'est pas une étape posée, c'est le décalage du plan.
VISITE_REPRISE_JOURS = 2


def _touche_pendante_du_plan(lead):
    """La touche du PLAN après-devis encore à faire — hors gestes de visite.

    C'est elle que la visite fait taire : les trois étapes de visite portent la
    même cadence (l'écran les montre dans la même frise) mais ne sont pas des
    barreaux du protocole, et décaler le débrief au motif qu'une visite est
    planifiée n'aurait aucun sens."""
    from django.db.models import F

    return (lead.relance_etapes
            .filter(cadence=VISITE_CADENCE,
                    statut=RelanceEtape.Statut.A_FAIRE)
            .exclude(q_visite())
            .order_by(F('due_at').asc(nulls_last=True), 'due_date', 'ordre')
            .first())


def suspendre_plan_jusqu_apres_visite(lead, user, date_prevue):
    """AMENDEMENT FONDATEUR (15/09/2026) — le plan se TAIT, il ne meurt pas.

    La touche pendante du protocole est REPORTÉE à ``date_prevue +
    VISITE_REPRISE_JOURS``, et avec elle — par la mécanique EXISTANTE de
    ``reporter_prochaine_touche``, jamais une seconde — toutes les touches
    suivantes de la cadence ET l'ancre ``cadence_depart``, du même delta. Le
    lead reste donc EXACTEMENT à sa place : même barreau, même libellé, même
    reste de plan, simplement plus tard. Si la visite n'aboutit pas, le suivi
    reprend de lui-même — aucun redémarrage de cadence n'existe nulle part.

    Deux no-op délibérés :

    * aucune touche pendante (le plan n'a pas démarré, ou il est épuisé) ⇒
      rien à décaler, et surtout rien à CRÉER : ce serait un restart ;
    * la touche pendante tombe DÉJÀ après la reprise ⇒ on ne la tire jamais
      EN AVANT. Une visite planifiée ne doit pas accélérer une relance.

    Renvoie la touche déplacée, ou ``None``."""
    cible = _touche_pendante_du_plan(lead)
    if cible is None:
        return None
    reprise = date_prevue + datetime.timedelta(days=VISITE_REPRISE_JOURS)
    if cible.due_date is not None and cible.due_date >= reprise:
        return None
    from . import horaires

    quand = datetime.datetime.combine(
        reprise, datetime.time(9, 0), tzinfo=horaires.CASABLANCA)
    # ``journaliser=False`` : l'appelant écrit UNE note qui dit la vraie
    # raison (« Relances décalées après la visite »), et « Rappel demandé »
    # serait faux — le client n'a rien demandé. COCKPIT-CONTRÔLE : un
    # décalage du MOTEUR, jamais un report compté à la commerciale.
    return reporter_prochaine_touche(
        lead, user, quand, etape=cible, journaliser=False,
        compter_report=False)


# ── CAD-B ── CAD28 ──────────────────────────────────────────────────────────

def reprendre_plan_apres_retour_visite(lead, user):
    """CAD28 — la reprise du protocole part du RETOUR RÉELLEMENT SAISI.

    La suspension calait la reprise sur la date PRÉVUE de la visite. Une
    visite reportée à la dernière minute sans mise à jour de la fiche laissait
    donc la relance repartir quand même : le client recevait un message
    « suite à notre visite » avant que quiconque soit passé chez lui.

    Le retour de visite, lui, est déjà saisi (``appliquer_retour_visite``).
    On recale donc la touche pendante du protocole sur CE jour-là plus le
    délai de débrief, par la mécanique EXISTANTE — jamais une seconde :
    ``suspendre_plan_jusqu_apres_visite`` avec la date du jour. Elle apporte
    ses deux garde-fous tels quels : aucune touche pendante ⇒ on ne CRÉE
    rien ; une touche déjà postérieure à la reprise ⇒ on ne la tire jamais EN
    AVANT (un retour tardif ne doit pas accélérer une relance).

    Le délai reste ``VISITE_REPRISE_JOURS`` — la place du débrief plus un
    jour, non réglable : un réglage de plus pour deux personnes. PARAM-CADENCE
    (25/09/2026) : ce n'est PAS un barreau du gabarit « Visite technique » —
    c'est le décalage du PLAN autour de la visite, pas une étape posée.

    Rend la touche déplacée, ou ``None`` (les deux no-op ci-dessus).
    """
    deplacee = suspendre_plan_jusqu_apres_visite(
        lead, user, aujourd_hui_local())
    if deplacee is None:
        return None
    LeadActivity.objects.create(
        company=lead.company, lead=lead, user=None,
        kind=LeadActivity.Kind.NOTE,
        body=('Relances recalées sur le retour de visite — prochaine touche '
              f'le {deplacee.due_date:%d/%m/%Y}.'))
    return deplacee


def _devis_id_de_la_cadence(lead):
    """L'id du devis suivi par la cadence après-devis, s'il est SANS DOUTE.

    Deux devis relancés en parallèle (cas rare mais réel) ⇒ ``None`` : mieux
    vaut deux étapes de visite sans devis attaché qu'un rendez-vous rattaché
    au mauvais dossier."""
    ids = set(
        lead.relance_etapes
        .filter(cadence=VISITE_CADENCE)
        .exclude(devis__isnull=True)
        .values_list('devis_id', flat=True))
    return ids.pop() if len(ids) == 1 else None


# ── CAD123 — une visite SANS devis envoyé : on AVERTIT, on ne bloque pas
# (décision fondateur du 21/09/2026).
#
# La doctrine du 15/09 est « visite technique jamais avant le devis » : le
# panneau de coaching la respecte (il ne vit que sur le suivi de proposition),
# mais la fiche (``SectionVisite``) planifiait sans aucune garde. Le terrain a
# des exceptions légitimes : l'écran NOMME la règle et laisse passer. Le texte
# vit ICI, une fois — chaque chemin qui planifie l'affiche tel quel, il ne
# peut donc pas dire deux choses différentes. La visite posée malgré tout est
# signalée comme telle dans le suivi (note de ``appliquer_visite_planifiee``).

#: CAD123 — la règle, telle que l'écran la dit.
AVERTISSEMENT_VISITE_SANS_DEVIS = (
    'Aucun devis n’a encore été envoyé à ce client. Règle : la visite '
    'technique se propose APRÈS le devis (c’est un outil de closing). Vous '
    'pouvez la planifier quand même — elle sera signalée « sans devis » dans '
    'le suivi.')

#: CAD123 × CAD122 — l'effet de bord juridique, rappelé à côté : un bon de
#: commande signé pendant la visite, chez le client, est un démarchage à
#: domicile (loi 31-08, art. 45) ; les mentions viennent de la décision
#: CAD122 (`docs/crm/messages_meryem.md`), rien n'est ajouté.
RAPPEL_JURIDIQUE_VISITE_DOMICILE = (
    'Si le bon de commande se signe pendant la visite, chez le client : '
    'démarchage à domicile (loi 31-08, art. 45) — cocher « signé au '
    'domicile », formulaire de rétractation remis, aucun acompte encaissé '
    'avant 7 jours (art. 49 et 50).')

#: La phrase ajoutée à la note de planification quand aucun devis n'est parti.
MENTION_VISITE_SANS_DEVIS = (
    'Planifiée SANS devis envoyé — exception à la règle « la visite se '
    'propose après le devis ».')


#: AGR408 (D-AGR-4) — la règle POMPAGE : pour un lead agricole dont le niveau
#: d'eau ou le débit du forage est inconnu, la visite de relevé du point d'eau
#: se fait AVANT le devis. Ce n'est pas une exception.
AVERTISSEMENT_VISITE_POINT_EAU = (
    'Pompage : niveau d’eau ou débit du forage inconnu — la visite de relevé '
    'du point d’eau se fait AVANT le devis.')

#: AGR408 — la phrase de la note de planification dans ce cas.
MENTION_VISITE_POINT_EAU = (
    'Visite de relevé du point d’eau, avant devis (règle pompage).')


#: CIQ411 (D-CIQ-5) — la règle SITE PROFESSIONNEL : pour un lead commercial
#: ou industriel dont le site est en MT, ou dont la tension, la puissance
#: souscrite ou le toit restent inconnus, la visite technique se fait AVANT le
#: devis final. Ce n'est pas une exception ; jamais un blocage.
AVERTISSEMENT_VISITE_PRO = (
    'Site professionnel : {motifs} — la visite technique se fait AVANT le '
    'devis final (un devis indicatif reste possible, marqué « estimation '
    'sous réserve de visite »).')

#: CIQ411 — la phrase de la note de planification dans ce cas.
MENTION_VISITE_PRO = 'Visite technique avant devis (règle site professionnel).'


def visite_sans_devis(lead):
    """CAD123 — ce lead n'a-t-il encore reçu AUCUN devis (sorti du
    brouillon) ? Lecture par le sélecteur de ``ventes`` (frontière M3).
    Best-effort : dans le doute (lecture en échec), on répond NON — un
    avertissement faux vaut moins que pas d'avertissement."""
    if lead is None or not getattr(lead, 'pk', None):
        return False
    try:
        from apps.ventes.selectors import lead_a_un_devis

        return not lead_a_un_devis(lead)
    except Exception:  # noqa: BLE001 — jamais bloquant
        logger.warning('CAD123 : devis du lead #%s illisibles',
                       getattr(lead, 'pk', '?'), exc_info=True)
        return False


#: Décision fondateur du 24/09/2026 — la note des étapes « préparer et
#: envoyer le devis » mises EN ATTENTE par une visite planifiée sans devis.
NOTE_DEVIS_APRES_VISITE = ('visite planifiée : le devis se prépare après la '
                           'visite')
#: … et la phrase ajoutée, dans ce cas, à la note de planification.
#: PARAM-CADENCE — la phrase porte le libellé RÉEL de l'étape annulée
#: (``mention_devis_apres_visite``) ; cette constante est la phrase au
#: libellé par défaut.
MENTION_DEVIS_APRES_VISITE = (
    f'Étape « {FILET_JOINT_LIBELLE} » mise en attente : le devis se prépare '
    'après la visite.')


def mention_devis_apres_visite(libelle):
    """La phrase de ``MENTION_DEVIS_APRES_VISITE`` au libellé réel."""
    return (f'Étape « {libelle or FILET_JOINT_LIBELLE} » mise en attente : '
            'le devis se prépare après la visite.')


#: La note d'un débrief annulé au retour terrain sans devis.
NOTE_RETOUR_SANS_DEVIS = 'retour terrain sans devis : préparer le devis'
#: Relevé du 25/09/2026 — la note de l'étape « Confirmer la visite (veille) »
#: encore ouverte quand le retour terrain arrive : la visite a eu lieu, il n'y
#: a plus rien à confirmer (même geste que le filet « planifier la visite »,
#: annulé à la planification).
NOTE_CONFIRMATION_VISITE_FAITE = 'visite effectuée'

#: La notification « Retour de visite » du responsable — la suite par défaut
#: (débrief : un devis est parti, il reste à conclure).
NOTIF_RETOUR_VISITE_RAPPELER = ('La visite technique est terminée. Rappeler '
                                'le client sous 24-48 h pour conclure.')


def phrase_notification_retour_visite(etape):
    """Le corps de la notification « Retour de visite », lu sur l'étape que
    ``appliquer_retour_visite`` vient de RENDRE — jamais deviné.

    Relevé du 25/09/2026 (décision fondateur du 24/09) : sans devis parti, la
    suite du retour est « Préparer et envoyer le devis », pas un rappel « pour
    conclure » ; la notification disait pourtant toujours « rappeler sous
    24-48 h ». Elle dit désormais la suite posée et sa date."""
    if (etape is not None and getattr(etape, 'due_date', None) is not None
            and est_etape(etape, CLE_DEVIS)):
        return ('La visite technique est terminée. Suite : préparer et '
                f'envoyer le devis pour le {etape.due_date:%d/%m}.')
    return NOTIF_RETOUR_VISITE_RAPPELER


def aucun_devis_parti(lead):
    """Décision fondateur du 24/09/2026 — AUCUN devis n'est encore parti vers
    ce client : ni devis sorti du brouillon dans l'ERP (``visite_sans_devis``,
    CAD123), ni suivi de proposition démarré sur un devis envoyé hors ERP.

    C'est le cas d'une visite qui PRÉCÈDE le devis : le devis se prépare
    APRÈS elle, et c'est lui — pas un débrief « rappeler le client » — que la
    visite doit faire naître."""
    return visite_sans_devis(lead) and not _suivi_de_proposition_existe(lead)


def avertissement_visite(lead):
    """CAD123 — ``{'avertissement_sans_devis', 'rappel_juridique'}`` pour
    l'écran qui planifie une visite : les deux textes quand aucun devis n'est
    parti, deux chaînes VIDES (jamais null) sinon. Aucun blocage : c'est une
    information, pas un refus."""
    if visite_sans_devis(lead):
        # AGR408 (D-AGR-4) — pompage au point d'eau inconnu : la visite de
        # relevé vient AVANT le devis, c'est la règle (le rappel juridique,
        # lui, est inchangé).
        texte = (AVERTISSEMENT_VISITE_POINT_EAU
                 if visite_point_eau_requise(lead)
                 else AVERTISSEMENT_VISITE_SANS_DEVIS)
        # CIQ411 (D-CIQ-5) — site pro en MT ou aux faits inconnus : la
        # visite AVANT le devis final est la règle, pas une exception.
        pro = visite_pro_avant_devis(lead)
        if pro is not None:
            texte = AVERTISSEMENT_VISITE_PRO.format(
                motifs=', '.join(pro['motifs']))
        return {'avertissement_sans_devis': texte,
                'rappel_juridique': RAPPEL_JURIDIQUE_VISITE_DOMICILE}
    return {'avertissement_sans_devis': '', 'rappel_juridique': ''}


def appliquer_visite_planifiee(lead, user, date_prevue, commercial_nom=''):
    """Un RENDEZ-VOUS de visite est posé (ou déplacé) : le suivi s'y recale.

    Dans l'ordre, et jamais autrement :

    1. la fiche porte la date (``Lead.visite_prevue_le``) — c'est elle que lit
       le message de confirmation ``{date_visite}`` ;
    2. sur un lead ACTIF : le plan après-devis en cours est SUSPENDU PAR
       DÉCALAGE (``suspendre_plan_jusqu_apres_visite``) — jamais annulé. Le
       lead garde sa position exacte dans le protocole et, si la visite
       n'aboutit pas, le suivi reprend tout seul là où il en était ;
    3. UNE note de chatter, toujours — même sur un dossier qu'on ne relance
       plus : savoir qu'une visite a été calée reste une information. Elle dit
       le décalage quand il a eu lieu, et se tait sinon (annoncer des relances
       décalées alors qu'aucune n'était pendante serait faux) ;
    4. les DEUX gestes du rendez-vous — confirmer la veille, débriefer le
       lendemain. Le filet « planifier la visite convenue », s'il traînait, est
       ANNULÉ : lui seul, et parce qu'il a rempli son office ;
    5. décision fondateur du 24/09/2026 — SANS devis parti
       (``aucun_devis_parti``), l'étape « préparer et envoyer le devis »
       restée ouverte est ANNULÉE (le devis se prépare APRÈS la visite, le
       retour terrain la re-pose) et la note de l'étape 3 le dit.

    RE-PLANIFICATION : les deux étapes encore ouvertes sont DÉPLACÉES, jamais
    dupliquées (``_poser_etape_visite`` est idempotente par libellé) — « on
    décale à jeudi » ne doit pas laisser la confirmation de mardi dans la file
    — et le plan glisse d'un delta ADDITIONNEL depuis la nouvelle date.

    ``STAGES.py`` n'est pas touché, et AUCUNE étape du plan après-devis n'est
    annulée. Renvoie les étapes posées/déplacées."""
    champs = []
    if lead.visite_prevue_le != date_prevue:
        lead.visite_prevue_le = date_prevue
        champs.append('visite_prevue_le')
    if champs:
        lead.save(update_fields=champs)

    relancable = _lead_relancable(lead)
    # Le décalage AVANT la note : c'est lui qui décide de la dernière phrase.
    decalee = (suspendre_plan_jusqu_apres_visite(lead, user, date_prevue)
               if relancable else None)
    sans_devis = visite_sans_devis(lead)
    # Décision fondateur du 24/09/2026 — une visite planifiée SANS devis met
    # le devis EN ATTENTE d'elle : l'étape « préparer et envoyer le devis »
    # restée ouverte (filet « client joint », datée de demain) est ANNULÉE —
    # statut moteur CKP1, comme le filet « planifier la visite » plus bas.
    # Laissée là, elle restait orpheline dans la file ; et cochée « Fait »
    # sans issue, elle valait « devis parti » (QJ-FUNNEL) alors qu'aucun
    # devis n'était fait. C'est le retour terrain qui la re-posera
    # (``appliquer_retour_visite``). Idempotent : une re-planification ne
    # trouve plus rien à annuler, et la note n'en dit rien.
    devis_en_attente = 0
    libelle_devis = ''
    if (relancable and sans_devis
            and not _suivi_de_proposition_existe(lead)):
        en_attente = lead.relance_etapes.filter(
            q_etape(CLE_DEVIS), statut=RelanceEtape.Statut.A_FAIRE)
        libelle_devis = (en_attente.values_list('libelle', flat=True)
                         .first() or '')
        devis_en_attente = en_attente.update(
            statut=RelanceEtape.Statut.ANNULEE,
            note=NOTE_DEVIS_APRES_VISITE, traite_par=None,
            traite_le=timezone.now())

    quand = date_prevue.strftime('%d/%m/%Y')
    corps = f'Visite technique planifiée le {quand}'
    corps += (f' — assignée à {commercial_nom}.' if commercial_nom
              else ' — pas encore assignée.')
    if decalee is not None:
        corps += ' Relances décalées après la visite.'
    if sans_devis:
        # CAD123 — la visite posée avant tout devis est VISIBLE comme telle
        # dans le suivi : on a averti, on n'a pas bloqué, on le dit.
        # AGR408 (D-AGR-4) — pour un lead agricole au point d'eau inconnu,
        # c'est la RÈGLE pompage, pas une exception.
        # CIQ411 (D-CIQ-5) — site pro : visite avant devis, la règle.
        if visite_pro_avant_devis(lead) is not None:
            corps += f' {MENTION_VISITE_PRO}'
        else:
            corps += (f' {MENTION_VISITE_POINT_EAU}'
                      if visite_point_eau_requise(lead)
                      else f' {MENTION_VISITE_SANS_DEVIS}')
    if devis_en_attente:
        corps += f' {mention_devis_apres_visite(libelle_devis)}'
    # Note SYSTÈME (``user=None``) : PLANIFIER n'est pas AVOIR contacté le
    # lead — même motif que ``arreter_cadence`` / ``initialiser_plan_relance``
    # (garde QJ7, qui traiterait sinon cette note comme un premier contact).
    LeadActivity.objects.create(
        company=lead.company, lead=lead, user=None,
        kind=LeadActivity.Kind.NOTE, body=corps)

    if not relancable:
        return []

    devis_id = _devis_id_de_la_cadence(lead)
    # Le filet « planifier la visite convenue » a rempli son office : on
    # l'ANNULE (statut moteur CKP1, jamais « sautée par un humain »). C'est la
    # SEULE étape que cette fonction annule — le plan, lui, est décalé.
    lead.relance_etapes.filter(
        q_etape(CLE_PLANIFIER),
        statut=RelanceEtape.Statut.A_FAIRE).update(
            statut=RelanceEtape.Statut.ANNULEE, note='visite planifiée',
            traite_par=None, traite_le=timezone.now())

    # PARAM-CADENCE — les deux gestes suivent le gabarit « Visite technique »
    # de la société : ``delai_jours`` de la confirmation = jours AVANT la
    # visite (la veille = 1), celui du débrief = jours APRÈS.
    confirmation = _config_visite(lead, CLE_CONFIRMATION)
    debrief = _config_visite(lead, CLE_DEBRIEF)
    veille = date_prevue - datetime.timedelta(
        days=confirmation['delai_jours'])
    if veille < aujourd_hui_local():
        # Visite calée pour aujourd'hui ou demain-matin-même : la veille est
        # déjà passée. On confirme AUJOURD'HUI — jamais une étape rétrodatée,
        # qui naîtrait « en retard » dans la file sans que personne n'ait
        # manqué quoi que ce soit.
        veille = aujourd_hui_local()
    # RE-PLANIFICATION — les deux étapes ci-dessous ont pu être emportées par
    # le décalage du plan (elles portent la même cadence et un ``ordre``
    # supérieur, donc ``reporter_prochaine_touche`` les glisse aussi). C'est
    # sans conséquence : elles sont RÉ-ANCRÉES ici même sur la nouvelle date de
    # visite, qui est leur seule vérité.
    etapes = [
        _poser_etape_visite(
            lead, cle=CLE_CONFIRMATION, ordre=VISITE_ORDRE_CONFIRMATION,
            quand=veille, devis_id=devis_id, config=confirmation),
        _poser_etape_visite(
            lead, cle=CLE_DEBRIEF, ordre=VISITE_ORDRE_DEBRIEF,
            quand=date_prevue + datetime.timedelta(
                days=debrief['delai_jours']),
            devis_id=devis_id, config=debrief),
    ]
    _recaler_file(lead, user)
    return etapes


def clore_etape_apres_planification(etape, user, *, note='',
                                    echeance_avant=None):
    """SUIVI E18 (30/09/2026) — la planification d'une visite CLÔT la touche
    qui l'a demandée (l'écran n'envoie plus jamais « Fait visite acceptée »
    AVANT d'avoir planifié).

    Appelée APRÈS la planification réussie (``visite_planifiee`` a déjà recalé
    le suivi) :

    * la touche est encore À FAIRE → close « visite acceptée » avec
      ``note`` (``marquer_etape_relance``) : la prise de contact s'arrête, le
      funnel avance, et le filet « planifier la visite » ne pose rien — un
      rendez-vous est calé ;
    * EXCEPTION : « Confirmer la visite » et « Débrief visite » encore
      ouvertes SUIVENT le rendez-vous (re-planification : la planification
      vient de les recaler) — elles restent ouvertes ;
    * la planification l'a déjà annulée (« Planifier la visite », ou l'étape
      devis mise en attente de la visite) → elle reste annulée.

    Dans les deux derniers cas, la note éventuelle part dans UNE ligne de
    chatter. Renvoie la touche (relue).

    COCKPIT-CONTRÔLE B8 — UNE ÉTAPE CLOSE GARDE L'ÉCHÉANCE QU'ELLE AVAIT
    QUAND ON L'A TRAITÉE. La planification vient de décaler le suivi pendant
    — cette touche comprise — jusqu'après la visite
    (``suspendre_plan_jusqu_apres_visite``, un déplacement du MOTEUR) ; close
    telle quelle, la touche se lisait due APRÈS la visite, « traitée en
    avance », et le contrôle du suivi la jugeait sur un jour à venir.
    ``echeance_avant`` = ``(due_at, due_date, due_initial_at)`` lus par
    l'appelant AVANT la planification : quand CETTE fonction clôt la touche,
    ces trois colonnes — et elles seules (UPDATE borné) — sont rétablies,
    juste avant la clôture (la ligne de chatter dit ainsi la vraie
    échéance). Ni ``cadence_depart``, ni la suite du plan (décalée après la
    visite), ni la naissance d'une touche ne changent : « visite acceptée »
    n'en fait naître aucune (``issue_fait_naitre_la_suite``)."""
    etape.refresh_from_db()
    note = str(note or '').strip()
    if (etape.statut == RelanceEtape.Statut.A_FAIRE
            and not est_etape(etape, CLE_CONFIRMATION, CLE_DEBRIEF)):
        if echeance_avant is not None:
            _retablir_echeance_traitee(etape, echeance_avant)
        return marquer_etape_relance(
            etape, user, RelanceEtape.Statut.FAIT, note=note,
            outcome=OUTCOME_VISITE_ACCEPTEE)
    if note:
        libelle = (etape.libelle or '').strip() or etape.get_canal_display()
        activity.log_note(
            etape.lead, user,
            f'Visite planifiée depuis l’étape « {libelle} » — note : {note}')
    return etape


def _retablir_echeance_traitee(etape, echeance):
    """COCKPIT-CONTRÔLE B8 — rétablit ``(due_at, due_date, due_initial_at)``
    sur ``etape`` : un UPDATE borné à ces trois colonnes (jamais un ``save``
    complet qui réécrirait le reste), puis l'instance en mémoire suit."""
    due_at, due_date, due_initial_at = echeance
    RelanceEtape.objects.filter(pk=etape.pk).update(
        due_at=due_at, due_date=due_date, due_initial_at=due_initial_at)
    etape.due_at = due_at
    etape.due_date = due_date
    etape.due_initial_at = due_initial_at


def annuler_rendez_vous_du_lead(lead, user, *, motif='',
                                vider_date_passee=True):
    """SUIVI E4/E21 (30/09/2026) — le rendez-vous de visite EN ATTENTE du
    lead est annulé : côté visites par LEUR service
    (``apps.visites.services.annuler_rendez_vous`` — frontière M3, jamais
    ``visites.models``), côté fiche ``Lead.visite_prevue_le`` est vidé.

    BEST-EFFORT : un module visites en échec ne bloque jamais le geste
    commercial qui a demandé l'annulation (il est déjà acté). Avec
    ``vider_date_passee=False``, une date de visite PASSÉE (la visite a eu
    lieu, ou non) reste sur la fiche : seul un rendez-vous à venir est une
    promesse faite au technicien. Renvoie le nombre de rendez-vous annulés
    dans le module visites."""
    annules = 0
    try:
        from apps.visites.services import annuler_rendez_vous

        annules = annuler_rendez_vous(lead, user, motif=motif)
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        logger.warning(
            'SUIVI E21 : rendez-vous de visite non annulé (lead #%s)',
            getattr(lead, 'pk', '?'), exc_info=True)
    jour = getattr(lead, 'visite_prevue_le', None)
    if jour is not None and (vider_date_passee
                             or jour >= aujourd_hui_local()):
        lead.visite_prevue_le = None
        lead.save(update_fields=['visite_prevue_le'])
    return annules


#: SUIVI E21 — les causes écrites (visite, message au technicien, chatter)
#: quand un arrêt de tout le suivi annule aussi le rendez-vous.
CAUSE_RDV_REFUS = 'le client a refusé'
CAUSE_RDV_NE_PLUS_CONTACTER = 'le client ne veut plus être contacté'


def cause_rdv_perdu(motif=''):
    """SUIVI E21 — la cause d'annulation d'un rendez-vous quand le lead
    passe PERDU (avec son motif s'il en a un)."""
    motif = str(motif or '').strip()
    return f'dossier perdu ({motif})' if motif else 'dossier perdu'


def annuler_rendez_vous_sur_arret(lead, user, *, cause):
    """SUIVI E21 (30/09/2026) — quand TOUT s'arrête (« Refus », « Perdu »,
    « Ne plus me contacter »), le rendez-vous de visite EN ATTENTE s'annule
    aussi.

    Avant, les relances s'arrêtaient mais la visite planifiée restait dans le
    module Visites : le technicien se serait déplacé chez un client qui venait
    de refuser. Même porte que E4 (``annuler_rendez_vous_du_lead``), avec
    ``vider_date_passee=False`` : une visite PASSÉE reste sur la fiche, c'est
    de l'historique. UNE note système le dit — seulement quand un rendez-vous
    a RÉELLEMENT été annulé (idempotent : un second arrêt ne trouve plus rien
    et n'écrit rien).

    BEST-EFFORT : ne lève jamais — l'arrêt qui l'a demandé est déjà acté.
    Renvoie le nombre de rendez-vous annulés dans le module visites."""
    try:
        if getattr(lead, 'pk', None):
            lead.refresh_from_db(fields=['visite_prevue_le'])
        jour = lead.visite_prevue_le
        annules = annuler_rendez_vous_du_lead(
            lead, user, motif=cause, vider_date_passee=False)
        date_retiree = jour is not None and lead.visite_prevue_le is None
        if annules or date_retiree:
            quand = f' du {jour:%d/%m/%Y}' if date_retiree else ''
            prevenu = ' (le technicien est prévenu)' if annules else ''
            # Note SYSTÈME (``user=None``) : dire ce que le moteur a fait
            # n'est pas un contact (garde QJ7).
            LeadActivity.objects.create(
                company=lead.company, lead=lead, user=None,
                kind=LeadActivity.Kind.NOTE,
                body=(f'Rendez-vous de visite{quand} annulé{prevenu} : '
                      f'{cause}.'))
        return annules
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        logger.warning(
            'SUIVI E21 : rendez-vous non annulé à l’arrêt (lead #%s)',
            getattr(lead, 'pk', '?'), exc_info=True)
        return 0


#: Longueur maximale de la note de retour terrain posée au chatter. Un
#: technicien consciencieux peut écrire beaucoup ; l'historique d'un lead doit
#: rester lisible. Le texte intégral reste sur la visite, jamais perdu.
RETOUR_VISITE_MAX = 1500


def _lignes_qualification(qualification):
    """Les lignes « Qualification : … » / « Conseil : … », ou une liste vide.

    Le vocabulaire et les libellés vivent dans ``apps.visites.qualification``
    (frontière M3 : on lit le module de l'app qui POSSÈDE ce vocabulaire, on ne
    redéclare pas une table de libellés qui dériverait au premier
    reformulage du fondateur). Best-effort : une qualification illisible ne
    fait jamais perdre le retour terrain qui la suit."""
    if not qualification:
        return []
    try:
        from apps.visites.selectors import conseil, phrase

        return [ligne for ligne in (phrase(qualification),
                                    conseil(qualification)) if ligne]
    except Exception:  # noqa: BLE001 — jamais bloquant
        logger.warning('VISITE-CADENCE: qualification illisible',
                       exc_info=True)
        return []


def composer_note_retour_visite(retour, auteur='', qualification=None):
    """La note de chatter du RETOUR TERRAIN, tronquée à ``RETOUR_VISITE_MAX``.

    La QUALIFICATION vient EN TÊTE (amendement fondateur n°2 du 15/09/2026) :
    c'est la ligne qu'un responsable lit en diagonale avant de rappeler —
    « Client chaud · Le devis convient · Décide seul · … ». Le conseil de
    closing la suit, puis le retour libre.

    Le texte libre du technicien EST l'information : « le tableau est saturé »,
    « accès par le garage » — rien de tout cela n'entre dans un récap de
    mesures, et c'est pourtant ce que le commercial doit lire avant de
    rappeler. Un retour muet le DIT (« sans commentaire ») plutôt que de poser
    une note vide qui ferait croire à un oubli d'affichage."""
    entete = 'Visite technique terminée'
    entete += f' par {auteur}.' if auteur else '.'
    notes = (retour or {}).get('notes') or ''
    lignes = _lignes_qualification(qualification)
    if notes.strip():
        lignes.append(f'{entete} Retour terrain : « {notes.strip()} »')
    else:
        lignes.append(f'{entete} Aucun commentaire écrit sur place.')
    for photo in (retour or {}).get('commentaires_photos') or []:
        commentaire = (photo.get('commentaire') or '').strip()
        if not commentaire:
            continue
        lignes.append(f'— {photo.get("slot") or ""} : {commentaire}')
    corps = '\n'.join(lignes)
    if len(corps) > RETOUR_VISITE_MAX:
        corps = corps[:RETOUR_VISITE_MAX - 1].rstrip() + '…'
    return corps


def _plan_du_debrief(qualification, lead=None):
    """``(clé, jours, rappel_choisi)`` du débrief, dictés par la
    qualification du terrain.

    Sans qualification, le comportement historique : « rappeler le client »,
    DEMAIN. Avec elle, c'est le terrain qui décide — il a vu le client :

    * le MOMENT vient de ``rappel`` (demain matin/soir ⇒ demain ; cette
      semaine ⇒ trois jours : le client a dit qu'il ne fallait pas le presser) ;
    * la NATURE vient de ``devis`` : à modifier ou à refaire ⇒ la prochaine
      chose à faire n'est plus de rappeler pour conclure, c'est de PRÉPARER le
      devis corrigé, et le libellé de l'étape le dit.

    Le troisième élément du tuple dit si le MOMENT est un choix EXPLICITE du
    terrain : lui seul autorise à déplacer un débrief déjà posé dans les deux
    sens (voir ``appliquer_retour_visite``).

    Lecture du vocabulaire par le module de l'app qui le possède (frontière
    M3). Best-effort : une qualification illisible retombe sur le défaut.

    PARAM-CADENCE — la NATURE est une clé (``debrief`` / ``devis_modifie``)
    et le moment PAR DÉFAUT est le ``delai_jours`` de son barreau « Visite
    technique » (demain par défaut) ; un moment choisi par le terrain le
    remplace."""
    def _defaut(cle):
        if lead is None:
            return gabarit_relance.barreau_par_defaut(
                cadence_config.CADENCE_DE_LA_CLE[cle], cle)['delai_jours']
        return _config_visite(lead, cle)['delai_jours']

    if not qualification:
        return CLE_DEBRIEF, _defaut(CLE_DEBRIEF), False
    try:
        from apps.visites.selectors import (
            devis_a_reprendre, jours_avant_rappel, rappel_explicite,
        )

        cle = (CLE_DEVIS_MODIFIE if devis_a_reprendre(qualification)
               else CLE_DEBRIEF)
        return (cle, jours_avant_rappel(qualification, defaut=_defaut(cle)),
                rappel_explicite(qualification))
    except Exception:  # noqa: BLE001 — jamais bloquant
        logger.warning('VISITE-CADENCE: plan de débrief non déduit',
                       exc_info=True)
        return CLE_DEBRIEF, _defaut(CLE_DEBRIEF), False


def _debrief_ouvert(lead):
    """L'étape de débrief encore à faire, quel que soit son LIBELLÉ.

    Elle est UNE : la chercher sous ses deux CLÉS est ce qui empêche une
    re-qualification (« finalement le devis est à modifier ») de laisser deux
    débriefs ouverts dans la file."""
    for cle in _CLES_DEBRIEF:
        etape = _etape_visite_ouverte(lead, cle)
        if etape is not None:
            return etape
    return None


def _requalifier_debrief(etape, cle, config=None):
    """RENOMME l'étape de débrief vers la nature ``cle`` (clé ET libellé
    configuré) plutôt que de la recréer : c'est la MÊME étape, dont la nature
    vient d'être précisée. No-op si elle l'a déjà."""
    if cle_de(etape) == cle:
        return etape
    config = config or _config_visite(etape.lead, cle)
    etape.cle = cle
    etape.libelle = config['libelle']
    etape.save(update_fields=['cle', 'libelle'])
    return etape


def appliquer_retour_visite(lead, user, retour, auteur='',
                            qualification=None):
    """Le technicien est reparti : son retour redescend, et on rappelle.

    1. UNE note de chatter portant, dans cet ordre, la QUALIFICATION du client
       (une ligne lisible en diagonale), le conseil de closing s'il y en a un,
       puis le TEXTE LIBRE du terrain (notes + un commentaire de photo par
       ligne, le tout tronqué) ;
    2. ``Lead.visite_effectuee`` est posé — via ``ecrire_retour_lead_visite``,
       donc avec ses garanties : idempotent, et une note écrite à la main dans
       ``visite_notes`` n'est JAMAIS écrasée ;
    3. le DÉBRIEF est calé sur ce que le terrain a rapporté
       (``_plan_du_debrief``) : DEMAIN par défaut, dans trois jours si le
       client a demandé « cette semaine », et son libellé devient « préparer le
       devis modifié » quand le devis doit être repris. Il existait déjà (posé
       à la planification) ? Il est RENOMMÉ si besoin et AVANCÉ seulement s'il
       était plus loin — jamais repoussé, jamais dupliqué. Il n'existe pas
       (visite faite sans avoir été planifiée dans l'ERP) ? On le pose, à
       condition que le lead soit encore relançable ;
    4. CAD28 — la reprise du PROTOCOLE est recalée sur CE retour plutôt que
       sur la date prévue de la visite (``reprendre_plan_apres_retour_visite``),
       et jamais tirée en avant.

    VISITE SANS DEVIS (décision fondateur du 24/09/2026 — « et même après ça
    rien ne se passe »). Quand aucun devis n'est parti (``aucun_devis_parti``)
    et que le terrain ne dit pas « devis à modifier / à refaire », la suite du
    retour n'est PAS un débrief « rappeler le client » — il n'y a encore rien
    à conclure — mais la tâche de PRODUCTION « Préparer et envoyer le devis
    (ou fixer un rappel) » (``poser_etape_preparer_devis``) : demain, ou au
    moment que le terrain a convenu devant le client. Le débrief posé à la
    planification est ANNULÉ (statut moteur), et la note du retour — elle
    seule, jamais une seconde — dit la suite et sa date. Renvoie alors
    l'étape devis.

    ``STAGES.py`` n'est pas touché. Renvoie l'étape de débrief, ou ``None``."""
    corps = composer_note_retour_visite(retour, auteur=auteur,
                                        qualification=qualification)
    # Relevé du 25/09/2026 — la visite a EU LIEU : une « Confirmer la visite
    # (veille) » encore ouverte (retour saisi avant que la confirmation soit
    # cochée) n'a plus d'objet. Annulée par le moteur (CKP1, jamais « sautée
    # par un humain »), comme le filet « planifier » l'est à la planification.
    lead.relance_etapes.filter(
        q_etape(CLE_CONFIRMATION),
        statut=RelanceEtape.Statut.A_FAIRE).update(
            statut=RelanceEtape.Statut.ANNULEE,
            note=NOTE_CONFIRMATION_VISITE_FAITE, traite_par=None,
            traite_le=timezone.now())
    cle, jours, rappel_choisi = _plan_du_debrief(qualification, lead)
    if (cle == CLE_DEBRIEF and _lead_relancable(lead)
            and aucun_devis_parti(lead)):
        etape = poser_etape_preparer_devis(
            lead, origine='retour de visite technique', user=user,
            jours=jours if rappel_choisi else None,
            journaliser=False)
        if etape is not None:
            debrief = _debrief_ouvert(lead)
            if debrief is not None:
                RelanceEtape.objects.filter(pk=debrief.pk).update(
                    statut=RelanceEtape.Statut.ANNULEE,
                    note=NOTE_RETOUR_SANS_DEVIS, traite_par=None,
                    traite_le=timezone.now())
            corps += ('\nSuite : préparer et envoyer le devis (pour le '
                      f'{etape.due_date:%d/%m/%Y}).')
            LeadActivity.objects.create(
                company=lead.company, lead=lead, user=None,
                kind=LeadActivity.Kind.NOTE, body=corps)
            ecrire_retour_lead_visite(lead, '')
            _recaler_file(lead, user)
            return etape
    LeadActivity.objects.create(
        company=lead.company, lead=lead, user=None,
        kind=LeadActivity.Kind.NOTE, body=corps)
    ecrire_retour_lead_visite(lead, '')

    if not _lead_relancable(lead):
        return None
    # CAD28 — la reprise du protocole part d'ICI, du retour réellement saisi,
    # et plus de la date PRÉVUE de la visite (voir
    # ``reprendre_plan_apres_retour_visite``). Best-effort : un recalage
    # impossible ne doit jamais faire échouer la redescente du terrain.
    try:
        reprendre_plan_apres_retour_visite(lead, user)
    except Exception:  # noqa: BLE001 — jamais bloquant pour le retour terrain
        logger.warning(
            'CAD28: reprise du plan non recalée sur le retour (lead #%s)',
            getattr(lead, 'pk', '?'), exc_info=True)
    vise = aujourd_hui_local() + datetime.timedelta(days=jours)
    config = _config_visite(lead, cle)
    existante = _debrief_ouvert(lead)
    if existante is not None:
        # RENOMMER plutôt que recréer : c'est la MÊME étape, dont la nature
        # vient d'être précisée par le terrain.
        _requalifier_debrief(existante, cle, config)
    if (existante is not None and existante.due_date <= vise
            and not rappel_choisi):
        # Sans choix EXPLICITE du terrain, un débrief déjà dû plus tôt n'est
        # jamais repoussé. Quand le terrain a convenu d'un moment DEVANT le
        # client (« cette semaine » = ne pas le presser), c'est SON choix qui
        # gagne — dans les deux sens : l'écran du wizard promet « le rappel
        # de closing se calera dessus », et rappeler avant le moment convenu
        # serait exactement la pression que le client a refusée.
        return existante
    etape = _poser_etape_visite(
        lead, cle=cle, ordre=VISITE_ORDRE_DEBRIEF, quand=vise,
        devis_id=_devis_id_de_la_cadence(lead), config=config)
    _recaler_file(lead, user)
    return etape
