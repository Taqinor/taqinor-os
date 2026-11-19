"""Copilote vague 2 (lane CALA) — les actions de l'assistant sur le calepinage.

Catalogue déclaré en code (registre AG1, :mod:`apps.agent.registry`) et
découvert par le manifeste (``platform.py`` → ``agent_actions_module``,
ARC33) : les actions disparaissent quand le module calepinage est éteint pour
la société. Toutes naissent dans le lot ``copilote`` (servies seulement copilote
allumé) ; hors noyau, elles sont ``natif_seul`` (jamais servies à LangChain).

Ce module ne contient AUCUNE logique d'exécution : chaque action nomme une
route qui re-vérifie permission ET société à l'exécution (``calepinage_voir``
pour lire, ``calepinage_gerer`` pour écrire — les gardes réelles des routes).
``company`` n'apparaît jamais dans les entrées ; aucune entrée ``forcer``,
``derogation_electrique``, ``taux_tva``, ``remise_globale`` ni ``remplacer``.

Règles qui bornent ce que l'assistant DIT (décisions D-ACAL) :
* la production montrée au client est celle du DEVIS (D-ACAL-6) ; le P50 du
  calepinage est une étude technique INTERNE, jamais un texte pour le client ;
* production en « borne haute » (pertes non renseignées) : le dire tel quel,
  ne citer ni P90 ni PR (D-ACAL-7) ;
* un verdict électrique BLOQUANT se lève à l'écran par un approbateur
  (dérogation tracée, D-ACAL-9) — jamais par l'assistant ;
* l'approbation et le pack technique restent humains (D-ACAL-11/24) ;
* l'assistant ne dessine pas : pour dessiner, il donne le lien de l'atelier.
"""
from __future__ import annotations

from apps.calepinage.permissions import CAL_GERER, CAL_VOIR
from apps.agent.registry import (
    AgentAction, LOT_COPILOTE, RISK_INTERNAL, RISK_OUTWARD, register, _REGISTRY,
)

BASE = '/api/django/calepinage/calepinages/'

#: La règle de lecture de la production, répétée dans chaque description qui
#: la sert (le modèle ne lit que la description de l'outil qu'il appelle).
REGLE_PRODUCTION = (
    "Le P50 est une étude technique INTERNE du calepinage : la production "
    "montrée au client est celle du devis. Si « mention » dit « borne "
    "haute », dis-le tel quel et ne cite ni P90 ni PR.")


def _schema(proprietes, requis=()):
    return {'type': 'object', 'properties': proprietes,
            'required': list(requis), 'additionalProperties': False}


ENTIER = {'type': 'integer', 'minimum': 1}


DU_LEAD = AgentAction(
    key='calepinage.du_lead',
    label="Où en est le calepinage d'un lead",
    description=(
        "Sert à : savoir si un lead a un calepinage, où il en est (conception, "
        "simulation, devis lié, approbation, reprise de la visite) et le geste "
        "suivant (« a_faire »). Ne pas utiliser pour : dessiner (donne le lien "
        "« lien »), ni compter des panneaux avant dessin "
        "(calepinage.contenance). Exemple : « où en est le calepinage de "
        "Karim Alami ? » → lead=1637. Résultat : le résumé du calepinage "
        "ouvert, ou null et a_faire=creer (suite : calepinage.preparer). "
        + REGLE_PRODUCTION),
    endpoint=BASE + 'du-lead/',
    method='GET',
    inputs=_schema({'lead': dict(ENTIER, description='Identifiant du lead.')},
                   ('lead',)),
    required_permission=CAL_VOIR,
    risk=RISK_INTERNAL,
    carte='fiche_calepinage',
    lot=LOT_COPILOTE,
)

