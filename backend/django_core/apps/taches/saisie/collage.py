"""Coller une liste (reference/regles.md §1.10) — pur, sans Django ni base.

`decouper_collage(textes, …)` découpe un ou plusieurs collages (un par note, un
par liste) en lignes analysées : puces et cases retirées, titres de groupe
(« Courses : »), première ligne proposée comme projet, points de check-list
(lignes en retrait), doublons, projet suggéré sans IA. Rien n'est écrit : le
résultat est l'aperçu que l'écran montre avant « Créer N tâches ».
"""
import re
from dataclasses import dataclass, replace

from apps.taches.choix import AlerteSaisie
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


LONGUEUR_MAX_TITRE = 60           # R2-004 : un titre de groupe sans « : » tient sur une ligne courte
LIGNES_SOUS_TITRE = 2              # … et annonce au moins deux lignes (ligne vide, casse)
_FIN_DE_PHRASE = ('.', '?', '!', '…')


@dataclass(frozen=True)
class LigneNette:
    """Une ligne collée une fois nettoyée (puces et cases retirées)."""
    texte: str
    retrait: int = 0
    deja_faite: bool = False
    avait_puce: bool = False
    titre_groupe: bool = False
    apres_vide: bool = False


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
    """Les lignes nettes ; `apres_vide` dit qu'une ligne vraiment vide (blancs seuls) les sépare de la précédente."""
    nettes, vide = [], False
    for brute in texte.splitlines():
        nette = nettoyer_ligne(brute)
        if nette is None:
            vide = vide or not brute.strip()
            continue
        nettes.append(replace(nette, apres_vide=vide and bool(nettes)))
        vide = False
    return nettes


def _premiere_lettre(texte):
    return next((c for c in texte if c.isalpha()), '')


def _en_minuscule(nette):
    return _premiere_lettre(nette.texte).islower()


def _candidat_titre(nette, base, projets):
    """Peut nommer un groupe : courte, sans puce ni case, pas une phrase finie, et rien n'y est lu (date, `#`, `!`…)."""
    texte = nette.texte.rstrip()
    if nette.avait_puce or nette.deja_faite or len(texte) > LONGUEUR_MAX_TITRE or texte.endswith(_FIN_DE_PHRASE):
        return False
    return not analyser(texte, base['aujourdhui'], base['maintenant'], projets=projets).jetons


def _lignes_du_bloc(nettes, i):
    """Les lignes qui suivent `i` jusqu'à la prochaine ligne vide."""
    n = 0
    for suivante in nettes[i + 1:]:
        if suivante.apres_vide:
            break
        n += 1
    return n


def _points_qui_suivent(nettes, i):
    """Les lignes « d'élément » qui suivent `i` : à puce ou commençant par une minuscule, sans ligne vide."""
    n = 0
    for suivante in nettes[i + 1:]:
        if suivante.apres_vide or not (suivante.avait_puce or _en_minuscule(suivante)):
            break
        n += 1
    return n


def _titres_sans_deux_points(nettes, base, projets):
    """R2-004 — indices des titres de groupe écrits « comme dans Notes », sans « : ».

    Une ligne candidate (`_candidat_titre`) suivie d'une ligne à puce au même niveau (une ligne EN RETRAIT reste un
    point de check-list), ou précédée d'une ligne vide et suivie d'au moins deux lignes. Dès qu'un tel titre (ou un
    titre « : ») existe, la liste est structurée : une ligne en Majuscule entre des lignes en minuscule (« Admin »
    entre « envoyer la proforma » et « payer la CNSS ») suivie d'au moins deux points en est un aussi, et la
    première ligne candidate devient le titre de son groupe (la « première ligne = projet » ne joue plus).
    """
    candidats = [_candidat_titre(n, base, projets) for n in nettes]
    titres = set()
    for i in range(1, len(nettes) - 1):
        n, suivante = nettes[i], nettes[i + 1]
        if not candidats[i]:
            continue
        a_puce = suivante.avait_puce and suivante.retrait < n.retrait + RETRAIT_SOUS_TACHE
        if a_puce or (n.apres_vide and _lignes_du_bloc(nettes, i) >= LIGNES_SOUS_TITRE):
            titres.add(i)
    if not titres and not any(n.titre_groupe for n in nettes):
        return titres
    for i in range(1, len(nettes) - 1):
        n, precedente = nettes[i], nettes[i - 1]
        if (i not in titres and candidats[i] and _premiere_lettre(n.texte).isupper()
                and (precedente.avait_puce or _en_minuscule(precedente))
                and _points_qui_suivent(nettes, i) >= LIGNES_SOUS_TITRE):
            titres.add(i)
    if len(nettes) > 1 and candidats[0] and 1 not in titres and not nettes[1].titre_groupe:
        titres.add(0)
    return titres


def _marquer_titres(nettes, base, projets, avec_implicites=True):
    """Un titre de groupe doit être suivi d'au moins une ligne ; sinon c'est une tâche."""
    implicites = _titres_sans_deux_points(nettes, base, projets) if avec_implicites else set()
    marquees = []
    for i, n in enumerate(nettes):
        suivie = i < len(nettes) - 1
        titre = (n.titre_groupe or i in implicites) and suivie
        marquees.append(replace(n, titre_groupe=titre))
    return marquees


