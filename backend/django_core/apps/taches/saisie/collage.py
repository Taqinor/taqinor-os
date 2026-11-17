"""Coller une liste (reference/regles.md §1.10) — pur, sans Django ni base.

`decouper_collage(textes, …)` découpe un ou plusieurs collages (un par note, un
par liste) en lignes analysées : puces et cases retirées, titres de groupe
(« Courses : »), première ligne proposée comme projet, points de check-list
(lignes en retrait), doublons, projet suggéré sans IA. Rien n'est écrit : le
résultat est l'aperçu que l'écran montre avant « Créer N tâches ».
"""
import re
from dataclasses import dataclass

from apps.taches.saisie.analyseur import analyser, resoudre_projet
from apps.taches.saisie.grammaire import ContexteSaisie
from apps.taches.saisie.normalisation import cle_nom, normaliser

MAX_LIGNES = 200
MAX_CARACTERES = 20_000
MAX_COLLAGES = 10
MAX_NOUVEAUX_PROJETS = 10
LONGUEUR_MAX_PROJET_LIGNE = 60     # (d) de la règle « première ligne = projet »
LIGNES_APRES_PROJET = 2            # (e) au moins deux lignes la suivent
RETRAIT_SOUS_TACHE = 2             # ≥ 2 espaces de plus que la dernière ligne non en retrait
LONGUEUR_MIN_NOM_SUGGERE = 4
PRIORITE_PROJET_NE = 2

MESSAGE_TROP_DE_LIGNES = 'Liste trop longue : 200 lignes au plus (ici {n}). Colle-la en deux fois.'
MESSAGE_TROP_DE_CARACTERES = '20 000 caractères au plus.'
MESSAGE_TROP_DE_COLLAGES = '10 collages au plus par aperçu.'
MESSAGE_TROP_DE_PROJETS = '10 nouveaux projets au plus par envoi.'

_PUCE = re.compile(r'(?:[•·]\s*|[-*–—]\s+|\d{1,3}[.)]\s+)')
_CASE_FAITE = re.compile(r'(?:\[[xX]\]|✓|✔|☑)\s*')
_CASE_VIDE = re.compile(r'(?:\[\s?\]|☐|□)\s*')


@dataclass(frozen=True)
class LigneNette:
    """Une ligne collée une fois nettoyée (puces et cases retirées)."""
    texte: str
    retrait: int = 0
    deja_faite: bool = False
    avait_puce: bool = False
    titre_groupe: bool = False


# ---------------------------------------------------------------- nettoyage

def _mesurer_retrait(brute):
    """Retrait mesuré AVANT normalisation : une tabulation = 4 espaces."""
    marge = brute[:len(brute) - len(brute.lstrip())]
    return len(marge.replace('\t', '    '))


def _retirer_prefixes(texte):
    """`(texte, deja_faite, avait_puce)` : puces de tête, puis case cochée ou vide."""
    avait = False
    m = _PUCE.match(texte)
    if m:
        texte, avait = texte[m.end():], True
    faite = _CASE_FAITE.match(texte)
    if faite:
        return texte[faite.end():].strip(), True, True
    vide = _CASE_VIDE.match(texte)
    if vide:
        return texte[vide.end():].strip(), False, True
    return texte.strip(), False, avait


def est_titre_groupe(texte):
    """Une ligne qui finit par « : » (reste à vérifier qu'une ligne la suit)."""
    return texte.rstrip().endswith((':', '：'))


def nettoyer_ligne(brute):
    """`LigneNette`, ou None pour une ligne vide ou de ponctuation seule."""
    corps = brute.strip()
    if not any(c.isalnum() for c in corps):
        return None
    texte, faite, avait = _retirer_prefixes(corps)
    if not texte:
        return None
    return LigneNette(texte=texte, retrait=_mesurer_retrait(brute), deja_faite=faite,
                      avait_puce=avait, titre_groupe=est_titre_groupe(texte))


def _lignes_nettes(texte):
    return [n for n in (nettoyer_ligne(b) for b in texte.splitlines()) if n is not None]


def _marquer_titres(nettes):
    """Un titre de groupe doit être suivi d'au moins une ligne ; sinon c'est une tâche."""
    marquees = []
    for i, n in enumerate(nettes):
        suivie = i < len(nettes) - 1
        if n.titre_groupe and not suivie:
            n = LigneNette(n.texte, n.retrait, n.deja_faite, n.avait_puce, False)
        marquees.append(n)
    return marquees