RESUME = AgentAction(
    key='calepinage.resume',
    label="Résumé d'un calepinage",
    description=(
        "Sert à : expliquer un calepinage connu par son identifiant (ou une "
        "de ses variantes) : modules, kWc, pans, simulation, pertes "
        "principales, verdict électrique, devis lié, approbation. Ne pas "
        "utiliser pour : un lead (calepinage.du_lead). Exemple : « explique-"
        "moi le résultat du calepinage 12 » → id=12. Résultat : un résumé "
        "court avec « a_faire » et « lien ». " + REGLE_PRODUCTION),
    endpoint=BASE + '{id}/resume/',
    method='GET',
    inputs=_schema({'id': dict(ENTIER, description='Identifiant du calepinage.'),
                    'variante': dict(ENTIER, description='Variante du même calepinage (facultatif).')},
                   ('id',)),
    required_permission=CAL_VOIR,
    risk=RISK_INTERNAL,
    carte='fiche_calepinage',
    lot=LOT_COPILOTE,
)

VARIANTES_COMPARER = AgentAction(
    key='calepinage.variantes_comparer',
    label='Comparer les variantes',
    description=(
        "Sert à : comparer les variantes d'un calepinage (modules, kWc, "
        "production simulée, écarts à la variante retenue). Ne pas utiliser "
        "pour : retenir une variante (calepinage.retenir). Exemple : « compare "
        "les variantes du calepinage 12 » → id=12. Résultat : une ligne par "
        "variante ; une variante non simulée a ses chiffres à null (jamais "
        "zéro). Ne cite P75/P90 d'une variante que si le résumé dit la "
        "production complète. " + REGLE_PRODUCTION),
    endpoint=BASE + '{id}/comparer/',
    method='GET',
    inputs=_schema({'id': dict(ENTIER, description='Identifiant du calepinage.')},
                   ('id',)),
    required_permission=CAL_VOIR,
    risk=RISK_INTERNAL,
    lot=LOT_COPILOTE,
)

SIMULATION_SUIVRE = AgentAction(
    key='calepinage.simulation_suivre',
    label="Suivre une simulation lancée",
    description=(
        "Sert à : relire une simulation lancée par calepinage.simuler, avec "
        "le job_id qu'elle a rendu. Ne pas utiliser pour : lancer une "
        "simulation. Exemple : job_id=88. Résultat : statut du calcul ; "
        "« resultat » null = pas encore fini : relis au tour suivant, jamais "
        "plus de deux relectures dans un tour. En échec, « elements[0].champ » "
        "nomme le réglage à corriger : dis-le, sans recopier "
        "« message_erreur » (texte technique). Une fois fini, enchaîne sur "
        "calepinage.resume."),
    endpoint='/api/django/calepinage/moteur/resultat/{job_id}/',
    method='GET',
    inputs=_schema({'job_id': dict(ENTIER, description='Le job_id rendu par calepinage.simuler.')},
                   ('job_id',)),
    required_permission=CAL_VOIR,
    risk=RISK_INTERNAL,
    lot=LOT_COPILOTE,
)

SIMULER = AgentAction(
    key='calepinage.simuler',
    label='Lancer la simulation de production',
    description=(
        "Sert à : lancer (ou relire si rien n'a changé) la simulation de "
        "production d'un calepinage dessiné, ou d'une de ses variantes. "
        "N'écrit que l'étude technique interne : aucun statut, aucun devis. "
        "Ne pas utiliser pour : un calepinage sans pans équipés (dessiner "
        "d'abord, lien de l'atelier). Exemple : « lance la simulation du "
        "calepinage 12 » → id=12. Résultat : 202 avec un job_id (suis-le avec "
        "calepinage.simulation_suivre), ou 200 deja_calcule (enchaîne sur "
        "calepinage.resume). Un refus 409 NOMME le réglage manquant : "
        "« parametres.simulation.* » = réglage société (Paramètres du "
        "calepinage), « plans » = panneau non désigné (onglet Matériel "
        "électrique), « site.pin » = épingle du site dans l'atelier, "
        "« temperatures » = saisies électriques ; dis-le et donne le lien du "
        "calepinage (erp.ouvrir). Ne relance jamais pour forcer un calcul."),
    endpoint=BASE + '{id}/simuler/',
    method='POST',
    inputs=_schema({'id': dict(ENTIER, description='Identifiant du calepinage.'),
                    'variante_id': dict(ENTIER, description='Variante du même calepinage (facultatif).')},
                   ('id',)),
    required_permission=CAL_GERER,
    risk=RISK_INTERNAL,
    lot=LOT_COPILOTE,
    objets={'id': 'calepinage', 'variante_id': 'variante'},
)

