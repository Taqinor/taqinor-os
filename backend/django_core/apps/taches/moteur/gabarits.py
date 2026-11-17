"""Gabarits de phrases purs (reference/textes.md §0, §3, §4) : tout ce que l'utilisateur lit.

Module pur : bibliothèque standard seule, aucune base, aucune horloge vivante.
Chaque phrase est ÉCRITE ICI telle que `textes.md` la donne ; aucun nombre n'y est
tapé : tout chiffre vient des données, ou des constantes nommées de `CONSTANTES`.

Syntaxe d'un gabarit : `{nom}` insère la variable ; `{nom?sing|plur}` insère `sing`
quand la variable vaut 0 ou 1 (ou moins de 2 pour un décimal), `plur` sinon.

Appelant : `texte(type_, cle, donnees, variante, nom_pour)`.
  type_ `notification` : `titre.<type>`, `matin.pousser_gardees`, `matin.pousser_proposees`,
    `matin.tenir`, `matin.libre`, `relance.echeance`, `relance.derive_pousser_essentiel`,
    `relance.derive_pousser_sans_essentiel`, `relance.derive_tenir`, `relance.neglige`,
    `soir.pousser`, `soir.libre`, `revue`, `revue.courte`, `rappel`, `test`.
  type_ `carte` : `palier.monter|baisser|premier|journee_type`, `garde_taille`,
    `derive.sous|au_dessus`, `pause`, `retour` ; type_ `retour` : cle `carte`.
  type_ `confirmation` : phrases de geste (§4.1) ; `bilan` : cle `texte` (deux lignes) ;
    `constat` : `C1`..`C8`, `C1.detail`, `C8.ecran`, `Cn.question` ; `revue` : `entete`.
`nom_pour(objet, usage)` rend le nom à montrer (ou `None` : rien de confidentiel).
"""
import math
import re
from datetime import time

CONSTANTES = {
    'bloc': 10,          # jours travaillés d'un bloc de rythme
    'fenetre_derive': 14,  # jours travaillés de la dérive « tenir » et du projet négligé
    'defaut': 5,         # objectif par défaut
    'reports': 3,        # reports qui rendent une tâche « à revoir »
    'apres_h': 16,       # heure de « celles d'après 16 h » (créneau fin de journée)
}
NB_VARIANTES = 3
JOURS_ABR = ('lun.', 'mar.', 'mer.', 'jeu.', 'ven.', 'sam.', 'dim.')
JOURS_NOM = ('Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche')
MOIS_ABR = ('janv.', 'févr.', 'mars', 'avr.', 'mai', 'juin', 'juil.', 'août',
            'sept.', 'oct.', 'nov.', 'déc.')
MOIS_NOM = ('janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août',
            'septembre', 'octobre', 'novembre', 'décembre')
ARRONDIS = ('R', 'm', 'bas', 'haut', 'N', 'N1', 'N_1', 'type', 'dit')

_JETON = re.compile(r'\{(\w+)(?:\?([^|}]*)\|([^}]*))?\}')


# --- Formats communs (textes.md §0) ---------------------------------------------------

def arrondir(x):
    """Au plus proche, la demie vers le bas (regles.md §0)."""
    return math.ceil(x - 0.5)


def format_heure(t):
    """« 10:00 » : puce, ligne, tuile."""
    return f'{t.hour:02d}:{t.minute:02d}'


def format_heure_dite(t):
    """« 10 h », « 10 h 30 » : phrase lue ou dite."""
    return f'{t.hour} h' if t.minute == 0 else f'{t.hour} h {t.minute:02d}'


def format_duree(minutes):
    """« 45 min », « 1 h », « 3 h 10 »."""
    h, m = divmod(int(minutes), 60)
    if h == 0:
        return f'{m} min'
    return f'{h} h' if m == 0 else f'{h} h {m:02d}'


