"""NTAPI32 — définition du connecteur no-code (Zapier / Make) : triggers sur
le flux d'évènements + actions d'écriture.

CE QUE CE MODULE EST. Une DÉFINITION, pas un runtime. Zapier et Make attendent
tous deux la même chose d'une intégration REST : une liste de triggers (« quand
ceci arrive, réveille mon scénario ») et une liste d'actions (« fais ceci »),
chacune décrite par sa méthode, son URL, son scope et sa forme de corps. Ce
module produit cette liste ; le PLATEAU no-code fait les appels HTTP lui-même.
Aucun appel sortant n'est émis ici, aucune donnée de société n'est lue.

POURQUOI DES TRIGGERS DE POLLING ET NON DES REST HOOKS. Un abonnement webhook
(``publicapi.Webhook``) exige une URL https publique stable, que la plupart des
comptes no-code n'exposent pas de façon fiable ; le flux à curseur
(``GET /api/public/v1/events/?after=<sequence>``, NTAPI17) est le pendant PULL
exact des mêmes signaux. Un trigger déclare donc : l'URL du flux, le paramètre
de curseur, le champ à mémoriser entre deux exécutions, et le code d'évènement
à demander (``?type=``, ajouté par cette tâche pour qu'un scénario reçoive
UNIQUEMENT son évènement).

SOURCE UNIQUE. Rien n'est listé à la main :
  * les libellés d'évènements viennent de ``constants.EVENT_CHOICES`` ;
  * la DISPONIBILITÉ d'un trigger et son scope viennent de
    ``events_feed.SCOPE_PAR_EVENEMENT`` — un évènement que le flux ne peut pas
    servir (aucun scope de lecture pour sa famille) est déclaré INDISPONIBLE
    avec son motif, jamais promis puis silencieusement vide ;
  * les actions viennent de ``docs.public_api_reference()`` (FG105), donc des
    endpoints d'écriture RÉELLEMENT montés (NTAPI18 inclus : devis brouillon et
    ticket SAV).
Ajouter un évènement ou un endpoint d'écriture enrichit donc le connecteur sans
toucher ce fichier.
"""
from __future__ import annotations

import json
import os

from .constants import (
    EVENT_CHOICES, PUBLIC_API_BASE, PUBLIC_API_DEFAULT_VERSION,
    SCOPE_READ_EVENTS,
)

NOM_FICHIER = 'connecteur-taqinor.json'

# Chemin du flux d'évènements, reconstruit depuis la racine canonique (jamais
# une chaîne `/api/public/v1/...` réécrite en dur).
CHEMIN_FLUX = f'{PUBLIC_API_BASE}events/'

# Paramètres du polling, identiques pour tous les triggers : le plateau no-code
# mémorise `next_after` entre deux exécutions et le repasse dans `after`.
CURSEUR_PARAM = 'after'
CURSEUR_REPONSE = 'next_after'
COLLECTION_REPONSE = 'results'
# Champ de déduplication côté plateau : le même `event_id` est porté par la
# livraison webhook ET par l'entrée du flux (NTAPI10/17), donc un scénario
# branché sur les DEUX canaux ne se déclenche qu'une fois.
CHAMP_DEDUP = 'event_id'


def _libelles_evenements():
    return dict(EVENT_CHOICES)


def triggers():
    """Triggers de polling réellement servables, un par code d'évènement."""
    from .events_feed import SCOPE_PAR_EVENEMENT

    libelles = _libelles_evenements()
    resultat = []
    for code, _libelle in EVENT_CHOICES:
        scope = SCOPE_PAR_EVENEMENT.get(code)
        if not scope:
            continue
        resultat.append({
            'cle': f'evenement__{code.replace(".", "_")}',
            'evenement': code,
            'libelle': libelles.get(code, code),
            # Le canal (`read:events`) ET la famille : déclarer les deux évite
            # la clé mal taillée qui lit un flux vide sans comprendre pourquoi.
            'scopes_requis': [SCOPE_READ_EVENTS, scope],
            'polling': {
                'methode': 'GET',
                'chemin': CHEMIN_FLUX,
                'parametres': {'type': code, CURSEUR_PARAM: '{{curseur}}'},
                'collection': COLLECTION_REPONSE,
                'curseur_reponse': CURSEUR_REPONSE,
                'champ_dedup': CHAMP_DEDUP,
            },
        })
    return resultat


