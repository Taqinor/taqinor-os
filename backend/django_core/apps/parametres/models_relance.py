"""RELANCE FOUNDATION — cadence de relance par défaut, par société.

Référentiel founder-editable (Paramètres → CRM) consommé par
``apps.crm.services.initialiser_plan_relance`` pour matérialiser un plan de
relance structuré (``apps.crm.models.RelanceEtape``) sur un lead donné. Chaque
« barreau » de la cadence est un délai en jours après le point de départ du
plan, un canal SUGGÉRÉ (appel/whatsapp/email/visite) et un libellé.

Zéro chiffre affiché au client : ce sont des DÉFAUTS DE PLANIFICATION interne
(ordonnancement de rappels), jamais une statistique de conversion ni une
preuve chiffrée présentée à qui que ce soit (règle fondateur « zéro chiffre
inventé/affiché »). Même patron que ``UniteMesure``
(``apps/parametres/models_units.py``) : ``TenantModel``, seed idempotent
additif, seedé au signup ET à la volée pour les sociétés déjà existantes.
"""
import datetime

from django.db import IntegrityError, models, transaction

from core.models import TenantModel


class CanalRelance(models.TextChoices):
    APPEL = 'appel', 'Appel'
    WHATSAPP = 'whatsapp', 'WhatsApp'
    EMAIL = 'email', 'E-mail'
    VISITE = 'visite', 'Visite'


# Échelle NEUTRE par défaut (J+2/J+5/J+10/J+20/J+35) — un ordonnancement de
# rappels internes modifiable par société, jamais une statistique de
# conversion affichée (« modifiable » dans Paramètres → CRM).
CADENCE_RELANCE_DEFAUT = [
    {'ordre': 1, 'delai_jours': 2, 'canal': CanalRelance.APPEL,
     'libelle': 'Premier rappel'},
    {'ordre': 2, 'delai_jours': 5, 'canal': CanalRelance.WHATSAPP,
     'libelle': 'Relance WhatsApp'},
    {'ordre': 3, 'delai_jours': 10, 'canal': CanalRelance.EMAIL,
     'libelle': 'Relance e-mail'},
    {'ordre': 4, 'delai_jours': 20, 'canal': CanalRelance.APPEL,
     'libelle': "Point d'étape"},
    # CAD58 (décision fondateur du 21/09/2026) — le canal VISITE est RETIRÉ de
    # la cadence générique : ce barreau ne posait aucune condition de devis,
    # alors que la doctrine du 15/09 est « visite technique JAMAIS avant le
    # devis, proposée après ». Le J+35 devient un APPEL. Les 5 barreaux ne
    # sont ni supprimés ni réordonnés — seul le canal du dernier change.
    {'ordre': 5, 'delai_jours': 35, 'canal': CanalRelance.APPEL,
     'libelle': 'Dernière relance'},
]


# ── CAD25 (TRANCHÉ 21/09/2026) — CRÉNEAUX PAR TYPE DE TOUCHE ────────────────
#
# 7 des 11 touches de la prise de contact et 9 des 10 barreaux après devis
# n'avaient AUCUNE heure cible : leur heure était celle de l'arrivée du lead
# ou de l'envoi du devis. Un devis fini à 19 h 50 faisait tomber « le PDF
# s'ouvre bien ? » à 19 h 50 le lendemain, et tous les leads de nuit ou de
# week-end se regroupaient à l'ouverture.
#
# Décision fondateur : un créneau par TYPE de touche — les MESSAGES à 09 h 30,
# les APPELS entre 17 h 30 et 18 h 30 (on pose le milieu de la fourchette,
# 18 h 00, qui est aussi l'heure déjà retenue pour l'« Appel 4 »). Ces heures
# sont des DÉFAUTS DE SEED : l'éditeur Paramètres → CRM reste la source de
# vérité par société, et une société qui observe le Ramadan y ajuste ses
# créneaux comme le reste.
#
# DEUX FAMILLES GARDENT VOLONTAIREMENT `heure_cible: None` :
#   * les trois gestes J0 de la prise de contact (J0, J0+3 min, J0+2 h 30) —
#     ce n'est pas un créneau mais une SÉQUENCE dans la journée, celle qui
#     tient la promesse « rappelé dans les cinq minutes ». Leur imposer une
#     heure les écraserait sur la même minute, le défaut que MRY5 a corrigé ;
#   * les deux réveils J30/J60 — ils sont POSÉS sur un créneau d'étalement
#     calculé par le placement (MRY30, huit réveils par jour ouvré, 20 min
#     d'écart). Une heure imposée ferait retomber les huit sur la même minute.
# La cadence `generique` (historique, plus jamais démarrée — CAD143) n'est pas
# touchée : ses cinq barreaux restent exactement ce qu'ils ont toujours été.
#
# Garde-fou : ces heures restent BORNÉES par les fenêtres de la société
# (message dès 08:30, appel dès 09:00, fermeture 20:00) et par la fenêtre du
# Ramadan — `apps.crm.horaires.prochain_creneau_appel` recale toute heure qui
# n'y tiendrait pas.
CRENEAU_MESSAGE = datetime.time(9, 30)
#: Bornes de la fourchette d'appel décidée le 21/09/2026.
CRENEAU_APPEL_DEBUT = datetime.time(17, 30)
CRENEAU_APPEL_FIN = datetime.time(18, 30)
#: L'heure POSÉE par défaut sur un appel sans heure : le milieu de la
#: fourchette, jamais un de ses bords.
CRENEAU_APPEL = datetime.time(18, 0)