def format_jour(d, aujourdhui, phrase=False):
    """`{jour}` de textes.md §0 : relatif, puis « jeu. 19 », « mar. 1 déc. », « 05/11/2027 ».

    Passé : « jeu. 12/11 ». `phrase=True` : le premier du mois s'écrit « 1er décembre ».
    """
    ecart = (d - aujourdhui).days
    if ecart == 0:
        return "aujourd'hui"
    if ecart == 1:
        return 'demain'
    abr = JOURS_ABR[d.weekday()]
    if ecart < 0:
        return f'{abr} {d.day:02d}/{d.month:02d}'
    if ecart <= 13:
        return f'{abr} {d.day}'
    if d.year != aujourdhui.year:
        return f'{d.day:02d}/{d.month:02d}/{d.year}'
    if phrase and d.day == 1:
        return f'{abr} 1er {MOIS_NOM[d.month - 1]}'
    return f'{abr} {d.day} {MOIS_ABR[d.month - 1]}'


def _nombre(valeur):
    if isinstance(valeur, float):
        return f'{valeur:.1f}'.replace('.', ',')
    return str(valeur)


def _montrer(valeur):
    if isinstance(valeur, time):
        return format_heure_dite(valeur)
    return _nombre(valeur)


def _rendre(modele, variables):
    def remplace(m):
        nom, sing, plur = m.groups()
        if nom not in variables:
            raise KeyError(f'variable manquante pour le gabarit : {nom}')
        valeur = variables[nom]
        if sing is None:
            return _montrer(valeur)
        return sing if abs(valeur) < 2 else plur
    return _JETON.sub(remplace, modele)


def _variables(donnees):
    v = dict(CONSTANTES)
    v.update(donnees)
    for nom in ARRONDIS:
        if isinstance(v.get(nom), float):
            v[nom] = arrondir(v[nom])
    return v


def _nom(v, cle, nom_pour, usage):
    """Nom montré de `v[cle]` par `nom_pour`, ou `None` (rien à montrer)."""
    if nom_pour is None or v.get(cle) is None:
        return None
    return nom_pour(v[cle], usage)


# --- Notifications (textes.md §3) -----------------------------------------------------

_TITRES = {
    'titre.plan_matin': "Aujourd'hui",
    'titre.relance': 'Message de {heure}',
    'titre.bilan_soir': 'Bilan du soir',
    'titre.revue_semaine': 'Revue de la semaine',
    'titre.rappel': 'Rappel',
    'titre.test': 'Test des notifications',
}

_NEGLIGE = "n'a pas avancé depuis {fenetre_derive} jours."
_ECHEANCE = "{n} tâche{n?|s} {n?a son|ont leur} échéance aujourd'hui."

