#!/usr/bin/env python3
"""Garde permanente : ne pas COMMANDER, ni ECRIRE, du travail mort.

POURQUOI CETTE GARDE EXISTE — INCIDENT DU 03/08/2026
----------------------------------------------------
Le module « Appels d'offres » a ete livre et declare TERMINE : 194 taches
cochees, CI verte, deploye. Mesures faites le jour meme, en ouvrant l'app :

    68 ecrans existent sur le disque dans frontend/src/features/ao/
     7 seulement sont atteignables depuis le menu
    61 ne le sont pas.
   206 ressources backend construites, testees, exposees — qu'AUCUN ecran
       n'appelle : le travail est fait, et invisible.
     L'ecran AO « Bibliotheque » appelait /ao/bibliotheque/, une route que le
       backend n'a JAMAIS enregistree ; le tableau de bord lisait 6 cles sur 6
       fausses. Les deux suites de tests etaient VERTES en se contredisant.

CAUSE RACINE — ELLE EST EN AMONT, DANS LE TEXTE DES TACHES
-----------------------------------------------------------
``check_ecrans_atteignables.py``, ``check_api_contract.py`` et
``check_api_shapes.py`` (meme incident, meme jour) attrapent le defaut APRES sa
livraison. Cette garde-ci ferme le robinet un cran plus haut : la tache de plan
elle-meme.

Une tache dit « cree ``frontend/src/features/<app>/MonEcran.jsx`` » et s'arrete
la. Personne ne declare la route — et la regle du depot (« touche uniquement
les fichiers nommes », CLAUDE.md) INTERDIT meme a l'agent de le faire, puisque
le fichier de montage n'est pas dans ``Files:``. L'agent qui OBEIT produit donc
mecaniquement un ecran mort. Le defaut n'est pas une negligence d'execution :
il est ECRIT dans la commande.

LES QUATRE FORMES GARDEES (une seule garde, quatre regles)
-----------------------------------------------------------
FORME 1 « ecran-sans-cablage » — BLOQUANTE.
    Une tache qui CREE un ecran doit nommer son fichier de montage dans
    ``Files:`` ET porter une clause d'atteignabilite dans son texte.

FORME 2 « backend-sans-consommateur » — AVERTISSEMENT SEUL, NON BLOQUANTE.
    Une tache qui cree une surface HTTP destinee a un humain, sans nommer
    aucun fichier frontend, devrait exiger son consommateur (ou porter
    « sans ecran par design : <raison> »). ELLE N'ECHOUE PAS — voir
    « HONNETETE SUR LA FORME 2 ».

FORME 3 « contrat-absent » — BLOQUANTE.
    Une tache qui nomme A LA FOIS un fichier backend et un fichier frontend
    doit exiger un contrat PARTAGE et verifiable (exemple de reponse committe
    que le test backend affirme et que le test frontend importe, ou renvoi a
    ``docs/api-contracts.md`` / ``check_api_shapes.py``). Nommer les deux
    fichiers ne suffit pas : c'est exactement ce que faisaient les taches qui
    ont produit le 404 du 03/08.

FORME 4 « composant-redefini » — AVERTISSEMENT SEUL, NON BLOQUANTE.
    Un composant possede son fichier partage ``<X>.jsx`` et un AUTRE fichier
    le REDEFINIT localement au lieu de l'importer. C'est l'autre moitie du
    gaspillage : au lieu de ne pas brancher ce qui existe, on le reecrit.
    Elle N'ECHOUE PAS — voir « HONNETETE SUR LA FORME 4 ».

MESURES DU 03/08/2026 sur ``origin/main`` (@70dbc196)
------------------------------------------------------
    1921 taches ouvertes lues dans 13 fichiers de plan.
    FORME 1 : 289 nomment un ecran, 216 le CREENT, 99 exigent deja le
              cablage, 117 ne l'exigent pas.
    FORME 2 : 917 nomment un fichier backend sans aucun fichier frontend.
    FORME 3 : 83 nomment les deux moities ; 3 seulement exigent un contrat.
    FORME 4 : 874 fichiers .jsx non-test analyses, 753 composants a fichier
              proprietaire, 25 redefinitions brutes -> 10 apres retrait des
              homonymes et des adaptations, dont 4 VRAIS doublons verifies en
              lisant le code (voir « HONNETETE SUR LA FORME 4 »).

NE LA DESACTIVEZ PAS. Si elle rougit, c'est qu'une tache vient d'etre ecrite
qui produira du travail mort, ou qu'un composant vient d'etre reecrit alors
qu'il existait deja.

HONNETETE SUR LA FORME 2 (pourquoi elle n'est pas bloquante)
-------------------------------------------------------------
La consigne etait explicite : « n'accuse QUE ce qui cree une surface HTTP
destinee a un humain [...] si tu n'arrives pas a distinguer de facon fiable,
dis-le ». Mesure faite : sur 917 taches backend-sans-frontend, les marqueurs
d'exemption LEGITIME se chevauchent massivement avec les marqueurs
d'accusation — 266 parlent de migration, 34 d'un signal, 33 de Celery, 30 d'un
webhook, 30 d'une commande de gestion, 19 de provisioning. Surtout, une part
irreductible de taches decrit un endpoint en prose SANS jamais dire s'il est
destine a un humain, a un integrateur, a une sonde ou a un job. Aucune regle
textuelle testee ici ne separe ces deux populations sans se tromper, et un
faux positif sur une file de 900 taches suffirait a faire desactiver la garde
entiere — donc les trois autres formes avec elle.

Elle est donc CONSTRUITE, MESUREE et AFFICHEE (``--stats``, ``--forme2``) mais
ne fait jamais echouer la CI. Ce qui la remplace comme garde DURE : la FORME 3,
qui attrape le meme defaut par son cote verifiable, et
``check_api_contract.py`` qui le mesure sur le CODE livre.

HONNETETE SUR LA FORME 4 (pourquoi elle n'est pas bloquante non plus)
----------------------------------------------------------------------
Le signal brut a ete presente comme fiable (« 18 doublons reels »). Il ne
l'est pas, et le chiffre a ete VERIFIE ici, cas par cas, en lisant les deux
composants de chaque paire :

    25 redefinitions brutes
    -14 homonymes retires mecaniquement (le redefinisseur s'appelle LUI AUSSI
        `<X>.jsx` : deux `DashboardPage.jsx` dans deux apps sont deux ecrans
        differents, pas un doublon)
    = 11 candidats, dont apres lecture du CODE :
        4 VRAIS DOUBLONS  — `RecordCard` (MessageBubble, 17 lignes, meme CSS
          et meme role, et le fichier partage est ORPHELIN) et `SimpleTable`
          recopie a l'identique dans logistique, magasin et installations ;
        7 LEGITIMES — `CalendarView` (142 lignes, ajoute le glisser-deposer de
          replanification et opere sur des chantiers, pas des leads),
          `KanbanView`/`ListView` d'interventions (colonnes et statuts
          propres, 45-51 lignes contre 1103 chez le « proprietaire »),
          `LigneRow` de compta (grille debit/credit contre ligne de bordereau
          AO : homonyme de sens different), `ListShell` d'astreintes et de
          suivi GPS (helper de 13 lignes spinner/erreur/vide, sans aucun
          rapport avec le moteur DataTable de 89 lignes qui porte ce nom), et
          `Table` de Rapports.jsx qui IMPORTE le partage et se contente de
          l'adapter.

    TAUX D'ERREUR DU SIGNAL MECANIQUE : 7 sur 11, soit 64 %.

Aucun seuil de taille ne rattrape cela : le plus petit VRAI doublon fait 17
lignes, le plus gros helper LEGITIME en fait 13, et un homonyme legitime en
fait 35 — la fenetre est etroite ET non monotone. Ce qui separe reellement les
deux populations est le CONTRAT DE PROPS et le sens metier, c'est-a-dire une
lecture du code, pas une regle statique.

Une garde qui se trompe deux fois sur trois serait desactivee en une semaine,
et emporterait les formes 1 et 3 avec elle. La FORME 4 est donc MESUREE et
AFFICHEE (``--stats``, ``--doublons``) sans jamais faire echouer la CI. Les 4
vrais doublons sont un travail de nettoyage a faire, pas une regle a armer.

HONNETETE SUR LA « TACHE QUI RECREE UN FICHIER EXISTANT »
----------------------------------------------------------
Demande a ete faite d'ajouter une cinquieme regle : « une tache qui nomme un
fichier DEJA EXISTANT avec un verbe de creation ». Mesure : 858 chemins de
code nommes par les taches ouvertes, 506 pointent un fichier existant, et le
detecteur naif « existant + verbe de creation » en accuse 263 — dont
l'ecrasante majorite a tort. ``module.config.jsx`` existe FORCEMENT puisque
c'est le fichier de MONTAGE qu'on vient modifier ; une tache qui « cree
l'onglet X dans EcranY.jsx » nomme legitimement un EcranY existant. Le verbe
de creation porte sur le LIVRABLE (un onglet, un champ, une action), pas sur
le fichier ; distinguer les deux demanderait de comprendre la phrase.

AUCUNE formulation testee ici n'atteint le zero faux positif. Cette regle
N'EST DONC PAS UNE GARDE CI. Ce qui la remplace : la FORME 4, qui mesure le
MEME gaspillage sur le code REELLEMENT ecrit (donc sans interpretation de
prose), et une consigne de RUN — « avant d'ecrire un fichier, verifier qu'il
n'existe pas ; s'il existe, la tache est un BRANCHEMENT ou une MODIFICATION,
jamais une creation ». Une consigne se lit ; une garde bruyante se desactive.

PRINCIPE ANTI-FAUX-POSITIF (assume, delibere)
---------------------------------------------
Une garde qui crie au loup finit desactivee, et le defaut reviendra. Donc :
  - un `.jsx` hors de ``features/`` et ``pages/`` n'est PAS un ecran. Un
    composant partage (``components/``, ``ui/``), un hook, un utilitaire, une
    traduction ne s'ouvrent pas depuis un menu et n'ont rien a router ;
  - un fichier DEJA SUR LE DISQUE n'est pas cree : la tache le MODIFIE. Ce
    signal STRUCTUREL prime sur tout signal textuel (piege reel : plusieurs
    taches de correction portent le gabarit « l'ecran est ATTEIGNABLE » par
    copier-coller alors que leur ecran existe et est deja branche) ;
  - l'existence est verifiee de facon TOLERANTE (meme nom de fichier ailleurs
    dans l'arborescence) : trois taches mesurees citent ``pages/x/Y.jsx``
    quand le fichier vit en ``features/x/pages/Y.jsx``. Un match strict les
    aurait accusees a tort ;
  - un chemin nomme par PLUSIEURS taches appartient a celle qui le marque
    ``(nouveau)``, sinon a la PREMIERE : les taches qui l'ETENDENT ensuite
    (chainage ``@after:``) ne sont pas accusees a la place de celle qui le cree ;
  - le mot « existant » dans le texte n'exempte JAMAIS : plusieurs taches
    parlent d'un ecran existant AUTRE que celui qu'elles creent ;
  - un ecran PUBLIC a jeton (``AllowAny``, partage par lien/QR) est hors du
    shell applicatif PAR CONCEPTION : lui exiger une entree de nav serait
    absurde ;
  - une tache qui modifie une GARDE (``scripts/check_*.py``) cite des ecrans a
    titre de PREUVE, pas de livrable ;
  - une tache de SUPPRESSION, RENOMMAGE ou DEPLACEMENT ne cree rien ;
  - les fichiers de test (``*.test.*``, ``*.spec.*``) ne sont jamais des ecrans ;
  - une tache sans identifiant lisible ou sans ligne ``Files:`` ne produit
    AUCUNE alerte : on sous-detecte, on n'invente pas ;
  - une tache deja cochee ``[x]`` n'est jamais examinee : on ne reecrit pas
    l'histoire.

CE QUI N'EST PAS UN DOUBLON (forme 4)
--------------------------------------
Deux filtres mecaniques sont appliques avant meme d'AFFICHER un doublon :
  - HOMONYMIE : si le fichier qui redefinit s'appelle LUI AUSSI ``<X>.jsx``,
    il n'y a pas de « redefinition locale », il y a deux fichiers homonymes
    dont aucun n'est « le » proprietaire — ``features/ao/DashboardPage.jsx``
    et ``features/contrats/DashboardPage.jsx`` sont deux tableaux de bord
    DIFFERENTS (14 des 25 cas bruts) ;
  - ADAPTATION : si le fichier qui redefinit IMPORTE le fichier proprietaire,
    il l'adapte, il ne le duplique pas — ``Rapports.jsx`` importe
    ``reporting/Table`` sous un alias et lui delegue tout le rendu.
Aucun seuil de taille n'est applique : mesure faite, la plus petite
redefinition REELLE (``RecordCard``, 17 lignes) depasse a peine le plus gros
helper LEGITIME (``ListShell``, 13 lignes), et un homonyme legitime
(``LigneRow``) en fait 35 — un seuil trancherait a l'envers.

BASE DE REFERENCE — ELLE NE PEUT QUE RETRECIR
---------------------------------------------
La dette du 03/08/2026 est GELEE dans ``scripts/taches_cablage_allow.txt``.
Cette garde empeche la RECIDIVE ; elle ne reecrit pas les taches existantes.
``--write-baseline`` REFUSE d'ajouter une ligne : il ne sait qu'en retirer
(celles qui sont corrigees). Ajouter une dette exige
``--autoriser-croissance``, drapeau reserve au fondateur, visible en revue.

La signature est ``<forme>|<IDENTIFIANT DE TACHE>`` pour les formes de plan
(``ecran-sans-cablage|PACT42``) et ``composant-redefini|<Nom>|<fichier>`` pour
la forme 4 — jamais ``fichier:ligne`` : une tache qui se decale dans son
fichier, ou un composant qui descend de vingt lignes, ne doit pas invalider la
base.

Usage :
    python scripts/check_taches_cablage.py                 # garde CI
    python scripts/check_taches_cablage.py --stats         # inventaire chiffre
    python scripts/check_taches_cablage.py --forme2        # l'avertissement seul
    python scripts/check_taches_cablage.py --write-baseline
"""
from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from pathlib import Path

