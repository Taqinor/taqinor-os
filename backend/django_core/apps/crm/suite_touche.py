"""CAD17 — la SUITE annoncée d'une réponse de touche, DÉRIVÉE DU MOTEUR.

LA CAUSE COMMUNE (audit L3 du 21/09/2026). Les phrases « suite » du panneau
« Fait » (``RelanceEtapeRow.jsx``) étaient écrites PAR CADENCE, dans un objet
littéral d'écran, alors que ce que fait le serveur dépend AUSSI du libellé de
la touche (barreau du protocole, étape posée par le filet, geste de visite),
de son RANG (la dernière touche d'une cadence ne fait naître aucune suivante)
et de l'état du devis. Aucun test ne confrontait une promesse d'écran à
l'effet réel : c'est la racine de CAD1 (« Intéressé » promettait une suite et
rejouait le plan), CAD3 (« À rappeler » promettait un report et consommait
l'étape), CAD16 (le dernier réveil promettait un réveil suivant inexistant) et
CAD97 (« demain » annoncé pour un barreau posé à son délai).

LA RÉPONSE. La promesse n'est plus écrite à l'écran : elle est CALCULÉE ICI, à
partir des MÊMES tables et fonctions de décision que le moteur
(``CADENCES_ARRETEES_PAR_ISSUE``, ``_palier_sans_reponse``, les libellés de
filet et de visite, les barreaux actifs du gabarit, ``REPONSES_TOUCHE``), et
servie avec la touche (clé ``suites`` du contrat ``relance_etape_v2``) : pour
chaque réponse que l'écran propose, une LISTE DE CODES D'EFFET. L'écran ne
fait plus que traduire chaque code en UNE phrase
(``frontend/src/features/crm/relances/suite_phrases.json``).

LA GARDE. ``apps/crm/tests_cad17_parite_promesse_effet.py`` rejoue chaque
réponse de chaque cadence, dans chaque nature et chaque rang de touche, par
l'API réelle, et vérifie pour chaque code annoncé l'effet observé en base. Un
code sans effet correspondant — le cinquième mensonge d'écran — casse le
test au prochain drain, sans réunion.

Hypothèses assumées (et documentées plutôt que cachées) :

* une prise de contact, une cadence générique ou une « deuxième affaire »
  ouverte n'a pas de devis ENVOYÉ en parallèle : l'envoi d'un devis arrête
  ces cadences (MRY7, CADX). Seuls les réveils et les étapes de filet
  annoncent donc la branche « si le suivi d'un devis envoyé n'est pas allé
  au bout » ;
* seul le réveil vit au Froid : le passage à COLD arrête la prise de contact
  et le suivi de proposition (MRY9), et la cadence générique est historique.

LECTURE PURE : aucune écriture, et UNE requête par (société, cadence) au plus
(cache du sérialiseur) — jamais une par touche.

PARAM-CADENCE (décision fondateur du 25/09/2026) — la chaîne après l'appel et
autour de la visite est réglable dans Paramètres. La NATURE d'une touche et
l'ESCALIER « ne décroche pas » se lisent donc sur la CLÉ du barreau
(``cadence_config``), jamais sur un libellé qu'une société peut renommer ; un
PALIER désactivé (``appel_apres_reponse``, ``message_creneau``,
``dernier_appel``) est sauté ici exactement comme le moteur le saute (lecture
paresseuse de ``cadence_config.cles_actives``, UNE requête par société au
plus, jamais une écriture).

LIMITE ASSUMÉE (et documentée plutôt que cachée) : les codes décrivent des
EFFETS, mais les phrases de l'écran (``suite_phrases.json``) de plusieurs
d'entre eux nomment une étape ou un délai PAR DÉFAUT —
``etape_devis_demain`` et ``etape_devis_demain_sauf_suivi`` (« demain :
Préparer et envoyer le devis »), ``etape_devis_a_la_date`` et
``etape_devis_a_la_date_sauf_suivi`` (le libellé), ``etape_dernier_appel``
(« demain »), ``etape_devis_modifie`` (libellé et « demain »),
``etape_planifier_visite`` (libellé et « pour aujourd'hui »),
``etape_decider_suite`` (libellé). Pour une société qui renomme ou décale
ces barreaux, la phrase dit le défaut livré. Aucun code existant ne porte
« à son délai réglé » (``*_A_LA_DATE`` veut dire « à la date CHOISIE par la
commerciale ») et un code neuf exigerait sa phrase d'écran (garde CAD17) :
la correction passe par le
contrat (servir le libellé et le délai réglés de ces clés avec la touche) et
l'écran — hors de cette moitié serveur.

SUIVI-PARCOURS (ordre fondateur du 30/09/2026 — « make sure we have the right
set of answers after each step »). Les réponses servies ne se lisent plus PAR
CADENCE : elles suivent LA TABLE du parcours
(``frontend/src/features/crm/relances/parcours_suivi.json``), TYPE d'étape par
TYPE d'étape. ``type_etape`` reconnaît le type exactement comme la table
(``reconnaissance`` : la CLÉ d'abord, puis le libellé, puis cadence + canal) ;
``REPONSES_PAR_TYPE`` est le miroir des clés de réponse de la table, dans son
ordre ; la garde ``tests_suivi_e14_table_reponses.py`` lit la table et exige
l'égalité. Le serveur ne lit JAMAIS le fichier de l'écran à l'exécution (il
n'existe pas dans l'image du serveur) : le miroir est ici, la garde le tient.
"""

# ── Les codes d'effet ────────────────────────────────────────────────────────
#
# Un code = UN effet observable du moteur, vérifié par la garde, traduit en
# UNE phrase à l'écran. Ajouter un code sans phrase ou sans vérificateur casse
# la garde (les trois ensembles doivent être égaux).

