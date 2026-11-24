"""Les textes personnalisés d'un acte : forme stockée, rendu strict,
résolution, alignement d'une correction faite à l'écran, validation des
personnalisations reçues (docs/contrats/conception.md § 4).

Déplacé tel quel de ``contenu.py`` (mur des 2 000 lignes) ; ``contenu``
réexporte chaque nom. Ce module n'importe jamais ``contenu`` (aucun
cycle) : lectures pures, rien n'est écrit ici.
"""
import difflib
import functools
import re
import string
import types
from datetime import date
from decimal import Decimal, InvalidOperation

from . import types as T

ZERO = Decimal('0')

A_PRECISER = {'fr': 'à préciser', 'ar': 'يُحدَّد لاحقًا'}


def _d(valeur):
    if valeur is None or valeur == '':
        return None
    try:
        return Decimal(str(valeur))
    except (InvalidOperation, ValueError):
        return None


def _date(valeur):
    if isinstance(valeur, date):
        return valeur
    try:
        return date.fromisoformat(str(valeur)[:10]) if valeur else None
    except ValueError:
        return None


# ── Gabarits : un texte personnalisé ne fige jamais une valeur ──────────────
# Un article ou un quitus est une suite de JETONS : texte littéral
# ``('t', texte)`` ou repère ``('r', nom)`` (la valeur vivante ``ctx[nom]``).
# Les textes par défaut sont lus en jetons en les rendant avec des
# SENTINELLES à la place des valeurs. Une correction faite à l'écran est une
# différence sur le texte que l'écran AFFICHAIT : elle est rejouée sur les
# jetons de ce texte (``aligner``), jamais devinée en cherchant une valeur
# dans le texte.
#
# Forme stockée d'un texte : une chaîne où « {nom} » est un repère et
# « {{ » / « }} » des accolades tapées ; le rendu ne substitue que des noms de
# repères connus (``noms_reperes`` et clés du contexte), jamais par
# ``str.format`` : aucun accès « {societe[x]} » n'est évalué. Un paragraphe
# (ou le titre) peut aussi valoir ``{'defaut': j}`` — le paragraphe j de
# l'article de base, entièrement vivant, y compris si le texte par défaut
# change — ou ``{'defaut': j, 'texte': …}`` — la version de l'utilisateur du
# paragraphe j, imprimée tant que ce paragraphe existe (une option qui le
# retire la masque, la recocher la rend). Un article personnalisé est stocké
# ``{cle, v: 2, titre, paragraphes[, base]}`` ; l'ancienne forme (chaînes
# seules, sans ``v``) se lit toujours, rendue telle qu'elle est.

#: Espaces que les montants mis en forme emploient (normale, insécable,
#: fine insécable).
_SEPARATEURS = '   '
_OUVRE, _FERME = '', ''
_SENTINELLE = re.compile(f'{_OUVRE}([^{_FERME}]*){_FERME}')
_NOM_REPERE = re.compile(r'[A-Za-z_][A-Za-z0-9_]*')
_REPERE_STOCKE = re.compile(r'\{\{|\}\}|\{([A-Za-z_][A-Za-z0-9_]*)\}')
#: Forme stockée d'un article personnalisé.
FORME_ARTICLE = 2
#: Séparateur des paragraphes quand plusieurs sont alignés d'un bloc.
_SEP = '\n\n'
#: Un repère VIDE ne s'ancre qu'à un voisin resté dans un bloc d'au moins
#: autant de caractères inchangés — jamais à une lettre isolée qu'un texte
#: réécrit partage par hasard avec l'ancien.
_ANCRE_MIN = 3
_ESPACES = str.maketrans({' ': ' ', ' ': ' '})


def _espaces(texte):
    """Le texte, espaces insécables et fines ramenées à l'espace normale :
    deux textes qui ne diffèrent que par elles sont le même texte (le
    navigateur renvoie souvent des espaces normales)."""
    return texte.translate(_ESPACES)


def _memes(a, b):
    if isinstance(a, list):
        return isinstance(b, list) and len(a) == len(b) and all(
            _memes(x, y) for x, y in zip(a, b))
    return isinstance(b, str) and _espaces(a) == _espaces(b)


def _fusionner(jetons):
    """Jetons normalisés : littéraux voisins réunis, littéraux vides ôtés."""
    sortie = []
    for sorte, valeur in jetons:
        if sorte == 't':
            if not valeur:
                continue
            if sortie and sortie[-1][0] == 't':
                sortie[-1] = ('t', sortie[-1][1] + valeur)
                continue
        sortie.append((sorte, valeur))
    return sortie


def lire_gabarit(texte):
    """Les jetons d'un texte stocké (« {nom} » repère, « {{ » / « }} »
    accolades ; toute autre accolade est du texte)."""
    texte = '' if texte is None else str(texte)
    jetons, pos = [], 0
    for m in _REPERE_STOCKE.finditer(texte):
        jetons.append(('t', texte[pos:m.start()]))
        if m.group(1):
            jetons.append(('r', m.group(1)))
        else:
            jetons.append(('t', m.group(0)[0]))
        pos = m.end()
    jetons.append(('t', texte[pos:]))
    return _fusionner(jetons)


