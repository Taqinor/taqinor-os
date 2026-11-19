"""Analyseur de saisie rapide (reference/regles.md §1.5-§1.9) — pur, sans Django ni base.

`analyser(texte, aujourdhui, maintenant, …)` lit UNE ligne et rend ce qui a été
compris (`champs`) ET où dans le texte (`jetons[].debut/fin`, pour surligner),
le titre restant et les alertes. Une phrase que la grammaire ne comprend pas
reste un titre intact : jamais une exception. « Aujourd'hui » et « maintenant »
sont des paramètres, jamais l'horloge.

`grammaire.py` porte les motifs de jour, heure, moment, échéance, durée et
priorité ; ce module ajoute les motifs de projet, étape, étiquette, « en
réserve », récurrence et rappel, assemble les champs (§1.6) et applique les
portes (§1.8) : `rapide` lit tout, `capture` ne lit que sept types et un projet
EXISTANT.
"""
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from apps.taches.choix import AlerteSaisie, Frequence, ModeRecurrence
from apps.taches.moteur.recurrence import (
    RegleRecurrencePure, libelle_regle, premiere_occurrence)
from apps.taches.saisie.grammaire import (
    CONVERTISSEURS, JOURS_SEMAINE, MOTIFS, TYPES_CAPTURE, Candidat, ContexteSaisie, Lu, Motif,
    _heure_apres, candidats, choisir, composer_echeances, filtrer_contexte, libelle_jour,
    masquer_guillemets, moment_de)
from apps.taches.saisie.normalisation import cle_nom

TITRE_MAX = 280
MESSAGE_TITRE_VIDE = 'Le titre est vide une fois la date et le projet retirés.'
MESSAGE_TITRE_LONG = 'Le titre est trop long : 280 caractères au plus.'
PRIORITE_NOUVEAU_PROJET = 2  # « Moyenne » (A16-M3)
STATUTS_OUVERTS = ('actif', 'en_pause')
INTERVALLE_MAX = 99


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


# ------------------------------------------------- convertisseurs (§1.3, §1.9)

def conv_quelque_jour(m, ctx, texte):
    return Lu(True, 'Plus tard')


def _nom_du_mot(m, texte):
    """Nom d'un `#projet`, `/étape` ou `%étiquette` : texte original, `_` = espace."""
    return texte[m.start() + 1:m.end()].replace('_', ' ')


_SEPARATEURS_NOM = re.compile(r'[\s\-_]+')


def _debute_un_mot(cle, nom):
    """`cle` est le DÉBUT d'un mot du nom, lu jusqu'au bout du nom (« sal » → « Salon Solaire Expo », « salonsol »
    aussi, « solaire » aussi ; « alon » non) — par `cle_nom`, donc sans accents, casse, espaces ni `_`."""
    mots = [m for m in _SEPARATEURS_NOM.split(nom) if m]
    return any(cle_nom(''.join(mots[i:])).startswith(cle) for i in range(len(mots)))


def _ouverts_par_debut(cle, ctx):
    """R2-003 — sans égalité : les projets OUVERTS dont un mot commence par `cle`, par rang."""
    if not cle:
        return []
    return sorted((p for p in ctx.projets if p.statut in STATUTS_OUVERTS and _debute_un_mot(cle, p.nom)),
                  key=lambda p: p.rang)