PREPARER = AgentAction(
    key='calepinage.preparer',
    label="Ouvrir le calepinage du lead et y reprendre la visite validée",
    description=(
        "Sert à : préparer le calepinage d'un lead en un geste — l'ouvrir s'il "
        "n'existe pas (jamais un second), puis y reprendre les mesures et les "
        "photos de la visite VALIDÉE (rien n'est converti, rien n'est "
        "dessiné). Ne pas utiliser pour : dessiner ou poser des panneaux (le "
        "dessin reste humain : le résultat est un bouton vers l'atelier), ni "
        "un lead dont calepinage.du_lead dit qu'il a déjà un calepinage à jour. "
        "Exemple : « la visite de Karim Alami est validée, prépare son "
        "calepinage » → lead=1637. Résultat : le bouton « Ouvrir le "
        "calepinage », cree, et reprise_visite = reprise | deja_reprise | "
        "aucune_visite_validee."),
    endpoint=BASE + 'preparer/',
    method='POST',
    inputs=_schema({'lead': dict(ENTIER, description='Identifiant du lead.')},
                   ('lead',)),
    required_permission=CAL_GERER,
    risk=RISK_OUTWARD,
    confirm_summary=(
        "Ouvrir le calepinage de ce lead (créé s'il n'existe pas) et y "
        "reprendre les mesures et les photos de la visite validée. Rien n'est "
        "dessiné ni converti ; aucun devis ne change."),
    carte='lien_ecran',
    lot=LOT_COPILOTE,
    objets={'lead': 'lead'},
)

PUBLIER_APERCU = AgentAction(
    key='calepinage.publier_apercu',
    label='Aperçu : publier la conception au devis',
    description=(
        "Sert à : savoir, SANS rien écrire, ce que changerait la publication "
        "de la conception au devis : génération du brouillon ou "
        "resynchronisation du devis lié (même ENVOYÉ), ancien et nouveau "
        "total TTC, kWc avant / après. Ne pas utiliser pour : publier (c'est "
        "calepinage.publier_devis, qui exige les deux totaux lus ici). "
        "Exemple : « mets le devis à jour avec le calepinage 12 » → id=12, "
        "puis propose calepinage.publier_devis avec ces totaux. Résultat : "
        "geste, devis lié, corrige_apres_envoi, ancien_total_ttc, "
        "nouveau_total_ttc, a_faire (publier | rien). Un devis figé ou un "
        "verdict électrique bloquant est refusé ici (409 nommé) : dis-le et "
        "donne le lien."),
    endpoint=BASE + '{id}/publier-devis/apercu/',
    method='GET',
    inputs=_schema({'id': dict(ENTIER, description='Identifiant du calepinage.')},
                   ('id',)),
    required_permission=CAL_GERER,
    risk=RISK_INTERNAL,
    lot=LOT_COPILOTE,
)

MONTANT = {'type': 'string', 'pattern': r'^\d+\.\d{2}$'}