TOUCHE_SUIVANTE = 'touche_suivante'
TOUCHE_SUIVANTE_A_LA_DATE = 'touche_suivante_a_la_date'
DERNIERE_FROID_REVEILS = 'derniere_froid_reveils'
DERNIER_REVEIL = 'dernier_reveil'
DERNIER_REVEIL_DATE_PERDUE = 'dernier_reveil_date_perdue'
RESTE_AU_FROID = 'reste_au_froid'
SORT_DU_FROID = 'sort_du_froid'
CONTACT_ARRETEE = 'contact_arretee'
REVEILS_ARRETES = 'reveils_arretes'
RELANCES_ARRETEES = 'relances_arretees'
ETAPE_APPELER = 'etape_appeler'
ETAPE_DEVIS_DEMAIN = 'etape_devis_demain'
ETAPE_APPELER_SAUF_SUIVI = 'etape_appeler_sauf_suivi'
ETAPE_DEVIS_DEMAIN_SAUF_SUIVI = 'etape_devis_demain_sauf_suivi'
ETAPE_DEVIS_A_LA_DATE = 'etape_devis_a_la_date'
ETAPE_DEVIS_A_LA_DATE_SAUF_SUIVI = 'etape_devis_a_la_date_sauf_suivi'
ETAPE_DECIDER_SUITE = 'etape_decider_suite'
ETAPE_DEPLACEE_A_LA_DATE = 'etape_deplacee_a_la_date'
SUIVI_PROPOSITION_DEMARRE = 'suivi_proposition_demarre'
ETAPE_PLANIFIER_VISITE = 'etape_planifier_visite'
ETAPE_MESSAGE_CRENEAU = 'etape_message_creneau'
ETAPE_DERNIER_APPEL = 'etape_dernier_appel'
# Décision fondateur du 24/09/2026 — ``visite_froid_si_seule`` (« si c'était
# la dernière relance ouverte, le dossier part au Froid ») n'existe plus : une
# étape de visite sans réponse ne parque JAMAIS le lead au Froid, le filet
# prend le relais (``SUITE_SI_PLUS_RIEN_OUVERT``).
SUITE_SI_PLUS_RIEN_OUVERT = 'suite_si_plus_rien_ouvert'
# SUIVI E3 (30/09/2026) — `prochaine_relance_a_la_date` (« À rappeler le… »
# sur une étape de visite déplaçait la prochaine relance ouverte, pas elle)
# n'existe plus : l'étape de visite est déplacée elle-même
# (``etape_deplacee_a_la_date``).
ETIQUETTE_DECISION = 'etiquette_decision'
NE_PLUS_CONTACTER = 'ne_plus_contacter'
VEILLE_MEME_TOUCHE = 'veille_meme_touche'
QUESTION_PRIX_PAUSE = 'question_prix_pause'
QUESTION_PRIX_ETAPE = 'question_prix_etape'
ETAPE_DEVIS_MODIFIE = 'etape_devis_modifie'
# CAD15 — le JOURNAL D'APPEL de la fiche : une issue journalisée ne clôt
# aucune touche, seuls les récepteurs MRY9 réagissent — d'où des effets
# propres, dits eux aussi.
JOURNAL_SUITE_SI_RIEN_OUVERT = 'journal_suite_si_rien_ouvert'
JOURNAL_DECIDER_SI_RIEN_OUVERT = 'journal_decider_si_rien_ouvert'
JOURNAL_SANS_EFFET = 'journal_sans_effet'
# SUIVI E7 (30/09/2026) — `suivi_demarre_sans_envoi` (CAD47 : « sauter
# l'étape devis vaut devis parti ») n'existe plus : une étape devis SAUTÉE ne
# démarre plus aucun suivi, le filet pose « Décider la suite ».
# SUIVI E2 (30/09/2026) — « Perdu — clore le dossier » sur « Décider la
# suite » : le lead passe perdu avec son motif, tout s'arrête, rien n'est
# posé.
LEAD_PERDU = 'lead_perdu'
# SUIVI E4 (30/09/2026) — « Ne veut plus de visite » : le rendez-vous est
# annulé, les gestes de visite retirés ; le suivi continue sans visite
# (``suite_si_plus_rien_ouvert`` le dit).
VISITE_ABANDONNEE = 'visite_abandonnee'
# SUIVI E10 (30/09/2026) — un créneau CONVENU devient un APPEL : l'étape
# « Rappeler le client — rappel convenu » est posée à la date et à l'heure
# convenues (et, E17, sur le dernier réveil).
ETAPE_RAPPEL_CONVENU_A_LA_DATE = 'etape_rappel_convenu_a_la_date'
# SUIVI E12 (30/09/2026) — « Planifier la visite » sans réponse : l'étape est
# reposée pour demain.
ETAPE_PLANIFIER_DEMAIN = 'etape_planifier_demain'