def resoudre_projet(nom, ctx, *, par_debut=False):
    """`Lu` du projet nommé `nom` : connu, archivé ou nouveau ; None si la porte l'interdit.

    `par_debut` (le `#mot` de la saisie, R2-003) : sans projet de ce nom exact, un projet OUVERT dont un mot
    commence par `nom` le prend (« #Salon » → « Salon Solaire Expo ») au lieu d'en créer un en double ; plusieurs →
    le premier par rang + `plusieurs_projets`. L'égalité reste prioritaire ; la porte `capture` ne lit jamais par début.
    """
    cle = cle_nom(nom)
    trouves = sorted((p for p in ctx.projets if cle_nom(p.nom) == cle), key=lambda p: p.rang)
    ouverts = [p for p in trouves if p.statut in STATUTS_OUVERTS]
    if not trouves and par_debut and ctx.porte != 'capture':
        ouverts = _ouverts_par_debut(cle, ctx)
    if ouverts:
        p = ouverts[0]
        alertes = (AlerteSaisie.PLUSIEURS_PROJETS.value,) if len(ouverts) > 1 else ()
        return Lu({'id': p.id, 'nom': p.nom, 'nouveau': False}, f'● {p.nom}', alertes)
    if trouves:
        p = trouves[0]
        return Lu({'id': p.id, 'nom': p.nom, 'nouveau': False, 'archive': True},
                  f'Projet archivé : {p.nom}', (AlerteSaisie.PROJET_ARCHIVE.value,))
    if ctx.porte == 'capture':
        return None
    return Lu({'id': None, 'nom': nom, 'nouveau': True, 'priorite': PRIORITE_NOUVEAU_PROJET},
              f'Nouveau projet : {nom}')


def conv_projet(m, ctx, texte):
    return resoudre_projet(_nom_du_mot(m, texte), ctx, par_debut=True)


def conv_section(m, ctx, texte):
    nom = _nom_du_mot(m, texte)
    return Lu({'nom': nom}, f'Étape : {nom}')


def conv_etiquette(m, ctx, texte):
    nom = _nom_du_mot(m, texte)
    cle = cle_nom(nom)
    existante = next((e for e in ctx.etiquettes if cle_nom(e[1]) == cle), None)
    if existante is not None:
        return Lu({'id': existante[0], 'nom': existante[1]}, existante[1])
    return Lu({'nom': nom}, nom)


# ---------------------------------------------------------- récurrence (§1.3)

_RANGS = {
    'premier': 1, 'deuxieme': 2, 'troisieme': 3, 'quatrieme': 4, 'dernier': -1,
    'first': 1, 'second': 2, 'third': 3, 'fourth': 4, 'last': -1}


def _masque_jours(texte_jours):
    """Masque `'1001000'` des noms de jour trouvés dans `texte_jours` (« lundis et jeudis »)."""
    trouves = {JOURS_SEMAINE[mot] for mot in re.findall('|'.join(JOURS_SEMAINE), texte_jours)}
    return ''.join('1' if i in trouves else '0' for i in range(7))


def _intervalle(m):
    """Intervalle écrit (1 si absent) ; None s'il sort de 1-99 (non lu)."""
    valeur = m.groupdict().get('n')
    n = int(valeur) if valeur else 1
    return n if 1 <= n <= INTERVALLE_MAX else None


def _mode(m):
    """« après fait » ou `every!` → `apres_fait`, sinon `calendrier`."""
    groupes = m.groupdict()
    apres = groupes.get('af') or groupes.get('bang')
    return (ModeRecurrence.APRES_FAIT if apres else ModeRecurrence.CALENDRIER).value


def regle_en_champ(regle):
    """Règle → dict sérialisable (champ `recurrence` d'une LIGNE)."""
    return {'frequence': str(regle.frequence), 'intervalle': regle.intervalle,
            'jours_semaine': regle.jours_semaine, 'jour_du_mois': regle.jour_du_mois,
            'rang_dans_mois': regle.rang_dans_mois, 'mode': str(regle.mode),
            'date_debut': regle.date_debut.isoformat()}


def _lire_regle(m, ctx, frequence, **champs):
    n = _intervalle(m)
    if n is None:
        return None
    regle = RegleRecurrencePure(
        frequence=frequence.value, date_debut=ctx.aujourdhui, intervalle=n,
        mode=_mode(m), **champs)
    return Lu(regle, libelle_regle(regle))


def conv_rec_quotidien(m, ctx, texte):
    return _lire_regle(m, ctx, Frequence.QUOTIDIEN)


def conv_rec_jours_ouvres(m, ctx, texte):
    return _lire_regle(m, ctx, Frequence.JOURS_OUVRES)


