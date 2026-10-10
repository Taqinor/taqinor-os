"""Repères de la cadence : clés, libellés et prédicats (SPL8, extrait de crm/services.py : déplacement pur).

Module de type (a) de la scission : il n'importe ni ``.services`` ni un
module racine ; ``services`` réexporte ce qu'il faut (façade).
"""
import datetime

from django.utils import timezone

from apps.parametres import models_relance as gabarit_relance

from . import cadence_config, stages
from .cadence_config import (
    CLES_APRES_CONTACT,
    CLES_VISITE,
    CLE_DEBRIEF,
    CLE_DEVIS_MODIFIE,
    est_etape,
    q_etape,
)
from .leads_doublons import _strip_accents
from .models import LeadActivity, RelanceEtape


def _lead_porte_tag(lead, tag) -> bool:
    """``lead`` porte-t-il l'étiquette ``tag`` ?

    ``Lead.tags`` est un champ LIBRE (texte séparé par des virgules), saisi à
    la main : la comparaison ignore la casse ET les accents — « Decision a
    plusieurs » vaut « Décision à plusieurs »."""
    def _cle(valeur):
        return _strip_accents((valeur or '').strip()).casefold()

    cible = _cle(tag)
    if not cible:
        return False
    return any(_cle(morceau) == cible
               for morceau in (getattr(lead, 'tags', '') or '').split(','))


#: VISITE-CADENCE (fondateur 15/09/2026) — « le client accepte la visite ».
#: C'est une issue de SUCCÈS d'un genre nouveau : le client n'a ni signé ni
#: refusé, il a dit oui à un RENDEZ-VOUS. Le suivi de PROPOSITION ne
#: s'arrête donc PAS (la proposition reste à relancer si la visite tombe à
#: l'eau), mais poser le geste générique suivant du protocole serait absurde :
#: la seule chose à faire est de CALER la visite. Le filet ci-dessous s'en
#: charge.
#: Décision fondateur du 24/09/2026 — l'issue vaut sur TOUTE touche, prise de
#: contact et réveil compris : un client qui accepte la visite a atteint le
#: but de la prise de contact, exactement comme « joint » — ces deux cadences
#: s'arrêtent (``CADENCES_ARRETEES_PAR_ISSUE``, bas de fichier).
OUTCOME_VISITE_ACCEPTEE = 'visite_acceptee'


#: MRY10 — canal de la touche → type d'activité du chatter. Une touche traitée
#: doit laisser UNE ligne typée (appel/WhatsApp/e-mail), pas une note libre :
#: c'est elle que compte le compteur de tentatives (MRY20) et que lisent les
#: règles d'arrêt sur l'issue (MRY9). « visite » n'a pas de type dédié — elle
#: reste une NOTE, faute de mieux, plutôt qu'un type inventé.
_CANAL_VERS_KIND = {
    RelanceEtape.Canal.APPEL: LeadActivity.Kind.APPEL,
    RelanceEtape.Canal.WHATSAPP: LeadActivity.Kind.WHATSAPP,
    RelanceEtape.Canal.EMAIL: LeadActivity.Kind.EMAIL,
    RelanceEtape.Canal.VISITE: LeadActivity.Kind.NOTE,
}

# ── CAD-K ── CAD131 — la première TENTATIVE n'est pas le premier CONTACT ────
#
# Audit L3 du 21/09/2026. ``first_contacted_at`` était posé dès qu'une note,
# un appel, un e-mail ou un WhatsApp était écrit par un humain — or SAUTER une
# touche écrit une NOTE signée par le commercial. Sauter la toute première
# touche satisfaisait donc la promesse client (« rappelé en moins de N
# minutes ») ET éteignait l'escalade, qui n'agit que sur les leads SANS
# horodatage : personne ne parlait au client, et plus rien ne le signalait.
#
# Le verbe est hissé en CONSTANTE pour que la reconnaissance vive à UN SEUL
# endroit, celui qui ÉCRIT la note — jamais un texte deviné ailleurs (même
# discipline que les préfixes du journal RLC2).
VERBE_TOUCHE_SAUTEE = 'sautée'
MENTION_TOUCHE_SAUTEE = f'marquée {VERBE_TOUCHE_SAUTEE}.'