class Cadence(models.TextChoices):
    """MRY4 — les trois cadences NOMMÉES du protocole de rappel, plus la
    cadence historique.

    Une seule échelle anonyme ne pouvait pas porter trois rythmes différents :
    la prise de contact (11 touches sur 14 j — 6 appels et 5 WhatsApp —, dont
    la PREMIÈRE est le message d'identité à J0 + 0 minute, la deuxième l'appel
    d'ouverture à J0 + 3 minutes et la troisième l'appel 2 à J0 + 2 h 30),
    le suivi après devis (J1…J14) et le réveil des dormants (J30/J60). La
    quatrième valeur, ``generique``, N'EST PAS une nouveauté : c'est le nom
    donné aux 5 barreaux neutres qui existaient déjà (J+2/5/10/20/35). Ils ne
    sont ni supprimés ni réécrits — la migration 0081 se contente de les
    étiqueter."""
    CONTACT = 'contact', 'Prise de contact'
    APRES_DEVIS = 'apres_devis', 'Après devis'
    REVEIL = 'reveil', 'Réveil'
    GENERIQUE = 'generique', 'Générique (historique)'
    # CAD128 (21/09/2026) — la cadence COURTE d'un client DÉJÀ ACQUIS qui
    # redemande un devis. Elle n'est PAS une variante du protocole contact :
    # six appels sur quatorze jours à quelqu'un qui a déjà acheté serait
    # insultant. Deux touches seulement, et elles ne sont pas inventées —
    # ce sont les DEUX PREMIÈRES du protocole validé (message d'identité,
    # puis appel d'ouverture trois minutes après), arrêtées là.
    DEUXIEME_AFFAIRE = 'deuxieme_affaire', 'Deuxième affaire (client acquis)'
    # PARAM-CADENCE (décision fondateur du 25/09/2026 — « cette cadence doit
    # être dans Paramètres, pour qu'une autre société ou nous puissions tout
    # y changer »). Ces deux-là ne sont PAS des plans qu'on démarre : ce sont
    # les GABARITS des étapes que le moteur pose lui-même après l'appel
    # (filet) et autour de la visite technique. Le moteur retrouve chaque
    # barreau par sa CLÉ stable (``CadenceRelanceEtape.cle``), jamais par son
    # libellé : une société peut renommer, décaler, changer le canal ou
    # l'heure. Les étapes posées gardent la cadence de leur frise
    # (``generique`` pour le filet, ``apres_devis`` pour la visite).
    APRES_CONTACT = 'apres_contact', "Après l'appel (avant devis)"
    VISITE = 'visite', 'Visite technique'