def conv_rec_hebdo(m, ctx, texte):
    liste = m.groupdict().get('liste')
    if liste:
        masque = _masque_jours(liste)
    else:
        masque = ''.join('1' if i == ctx.aujourdhui.weekday() else '0' for i in range(7))
    return _lire_regle(m, ctx, Frequence.HEBDO, jours_semaine=masque)


def conv_rec_fin_mois(m, ctx, texte):
    return _lire_regle(m, ctx, Frequence.MENSUEL, jour_du_mois=-1)


def conv_rec_rang(m, ctx, texte):
    masque = _masque_jours(m.group('jour'))
    return _lire_regle(m, ctx, Frequence.MENSUEL, jours_semaine=masque,
                       rang_dans_mois=_RANGS[m.group('rang')])


def _jour_du_mois_ecrit(m, ctx):
    """Quantième écrit ; sans quantième, celui du jour en mode calendrier (E16)."""
    ecrit = m.groupdict().get('j')
    if ecrit in ('dernier', 'last'):
        return -1
    if ecrit:
        return int(ecrit) if 1 <= int(ecrit) <= 31 else 0
    return None if _mode(m) == ModeRecurrence.APRES_FAIT.value else ctx.aujourdhui.day


def conv_rec_mensuel(m, ctx, texte):
    jour = _jour_du_mois_ecrit(m, ctx)
    if jour == 0:
        return None
    return _lire_regle(m, ctx, Frequence.MENSUEL, jour_du_mois=jour)


def conv_rec_annuel(m, ctx, texte):
    return _lire_regle(m, ctx, Frequence.ANNUEL)


CONVERTISSEURS_ANALYSEUR = {
    'quelque_jour': conv_quelque_jour,
    'projet': conv_projet,
    'section': conv_section,
    'etiquette': conv_etiquette,
    'rec_quotidien': conv_rec_quotidien,
    'rec_jours_ouvres': conv_rec_jours_ouvres,
    'rec_hebdo': conv_rec_hebdo,
    'rec_fin_mois': conv_rec_fin_mois,
    'rec_rang': conv_rec_rang,
    'rec_mensuel': conv_rec_mensuel,
    'rec_annuel': conv_rec_annuel,
}

_DOW = '|'.join(JOURS_SEMAINE)
_LISTE = rf'(?:{_DOW})s?(?:\s*(?:,|et|and)\s*(?:{_DOW})s?)*'
_EV = r'(?P<ev>every(?P<bang>!)?|chaque|tous\s+les|toutes\s+les)'
_AF = r'(?P<af>\s+apres\s+(?:avoir\s+)?fait)?'
_NOM = r'(?<!\S){}(?=[^\W\d_])[\w-]*'


def _m(type_, regex, convertisseur):
    return Motif(type_, re.compile(regex), convertisseur)


