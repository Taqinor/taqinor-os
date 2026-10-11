"""Clôture et annulation d'une touche (marquer fait, RLC1) (SPL13, extrait de crm/services.py : déplacement pur).

Module de type (a) de la scission : il n'importe ni ``.services`` ni un
module racine ; ``services`` réexporte ce qu'il faut (façade).
"""
import datetime
import logging

from django.utils import timezone

from . import activity, stages
from .cadence_config import CLE_DEVIS, CLE_DEVIS_MODIFIE, cle_de, est_etape
from .cadence_filet import assurer_prochaine_etape_apres_succes, poser_filet_visite_a_planifier
from .cadence_plan import (
    CadenceActiveConflit,
    ISSUES_CLIENT_JOINT,
    RaisonSuite,
    _lead_premier_argument,
    _prochaine_touche_a_faire,
    _recaler_file,
    _sous_verrou_du_lead,
    cloturer_cadence,
    initialiser_plan_relance,
    materialiser_touche_suivante,
)
from .cadence_reperes import (
    OUTCOME_VISITE_ACCEPTEE,
    VERBE_TOUCHE_SAUTEE,
    _ATTRIBUT_TOUCHE_CLOSE,
    _CANAL_VERS_KIND,
    _OUTCOMES_SANS_CLOTURE,
    est_etape_de_visite,
    prefixe_activite_touche,
    touche_traitee_en_avance,
)
from .fiche_funnel import appliquer_stage_lead, avancer_stage_devis_envoye_sur_touche
from .models import LeadActivity, RelanceEtape

logger = logging.getLogger(__name__)


def _lead_de_l_etape(etape, *args, **kwargs):
    return getattr(etape, 'lead', None)


# ── CAD-B ── CAD107 ─────────────────────────────────────────────────────────

@_sous_verrou_du_lead(_lead_premier_argument)
def reprendre_cadence_apres_reouverture(lead, user, *, origine=''):
    """CAD107 — UN seul comportement pour les trois chemins de réouverture.

    Un client PERDU qui revient est le meilleur signal d'achat qui existe, et
    il avait trois sorties différentes : le PATCH qui décoche « Perdu » ne
    déclenchait RIEN (seul le passage inverse était traité), le lot
    `unset_perdu` appelait le filet, et `reactivate_lead_on_new_touch` ne
    créait aucune `RelanceEtape`. Dans les trois cas la prise de contact ne
    pouvait de toute façon pas repartir (garde « déjà contacté ») : au mieux
    une étape nue.

    Le comportement unique REUTILISE la cadence RÉVEIL — jamais une nouvelle
    cadence (CADX), et c'est exactement ce à quoi elle sert : reprendre le
    contact d'un dossier mis de côté, sans rejouer six appels en quatorze
    jours à quelqu'un qu'on a déjà travaillé.

    Trois no-op délibérés :

    * une touche est DÉJÀ ouverte ⇒ rien. CADX interdit deux cadences en
      parallèle, et le dossier est déjà suivi ;
    * lead perdu, archivé, « ne plus contacter », signé ou au froid ⇒ rien :
      ce n'est pas une réouverture ;
    * une cadence plus prioritaire est active ⇒ `CadenceActiveConflit` est
      avalée, l'humain arrête d'abord (recette du 08/09).

    Rend la liste des touches posées (vide sur no-op).
    """
    if lead is None or not getattr(lead, 'pk', None):
        return []
    lead.refresh_from_db(
        fields=['stage', 'perdu', 'is_archived', 'ne_plus_contacter'])
    if (lead.perdu or lead.is_archived
            or getattr(lead, 'ne_plus_contacter', False)):
        return []
    if lead.stage in (stages.SIGNED, stages.COLD):
        return []
    if lead.relance_etapes.filter(
            statut=RelanceEtape.Statut.A_FAIRE).exists():
        return []
    try:
        etapes = initialiser_plan_relance(
            lead, user, cadence='reveil', depart=timezone.now())
    except CadenceActiveConflit:
        etapes = []
    if not etapes:
        # REPLI — société sans gabarit de réveil, ou conflit de cadence :
        # QJ-INVARIANT prime, un lead actif ne reste jamais sans prochaine
        # étape. Le filet pose alors ce qu'il sait poser.
        etape = assurer_prochaine_etape_apres_succes(lead, user)
        return [etape] if etape is not None else []
    LeadActivity.objects.create(
        company=lead.company, lead=lead, user=None,
        kind=LeadActivity.Kind.NOTE,
        body=('Dossier rouvert' + (f' ({origine})' if origine else '')
              + ' — cadence de reprise posée.'))
    return etapes