def triggers_indisponibles():
    """Évènements du vocabulaire que le flux ne peut PAS servir aujourd'hui.

    Déclarés explicitement avec leur motif : un plateau no-code qui proposerait
    un trigger jamais déclenché coûterait plus cher en support qu'une absence
    assumée et documentée."""
    from .events_feed import SCOPE_PAR_EVENEMENT

    return [
        {
            'evenement': code,
            'libelle': libelle,
            'motif': (
                "Aucun scope de lecture ne couvre cette famille d'évènements : "
                "le flux ne la sert pas (il n'est jamais un contournement des "
                "scopes de lecture)."),
        }
        for code, libelle in EVENT_CHOICES
        if code not in SCOPE_PAR_EVENEMENT
    ]


def actions():
    """Actions d'écriture, dérivées des endpoints d'écriture documentés."""
    from .docs import public_api_reference

    reference = public_api_reference()
    ecriture = reference['endpoints_ecriture']
    resultat = []
    for entree in ecriture['liste']:
        chemin = entree['chemin']
        resultat.append({
            'cle': _cle_action(entree),
            'libelle': entree['description'],
            'methode': entree['methode'],
            'chemin': chemin,
            'scope_requis': entree['scope'],
            # Le plateau renvoie la MÊME clé d'idempotence quand il retente une
            # étape : un rejeu ne recrée jamais l'objet (NTAPI18/XPLT5).
            'entete_idempotence': ecriture['entete_idempotence'],
        })
    return resultat


def _cle_action(entree):
    """Identifiant stable d'une action, dérivé de sa méthode + son chemin."""
    reste = entree['chemin'][len(PUBLIC_API_BASE):].strip('/')
    reste = reste.replace('<id>', 'id').replace('/', '__').replace('-', '_')
    return f"{entree['methode'].lower()}__{reste}"


def definition():
    """Manifeste complet du connecteur (dict sérialisable en JSON)."""
    return {
        'nom': 'Connecteur no-code (Zapier / Make)',
        'version_api': PUBLIC_API_DEFAULT_VERSION,
        'base_url': PUBLIC_API_BASE,
        'authentification': {
            'type': 'api_key_entete',
            'entete': 'Authorization',
            'format': 'Api-Key <clé>',
            'alternative_oauth2': {
                'grant': 'client_credentials',
                'chemin_jeton': f'{PUBLIC_API_BASE}oauth/token/',
                'entete': 'Authorization',
                'format': 'Bearer <jeton>',
            },
        },
        'triggers': triggers(),
        'triggers_indisponibles': triggers_indisponibles(),
        'actions': actions(),
    }


def rendu_json(*, indent=2):
    """Manifeste sérialisé — l'artefact que le plateau no-code importe."""
    return json.dumps(definition(), ensure_ascii=False, indent=indent) + '\n'


def ecrire(dossier, *, indent=2):
    """Écrit le manifeste dans ``dossier`` et renvoie le chemin du fichier.

    Comme le générateur de SDK (NTAPI28), ce module ÉMET du texte : c'est
    l'appelant (commande de gestion, ou un test) qui choisit la destination."""
    os.makedirs(dossier, exist_ok=True)
    chemin = os.path.join(dossier, NOM_FICHIER)
    with open(chemin, 'w', encoding='utf-8') as fichier:
        fichier.write(rendu_json(indent=indent))
    return chemin
