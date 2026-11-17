"""Analyseur de saisie rapide (reference/regles.md §1.5-§1.8) — pur, sans Django ni base.

`analyser(texte, aujourdhui, maintenant, …)` lit UNE ligne et rend ce qui a été
compris (`champs`) ET où dans le texte (`jetons[].debut/fin`, pour surligner),
le titre restant et les alertes. Une phrase que la grammaire ne comprend pas
reste un titre intact : jamais une exception. « Aujourd'hui » et « maintenant »
sont des paramètres, jamais l'horloge.
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from apps.taches.choix import AlerteSaisie
from apps.taches.saisie.grammaire import (
    CONVERTISSEURS, MOTIFS, TYPES_CAPTURE, ContexteSaisie, candidats, choisir,
    composer_echeances, filtrer_contexte, libelle_jour, masquer_guillemets, moment_de)

TITRE_MAX = 280
MESSAGE_TITRE_VIDE = 'Le titre est vide une fois la date et le projet retirés.'
MESSAGE_TITRE_LONG = 'Le titre est trop long : 280 caractères au plus.'


@dataclass(frozen=True)
class Analyse:
    """Sortie de `analyser` : titre, jetons (positions), champs (LIGNE de l'API), alertes."""
    titre: str
    jetons: tuple = ()
    champs: dict = field(default_factory=dict)
    alertes: tuple = ()
    erreurs: dict = field(default_factory=dict)


def _hhmm(t):
    return t.strftime('%H:%M')


def _heure_murale(maintenant):
    return maintenant.time() if isinstance(maintenant, datetime) else maintenant


def types_permis(porte):
    """Types de jetons que la porte lit (§1.8) ; None = tous."""
    return TYPES_CAPTURE if porte == 'capture' else None


def retirer_ignores(cands, ignorer, texte):
    """Retire les jetons que l'utilisateur a annulés (×) : `{type, source}`."""
    if not ignorer:
        return list(cands)
    refus = {(i['type'], i['source']) for i in ignorer}
    return [c for c in cands if (c.type, texte[c.debut:c.fin]) not in refus]


def lire(texte, ctx):
    """Jetons retenus et alertes de lecture pour `texte` (grammaire seule, sans assemblage)."""
    masque = masquer_guillemets(texte)
    bases, rejets = candidats(
        masque, texte, ctx, motifs=MOTIFS_LUS, registre=REGISTRE,
        types=types_permis(ctx.porte))
    bases = filtrer_contexte(retirer_ignores(bases, ctx.ignorer, texte), masque)
    composes = composer_echeances(masque, bases)
    retenus, doubles = choisir(bases + retirer_ignores(composes, ctx.ignorer, texte))
    alertes = list(rejets) + doubles
    for c in retenus:
        alertes.extend(c.alertes)
    return retenus, alertes


MOTIFS_LUS = MOTIFS
REGISTRE = dict(CONVERTISSEURS)


# ---------------------------------------------------------------- assembler

def _passee(t, ctx):
    return t <= _heure_murale(ctx.maintenant)


def _jour_pour_heure(t, ctx, alertes):
    """Heure seule : aujourd'hui si elle est à venir, sinon demain (+ `heure_passee`)."""
    if _passee(t, ctx):
        alertes.append(AlerteSaisie.HEURE_PASSEE.value)
        return ctx.aujourdhui + timedelta(days=1)
    return ctx.aujourdhui


def _poser_jour(champs, alertes, par_type, ctx):
    jour = par_type.get('jour')
    if jour is not None:
        champs['jour_prevu'] = jour.valeur.isoformat()


def _heure_avec_moment(heure, moment):
    """« ce soir 9h » : un moment après-midi/soir ajoute 12 h à une heure 1-11 (§1.4)."""
    t = heure.en_time()
    if moment is not None and moment[0] in ('apres_midi', 'soir') and 1 <= heure.h <= 11 \
            and not heure.explicite:
        return heure.en_time(12)
    return t


def _poser_heure_moment(champs, alertes, par_type, ctx):
    heure, moment = par_type.get('heure'), par_type.get('moment')
    cle_moment = moment.valeur if moment is not None else None
    if heure is None:
        if moment is not None:
            champs['moment'] = cle_moment[0]
            if cle_moment[1] and 'jour_prevu' not in champs:
                champs['jour_prevu'] = ctx.aujourdhui.isoformat()
        return
    t = _heure_avec_moment(heure.valeur, cle_moment)
    champs['heure_debut'] = _hhmm(t)
    champs['moment'] = moment_de(t)
    if 'jour_prevu' not in champs:
        if cle_moment is not None and cle_moment[1]:
            jour = ctx.aujourdhui
            if _passee(t, ctx):
                alertes.append(AlerteSaisie.HEURE_PASSEE.value)
        else:
            jour = _jour_pour_heure(t, ctx, alertes)
        champs['jour_prevu'] = jour.isoformat()
    elif champs['jour_prevu'] == ctx.aujourdhui.isoformat() and _passee(t, ctx):
        alertes.append(AlerteSaisie.HEURE_PASSEE.value)


def _poser_echeance(champs, alertes, par_type, ctx):
    ech = par_type.get('echeance')
    if ech is None:
        return
    jour, heure = ech.valeur
    t = heure.en_time() if heure is not None else None
    if jour is None:
        jour = _jour_pour_heure(t, ctx, alertes)
    champs['echeance'] = jour.isoformat()
    if t is not None:
        champs['echeance_heure'] = _hhmm(t)


def _poser_duree(champs, alertes, par_type, ctx):
    duree = par_type.get('duree')
    if duree is not None:
        champs['estimation_minutes'] = duree.valeur


def _poser_priorite(champs, alertes, par_type, ctx):
    priorite = par_type.get('priorite')
    champs['priorite'] = priorite.valeur if priorite is not None else 0


POSEURS = (_poser_jour, _poser_heure_moment, _poser_echeance, _poser_duree, _poser_priorite)


def assembler(retenus, ctx):
    """Dérivations de §1.6 dans l'ordre : `(champs, alertes)` à partir des jetons retenus."""
    par_type = {}
    for c in retenus:
        par_type.setdefault(c.type, c)
    champs, alertes = {}, []
    for poseur in POSEURS:
        poseur(champs, alertes, par_type, ctx)
    return champs, alertes


# ------------------------------------------------------------- sortie publique

def _valeur_echeance(valeur):
    jour, heure = valeur
    return {'jour': jour.isoformat() if jour else None,
            'heure': _hhmm(heure.en_time()) if heure else None}


def _libelle_echeance(valeur):
    jour, heure = valeur
    morceaux = ['échéance']
    if jour is not None:
        morceaux.append(libelle_jour(jour))
    if heure is not None:
        morceaux.append(('· ' if jour is not None else '') + _hhmm(heure.en_time()))
    return ' '.join(morceaux)


def _valeur_publique(c):
    """Valeur sérialisable d'un jeton (dates ISO, heures « HH:MM »)."""
    if c.type == 'jour':
        return c.valeur.isoformat()
    if c.type == 'heure':
        return _hhmm(c.valeur.en_time())
    if c.type == 'moment':
        return c.valeur[0]
    if c.type == 'echeance':
        return _valeur_echeance(c.valeur)
    return c.valeur


def _libelle_public(c):
    return _libelle_echeance(c.valeur) if c.type == 'echeance' else c.libelle


def jeton_public(c, texte):
    return {'type': c.type, 'source': texte[c.debut:c.fin], 'debut': c.debut, 'fin': c.fin,
            'valeur': _valeur_publique(c), 'libelle': _libelle_public(c)}


def titre_de(texte, retenus):
    """Texte original moins les jetons retenus, espaces fusionnés, bords rognés."""
    morceaux, pos = [], 0
    for c in retenus:
        morceaux.append(texte[pos:c.debut])
        pos = c.fin
    morceaux.append(texte[pos:])
    return ' '.join(''.join(morceaux).split())


def _erreurs_titre(titre):
    if not titre:
        return {'titre': [MESSAGE_TITRE_VIDE]}
    if len(titre) > TITRE_MAX:
        return {'titre': [MESSAGE_TITRE_LONG]}
    return {}


def _sans_doublons(codes):
    return tuple(dict.fromkeys(codes))


def analyser(texte, aujourdhui, maintenant, projets=(), sections=(), etiquettes=(),
             porte='rapide', ignorer=(), est_ouvre=None):
    """Lit une ligne de saisie rapide.

    `aujourdhui` (date) et `maintenant` (heure murale, `time` ou `datetime`)
    sont fournis par l'appelant. `projets` (`ProjetConnu`), `sections`
    `(projet_id, section_id, nom)`, `etiquettes` `(id, nom)` décrivent ce qui
    existe déjà ; `ignorer` = `[{type, source}]` (effet du × sur une puce).
    """
    ctx = ContexteSaisie(
        aujourdhui=aujourdhui, maintenant=_heure_murale(maintenant), porte=porte,
        projets=tuple(projets), sections=tuple(sections), etiquettes=tuple(etiquettes),
        ignorer=tuple(ignorer), est_ouvre=est_ouvre)
    retenus, alertes_lecture = lire(texte, ctx)
    champs, alertes = assembler(retenus, ctx)
    titre = titre_de(texte, retenus)
    return Analyse(
        titre=titre, jetons=tuple(jeton_public(c, texte) for c in retenus), champs=champs,
        alertes=_sans_doublons(alertes_lecture + alertes), erreurs=_erreurs_titre(titre))