def touche_traitee_en_avance(etape):
    """CAD44 — cette touche a-t-elle été TRAITÉE AVANT son échéance (jour local
    Casablanca de ``traite_le`` antérieur à ``due_date``) ?

    Décision fondateur du 21/09/2026 : agir en avance est permis (appeler,
    écrire, reporter), et une touche faite avant son jour n'est PAS une faute
    d'adhérence (``selectors._a_lheure``, CAD22). Le serveur la marque à sa
    date RÉELLE et le chatter le dit ; le reste du plan ne bouge pas (les
    barreaux suivants restent datés depuis l'ancre ``cadence_depart``)."""
    from . import horaires

    if etape is None or etape.traite_le is None or etape.due_date is None:
        return False
    return (etape.traite_le.astimezone(horaires.CASABLANCA).date()
            < etape.due_date)


def est_note_de_touche_sautee(activite):
    """CAD131 — cette ligne de chatter est-elle la note d'une touche SAUTÉE ?

    Une touche sautée n'est PAS une tentative : rien n'est sorti vers le
    client. Seule cette note doit être écartée du premier contact — une note
    ordinaire écrite à la main par la commerciale (« Appelé, pas de réponse »)
    reste un contact, comme depuis MRY19.
    """
    if activite is None:
        return False
    if getattr(activite, 'kind', None) != LeadActivity.Kind.NOTE:
        return False
    return MENTION_TOUCHE_SAUTEE in (getattr(activite, 'body', '') or '')


# ── COCKPIT-CONTRÔLE B4 — un REPORT n'est pas un premier contact ────────────
#
# Même trou que CAD131, par une autre porte : « Reporter » (et « Mettre en
# veille ») écrit une NOTE signée par la commerciale — « Rappel demandé le … —
# touche « … » reportée. » — et le récepteur QJ7 la prenait pour une
# tentative : reporter la toute première touche d'un lead neuf horodatait
# ``first_contacted_at`` et ÉTEIGNAIT l'escalade, sans que personne ait parlé
# au client. Les textes sont hissés en CONSTANTES, utilisées pour ÉCRIRE les
# notes (``reporter_prochaine_touche``, ``_veille_simple``,
# ``_basculer_veille_en_reveil``) et pour les RECONNAÎTRE — jamais un texte
# deviné ailleurs.
PREFIXE_NOTE_REPORT = 'Rappel demandé le '
FIN_NOTE_REPORT = ' reportée.'
PREFIXE_NOTE_VEILLE = 'Mise en veille '


def est_note_de_report(activite):
    """COCKPIT-CONTRÔLE B4 — cette ligne de chatter est-elle la note d'un
    REPORT de touche ou d'une MISE EN VEILLE ?

    Un report déplace le PLAN, rien ne sort vers le client : cette note ne
    pose pas ``first_contacted_at`` (même patron que
    ``est_note_de_touche_sautee``). Une note ordinaire de la commerciale, et
    la ligne TYPÉE d'une réponse « Plus tard » (un vrai échange, issue « à
    rappeler »), restent des contacts."""
    if activite is None:
        return False
    if getattr(activite, 'kind', None) != LeadActivity.Kind.NOTE:
        return False
    corps = getattr(activite, 'body', '') or ''
    return ((corps.startswith(PREFIXE_NOTE_REPORT)
             and corps.endswith(FIN_NOTE_REPORT))
            or corps.startswith(PREFIXE_NOTE_VEILLE))