#: Le vocabulaire COMPLET — la garde exige qu'il soit égal à l'ensemble des
#: phrases de l'écran ET à l'ensemble des vérificateurs.
CODES = frozenset({
    TOUCHE_SUIVANTE, TOUCHE_SUIVANTE_A_LA_DATE, DERNIERE_FROID_REVEILS,
    DERNIER_REVEIL, DERNIER_REVEIL_DATE_PERDUE, RESTE_AU_FROID,
    SORT_DU_FROID, CONTACT_ARRETEE, REVEILS_ARRETES, RELANCES_ARRETEES,
    ETAPE_APPELER, ETAPE_DEVIS_DEMAIN, ETAPE_APPELER_SAUF_SUIVI,
    ETAPE_DEVIS_DEMAIN_SAUF_SUIVI, ETAPE_DEVIS_A_LA_DATE,
    ETAPE_DEVIS_A_LA_DATE_SAUF_SUIVI, ETAPE_DECIDER_SUITE,
    ETAPE_DEPLACEE_A_LA_DATE, SUIVI_PROPOSITION_DEMARRE,
    ETAPE_PLANIFIER_VISITE, ETAPE_MESSAGE_CRENEAU, ETAPE_DERNIER_APPEL,
    SUITE_SI_PLUS_RIEN_OUVERT, ETIQUETTE_DECISION, NE_PLUS_CONTACTER,
    VEILLE_MEME_TOUCHE, QUESTION_PRIX_PAUSE, QUESTION_PRIX_ETAPE,
    ETAPE_DEVIS_MODIFIE, JOURNAL_SUITE_SI_RIEN_OUVERT,
    JOURNAL_DECIDER_SI_RIEN_OUVERT, JOURNAL_SANS_EFFET,
    LEAD_PERDU, VISITE_ABANDONNEE, ETAPE_RAPPEL_CONVENU_A_LA_DATE,
    ETAPE_PLANIFIER_DEMAIN,
})

# ── La nature d'une touche ───────────────────────────────────────────────────

#: Un barreau du gabarit de la cadence (ou une touche hors gabarit qui se
#: comporte comme une dernière touche : réveil saisonnier, rappel demandé).
NATURE_BARREAU = 'barreau'
#: L'étape de filet « Préparer et envoyer le devis » : la cocher sans issue
#: vaut « devis parti » (QJ-FUNNEL / RELANCE-SUITE).
NATURE_ENVOI_DEVIS = 'envoi_devis'
#: Une autre étape posée par le filet (hors protocole).
NATURE_FILET = 'filet'
#: La touche de passation (CAD54) : posée À CÔTÉ du plan en cours.
NATURE_PASSATION = 'passation'
#: Un des gestes du rendez-vous de visite technique (VISITE-CADENCE).
NATURE_VISITE = 'visite'

#: La clé de la réponse « Fait — passer à la suite » (aucune issue) : une
#: chaîne vide ferait une clé JSON illisible côté écran.
CLE_SANS_ISSUE = 'sans_issue'
#: CAD47 — la clé du geste « Sauter » (panneau distinct du « Fait »).
CLE_SAUTER = 'sauter'

#: Les canaux d'une touche ÉCRITE : c'est le canal qui décide, après une
#: réponse du client, si la suite est de l'appeler (message répondu) ou de
#: préparer le devis (appel fait) — RELANCE-SUITE.
_CANAUX_ECRITS = ('whatsapp', 'email')

# ── SUIVI-PARCOURS — le TYPE d'une étape, lu comme la table le lit ──────────
#
# Les identifiants sont ceux de la table (`etapes[].id`). Les dix étapes que
# le moteur pose depuis Paramètres ont pour identifiant leur CLÉ
# (``cadence_config``) : une étape renommée par la société garde son type.

TYPE_CONTACT_APPEL = 'contact_appel'
TYPE_CONTACT_MESSAGE = 'contact_message'
TYPE_DEVIS = 'devis'
TYPE_APPEL_APRES_REPONSE = 'appel_apres_reponse'
TYPE_MESSAGE_CRENEAU = 'message_creneau'
TYPE_DERNIER_APPEL = 'dernier_appel'
TYPE_RAPPEL_CONVENU = 'rappel_convenu'
TYPE_DECIDER_SUITE = 'decider_suite'
TYPE_SUIVI_APPEL = 'suivi_appel'
TYPE_SUIVI_MESSAGE = 'suivi_message'
TYPE_QUESTION_PRIX = 'question_prix'
TYPE_PLANIFIER = 'planifier'
TYPE_CONFIRMATION = 'confirmation'
TYPE_DEBRIEF = 'debrief'
TYPE_DEVIS_MODIFIE = 'devis_modifie'
TYPE_REVEIL_APPEL = 'reveil_appel'
TYPE_REVEIL_MESSAGE = 'reveil_message'
TYPE_GENERIQUE = 'generique'

#: Clé moteur → type (ils portent le même nom : la table le veut ainsi).
_TYPES_PAR_CLE = frozenset({
    TYPE_DEVIS, TYPE_APPEL_APRES_REPONSE, TYPE_MESSAGE_CRENEAU,
    TYPE_DERNIER_APPEL, TYPE_RAPPEL_CONVENU, TYPE_DECIDER_SUITE,
    TYPE_PLANIFIER, TYPE_CONFIRMATION, TYPE_DEBRIEF, TYPE_DEVIS_MODIFIE,
})

#: Cadence de protocole → (type de l'APPEL, type du MESSAGE). La deuxième
#: affaire EST une prise de contact (celle d'un client acquis) : la table la
#: range sous les deux mêmes types.
_TYPES_PAR_CADENCE = {
    'contact': (TYPE_CONTACT_APPEL, TYPE_CONTACT_MESSAGE),
    'deuxieme_affaire': (TYPE_CONTACT_APPEL, TYPE_CONTACT_MESSAGE),
    'apres_devis': (TYPE_SUIVI_APPEL, TYPE_SUIVI_MESSAGE),
    'reveil': (TYPE_REVEIL_APPEL, TYPE_REVEIL_MESSAGE),
}