MOTIFS_ANALYSEUR = (
    _m('quelque_jour', r"(?:(?<!\w)un\s+jour|(?<!\w)en\s+reserve)(?=[\s.!?,;]*$)", 'quelque_jour'),
    _m('quelque_jour', r'(?<!\w)someday(?!\w)', 'quelque_jour'),
    _m('projet', _NOM.format('#'), 'projet'),
    _m('section', _NOM.format('/'), 'section'),
    _m('etiquette', _NOM.format('%'), 'etiquette'),
    # récurrence : une famille par motif, un convertisseur par famille
    _m('recurrence', rf'(?<!\w){_EV}\s+(?:(?P<n>\d+)\s+)?(?:jours?|days?)(?!\w)' + _AF,
       'rec_quotidien'),
    _m('recurrence', rf'(?<!\w)(?:{_EV}\s+(?:(?P<n>\d+)\s+)?(?:jours?\s+(?:ouvres?|ouvrables?'
       r'|travailles?)|weekdays?|(?:working|business)\s+days?)|en\s+semaine)(?!\w)' + _AF,
       'rec_jours_ouvres'),
    _m('recurrence', rf'(?<!\w){_EV}\s+(?P<liste>{_LISTE})(?!\w)' + _AF, 'rec_hebdo'),
    _m('recurrence', rf'(?<!\w){_EV}\s+(?:(?P<n>\d+)\s+)?(?:semaines?|weeks?)'
       rf'(?:\s+(?:le|on)\s+(?P<liste>{_LISTE}))?(?!\w)' + _AF, 'rec_hebdo'),
    _m('recurrence', r'(?<!\w)(?:chaque\s+fin\s+de\s+mois|every(?P<bang>!)?\s+end\s+of\s+'
       r'(?:the\s+)?month)(?!\w)' + _AF, 'rec_fin_mois'),
    _m('recurrence', rf'(?<!\w){_EV}\s+(?P<rang>premier|deuxieme|troisieme|quatrieme|dernier'
       rf'|first|second|third|fourth|last)\s+(?P<jour>{_DOW})'
       r'(?:\s+du\s+mois|\s+of\s+(?:the\s+)?month)?(?!\w)' + _AF, 'rec_rang'),
    _m('recurrence', rf'(?<!\w){_EV}\s+(?:(?P<n>\d+)\s+)?(?:mois|months?)'
       r'(?:\s+(?:le|on\s+the|on|the)\s+(?P<j>\d{1,2}|dernier|last)(?:er|st|nd|rd|th)?)?(?!\w)'
       + _AF, 'rec_mensuel'),
    _m('recurrence', r'(?<!\w)(?:chaque\s+(?:annee|an)|tous\s+les\s+(?:(?P<n>\d+)\s+)?ans)(?!\w)'
       + _AF, 'rec_annuel'),
    _m('recurrence', r'(?<!\w)every(?P<bang>!)?\s+(?:(?P<n>\d+)\s+)?years?(?!\w)' + _AF,
       'rec_annuel'),
)

MOTIFS_LUS = MOTIFS + MOTIFS_ANALYSEUR
REGISTRE = {**CONVERTISSEURS, **CONVERTISSEURS_ANALYSEUR}


# ------------------------------------------------------------ rappel composé

_DECLENCHEUR_RAPPEL = re.compile(r'(?<!\w)(?:rappelle-moi|rappel|remind\s+me|remind)\s+')


def _rappel_depuis(m, masque, bases):
    pos = m.end()
    heures = [c for c in bases if c.type == 'heure']
    jours = [c for c in bases if c.type == 'jour' and c.debut == pos]
    if jours:
        jour = max(jours, key=lambda c: c.fin)
        heure = _heure_apres(masque, jour.fin, heures)
        alertes = jour.alertes
    else:
        jour, alertes = None, ()
        heure = next((c for c in heures if c.debut == pos), None)
    if heure is None:
        return None
    return Candidat(m.start(), heure.fin, 'rappel',
                    (jour.valeur if jour else None, heure.valeur), alertes=alertes)


def composer_rappels(masque, bases):
    """« rappel / rappelle-moi / remind [me] » + [jour] + heure → un jeton `rappel`."""
    trouves = (_rappel_depuis(m, masque, bases) for m in _DECLENCHEUR_RAPPEL.finditer(masque))
    return [c for c in trouves if c is not None]


# ------------------------------------------------------- « projet <nom> » en tête

_EN_TETE_PROJET = re.compile(r'\s*(?:projet|project)\s+')


def projet_en_tete(masque, texte, ctx):
    """Capture : « projet <nom> » EN TÊTE, le plus long nom de projet existant qui suit (A1)."""
    m = _EN_TETE_PROJET.match(masque)
    if m is None or not ctx.projets:
        return None
    debut = m.start() + len(m.group()) - len(m.group().lstrip())
    mots = list(re.finditer(r'\S+', masque[m.end():]))
    longueur_max = max(len(p.nom.split()) for p in ctx.projets)
    for k in range(min(len(mots), longueur_max), 0, -1):
        fin = m.end() + mots[k - 1].end()
        lu = resoudre_projet(texte[m.end():fin], ctx)
        if lu is not None and not lu.valeur['nouveau']:
            return Candidat(debut, fin, 'projet', lu.valeur, lu.libelle, tuple(lu.alertes))
    return None