# ------------------------------------------------------------------ projets

def _contexte(base, projets):
    return ContexteSaisie(base['aujourdhui'], base['maintenant'], projets=tuple(projets))


def _champs_projet(valeur):
    """Champs `projet_id` / `nouveau_projet` d'un projet résolu ({} si archivé)."""
    if valeur is None or valeur.get('archive'):
        return {}
    if valeur['nouveau']:
        return {'nouveau_projet': {'nom': valeur['nom'], 'priorite': valeur['priorite']}}
    return {'projet_id': valeur['id']}


def projet_premiere_ligne(nettes, base, projets):
    """(a)-(e) de §1.10.5 : la première ligne devient le projet commun de son collage.

    Rend `(valeur de projet, nom)` ou None.
    """
    if len(nettes) < 1 + LIGNES_APRES_PROJET:
        return None
    premiere = nettes[0]
    if premiere.titre_groupe or premiere.avait_puce or premiere.deja_faite:
        return None
    if len(premiere.texte) > LONGUEUR_MAX_PROJET_LIGNE:
        return None
    lecture = analyser(premiere.texte, base['aujourdhui'], base['maintenant'], projets=projets)
    if lecture.jetons:
        return None
    return resoudre_projet(premiere.texte, _contexte(base, projets)).valeur


def _projet_suggere(titre, projets):
    """Exactement un projet actif (nom ≥ 4 caractères) contenu comme mot entier dans le titre."""
    cible = normaliser(titre)
    trouves = [p for p in projets
               if p.statut == 'actif' and len(p.nom) >= LONGUEUR_MIN_NOM_SUGGERE
               and re.search(r'(?<!\w)' + re.escape(normaliser(p.nom)) + r'(?!\w)', cible)]
    if len(trouves) != 1:
        return None
    return {'id': trouves[0].id, 'nom': trouves[0].nom}


# ------------------------------------------------------------------- lignes

def _ligne_apercu(index, collage, nette, lecture, parent, projet):
    """Un élément de `lignes[]` de l'aperçu (forme de saisie_apercu.json)."""
    champs = dict(lecture.champs)
    if not any(j['type'] == 'projet' for j in lecture.jetons):
        champs = {**champs, **_champs_projet(projet)} if projet else champs
    ligne = {
        'index': index, 'collage': collage, 'tache_id': None, 'texte': nette.texte,
        'titre': lecture.titre, 'cochee': not nette.deja_faite, 'deja_faite': nette.deja_faite,
        'doublon_de': None, 'doublon_de_ligne': None, 'etape_de': parent,
        'alertes': list(lecture.alertes), 'jetons': list(lecture.jetons), 'champs': champs,
        'projet_suggere': None}
    if lecture.erreurs:
        ligne['erreurs'] = lecture.erreurs
        ligne['cochee'] = False
    return ligne


def _est_sous_tache(nette, base_retrait):
    return base_retrait is not None and nette.retrait >= base_retrait + RETRAIT_SOUS_TACHE


def _analyser_collage(numero, texte, base, projets, depart, projet_impose):
    """Lignes d'un collage et son projet commun : `(lignes, projet_commun | None)`."""
    nettes = _marquer_titres(_lignes_nettes(texte))
    commun = projet_impose
    entree = None
    if commun is None:
        commun = projet_premiere_ligne(nettes, base, projets)
        if commun is not None:
            entree = {'collage': numero, 'id': commun['id'], 'nom': commun['nom'],
                      'nouveau': commun['nouveau'], 'priorite': commun.get('priorite'),
                      'source': 'premiere_ligne'}
            nettes = nettes[1:]
    lignes = _lignes_du_collage(numero, nettes, base, projets, depart, commun)
    return lignes, entree


def _lignes_du_collage(numero, nettes, base, projets, depart, commun):
    lignes, projet, parent, base_retrait = [], commun, None, None
    for nette in nettes:
        if nette.titre_groupe:
            nom = nette.texte.rstrip().rstrip(':：').strip()
            projet = resoudre_projet(nom, _contexte(base, projets)).valeur
            parent, base_retrait = None, None
            continue
        sous = _est_sous_tache(nette, base_retrait)
        lecture = analyser(nette.texte, base['aujourdhui'], base['maintenant'],
                           projets=projets, sections=base['sections'],
                           etiquettes=base['etiquettes'], est_ouvre=base['est_ouvre'])
        index = depart + len(lignes)
        lignes.append(_ligne_apercu(index, numero, nette, lecture,
                                    parent if sous else None, projet))
        if not sous:
            parent, base_retrait = index, nette.retrait
    return lignes