from check_api_contract import scan_js

ROOT = Path(__file__).resolve().parent.parent
BASELINE_PATH = ROOT / "scripts" / "taches_cablage_allow.txt"
FRONT_SRC = ROOT / "frontend" / "src"

# Fichiers de plan examines. Les six premiers sont nommes explicitement ; les
# files de domaine sont resolues par glob (elles sont nees d'un split et
# d'autres peuvent apparaitre : une nouvelle file ne doit pas echapper a la
# garde par simple oubli de l'inscrire ici).
PLAN_FILES_EXPLICITES = (
    "docs/PLAN.md",
    "docs/PLAN2.md",
    "docs/new_tasks_plan.md",
    "docs/ERROR_PLAN.md",
    "docs/WEB_PLAN.md",
    "docs/FRONTEND_GAP_PLAN.md",
)
PLAN_GLOB = ("docs/plans", "PLAN_*.md")

# Les quatre formes gardees. La FORME 2 est deliberement non bloquante.
FORME_ECRAN = "ecran-sans-cablage"
FORME_BACKEND = "backend-sans-consommateur"
FORME_CONTRAT = "contrat-absent"
FORME_DOUBLON = "composant-redefini"
# La FORME 2 et la FORME 4 sont MESUREES mais jamais bloquantes : leur taux de
# faux positifs a ete mesure, pas suppose (voir l'en-tete).
FORMES_BLOQUANTES = (FORME_ECRAN, FORME_CONTRAT)
FORMES_AVERTISSEMENT = (FORME_BACKEND, FORME_DOUBLON)