_NOTIFICATIONS = {
    'matin.pousser_gardees': (
        'Ta journée : {prevues} prévue{prevues?|s} · objectif {objectif}.',
        'Bonjour. {prevues} tâche{prevues?|s} gardée{prevues?|s} ; objectif du jour : {objectif}.',
        'Plan du jour : choisis ton essentiel (objectif {objectif}).'),
    'matin.pousser_proposees': (
        '{proposees} proposée{proposees?|s} pour ton objectif de {objectif}.',
        "Bonjour. Proposé pour aujourd'hui : {proposees} tâche{proposees?|s} ; objectif {objectif}.",
        'Plan du jour : garde tes tâches et choisis ton essentiel (objectif {objectif}).'),
    'matin.tenir': (
        'Ta journée : {prevues} prévue{prevues?|s} · ton rythme {bas} à {haut}.',
        "Bonjour. {prevues} tâche{prevues?|s} t'attend{prevues?|ent} ; ton rythme : {bas} à {haut}.",
        'Plan du jour : choisis ton essentiel (rythme {bas} à {haut}).'),
    'matin.libre': (
        'Ta journée : {prevues} prévue{prevues?|s}.',
        "Bonjour. {prevues} tâche{prevues?|s} t'attend{prevues?|ent}.",
        'Plan du jour : choisis ton essentiel.'),
    'relance.echeance': (
        _ECHEANCE,
        "Échéance aujourd'hui : {n} tâche{n?|s} encore ouverte{n?|s}.",
        'Avant ce soir : {n} tâche{n?|s} à échéance.'),
    'relance.derive_pousser_essentiel': (
        '{faites} sur {objectif} ; ton essentiel est encore ouvert.',
        'À {heure} : {faites} sur {objectif}, essentiel à faire.',
        "Point de {heure} : {faites} sur {objectif} ; l'essentiel d'abord ?"),
    'relance.derive_pousser_sans_essentiel': (
        "{faites} sur {objectif} pour l'instant.",
        'À {heure} : {faites} sur {objectif}.',
        'Point de {heure} : {faites} sur {objectif}.'),
    'relance.derive_tenir': (
        '{faites} faite{faites?|s}, ton rythme est {bas} à {haut} : le reste peut attendre demain.',
        'Déjà {faites} faite{faites?|s}, au-delà de ton rythme ({bas} à {haut}).',
        "{faites} faite{faites?|s} aujourd'hui : tu peux t'arrêter là."),
    'relance.neglige': (
        "Ton projet prioritaire " + _NEGLIGE,
        'Rien de fait depuis {fenetre_derive} jours dans ton projet prioritaire.',
        'Ton projet prioritaire attend une tâche depuis {fenetre_derive} jours.'),
    'soir.pousser': (
        'Bilan : {faites} sur {objectif}.',
        'Journée close ? {faites} sur {objectif}.',
        '{faites} sur {objectif}, {restes} à placer.'),
    'soir.pousser.sans_reste': (
        'Bilan : {faites} sur {objectif}.',
        'Journée close ? {faites} sur {objectif}.',
        '{faites} sur {objectif}, rien à placer.'),
    'soir.libre': (
        'Bilan : {faites} faite{faites?|s}.',
        'Journée close ? {faites} tâche{faites?|s} faite{faites?|s}.',
        '{faites} faite{faites?|s}, {restes} à placer.'),
    'revue': (
        "Semaine : {faites} tâche{faites?|s} en {jours} jour{jours?|s}. La revue t'attend.",
        'Fin de semaine : {faites} faite{faites?|s}. On passe tes projets en revue ?',
        'Revue de la semaine : {projets} projet{projets?|s} actif{projets?|s} à passer en revue.'),
    'revue.courte': ('Semaine courte : on reprend lundi.',),
    'rappel': (
        'Une tâche à {heure}.',
        'Rappel de {heure} : {n} tâche{n?|s}.',
        "C'est l'heure : {n} tâche{n?|s} à {heure}."),
    'rappel.plusieurs': (
        '{n} tâches à {heure}.',
        'Rappel de {heure} : {n} tâche{n?|s}.',
        "C'est l'heure : {n} tâche{n?|s} à {heure}."),
    'test': ('Les notifications de Tâches arrivent bien sur cet appareil.',),
}


def _cle_notification(cle, v):
    if cle == 'soir.pousser' and v.get('restes') == 0:
        return 'soir.pousser.sans_reste'
    if cle == 'rappel' and v.get('n', 1) > 1:
        return 'rappel.plusieurs'
    return cle


def _avec_titre(cle, base, v, nom_pour):
    """Variante « avec titres » : seulement si l'appelant l'autorise ET le nom est montrable."""
    if not v.get('avec_titres'):
        return base
    if cle == 'relance.neglige':
        nom = _nom(v, 'projet', nom_pour, 'notification')
        return base if nom is None else _rendre('« %s » ' % nom + _NEGLIGE, v)
    nom = _nom(v, 'titre', nom_pour, 'notification')
    if nom is None:
        return base
    if cle.startswith('matin.'):
        return f'{base} En tête : « {nom} ».'
    if cle == 'relance.derive_pousser_essentiel':
        return f'{base} Essentiel : « {nom} ».'
    if cle == 'relance.echeance':
        return _echeance_avec_titre(nom, v)
    if cle in ('rappel', 'rappel.plusieurs') and v.get('n', 1) == 1:
        return _rendre('« %s » · {heure}' % nom, v)
    return base


def _echeance_avec_titre(nom, v):
    autres = v.get('n_autres') or 0
    if autres:
        return _rendre('« %s » et {n_autres} autre{n_autres?|s} ont leur échéance aujourd\'hui.' % nom, v)
    return "« %s » a son échéance aujourd'hui." % nom


def _notification(cle, v, var, nom_pour):
    if cle in _TITRES:
        return _rendre(_TITRES[cle], v)
    cle = _cle_notification(cle, v)
    modeles = _NOTIFICATIONS[cle]
    base = _rendre(modeles[var if len(modeles) > 1 else 0], v)
    return _avec_titre(cle, base, v, nom_pour)