def ecrire_gabarit(jetons):
    """La forme stockée de jetons (accolades tapées doublées)."""
    return ''.join(
        valeur.replace('{', '{{').replace('}', '}}') if sorte == 't'
        else '{' + valeur + '}' for sorte, valeur in jetons)


def _chaines_du_module(module):
    """Les chaînes écrites dans un module de textes (constantes et corps des
    fonctions), pour y lire les repères qu'ils citent."""
    pile = [v for k, v in vars(module).items() if not k.startswith('__')]
    vus = set()
    while pile:
        objet = pile.pop()
        if id(objet) in vus:
            continue
        vus.add(id(objet))
        if isinstance(objet, str):
            yield objet
        elif isinstance(objet, (tuple, list, set, frozenset)):
            pile.extend(objet)
        elif isinstance(objet, dict):
            pile.extend(objet.values())
        elif isinstance(objet, types.CodeType):
            pile.extend(objet.co_consts)
        elif isinstance(objet, types.FunctionType) \
                and objet.__module__ == module.__name__:
            pile.append(objet.__code__)


def _champs(chaine):
    try:
        return {nom for _l, nom, _s, _c in string.Formatter().parse(chaine)
                if nom and _NOM_REPERE.fullmatch(nom)}
    except ValueError:
        return set()


@functools.lru_cache(maxsize=1)
def noms_reperes():
    """Tous les repères que les textes par défaut citent (lus dans
    ``textes`` et ``textes_ar``, jamais une liste écrite ici) : un repère
    connu mais absent du contexte s'imprime « à préciser »."""
    from . import textes
    modules, noms = [textes], set()
    try:
        from . import textes_ar
        modules.append(textes_ar)
        noms |= set(getattr(textes_ar, 'FORMES_CTX', {}))
    except ImportError:
        pass
    for module in modules:
        for chaine in _chaines_du_module(module):
            noms |= _champs(chaine)
    return frozenset(noms)


def _valeur(nom, ctx, langue, connus):
    if nom in ctx:
        valeur = ctx[nom]
        return '' if valeur is None else str(valeur)
    if nom in connus:
        return A_PRECISER.get(langue, A_PRECISER['fr'])
    return '{' + nom + '}'


def rendre_jetons(jetons, ctx, langue='fr', connus=None):
    """Le texte de jetons, avec les valeurs vivantes de ``ctx`` (un repère
    connu absent s'imprime « à préciser » ; un nom inconnu reste écrit)."""
    ctx = ctx or {}
    connus = (frozenset(ctx) | noms_reperes()) if connus is None else connus
    return ''.join(valeur if sorte == 't'
                   else _valeur(valeur, ctx, langue, connus)
                   for sorte, valeur in jetons)


def rendre_gabarit(gabarit, ctx, langue='fr'):
    """Le texte d'un gabarit stocké, avec les valeurs vivantes de ``ctx`` —
    substitution stricte des seuls repères connus, jamais d'erreur."""
    return rendre_jetons(lire_gabarit(gabarit), ctx, langue)


def _jetons_sentinelles(texte):
    texte = texte or ''
    jetons, pos = [], 0
    for m in _SENTINELLE.finditer(texte):
        jetons += [('t', texte[pos:m.start()]), ('r', m.group(1))]
        pos = m.end()
    jetons.append(('t', texte[pos:]))
    return _fusionner(jetons)


def _sentinelles(ctx):
    return {nom: f'{_OUVRE}{nom}{_FERME}'
            for nom in set(ctx or {}) | noms_reperes()}


def articles_en_jetons(textes, type_acte, variante, options, ctx):
    """Les articles PAR DÉFAUT d'un acte, en jetons (mêmes clés, mêmes
    paragraphes, mêmes conditions sur ``options`` que ``textes``)."""
    s = _sentinelles(ctx)
    return [{'cle': a['cle'], 'titre': _jetons_sentinelles(a.get('titre')),
             'paragraphes': [_jetons_sentinelles(p)
                             for p in a.get('paragraphes') or []]}
            for a in textes.articles_par_defaut(type_acte, variante, s,
                                                options)]


def quitus_en_jetons(textes, ctx):
    return [_jetons_sentinelles(p)
            for p in textes.quitus_par_defaut(_sentinelles(ctx))]


# ── Résolution : textes stockés → jetons ────────────────────────────────────

def _ref(x):
    """L'indice d'un renvoi ``{'defaut': j}`` (avec ou sans ``texte``)."""
    if isinstance(x, dict):
        j = x.get('defaut')
        if isinstance(j, int) and not isinstance(j, bool):
            return j
    return None


def _jetons_de(x, base):
    """Les jetons d'un texte stocké relatif à ``base`` (liste de jetons), ou
    None quand il ne s'imprime pas (renvoi vers un paragraphe absent)."""
    if isinstance(x, str):
        return lire_gabarit(x)
    j = _ref(x)
    if j is None or not 0 <= j < len(base):
        return None
    if isinstance(x.get('texte'), str):
        return lire_gabarit(x['texte'])
    return base[j]