@_sous_verrou_du_lead(_lead_de_l_etape)
def marquer_etape_relance(etape, user, statut, note='', outcome='',
                          body='', suite=True, canal_reel=None):
    """Marque une ``RelanceEtape`` ``fait`` ou ``sautee`` (jamais un retour
    silencieux en arrière) : trace l'acteur/l'horodatage, journalise dans le
    chatter du lead, puis fait AVANCER ``Lead.relance_date`` vers la
    prochaine étape ``a_faire`` de CE plan (ou la vide si le plan est
    terminé) — garde ``sync_relance_activity`` en phase, jamais un second
    système de rappel concurrent.

    CKP2 — c'est aussi ICI que naît la touche SUIVANTE du protocole
    (``materialiser_touche_suivante``) quand la clôture n'est pas un succès :
    la cadence est RÉACTIVE, une touche à la fois, et c'est l'issue saisie qui
    programme le geste d'après.

    CAD-A (réponses de touche) — ``suite=False`` : l'APPELANT décide seul de
    ce qui vient après (« Ne plus me contacter » n'a pas de suite, « Question
    de prix » ou « Devis modifié » posent LEUR étape). Ni barreau suivant, ni
    clôture au froid, ni filet d'invariant : ces trois automatismes
    choisiraient une suite contraire à ce que le client vient de dire. La
    trace (touche close, ligne de chatter, issue) reste identique.

    SUIVI E16 (30/09/2026) — ``canal_reel`` : le canal par lequel la touche
    a RÉELLEMENT été faite quand il diffère du canal prévu (« Client joint au
    téléphone » sur une touche message). La ligne de chatter est alors typée
    selon ce canal réel (un APPEL abouti) : c'est elle que lisent le
    récepteur d'issue (MRY9 — la suite d'un appel abouti, jamais « il a
    répondu au message ») et le compteur de tentatives."""
    if statut not in (RelanceEtape.Statut.FAIT, RelanceEtape.Statut.SAUTEE):
        raise ValueError("Statut de relance invalide (fait ou sautee attendu).")

    # MRY11 × MRY9 — combien de touches de CETTE cadence restaient ouvertes
    # AVANT toute écriture, celle-ci exclue. Se le demander APRÈS était le
    # bug : marquer une touche de milieu de cadence « joint » déclenche le
    # récepteur `_arreter_cadence_on_outcome` (MRY9), qui passe TOUTES les
    # touches restantes à SAUTEE de façon SYNCHRONE sur le post_save de
    # l'activité — la question « reste-t-il une touche à faire ? » posée
    # ensuite répondait donc toujours « non », et le lead qu'on venait
    # justement de JOINDRE partait au froid, étiqueté injoignable, avec des
    # réveils J30/J60. La photo est prise avant, jamais après.
    restantes_avant = etape.lead.relance_etapes.filter(
        cadence=etape.cadence,
        statut=RelanceEtape.Statut.A_FAIRE,
    ).exclude(pk=etape.pk).count()

    etape.statut = statut
    etape.note = note or ''
    etape.traite_par = user
    etape.traite_le = timezone.now()
    # CAD118 — l'issue est écrite SUR la touche, au même instant que la ligne
    # d'historique ci-dessous. La ligne de chatter reste la source de vérité
    # du chatter ; cette colonne est ce qui rend mesurable « quelle touche, à
    # quelle heure, quel jour, sur quel canal joint réellement le client »
    # (CAD87) sans la fenêtre de rapprochement de deux minutes.
    etape.outcome = outcome or ''
    etape.save(update_fields=['statut', 'note', 'outcome', 'traite_par',
                              'traite_le'])

    verbe = ('faite' if statut == RelanceEtape.Statut.FAIT
             else VERBE_TOUCHE_SAUTEE)
    # SUIVI E16 — le canal RÉEL, quand la touche n'a pas été faite par le
    # canal prévu (le préfixe RLC2, seul relu ailleurs, ne change pas).
    canal_reel = (canal_reel or '').strip() or None
    if canal_reel == etape.canal:
        canal_reel = None
    canal_affiche = (f'{RelanceEtape.Canal(canal_reel).label} au lieu de '
                     f'{etape.get_canal_display()}' if canal_reel
                     else etape.get_canal_display())
    # MRY5 — le corps disait « Relance J+{ordre} », faux depuis que `ordre`
    # est un RANG dans la cadence et non plus un délai en jours (la touche 2
    # de la prise de contact tombe à J0 + 3 minutes, pas à J+2).
    corps = (f'{prefixe_activite_touche(etape)} '
             f'({canal_affiche}, cadence '
             f'{etape.cadence}) marquée {verbe}.')
    # CAD44 — une touche faite AVANT son échéance le dit dans le journal (sa
    # date réelle est `traite_le`) ; ce n'est pas une faute d'adhérence.
    if (statut == RelanceEtape.Statut.FAIT
            and touche_traitee_en_avance(etape)):
        corps += (' Traitée en avance (échéance du '
                  f'{etape.due_date:%d/%m/%Y}).')
    if body:
        corps += f' {body}'
    if note:
        corps += f" Note : {note}"
    # MRY10 — UNE SEULE ligne de chatter par touche, TYPÉE selon le canal
    # (jamais une note libre en plus d'une activité) : c'est elle que compte
    # le compteur de tentatives et que lisent les règles d'arrêt (MRY9).
    # SUIVI E16 — typée selon le canal RÉEL quand il diffère du prévu.
    kind = (_CANAL_VERS_KIND.get(canal_reel or etape.canal,
                                 LeadActivity.Kind.NOTE)
            if statut == RelanceEtape.Statut.FAIT
            else LeadActivity.Kind.NOTE)
    ligne = LeadActivity(
        company=etape.company, lead=etape.lead, user=user,
        kind=kind, body=corps, outcome=(outcome or ''))
    # SUIVI E22 (30/09/2026) — la touche close VOYAGE avec sa ligne de
    # chatter (attribut TRANSITOIRE, jamais une colonne) : le récepteur
    # d'issue MRY9, qui ne tient que l'activité, sait ainsi QUELLE touche
    # vient d'aboutir (``touche_close_de``) — sur la DERNIÈRE touche du
    # suivi de proposition, il pose « Décider la suite », jamais l'étape
    # devis d'un devis déjà parti.
    setattr(ligne, _ATTRIBUT_TOUCHE_CLOSE, etape)
    ligne.save(force_insert=True)

    lead = etape.lead
    # RELANCE-SUITE (08/09/2026) — LA détection « devis parti » : la touche
    # générique d'envoi du devis, sans issue. Hissée ici (une seule règle de
    # libellé) car DEUX consommateurs la lisent désormais : le filet plus bas
    # (démarrage du plan après-devis, comportement inchangé) et QJ-FUNNEL
    # juste en dessous (l'étape du funnel).
    # PARAM-CADENCE — reconnue par sa CLÉ (``devis``) : une société qui la
    # renomme « Faire le devis » garde « Fait » sans issue = devis parti.
    # SUIVI E13 (30/09/2026) — « Préparer le devis modifié — rappeler le
    # client » cochée FAITE sans issue vaut « devis parti », exactement comme
    # l'étape devis : c'est le devis MODIFIÉ qui part.
    touche_envoi_devis = not (outcome or '') and (
        (etape.cadence == 'generique' and est_etape(etape, CLE_DEVIS))
        or est_etape(etape, CLE_DEVIS_MODIFIE))
    # SUIVI E7 (30/09/2026) — « devis parti » seulement quand l'étape est
    # COCHÉE FAITE : une étape devis SAUTÉE n'a rien envoyé. Avant, le saut
    # passait `brouillon_compris` au filet et DÉMARRAIT le suivi de
    # proposition sans qu'aucun devis ne soit parti ; désormais le filet
    # applique sa ceinture (on ne re-pose jamais la touche close) et pose
    # « Décider la suite ».
    devis_parti = touche_envoi_devis and statut == RelanceEtape.Statut.FAIT
    # QJ-FUNNEL (fondateur 09/09/2026 — « when I do Fait for quote sent, it
    # should be at quote sent ») — cocher FAIT la touche d'envoi place le
    # lead à « Devis envoyé » sur-le-champ, quel que soit le reste du plan
    # (une touche SAUTÉE ne vaut jamais un envoi).
    if devis_parti:
        avancer_stage_devis_envoye_sur_touche(lead, user)
    # CKP2 — LA CADENCE RÉACTIVE : la touche suivante du protocole naît ICI,
    # de l'issue qu'on vient de saisir, et nulle part ailleurs.
    #   * FAIT sans issue d'arrêt (« pas de réponse » sur un appel, ou aucune
    #     issue sur un message/e-mail/visite) → le geste suivant est programmé.
    #   * SAUTÉE par un humain → idem : passer une touche ne doit pas éteindre
    #     la cadence, sinon sauter le message d'identité supprimait le reste du
    #     protocole.
    #   * « joint »/« intéressé »/« refus » → RIEN : le récepteur MRY9 vient
    #     d'ANNULER les touches restantes et le filet
    #     `assurer_prochaine_etape_apres_succes` pose la vraie suite.
    #   * « visite acceptée » → RIEN NON PLUS : le client a dit oui à un
    #     RENDEZ-VOUS, la seule suite utile est de le CALER. Le filet juste
    #     en dessous pose cette étape-là, jamais le barreau suivant du
    #     protocole (qui relancerait un client déjà conquis).
    # CAD1 — la condition se lit désormais AVEC la cadence de la touche :
    # « intéressé » n'arrête PAS le suivi de proposition, il en fait naître le
    # barreau suivant, exactement comme « pas de réponse ».
    suivante = None
    raison_suite = None
    if suite and (statut == RelanceEtape.Statut.SAUTEE
                  or issue_fait_naitre_la_suite(outcome, etape.cadence)):
        try:
            suivante, raison_suite = materialiser_touche_suivante(
                etape, user, avec_raison=True)
        except Exception:  # noqa: BLE001 — jamais bloquant pour le geste
            # ACRM12 — une panne n'est JAMAIS une fin de cadence : raison
            # INDÉTERMINÉE, le filet plus bas pose la suite (jamais le Froid).
            raison_suite = RaisonSuite.INDETERMINE
            logger.warning(
                'CKP2: touche suivante non matérialisée (étape #%s)',
                getattr(etape, 'pk', '?'), exc_info=True)
    # VISITE-CADENCE — « le client accepte la visite » : on pose LA seule
    # suite qui a du sens, planifier le passage du technicien. Sauf si un
    # rendez-vous est DÉJÀ calé (le client avait déjà sa date) — sinon cocher
    # deux fois l'issue empilerait deux rappels pour la même visite.
    if (statut == RelanceEtape.Statut.FAIT
            and (outcome or '') == OUTCOME_VISITE_ACCEPTEE):
        try:
            poser_filet_visite_a_planifier(
                lead, user, devis_id=etape.devis_id)
        except Exception:  # noqa: BLE001 — jamais bloquant pour le geste
            logger.warning(
                'VISITE-CADENCE: filet « planifier la visite » non posé '
                '(étape #%s)', getattr(etape, 'pk', '?'), exc_info=True)
    # ACRM37 — LE recalage unique de la file (``_recaler_file``).
    _recaler_file(lead, user)
    if not suite:
        # CAD-A — l'appelant pose (ou refuse) lui-même la suite.
        return etape
    # MRY11 — la cadence vient-elle de s'ÉPUISER ? Uniquement ici : une
    # cadence ARRÊTÉE (MRY9) n'est pas une cadence terminée, et clôturer un
    # lead qu'on vient de joindre serait exactement l'inverse du bon geste.
    # DEUX conditions, et aucune ne se lit après coup :
    #   * cette touche était bien la DERNIÈRE encore ouverte (photo prise
    #     avant l'écriture, cf. `restantes_avant`) ;
    #   * son issue n'est pas une issue de SUCCÈS — joindre, intéresser ou
    #     convenir d'un rappel ne clôt jamais un dossier au froid.
    # CKP2 — TROISIÈME condition, indispensable depuis la cadence réactive :
    # `restantes_avant == 0` est désormais VRAI à chaque touche (il n'y en a
    # jamais qu'une d'ouverte à la fois). Sans le `suivante is None`, le
    # premier « pas de réponse » du protocole aurait envoyé le lead au parking
    # étiqueté « Injoignable 6 appels » — après UN seul appel. La cadence n'est
    # épuisée que si le gabarit n'a plus rien à faire naître.
    # QUATRIÈME condition (décision fondateur du 24/09/2026 — « et même après
    # ça rien ne se passe ») : une étape de VISITE (planifier, confirmer,
    # débrief, devis modifié) n'est PAS un barreau du protocole, c'est un
    # geste posé À CÔTÉ de lui. Elle portait la cadence ``apres_devis`` et
    # aucune touche suivante ne naît d'elle : un débrief « pas de réponse »
    # épuisait donc la cadence et parquait le lead au FROID, étiqueté « Devis
    # sans suite », avec réveils J30/J60 — même sans aucun devis envoyé.
    # Jamais plus : c'est le filet ci-dessous (QJ-INVARIANT) qui prend le
    # relais — le plan s'il est pendant, sinon « Rappeler — dernier essai
    # avant de chiffrer » (``_FILET_SANS_REPONSE_PALIERS``), puis le devis.
    # ACRM12 (C-ACRM-007) — CINQUIÈME condition : la clôture n'a lieu que si
    # le gabarit est RÉELLEMENT épuisé (``RaisonSuite.FIN_GABARIT``, relu sur
    # les barreaux actifs). Un barreau désactivé, une panne, un barreau déjà
    # pris ou un lead hors relance ne parquent plus le lead au Froid.
    if (restantes_avant == 0 and suivante is None
            and raison_suite == RaisonSuite.FIN_GABARIT
            and (outcome or '') not in _OUTCOMES_SANS_CLOTURE
            and not est_etape_de_visite(etape)):
        cloturer_cadence(lead, user, etape.cadence)
    # QJ-INVARIANT (fondateur 07/09/2026, « fix this relance once and for
    # all ») — aucun geste de relance ne laisse un lead ACTIF sans prochaine
    # étape : si ni la cadence, ni la clôture MRY11 (parking Froid + réveils),
    # ni le récepteur MRY9 n'ont laissé de suite, le filet en pose une (plan
    # après-devis complet si un devis existe — l'étape générique « envoyer le
    # devis » traitée démarre ainsi le VRAI suivi de proposition — sinon une
    # étape générique). Ses gardes (signé/froid/perdu/archivé) décident
    # seules : la liste ne se termine que par Froid ou Signé.
    if _prochaine_touche_a_faire(lead) is None:
        # RELANCE-SUITE (08/09/2026) — seul le fait de COCHER l'étape
        # « préparer et envoyer le devis » vaut « devis parti » : elle seule
        # démarre le suivi de proposition sur un devis resté brouillon (cas
        # AR). Toute autre touche laissée sans suite reçoit une étape
        # générique — le suivi de proposition, lui, démarre à l'ENVOI.
        # (Détection hissée en tête de fonction — `devis_parti`, SUIVI E7 :
        # une étape devis SAUTÉE ne vaut jamais « devis parti ».)
        assurer_prochaine_etape_apres_succes(
            lead, user, brouillon_compris=devis_parti,
            libelle_touche_close=(etape.libelle or ''),
            # PARAM-CADENCE — la CLÉ de la touche close voyage avec elle : la
            # ceinture et l'escalier la lisent, jamais le libellé.
            cle_touche_close=cle_de(etape),
            # CAD3 — l'issue voyage avec le libellé : la ceinture doit pouvoir
            # distinguer « le client a demandé un rappel » d'un arbitrage.
            issue_touche_close=(outcome or '').strip(),
            # CAD2 — une étape de VISITE close (confirmer, débrief, devis
            # modifié, planifier) ne DÉMARRE jamais le suivi de proposition :
            # « Client joint » sur un débrief relançait tout le plan depuis
            # « Le PDF s'ouvre bien ? ». Le poursuivre reste permis (CAD1).
            # SUIVI E13 — sauf « devis modifié envoyé » : un devis part, son
            # suivi démarre (ou se poursuit).
            demarrer_plan=devis_parti or not est_etape_de_visite(etape))
    return etape