# ---------------------------------------------------------------------------
# Ce qu'est un ECRAN (et surtout ce qui n'en est pas)
# ---------------------------------------------------------------------------
# Un ecran est ce qu'un utilisateur OUVRE. Dans ce depot, cela vit sous
# `frontend/src/features/**` (routes par `features/<app>/module.config.jsx`) et
# `frontend/src/pages/**` (routes par `router/index.jsx` ou par un
# module.config qui les importe). Tout le reste de `frontend/src` — components,
# ui, hooks, lib, utils, store, providers, api, i18n, design, styles — est de la
# matiere premiere : cela ne se route pas, cela n'a pas de menu, et l'exiger
# serait le faux positif qui ferait desactiver la garde.
DOSSIERS_ECRANS = ("features", "pages")

# Fichiers de MONTAGE : ils relient un ecran au menu. Nommes dans `Files:`, ils
# satisfont l'exigence (a). Ce ne sont jamais des ecrans eux-memes.
FICHIERS_MONTAGE = re.compile(
    r"(?i)(?:^|/)(?:module\.config\.jsx"
    r"|router/(?:index|moduleRoutes)\.jsx"
    r"|moduleRoutes\.jsx"
    r"|App\.jsx"
    r"|Sidebar\.jsx"
    r"|routes\.meta\.js)$")

TEST_MARKERS = (".test.", ".spec.")
TEST_DIRS = ("__tests__", "__mocks__")

# ---------------------------------------------------------------------------
# Lecture des taches
# ---------------------------------------------------------------------------
# La case peut contenir des crochets IMBRIQUES — vu sur le depot :
# `- [BLOCKED: ... se marque [GATED si dev-dep a ajouter]] VX198 — ...`.
# Un `\[([^\]]*)\]` naif s'arreterait au premier `]` et lirait « ] VX198 »
# comme identifiant. On consomme donc les `]` orphelins qui restent en tete.
_TACHE = re.compile(r"^- \[(?P<etat>.*?)\]\s*(?P<reste>.*)$")
_CROCHETS_RESIDUELS = re.compile(r"^\]+\s*")
# Identifiants reels du depot : `PACT42`, `NTSRV4`, `VX198`, `FE-ZSTK6/12`.
_IDENTIFIANT = re.compile(r"^(?P<id>[A-Z][A-Za-z0-9]*[0-9]+|FE-[A-Za-z0-9/_-]+)\b")

# `Files:`, `File:`, `Files :`, `fichier :` — toutes les formes vues au grep.
_CLAUSE_FILES = re.compile(r"(?i)\b(?:files?|fichiers?)\s*:")

# Un chemin frontend cite dans la ligne `Files:`. Les delimiteurs exclus sont
# ceux qui entourent reellement les chemins ici : backticks, guillemets,
# virgules, parentheses (`... .jsx (nouveau)`).
_CHEMIN_FRONT = re.compile(r"frontend/src/[^\s`'\"),;]*\.(?:jsx|tsx)")
# Tout fichier frontend, y compris les clients d'API `.js` : c'est ce qui
# distingue une tache « backend seul » (FORME 2) d'une tache a deux moities
# (FORME 3).
_FICHIER_FRONT = re.compile(r"frontend/src/[^\s`'\"),;]*\.(?:jsx|tsx|js|ts)")

# Fichiers backend qui portent le MODELE ou la LOGIQUE.
_FICHIER_BACKEND = re.compile(
    r"(?:^|[\s`'\"(,/])(?:apps|backend)/[^\s`'\"),;]*/"
    r"(?:models|views|urls|serializers|services|selectors)\.py"
    r"|(?:^|[\s`'\"(,])(?:models|views|urls|serializers|services|selectors)\.py")
# Fichiers backend qui EXPOSENT du HTTP. Seuls ceux-la peuvent produire une
# ressource « sans consommateur » : un `models.py` seul n'expose rien.
_FICHIER_EXPOSANT = re.compile(
    r"(?:^|[\s`'\"(,/])(?:apps|backend)/[^\s`'\"),;]*/(?:views|urls)\.py"
    r"|(?:^|[\s`'\"(,])(?:views|urls)\.py")
# Une tache qui modifie une GARDE cite des ecrans a titre de PREUVE.
_FICHIER_GARDE = re.compile(r"scripts/(?:check_|\w+_allow\.txt)")

# Marqueur de CREATION accole au chemin : `MonEcran.jsx (nouveau)`,
# `(nouveau onglet)`, `(a creer)`, `(new)`.
_MARQUEUR_NOUVEAU = re.compile(r"(?i)^\s*\((?:nouveau|nouvelle|new|a\s+creer|to\s+create)\b")
# `X.jsx (nouveau ou section de Y.jsx)` : la tache offre explicitement de
# n'ecrire aucun nouvel ecran. Accuser la voie « nouveau » serait presumer.
# `X.jsx (onglet RMA)` : le livrable est un ONGLET de X, pas un ecran route —
# il se monte dans sa page, qui est justement nommee dans `Files:`.
_ALTERNATIVE_SECTION = re.compile(
    r"(?i)\((?:[^)]*\b(?:ou|or)\s+(?:section|onglet|bloc|carte|encart)\b[^)]*)\)"
    r"|\((?:nouvel?\s+)?onglet\b[^)]*\)")