#: MRY11 × MRY9 — les issues qui INTERDISENT la clôture, même sur la dernière
#: touche : on a joint la personne (ou on est convenu d'un rappel). La mettre
#: au froid et l'étiqueter « injoignable » serait l'inverse du bon geste.
#: B1 (revue Fable 07/09/2026) — ``refuse`` aussi : le client a RÉPONDU.
#: Clôturer l'étiquetterait « Injoignable » et lui enverrait des réveils
#: J30/J60 « vous étiez injoignable » ; le filet « décider la suite » (posé
#: par le récepteur MRY9) assure déjà la suite du dossier.
#: VISITE-CADENCE — « visite acceptée » aussi, évidemment : envoyer au parking
#: Froid, étiqueté « Injoignable », un client qui vient d'accepter de recevoir
#: le technicien chez lui serait l'erreur la plus grossière du moteur.
_OUTCOMES_SANS_CLOTURE = frozenset({'joint', 'interesse', 'rappel', 'refuse',
                                    OUTCOME_VISITE_ACCEPTEE})


#: MRY11 — ce que devient un lead dont la cadence s'est épuisée sans réponse.
#: Le tag NOMME la raison : « injoignable » et « devis sans suite » ne se
#: traitent pas de la même façon au réveil.
#: « 6 appels » et non « 7 tentatives » : le Protocole v3 compte SIX appels
#: (plus cinq WhatsApp) — l'étiquette affichée à Meryem doit dire ce que la
#: cadence a réellement fait. Migration 0093 pour l'existant.
_CLOTURE_TAG_INJOIGNABLE = 'Injoignable 6 appels'
#: SUIVI E26 (décision fondateur du 30/09/2026) — la cadence COURTE « deuxième
#: affaire » (CAD128, un message et un appel) s'épuise comme la prise de
#: contact : parking Froid + réveils. Son étiquette dit ce que CETTE cadence a
#: réellement fait — jamais « 6 appels », elle n'en compte qu'un.
_CLOTURE_TAG_DEUXIEME_AFFAIRE = 'Deuxième affaire sans réponse'
_CLOTURE_TAGS = {
    'contact': _CLOTURE_TAG_INJOIGNABLE,
    'apres_devis': 'Devis sans suite',
    'deuxieme_affaire': _CLOTURE_TAG_DEUXIEME_AFFAIRE,
}

#: MRY11 — étape la plus AVANCÉE qu'une cadence puisse encore parquer.
#: `_bulk_stage_allowed` autorise « vers COLD » depuis N'IMPORTE OÙ (c'est
#: voulu pour une mise au parking manuelle) : sans ce plafond, épuiser une
#: cadence `contact` sur un lead qui a depuis SIGNÉ le ferait retomber au
#: froid — un devis signé effacé par un rappel resté ouvert.
_CLOTURE_PLAFOND = {
    'contact': stages.CONTACTED,
    'apres_devis': stages.FOLLOW_UP,
    # SUIVI E26 — la deuxième affaire est la prise de contact d'un client
    # acquis qui revient (une fiche NEUVE) : même plafond que ``contact``.
    # Avant, sa dernière touche sans réponse posait « Préparer et envoyer le
    # devis » le lendemain — un chiffrage réclamé pour quelqu'un que personne
    # n'avait eu au téléphone, alors que le guide annonçait le Froid.
    'deuxieme_affaire': stages.CONTACTED,
}

#: SUIVI E19 — le motif écrit sur une étape de filet annulée parce que le
#: dossier part au parking Froid (``cloturer_cadence``).
MOTIF_PARQUE_AU_FROID = 'dossier parqué au Froid'