def resoudre_paragraphes(base, liste, masques=None):
    """``[(jetons, source)]`` : une liste stockée de paragraphes appliquée
    aux paragraphes ``base`` (None : ceux de la base, en renvois)."""
    if not isinstance(liste, list):
        return [(p, {'defaut': j}) for j, p in enumerate(base)]
    sortie = []
    for x in liste:
        jetons = _jetons_de(x, base)
        if jetons is not None:
            sortie.append((jetons, x))
        elif masques is not None and _ref(x) is not None:
            masques.append(x)
    return sortie


def _en_base(articles):
    """Des articles résolus devenus la BASE du niveau suivant : chaque
    paragraphe y est le renvoi ``{'defaut': j}``."""
    return [{'cle': a['cle'], 'titre': a['titre'],
             'paragraphes': list(a['paragraphes']),
             'src_titre': {'defaut': 0},
             'src': [{'defaut': j} for j in range(len(a['paragraphes']))],
             'de_base': True, 'entree': None} for a in articles]


def resoudre_articles(base, liste, masques=None):
    """Applique une liste d'articles stockée à ``base`` (articles en jetons).
    Entrées : ``{cle}`` reprend l'article de base ; ``{cle, retire}`` est un
    article supprimé à l'écran ; ``{cle, titre, paragraphes[, base]}`` est un
    article personnalisé. Une personnalisation d'un article de base
    (``base``) n'est pas imprimée quand une option retire cet article —
    elle reste stockée et revient avec l'option (``masques`` la reçoit) ; un
    article de base jamais cité par la liste (une option recochée, un
    article nouveau) reprend sa place dans l'ordre de base."""
    if not isinstance(liste, list):
        return list(base)
    par_cle = {a['cle']: a for a in base}
    citees = {a.get('cle') for a in liste if isinstance(a, dict)}
    sortie = []
    for e in liste:
        if not isinstance(e, dict) or e.get('retire'):
            continue
        cle = e.get('cle') or ''
        b = par_cle.get(cle)
        if 'paragraphes' not in e and 'titre' not in e:
            if b is not None:
                sortie.append(b)
            continue
        if e.get('base') and b is None:
            if masques is not None:
                masques.append(('article', e))
            continue
        titre = _jetons_de(e.get('titre', ''), [b['titre']] if b else [])
        caches = []
        paragraphes = resoudre_paragraphes(
            b['paragraphes'] if b else [], list(e.get('paragraphes') or []),
            caches)
        if caches and masques is not None:
            masques.append(('paragraphe', e))
        sortie.append({'cle': cle, 'titre': titre or [],
                       'paragraphes': [j for j, _s in paragraphes],
                       'src_titre': e.get('titre', ''),
                       'src': [s for _j, s in paragraphes],
                       'de_base': b is not None, 'entree': e})
    for i, b in enumerate(base):
        if b['cle'] in citees:
            continue
        avant = {x['cle'] for x in base[:i]}
        pos = 0
        for j, s in enumerate(sortie):
            if s['cle'] in avant:
                pos = j + 1
        sortie.insert(pos, b)
    return sortie


def _rendre_article(a, ctx, langue, connus):
    return {'cle': a['cle'],
            'titre': rendre_jetons(a['titre'], ctx, langue, connus),
            'paragraphes': [rendre_jetons(p, ctx, langue, connus)
                            for p in a['paragraphes']]}


# ── Alignement : une correction rejouée sur les jetons affichés ─────────────

def _ancre(a, debuts, image, bloc, longueur):
    """Position, dans le texte saisi, d'un repère VIDE placé en ``a`` du
    texte affiché : juste après son voisin de gauche s'il est resté (un
    fragment vide est collé au texte qui le précède : « {devis_reference}
    {devis_accepte_le} », « {contrat_reference}.{ecart_regle} ») ; en début
    de paragraphe, juste avant son voisin de droite. None : l'utilisateur a
    réécrit cet endroit, le repère disparaît."""
    if a > 0 and a not in debuts:
        g = image[a - 1]
        return g + 1 if g is not None and bloc[a - 1] >= _ANCRE_MIN else None
    if a < longueur and image[a] is not None and bloc[a] >= _ANCRE_MIN:
        return image[a]
    return None