# Une annotation peut etre posee DEDANS ou DEHORS les accents graves :
# `` `X.jsx (nouveau)` `` mais aussi `` `X.jsx` (nouveau ou section de Y) ``.
# Sans retirer les accents graves de tete, la seconde forme etait invisible —
# faux positif mesure sur NTAGR27.
_AVANT_ANNOTATION = re.compile(r"^[\s`'\"]+")

# Verbes qui excluent la creation : la tache retire ou deplace quelque chose.
_TACHE_DESTRUCTIVE = re.compile(
    r"(?i)\b(?:supprim|suppression|retir|efface|renomm|renommage|deplac"
    r"|deplacement|remplace\s+par|migre\s+vers|fusionn)")


def normaliser(texte: str) -> str:
    """Minuscules sans accents — les clauses sont ecrites en francais accentue,
    et une garde qui dependrait d'un accent bien place serait fragile."""
    decompose = unicodedata.normalize("NFKD", texte)
    return "".join(c for c in decompose if not unicodedata.combining(c)).lower()


# --- FORME 1 : clause d'atteignabilite -------------------------------------
# Cherchee sur le texte NORMALISE (sans accents). La premiere alternative est
# la clause canonique deja employee 120 fois dans docs/PLAN.md : « **Et l'ecran
# est ATTEIGNABLE** : route declaree + entree de nav (ou onglet monte dans son
# ecran parent), et `check_ecrans_atteignables.py` ne signale aucune nouvelle
# dette — un ecran livre mais injoignable ne compte PAS comme fait ».
_CLAUSE_ATTEIGNABILITE = re.compile(
    r"atteignabl"
    r"|injoignable"
    r"|check_ecrans_atteignables"
    r"|route\s+declaree"
    r"|routes?\s+declaree?s?"
    r"|declare\w*\s+(?:la\s+|une\s+)?route"
    r"|entree\s+de\s+nav"
    r"|entree\s+de\s+menu"
    r"|onglet\s+monte"
    r"|monte\w*\s+(?:dans|en)\s+(?:un\s+)?onglet"
    r"|inscrit\w*\s+au\s+menu"
    r"|ajout\w*\s+au\s+menu"
    r"|navigation\s+depuis\s+le\s+menu"
    r"|depuis\s+le\s+menu")

# Le livrable est un COMPOSANT, pas un ecran : un panneau monte dans cinq
# fiches existantes, une modale ouverte par un bouton, une banniere du shell.
# N'exempte QUE si la tache ne parle jamais d'ecran, de page ni de route —
# sinon « l'ecran X avec son panneau Y » s'exempterait tout seul.
_LIVRABLE_COMPOSANT = re.compile(
    r"\bcomposant|\bpanneau|\bmodale?\b|\bbandeau|\bbadge|\bwidget"
    r"|\btiroir|\bdrawer|\bpastille|\bencart|\bbouton\b")
_PARLE_D_ECRAN = re.compile(r"\becran|\bpage\b|\broute\b|\bnav\b|\bmenu\b")

# Ecran PUBLIC a jeton : hors du shell applicatif par conception.
_ECRAN_PUBLIC = re.compile(
    r"allowany"
    r"|pattern\s+(?:sharelink|partageged)"
    r"|lien\s+de\s+partage"
    r"|partage\s+par\s+(?:lien|qr)"
    r"|token\s+public"
    r"|public\s+token"
    r"|sans\s+authentification")

# --- FORME 3 : clause de contrat partage ------------------------------------
# Ce qui compte est un ARTEFACT COMMUN aux deux moities, pas une promesse.
_CLAUSE_CONTRAT = re.compile(
    r"api-contracts"
    r"|check_api_shapes"
    r"|check_api_contract"
    r"|check_openapi_schema"
    r"|contrat\s+(?:partage|commun|unique|verifiable|d'api|api)"
    r"|(?:meme|la\s+meme|une\s+seule)\s+fixture"
    r"|fixture\s+(?:partagee|commune|committee|unique)"
    r"|exemple\s+de\s+reponse\s+(?:committe|partage|commun)"
    r"|le\s+test\s+frontend\s+importe"
    r"|importee?\s+par\s+le\s+test\s+frontend"
    r"|jamais\s+un\s+mock\s+(?:invente|ecrit)")

# --- FORME 2 : marqueurs (mesure seulement, jamais bloquants) ---------------
_SURFACE_HTTP = re.compile(
    r"endpoint"
    r"|router\.register"
    r"|@action"
    r"|viewset"
    r"|\bpost\s+/|\bget\s+/|\bpatch\s+/|\bdelete\s+/"
    r"|nouvelle\s+route"
    r"|route\s+`?/")
_SANS_ECRAN_LEGITIME = re.compile(
    r"webhook|celery|cron|\bbeat\b|planifiee?|periodique"
    r"|manage\.py|commande\s+de\s+gestion|management\s+command"
    r"|sonde|healthcheck|health\s+check|liveness|readiness"
    r"|provisionn?|\.ics|icalendar"
    r"|migration|refactor|signal|receiver"
    r"|portail\s+public|token\s+public|allowany|sans\s+authentification"
    r"|integrateur|api\s+publique|public\s+api|machine\s+a\s+machine")
_CONSOMMATEUR = re.compile(
    r"ecran|\bpage\b|\bui\b|frontend|affich|consomm|visible\s+dans"
    r"|sans\s+ecran\s+par\s+design")