# ------------------------------------------------------------------ projets

def _contexte(base, projets):
    return ContexteSaisie(base['aujourdhui'], base['maintenant'], projets=tuple(projets))


def resoudre_groupe(nom, ctx):
    """R3-043 — le projet d'un titre de groupe ou d'une première ligne : le nom exact, sinon le projet OUVERT dont un
    mot commence ainsi (« Recrutement » → « Recrutement technicien », au lieu d'un « Nouveau projet : Recrutement » à
    côté) — mais seulement s'il est le SEUL (règle de R2-003) : un début partagé par deux projets ne rattache le
    groupe à aucun, il reste un nouveau projet. Rend la valeur de projet (`resoudre_projet`)."""
    exact = resoudre_projet(nom, ctx).valeur
    if exact is None or not exact['nouveau']:
        return exact
    par_debut = resoudre_projet(nom, ctx, par_debut=True)
    if par_debut.valeur['nouveau'] or AlerteSaisie.PLUSIEURS_PROJETS.value in par_debut.alertes:
        return exact
    return par_debut.valeur


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
    return resoudre_groupe(premiere.texte, _contexte(base, projets))


#: R4-26 — petits mots ignorés quand on compare deux noms de projet (« Ecole Al Manar de Salé » ~ « École Al-Manar »).
_MOTS_VIDES = frozenset({'a', 'au', 'aux', 'd', 'de', 'des', 'du', 'en', 'et', 'l', 'la', 'le', 'les', 'pour', 'sur',
                         'un', 'une'})
_STATUTS_PROPOSES = ('actif', 'en_pause')
MOTS_COMMUNS_MIN = 2


def _mots(nom):
    return frozenset(m for m in re.findall(r'\w+', normaliser(nom)) if m not in _MOTS_VIDES)


def ressemblance(nom, projets):
    """R4-26 — le projet OUVERT dont le nom ressemble à celui d'un NOUVEAU projet (« Pompage Ouled Saleh » à côté de
    « Pompage Douar Ouled Saleh ») : tous les mots de l'un sont dans l'autre (accents, casse, ponctuation et petits
    mots ignorés), au moins deux en commun. Le plus de mots communs l'emporte ; deux candidats à égalité : aucun
    (jamais un choix au hasard). Rend `{'id', 'nom'}` ou None. Rien n'est fusionné : l'écran PROPOSE « Utiliser »."""
    mots = _mots(nom)
    candidats = []
    for projet in projets:
        if projet.statut not in _STATUTS_PROPOSES or cle_nom(projet.nom) == cle_nom(nom):
            continue
        siens = _mots(projet.nom)
        communs = len(mots & siens)
        if communs >= MOTS_COMMUNS_MIN and (mots <= siens or siens <= mots):
            candidats.append((communs, projet))
    if not candidats:
        return None
    candidats.sort(key=lambda c: -c[0])
    if len(candidats) > 1 and candidats[1][0] == candidats[0][0]:
        return None
    meilleur = candidats[0][1]
    return {'id': meilleur.id, 'nom': meilleur.nom}


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
    # un projet imposé (« Range dans ce projet ») vaut pour tout l'envoi : seuls les titres « : » le changent
    nettes = _marquer_titres(_lignes_nettes(texte), base, projets, avec_implicites=projet_impose is None)
    commun = projet_impose
    entree = None
    if commun is None and not any(n.titre_groupe for n in nettes[1:]):
        commun = projet_premiere_ligne(nettes, base, projets)
        if commun is not None:
            entree = {'collage': numero, 'id': commun['id'], 'nom': commun['nom'],
                      'nouveau': commun['nouveau'], 'priorite': commun.get('priorite'),
                      'source': 'premiere_ligne',
                      'ressemble_a': ressemblance(commun['nom'], projets) if commun['nouveau'] else None}
            nettes = nettes[1:]
    lignes = _lignes_du_collage(numero, nettes, base, projets, depart, commun)
    return lignes, entree


def _lignes_du_collage(numero, nettes, base, projets, depart, commun):
    lignes, projet, parent, base_retrait = [], commun, None, None
    for nette in nettes:
        if nette.titre_groupe:
            nom = nette.texte.rstrip().rstrip(':：').strip()
            projet = resoudre_groupe(nom, _contexte(base, projets))
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


def _projets_nouveaux(lignes, communs, projets=()):
    """Projets nés de l'envoi, sans doublon (par `cle_nom`), `priorite` 2 par défaut ; R4-26 : `ressemble_a`, le
    projet existant dont le nom est proche (ou None)."""
    vus, nouveaux = set(), []
    candidats = [{'nom': c['nom'], 'priorite': c['priorite'] or PRIORITE_PROJET_NE}
                 for c in communs if c['nouveau']]
    candidats += [ligne['champs']['nouveau_projet'] for ligne in lignes
                  if 'nouveau_projet' in ligne['champs']]
    for projet in candidats:
        cle = cle_nom(projet['nom'])
        if cle not in vus:
            vus.add(cle)
            nouveaux.append({'nom': projet['nom'], 'priorite': projet['priorite'],
                             'ressemble_a': ressemblance(projet['nom'], projets)})
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
            'projets_nouveaux': _projets_nouveaux(lignes, communs, projets)}