def type_etape(etape):
    """SUIVI-PARCOURS — l'identifiant, dans la table du parcours, du TYPE de
    ``etape``. Fonction PURE (aucune requête), reconnaissance dans l'ordre de
    la table : la CLÉ moteur d'abord (``cle_de`` : une étape posée avant la
    clé est reconnue par son libellé PAR DÉFAUT), puis le libellé (la
    question de prix, hors gabarit), puis la cadence et le canal (un canal
    historique « visite » compte comme un appel, ``_canal_configure``).
    Toute étape d'une autre cadence est « générique »."""
    from .cadence_config import cle_de
    from .services import QUESTION_PRIX_LIBELLE

    cle = cle_de(etape)
    if cle in _TYPES_PAR_CLE:
        return cle
    if (not (getattr(etape, 'cle', '') or '')
            and (etape.libelle or '').strip() == QUESTION_PRIX_LIBELLE):
        return TYPE_QUESTION_PRIX
    paire = _TYPES_PAR_CADENCE.get(etape.cadence)
    if paire is None:
        return TYPE_GENERIQUE
    return paire[1] if etape.canal in _CANAUX_ECRITS else paire[0]


#: SUIVI-PARCOURS — les CLÉS de réponse de chaque type, dans l'ORDRE de la
#: table (le miroir de ``parcours_suivi.json`` ; la garde E14 exige
#: l'égalité). Clé d'une réponse = sa ``reponse`` serveur si elle en a une,
#: sinon son issue (``''`` → ``sans_issue``) ; les gestes sans envoi (« la
#: date est calée », « reportée à une autre date ») n'en ont pas — c'est la
#: planification qui clôt l'étape.
REPONSES_PAR_TYPE = {
    TYPE_CONTACT_APPEL: (
        'joint', 'visite_acceptee', 'non_joint', 'rappel', 'plus_tard',
        'refuse', 'ne_plus_contacter'),
    TYPE_CONTACT_MESSAGE: (
        'joint', 'visite_acceptee', 'non_joint', 'rappel',
        'plus_tard', 'refuse', 'ne_plus_contacter'),
    TYPE_DEVIS: (
        'sans_issue', 'visite_acceptee', 'rappel', 'refuse',
        'ne_plus_contacter'),
    TYPE_APPEL_APRES_REPONSE: (
        'joint', 'visite_acceptee', 'non_joint', 'rappel', 'refuse',
        'ne_plus_contacter'),
    TYPE_MESSAGE_CRENEAU: (
        'sans_issue', 'rappel', 'joint', 'visite_acceptee', 'refuse',
        'ne_plus_contacter'),
    TYPE_DERNIER_APPEL: (
        'joint', 'visite_acceptee', 'non_joint', 'rappel', 'refuse',
        'ne_plus_contacter'),
    TYPE_RAPPEL_CONVENU: (
        'joint', 'visite_acceptee', 'non_joint', 'rappel', 'refuse',
        'ne_plus_contacter'),
    TYPE_DECIDER_SUITE: (
        'perdu', 'rappel', 'sans_issue', 'ne_plus_contacter'),
    TYPE_SUIVI_APPEL: (
        'joint', 'visite_acceptee', 'non_joint', 'rappel', 'refuse',
        'plus_tard', 'question_prix', 'devis_modifie', 'decision_famille',
        'decision_proprietaire', 'ne_plus_contacter'),
    TYPE_SUIVI_MESSAGE: (
        'joint', 'visite_acceptee', 'non_joint', 'rappel',
        'refuse', 'plus_tard', 'question_prix', 'devis_modifie',
        'decision_famille', 'decision_proprietaire', 'ne_plus_contacter'),
    TYPE_QUESTION_PRIX: (
        'sans_issue', 'rappel', 'refuse', 'ne_plus_contacter'),
    TYPE_PLANIFIER: (
        'rappel', 'non_joint', 'visite_abandonnee', 'refuse',
        'ne_plus_contacter'),
    TYPE_CONFIRMATION: (
        'joint', 'non_joint', 'visite_abandonnee', 'refuse',
        'ne_plus_contacter'),
    TYPE_DEBRIEF: (
        'joint', 'non_joint', 'rappel', 'visite_abandonnee', 'question_prix',
        'devis_modifie', 'decision_famille', 'decision_proprietaire',
        'refuse', 'ne_plus_contacter'),
    TYPE_DEVIS_MODIFIE: (
        'sans_issue', 'rappel', 'refuse', 'ne_plus_contacter'),
    TYPE_REVEIL_APPEL: (
        'joint', 'visite_acceptee', 'non_joint', 'rappel', 'plus_tard',
        'refuse', 'ne_plus_contacter'),
    TYPE_REVEIL_MESSAGE: (
        'joint', 'visite_acceptee', 'non_joint', 'rappel',
        'plus_tard', 'refuse', 'ne_plus_contacter'),
    TYPE_GENERIQUE: (
        'sans_issue', 'visite_acceptee', 'rappel', 'refuse',
        'ne_plus_contacter'),
}

#: Les réponses que la table ajoute sur une touche d'APPEL seulement
#: (``reponses_appel`` : Répondeur, Occupé, Numéro invalide, A bloqué — toutes
#: l'issue « non joint »).
REPONSES_APPEL_PAR_TYPE = {
    TYPE_GENERIQUE: ('non_joint',),
}

#: Les TÂCHES de la table (``tache: true``) : elles ont chacune leurs
#: réponses, et le geste « Sauter » n'y est pas proposé.
TYPES_TACHE = frozenset({
    TYPE_DEVIS, TYPE_DECIDER_SUITE, TYPE_QUESTION_PRIX, TYPE_PLANIFIER,
    TYPE_DEVIS_MODIFIE,
})