# ── RLC1 — ANNULER UNE TOUCHE TRAITÉE PAR ERREUR (retour arrière < 24 h) ─────
#
# Relevé fondateur du 08/09/2026 (lead test1 aa) : « une touche "Fait" par
# erreur ne se défait pas ». Ce qui manquait n'est pas un journal de plus —
# c'est le RETRAIT d'un geste, journalisé comme tout le reste.
#
# TROIS RÈGLES, et rien d'autre :
#   1. on ne défait QUE ce que le code PROUVE défaisable. Chaque effet annulé
#      ci-dessous est rattaché à sa clôture par une preuve datée (``created_at``
#      d'une étape née dans la fenêtre de la clôture, ``traite_le`` d'une touche
#      annulée par l'arrêt de cadence, entrée de chatter du mouvement d'étape) ;
#   2. un effet devenu irréversible donne un REFUS MOTIVÉ nommant le champ
#      fautif — jamais une annulation à moitié faite qui laisserait le plan
#      incohérent. Irréversibles : devis parti (le lead est passé « Devis
#      envoyé »), cadence clôturée (dossier parqué au Froid avec ses réveils),
#      lead signé ou perdu, touche suivante déjà traitée, étape du lead
#      déplacée depuis par quelqu'un d'autre ;
#   3. rien n'est EFFACÉ de l'historique : la ligne de chatter de la touche
#      reste (elle dit la vérité de ce qui a été saisi), et l'annulation AJOUTE
#      sa propre note système qui dit qui a annulé et ce qui a été défait.