def aligner(affiches, saisis, ctx, langue='fr', connus=None):
    """Rejoue sur des jetons la correction faite à l'écran.

    ``affiches`` : les jetons des paragraphes que l'écran a montrés (rendus
    avec ``ctx``) ; ``saisis`` : les paragraphes renvoyés. Rend une liste de
    jetons par paragraphe saisi. Les caractères laissés tels quels gardent
    leur origine ; un repère dont TOUTE la valeur est restée, d'un seul
    tenant, redevient ``{nom}`` ; un repère dont la valeur a été modifiée
    en son milieu devient du texte (l'utilisateur l'a reprise à son compte —
    le contrôle des montants à l'émission s'y applique) ; un repère vide
    garde sa place tant que son voisin est resté (``_ancre``)."""
    ctx = ctx or {}
    connus = (frozenset(ctx) | noms_reperes()) if connus is None else connus
    morceaux, reperes, debuts, pos = [], [], set(), 0
    for k, jetons in enumerate(affiches):
        if k:
            morceaux.append(_SEP)
            pos += len(_SEP)
        debuts.add(pos)
        for sorte, valeur in jetons:
            texte = (valeur if sorte == 't'
                     else _valeur(valeur, ctx, langue, connus))
            if sorte == 'r':
                reperes.append((valeur, pos, pos + len(texte)))
            morceaux.append(texte)
            pos += len(texte)
    affiche = ''.join(morceaux)
    saisi = _SEP.join(saisis)
    image, bloc = [None] * len(affiche), [0] * len(affiche)
    inverse = [None] * len(saisi)
    # Espaces normale, insécable et fine insécable : égales pour
    # l'alignement (le navigateur rend souvent des espaces normales).
    for tag, i1, i2, j1, _j2 in difflib.SequenceMatcher(
            None, _espaces(affiche), _espaces(saisi),
            autojunk=False).get_opcodes():
        if tag == 'equal':
            for k in range(i2 - i1):
                image[i1 + k], bloc[i1 + k] = j1 + k, i2 - i1
                inverse[j1 + k] = i1 + k

    def litteral(a, b):
        # Un caractère resté garde celui du texte affiché (ses espaces).
        return ''.join(saisi[u] if inverse[u] is None
                       else affiche[inverse[u]] for u in range(a, b))
    evenements = []
    for ordre, (nom, a, b) in enumerate(reperes):
        if b > a:
            vues = image[a:b]
            if None not in vues and vues[-1] - vues[0] == b - a - 1:
                evenements.append((vues[0], ordre, vues[-1] + 1, nom))
        else:
            u = _ancre(a, debuts, image, bloc, len(affiche))
            if u is not None:
                evenements.append((u, ordre, u, nom))
    evenements.sort()
    sortie, debut = [], 0
    for texte in saisis:
        fin, jetons, curseur = debut + len(texte), [], debut
        for ud, _ordre, uf, nom in evenements:
            if ud < curseur or ud < debut or uf > fin:
                continue
            jetons += [('t', litteral(curseur, ud)), ('r', nom)]
            curseur = uf
        jetons.append(('t', litteral(curseur, fin)))
        sortie.append(_fusionner(jetons))
        debut = fin + len(_SEP)
    return sortie


def _forme_stockee(jetons, source, base):
    """La forme stockée d'un paragraphe (ou titre) aligné : le renvoi
    ``{'defaut': j}`` s'il redevient le paragraphe j de la base, sinon sa
    chaîne — liée au paragraphe d'origine (``{'defaut': j, 'texte'}``) quand
    il en vient, pour qu'une option qui retire ce paragraphe la masque."""
    j = _ref(source)
    jetons = _fusionner(jetons)
    candidats = ([j] if j is not None and j < len(base) else []) + list(
        range(len(base)))
    for k in candidats:
        if _fusionner(base[k]) == jetons:
            return {'defaut': k}
    texte = ecrire_gabarit(jetons)
    return {'defaut': j, 'texte': texte} if j is not None else texte


def _compacter_paragraphes(affiches, saisis, base, ctx, langue, connus):
    """Forme stockée d'une liste de paragraphes renvoyée par l'écran.
    ``affiches`` : ``[(jetons, source)]`` tels que montrés. Même nombre :
    paragraphe par paragraphe ; sinon les listes sont d'abord alignées
    (paragraphes inchangés, blocs remplacés alignés d'un tenant). Un
    paragraphe inchangé garde sa source (renvoi vivant ou texte stocké) ;
    un paragraphe ajouté est du texte."""
    rendus = [rendre_jetons(j, ctx, langue, connus) for j, _s in affiches]
    if len(rendus) == len(saisis):
        paires = [([i], [i]) for i in range(len(saisis))]
    else:
        paires = []
        for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(
                None, [_espaces(r) for r in rendus],
                [_espaces(s) for s in saisis], autojunk=False).get_opcodes():
            if tag == 'equal':
                paires += [([i1 + k], [j1 + k]) for k in range(i2 - i1)]
            elif j2 > j1:
                paires.append((list(range(i1, i2)), list(range(j1, j2))))
    sortie = []
    for ia, ju in paires:
        seul = len(ia) == 1 and len(ju) == 1
        if seul and _memes(rendus[ia[0]], saisis[ju[0]]):
            sortie.append(affiches[ia[0]][1])
            continue
        source = affiches[ia[0]][1] if seul else None
        for jetons in aligner([affiches[i][0] for i in ia],
                              [saisis[j] for j in ju], ctx, langue, connus):
            sortie.append(_forme_stockee(jetons, source, base))
    return sortie