def nature_touche(etape):
    """La nature de ``etape`` — lue sur sa CLÉ (PARAM-CADENCE), exactement
    comme le moteur la lit (``materialiser_touche_suivante``,
    ``est_etape_de_filet``, ``marquer_etape_relance``) : une étape renommée
    garde sa nature ; une étape posée avant la clé est reconnue par son
    libellé par défaut."""
    from .cadence_config import CLE_DEVIS, est_etape
    from .services import (
        PASSATION_LIBELLE, est_etape_de_filet, est_etape_de_visite)

    if est_etape_de_visite(etape):
        return NATURE_VISITE
    if etape.cadence == 'generique' and est_etape(etape, CLE_DEVIS):
        return NATURE_ENVOI_DEVIS
    if (not (getattr(etape, 'cle', '') or '')
            and (etape.libelle or '').strip() == PASSATION_LIBELLE):
        return NATURE_PASSATION
    if est_etape_de_filet(etape):
        return NATURE_FILET
    return NATURE_BARREAU


def lecteur_paliers_actifs(company_id, actives=None):
    """PARAM-CADENCE — ``est_actif(cle)`` : un pilier l'est toujours, un
    PALIER seulement si la société l'a gardé dans « Après l'appel (avant
    devis) ». Lecture PURE et PARESSEUSE : la requête
    (``cadence_config.cles_actives``, qui n'écrit jamais) n'a lieu qu'au
    premier palier interrogé, une fois ; une touche sans société (touche non
    enregistrée des gardes) lit les défauts — tout actif."""
    etat = {'cles': actives}

    def est_actif(cle):
        from apps.parametres.models_relance import CLES_PALIERS, Cadence

        from .cadence_config import cles_actives

        if cle not in CLES_PALIERS:
            return True
        if etat['cles'] is None:
            etat['cles'] = (cles_actives(company_id, Cadence.APRES_CONTACT)
                            if company_id else frozenset(CLES_PALIERS))
        return cle in etat['cles']

    return est_actif


def ordres_de_la_cadence(company_id, cadence):
    """Les ``ordre`` des barreaux ACTIFS de ``cadence`` pour la société — ceux
    que ``CadenceRelanceEtape.cadence_pour`` rendrait, SANS rien écrire.

    ``cadence_pour`` seede la cadence à la volée quand elle n'a aucun barreau
    actif (``get_or_create`` par ordre : seuls les ordres ABSENTS naissent,
    jamais un barreau désactivé ne revient) ; on rejoue ce calcul à blanc
    pour qu'une lecture ne fasse jamais une écriture."""
    from apps.parametres.models_relance import (
        CADENCES_DEFAUT, CadenceRelanceEtape)

    lignes = list(CadenceRelanceEtape.objects.filter(
        company_id=company_id, cadence=cadence,
    ).values_list('ordre', 'actif'))
    actifs = {ordre for ordre, actif in lignes if actif}
    if not actifs:
        existants = {ordre for ordre, _actif in lignes}
        defauts = CADENCES_DEFAUT.get(cadence, [])
        actifs = {entree['ordre'] for entree in defauts} - existants
    return frozenset(actifs)


def est_derniere_touche(etape, ordres):
    """Cette touche est-elle la DERNIÈRE de sa cadence — celle après laquelle
    ``materialiser_touche_suivante`` ne fait plus rien naître ?

    Vrai pour le plus grand ordre actif, et pour toute touche dont l'ordre
    n'est PAS un barreau actif (réveil saisonnier CAD74, rappel demandé
    CAD129) : le moteur ne lui trouve aucun rang, donc aucune suivante."""
    if not ordres or etape.ordre not in ordres:
        return True
    return etape.ordre == max(ordres)


def cles_de_reponse(etape):
    """SUIVI-PARCOURS — les clés des réponses que l'écran propose sur
    ``etape``, EXACTEMENT celles de la table pour son type
    (``REPONSES_PAR_TYPE``, dans l'ordre de la table), suivies de ``sauter``
    quand l'étape l'autorise (jamais sur une TÂCHE : devis, planifier la
    visite, décider la suite, devis modifié, question de prix).

    Signature TOLÉRANTE : un appelant qui passe encore une CADENCE (chaîne)
    reçoit les clés d'une touche d'APPEL de cette cadence."""
    if isinstance(etape, str):
        from .models import RelanceEtape

        etape = RelanceEtape(cadence=etape, canal=RelanceEtape.Canal.APPEL)
    type_id = type_etape(etape)
    cles = list(REPONSES_PAR_TYPE[type_id])
    if etape.canal not in _CANAUX_ECRITS:
        cles += [cle for cle in REPONSES_APPEL_PAR_TYPE.get(type_id, ())
                 if cle not in cles]
    if type_id not in TYPES_TACHE:
        cles.append(CLE_SAUTER)
    return cles


def _appeler_apres_message(etape, est_actif):
    """Message répondu → l'appeler, sauf si la société a désactivé ce
    palier (PARAM-CADENCE) : le moteur pose alors le devis."""
    from .cadence_config import CLE_APPEL_APRES_REPONSE

    return (etape.canal in _CANAUX_ECRITS
            and est_actif(CLE_APPEL_APRES_REPONSE))


def _filet_apres_reponse(etape, est_actif):
    """L'étape que le filet pose quand un client « joint » ne laisse rien
    d'ouvert : message répondu → l'appeler ; appel fait → le devis demain."""
    return (ETAPE_APPELER if _appeler_apres_message(etape, est_actif)
            else ETAPE_DEVIS_DEMAIN)


def _filet_apres_reponse_sauf_suivi(etape, est_actif):
    return (ETAPE_APPELER_SAUF_SUIVI
            if _appeler_apres_message(etape, est_actif)
            else ETAPE_DEVIS_DEMAIN_SAUF_SUIVI)