# ------------------------------------------------------------------ doublons

def marquer_doublons(lignes, taches_ouvertes, projets):
    """§1.10.8-9 : doublon d'une tâche ouverte ou d'une ligne précédente ; projet suggéré."""
    ouvertes = {}
    for identifiant, titre in taches_ouvertes:
        ouvertes.setdefault(cle_nom(titre), identifiant)
    vues = {}
    for ligne in lignes:
        if ligne['etape_de'] is not None:
            continue
        cle = cle_nom(ligne['titre'])
        if cle and cle in ouvertes:
            ligne['doublon_de'], ligne['cochee'] = ouvertes[cle], False
        elif cle and cle in vues:
            ligne['doublon_de_ligne'], ligne['cochee'] = vues[cle], False
        elif cle:
            vues[cle] = ligne['index']
        if not _a_un_projet(ligne):
            ligne['projet_suggere'] = _projet_suggere(ligne['titre'], projets)


def _a_un_projet(ligne):
    champs = ligne['champs']
    return 'projet_id' in champs or 'nouveau_projet' in champs


def _projets_nouveaux(lignes, communs):
    """Projets nés de l'envoi, sans doublon (par `cle_nom`), `priorite` 2 par défaut."""
    vus, nouveaux = set(), []
    candidats = [{'nom': c['nom'], 'priorite': c['priorite'] or PRIORITE_PROJET_NE}
                 for c in communs if c['nouveau']]
    candidats += [ligne['champs']['nouveau_projet'] for ligne in lignes
                  if 'nouveau_projet' in ligne['champs']]
    for projet in candidats:
        cle = cle_nom(projet['nom'])
        if cle not in vus:
            vus.add(cle)
            nouveaux.append({'nom': projet['nom'], 'priorite': projet['priorite']})
    return nouveaux


# ------------------------------------------------------------------- publique

def erreurs_limites(textes):
    """Plafonds §1.7 d'un aperçu : `{'texte': [message]}` ou `{}` (400 sur `texte`)."""
    textes = [textes] if isinstance(textes, str) else list(textes)
    messages = []
    nombre = sum(1 for t in textes for ligne in t.splitlines() if ligne.strip())
    if len(textes) > MAX_COLLAGES:
        messages.append(MESSAGE_TROP_DE_COLLAGES)
    if nombre > MAX_LIGNES:
        messages.append(MESSAGE_TROP_DE_LIGNES.format(n=nombre))
    if sum(len(t) for t in textes) > MAX_CARACTERES:
        messages.append(MESSAGE_TROP_DE_CARACTERES)
    return {'texte': messages} if messages else {}


def decouper_collage(textes, aujourdhui, maintenant, projets=(), sections=(), etiquettes=(),
                     taches_ouvertes=(), est_ouvre=None, projet_impose=None):
    """Aperçu d'un ou plusieurs collages (rien n'est écrit).

    `textes` : un collage par élément (un par note). `taches_ouvertes` :
    `(id, titre)` des tâches ouvertes du propriétaire (doublons). `projet_impose`
    : valeur de projet (`resoudre_projet`) valable pour tout l'envoi, qui
    remplace la « première ligne = projet ». Rend `{'projets_communs',
    'lignes', 'projets_nouveaux'}` (forme de `saisie_apercu.json`).
    """
    textes = [textes] if isinstance(textes, str) else list(textes)
    projets = tuple(projets)
    base = {'aujourdhui': aujourdhui, 'maintenant': maintenant, 'sections': tuple(sections),
            'etiquettes': tuple(etiquettes), 'est_ouvre': est_ouvre}
    lignes, communs = [], []
    for numero, texte in enumerate(textes):
        du_collage, commun = _analyser_collage(
            numero, texte, base, projets, len(lignes), projet_impose)
        lignes.extend(du_collage)
        if commun is not None:
            communs.append(commun)
    marquer_doublons(lignes, taches_ouvertes, projets)
    return {'projets_communs': communs, 'lignes': lignes,
            'projets_nouveaux': _projets_nouveaux(lignes, communs)}