# ── Protocole de rappel v3 (04/09/2026) ─────────────────────────────────────
# 6 APPELS MAXIMUM + 5 WhatsApp sur 14 jours, jamais plus d'un appel ET d'un
# message par jour — **HORS J0** : les trois gestes du jour même (message
# d'identité, appel d'ouverture, appel 2 à +2 h 30) sont VOULUS ensemble, c'est
# la promesse « rappelé dans les cinq minutes ». Ces délais viennent du
# protocole validé par le fondateur — ils ne sont pas une estimation et ne se
# retouchent pas ici.
# CAD20 (21/09/2026) — cette phrase n'est plus une intention : elle est
# EXÉCUTÉE par le moteur (`apps.crm.cadence_temps.un_geste_par_jour`, appelé
# par `calculer_echeances_cadence`). Une touche en trop sur une journée est
# décalée d'un jour ouvré ; les trois touches J0 et le rendez-vous dominical
# en sont exemptés. Un délai retouché depuis Paramètres ne peut donc plus
# empiler trois appels le même jour.
#
# ``dimanche_ok`` : la touche 8 (5ᵉ appel) est le SEUL rendez-vous autorisé le
# dimanche, entre 16 h et 19 h, pour les prospects qu'on ne trouve jamais en
# semaine. Toutes les autres touches sont recalées sur les jours ouvrés.
CADENCE_CONTACT_DEFAUT = [
    {'ordre': 1, 'delai_jours': 0, 'delai_minutes': 0, 'heure_cible': None,
     'canal': CanalRelance.WHATSAPP, 'libelle': "Message d'identité",
     'template_cle': 'identite', 'dimanche_ok': False},
    {'ordre': 2, 'delai_jours': 0, 'delai_minutes': 3, 'heure_cible': None,
     'canal': CanalRelance.APPEL, 'libelle': "Appel d'ouverture",
     'template_cle': 'appel_ouverture', 'dimanche_ok': False},
    {'ordre': 3, 'delai_jours': 0, 'delai_minutes': 150, 'heure_cible': None,
     'canal': CanalRelance.APPEL, 'libelle': 'Appel 2 (répondeur)',
     'template_cle': 'repondeur', 'dimanche_ok': False},
    # CAD67 (21/09/2026) — `repondeur` partait DEUX fois en ~20 h (ici ET à
    # l'ordre 6) : le document source (`docs/crm/messages_meryem.md`) le
    # place sur les appels 2 et 4, pas 2 et 3. `repondeur` est donc retiré
    # d'ici (script dédié `appel_relance`) et posé sur l'ordre 6 à sa place,
    # ce qui espace les deux messages répondeur de ~2 jours au lieu de ~20 h.
    {'ordre': 4, 'delai_jours': 1, 'delai_minutes': 0,
     'heure_cible': datetime.time(10, 30),
     'canal': CanalRelance.APPEL, 'libelle': 'Appel 3',
     'template_cle': 'appel_relance', 'dimanche_ok': False},
    {'ordre': 5, 'delai_jours': 1, 'delai_minutes': 0,
     'heure_cible': CRENEAU_MESSAGE,
     'canal': CanalRelance.WHATSAPP, 'libelle': 'WhatsApp de valeur',
     'template_cle': 'valeur_j1', 'dimanche_ok': False},
    {'ordre': 6, 'delai_jours': 2, 'delai_minutes': 0,
     'heure_cible': datetime.time(18, 0),
     'canal': CanalRelance.APPEL, 'libelle': 'Appel 4 (répondeur)',
     'template_cle': 'repondeur', 'dimanche_ok': False},
    {'ordre': 7, 'delai_jours': 3, 'delai_minutes': 0,
     'heure_cible': CRENEAU_MESSAGE,
     'canal': CanalRelance.WHATSAPP, 'libelle': 'Vocal',
     'template_cle': 'vocal_j3', 'dimanche_ok': False},
    {'ordre': 8, 'delai_jours': 5, 'delai_minutes': 0,
     'heure_cible': datetime.time(10, 30),
     'canal': CanalRelance.APPEL, 'libelle': 'Appel 5 (dimanche)',
     'template_cle': 'appel_dimanche', 'dimanche_ok': True},
    {'ordre': 9, 'delai_jours': 7, 'delai_minutes': 0,
     'heure_cible': CRENEAU_MESSAGE,
     'canal': CanalRelance.WHATSAPP, 'libelle': '« Je classe ? »',
     'template_cle': 'je_classe_j7', 'dimanche_ok': False},
    # CAD67 — le DERNIER appel avant clôture (celui qui décide du classement
    # du lead) n'avait aucune phrase d'ouverture : script court dédié.
    {'ordre': 10, 'delai_jours': 10, 'delai_minutes': 0,
     'heure_cible': datetime.time(15, 0),
     'canal': CanalRelance.APPEL, 'libelle': 'Appel 6 (dernier)',
     'template_cle': 'appel_dernier', 'dimanche_ok': False},
    {'ordre': 11, 'delai_jours': 14, 'delai_minutes': 0,
     'heure_cible': CRENEAU_MESSAGE,
     'canal': CanalRelance.WHATSAPP, 'libelle': 'Clôture',
     'template_cle': 'cloture_j14', 'dimanche_ok': False},
]