# --- Cartes à réponse (textes.md §4.2) ------------------------------------------------

_CARTES = {
    'palier.monter': 'Ces {bloc} jours travaillés, tu as fait au moins {N} tâche{N?|s} {tenus} fois. '
                     'On passe à {N1} ?',
    'palier.baisser': 'Ces {bloc} jours travaillés, {N} tâche{N?|s} ou plus : {tenus} fois. '
                      'Revenir à {N_1} pour un temps ?',
    'palier.premier': "J'ai {bloc} jours de toi : ta journée type est {type} tâche{type?|s}. "
                      'Ton objectif est encore la valeur par défaut, {defaut}. Le mettre à {type} ?',
    'palier.journee_type': "J'ai {bloc} jours de toi : ta journée type est {type} tâche{type?|s} ; "
                           "ton objectif est {dit}, comme tu l'as choisi. Le mettre à {type} ?",
    'garde_taille': "Tes tâches terminées sont plus courtes qu'au départ ({med} min en médiane contre {ref}) "
                    ': je ne propose pas de monter.',
    'derive.sous': 'Ces {fenetre_derive} jours travaillés : {moyenne} tâche{moyenne?|s} par jour, '
                   'sous ton rythme ({bas} à {haut}). Garder {R}, ou descendre à {m} ?',
    'derive.au_dessus': 'Ces {fenetre_derive} jours travaillés : {moyenne} tâche{moyenne?|s} par jour, '
                        'au-dessus de ton rythme ({bas} à {haut}). Garder {R}, ou monter à {m} ?',
    'retour': 'Tu reviens après {jours} jour{jours?|s} : {taches} tâche{taches?|s} attend{taches?ait|aient}.',
}
_PAUSE_TYPES = {
    'plan_matin': 'le message du matin',
    'relance': 'le message de {heure}',
    'bilan_soir': 'le bilan du soir',
    'revue_semaine': 'la revue de la semaine',
}
_PAUSE = "J'ai mis en pause {quoi} : {ignorees} de suite sans être ouverts. Le réactiver ?"


def _carte(cle, v, var, nom_pour):
    if cle == 'pause':
        v['quoi'] = _rendre(_PAUSE_TYPES[v['type_pause']], v)
        return _rendre(_PAUSE, v)
    if cle == 'retour' and v['taches'] == 0:
        return ''  # 0 tâche : pas de carte
    return _rendre(_CARTES[cle], v)


def _retour(cle, v, var, nom_pour):
    return _carte('retour', v, var, nom_pour)


def boutons(cle, donnees):
    """Boutons d'une carte : liste de (libellé, `reponse`) — textes.md §4.2."""
    v = _variables(donnees)
    if cle == 'palier.monter':
        suite = [('Monter à {N1}', 'oui'), ('Pas maintenant', 'pas_maintenant')]
        if v.get('refus', 0) >= 3:
            suite.append(('Garder ce rythme', 'garder_ce_rythme'))
        return [(_rendre(libelle, v), rep) for libelle, rep in suite]
    table = {
        'palier.baisser': [('Descendre à {N_1}', 'oui'), ('Garder {N}', 'garder')],
        'garde_taille': [('Mes tâches ont changé', 'taches_changees'), ('OK', 'ok')],
        'derive.sous': [('Garder {R}', 'garder'), ('Descendre à {m}', 'passer')],
        'derive.au_dessus': [('Garder {R}', 'garder'), ('Monter à {m}', 'passer')],
        'pause': [('Le réactiver', 'reactiver'), ('OK', 'ok')],
        'retour': [('Les remettre dans Proposé', 'remettre_dans_propose'),
                   ('Les voir une par une', 'une_par_une')],
        'constat': [('Oui', 'oui'), ('Pas maintenant', 'pas_maintenant')],
        'constat.information': [('OK', 'ok')],
    }
    if cle in ('palier.premier', 'palier.journee_type'):
        return _boutons_type(cle, v)
    return [(_rendre(libelle, v), rep) for libelle, rep in table[cle]]