#: RLC1 — au-delà, une touche traitée ne s'annule plus (« depuis moins de
#: 24 h »). Le contrôle est SERVEUR ; l'écran n'affiche le bouton que dans la
#: même fenêtre, jamais l'inverse.
ANNULATION_TOUCHE_HEURES = 24

#: RLC1 — largeur de la fenêtre qui RATTACHE un effet à la clôture qui l'a
#: produit. Toute la cascade de ``marquer_etape_relance`` (matérialisation de la
#: touche suivante, arrêt de cadence par le récepteur MRY9, filets, mouvement
#: d'étape du funnel) est SYNCHRONE dans la requête qui a coché la touche :
#: deux minutes sont une borne très large pour une requête HTTP, et assez
#: étroite pour ne pas attraper un geste ultérieur indépendant sur le lead.
_ANNULATION_FENETRE_EFFETS = datetime.timedelta(minutes=2)

#: RLC1 — les issues qui valent « le client a RÉPONDU » : ce sont elles qui
#: font avancer le funnel (récepteur QJ7). Si une AUTRE activité du lead en
#: porte une, l'avance d'étape est confirmée par ailleurs et l'annulation de
#: CETTE touche ne la défait pas (règle fondateur : « annulée si aucune autre
#: réponse ne l'a confirmée »).
_OUTCOMES_REPONSE_CONFIRMEE = ISSUES_CLIENT_JOINT