# Suivi APRÈS ENVOI DU DEVIS (Guide v2.1 chapitre 7). La touche « dimanche
# famille » est posée sur le premier dimanche 16 h après J3, pour les seuls
# leads portant l'étiquette « Décision à plusieurs ».
#
# CAD52 — PAS DE VARIANTE PAR SEGMENT — décision du 21/09/2026, à rouvrir sur
# les mesures de CAD87.
# `unique_together = ('company', 'cadence', 'ordre')` n'autorise qu'UNE
# cadence après-devis par société, et l'action de démarrage ne lit que le nom
# de la cadence : un rythme différent pour l'agricole ou le B2B demanderait
# donc d'ouvrir la clé, l'API, l'éditeur et le démarrage. Décision fondateur
# du 21/09/2026 : on ne le construit PAS — l'effort est gros, aucune source
# primaire sur le cycle de décision agricole n'a pu être ouverte, et rendre
# les phrases de l'écran lisibles (CAD46-CAD48) couvre le besoin ressenti.
# La question se rouvrira sur les CHIFFRES de CAD87, jamais sur une intuition.
# Cette note existe pour qu'un futur audit ne la re-soulève pas.
#
# CAD98 (23/09/2026) — les trois « Appel de suivi » (ordres 2, 6 et 8 : J2,
# J7, J11) portaient `template_cle` vide : 30 % des touches après devis ne
# donnaient ni question ni phrase d'ouverture, alors que la cadence contact
# en a une pour chacun de ses appels (CAD67). Chacun reçoit un script court
# dédié (`appel_suivi_j2`/`_j7`/`_j11`). Garde-fou : aucun barreau ajouté,
# retiré ni déplacé — seules les trois clés de gabarit changent. Comme pour
# CAD67, ces défauts ne valent que pour les barreaux SEEDÉS après ce lot :
# `seed_cadence` ne retouche jamais un barreau existant.
CADENCE_APRES_DEVIS_DEFAUT = [
    {'ordre': 1, 'delai_jours': 1, 'delai_minutes': 0,
     'heure_cible': CRENEAU_MESSAGE,
     'canal': CanalRelance.WHATSAPP, 'libelle': 'Le PDF s\'ouvre bien ?',
     'template_cle': 'j1_pdf', 'dimanche_ok': False},
    {'ordre': 2, 'delai_jours': 2, 'delai_minutes': 0,
     'heure_cible': CRENEAU_APPEL,
     'canal': CanalRelance.APPEL, 'libelle': 'Appel de suivi',
     'template_cle': 'appel_suivi_j2', 'dimanche_ok': False},
    {'ordre': 3, 'delai_jours': 3, 'delai_minutes': 0,
     'heure_cible': datetime.time(16, 0),
     'canal': CanalRelance.WHATSAPP, 'libelle': 'Dimanche famille',
     'template_cle': 'dimanche_famille', 'dimanche_ok': True},
    {'ordre': 4, 'delai_jours': 4, 'delai_minutes': 0,
     'heure_cible': CRENEAU_MESSAGE,
     'canal': CanalRelance.WHATSAPP, 'libelle': 'Preuve — chantier comparable',
     'template_cle': 'j4_preuve', 'dimanche_ok': False},
    {'ordre': 5, 'delai_jours': 6, 'delai_minutes': 0,
     'heure_cible': CRENEAU_MESSAGE,
     'canal': CanalRelance.WHATSAPP, 'libelle': 'Garanties fabricants',
     'template_cle': 'j6_garanties', 'dimanche_ok': False},
    {'ordre': 6, 'delai_jours': 7, 'delai_minutes': 0,
     'heure_cible': CRENEAU_APPEL,
     'canal': CanalRelance.APPEL, 'libelle': 'Appel de suivi',
     'template_cle': 'appel_suivi_j7', 'dimanche_ok': False},
    {'ordre': 7, 'delai_jours': 9, 'delai_minutes': 0,
     'heure_cible': CRENEAU_MESSAGE,
     'canal': CanalRelance.WHATSAPP, 'libelle': 'Validité de la proposition',
     'template_cle': 'j9_validite', 'dimanche_ok': False},
    {'ordre': 8, 'delai_jours': 11, 'delai_minutes': 0,
     'heure_cible': CRENEAU_APPEL,
     'canal': CanalRelance.APPEL, 'libelle': 'Appel de suivi',
     'template_cle': 'appel_suivi_j11', 'dimanche_ok': False},
    {'ordre': 9, 'delai_jours': 13, 'delai_minutes': 0,
     'heure_cible': CRENEAU_MESSAGE,
     'canal': CanalRelance.WHATSAPP, 'libelle': 'Dernier message',
     'template_cle': 'j13_dernier', 'dimanche_ok': False},
    {'ordre': 10, 'delai_jours': 14, 'delai_minutes': 0,
     'heure_cible': CRENEAU_MESSAGE,
     'canal': CanalRelance.WHATSAPP, 'libelle': 'Mise en pause',
     'template_cle': 'j14_pause', 'dimanche_ok': False},
]

# Réveil des dormants — deux touches seulement, très espacées.
# CAD74 (décision fondateur du 21/09/2026, Q20) : le réveil J30 est un APPEL
# (son script vit avec la touche, CAD151) ; le J60 reste un WhatsApp et porte
# « reveil_a3 » — ce que `_adapter_gabarits_reveil` lui assigne déjà par rang,
# donc la clé seedée ici n'est pas retouchée. Le nombre (2), l'ordre et les
# J+N ne changent pas. La touche saisonnière `reveil_b` n'est PAS un barreau
# de cette échelle : c'est une touche calendaire, hors gabarit
# (`apps/crm/cadence_reveil_saison.py`).
CADENCE_REVEIL_DEFAUT = [
    {'ordre': 1, 'delai_jours': 30, 'delai_minutes': 0, 'heure_cible': None,
     'canal': CanalRelance.APPEL, 'libelle': 'Réveil J30',
     'template_cle': 'reveil_a1', 'dimanche_ok': False},
    {'ordre': 2, 'delai_jours': 60, 'delai_minutes': 0, 'heure_cible': None,
     'canal': CanalRelance.WHATSAPP, 'libelle': 'Réveil J60',
     'template_cle': 'reveil_a2', 'dimanche_ok': False},
]