#: MRY34 — libellé du FILET « client joint » : l'étape unique posée quand une
#: cadence s'arrête sur une issue de SUCCÈS (joint/intéressé) sans qu'aucune
#: autre étape ne reste ouverte. Sans elle, le lead qu'on venait de JOINDRE
#: disparaissait de toutes les vues de relance (incident du 07/09/2026 : onze
#: touches barrées « joint », plus AUCUNE prochaine étape) — l'inverse exact
#: de MRY11, qui ne parque au froid que les cadences épuisées SANS réponse.
#: RELANCE-SUITE (fondateur 08/09/2026, lead test1 aa) — l'ancien libellé,
#: encore porté par les étapes posées avant le 08/09 : coché, il vaut « devis
#: parti » exactement comme le nouveau.
#:
#: PARAM-CADENCE (décision fondateur du 25/09/2026) — ces libellés sont
#: désormais les DÉFAUTS LIVRÉS du gabarit « Après l'appel (avant devis) »
#: de Paramètres (``apps/parametres/models_relance.py``, source unique) : une
#: société peut les renommer. Le moteur ne compare plus JAMAIS un libellé —
#: il reconnaît une étape par sa CLÉ (``cadence_config.est_etape``). Les noms
#: ci-dessous restent des alias des défauts, pour les lecteurs historiques.
_FILET_JOINT_LIBELLE_ANCIEN = cadence_config.LIBELLE_DEVIS_ANCIEN
FILET_JOINT_LIBELLE = gabarit_relance.LIBELLE_DEVIS

#: RELANCE-SUITE — le client a RÉPONDU à un MESSAGE (WhatsApp, e-mail) : la
#: suite est de L'APPELER, au prochain créneau d'appel — jamais le suivi de
#: proposition avant qu'un devis soit parti (« je fais le devis, je l'envoie,
#: PUIS vos étapes viennent »).
FILET_APPEL_LIBELLE = gabarit_relance.LIBELLE_APPEL_APRES_REPONSE
_KINDS_MESSAGE = frozenset({LeadActivity.Kind.WHATSAPP, LeadActivity.Kind.EMAIL})

#: QJ-INVARIANT — libellé du filet après un REFUS (téléphonique ou de devis) :
#: la suite d'un refus est une décision HUMAINE (MRY22), mais le dossier ne
#: doit pas disparaître des files en attendant qu'elle soit prise.
FILET_REFUS_LIBELLE = gabarit_relance.LIBELLE_DECIDER_SUITE

#: CAD3 — le filet posé après un RAPPEL CONVENU. « Rappelle-moi la semaine
#: prochaine » est la réponse la plus fréquente avant décision : la ceinture
#: anti-tapis-roulant renommait pourtant l'étape « Décider la suite — perdu
#: (motif) ou relance ultérieure », c'est-à-dire un arbitrage, là où le client
#: a seulement demandé du temps. Le nom de l'étape doit dire la vérité.
FILET_RAPPEL_LIBELLE = gabarit_relance.LIBELLE_RAPPEL_CONVENU

#: CAD102 — les deux paliers de « il a écrit, puis il ne décroche plus ».
#: L'appel du filet resté sans réponse envoyait directement sur « préparer et
#: envoyer le devis » : l'ERP réclamait un chiffrage pour quelqu'un que
#: personne n'avait jamais eu au téléphone. On tente d'abord de le JOINDRE —
#: un message pour convenir d'un créneau, puis un dernier appel — et seulement
#: ensuite on parle de devis. Ce sont des étapes de FILET, pas des barreaux du
#: protocole : le nombre de touches de la cadence ne bouge pas.
FILET_MESSAGE_CRENEAU_LIBELLE = gabarit_relance.LIBELLE_MESSAGE_CRENEAU
FILET_DERNIER_APPEL_LIBELLE = gabarit_relance.LIBELLE_DERNIER_APPEL

#: CAD54 — la touche qui DIT au client que son dossier change de mains. C'est
#: une étape de FILET (posée par le moteur, hors protocole), déclarée ici avec
#: ses sœurs pour que `_LIBELLES_FILET` la connaisse sans second littéral.
PASSATION_LIBELLE = 'Passation — prévenir le client du changement de conseiller'

#: CAD7 — le client NÉGOCIE le prix : le suivi de proposition se met en PAUSE
#: le temps de préparer l'appel du fondateur. Étape de FILET (posée par le
#: moteur, hors protocole) : la traiter rouvre le suivi au barreau suivant
#: (CAD1). Aucun texte d'offre n'y est attaché — l'offre ne part JAMAIS avant
#: la décision du fondateur (CAD60).
QUESTION_PRIX_LIBELLE = (
    'Question de prix — préparer l’appel du fondateur (aucune offre avant '
    'sa décision)')