def _boutons_type(cle, v):
    cible = v['type']
    reference = v['dit'] if cle == 'palier.journee_type' else v['defaut']
    boutons_ = []
    if cible > reference:
        boutons_.append((_rendre('Monter à {type}', v), 'oui'))
    elif cible < reference:
        boutons_.append((_rendre('Descendre à {type}', v), 'oui'))
    if cle == 'palier.premier':
        boutons_.append((_rendre('Garder {defaut}', v), 'garder'))
    else:
        boutons_.append(('Pas maintenant', 'pas_maintenant'))
    return boutons_


# --- Confirmations de geste (textes.md §4.1) ------------------------------------------

_CONFIRMATIONS = {
    'objectif_dit': "Objectif du jour : {nb}, dès aujourd'hui.",
    'plus': "Objectif du jour : {nb} (un de plus), dès aujourd'hui.",
    'moins': "Objectif du jour : {nb} (un de moins), dès aujourd'hui.",
    'en_faire_plus': "En faire plus : objectif du jour {nb}. Je te proposerai d'aller plus loin quand tu le tiens.",
    'garder_ce_rythme': 'Garder ce rythme : environ {R} tâche{R?|s} par jour ({bas} à {haut}). '
                        "Je ne te pousse plus ; je te préviens seulement si tu t'en éloignes.",
    'garder_ce_rythme.provisoire': 'Garder ce rythme : environ {R} tâche{R?|s} par jour ({bas} à {haut}). '
                                   "Je ne te pousse plus ; je te préviens seulement si tu t'en éloignes. "
                                   'À confirmer sur {fenetre_derive} jours travaillés.',
    'sans_objectif': 'Sans objectif : plus de nombre visé. Tes faites, ton essentiel et tes gardées '
                     'restent affichés.',
    'comprendre_eteint': "C'est éteint : plus rien n'est calculé ni gardé sur ton rythme.",
}


def _confirmation(cle, v, var, nom_pour):
    return _rendre(_CONFIRMATIONS[cle], v)


# --- Bilan du soir (textes.md §4.3) ---------------------------------------------------

def _tete_bilan(v):
    mode = v['mode']
    if mode == 'libre':
        return _rendre('{faites} faite{faites?|s}', v)
    tete = _rendre('{faites} sur {objectif}', v)
    if mode == 'tenir':
        tete += _rendre(' (ton rythme : {bas} à {haut})', v)
    if v.get('jour_court'):
        tete += _rendre(' (jour court : objectif {objectif})', v)
    return tete


def _ligne_bilan(v):
    mode = v['mode']
    parties = [_tete_bilan(v)]
    atteint = mode == 'pousser' and v['faites'] >= v['objectif']
    if atteint:
        parties.append('objectif atteint')
    prevus = v.get('ep') or 0
    if prevus:
        if atteint and v['ef'] == prevus:
            parties.append('essentiel fait')
        else:
            parties.append(_rendre('essentiel {ef} sur {ep}', v))
    return ' · '.join(parties)


def _gardees(v):
    """« {pt} des {pl} gardées » ; vide quand rien n'était gardé."""
    if not v.get('pl'):
        return ''
    return _rendre('{pt} des {pl} gardée{pl?|s}', v)


def _bilan(cle, v, var, nom_pour):
    lignes = (_ligne_bilan(v), _gardees(v))
    return '\n'.join(ligne for ligne in lignes if ligne)


# --- Constats (textes.md §4.4) --------------------------------------------------------

_CONSTATS = {
    'C1': 'Tu finis plus souvent ton essentiel quand il est placé avant midi.',
    'C1.detail': 'Fini : {p1} % de tes gardées du matin, {p2} % de celles d\'après {apres_h} h '
                 '({n1} et {n2} ligne{n2?|s}).',
    'C1.question': "Mettre l'essentiel le matin ?",
    'C2': 'Essentiel fait {a} fois sur {na} quand il est en tête de ta journée, {b} sur {nb} sinon.',
    'C2.question': 'Le mettre en tête par défaut ?',
    'C3': '{Jour} : {m1} tâche{m1?|s} en moyenne, {m2} les autres jours.',
    'C3.question': 'En faire un jour court (un de moins) ?',
    'C4': "Tu gardes {p} tâche{p?|s}, tu en finis {f} (au milieu de tes {n} dernières journées).",
    'C4.question': 'Te proposer {f1} à garder ?',
    'C5': '{p} % de tes {n} tâche{n?|s} finie{n?|s} entre {h1} h et {h2} h.',
    'C6': 'Tes tâches « {nom} » ont pris {ratio} fois leur durée ({n} tâche{n?|s}).',
    'C6.question': 'Corriger leur durée à l\'avenir ?',
    'C7': '{n} tâche{n?|s} reportée{n?|s} {reports} fois ou plus.',
    'C7.question': 'Les revoir maintenant ?',
    'C8': "Ton projet prioritaire n'a pas avancé depuis {fenetre_derive} jours.",
    'C8.ecran': "« {nom} » n'a pas avancé depuis {fenetre_derive} jours.",
    'C8.question': 'Mettre une de ses tâches dans Proposé demain ?',
}