def _compacter_article(a, titre, paragraphes, b, ctx, langue, connus):
    """L'entrée stockée d'un article modifié à l'écran (``a`` : tel
    qu'affiché, ``b`` : son article de base ou None)."""
    if _memes(rendre_jetons(a['titre'], ctx, langue, connus), titre):
        src_titre = a['src_titre']
    else:
        src_titre = _forme_stockee(
            aligner([a['titre']], [titre], ctx, langue, connus)[0],
            a['src_titre'] if _ref(a['src_titre']) is not None else None,
            [b['titre']] if b else [])
    paras = _compacter_paragraphes(list(zip(a['paragraphes'], a['src'])),
                                   paragraphes,
                                   b['paragraphes'] if b else [], ctx, langue,
                                   connus)
    if b is not None and src_titre == {'defaut': 0} and paras == [
            {'defaut': j} for j in range(len(b['paragraphes']))]:
        return {'cle': a['cle']}
    entree = {'cle': a['cle'], 'v': FORME_ARTICLE, 'titre': src_titre,
              'paragraphes': paras}
    if b is not None:
        entree['base'] = True
    return entree


def _article_neuf(cle, titre, paragraphes):
    return {'cle': cle, 'v': FORME_ARTICLE,
            'titre': ecrire_gabarit([('t', titre)]),
            'paragraphes': [ecrire_gabarit([('t', p)]) for p in paragraphes]}


def _remettre_non_affichees(sortie, anciennes, affichees):
    """Les entrées déjà stockées pour un article que l'écran ne pouvait pas
    montrer (supprimé, ou personnalisé puis retiré par une option) sont
    gardées telles quelles, à leur place : la liste reçue ne les connaît
    pas, elle ne peut pas les défaire."""
    prises = {e.get('cle') for e in sortie}
    precedente = None
    for e in anciennes or []:
        if not isinstance(e, dict):
            continue
        cle = e.get('cle')
        if cle not in affichees and cle not in prises:
            pos = next((i + 1 for i, s in enumerate(sortie)
                        if s.get('cle') == precedente), 0)
            sortie.insert(pos, e)
            prises.add(cle)
        if cle in prises:
            precedente = cle
    return sortie


def compacter_articles(avant, apres, entrants, langue='fr'):
    """Forme stockée d'une liste d'articles reçue de l'écran.

    ``avant`` : l'état que l'écran AFFICHAIT (``_construire(...,
    interne=True)`` AVANT ce corps : anciennes options, anciennes dates,
    textes stockés) — chaque article reçu est comparé à CET affichage, jamais
    à une base calculée avec les options du même corps (B1). ``apres`` : le
    même acte avec les réglages communs du corps : il dit quels articles de
    base existent désormais. Une liste qui reprend au moins la moitié des
    articles affichés est COMPLÈTE (elle fixe l'ordre ; un article affiché
    et toujours dans la base qui en est absent est marqué ``retire``) ; une
    liste plus courte modifie les articles cités et ajoute les nouveaux à la
    fin. Un article inchangé garde son entrée (ou ``{cle}``) : il suit les
    options et la vente ; un article modifié est aligné (``aligner``)."""
    affiches = avant['articles']
    par_cle = {a['cle']: a for a in affiches}
    cles_aff = [a['cle'] for a in affiches]
    base_avant = {a['cle']: a for a in avant['base']}
    base_apres = {a['cle']: a for a in apres['base']}
    communes = {e['cle'] for e in entrants} & set(cles_aff)
    retires = []
    if not cles_aff or len(communes) * 2 >= len(cles_aff):
        liste = list(entrants)
        retires = [{'cle': c, 'retire': True} for c in cles_aff
                   if c not in communes and c in base_apres]
    else:
        remplaces = {e['cle']: e for e in entrants}
        liste = [remplaces.get(c) or {'cle': c, '_garder': True}
                 for c in cles_aff]
        liste += [e for e in entrants if e['cle'] not in par_cle]
    sortie = []
    for e in liste:
        cle = e['cle']
        a = par_cle.get(cle)
        if e.get('_garder'):
            sortie.append(a['entree'] or {'cle': cle})
            continue
        if 'paragraphes' not in e and 'titre' not in e:
            sortie.append(a['entree'] if a is not None and not a['de_base']
                          and a['entree'] else {'cle': cle})
            continue
        titre, paragraphes = e.get('titre') or '', list(
            e.get('paragraphes') or [])
        etat = avant
        if a is None and cle in base_apres:
            # Un article qu'une option de ce corps fait apparaître : comparé
            # à la nouvelle base, avec le nouveau contexte.
            a, etat = base_apres[cle], apres
        if a is None:
            sortie.append(_article_neuf(cle, titre, paragraphes))
            continue
        ctx, connus = etat['ctx'], etat['connus']
        if _memes(rendre_jetons(a['titre'], ctx, langue, connus), titre) \
                and _memes([rendre_jetons(p, ctx, langue, connus)
                            for p in a['paragraphes']], paragraphes):
            sortie.append(a['entree'] or {'cle': cle})
            continue
        b = (base_avant if etat is avant else base_apres).get(cle)
        sortie.append(_compacter_article(a, titre, paragraphes, b, ctx,
                                         langue, connus))
    sortie = _remettre_non_affichees(sortie, avant['entrees'], set(cles_aff))
    return sortie + [r for r in retires
                     if r['cle'] not in {s.get('cle') for s in sortie}]