def _codes_barreau(etape, issue, *, derniere, au_froid, est_actif):
    """Un barreau du protocole (ou une touche hors gabarit, traitée comme une
    dernière touche)."""
    from .services import CADENCES_ARRETEES_PAR_ISSUE, OUTCOME_VISITE_ACCEPTEE

    cadence = etape.cadence
    # La cadence de la touche SURVIT-elle à l'issue ? (récepteur MRY9, et
    # `issue_fait_naitre_la_suite` qui lit la même table.)
    survit = cadence not in CADENCES_ARRETEES_PAR_ISSUE.get(issue, ())

    if issue == 'refuse':
        codes = [RELANCES_ARRETEES,
                 RESTE_AU_FROID if au_froid else ETAPE_DECIDER_SUITE]
        if survit and not derniere:
            codes.append(TOUCHE_SUIVANTE)
        return codes

    if issue in ('joint', 'interesse'):
        codes = [SORT_DU_FROID] if au_froid else []
        if cadence == 'contact':
            return codes + [CONTACT_ARRETEE,
                            _filet_apres_reponse(etape, est_actif)]
        if cadence == 'reveil':
            return codes + [REVEILS_ARRETES,
                            _filet_apres_reponse_sauf_suivi(etape, est_actif)]
        if cadence == 'apres_devis':
            # Le filet du récepteur POURSUIT le plan (CAD1) : la touche
            # suivante naît ; après la dernière, l'étape de suite. SUIVI E6
            # (30/09/2026) — avec OU SANS devis dans l'ERP : un suivi sans
            # devis (parti hors ERP) est poursuivi depuis son dernier barreau
            # consommé, il ne pose plus l'étape devis à côté du suivant.
            return codes + ([_filet_apres_reponse(etape, est_actif)]
                            if derniere else [TOUCHE_SUIVANTE])
        # Cadence générique, deuxième affaire : le filet pose son étape (rien
        # d'ouvert, aucun devis relançable) ET, la cadence survivant à
        # l'issue, la touche suivante naît aussi.
        if survit and not derniere:
            codes.append(TOUCHE_SUIVANTE)
        return codes + [_filet_apres_reponse(etape, est_actif)]

    if issue == OUTCOME_VISITE_ACCEPTEE:
        # 24/09/2026 — sur la prise de contact et le réveil, l'issue arrête
        # la cadence exactement comme « joint » (même table, récepteur MRY9,
        # qui sort aussi un dormant du Froid) ; partout, la seule suite est
        # l'étape « Planifier la visite technique convenue ».
        codes = [SORT_DU_FROID] if au_froid else []
        if cadence == 'contact' and not survit:
            codes.append(CONTACT_ARRETEE)
        if cadence == 'reveil' and not survit:
            codes.append(REVEILS_ARRETES)
        return codes + [ETAPE_PLANIFIER_VISITE]

    if issue == 'rappel':
        if not derniere:
            return [TOUCHE_SUIVANTE_A_LA_DATE]
        if cadence == 'reveil':
            return ([DERNIER_REVEIL_DATE_PERDUE] if au_froid
                    else [ETAPE_DEVIS_A_LA_DATE_SAUF_SUIVI])
        return [ETAPE_DEVIS_A_LA_DATE]

    # « pas de réponse » (et ses précisions Répondeur/Occupé/numéro invalide),
    # ou « Fait — passer à la suite » sur la cadence générique.
    if not derniere:
        return [TOUCHE_SUIVANTE] + ([RESTE_AU_FROID] if au_froid else [])
    if cadence in ('contact', 'apres_devis'):
        # MRY11 — la cadence s'épuise sans réponse : parking Froid + réveils.
        return [DERNIERE_FROID_REVEILS]
    if cadence == 'reveil':
        # La cadence réveil ne se clôture jamais elle-même, et le filet ne
        # pose rien sur un dossier au Froid (CAD16).
        return ([DERNIER_REVEIL] if au_froid
                else [ETAPE_DEVIS_DEMAIN_SAUF_SUIVI])
    # Générique, deuxième affaire : aucune clôture, le filet pose sa suite.
    return [ETAPE_DEVIS_DEMAIN]


def _codes_envoi_devis(issue):
    """« Préparer et envoyer le devis (ou fixer un rappel) »."""
    from .services import OUTCOME_VISITE_ACCEPTEE

    if issue == '':
        return [SUIVI_PROPOSITION_DEMARRE]
    if issue == OUTCOME_VISITE_ACCEPTEE:
        # 24/09/2026 — une ISSUE est saisie : l'étape n'est PAS lue comme
        # « devis parti » (seule la clôture SANS issue l'est). Le devis se
        # préparera après la visite, au retour terrain.
        return [ETAPE_PLANIFIER_VISITE]
    if issue == 'rappel':
        return [ETAPE_DEPLACEE_A_LA_DATE]
    if issue == 'refuse':
        return [RELANCES_ARRETEES, ETAPE_DECIDER_SUITE]
    # « pas de réponse » : la ceinture anti-tapis-roulant refuse de re-poser
    # la même étape — c'est l'étape de décision qui prend le relais.
    return [ETAPE_DECIDER_SUITE]