#: CKP2 — les libellés des étapes POSÉES PAR LE FILET. Elles portent la
#: cadence `generique` sans être un barreau du gabarit `generique` : leur suite
#: est décidée par `assurer_prochaine_etape_apres_succes`, jamais par la
#: matérialisation réactive (`materialiser_touche_suivante` les ignore).
#: PARAM-CADENCE — les deux étapes HORS gabarit (passation, question de prix)
#: n'ont pas de clé : elles restent reconnues par leur libellé, qui n'est pas
#: réglable.
_LIBELLES_FILET_HORS_GABARIT = frozenset({
    PASSATION_LIBELLE,  # CAD54
    QUESTION_PRIX_LIBELLE,  # CAD7
})
#: Les libellés PAR DÉFAUT des étapes de filet (les étapes posées avant la
#: clé en portent un) — un lecteur ne s'en sert plus pour RECONNAÎTRE une
#: étape (``est_etape_de_filet``/``q_filet``), seulement pour les nommer.
_LIBELLES_FILET = (cadence_config.libelles_par_defaut(*CLES_APRES_CONTACT)
                   | _LIBELLES_FILET_HORS_GABARIT)

# ── VISITE-CADENCE — LES TROIS GESTES DU RENDEZ-VOUS ────────────────────────
#
# Doctrine fondateur (15/09/2026) : la visite technique n'est pas un préalable
# à l'étude, c'est un OUTIL DE CLOSING posé APRÈS l'envoi du devis, pendant que
# le client est chaud. Le suivi doit donc RÉAGIR à elle — et jusqu'ici il
# l'ignorait complètement : une visite pouvait être calée, faite, validée, sans
# qu'une seule touche de relance bouge.
#
# Trois libellés, trois moments, et rien de plus :
#   1. le client a dit oui au principe → CALER la date ;
#   2. la date est posée → la CONFIRMER la veille (le premier motif
#      d'échec d'une visite terrain est un client absent) ;
#   3. le technicien est reparti → RAPPELER dans les 24-48 h, quand tout est
#      encore frais. C'est le geste que la visite existe pour provoquer.
#: PARAM-CADENCE — défauts livrés du gabarit « Visite technique » de
#: Paramètres (source unique), réglables par société ; alias historiques.
VISITE_FILET_LIBELLE = gabarit_relance.LIBELLE_PLANIFIER
VISITE_CONFIRMATION_LIBELLE = gabarit_relance.LIBELLE_CONFIRMATION
VISITE_DEBRIEF_LIBELLE = gabarit_relance.LIBELLE_DEBRIEF

#: AMENDEMENT FONDATEUR n°2 (15/09/2026) — quand le terrain rapporte que le
#: devis est « à modifier » ou « à refaire », le débrief change de NATURE : la
#: prochaine chose à faire n'est plus de rappeler pour conclure, c'est de
#: PRÉPARER le devis corrigé. L'étape porte donc un autre libellé — et c'est
#: l'envoi du nouveau devis qui déclenchera sa propre cadence, par la mécanique
#: existante ; rien n'est câblé ici pour ça.
VISITE_DEVIS_LIBELLE = gabarit_relance.LIBELLE_DEVIS_MODIFIE

#: Les deux libellés PAR DÉFAUT que peut porter l'étape de débrief. Elle est
#: UNE, quelle que soit sa nature : la retrouver par ses DEUX clés (et jamais
#: par une seule) est ce qui empêche une re-qualification de laisser deux
#: débriefs dans la file.
_LIBELLES_DEBRIEF = (VISITE_DEBRIEF_LIBELLE, VISITE_DEVIS_LIBELLE)
_CLES_DEBRIEF = (CLE_DEBRIEF, CLE_DEVIS_MODIFIE)

#: Les libellés PAR DÉFAUT des quatre gestes de visite (lecteurs historiques
#: seulement : la reconnaissance passe par ``est_etape_de_visite``).
_LIBELLES_VISITE = cadence_config.libelles_par_defaut(*CLES_VISITE)