def compacter_quitus(avant, saisis, langue='fr'):
    """Forme stockée du quitus renvoyé par l'écran, aligné sur le quitus
    affiché ; None quand il redevient celui de la base."""
    affiches = avant['quitus']
    ctx, connus = avant['ctx'], avant['connus']
    if _memes([rendre_jetons(j, ctx, langue, connus) for j, _s in affiches],
              list(saisis)):
        return avant['quitus_stocke']
    stocke = _compacter_paragraphes(affiches, saisis, avant['quitus_base'],
                                    ctx, langue, connus)
    if stocke == [{'defaut': j} for j in range(len(avant['quitus_base']))]:
        return None
    return stocke


def texte_litteral(sources):
    """Le texte LITTÉRAL de textes stockés (chaînes ou ``{'defaut', 'texte'}``)
    : ce que l'utilisateur a tapé ou repris, sans la valeur d'aucun repère.
    Un renvoi vers la base n'en a pas."""
    morceaux = []
    for x in sources:
        texte = x if isinstance(x, str) else (
            x.get('texte') if isinstance(x, dict) else None)
        if isinstance(texte, str):
            morceaux.append(''.join(v if s == 't' else '\n'
                                    for s, v in lire_gabarit(texte)))
    return '\n'.join(morceaux)


#: Les options booléennes qui retirent un article ou un paragraphe, toutes
#: cochées : sert à nommer un article masqué par une option.
_OPTIONS_TOUT = {'reserve_propriete': True, 'raccorde_reseau': True,
                 'penalite_retard_pct': '1'}


def _titre_masque(entree, textes, type_acte, variante, options, ctx, langue):
    titre = entree.get('titre')
    if isinstance(titre, str) or isinstance((titre or {}).get('texte'), str):
        return rendre_gabarit(titre if isinstance(titre, str)
                              else titre['texte'], ctx, langue)
    for a in textes.articles_par_defaut(type_acte, variante, ctx,
                                        {**options, **_OPTIONS_TOUT}):
        if a['cle'] == entree.get('cle'):
            return a['titre']
    return entree.get('cle') or ''


def message_masques(masques, ctx, textes, contenu, langue='fr'):
    """Les phrases d'avertissement des textes personnalisés qu'une option
    empêche d'imprimer (ils reviennent avec elle)."""
    sortie = []
    for sorte, entree in masques:
        titre = _titre_masque(entree, textes, contenu['type'],
                              contenu['variante'], contenu['options'], ctx,
                              langue)
        if sorte == 'article':
            sortie.append(
                f"L'article « {titre} », que vous avez modifié, n'est pas "
                f"imprimé : l'option qui le porte est décochée. Votre version "
                f"reviendra si vous la cochez de nouveau.")
        else:
            sortie.append(
                f"Un paragraphe que vous avez modifié dans l'article « "
                f"{titre} » n'est pas imprimé : l'option qui le porte est "
                f"décochée. Votre version reviendra si vous la cochez de "
                f"nouveau.")
    return list(dict.fromkeys(sortie))


def sections_modifiables(type_acte, langue='fr'):
    sections = T.SECTIONS_MODIFIABLES[type_acte]
    if langue == 'ar':
        return [s for s in sections if s in T.SECTIONS_TEXTE]
    return list(sections)


# ── Validation des personnalisations reçues ─────────────────────────────────

class ContenuInvalide(ValueError):
    """Personnalisation refusée (400 ``contenu_invalide``), message français."""


def _exiger(condition, message):
    if not condition:
        raise ContenuInvalide(message)


def _texte(valeur, section):
    _exiger(isinstance(valeur, str), f'Section « {section} » : texte attendu.')
    return valeur


def _liste_textes(valeur, section):
    _exiger(isinstance(valeur, list) and all(isinstance(x, str) for x in valeur),
            f'Section « {section} » : liste de textes attendue.')
    return valeur


def _date_texte(valeur, section, vide_permis=True):
    if valeur is None or (vide_permis and valeur == ''):
        return None
    _exiger(isinstance(valeur, str) and _date(valeur) is not None
            and len(valeur) == 10,
            f'Section « {section} » : date AAAA-MM-JJ attendue.')
    return valeur


def _entier(valeur, section, *, positif=True):
    if valeur is None or valeur == '':
        return None
    if isinstance(valeur, bool):
        raise ContenuInvalide(f'Section « {section} » : nombre entier attendu.')
    try:
        d = Decimal(str(valeur).strip().replace(',', '.'))
    except (InvalidOperation, ValueError):
        raise ContenuInvalide(f'Section « {section} » : nombre entier attendu.')
    _exiger(d.is_finite() and d == d.to_integral_value()
            and (d >= 0 or not positif) and d < 100000,
            f'Section « {section} » : nombre entier attendu.')
    return int(d)