class AnnulationToucheRefusee(Exception):
    """RLC1 — refus MOTIVÉ d'une annulation de touche.

    Porte le CHAMP fautif et le message exact à afficher sous lui (règle
    fondateur du 08/09/2026) — jamais un « action impossible » générique qui
    laisserait l'utilisatrice deviner ce qui bloque."""

    def __init__(self, champ, message):
        super().__init__(message)
        self.champ = champ
        self.message = message


def _stage_depuis_libelle(valeur):
    """La clé d'étape STAGES.py derrière une valeur de chatter.

    Le chatter stocke le LIBELLÉ FR (``activity._display``) ; d'anciennes
    écritures portent la clé brute — les deux sont acceptées, comme le fait
    déjà la vérification d'annulation LB39. ``None`` si la valeur ne désigne
    aucune étape connue : on ne devine JAMAIS une étape."""
    brut = (valeur or '').strip()
    if not brut:
        return None
    if brut in stages.STAGES:
        return brut
    for cle, libelle in stages.STAGE_LABELS.items():
        if brut == libelle:
            return cle
    return None


def _activite_de_cloture(etape, *, debut, fin):
    """RLC1 — l'unique ligne de chatter que ``marquer_etape_relance`` a écrite
    pour CETTE clôture (celle qui porte son issue).

    Reconnue par son corps (« Touche « <libellé> » … ») dans la fenêtre de la
    clôture : c'est la seule activité de toute la cascade à porter un
    ``outcome``, ce qui permet de la distinguer d'une réponse saisie AILLEURS.
    ``None`` si elle est introuvable — l'appelant retombe alors sur la fenêtre,
    jamais sur une supposition."""
    return (etape.lead.activites
            .filter(created_at__gte=debut, created_at__lte=fin,
                    body__startswith=prefixe_activite_touche(etape))
            .order_by('created_at', 'pk').first())