def est_etape_de_visite(etape):
    """PARAM-CADENCE — un des gestes du rendez-vous de visite (planifier,
    confirmer, débrief, devis modifié), reconnu par sa CLÉ."""
    return est_etape(etape, *CLES_VISITE)


def q_visite():
    """``est_etape_de_visite`` en requête."""
    return q_etape(*CLES_VISITE)


def q_filet():
    """``est_etape_de_filet`` en requête : les étapes du gabarit « Après
    l'appel » (par clé, ou libellé par défaut) et les deux hors gabarit."""
    from django.db.models import Q

    return (q_etape(*CLES_APRES_CONTACT)
            | Q(cle='', libelle__in=tuple(_LIBELLES_FILET_HORS_GABARIT)))


def q_etape_moteur():
    """Toute étape posée par le moteur À CÔTÉ du protocole (filet ou
    visite) — jamais un barreau de gabarit de plan."""
    return q_filet() | q_visite()


def annuler_etapes_moteur_ouvertes(lead, *cles, note):
    """SUIVI-PARCOURS — ANNULE (statut moteur CKP1 : ``traite_par`` NULL, le
    motif dans ``note``) les étapes moteur encore ouvertes de ces CLÉS —
    reconnues par la clé, ou le libellé par défaut d'une étape posée avant
    la clé (``q_etape``). Une étape qui a rempli son office n'est jamais
    « sautée par un humain ». Renvoie le nombre d'étapes annulées."""
    if not cles:
        return 0
    return lead.relance_etapes.filter(
        q_etape(*cles), statut=RelanceEtape.Statut.A_FAIRE,
    ).update(statut=RelanceEtape.Statut.ANNULEE, note=(note or '')[:500],
             traite_par=None, traite_le=timezone.now())


def _canal_configure(config):
    """Le canal RÉEL d'une étape configurée — un gabarit réglé sur
    « visite » (canal de barreau historique) devient un appel (CAD58)."""
    canal = config.get('canal') or RelanceEtape.Canal.APPEL
    return (RelanceEtape.Canal.APPEL if canal == RelanceEtape.Canal.VISITE
            else canal)


def _echeance_configuree(lead, config, *, depuis=None, jours=None):
    """PARAM-CADENCE — l'échéance d'une étape de FILET configurée :
    ``depuis`` (maintenant) + ``delai_jours`` (ou ``jours`` imposé par
    l'appelant — le moment convenu devant le client) + ``delai_minutes`` ;
    ``heure_cible`` posée REMPLACE l'heure calculée, puis recalage sur la
    fenêtre du canal (même règle que ``calculer_echeances_cadence``, MRY8 /
    CAD21). Une étape ne naît jamais déjà échue (CAD22)."""
    from . import cadence_temps, horaires

    maintenant = timezone.now()
    base = depuis or maintenant
    delai = config['delai_jours'] if jours is None else jours
    vise = base + datetime.timedelta(
        days=delai, minutes=config.get('delai_minutes') or 0)
    heure = config.get('heure_cible')
    if heure is not None:
        vise = vise.astimezone(horaires.CASABLANCA).replace(
            hour=heure.hour, minute=heure.minute, second=0, microsecond=0)
    canal = _canal_configure(config)
    # D1 — un barreau moteur peut porter `dimanche_ok`/`samedi_ok` (réglé
    # depuis Paramètres, exactement comme un barreau du protocole) : sans ces
    # deux drapeaux, `prochain_creneau_appel` recale toujours sur le lundi,
    # même quand la société a explicitement ouvert le samedi ou le dimanche à
    # cette étape (même règle que `calculer_echeances_cadence`).
    echeance = horaires.prochain_creneau_appel(
        vise, lead.company, canal=canal, heure_cible=heure,
        dimanche=bool(config.get('dimanche_ok')),
        samedi=bool(config.get('samedi_ok')))
    if echeance < maintenant:
        # ACRM36 — les drapeaux du barreau voyagent jusqu'au recalage.
        echeance = cadence_temps.echeance_jamais_echue(
            echeance, company=lead.company, canal=canal,
            samedi=bool(config.get('samedi_ok')), heure_cible=heure)
    return echeance