def _dict_permis(valeur, section, cles):
    _exiger(isinstance(valeur, dict), f'Section « {section} » : objet attendu.')
    return {k: v for k, v in valeur.items() if k in cles}


def _textes_du_dict(v, cles, section):
    for k in cles:
        if v.get(k) is not None:
            _texte(v[k], section)
    return v


def _booleen(v, cle, section):
    if cle in v and v[cle] is not None:
        _exiger(isinstance(v[cle], bool),
                f'Section « {section} » : vrai ou faux attendu ({cle}).')


def _v_societe(valeur, langue):
    v = _dict_permis(valeur, 'societe', T.CLES_SOCIETE)
    return _textes_du_dict(v, T.CLES_SOCIETE, 'societe')


def _v_delais(valeur, langue):
    v = _dict_permis(valeur, 'delais', T.CLES_DELAIS if langue == 'fr'
                     else T.CLES_DELAIS_AR)
    if 'date_limite' in v:
        v['date_limite'] = _date_texte(v['date_limite'], 'delais')
    return _textes_du_dict(v, ('resume', 'detail'), 'delais')


def _v_livraison(valeur, langue):
    v = _dict_permis(valeur, 'livraison', T.CLES_LIVRAISON)
    if 'date' in v:
        v['date'] = _date_texte(v['date'], 'livraison')
    _booleen(v, 'avec_series', 'livraison')
    return _textes_du_dict(v, ('suite', 'suite_detail'), 'livraison')


def _v_reception(valeur, langue):
    v = _dict_permis(valeur, 'reception', T.CLES_RECEPTION)
    if 'date_mise_en_service' in v:
        v['date_mise_en_service'] = _date_texte(
            v['date_mise_en_service'], 'reception')
    _booleen(v, 'prononcee', 'reception')
    return _textes_du_dict(v, ('delai_levee_reserves',), 'reception')


def _v_sav(valeur, langue):
    v = _dict_permis(valeur, 'sav', T.CLES_SAV)
    return _textes_du_dict(v, T.CLES_SAV, 'sav')


def _v_paiement(valeur, langue):
    _exiger(isinstance(valeur, dict), 'Section « paiement » : objet attendu.')
    montants = [k for k in valeur if k not in T.CLES_PAIEMENT_TEXTE]
    _exiger(not montants,
            "Les montants ne se modifient pas dans un acte : corrigez "
            "l'échéancier de la vente (" + ', '.join(sorted(montants)) + ').')
    autres = [k for k in valeur if k not in T.CLES_PAIEMENT_MODIFIABLES]
    _exiger(not autres,
            'Section « paiement » : seuls les moyens de paiement '
            '(modalites) se modifient.')
    return _textes_du_dict(dict(valeur), T.CLES_PAIEMENT_MODIFIABLES,
                           'paiement')


def _v_options(valeur, langue):
    v = _dict_permis(valeur, 'options', T.CLES_OPTIONS)
    for k in ('consommateur', 'reserve_propriete', 'raccorde_reseau'):
        _booleen(v, k, 'options')
    if 'delai_execution_jours' in v:
        v['delai_execution_jours'] = _entier(v['delai_execution_jours'],
                                             'options')
    if v.get('penalite_retard_pct') is not None:
        d = _d(str(v['penalite_retard_pct']).replace(',', '.'))
        _exiger(d is not None and d.is_finite() and ZERO <= d <= 100,
                'Option « penalite_retard_pct » : pourcentage entre 0 et 100 '
                'attendu.')
        v['penalite_retard_pct'] = f'{d.normalize():f}'
    return v


def _v_echeancier_textes(valeur, langue):
    _exiger(isinstance(valeur, dict),
            'Section « echeancier_textes » : objet attendu.')
    sortie = {}
    for cle, mots in valeur.items():
        _exiger(isinstance(mots, dict),
                'Section « echeancier_textes » : objet attendu par tranche.')
        _exiger(all(k in ('exigibilite', 'note') for k in mots),
                "Les montants ne se modifient pas dans un acte : corrigez "
                "l'échéancier de la vente.")
        sortie[str(cle)] = {k: _texte(v, 'echeancier_textes')
                            for k, v in mots.items() if v is not None}
    return sortie


def _cles_perso(entrees):
    """Une entrée sans clé (ajoutée à l'écran) reçoit ``perso_<n>``."""
    n = 1
    prises = {e['cle'] for e in entrees if e['cle']}
    for e in entrees:
        if not e['cle']:
            while f'perso_{n}' in prises:
                n += 1
            e['cle'] = f'perso_{n}'
            prises.add(e['cle'])
    return entrees


def _v_articles(valeur, langue):
    _exiger(isinstance(valeur, list), 'Section « articles » : liste attendue.')
    sortie = []
    for a in valeur:
        _exiger(isinstance(a, dict),
                'Section « articles » : un objet par article attendu.')
        cle = a.get('cle')
        _exiger(cle is None or isinstance(cle, str),
                'Section « articles » : clé texte attendue.')
        entree = {'cle': cle or ''}
        if 'titre' in a or 'paragraphes' in a:
            entree['titre'] = _texte(a.get('titre') or '', 'articles')
            entree['paragraphes'] = _liste_textes(a.get('paragraphes') or [],
                                                  'articles')
        sortie.append(entree)
    return _cles_perso(sortie)