# ------------------------------------------------- « #Nom avec espaces » (R3-047)

_DIESE = re.compile(r'(?<!\S)#(?=[^\W\d_])')
_MOT = re.compile(r'\S+')
_PONCTUATION_FINALE = '.,;:!?)»"'


def _fins_possibles(segment, mots, k):
    """Fin (dans `segment`) du k-ième mot, brute puis sans sa ponctuation finale (« expo, » → « expo »)."""
    dernier = mots[k - 1]
    nette = dernier.start() + len(dernier.group().rstrip(_PONCTUATION_FINALE))
    return (dernier.end(), nette) if nette != dernier.end() else (dernier.end(),)


def projets_nommes_en_entier(masque, texte, ctx):
    """R3-047 — après `#`, le plus long nom de projet EXISTANT de deux mots ou plus, écrit avec ses espaces (le choix
    de la liste `#` l'insère ainsi : « #Chantier Benali 9 kWc »), comparé par `cle_nom`. Un nom inconnu n'est jamais
    lu au-delà de son premier mot (motif `#mot`, qui reste le seul pour un mot seul ou un nouveau projet)."""
    longueur_max = max((len(p.nom.split()) for p in ctx.projets), default=0)
    if longueur_max < 2:
        return []
    cles = {cle_nom(p.nom) for p in ctx.projets if len(p.nom.split()) >= 2}
    trouves = []
    for diese in _DIESE.finditer(masque):
        segment = masque[diese.end():]
        mots = []
        for mot in _MOT.finditer(segment):
            if mot.group()[0] in '#/%!':
                break
            mots.append(mot)
        for k in range(min(len(mots), longueur_max), 1, -1):
            fin = next((diese.end() + f for f in _fins_possibles(segment, mots, k)
                        if cle_nom(texte[diese.end():diese.end() + f]) in cles), None)
            if fin is None:
                continue
            lu = resoudre_projet(texte[diese.end():fin], ctx)
            if lu is not None and not lu.valeur['nouveau']:
                trouves.append(Candidat(diese.start(), fin, 'projet', lu.valeur, lu.libelle, tuple(lu.alertes)))
            break
    return trouves


# --------------------------------------------------------------------- lecture

def types_permis(porte):
    """Types de jetons que la porte lit (§1.8) ; None = tous."""
    return TYPES_CAPTURE if porte == 'capture' else None


def retirer_ignores(cands, ignorer, texte):
    """Retire les jetons que l'utilisateur a annulés (×) : `{type, source}`."""
    if not ignorer:
        return list(cands)
    refus = {(i['type'], i['source']) for i in ignorer}
    return [c for c in cands if (c.type, texte[c.debut:c.fin]) not in refus]


def _composes(masque, texte, bases, ctx):
    """Jetons composés de plusieurs candidats : échéance, et rappel (hors capture)."""
    composes = composer_echeances(masque, bases)
    if ctx.porte != 'capture':
        composes += composer_rappels(masque, bases)
    return retirer_ignores(composes, ctx.ignorer, texte)


def lire(texte, ctx):
    """Jetons retenus et alertes de lecture pour `texte` (grammaire seule, sans assemblage)."""
    masque = masquer_guillemets(texte)
    bases, rejets = candidats(
        masque, texte, ctx, motifs=MOTIFS_LUS, registre=REGISTRE, types=types_permis(ctx.porte))
    if ctx.porte == 'capture':
        en_tete = projet_en_tete(masque, texte, ctx)
        bases += [en_tete] if en_tete is not None else []
    bases += projets_nommes_en_entier(masque, texte, ctx)
    bases = filtrer_contexte(retirer_ignores(bases, ctx.ignorer, texte), masque)
    retenus, doubles = choisir(bases + _composes(masque, texte, bases, ctx))
    alertes = list(rejets) + doubles
    for c in retenus:
        alertes.extend(c.alertes)
    return retenus, alertes


# ---------------------------------------------------------------- assembler