class Tache:
    """Une tache de plan lue depuis une ligne de fichier."""

    def __init__(self, fichier: str, ligne: int, etat: str, identifiant: str, texte: str):
        self.fichier = fichier
        self.ligne = ligne
        self.etat = etat
        self.identifiant = identifiant
        self.texte = texte
        self.normalise = normaliser(texte)
        self.clause_files = self._clause_files()
        self.chemins = self._chemins()

    # -- lecture de la ligne ------------------------------------------------
    def _clause_files(self) -> str:
        """Tout ce qui suit le DERNIER `Files:` de la ligne, ou '' si absent."""
        derniere = None
        for match in _CLAUSE_FILES.finditer(self.texte):
            derniere = match
        return self.texte[derniere.end():] if derniere else ""

    def _chemins(self) -> list:
        """[(chemin, marque_nouveau, alternative)] des fichiers frontend."""
        trouves = []
        for match in _CHEMIN_FRONT.finditer(self.clause_files):
            suite = _AVANT_ANNOTATION.sub(
                "", self.clause_files[match.end():match.end() + 70])
            trouves.append((match.group(0),
                            bool(_MARQUEUR_NOUVEAU.match(suite)),
                            bool(_ALTERNATIVE_SECTION.match(suite))))
        return trouves

    # -- qualification ------------------------------------------------------
    @property
    def close(self) -> bool:
        """Une tache cochee n'est JAMAIS examinee : on ne reecrit pas l'histoire."""
        return self.etat.strip().lower().startswith("x")

    @property
    def destructive(self) -> bool:
        return bool(_TACHE_DESTRUCTIVE.search(self.normalise))

    @property
    def touche_une_garde(self) -> bool:
        return bool(_FICHIER_GARDE.search(self.clause_files))

    @property
    def ecran_public(self) -> bool:
        return bool(_ECRAN_PUBLIC.search(self.normalise))

    @property
    def livre_un_composant(self) -> bool:
        """Le livrable est un composant monte ailleurs, pas un ecran routable."""
        return bool(_LIVRABLE_COMPOSANT.search(self.normalise)) \
            and not _PARLE_D_ECRAN.search(self.normalise)

    @property
    def a_du_frontend(self) -> bool:
        return bool(_FICHIER_FRONT.search(self.clause_files))

    @property
    def a_du_backend(self) -> bool:
        return bool(_FICHIER_BACKEND.search(self.clause_files))

    @property
    def expose_du_http(self) -> bool:
        return bool(_FICHIER_EXPOSANT.search(self.clause_files))

    def exige_atteignabilite(self) -> bool:
        return bool(_CLAUSE_ATTEIGNABILITE.search(self.normalise))

    def exige_un_contrat(self) -> bool:
        return bool(_CLAUSE_CONTRAT.search(self.normalise))

    def exige_un_consommateur(self) -> bool:
        return bool(_CONSOMMATEUR.search(self.normalise))

    def fichier_de_montage(self) -> str | None:
        """Le fichier de `Files:` qui pourra relier l'ecran au menu, ou None.

        Deux formes acceptees :
          1. un `module.config.jsx` / `router/index.jsx` / `App.jsx` ;
          2. un ecran DEJA EXISTANT — c'est le « ecran parent qui le monte » de
             la regle : un onglet neuf se branche dans une fiche qui existe
             deja, et cette fiche est bien dans `Files:`.
        """
        for chemin, _, _ in self.chemins:
            if FICHIERS_MONTAGE.search(chemin):
                return chemin
        for chemin, nouveau, _ in self.chemins:
            if not nouveau and est_ecran(chemin) and existe_deja(chemin):
                return chemin
        return None


def est_test(chemin: str) -> bool:
    nom = chemin.rsplit("/", 1)[-1]
    if any(marqueur in nom for marqueur in TEST_MARKERS):
        return True
    return any(f"/{dossier}/" in chemin for dossier in TEST_DIRS)


def est_ecran(chemin: str) -> bool:
    """Un `.jsx`/`.tsx` qu'un utilisateur OUVRE (cf. DOSSIERS_ECRANS)."""
    if est_test(chemin) or FICHIERS_MONTAGE.search(chemin):
        return False
    parties = chemin.split("/")
    return len(parties) > 3 and parties[2] in DOSSIERS_ECRANS


_INDEX_NOMS: dict[str, bool] | None = None


def _index_noms() -> dict:
    """Noms de fichiers reellement presents sous frontend/src (memoise).

    Sert au match TOLERANT : trois taches mesurees citent `pages/<app>/X.jsx`
    quand le fichier vit en `features/<app>/pages/X.jsx`, et une autre cite
    `ProjetDetail.jsx` pour `ProjetDetailPage.jsx`. Un match STRICT du chemin
    les aurait declarees « creations » et accusees a tort.
    """
    global _INDEX_NOMS
    if _INDEX_NOMS is None:
        _INDEX_NOMS = {}
        if FRONT_SRC.is_dir():
            for path in FRONT_SRC.rglob("*.[jt]sx"):
                _INDEX_NOMS[path.name.lower()] = True
    return _INDEX_NOMS


def existe_deja(chemin: str) -> bool:
    """Le fichier existe-t-il — au chemin cite, ou sous le meme nom ailleurs ?"""
    if (ROOT / chemin).is_file():
        return True
    nom = chemin.rsplit("/", 1)[-1].lower()
    index = _index_noms()
    if nom in index:
        return True
    # `ProjetDetail.jsx` cite pour `ProjetDetailPage.jsx` (suffixe Page).
    tige, _, extension = nom.rpartition(".")
    return f"{tige}page.{extension}" in index


def app_de(chemin: str) -> str:
    """`features/<app>/…` ou `pages/<zone>/…` -> le nom d'app a suggerer."""
    parties = chemin.split("/")
    return parties[3] if len(parties) > 4 else (parties[2] if len(parties) > 2 else "<app>")


# ===========================================================================
# FORME 4 — composants redefinis
# ===========================================================================

# Declaration d'un composant React : `function X(`, `const X = (`,
# `const X = memo((`, `const X = forwardRef((`. Une fonction fleche a
# parametre nu (`const X = props =>`) n'est pas lue : on sous-detecte.
_DECLARATION_COMPOSANT = re.compile(
    r"^[ \t]*(?:export\s+(?:default\s+)?)?function\s+([A-Z][A-Za-z0-9_]*)\s*\("
    r"|^[ \t]*(?:export\s+)?(?:const|let|var)\s+([A-Z][A-Za-z0-9_]*)\s*=\s*"
    r"(?:React\.)?(?:memo\s*\(\s*)?(?:forwardRef\s*\(\s*)?\(",
    re.M)


def _fichiers_jsx() -> list:
    if not FRONT_SRC.is_dir():
        return []
    return [p for p in sorted(FRONT_SRC.rglob("*.jsx"))
            if not est_test(p.relative_to(ROOT).as_posix())]


_SPEC_IMPORT = re.compile(r"""\bfrom\s*(['"])([^'"\n]+)\1"""
                          r"""|\bimport\s*\(\s*(['"])([^'"\n]+)\3""")


def _lire_jsx(path: Path) -> str:
    try:
        source = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    code, _, _ = scan_js(source)      # commentaires retires : un composant
    return code                       # cite en commentaire n'est pas declare


def _composants_declares(code: str) -> set:
    return {
        (match.group(1) or match.group(2))
        for match in _DECLARATION_COMPOSANT.finditer(code)
    }


def _importe(code: str, importateur: Path, cible: Path) -> bool:
    """`importateur` importe-t-il le fichier `cible` ? (adaptation, pas doublon)"""
    for match in _SPEC_IMPORT.finditer(code):
        spec = match.group(2) or match.group(4)
        if not spec or not spec.startswith("."):
            continue
        base = importateur.parent / spec
        for candidat in (base, *(Path(str(base) + e) for e in (".jsx", ".js")),
                         base / "index.jsx", base / "index.js"):
            try:
                if candidat.resolve() == cible.resolve():
                    return True
            except OSError:
                continue
    return False