# CAD128 (21/09/2026) — DEUXIÈME AFFAIRE : un client SIGNÉ qui redemande un
# devis est le meilleur lead du portefeuille (il a déjà acheté), et la garde
# doublon le renvoyait sans protocole. Il reçoit ici une cadence COURTE, avec
# son propre texte — jamais les six appels sur quatorze jours du protocole
# contact.
#
# Les deux barreaux ne sont PAS inventés : ce sont les DEUX PREMIERS du
# protocole validé (`CADENCE_CONTACT_DEFAUT`, message d'identité puis appel
# d'ouverture trois minutes après), arrêtés là. Seule la clé de message du
# premier change — un client acquis ne se présente pas, on le retrouve.
CADENCE_DEUXIEME_AFFAIRE_DEFAUT = [
    dict(CADENCE_CONTACT_DEFAUT[0], template_cle='deuxieme_affaire'),
    dict(CADENCE_CONTACT_DEFAUT[1], template_cle='appel_ouverture'),
]

# ── PARAM-CADENCE (décision fondateur du 25/09/2026) ────────────────────────
#
# La chaîne APRÈS L'APPEL (le filet QJ-INVARIANT) et AUTOUR DE LA VISITE était
# codée en dur dans ``apps/crm/services.py`` — libellés, délais, canaux, et le
# moteur reconnaissait ces étapes par leur LIBELLÉ. Elle vit désormais ICI,
# comme les cadences du protocole : deux gabarits par société, modifiables
# dans Paramètres → CRM, et chaque barreau porte une CLÉ STABLE que le moteur
# lit (``apps/crm/cadence_config.py``). Les libellés ci-dessous sont les
# DÉFAUTS LIVRÉS — la source unique : ``crm.services`` les réexporte sous
# ses anciens noms (``FILET_JOINT_LIBELLE``…), il ne les redéclare pas.
#
# Deux familles de barreaux, et la différence compte :
#   * PILIERS (devis, planifier, confirmation, debrief, devis_modifie,
#     rappel_convenu, decider_suite) — la chaîne ne tient pas sans eux : un
#     barreau supprimé ou désactivé retombe sur le défaut livré ;
#   * PALIERS optionnels (appel_apres_reponse, message_creneau,
#     dernier_appel) — désactivés ou supprimés, ils sont SAUTÉS : la chaîne
#     passe directement à la marche suivante, jamais une boucle.
#
# Sens de ``delai_jours`` : jours APRÈS le geste qui pose l'étape (après la
# visite pour ``debrief`` et ``devis_modifie``) ; pour ``confirmation`` seule,
# jours AVANT la visite (la veille = 1, jamais avant aujourd'hui).

CLE_DEVIS = 'devis'
CLE_APPEL_APRES_REPONSE = 'appel_apres_reponse'
CLE_MESSAGE_CRENEAU = 'message_creneau'
CLE_DERNIER_APPEL = 'dernier_appel'
CLE_RAPPEL_CONVENU = 'rappel_convenu'
CLE_DECIDER_SUITE = 'decider_suite'
CLE_PLANIFIER = 'planifier'
CLE_CONFIRMATION = 'confirmation'
CLE_DEBRIEF = 'debrief'
CLE_DEVIS_MODIFIE = 'devis_modifie'

#: Les barreaux optionnels : inactifs ou supprimés, ils sont SAUTÉS.
CLES_PALIERS = frozenset({
    CLE_APPEL_APRES_REPONSE, CLE_MESSAGE_CRENEAU, CLE_DERNIER_APPEL})

LIBELLE_DEVIS = 'Préparer et envoyer le devis (ou fixer un rappel)'
LIBELLE_APPEL_APRES_REPONSE = 'Appeler le client — il a répondu au message'
LIBELLE_MESSAGE_CRENEAU = "Message — proposer un créneau pour l'appel"
LIBELLE_DERNIER_APPEL = 'Rappeler — dernier essai avant de chiffrer'
LIBELLE_RAPPEL_CONVENU = 'Rappeler le client — rappel convenu'
LIBELLE_DECIDER_SUITE = 'Décider la suite — perdu (motif) ou relance ultérieure'
LIBELLE_PLANIFIER = 'Planifier la visite technique convenue'
LIBELLE_CONFIRMATION = 'Confirmer la visite (veille)'
LIBELLE_DEBRIEF = 'Débrief visite — rappeler le client'
LIBELLE_DEVIS_MODIFIE = 'Préparer le devis modifié — rappeler le client'


def _barreau_moteur(ordre, cle, libelle, *, delai_jours, canal,
                    template_cle='', dimanche_ok=False, samedi_ok=False):
    # D1 — symétrique des gabarits du protocole (`CADENCE_CONTACT_DEFAUT`…) :
    # ces deux drapeaux étaient absents d'ici (seul `dimanche_ok`, figé à
    # `False`, existait), alors que `seed_cadence` les lit déjà tous les deux
    # (`entry.get('dimanche_ok'/'samedi_ok', False)`) et que le modèle porte
    # les deux colonnes. Défauts INCHANGÉS (`False`) tant qu'aucun appel ne
    # les force — le samedi/dimanche ne s'ouvre que par un geste humain,
    # depuis Paramètres.
    return {'ordre': ordre, 'cle': cle, 'delai_jours': delai_jours,
            'delai_minutes': 0, 'heure_cible': None, 'canal': canal,
            'libelle': libelle, 'template_cle': template_cle,
            'dimanche_ok': dimanche_ok, 'samedi_ok': samedi_ok}