def _defaire_avance_funnel(lead, user, mouvements, *, debut, fin, cloture):
    """RLC1 — défait l'avance d'étape produite par la clôture qu'on annule.

    ``mouvements`` = les entrées de chatter ``field='stage'`` écrites dans la
    fenêtre ``[debut, fin]`` de la clôture, dans l'ordre. L'étape est ramenée à
    l'``old_value`` du PREMIER mouvement : la chaîne entière (NEW → Contacté,
    puis le cran suivant si l'issue en a déclenché deux) se défait d'un coup,
    jamais à moitié.

    NE défait RIEN quand une AUTRE réponse confirmée du client existe sur le
    lead : l'avance tient alors de CELLE-LÀ, et la retirer effacerait un fait
    vrai (règle fondateur : « annulée si aucune autre réponse ne l'a
    confirmée »). « Autre » = toute activité à issue joint/intéressé saisie par
    un humain, sauf la ligne de la clôture elle-même (``cloture``) — à défaut de
    savoir laquelle c'est, toute la fenêtre de la clôture est écartée.

    Renvoie ``(ancienne_cle, nouvelle_cle)`` si l'étape a bougé, sinon
    ``None``. Passe par ``appliquer_stage_lead`` (point de passage canonique
    CRX20) : aucun déplacement d'étape muet."""
    if not mouvements:
        return None
    autres_reponses = lead.activites.filter(
        outcome__in=_OUTCOMES_REPONSE_CONFIRMEE, user__isnull=False)
    if cloture is not None:
        autres_reponses = autres_reponses.exclude(pk=cloture.pk)
    else:
        autres_reponses = autres_reponses.exclude(
            created_at__gte=debut, created_at__lte=fin)
    if autres_reponses.exists():
        return None
    cible = _stage_depuis_libelle(mouvements[0].old_value)
    if cible is None or cible == lead.stage:
        return None
    ancien = lead.stage
    if not appliquer_stage_lead(lead, cible, user=user):
        return None
    LeadActivity.objects.create(
        company=lead.company, lead=lead, user=user,
        kind=LeadActivity.Kind.MODIFICATION,
        field='stage', field_label='Étape',
        old_value=stages.STAGE_LABELS.get(ancien, ancien),
        new_value=stages.STAGE_LABELS.get(cible, cible),
        body='annulation de touche — avance automatique défaite')
    return ancien, cible