def doublons():
    """[(composant, fichier redefinisseur, [fichiers proprietaires])].

    Un PROPRIETAIRE est un fichier `<X>.jsx` qui declare `X`. Un
    REDEFINISSEUR est un fichier d'un AUTRE nom qui declare `X` aussi. Cette
    condition de nom differe est la seule regle anti-homonyme, et elle suffit :
    `features/ao/DashboardPage.jsx` et `features/contrats/DashboardPage.jsx`
    sont deux ecrans distincts, pas un doublon (14 des 25 cas bruts).
    """
    declarations = {}
    sources_par_fichier = {}
    proprietaires: dict[str, list] = {}
    for path in _fichiers_jsx():
        code = _lire_jsx(path)
        sources_par_fichier[path] = code
        noms = _composants_declares(code)
        declarations[path] = noms
        if path.stem in noms:
            proprietaires.setdefault(path.stem, []).append(path)

    trouves = []
    for path, noms in declarations.items():
        for nom in sorted(noms):
            sources = proprietaires.get(nom)
            if not sources or path.stem == nom:
                continue
            # Adaptation : il IMPORTE le partage et le decore. Pas un doublon.
            if any(_importe(sources_par_fichier[path], path, p) for p in sources):
                continue
            trouves.append((
                nom,
                path.relative_to(ROOT).as_posix(),
                sorted(p.relative_to(ROOT).as_posix() for p in sources)))
    return sorted(trouves), len(declarations), len(proprietaires)


# ===========================================================================
# Analyse
# ===========================================================================

def fichiers_de_plan() -> list:
    trouves = []
    for rel in PLAN_FILES_EXPLICITES:
        if (ROOT / rel).is_file():
            trouves.append(rel)
    dossier = ROOT / PLAN_GLOB[0]
    if dossier.is_dir():
        for path in sorted(dossier.glob(PLAN_GLOB[1])):
            trouves.append(path.relative_to(ROOT).as_posix())
    return trouves


def lire_taches(fichiers=None) -> list:
    taches = []
    for rel in (fichiers if fichiers is not None else fichiers_de_plan()):
        path = ROOT / rel
        try:
            contenu = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for numero, ligne in enumerate(contenu.splitlines(), 1):
            match = _TACHE.match(ligne)
            if not match:
                continue
            reste = _CROCHETS_RESIDUELS.sub("", match.group("reste"))
            identifiant = _IDENTIFIANT.match(reste)
            if not identifiant:
                # Sans identifiant lisible, aucune signature stable n'est
                # possible : on se tait (jamais d'accusation non tracable).
                continue
            taches.append(Tache(rel, numero, match.group("etat"),
                                identifiant.group("id"), reste))
    return taches


class Constat:
    """Un manquement, pour UNE forme."""

    def __init__(self, forme: str, cible: str, tache=None, detail=None, manques=()):
        self.forme = forme
        self.cible = cible            # identifiant de tache, ou <Nom>|<fichier>
        self.tache = tache
        self.detail = detail or []
        self.manques = manques

    @property
    def signature(self) -> str:
        return f"{self.forme}|{self.cible}"

    @property
    def tri(self):
        if self.tache is not None:
            return (self.forme, self.tache.fichier, self.tache.ligne)
        return (self.forme, self.cible, 0)


def _ecrans_crees(tache: Tache, proprietaires: dict) -> list:
    crees = []
    for chemin, nouveau, alternative in tache.chemins:
        if not est_ecran(chemin):
            continue
        if existe_deja(chemin):
            continue                          # existe deja -> la tache MODIFIE
        if alternative:
            continue                          # « nouveau OU section de X »
        proprio = proprietaires.get(chemin)
        if proprio and not nouveau and tache.identifiant not in proprio:
            continue                          # une AUTRE tache le cree
        crees.append(chemin)
    return crees


def analyse(fichiers=None, avec_doublons=True):
    taches = [t for t in lire_taches(fichiers) if not t.close]

    # Qui possede quel chemin : la tache qui le marque `(nouveau)`, sinon la
    # PREMIERE qui le nomme. Les taches qui l'ETENDENT ensuite (chainage
    # `@after:`) ne sont pas accusees a la place de celle qui le cree.
    proprietaires: dict[str, set] = {}
    premiers: dict[str, str] = {}
    for tache in taches:
        for chemin, nouveau, _ in tache.chemins:
            if not est_ecran(chemin):
                continue
            premiers.setdefault(chemin, tache.identifiant)
            if nouveau:
                proprietaires.setdefault(chemin, set()).add(tache.identifiant)
    for chemin, identifiant in premiers.items():
        proprietaires.setdefault(chemin, {identifiant})

    constats = []
    stats = {
        "taches": len(taches),
        "f1_candidates": 0, "f1_creations": 0, "f1_conformes": 0,
        "f1_sans_montage": 0, "f1_sans_clause": 0,
        "f2_candidates": 0, "f2_exposantes": 0, "f2_fautives": 0,
        "f3_candidates": 0, "f3_conformes": 0, "f3_fautives": 0,
        "f4_fichiers": 0, "f4_proprietaires": 0, "f4_doublons": 0,
    }

    for tache in taches:
        # ---------------- FORME 1 : ecran sans cablage ----------------
        ecrans = [c for c, _, _ in tache.chemins if est_ecran(c)]
        if ecrans:
            stats["f1_candidates"] += 1
            if not (tache.destructive or tache.touche_une_garde
                    or tache.ecran_public or tache.livre_un_composant):
                crees = _ecrans_crees(tache, proprietaires)
                if crees:
                    stats["f1_creations"] += 1
                    montage = tache.fichier_de_montage()
                    clause = tache.exige_atteignabilite()
                    if montage and clause:
                        stats["f1_conformes"] += 1
                    else:
                        manques = []
                        if not montage:
                            manques.append("a")
                            stats["f1_sans_montage"] += 1
                        if not clause:
                            manques.append("b")
                            stats["f1_sans_clause"] += 1
                        constats.append(Constat(FORME_ECRAN, tache.identifiant,
                                                tache, sorted(crees), tuple(manques)))

        # ------- FORME 3 : deux moities livrees sans contrat commun -------
        # Testee AVANT la forme 2 : une tache a deux moities n'est jamais
        # « backend sans consommateur », elle a deja son consommateur.
        if tache.a_du_backend and tache.a_du_frontend:
            stats["f3_candidates"] += 1
            if not (tache.destructive or tache.touche_une_garde):
                if tache.exige_un_contrat():
                    stats["f3_conformes"] += 1
                else:
                    stats["f3_fautives"] += 1
                    constats.append(Constat(FORME_CONTRAT, tache.identifiant, tache))

        # ------ FORME 2 : backend sans consommateur (NON BLOQUANTE) ------
        elif tache.a_du_backend and not tache.a_du_frontend:
            stats["f2_candidates"] += 1
            if tache.expose_du_http and _SURFACE_HTTP.search(tache.normalise):
                stats["f2_exposantes"] += 1
                if not _SANS_ECRAN_LEGITIME.search(tache.normalise) \
                        and not tache.exige_un_consommateur():
                    stats["f2_fautives"] += 1
                    constats.append(Constat(FORME_BACKEND, tache.identifiant, tache))

    # ---------------- FORME 4 : composants redefinis ----------------
    if avec_doublons:
        trouves, nb_fichiers, nb_proprietaires = doublons()
        stats["f4_fichiers"] = nb_fichiers
        stats["f4_proprietaires"] = nb_proprietaires
        stats["f4_doublons"] = len(trouves)
        for nom, fichier, sources in trouves:
            constats.append(Constat(FORME_DOUBLON, f"{nom}|{fichier}",
                                    detail=sources))

    return constats, stats