def _v_constats(valeur, langue):
    _exiger(isinstance(valeur, list), 'Section « constats » : liste attendue.')
    sortie = []
    for k in valeur:
        _exiger(isinstance(k, dict) and isinstance(k.get('texte'), str),
                'Section « constats » : {texte, cochee} attendu.')
        sortie.append({'texte': k['texte'], 'cochee': bool(k.get('cochee'))})
    return sortie


def _v_conseils(valeur, langue):
    _exiger(isinstance(valeur, list), 'Section « conseils » : liste attendue.')
    sortie = []
    for k in valeur:
        _exiger(isinstance(k, dict), 'Section « conseils » : objet attendu.')
        sortie.append({c: _texte(k.get(c) or '', 'conseils')
                       for c in T.CLES_CONSEIL})
    return sortie


def _v_garanties(valeur, langue):
    _exiger(isinstance(valeur, list), 'Section « garanties » : liste attendue.')
    if langue == 'ar':
        # La traduction ne porte que les textes d'une ligne française (même
        # clé) : durées et dates de fin reçues sont ignorées.
        sortie = []
        for g in valeur:
            _exiger(isinstance(g, dict),
                    'Section « garanties » : objet attendu.')
            _exiger(isinstance(g.get('cle'), str) and g['cle'],
                    'Section « garanties » : en arabe, chaque ligne porte la '
                    'clé de sa ligne française.')
            ligne = {'cle': g['cle']}
            for k in T.CLES_GARANTIE_TEXTE:
                if g.get(k) is not None:
                    ligne[k] = _texte(g[k], 'garanties')
            sortie.append(ligne)
        return sortie
    sortie = []
    for g in valeur:
        _exiger(isinstance(g, dict), 'Section « garanties » : objet attendu.')
        sortie.append({
            'cle': g.get('cle') if isinstance(g.get('cle'), str) else '',
            'designation': _texte(g.get('designation') or '', 'garanties'),
            'duree_mois': _entier(g.get('duree_mois'), 'garanties'),
            'duree_libelle': _texte(g.get('duree_libelle') or '', 'garanties'),
            'garant': _texte(g.get('garant') or '', 'garanties'),
            'detail': _texte(g.get('detail') or '', 'garanties'),
            'fin': _date_texte(g.get('fin'), 'garanties'),
        })
    return _cles_perso(sortie)


_VALIDATEURS = {
    'titre': lambda v, langue: _texte(v, 'titre'),
    'conditions_particulieres': lambda v, langue: _texte(
        v, 'conditions_particulieres'),
    'conseils_intro': lambda v, langue: _texte(v, 'conseils_intro'),
    'lieu': lambda v, langue: _texte(v, 'lieu'),
    'date_document': lambda v, langue: _date_texte(v, 'date_document'),
    'reserves': lambda v, langue: _liste_textes(v, 'reserves'),
    'quitus': lambda v, langue: _liste_textes(v, 'quitus'),
    'entretien': lambda v, langue: _liste_textes(v, 'entretien'),
    'societe': _v_societe, 'delais': _v_delais, 'livraison': _v_livraison,
    'reception': _v_reception, 'sav': _v_sav, 'paiement': _v_paiement,
    'options': _v_options, 'echeancier_textes': _v_echeancier_textes,
    'articles': _v_articles, 'constats': _v_constats, 'conseils': _v_conseils,
    'garanties': _v_garanties,
}


def _valider_section(type_acte, section, valeur, langue):
    validateur = _VALIDATEURS.get(section)
    if validateur is None:
        raise ContenuInvalide(f'Section inconnue : {section}.')
    return validateur(valeur, langue)


def valider_surcharges(type_acte, surcharges, langue='fr'):
    """Contrôle et nettoie des personnalisations reçues. Une section hors
    ``sections_modifiables`` (de la langue), un montant ou une forme
    inattendue lève ``ContenuInvalide`` (message français). ``None`` = remettre
    la section au défaut (gardé tel quel)."""
    if langue not in T.LANGUES:
        raise ContenuInvalide(f'Langue inconnue : {langue}.')
    _exiger(isinstance(surcharges, dict), 'Personnalisations : objet attendu.')
    permises = set(sections_modifiables(type_acte, langue))
    propre = {}
    for section, valeur in surcharges.items():
        if section not in permises:
            if section in T.SECTIONS_MODIFIABLES[type_acte] and langue == 'ar':
                raise ContenuInvalide(
                    f'Section « {section} » : commune aux deux langues, elle '
                    f'se règle en français.')
            raise ContenuInvalide(f'Section inconnue : {section}.')
        propre[section] = (None if valeur is None else
                           _valider_section(type_acte, section, valeur, langue))
    return propre