def _codes_filet(etape, issue, est_actif):
    """Une autre étape posée par le filet (hors protocole).

    PARAM-CADENCE — l'escalier se lit en CLÉS (``cle_de``) et saute un
    palier désactivé, exactement comme le moteur
    (``services.prochain_palier_sans_reponse``)."""
    from .cadence_config import CLE_DERNIER_APPEL, CLE_MESSAGE_CRENEAU, cle_de
    from .services import OUTCOME_VISITE_ACCEPTEE, prochain_palier_sans_reponse

    if issue == OUTCOME_VISITE_ACCEPTEE:
        # 24/09/2026 — la suite est de caler la visite, rien d'autre.
        return [ETAPE_PLANIFIER_VISITE]
    if issue == 'rappel':
        # SUIVI E10 — sur « proposer un créneau », le créneau convenu devient
        # l'appel « rappel convenu » ; partout ailleurs (CAD3), l'étape est
        # déplacée à la date.
        if cle_de(etape) == CLE_MESSAGE_CRENEAU:
            return [ETAPE_RAPPEL_CONVENU_A_LA_DATE]
        return [ETAPE_DEPLACEE_A_LA_DATE]
    if issue == 'refuse':
        return [RELANCES_ARRETEES, ETAPE_DECIDER_SUITE]
    if issue in ('joint', 'interesse'):
        # SUIVI-PARCOURS — « Client joint » sur une étape de filet : le
        # récepteur MRY9 pose la suite selon le CANAL de la touche (message
        # répondu → l'appeler ; appel abouti → le devis), sauf si le suivi
        # d'un devis envoyé reprend.
        return [_filet_apres_reponse_sauf_suivi(etape, est_actif)]
    palier = prochain_palier_sans_reponse(cle_de(etape), issue, est_actif)
    if palier == CLE_MESSAGE_CRENEAU:
        return [ETAPE_MESSAGE_CRENEAU]
    if palier == CLE_DERNIER_APPEL:
        return [ETAPE_DERNIER_APPEL]
    return [ETAPE_DEVIS_DEMAIN_SAUF_SUIVI]


def _codes_a_cote_du_plan(issue, *, visite, cle=''):
    """Une touche posée À CÔTÉ du plan en cours (geste de visite, passation) :
    ce qu'elle déclenche dépend de ce qui reste OUVERT à côté d'elle — d'où
    des phrases conditionnelles, vérifiées dans chacune de leurs branches.
    ``cle`` : la clé moteur de la touche (``cadence_config.cle_de``)."""
    from .cadence_config import CLE_PLANIFIER
    from .services import OUTCOME_VISITE_ACCEPTEE

    if issue == 'refuse':
        return [RELANCES_ARRETEES, ETAPE_DECIDER_SUITE]
    if issue == 'non_joint' and cle == CLE_PLANIFIER:
        # SUIVI E12 — le client a accepté la visite : on réessaie de caler
        # la date demain, jamais le devis à la place.
        return [ETAPE_PLANIFIER_DEMAIN]
    if issue == OUTCOME_VISITE_ACCEPTEE:
        return [ETAPE_PLANIFIER_VISITE]
    if issue == 'rappel':
        # SUIVI E3 (30/09/2026) — « À rappeler le… » sur une étape de VISITE
        # la DÉPLACE à la date, comme une étape de filet (CAD3) : la visite à
        # planifier ou le débrief ne disparaît plus au profit du filet.
        return [ETAPE_DEPLACEE_A_LA_DATE]
    # « pas de réponse », « Fait » sans issue ou saut (CAD47) : décision
    # fondateur du 24/09/2026, une étape de visite n'ÉPUISE plus la cadence
    # après-devis (plus de clôture MRY11 au Froid). Si rien d'autre n'est
    # ouvert, le filet prend le relais : le plan s'il n'est pas allé au bout,
    # sinon une étape de suite (le débrief sans réponse : « Rappeler — dernier
    # essai avant de chiffrer », ``_FILET_SANS_REPONSE_PALIERS``).
    return [SUITE_SI_PLUS_RIEN_OUVERT]


def _codes_sauter(etape, *, nature, derniere, au_froid, est_actif):
    """CAD47 — ce que fait « Sauter » : le moteur clôt la touche SAUTÉE sans
    issue (``marquer_etape_relance``), et la suite est celle d'une touche
    close sans réponse — barreau suivant, clôture au Froid après la dernière,
    filet sinon.

    SUIVI E7 (30/09/2026) — sauter l'étape « préparer et envoyer le devis »
    ne vaut PLUS « devis parti » : rien n'a été envoyé. La ceinture
    anti-tapis-roulant du filet refuse de re-poser la touche close et pose
    « Décider la suite »."""
    if nature == NATURE_ENVOI_DEVIS:
        return [ETAPE_DECIDER_SUITE]
    if nature == NATURE_FILET:
        return _codes_filet(etape, '', est_actif)
    if nature in (NATURE_VISITE, NATURE_PASSATION):
        return _codes_a_cote_du_plan('', visite=nature == NATURE_VISITE)
    return _codes_barreau(etape, '', derniere=derniere, au_froid=au_froid,
                          est_actif=est_actif)


def _codes_reponse_client(cle, *, nature, derniere):
    """Les RÉPONSES DU CLIENT (``REPONSES_TOUCHE``, CAD-A)."""
    from .services import (
        REPONSE_DECISION_FAMILLE, REPONSE_DECISION_PROPRIETAIRE,
        REPONSE_DEVIS_MODIFIE, REPONSE_NE_PLUS_CONTACTER, REPONSE_PERDU,
        REPONSE_PLUS_TARD, REPONSE_QUESTION_PRIX, REPONSE_VISITE_ABANDONNEE)

    if cle == REPONSE_NE_PLUS_CONTACTER:
        return [NE_PLUS_CONTACTER]
    if cle == REPONSE_PERDU:
        return [LEAD_PERDU]
    if cle == REPONSE_VISITE_ABANDONNEE:
        return [VISITE_ABANDONNEE, SUITE_SI_PLUS_RIEN_OUVERT]
    if cle == REPONSE_PLUS_TARD:
        return [VEILLE_MEME_TOUCHE]
    a_cote = nature in (NATURE_VISITE, NATURE_PASSATION)
    if cle == REPONSE_QUESTION_PRIX:
        return [QUESTION_PRIX_ETAPE if a_cote else QUESTION_PRIX_PAUSE]
    if cle == REPONSE_DEVIS_MODIFIE:
        return [ETAPE_DEVIS_MODIFIE]
    if cle in (REPONSE_DECISION_FAMILLE, REPONSE_DECISION_PROPRIETAIRE):
        # L'étiquette, puis une issue « à rappeler » SANS date, qui suit la
        # mécanique ordinaire de la touche.
        if a_cote:
            return [ETIQUETTE_DECISION, SUITE_SI_PLUS_RIEN_OUVERT]
        return [ETIQUETTE_DECISION,
                ETAPE_DEVIS_DEMAIN if derniere else TOUCHE_SUIVANTE]
    return []