# ===========================================================================
# Base de reference + CLI
# ===========================================================================

ENTETE_BASE = """\
# Base de reference de check_taches_cablage.py — DETTE HISTORIQUE, RIEN D'AUTRE.
#
# Chaque ligne est `<forme>|<cible>` : du travail mort deja commande ou deja
# ecrit le 03/08/2026.
#   ecran-sans-cablage  : une tache OUVERTE cree un ecran sans nommer son
#                         fichier de montage ni exiger route / nav / onglet.
#   contrat-absent      : une tache OUVERTE nomme les DEUX moities (backend +
#                         frontend) sans exiger de contrat partage verifiable.
#   composant-redefini  : un composant possede son fichier `<X>.jsx` et un
#                         AUTRE fichier le redefinit au lieu de l'importer.
# (La forme `backend-sans-consommateur` est mesuree mais NON bloquante — voir
#  l'en-tete du script : elle n'atteint pas le zero faux positif.)
#
# Un agent qui execute une telle tache A LA LETTRE produit mecaniquement du
# travail invisible : c'est ainsi que 61 des 68 ecrans du module « Appels
# d'offres » sont devenus inatteignables et que 206 ressources backend sont
# restees sans consommateur, le 03/08/2026.
#
# Cette liste est le gel de la dette mesuree ce jour-la. La garde n'echoue que
# sur une cible ABSENTE de cette liste : elle empeche la RECIDIVE, elle ne
# reecrit pas ce qui est deja ecrit.
#
# REGLE ABSOLUE : CETTE LISTE NE PEUT QUE RETRECIR.
#   - corriger une tache (ou importer le composant partage au lieu de le
#     redefinir) puis
#     `python scripts/check_taches_cablage.py --write-baseline` retire sa ligne ;
#   - `--write-baseline` REFUSE d'ajouter une ligne. Ajouter une dette exige
#     `--autoriser-croissance`, drapeau reserve au fondateur, visible en revue.
#
# La signature est l'IDENTIFIANT DE TACHE (ou <Composant>|<fichier>), jamais
# `fichier:ligne` : une tache qui se decale, ou un composant qui descend de
# vingt lignes, ne doit pas invalider la base.
"""


def charger_base(path: Path | None = None) -> set:
    # `path or BASELINE_PATH` resolu A L'APPEL, jamais en valeur par defaut :
    # une valeur par defaut est figee a la definition du module, si bien qu'un
    # test qui reassigne BASELINE_PATH ecrirait quand meme dans la VRAIE base
    # (piege documente dans check_ecrans_atteignables.py — il a effectivement
    # ecrase la base de reference du depot).
    path = path or BASELINE_PATH
    if not path.is_file():
        return set()
    return {
        ligne.strip()
        for ligne in path.read_text(encoding="utf-8").splitlines()
        if ligne.strip() and not ligne.strip().startswith("#")
    }


def ecrire_base(signatures: set, path: Path | None = None):
    path = path or BASELINE_PATH
    path.write_text(ENTETE_BASE + "\n".join(sorted(signatures)) + "\n",
                    encoding="utf-8", newline="\n")


def _suggestion_montage(chemins: list) -> str:
    """Le fichier de montage a nommer, deduit du chemin de l'ecran cree."""
    for chemin in chemins:
        app = app_de(chemin)
        candidat = f"frontend/src/features/{app}/module.config.jsx"
        if (ROOT / candidat).is_file():
            return candidat
        if chemin.split("/")[2] == "features":
            return candidat
    return "frontend/src/features/<app>/module.config.jsx"