def _passee(t, ctx):
    return t <= _heure_murale(ctx.maintenant)


def _jour_pour_heure(t, ctx, alertes):
    """Heure seule : aujourd'hui si elle est à venir, sinon demain (+ `heure_passee`)."""
    if _passee(t, ctx):
        alertes.append(AlerteSaisie.HEURE_PASSEE.value)
        return ctx.aujourdhui + timedelta(days=1)
    return ctx.aujourdhui


def _poser_recurrence(champs, alertes, par_type, ctx):
    rec = par_type.get('recurrence')
    if rec is None:
        return
    champs['recurrence'] = regle_en_champ(rec.valeur)
    premiere = premiere_occurrence(rec.valeur, ctx.est_ouvre)
    if premiere is not None:
        champs['jour_prevu'] = premiere.isoformat()


def _poser_jour(champs, alertes, par_type, ctx):
    jour = par_type.get('jour')
    if jour is not None:
        champs['jour_prevu'] = jour.valeur.isoformat()


def _heure_avec_moment(heure, moment):
    """« ce soir 9h » : un moment après-midi/soir ajoute 12 h à une heure 1-11 (§1.4)."""
    if (moment is not None and moment[0] in ('apres_midi', 'soir') and 1 <= heure.h <= 11
            and not heure.explicite):
        return heure.en_time(12)
    return heure.en_time()


def _jour_de_l_heure(t, moment, ctx, alertes):
    """Jour d'une heure sans jour : « ce/cet/this/tonight » posent J, sinon J ou J+1 (§1.6.2)."""
    if moment is not None and moment[1]:
        if _passee(t, ctx):
            alertes.append(AlerteSaisie.HEURE_PASSEE.value)
        return ctx.aujourdhui
    return _jour_pour_heure(t, ctx, alertes)


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
        champs['jour_prevu'] = _jour_de_l_heure(t, cle_moment, ctx, alertes).isoformat()
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


def _poser_rappel(champs, alertes, par_type, ctx):
    """§1.6.5 : date propre, sinon ancré sur `jour_prevu`, sinon J ou J+1 (et pose `jour_prevu`)."""
    rappel = par_type.get('rappel')
    if rappel is None:
        return
    jour, heure = rappel.valeur
    t = _hhmm(heure.en_time())
    if jour is None and 'jour_prevu' in champs:
        champs['rappel'] = {'ancre': 'jour_prevu', 'decalage_jours': 0, 'heure': t}
        return
    if jour is None:
        jour = ctx.aujourdhui + timedelta(days=1 if _passee(heure.en_time(), ctx) else 0)
        champs['jour_prevu'] = jour.isoformat()
    champs['rappel'] = {'jour': jour.isoformat(), 'heure': t}


def _poser_projet(champs, alertes, par_type, ctx):
    projet = par_type.get('projet')
    if projet is None:
        return
    v = projet.valeur
    if v.get('archive'):
        return  # « Projet archivé » : la tâche reste À trier
    if v['nouveau']:
        champs['nouveau_projet'] = {'nom': v['nom'], 'priorite': v['priorite']}
    else:
        champs['projet_id'] = v['id']


def _poser_section(champs, alertes, par_type, ctx):
    section = par_type.get('section')
    if section is None:
        return
    nom = section.valeur['nom']
    cle, projet_id = cle_nom(nom), champs.get('projet_id')
    existante = next((sid for pid, sid, n in ctx.sections
                      if pid == projet_id and cle_nom(n) == cle), None)
    if projet_id is not None and existante is not None:
        champs['section_id'] = existante
    else:
        champs['nouvelle_section'] = {'nom': nom}


def _poser_etiquettes(champs, alertes, par_type, ctx):
    lues, vues = [], set()
    for c in par_type.get('etiquettes', ()):
        cle = cle_nom(c.valeur['nom'])
        if cle not in vues:
            vues.add(cle)
            lues.append(c.valeur['id'] if 'id' in c.valeur else {'nom': c.valeur['nom']})
    if lues:
        champs['etiquettes'] = lues