def promesses_touche(etape, *, ordres=None, est_actif=None):
    """``{cle_de_reponse: [codes d'effet]}`` pour chaque réponse que le
    panneau « Fait » propose sur ``etape`` — les clés de ``cles_de_reponse``
    (la table du parcours, SUIVI-PARCOURS), ``sauter`` compris quand l'étape
    le propose.

    ``ordres`` : les barreaux actifs de sa cadence
    (``ordres_de_la_cadence``) — passé par le sérialiseur, qui les met en
    cache par (société, cadence). ``est_actif`` : le lecteur des paliers
    gardés par la société (``lecteur_paliers_actifs``, PARAM-CADENCE) — mis
    en cache par société de la même façon. Une touche déjà traitée n'a plus
    de suite à annoncer : ``{}``."""
    from . import stages
    from .cadence_config import cle_de
    from .models import RelanceEtape
    from .services import REPONSES_TOUCHE

    if etape.statut != RelanceEtape.Statut.A_FAIRE:
        return {}
    if ordres is None:
        ordres = ordres_de_la_cadence(etape.company_id, etape.cadence)
    if est_actif is None:
        est_actif = lecteur_paliers_actifs(etape.company_id)
    nature = nature_touche(etape)
    derniere = est_derniere_touche(etape, ordres)
    lead = getattr(etape, 'lead', None)
    au_froid = (etape.cadence == 'reveil'
                and getattr(lead, 'stage', None) == stages.COLD)

    promesses = {}
    for cle in cles_de_reponse(etape):
        if cle == CLE_SAUTER:
            # CAD47 — le panneau « Sauter » dit lui aussi ce qu'il déclenche.
            codes = _codes_sauter(
                etape, nature=nature, derniere=derniere, au_froid=au_froid,
                est_actif=est_actif)
        elif cle in REPONSES_TOUCHE:
            codes = _codes_reponse_client(
                cle, nature=nature, derniere=derniere)
        else:
            issue = '' if cle == CLE_SANS_ISSUE else cle
            if nature == NATURE_ENVOI_DEVIS:
                codes = _codes_envoi_devis(issue)
            elif nature == NATURE_FILET:
                codes = _codes_filet(etape, issue, est_actif)
            elif nature in (NATURE_VISITE, NATURE_PASSATION):
                codes = _codes_a_cote_du_plan(
                    issue, visite=nature == NATURE_VISITE,
                    cle=cle_de(etape))
            else:
                codes = _codes_barreau(
                    etape, issue, derniere=derniere, au_froid=au_froid,
                    est_actif=est_actif)
        promesses[cle] = codes
    return promesses


def promesses_journal():
    """CAD15 — ``{issue: [codes d'effet]}`` d'une ISSUE journalisée depuis la
    fiche (journal d'appel, ``LeadViewSet.log_interaction``).

    Là, AUCUNE touche n'est close : seul le récepteur MRY9
    (``receivers._arreter_cadence_on_outcome``) réagit à l'issue, en lisant
    la MÊME table que le panneau des touches (``CADENCES_ARRETEES_PAR_ISSUE``)
    — d'où cette dérivation, jamais une liste recopiée. Un « Refus » coché
    pour mémoire éteint toutes les relances du dossier : l'écran le DIT.

    La table est committée côté écran (``suite_phrases.json``, clé
    ``journal``) : la garde CAD17 exige qu'elle soit ÉGALE à ce calcul et
    rejoue chaque issue par l'API réelle."""
    from .models import LeadActivity
    from .services import CADENCES_ARRETEES_PAR_ISSUE, OUTCOME_VISITE_ACCEPTEE

    promesses = {}
    for issue, _libelle in LeadActivity.OUTCOMES:
        if not issue:
            continue
        arretees = CADENCES_ARRETEES_PAR_ISSUE.get(issue, ())
        if not arretees:
            promesses[issue] = [JOURNAL_SANS_EFFET]
        elif issue == OUTCOME_VISITE_ACCEPTEE:
            # 24/09/2026 — la visite acceptée arrête la prise de contact et
            # les réveils (comme « joint ») ; sa suite n'est pas l'étape
            # générique mais « Planifier la visite technique convenue », que
            # le récepteur pose aussi depuis le journal d'appel.
            promesses[issue] = [
                code for cadence, code in (('contact', CONTACT_ARRETEE),
                                           ('reveil', REVEILS_ARRETES))
                if cadence in arretees] + [ETAPE_PLANIFIER_VISITE]
        elif 'apres_devis' in arretees:
            promesses[issue] = [RELANCES_ARRETEES,
                                JOURNAL_DECIDER_SI_RIEN_OUVERT]
        else:
            promesses[issue] = [CONTACT_ARRETEE, REVEILS_ARRETES,
                                JOURNAL_SUITE_SI_RIEN_OUVERT]
    return promesses