def _explique(constat: Constat):
    """Les lignes « quoi ajouter exactement » d'un constat."""
    lignes = []
    if constat.forme == FORME_ECRAN:
        for chemin in constat.detail:
            lignes.append(f"      cree  {chemin}")
        if "a" in constat.manques:
            lignes.append(
                f"      MANQUE (a) le fichier de montage : ajoutez "
                f"`{_suggestion_montage(constat.detail)}` a Files:")
        if "b" in constat.manques:
            lignes.append(
                "      MANQUE (b) la clause d'atteignabilite : ajoutez au Done= "
                "« Et l'ecran est ATTEIGNABLE : route declaree + entree de nav "
                "(ou onglet monte dans son ecran parent) »")
    elif constat.forme == FORME_CONTRAT:
        lignes.append(
            "      nomme les DEUX moities (backend + frontend) sans exiger de "
            "contrat commun")
        lignes.append(
            "      MANQUE le contrat partage : ajoutez au Done= « le test "
            "backend AFFIRME l'exemple de reponse committe dans "
            "`docs/api-contracts.md` et le test frontend l'IMPORTE (jamais un "
            "mock ecrit a la main) »")
    elif constat.forme == FORME_DOUBLON:
        nom, _, fichier = constat.cible.partition("|")
        lignes.append(f"      redefinit `{nom}` alors que le composant a deja "
                      f"son fichier : {', '.join(constat.detail)}")
        lignes.append(f"      A FAIRE : importez `{nom}` depuis ce fichier et "
                      f"supprimez la copie locale — si le partage ne convient "
                      f"pas, renommez la copie locale pour dire en quoi elle "
                      f"differe.")
    else:
        lignes.append(
            "      cree une surface HTTP sans nommer de consommateur : ajoutez "
            "l'ecran (ou la tache d'ecran) qui l'appelle, ou la mention "
            "« sans ecran par design : <raison> »")
    return lignes


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    parser = argparse.ArgumentParser(
        description="Garde de cablage : ne pas commander, ni ecrire, du "
                    "travail mort.")
    parser.add_argument("--stats", action="store_true",
                        help="inventaire chiffre des quatre formes")
    parser.add_argument("--forme2", action="store_true",
                        help="liste l'avertissement backend-sans-consommateur "
                             "(jamais bloquant)")
    parser.add_argument("--doublons", action="store_true",
                        help="liste l'avertissement composant-redefini "
                             "(jamais bloquant)")
    parser.add_argument("--write-baseline", action="store_true",
                        help="retire de la base les cibles desormais corrigees")
    parser.add_argument("--autoriser-croissance", action="store_true",
                        help="FONDATEUR UNIQUEMENT : autorise l'ajout de dettes")
    args = parser.parse_args(argv)

    constats, stats = analyse()
    bloquants = [c for c in constats if c.forme in FORMES_BLOQUANTES]
    avert_backend = [c for c in constats if c.forme == FORME_BACKEND]
    avert_doublon = [c for c in constats if c.forme == FORME_DOUBLON]

    if args.stats:
        print(f"Taches de plan ouvertes lues : {stats['taches']}\n")
        print("FORME 1 — ecran sans cablage (BLOQUANTE)")
        print(f"  `Files:` nomme un ecran               : {stats['f1_candidates']}")
        print(f"  la tache CREE cet ecran               : {stats['f1_creations']}")
        print(f"     conformes (montage + clause)       : {stats['f1_conformes']}")
        print(f"     sans fichier de montage            : {stats['f1_sans_montage']}")
        print(f"     sans clause d'atteignabilite       : {stats['f1_sans_clause']}")
        print("\nFORME 2 — backend sans consommateur (AVERTISSEMENT SEUL)")
        print(f"  backend nomme, aucun frontend         : {stats['f2_candidates']}")
        print(f"     dont exposant une surface HTTP     : {stats['f2_exposantes']}")
        print(f"     sans consommateur ni justification : {stats['f2_fautives']}")
        print("\nFORME 3 — deux moities sans contrat commun (BLOQUANTE)")
        print(f"  backend ET frontend nommes            : {stats['f3_candidates']}")
        print(f"     exigeant un contrat partage        : {stats['f3_conformes']}")
        print(f"     n'exigeant aucun contrat           : {stats['f3_fautives']}")
        print("\nFORME 4 — composant redefini (AVERTISSEMENT SEUL)")
        print(f"  fichiers .jsx non-test analyses       : {stats['f4_fichiers']}")
        print(f"  composants a fichier proprietaire     : {stats['f4_proprietaires']}")
        print(f"     redefinitions (hors homonymes et   : {stats['f4_doublons']}")
        print("      adaptations) — 64 % de faux positifs mesures, d'ou le "
              "non-blocage")
        par_fichier: dict[tuple, int] = {}
        for constat in constats:
            if constat.tache is None:
                continue
            cle = (constat.tache.fichier, constat.forme)
            par_fichier[cle] = par_fichier.get(cle, 0) + 1
        if par_fichier:
            print("\nConstats par fichier de plan et par forme :")
            for (nom, forme), nombre in sorted(par_fichier.items(),
                                               key=lambda kv: (kv[0][1], -kv[1])):
                print(f"  {forme:<26} {nom:<34} {nombre:>4}")

    if args.forme2:
        print(f"\nAVERTISSEMENT (non bloquant) : {len(avert_backend)} tache(s) "
              f"creent une surface HTTP sans nommer de consommateur.\n")
        for constat in sorted(avert_backend, key=lambda c: c.tri):
            print(f"  {constat.tache.identifiant}  "
                  f"({constat.tache.fichier}:{constat.tache.ligne})")

    if args.doublons:
        print(f"\nAVERTISSEMENT (non bloquant) : {len(avert_doublon)} composant(s) "
              f"redefini(s) hors de leur fichier proprietaire.\n"
              f"  64 % de ces signalements ont ete VERIFIES faux (specialisation "
              f"legitime, homonyme de sens\n  different, helper minuscule) : a "
              f"lire, jamais a armer.\n")
        for constat in sorted(avert_doublon, key=lambda c: c.tri):
            nom, _, fichier = constat.cible.partition("|")
            print(f"  {nom}  redefini dans {fichier}")
            print(f"      fichier proprietaire : {', '.join(constat.detail)}")

    signatures = {c.signature for c in bloquants}
    base = charger_base()

    if args.write_baseline:
        ajouts = signatures - base
        amorce = not BASELINE_PATH.is_file()
        if ajouts and not (args.autoriser_croissance or amorce):
            print("REFUS : --write-baseline ne peut que RETRECIR la base.")
            print(f"{len(ajouts)} nouvelle(s) dette(s) voudraient y entrer :")
            for entree in sorted(ajouts)[:20]:
                print(f"  + {entree}")
            print("Corrigez la cible, ou assumez la dette avec "
                  "--autoriser-croissance.")
            return 1
        ecrire_base(signatures)
        print(f"Base de reference reecrite : {BASELINE_PATH.relative_to(ROOT)} "
              f"({len(signatures)} entree(s), {len(base - signatures)} retiree(s)).")
        return 0

    nouveaux = [c for c in bloquants if c.signature not in base]
    corriges = base - signatures

    if nouveaux:
        par_forme: dict[str, int] = {}
        for constat in nouveaux:
            par_forme[constat.forme] = par_forme.get(constat.forme, 0) + 1
        resume = ", ".join(f"{nombre} « {forme} »"
                           for forme, nombre in sorted(par_forme.items()))
        print(f"\nECHEC : {len(nouveaux)} constat(s) de travail MORT "
              f"({resume}) — hors base de reference.\n")
        for constat in sorted(nouveaux, key=lambda c: c.tri):
            if constat.tache is not None:
                print(f"  [{constat.forme}] {constat.tache.identifiant}  "
                      f"({constat.tache.fichier}:{constat.tache.ligne})")
            else:
                nom, _, fichier = constat.cible.partition("|")
                print(f"  [{constat.forme}] {nom}  ({fichier})")
            for ligne in _explique(constat):
                print(ligne)
        print("\nPOURQUOI : la regle du depot veut qu'un agent ne touche QUE les "
              "fichiers nommes dans `Files:`. Une tache qui nomme l'ecran sans "
              "nommer son fichier de montage INTERDIT donc de le brancher ; une "
              "tache a deux moities sans contrat commun laisse chaque cote "
              "INVENTER celui de l'autre ; et un composant redefini est du "
              "travail refait au lieu d'etre importe.")
        print("\nCette garde existe a cause de l'incident du 03/08/2026 : le "
              "module « Appels d'offres » a ete livre avec 194 taches cochees "
              "et une CI verte, pour 68 ecrans dont 7 seulement atteignables, "
              "206 ressources backend sans consommateur, et un ecran en 404 en "
              "production. Voir l'en-tete de scripts/check_taches_cablage.py. "
              "NE LA DESACTIVEZ PAS.")
        return 1

    print(f"OK : {stats['f1_creations']} tache(s) creent un ecran et "
          f"{stats['f3_candidates']} portent deux moities ; aucun NOUVEAU "
          f"constat bloquant ({len(base)} dette(s) historique(s) gelee(s), "
          f"dont {len(corriges)} desormais corrigee(s)).")
    print(f"   [non bloquant] {len(avert_backend)} tache(s) creent une surface "
          f"HTTP sans consommateur nomme — `--forme2` pour la liste.")
    print(f"   [non bloquant] {len(avert_doublon)} composant(s) redefini(s) "
          f"hors de leur fichier proprietaire — `--doublons` pour la liste.")
    if corriges:
        print("Ces dettes corrigees peuvent quitter la base : "
              "python scripts/check_taches_cablage.py --write-baseline")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