def _jour_de_visite_configure(lead, config, jour):
    """L'échéance d'un geste de VISITE, ancré sur un JOUR (``date``) :
    ``heure_cible`` du barreau (09 h sinon) + ``delai_minutes``, recalé sur
    la fenêtre du canal."""
    from . import horaires

    heure = config.get('heure_cible') or datetime.time(9, 0)
    vise = datetime.datetime.combine(
        jour, heure, tzinfo=horaires.CASABLANCA) + datetime.timedelta(
            minutes=config.get('delai_minutes') or 0)
    # D1 — même garde-fou que `_echeance_configuree` : un barreau de visite
    # marqué `dimanche_ok`/`samedi_ok` doit tenir sa fenêtre, pas retomber sur
    # le lundi.
    return horaires.prochain_creneau_appel(
        vise, lead.company, canal=_canal_configure(config),
        heure_cible=config.get('heure_cible'),
        dimanche=bool(config.get('dimanche_ok')),
        samedi=bool(config.get('samedi_ok')))


#: Ces trois étapes portent la cadence ``apres_devis`` (elles suivent bien la
#: proposition, et l'écran les affiche dans la même frise) mais ne sont PAS des
#: barreaux du gabarit : leur ``ordre`` est délibérément HORS de la plage du
#: gabarit (1-10) pour qu'aucune matérialisation réactive ne puisse les
#: confondre avec un barreau, et pour qu'elles se rangent après lui à
#: échéance égale.
VISITE_ORDRE_CONFIRMATION = 90
VISITE_ORDRE_DEBRIEF = 91
VISITE_ORDRE_FILET = 92

#: La cadence dans laquelle vivent les trois gestes ci-dessus. NOMMÉE une fois
#: : le jour où le fondateur voudra une cadence « visite » distincte, il y a UN
#: endroit à changer.
VISITE_CADENCE = 'apres_devis'

#: Délai (jours) du filet : DEMAIN, recalé sur le prochain créneau d'appel de
#: la société (fenêtres MRY4). Si Meryem donne une date de rappel en marquant
#: la touche, `reporter_prochaine_touche` déplace ce filet sur SA date — le
#: J+1 n'est que le défaut quand aucune date n'est saisie.
FILET_JOINT_DELAI_JOURS = 1


def prefixe_activite_touche(etape):
    """RLC2 — le PRÉFIXE de la ligne de chatter d'une touche CLÔTURÉE.

    Écrit par ``marquer_etape_relance``, relu par l'annulation (RLC1) et par le
    journal du plan (``selectors.journal_relance``, qui apparie une touche avec
    l'ISSUE saisie à sa clôture). Même raison que
    ``prefixe_activite_message_ouvert`` : trois littéraux identiques auraient
    dérivé, et l'appariement se serait tu sans qu'aucune garde ne rougisse."""
    libelle = (etape.libelle or '').strip() or etape.get_canal_display()
    return f'Touche « {libelle} »'


#: SUIVI E22 — l'attribut TRANSITOIRE (jamais une colonne) par lequel la
#: ligne de chatter d'une touche close porte LA touche jusqu'aux récepteurs
#: de ``post_save`` (MRY9). Une seule source : écrit par
#: ``marquer_etape_relance``, relu par ``touche_close_de``.
_ATTRIBUT_TOUCHE_CLOSE = '_touche_close'


def touche_close_de(activite):
    """SUIVI E22 — la touche dont ``activite`` est la ligne de CLÔTURE, telle
    que ``marquer_etape_relance`` vient de l'écrire ; ``None`` pour toute
    autre ligne (journal d'appel de la fiche, note, ligne relue en base) —
    le récepteur retombe alors sur son comportement ordinaire."""
    return getattr(activite, _ATTRIBUT_TOUCHE_CLOSE, None)