def annuler_touche_relance(etape, user):
    """RLC1 — Annule une touche « Fait »/« Sautée » traitée par erreur.

    La touche redevient ``a_faire`` à SON échéance d'origine (``due_at``/
    ``due_date`` n'ont jamais bougé — seuls statut, note et traçabilité de
    clôture sont retirés), et les effets automatiques de son issue sont défaits
    dans la mesure où le code les prouve défaisables :

      * les touches ANNULÉES par l'arrêt de cadence que cette issue a
        déclenché (récepteur MRY9, ``traite_par`` NULL + motif en note)
        redeviennent ``a_faire`` ;
      * l'étape que cette clôture a fait NAÎTRE — barreau suivant du protocole
        (``materialiser_touche_suivante``) ou étape de filet
        (``assurer_prochaine_etape_apres_succes`` / visite) — est supprimée ;
      * l'avance d'étape du funnel (NEW → Contacté, et le cran suivant s'il a
        été franchi dans le même geste) est défaite quand aucune AUTRE réponse
        du client ne l'a confirmée.

    Refus motivé (``AnnulationToucheRefusee``, champ + message exact) quand un
    effet n'est plus défaisable — voir le bloc de doctrine au-dessus.

    Journalise UNE note système (``user`` NULL — annuler est un geste tracé,
    pas une prise de contact ; le nom de l'auteur vit dans le texte) qui dit
    qui a annulé et ce qui a été défait. Renvoie la touche remise à faire."""
    from django.db import transaction

    if etape.statut not in (RelanceEtape.Statut.FAIT,
                            RelanceEtape.Statut.SAUTEE):
        raise AnnulationToucheRefusee(
            'statut',
            "Cette touche n'a pas été traitée par quelqu'un : il n'y a rien "
            'à annuler.')
    if etape.traite_le is None:
        raise AnnulationToucheRefusee(
            'traite_le',
            "Cette touche ne porte pas d'horodatage de traitement : son "
            "annulation ne peut pas être bornée aux "
            f'{ANNULATION_TOUCHE_HEURES} h.')
    if (timezone.now() - etape.traite_le
            > datetime.timedelta(hours=ANNULATION_TOUCHE_HEURES)):
        raise AnnulationToucheRefusee(
            'traite_le',
            f'Passé {ANNULATION_TOUCHE_HEURES} h, une touche traitée ne '
            "s'annule plus. Relancez la cadence depuis la fiche.")

    lead = etape.lead
    if lead.pk:
        lead.refresh_from_db(fields=['stage', 'perdu', 'ne_plus_contacter'])
    if lead.perdu:
        raise AnnulationToucheRefusee(
            'lead',
            'Ce lead est marqué perdu : rouvrez-le avant d\'annuler une '
            'touche de son plan.')
    if lead.ne_plus_contacter:
        # CAD5 — rouvrir des touches sur un client qui a demandé qu'on ne le
        # contacte plus violerait la garde dure (loi 09-08 art. 9 al. 2).
        # L'opposition se lève sur la FICHE, par un humain, jamais par un
        # retour arrière de touche.
        raise AnnulationToucheRefusee(
            'lead',
            'Ce lead est marqué « Ne plus contacter » : décochez la case sur '
            'la fiche avant d\'annuler une touche de son plan.')
    if lead.stage == stages.SIGNED:
        raise AnnulationToucheRefusee(
            'lead',
            'Ce lead est signé : les touches de son plan ne se rouvrent plus.')

    debut = etape.traite_le
    fin = debut + _ANNULATION_FENETRE_EFFETS
    # Ce que CETTE clôture a fait naître (preuve : l'horodatage de création).
    nees = lead.relance_etapes.filter(
        created_at__gte=debut, created_at__lte=fin).exclude(pk=etape.pk)
    if nees.filter(cadence='reveil').exists():
        raise AnnulationToucheRefusee(
            'statut',
            'Cette touche a clôturé la cadence : le dossier est parti au '
            'froid avec ses réveils. Utilisez « Relancer la cadence » sur la '
            'fiche plutôt que cette annulation.')
    if nees.exclude(statut=RelanceEtape.Statut.A_FAIRE).exists():
        raise AnnulationToucheRefusee(
            'statut',
            "L'étape programmée par cette touche a déjà été traitée : "
            "annuler celle-ci n'est plus possible.")

    mouvements = list(lead.activites.filter(
        kind=LeadActivity.Kind.MODIFICATION, field='stage',
        created_at__gte=debut, created_at__lte=fin,
    ).order_by('created_at', 'pk'))
    if any(_stage_depuis_libelle(m.new_value) == stages.QUOTE_SENT
           for m in mouvements):
        raise AnnulationToucheRefusee(
            'statut',
            "Cette touche a acté l'envoi du devis (le lead est passé « "
            f'{stages.STAGE_LABELS[stages.QUOTE_SENT]} ») : cet effet ne se '
            'défait pas ici.')
    if mouvements:
        arrivee = _stage_depuis_libelle(mouvements[-1].new_value)
        if arrivee is not None and lead.stage != arrivee:
            raise AnnulationToucheRefusee(
                'lead',
                "L'étape du lead a changé depuis : l'avance produite par "
                'cette touche ne peut plus être défaite.')

    with transaction.atomic():
        # L'ÉTAPE DU LEAD D'ABORD, les touches ensuite — l'ordre compte : un
        # retour vers COLD réveille le récepteur d'arrêt de cadence (MRY9 (b)),
        # qui n'annule que les touches encore À FAIRE. Défaire l'avance AVANT
        # de rouvrir les touches les met donc hors de sa portée ; l'inverse les
        # aurait refermées dans la seconde.
        mouvement_defait = _defaire_avance_funnel(
            lead, user, mouvements, debut=debut, fin=fin,
            cloture=_activite_de_cloture(etape, debut=debut, fin=fin))
        supprimees = sorted(
            (e.libelle or e.get_canal_display())
            for e in nees.only('libelle', 'canal'))
        nees.delete()
        # Les touches retirées du plan par l'ARRÊT de cadence déclenché par
        # cette issue : elles n'ont jamais été traitées par un humain
        # (`traite_par` NULL), leur motif vit en note — les deux repartent.
        restaurees = lead.relance_etapes.filter(
            statut=RelanceEtape.Statut.ANNULEE,
            traite_le__gte=debut, traite_le__lte=fin,
        ).update(statut=RelanceEtape.Statut.A_FAIRE, note='', traite_le=None)
        libelle = (etape.libelle or '').strip() or etape.get_canal_display()
        etape.statut = RelanceEtape.Statut.A_FAIRE
        etape.note = ''
        etape.traite_par = None
        etape.traite_le = None
        etape.save(update_fields=['statut', 'note', 'traite_par', 'traite_le'])
        # ACRM37 — LE recalage unique de la file.
        _recaler_file(lead, user)
        # JAMAIS un prénom en dur : l'auteur vient de la variable `user`.
        qui = getattr(user, 'username', '') or 'système'
        morceaux = [
            f'Annulation par {qui} : touche « {libelle} » '
            f'({etape.get_canal_display()}, cadence {etape.cadence}) remise '
            f'à faire au {etape.due_date:%d/%m/%Y}.']
        if restaurees:
            morceaux.append(
                f'{restaurees} touche(s) remise(s) à faire '
                "(arrêt de cadence défait).")
        if supprimees:
            morceaux.append(
                'Étape(s) programmée(s) par cette touche retirée(s) : '
                + ', '.join(f'« {s} »' for s in supprimees) + '.')
        if mouvement_defait:
            ancien, cible = mouvement_defait
            morceaux.append(
                'Étape du lead ramenée de « '
                f'{stages.STAGE_LABELS.get(ancien, ancien)} » à « '
                f'{stages.STAGE_LABELS.get(cible, cible)} ».')
        activity.log_note(lead, None, ' '.join(morceaux))
    return etape