PUBLIER_DEVIS = AgentAction(
    key='calepinage.publier_devis',
    label=('Mettre le devis à jour depuis la conception — un devis déjà envoyé au '
           'client est corrigé en place (ancien → nouveau total TTC)'),
    description=(
        "Sert à : publier la conception du calepinage au devis — générer le "
        "devis BROUILLON s'il n'y en a pas, sinon resynchroniser le devis lié, "
        "y compris un devis déjà ENVOYÉ (corrigé en place, tracé « corrigé "
        "après envoi »). Aucun PDF, aucun statut, aucune TVA ni remise. Ne pas "
        "utiliser pour : un devis accepté, refusé ou expiré (refusé : il se "
        "révise), ni lever un verdict électrique bloquant (dérogation humaine "
        "à l'écran). Exemple : après calepinage.publier_apercu (ancien "
        "84500.00, nouveau 86900.00, devis 45) → id=12, devis=45, ancien_total_ttc=\"84500.00\", "
        "nouveau_total_ttc=\"86900.00\" (sans ancien_total_ttc quand l'aperçu "
        "le dit null). Résultat : le devis généré ou resynchronisé ; 409 "
        "apercu_perime si les totaux ont bougé : relis l'aperçu et refais "
        "confirmer."),
    endpoint=BASE + '{id}/publier-devis/',
    method='POST',
    inputs=_schema({
        'id': dict(ENTIER, description='Identifiant du calepinage.'),
        'ancien_total_ttc': dict(MONTANT, title='Ancien total TTC (MAD)',
                                 description="Recopié de l'aperçu ; absent sans devis lié."),
        'nouveau_total_ttc': dict(MONTANT, title='Nouveau total TTC (MAD)',
                                  description="Recopié de l'aperçu."),
        'devis': dict(ENTIER, title='Devis mis à jour',
                      description="Identifiant du devis lié, recopié de l'aperçu (devis.id) ; "
                                  "absent quand l'aperçu dit devis null. Obligatoire si ce "
                                  "devis est déjà envoyé."),
    }, ('id', 'nouveau_total_ttc')),
    required_permission=CAL_GERER,
    risk=RISK_OUTWARD,
    confirm_summary=(
        "Mettre le devis à jour depuis la conception de ce calepinage, aux "
        "totaux affichés (un devis envoyé est corrigé en place). Aucun PDF, "
        "aucun envoi au client."),
    lot=LOT_COPILOTE,
    objets={'id': 'calepinage', 'devis': 'devis'},
)

RETENIR = AgentAction(
    key='calepinage.retenir',
    label=('Retenir la variante comme conception (approbation périmée, devis '
           'à resynchroniser)'),
    description=(
        "Sert à : retenir une variante d'un calepinage : elle devient LA "
        "conception (nouvelle version si elle diffère). L'approbation déjà "
        "donnée devient périmée et le devis lié devra être republié "
        "(calepinage.publier_apercu puis calepinage.publier_devis) ; le devis "
        "et la page du client ne changent PAS d'eux-mêmes. Ne pas utiliser "
        "pour : approuver (geste humain) ni publier au devis. Exemple : "
        "« retiens la variante paysage du calepinage 12 » → id=12, "
        "variante_id=7 (lu dans calepinage.variantes_comparer). Résultat : la "
        "variante retenue. Refus relayés tels quels : feu vert du bureau "
        "d'études (400), verdict électrique bloquant (409, dérogation humaine), "
        "devis lié figé (409 : il se révise), variante sans conception (409)."),
    endpoint=BASE + '{id}/variantes/{variante_id}/retenir/',
    method='POST',
    inputs=_schema({'id': dict(ENTIER, description='Identifiant du calepinage.'),
                    'variante_id': dict(ENTIER, description='La variante à retenir.')},
                   ('id', 'variante_id')),
    required_permission=CAL_GERER,
    risk=RISK_OUTWARD,
    confirm_summary=(
        "Retenir cette variante : elle devient la conception du calepinage "
        "(nouvelle version si elle diffère) ; l'approbation donnée devient "
        "périmée et le devis lié devra être resynchronisé."),
    lot=LOT_COPILOTE,
    objets={'id': 'calepinage', 'variante_id': 'variante'},
)