#: « Après l'appel (avant devis) » — contrat ``cadence_relance_v2.json``
#: (``exemple_apres_contact``). Les délais sont ceux que le moteur appliquait
#: en dur : le devis DEMAIN, l'appel au client qui a répondu TOUT DE SUITE
#: (prochain créneau d'appel), le message de créneau le jour même, le dernier
#: essai le lendemain, la décision après un refus le lendemain.
CADENCE_APRES_CONTACT_DEFAUT = [
    _barreau_moteur(1, CLE_DEVIS, LIBELLE_DEVIS, delai_jours=1,
                    canal=CanalRelance.APPEL),
    # CAD18 — le seul barreau du filet qui porte un script (le client a
    # répondu au message d'identité avant l'appel).
    _barreau_moteur(2, CLE_APPEL_APRES_REPONSE, LIBELLE_APPEL_APRES_REPONSE,
                    delai_jours=0, canal=CanalRelance.APPEL,
                    template_cle='appel_apres_reponse'),
    _barreau_moteur(3, CLE_MESSAGE_CRENEAU, LIBELLE_MESSAGE_CRENEAU,
                    delai_jours=0, canal=CanalRelance.WHATSAPP),
    _barreau_moteur(4, CLE_DERNIER_APPEL, LIBELLE_DERNIER_APPEL,
                    delai_jours=1, canal=CanalRelance.APPEL),
    _barreau_moteur(5, CLE_RAPPEL_CONVENU, LIBELLE_RAPPEL_CONVENU,
                    delai_jours=1, canal=CanalRelance.APPEL),
    _barreau_moteur(6, CLE_DECIDER_SUITE, LIBELLE_DECIDER_SUITE,
                    delai_jours=1, canal=CanalRelance.APPEL),
]

#: « Visite technique » — contrat ``cadence_relance_v2.json``
#: (``exemple_visite``) : planifier le jour même, confirmer la VEILLE (le
#: premier motif d'échec d'une visite est un client absent), débriefer le
#: lendemain, préparer le devis modifié le lendemain.
CADENCE_VISITE_DEFAUT = [
    _barreau_moteur(1, CLE_PLANIFIER, LIBELLE_PLANIFIER, delai_jours=0,
                    canal=CanalRelance.APPEL),
    _barreau_moteur(2, CLE_CONFIRMATION, LIBELLE_CONFIRMATION, delai_jours=1,
                    canal=CanalRelance.WHATSAPP,
                    template_cle='visite_confirmation'),
    _barreau_moteur(3, CLE_DEBRIEF, LIBELLE_DEBRIEF, delai_jours=1,
                    canal=CanalRelance.APPEL),
    _barreau_moteur(4, CLE_DEVIS_MODIFIE, LIBELLE_DEVIS_MODIFIE,
                    delai_jours=1, canal=CanalRelance.APPEL),
]

#: Les deux gabarits du MOTEUR : jamais un plan qu'on démarre sur un lead
#: (le démarrage d'une cadence les refuse), seulement la configuration des
#: étapes qu'il pose.
CADENCES_MOTEUR = (Cadence.APRES_CONTACT, Cadence.VISITE)

#: Cadence -> gabarit par défaut. ``generique`` garde EXACTEMENT les 5
#: barreaux historiques (aucune réécriture rétroactive).
CADENCES_DEFAUT = {
    Cadence.CONTACT: CADENCE_CONTACT_DEFAUT,
    Cadence.APRES_DEVIS: CADENCE_APRES_DEVIS_DEFAUT,
    Cadence.REVEIL: CADENCE_REVEIL_DEFAUT,
    Cadence.GENERIQUE: CADENCE_RELANCE_DEFAUT,
    Cadence.DEUXIEME_AFFAIRE: CADENCE_DEUXIEME_AFFAIRE_DEFAUT,
    Cadence.APRES_CONTACT: CADENCE_APRES_CONTACT_DEFAUT,
    Cadence.VISITE: CADENCE_VISITE_DEFAUT,
}


def barreau_par_defaut(cadence, cle):
    """PARAM-CADENCE — le barreau livré par défaut de cette clé (une
    COPIE du ``dict`` de ``CADENCES_DEFAUT``), ou ``None`` si la clé est
    inconnue dans cette cadence."""
    return next((dict(entree) for entree in CADENCES_DEFAUT.get(cadence, [])
                 if entree.get('cle') == cle), None)