def _poser_quelque_jour(champs, alertes, par_type, ctx):
    if par_type.get('quelque_jour') is not None:
        champs['quelque_jour'] = True


POSEURS = (
    _poser_recurrence, _poser_jour, _poser_heure_moment, _poser_echeance, _poser_duree,
    _poser_priorite, _poser_rappel, _poser_projet, _poser_section, _poser_etiquettes,
    _poser_quelque_jour)


def _ecarter_jours_si_recurrence(retenus, alertes):
    """La récurrence prime : un jeton `jour` reste du texte, avec `deux_jour` (§1.6.1)."""
    if not any(c.type == 'recurrence' for c in retenus):
        return retenus
    jours = [c for c in retenus if c.type == 'jour']
    if jours:
        alertes.append('deux_jour')
    return [c for c in retenus if c.type != 'jour']


def assembler(retenus, ctx):
    """Dérivations de §1.6 dans l'ordre : `(retenus, champs, alertes)` finaux."""
    alertes = []
    retenus = _ecarter_jours_si_recurrence(retenus, alertes)
    par_type = {}
    for c in retenus:
        par_type.setdefault(c.type, c)
    par_type['etiquettes'] = [c for c in retenus if c.type == 'etiquette']
    champs = {}
    for poseur in POSEURS:
        poseur(champs, alertes, par_type, ctx)
    return retenus, champs, alertes


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


def _valeur_rappel(valeur):
    jour, heure = valeur
    return {'jour': jour.isoformat() if jour else None, 'heure': _hhmm(heure.en_time())}


def _libelle_rappel(valeur):
    jour, heure = valeur
    return ' '.join(['Rappel'] + ([libelle_jour(jour)] if jour else []) + [_hhmm(heure.en_time())])


_VALEURS_PUBLIQUES = {
    'jour': date.isoformat,
    'heure': lambda v: _hhmm(v.en_time()),
    'moment': lambda v: v[0],
    'echeance': _valeur_echeance,
    'rappel': _valeur_rappel,
    'recurrence': regle_en_champ,
}
_LIBELLES_CALCULES = {'echeance': _libelle_echeance, 'rappel': _libelle_rappel}


def jeton_public(c, texte):
    """Jeton tel que l'API le montre : type, source, positions, valeur sérialisable, libellé."""
    valeur = _VALEURS_PUBLIQUES.get(c.type, lambda v: v)(c.valeur)
    libelle = _LIBELLES_CALCULES.get(c.type, lambda v: c.libelle)(c.valeur)
    return {'type': c.type, 'source': texte[c.debut:c.fin], 'debut': c.debut, 'fin': c.fin,
            'valeur': valeur, 'libelle': libelle}


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
    existe déjà ; `ignorer` = `[{type, source}]` (effet du × sur une puce) ;
    `porte` = `rapide` ou `capture` ; `est_ouvre(date)` sert la récurrence
    « jours ouvrés » (lundi-vendredi à défaut).
    """
    ctx = ContexteSaisie(
        aujourdhui=aujourdhui, maintenant=_heure_murale(maintenant), porte=porte,
        projets=tuple(projets), sections=tuple(sections), etiquettes=tuple(etiquettes),
        ignorer=tuple(ignorer), est_ouvre=est_ouvre)
    retenus, alertes_lecture = lire(texte, ctx)
    retenus, champs, alertes = assembler(retenus, ctx)
    titre = titre_de(texte, retenus)
    return Analyse(
        titre=titre, jetons=tuple(jeton_public(c, texte) for c in retenus), champs=champs,
        alertes=_sans_doublons(alertes_lecture + alertes), erreurs=_erreurs_titre(titre))


def classer_capture(analyse):
    """Où atterrit une capture (§1.8) : `journee` si un jour est posé, `projet`, sinon `a_trier`.

    Une échéance seule laisse la tâche dans À trier (invariant 1).
    """
    if 'jour_prevu' in analyse.champs:
        return 'journee'
    return 'projet' if 'projet_id' in analyse.champs else 'a_trier'