A_TRAITER = AgentAction(
    key='calepinage.a_traiter',
    label='Calepinages à traiter',
    description=(
        "Sert à : lister les calepinages ouverts de l'utilisateur modifiés "
        "depuis 30 jours qui attendent un geste (visite à reprendre, toit à "
        "dessiner, simulation à lancer, verdict électrique à corriger, "
        "approbation, devis à publier). Ne pas utiliser pour : un lead précis "
        "(calepinage.du_lead). Exemple : « quels calepinages dois-je "
        "traiter ? » → limite=10. Résultat : des lignes avec leurs signaux, "
        "« a_faire » et « lien » ; « evalue: false » = simulation et verdict "
        "électrique non évalués pour cette ligne (ne les devine pas). Aucun "
        "classement de personnes."),
    endpoint=BASE + 'a-traiter/',
    method='GET',
    inputs=_schema({'limite': {'type': 'integer', 'minimum': 1, 'maximum': 20,
                               'description': 'Nombre de lignes (10 par défaut).'}}),
    required_permission=CAL_VOIR,
    risk=RISK_INTERNAL,
    carte='liste_calepinages',
    lot=LOT_COPILOTE,
)

CONTENANCE = AgentAction(
    key='calepinage.contenance',
    label='Estimer combien de panneaux tiennent',
    description=(
        "Sert à : ESTIMER, avant tout dessin, combien de panneaux tiennent sur "
        "un toit : depuis la visite validée (origine=visite), le tracé du "
        "calepinage ouvert (origine=trace) ou des dimensions que "
        "l'utilisateur te dicte (origine=dicte, avec longueur_m, largeur_m et "
        "pente_deg ou toit_plat). Ne pas utiliser pour : un nombre à mettre au "
        "devis ou à promettre au client — ce n'est JAMAIS un engagement, le "
        "calepinage dessiné fait foi. Exemple : « 10 m sur 6, toit plat, "
        "combien de panneaux ? » → lead=1665, origine=dicte, longueur_m=10, "
        "largeur_m=6, toit_plat=true. Résultat : une fourchette min–max par "
        "zone et au total, avec « libelle » (à répéter tel quel), « regles » "
        "et « suppositions » (à dire) ; aucune production, aucun prix. "
        "Sans panneau désigné, celui du devis automatique est pris et dit "
        "dans « suppositions » ; s'il n'y en a pas, le refus dit d'en choisir un."),
    endpoint=BASE + 'contenance/',
    method='GET',
    inputs=_schema({
        'lead': dict(ENTIER, description='Identifiant du lead.'),
        'origine': {'type': 'string', 'enum': ['visite', 'trace', 'dicte']},
        'longueur_m': {'type': 'number', 'minimum': 0.5, 'maximum': 200,
                       'description': 'Dictée seulement (m).'},
        'largeur_m': {'type': 'number', 'minimum': 0.5, 'maximum': 200,
                      'description': 'Dictée seulement (m).'},
        'pente_deg': {'type': 'number', 'minimum': 0, 'maximum': 60,
                      'description': 'Dictée seulement (degrés).'},
        'toit_plat': {'type': 'boolean', 'description': 'Dictée seulement.'},
        'produit': dict(ENTIER, description='Panneau du catalogue (facultatif).'),
    }, ('lead', 'origine')),
    required_permission=CAL_VOIR,
    risk=RISK_INTERNAL,
    carte='contenance',
    lot=LOT_COPILOTE,
)

ACTIONS = (DU_LEAD, RESUME, VARIANTES_COMPARER, SIMULATION_SUIVRE, SIMULER,
           PREPARER, PUBLIER_APERCU, PUBLIER_DEVIS, RETENIR, A_TRAITER,
           CONTENANCE)


def register_actions() -> None:
    """Enregistre les actions ``calepinage.*`` (idempotent : une clé déjà
    posée est ignorée) — appelée par la découverte des manifestes (ARC33)."""
    for action in ACTIONS:
        if action.key not in _REGISTRY:
            register(action)