class CadenceRelanceEtape(TenantModel):
    """Un barreau (délai + canal + libellé) de la cadence de relance par
    défaut d'une société — modifiable via l'API Paramètres. Purement un
    GABARIT : ``crm.RelanceEtape`` matérialise une COPIE indépendante par
    lead au moment de l'initialisation (modifier le gabarit après coup
    n'altère jamais un plan déjà initialisé sur un lead)."""

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,  # on_delete: purge tenant
        related_name='cadence_relance_etapes')
    # MRY4 — à QUELLE cadence ce barreau appartient. Défaut `contact` pour les
    # créations nouvelles ; la migration 0081 étiquette l'existant `generique`.
    cadence = models.CharField(
        max_length=20, choices=Cadence.choices, default=Cadence.CONTACT,
        verbose_name='Cadence')
    ordre = models.PositiveIntegerField(default=0)
    delai_jours = models.PositiveIntegerField(
        help_text="Nombre de jours après le point de départ du plan.")
    # MRY4 — granularité MINUTE : la 2ᵉ touche de la prise de contact tombe à
    # J0 + 3 minutes (« rappelé dans les cinq minutes »), ce qu'un délai en
    # jours ne pouvait pas exprimer.
    delai_minutes = models.PositiveIntegerField(
        default=0,
        help_text="Minutes ajoutées au délai en jours (0 à 1439).")
    # Heure locale visée (Africa/Casablanca) : quand elle est posée, elle
    # REMPLACE l'heure calculée avant le recalage sur la fenêtre d'appel.
    heure_cible = models.TimeField(
        null=True, blank=True, verbose_name='Heure cible')
    # Clé du gabarit de message (`parametres.MessageTemplate.Cle`). TEXTE
    # LIBRE volontairement : une FK créerait une dépendance d'import entre
    # deux référentiels qui n'ont pas à se connaître.
    template_cle = models.CharField(
        max_length=40, blank=True, default='',
        verbose_name='Clé du gabarit de message')
    # Seule une touche marquée ainsi peut tomber un dimanche (16 h-19 h) —
    # le rendez-vous du protocole v3 pour les prospects injoignables en
    # semaine. Toutes les autres sont recalées sur un jour ouvré.
    dimanche_ok = models.BooleanField(
        default=False, verbose_name='Autorisée le dimanche')
    # CAD43 — symétrique exact de `dimanche_ok`, pour le SAMEDI. Les jours
    # ouvrés par défaut sont lundi-vendredi : toute touche calculée un samedi
    # est repoussée au lundi, y compris le message d'identité J0. Cocher
    # « Samedi » dans Paramètres → Notifications ouvrirait le samedi aux SIX
    # appels d'un coup ; ce drapeau PAR TOUCHE permet d'ouvrir le seul
    # message (canal silencieux) pour le lead arrivé le vendredi soir.
    # Par défaut FAUX partout : rien ne change tant que personne ne coche.
    samedi_ok = models.BooleanField(
        default=False, verbose_name='Autorisée le samedi',
        help_text='Cette touche peut-elle tomber un samedi ? À réserver aux '
                  'canaux silencieux (WhatsApp, e-mail) — un appel le samedi '
                  "n'est pas dans le protocole.")
    canal = models.CharField(max_length=20, choices=CanalRelance.choices)
    libelle = models.CharField(max_length=150)
    actif = models.BooleanField(default=True)
    # PARAM-CADENCE (25/09/2026) — clé STABLE d'un barreau que le MOTEUR pose
    # lui-même (cadences ``apres_contact`` et ``visite``) : c'est par elle,
    # jamais par le libellé, qu'il retrouve le barreau. Posée par le seed,
    # jamais par l'écran (lecture seule dans l'API). Vide sur les barreaux du
    # protocole et sur un barreau ajouté à la main — le moteur ne pose jamais
    # ceux-là. Unique par (société, cadence) quand elle est posée.
    cle = models.CharField(
        max_length=40, blank=True, default='', verbose_name='Clé moteur',
        help_text='Clé stable lue par le moteur (jamais modifiable).')

    class Meta:
        verbose_name = 'Étape de cadence de relance'
        verbose_name_plural = 'Étapes de cadence de relance'
        ordering = ['cadence', 'ordre', 'delai_jours']
        # Un seul barreau par société + cadence + ordre (idempotence
        # seed/backfill). L'ordre 1 existe désormais dans CHAQUE cadence :
        # l'ancienne clé (company, ordre) les aurait fait se percuter.
        #
        # CAD124 — PAS D'AXE SEGMENT : décision du 21/09/2026. La clé reste
        # (société, cadence, ordre) et n'accueillera PAS `type_installation`.
        # Le CRM lit déjà le segment pour scorer (`apps/crm/scoring.py`) et
        # pour exiger les bons champs au devis (`apps/ventes/devis_auto.py`),
        # mais le GABARIT de cadence reste aveugle : le levier langue/texte
        # (CAD126) et le playbook conditionné sur `{type_installation}`
        # (CAD125) couvrent l'essentiel sans migration ni sélecteur de plus.
        # Une quatrième dimension ici multiplierait les barreaux à maintenir
        # par le nombre de segments, pour un protocole dont le fondateur a
        # tranché qu'il ne change pas. La décision se rouvrira sur le VOLUME
        # par segment (comptage CADM7), pas avant.
        unique_together = [('company', 'cadence', 'ordre')]
        indexes = [
            models.Index(fields=['company', 'cadence', 'actif'],
                         name='param_cad_co_cad_act_idx'),
        ]
        constraints = [
            # PARAM-CADENCE — UN barreau par clé moteur dans une cadence : le
            # moteur ne doit jamais avoir à choisir entre deux « devis ».
            models.UniqueConstraint(
                fields=['company', 'cadence', 'cle'],
                condition=models.Q(cle__gt=''),
                name='param_cad_cle_uniq'),
        ]

    def __str__(self):
        return (f'{self.company_id}: [{self.cadence}] J+{self.delai_jours} '
                f'{self.libelle}')

    @classmethod
    def seed_defaults(cls, company):
        """Seede la cadence NEUTRE historique (``generique``) pour ``company``.

        Signature et effet INCHANGÉS depuis RELANCE FOUNDATION : 5 barreaux
        J+2/5/10/20/35. Les trois cadences nommées passent par
        ``seed_cadence`` — mélanger les deux ferait varier en silence ce que
        cette méthode a toujours produit."""
        return cls.seed_cadence(company, Cadence.GENERIQUE)

    @classmethod
    def seed_cadence(cls, company, cadence):
        """MRY4 — seede UNE cadence nommée (idempotent, additif).

        ``get_or_create`` par (company, cadence, ordre) : rejouable sans
        doublon, ne retouche JAMAIS un barreau déjà personnalisé (le
        fondateur peut décaler un délai sans qu'un redéploiement l'écrase)."""
        crees = 0
        # PARAM-CADENCE — une clé déjà présente (barreau déplacé à un autre
        # rang par la société) n'est jamais re-seedée : la contrainte
        # d'unicité (société, cadence, clé) l'interdirait, et le barreau de la
        # société EST ce barreau-là.
        cles_prises = set(cls.objects.filter(
            company=company, cadence=cadence).exclude(cle='')
            .values_list('cle', flat=True))
        for entry in CADENCES_DEFAUT.get(cadence, []):
            cle = entry.get('cle', '')
            if cle and cle in cles_prises:
                continue
            try:
                with transaction.atomic():
                    _, created = cls.objects.get_or_create(
                        company=company, cadence=cadence,
                        ordre=entry['ordre'],
                        defaults={
                            'delai_jours': entry['delai_jours'],
                            'delai_minutes': entry.get('delai_minutes', 0),
                            'heure_cible': entry.get('heure_cible'),
                            'template_cle': entry.get('template_cle', ''),
                            'dimanche_ok': entry.get('dimanche_ok', False),
                            # CAD43 — absent de tous les gabarits par défaut :
                            # le samedi ne s'ouvre que par un geste humain.
                            'samedi_ok': entry.get('samedi_ok', False),
                            'canal': entry['canal'],
                            'libelle': entry['libelle'],
                            'actif': True,
                            'cle': cle,
                        })
            except IntegrityError:
                # Seed concurrent : la clé vient d'être posée par l'autre.
                continue
            if created:
                crees += 1
        return crees

    @classmethod
    def barreau_par_cle(cls, company, cadence, cle, *, inactif_ok=False):
        """PARAM-CADENCE — LE barreau de clé ``cle`` de cette cadence pour
        ``company`` : actif (ou inactif si ``inactif_ok``), seedé à la volée
        si la cadence n'a encore AUCUN barreau (même règle que
        ``cadence_pour`` : jamais un défaut codé en dur côté appelant),
        ``None`` s'il a été supprimé — ou désactivé sans ``inactif_ok``.

        UNE requête dans le cas courant : les barreaux d'une cadence sont peu
        nombreux, on les lit d'un coup."""
        def _lignes():
            return list(cls.objects.filter(company=company, cadence=cadence))

        lignes = _lignes()
        if not lignes:
            cls.seed_cadence(company, cadence)
            lignes = _lignes()
        barreau = next((b for b in lignes if b.cle == cle), None)
        if barreau is None or (not barreau.actif and not inactif_ok):
            return None
        return barreau

    @classmethod
    def cadence_pour(cls, company, cadence=Cadence.CONTACT):
        """Barreaux ACTIFS d'UNE cadence de ``company``, triés par ordre —
        seedés à la volée si cette cadence est vide (sociétés créées avant le
        référentiel : jamais un défaut codé en dur côté appelant)."""
        def _qs():
            return cls.objects.filter(
                company=company, cadence=cadence, actif=True
            ).order_by('ordre', 'delai_jours', 'delai_minutes')

        if not _qs().exists():
            cls.seed_cadence(company, cadence)
        return list(_qs())