def est_cloture_d_etape_visite(activite):
    """CAD2 — cette ligne de chatter est-elle la CLÔTURE d'une étape de visite
    (planifier, confirmer, débrief, devis modifié) ?

    Relue par le récepteur d'issue (MRY9), qui ne tient que l'activité : c'est
    le PRÉFIXE écrit par ``marquer_etape_relance`` (``prefixe_activite_touche``,
    source unique RLC2) qui dit de quelle touche elle vient — jamais un
    littéral recopié."""
    corps = getattr(activite, 'body', '') or ''
    if any(corps.startswith(
            prefixe_activite_touche(RelanceEtape(libelle=libelle)))
           for libelle in _LIBELLES_VISITE):
        return True
    # PARAM-CADENCE — une étape de visite RENOMMÉE par la société porte son
    # propre libellé : on relit les étapes de visite À CLÉ déjà traitées de
    # CE lead (quelques lignes, une requête) plutôt que de deviner.
    lead_id = getattr(activite, 'lead_id', None)
    if not corps.startswith('Touche « ') or lead_id is None:
        return False
    etapes = (RelanceEtape.objects
              .filter(lead_id=lead_id, cle__in=CLES_VISITE)
              .exclude(traite_le=None).only('libelle', 'canal'))
    return any(corps.startswith(prefixe_activite_touche(etape))
               for etape in etapes)


def prefixe_activite_message_ouvert(etape):
    """RLC3 — le PRÉFIXE de la ligne de chatter « message ouvert » de CETTE
    touche.

    UNE seule source : ``journaliser_whatsapp_ouvert`` juste dessous l'écrit,
    ``RelanceEtapeSerializer.get_message_ouvert_le`` le relit. Deux littéraux
    auraient dérivé au premier ajustement de la phrase, et le rappel « message
    ouvert ? » du panneau « Fait » se serait tu sans que rien ne rougisse."""
    libelle = (etape.libelle or '').strip() or etape.get_canal_display()
    return f'WhatsApp ouvert — touche « {libelle} »'


def journaliser_whatsapp_ouvert(etape, user):
    """RELANCE-WA (fondateur 08/09/2026) — ouvrir WhatsApp depuis une touche
    n'AVANCE plus la touche. Le clic est INSCRIT dans l'historique du lead
    (activité typée WhatsApp : comptée comme tentative MRY20 et comme premier
    contact MRY19 par les récepteurs) et la touche reste À FAIRE jusqu'à la
    réponse aux questions guidées (« Fait »). Avant, le clic marquait la
    touche faite (décision D5 du 07/09) : une conversation ouverte n'est pas
    une réponse du client. Aucune issue posée → aucune cadence arrêtée,
    aucune avance d'étape."""
    return LeadActivity.objects.create(
        company=etape.company, lead=etape.lead, user=user,
        kind=LeadActivity.Kind.WHATSAPP,
        body=(f'{prefixe_activite_message_ouvert(etape)} (cadence '
              f'{etape.cadence}) : message préparé ; la touche reste à faire '
              "jusqu'à la réponse du client."))


#: Le canal retiré des cadences. Valeur de ``parametres.CanalRelance.VISITE``,
#: reprise en littéral (ce module ne dépend d'aucun modèle de référentiel).
CANAL_VISITE = 'visite'

#: Ce qu'une touche legacy `visite` devient : un appel. C'est le canal le plus
#: prudent (fenêtre d'appel, pause du vendredi respectée) et c'est la décision.
CANAL_VISITE_REMPLACEMENT = 'appel'


def _canal_effectif(gabarit):
    """Le canal RÉEL d'une touche de cadence — jamais `visite` (CAD58).

    `appel` par défaut, jamais deviné. Un gabarit encore en `visite` (société
    seedée avant le 21/09/2026) est normalisé ici plutôt que refusé : la
    touche existe, elle doit juste cesser d'annoncer une visite.
    """
    canal = getattr(gabarit, 'canal', None) or CANAL_VISITE_REMPLACEMENT
    if canal == CANAL_VISITE:
        return CANAL_VISITE_REMPLACEMENT
    return canal