# ── CAD-A ── CAD1 — « intéressé » poursuit le plan, il ne le rejoue pas ──────
#
#: Quelles cadences une ISSUE arrête — LA source unique, lue par le récepteur
#: MRY9 (``receivers._arreter_cadence_on_outcome``) comme par la
#: matérialisation réactive ci-dessous. Deux listes séparées auraient dérivé :
#: c'est précisément ce que CAD1 répare, puisque la matérialisation traitait
#: « intéressé » comme un arrêt TOTAL alors que le récepteur, lui, laissait
#: vivre le suivi de proposition.
#:
#: * ``joint`` / ``interesse`` → la PRISE DE CONTACT a atteint son but, et les
#:   réveils d'un dormant n'ont plus lieu d'être. Le suivi de PROPOSITION, lui,
#:   continue : un client joint reste à relancer sur son devis.
#: * ``refuse`` → tout s'arrête, y compris la proposition refusée. Le lead
#:   n'est PAS marqué perdu pour autant (MRY22 : décision humaine, avec motif).
#: * ``visite_acceptee`` (décision fondateur du 24/09/2026) → exactement comme
#:   ``joint`` : le client qui accepte la visite a atteint le but de la prise
#:   de contact, et un dormant qui l'accepte n'a plus à être réveillé. Le
#:   suivi de proposition continue (il se décale autour du rendez-vous,
#:   ``suspendre_plan_jusqu_apres_visite``). La suite n'est pas l'étape
#:   générique du filet mais « Planifier la visite technique convenue »
#:   (``poser_filet_visite_a_planifier``).
#: * SUIVI E15 (30/09/2026) — la DEUXIÈME AFFAIRE (CAD128, la prise de
#:   contact d'un client acquis) s'arrête exactement comme la prise de
#:   contact : « joint » posait l'étape de filet ET faisait naître le
#:   barreau 2 (deux touches ouvertes pour un client déjà joint).
CADENCES_ARRETEES_PAR_ISSUE = {
    'joint': ('contact', 'reveil', 'deuxieme_affaire'),
    'interesse': ('contact', 'reveil', 'deuxieme_affaire'),
    'refuse': ('contact', 'apres_devis', 'reveil', 'deuxieme_affaire'),
    OUTCOME_VISITE_ACCEPTEE: ('contact', 'reveil', 'deuxieme_affaire'),
}


def issue_fait_naitre_la_suite(outcome, cadence):
    """CAD1 — cette ISSUE, sur une touche de CETTE cadence, doit-elle faire
    naître le barreau suivant du protocole ?

    Trois cas, et rien d'autre :

    * « visite acceptée » → JAMAIS : le client a dit oui à un rendez-vous, la
      seule suite utile est de le caler (VISITE-CADENCE) ;
    * une issue qui ARRÊTE la cadence de la touche → non plus : le récepteur
      MRY9 vient d'annuler ce qui restait, et le filet pose la vraie suite ;
    * tout le reste (« pas de réponse », « à rappeler », aucune issue sur un
      message, et « intéressé »/« joint » sur le suivi de PROPOSITION que ces
      issues n'arrêtent pas) → oui, le geste suivant est programmé.
    """
    issue = (outcome or '').strip()
    if issue == OUTCOME_VISITE_ACCEPTEE:
        return False
    return cadence not in CADENCES_ARRETEES_PAR_ISSUE.get(issue, ())