def _constat(cle, v, var, nom_pour):
    if cle == 'C3':
        jour = v['jour']
        v['Jour'] = JOURS_NOM[jour] if isinstance(jour, int) else jour[:1].upper() + jour[1:]
    if cle in ('C6', 'C8.ecran'):
        v['nom'] = _nom(v, 'projet', nom_pour, 'ecran') or 'un projet'
    return _rendre(_CONSTATS[cle], v)


# --- Revue de la semaine (textes.md §4.6) ---------------------------------------------

def _jour_court(d):
    return f'{JOURS_ABR[d.weekday()]} {d.day}'


def _debut_revue(v):
    phrase = 'Du {debut} au {fin} : {faites} tâche{faites?|s} en {jours} jour{jours?|s}'
    v = dict(v, debut=_jour_court(v['debut']), fin=_jour_court(v['fin']))
    if v.get('prec') is not None:
        phrase += ' (précédente : {prec})'
    return _rendre(phrase, v) + '.'


def _chiffres_revue(v):
    parties = []
    if v.get('mode') != 'libre' and v.get('oa') is not None:
        parties.append(_rendre('Objectif atteint {oa} jour{oa?|s} sur {jours}', v))
    if v.get('je'):
        parties.append(_rendre('essentiel {e} sur {je}', v))
    gardees = _gardees(v)
    if gardees:
        parties.append(gardees)
    if not parties:
        return ''
    return ' · '.join(parties) + '.'


def _revue(cle, v, var, nom_pour):
    if v.get('semaine_courte'):
        return 'Semaine courte, on reprend lundi.'
    morceaux = [_debut_revue(v), _chiffres_revue(v)]
    n = v.get('non_travailles')
    if n:
        libelle = 'Jours non travaillés' if n >= 2 else 'Jour non travaillé'
        morceaux.append(f'{libelle} : {n}.')
    return ' '.join(m for m in morceaux if m)


# --- Point d'entrée -------------------------------------------------------------------

_RENDEURS = {
    'notification': _notification,
    'carte': _carte,
    'retour': _retour,
    'confirmation': _confirmation,
    'bilan': _bilan,
    'constat': _constat,
    'revue': _revue,
}


def texte(type_, cle, donnees, variante=0, nom_pour=None):
    """Rend la phrase `cle` du `type_`, mot pour mot, avec ses accords.

    `variante` : 0, 1 ou 2 (rotation `variante(J.toordinal())`) ; sans effet sur les
    phrases à formulation unique. Variable manquante : `KeyError` (jamais un texte à trous).
    """
    rendeur = _RENDEURS.get(type_)
    if rendeur is None:
        raise ValueError(f'type de gabarit inconnu : {type_!r}')
    return rendeur(cle, _variables(donnees), variante % NB_VARIANTES, nom_pour)


def toutes_les_phrases():
    """Chaque modèle écrit dans ce module (pour le contrôle du lexique)."""
    for modeles in _NOTIFICATIONS.values():
        yield from modeles
    yield from _TITRES.values()
    yield from _CARTES.values()
    yield from _PAUSE_TYPES.values()
    yield _PAUSE
    yield from _CONFIRMATIONS.values()
    yield from _CONSTATS.values()


__all__ = ('texte', 'boutons', 'arrondir', 'format_jour', 'format_heure', 'format_heure_dite',
           'format_duree', 'toutes_les_phrases')
