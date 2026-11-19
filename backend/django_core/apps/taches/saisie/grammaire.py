"""Grammaire de la saisie rapide (reference/regles.md §1.2-§1.5) — pur, sans Django ni base.

Tout se lit dans la copie NORMALISÉE (`normaliser` : minuscules, sans accents,
même longueur que l'original) dont les guillemets sont masqués : une position
trouvée ici vaut aussi dans le texte original.

Le module expose la TABLE des motifs (`MOTIFS`), la recherche des candidats
(`candidats`), les règles de contexte (`filtrer_contexte`), les échéances
composées (`composer_echeances`), le choix sans chevauchement (`choisir`) et les
convertisseurs de `jour`, `heure`, `moment`, `echeance` et `duree`. Les autres
types (projet, étape, étiquette, priorité, récurrence, rappel, « pour plus tard »)
sont convertis par `analyseur.py`, qui complète `CONVERTISSEURS`.

Un convertisseur reçoit `(m, ctx, texte)` — `m` est le résultat de la recherche
dans la copie masquée, `texte` l'original — et rend `Lu` (jeton lu), `Rejet`
(le texte reste dans le titre, avec une alerte) ou `None` (rien de lu).
"""
import re
from collections import namedtuple
from dataclasses import dataclass, field
from datetime import date, time, timedelta

from apps.taches.choix import AlerteSaisie, alerte_deux
from apps.taches.saisie.dates_pures import (
    ajouter_mois_borne, fin_de_mois, prochain_jour_semaine)
from apps.taches.saisie.normalisation import normaliser

DUREE_MIN, DUREE_MAX = 5, 960
DUREE_POUR_MAX = 360  # « pour / for » + durée : formes ≤ 6 h
ETIQUETTE = 'etiquette'  # seul type qui peut être lu plusieurs fois

# Ordre de départage à position et longueur égales (§1.5).
ORDRE_TYPES = (
    'recurrence', 'rappel', 'echeance', 'duree', 'heure', 'jour', 'moment',
    'quelque_jour', 'projet', 'section', 'priorite', ETIQUETTE)

# Types lus par chaque porte (§1.8) : la capture n'en lit que sept.
TYPES_CAPTURE = frozenset(
    {'jour', 'heure', 'moment', 'echeance', 'priorite', 'duree', 'projet'})

JOURS_SEMAINE = {
    'lundi': 0, 'mardi': 1, 'mercredi': 2, 'jeudi': 3, 'vendredi': 4,
    'samedi': 5, 'dimanche': 6,
    'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3, 'friday': 4,
    'saturday': 5, 'sunday': 6}
MOIS = {
    'janvier': 1, 'janv': 1, 'fevrier': 2, 'fevr': 2, 'mars': 3, 'avril': 4,
    'avr': 4, 'mai': 5, 'juin': 6, 'juillet': 7, 'juil': 7, 'aout': 8,
    'septembre': 9, 'sept': 9, 'octobre': 10, 'oct': 10, 'novembre': 11,
    'nov': 11, 'decembre': 12, 'dec': 12, 'january': 1, 'jan': 1,
    'february': 2, 'feb': 2, 'march': 3, 'mar': 3, 'april': 4, 'apr': 4,
    'may': 5, 'june': 6, 'jun': 6, 'july': 7, 'jul': 7, 'august': 8,
    'aug': 8, 'september': 9, 'sep': 9, 'october': 10, 'november': 11,
    'december': 12}
_JOURS_ABREGES = ('lun.', 'mar.', 'mer.', 'jeu.', 'ven.', 'sam.', 'dim.')
_MOIS_ABREGES = (
    'janv.', 'févr.', 'mars', 'avr.', 'mai', 'juin', 'juil.', 'août', 'sept.',
    'oct.', 'nov.', 'déc.')
_MOMENTS_LIBELLES = {'matin': 'Matin', 'apres_midi': 'Après-midi', 'soir': 'Ce soir'}

Lu = namedtuple('Lu', 'valeur libelle alertes', defaults=('', ()))
Rejet = namedtuple('Rejet', 'alerte')
Motif = namedtuple('Motif', 'type regex convertisseur')


@dataclass(frozen=True)
class ProjetConnu:
    """Un projet du propriétaire, tel que la vue le fournit (jamais l'ORM)."""
    id: int
    nom: str
    statut: str = 'actif'
    rang: int = 0


@dataclass(frozen=True)
class ContexteSaisie:
    """Tout ce que l'analyseur sait du monde : jamais l'horloge ni la base."""
    aujourdhui: date
    maintenant: time
    porte: str = 'rapide'
    projets: tuple = ()          # ProjetConnu
    sections: tuple = ()         # (projet_id, section_id, nom)
    etiquettes: tuple = ()       # (etiquette_id, nom)
    ignorer: tuple = ()          # ({type, source}, …) : effet du × d'une puce
    est_ouvre: object = None     # fonction date -> bool (récurrence jours ouvrés)


@dataclass(frozen=True)
class HeureLue:
    """Une heure lue : `explicite` quand elle porte am/pm (pas de +12 h dérivé)."""
    h: int
    m: int = 0
    explicite: bool = False
    midi: bool = False  # « midi / noon » : lu seulement selon `filtrer_contexte`

    def en_time(self, decalage=0):
        return time(self.h + decalage, self.m)


@dataclass(frozen=True)
class Candidat:
    """Un jeton possible : positions dans le texte, valeur déjà convertie."""
    debut: int
    fin: int
    type: str
    valeur: object
    libelle: str = ''
    alertes: tuple = field(default=())


# ---------------------------------------------------------------- libellés

def libelle_jour(d):
    """« mer. 18 nov. » (puce de jeton)."""
    return f'{_JOURS_ABREGES[d.weekday()]} {d.day} {_MOIS_ABREGES[d.month - 1]}'


def libelle_duree(minutes):
    """« 30 min », « 2 h », « 1 h 30 »."""
    heures, reste = divmod(minutes, 60)
    if not heures:
        return f'{reste} min'
    return f'{heures} h' if not reste else f'{heures} h {reste:02d}'


def moment_de(t):
    """Moment dérivé d'une heure (invariant 15) : < 12 h matin, < 18 h après-midi."""
    if t.hour < 12:
        return 'matin'
    return 'apres_midi' if t.hour < 18 else 'soir'


def prochaine_date_sans_annee(jj, mm, aujourdhui):
    """Première date `jj/mm` ≥ `aujourdhui` ; None si ce jour n'existe jamais (31/11)."""
    for annee in range(aujourdhui.year, aujourdhui.year + 9):
        try:
            d = date(annee, mm, jj)
        except ValueError:
            continue
        if d >= aujourdhui:
            return d
    return None


# ------------------------------------------------------- convertisseurs : jour

def conv_jour_relatif(m, ctx, texte):
    mot = m.group('m')
    if mot.startswith('apres'):
        decalage = 2
    else:
        decalage = 1 if mot in ('demain', 'tomorrow') else 0
    d = ctx.aujourdhui + timedelta(days=decalage)
    return Lu(d, libelle_jour(d))


def conv_jour_semaine(m, ctx, texte):
    d = prochain_jour_semaine(ctx.aujourdhui, JOURS_SEMAINE[m.group('j')])
    return Lu(d, libelle_jour(d))


def _fin_de_semaine(j):
    if j.weekday() <= 4:
        return j + timedelta(days=4 - j.weekday())
    return prochain_jour_semaine(j, 4)


def conv_jour_periode(m, ctx, texte):
    j, p = ctx.aujourdhui, m.group('p')
    if 'week-end' in p or 'weekend' in p or 'week end' in p:
        d = j if j.weekday() >= 5 else prochain_jour_semaine(j, 5)
    elif p.startswith(('fin', 'end')):
        d = _fin_de_semaine(j)
    else:
        d = prochain_jour_semaine(j, 0)
    return Lu(d, libelle_jour(d))


# R3-047 — « dans quinze jours » : un nombre de un à trente écrit en lettres (forme normalisée : minuscules, sans
# accents ; trait d'union ou espace entre les mots) vaut le même nombre en chiffres.
_UNITES_LETTRES = ('un', 'deux', 'trois', 'quatre', 'cinq', 'six', 'sept', 'huit', 'neuf')
NOMBRES_EN_LETTRES = {
    **{mot: i for i, mot in enumerate(_UNITES_LETTRES, start=1)}, 'une': 1,
    **{mot: i for i, mot in enumerate(
        ('dix', 'onze', 'douze', 'treize', 'quatorze', 'quinze', 'seize'), start=10)},
    'dix-sept': 17, 'dix-huit': 18, 'dix-neuf': 19, 'vingt': 20, 'vingt et un': 21, 'vingt et une': 21,
    **{f'vingt-{mot}': 20 + i for i, mot in enumerate(_UNITES_LETTRES[1:], start=2)},
    'trente': 30}
_SEPARATEUR_NOMBRE = re.compile(r'[\s-]+')


def _cle_nombre(texte):
    """« vingt-et-un », « vingt et un » et « vingt et-un » ont la même clé (mots séparés par une espace)."""
    return _SEPARATEUR_NOMBRE.sub(' ', texte.strip())


_NOMBRES_PAR_CLE = {_cle_nombre(mot): n for mot, n in NOMBRES_EN_LETTRES.items()}
# les plus longs d'abord : « dix-sept » avant « dix », « vingt et un » avant « vingt », « une » avant « un »
_ALT_NOMBRES_LETTRES = '|'.join(
    r'[\s-]+'.join(cle.split(' ')) for cle in sorted(_NOMBRES_PAR_CLE, key=len, reverse=True))


def _nombre_ecrit(texte):
    """Le nombre d'un décalage : en chiffres, « a/an/one » (R2-006), ou en lettres de un à trente (R3-047)."""
    if texte.isdigit():
        return int(texte)
    if texte in ('a', 'an', 'one'):
        return 1
    return _NOMBRES_PAR_CLE[_cle_nombre(texte)]


def conv_jour_decalage(m, ctx, texte):
    n = _nombre_ecrit(m.group('n'))
    unite = m.group('u')
    if n < 1:
        return None
    try:
        if unite.startswith(('jour', 'day')):
            d = ctx.aujourdhui + timedelta(days=n)
        elif unite.startswith(('semaine', 'week')):
            d = ctx.aujourdhui + timedelta(weeks=n)
        else:
            d = ajouter_mois_borne(ctx.aujourdhui, n)
    except (OverflowError, ValueError):  # au-delà de l'an 9999 : pas une date, la ligne garde son texte
        return None
    return Lu(d, libelle_jour(d))


def _date_lue(jj, mm, annee_txt, ctx):
    """Date `jj/mm[/annee]` lue : `Lu`, ou `Rejet` si elle n'existe pas (IR4)."""
    if not (1 <= mm <= 12 and 1 <= jj <= 31):
        return Rejet(AlerteSaisie.DATE_INVALIDE.value)
    if annee_txt is None:
        d = prochaine_date_sans_annee(jj, mm, ctx.aujourdhui)
        return Lu(d, libelle_jour(d)) if d else Rejet(AlerteSaisie.DATE_INVALIDE.value)
    annee = int(annee_txt)
    annee += 2000 if annee < 100 else 0
    try:
        d = date(annee, mm, jj)
    except ValueError:
        return Rejet(AlerteSaisie.DATE_INVALIDE.value)
    alertes = (AlerteSaisie.DATE_PASSEE.value,) if d < ctx.aujourdhui else ()
    return Lu(d, libelle_jour(d), alertes)


def conv_jour_date_slash(m, ctx, texte):
    return _date_lue(int(m.group('d')), int(m.group('m')), m.group('y'), ctx)


def conv_jour_date_texte(m, ctx, texte):
    return _date_lue(int(m.group('d')), MOIS[m.group('mois')], m.group('y'), ctx)


def conv_jour_date_iso(m, ctx, texte):
    return _date_lue(int(m.group('d')), int(m.group('m')), m.group('y'), ctx)


def conv_jour_fin_mois(m, ctx, texte):
    d = fin_de_mois(ctx.aujourdhui)
    return Lu(d, libelle_jour(d))


def conv_jour_quantieme(m, ctx, texte):
    """R2-006 — « le 25 » : le prochain 25 à partir d'aujourd'hui (ce mois-ci s'il n'est pas passé), sinon rien."""
    jj = int(m.group('d'))
    if not 1 <= jj <= 31:
        return None
    j = ctx.aujourdhui
    for decalage in range(13):
        mois0 = j.month - 1 + decalage
        try:
            d = date(j.year + mois0 // 12, mois0 % 12 + 1, jj)
        except ValueError:
            continue
        if d >= j:
            return Lu(d, libelle_jour(d))
    return None


# ----------------------------------------------------- convertisseurs : heure

_RE_HM = re.compile(r'(\d{1,2})\s*(?:h|heures?|hours?|hrs?)(?:\s*(\d{2}))?')


def _lire_hm(texte_hm):
    """`(heures, minutes | None)` d'un fragment « 15h30 », « 10 h », « 15 heures »."""
    r = _RE_HM.match(texte_hm)
    return int(r.group(1)), (int(r.group(2)) if r.group(2) else None)


def conv_heure_hm(m, ctx, texte):
    """`Nh` nu seulement si 7 ≤ N ≤ 23 ; `NhMM` nu seulement si 5 ≤ N ≤ 23 (IR5) ; « à N h » : tout."""
    h, mi = _lire_hm(m.group('hm'))
    if h > 23 or (mi or 0) > 59:
        return None
    if m.group('a') is None and h < (7 if mi is None else 5):
        return None
    heure = HeureLue(h, mi or 0)
    return Lu(heure, heure.en_time().strftime('%H:%M'))


def conv_heure_colon(m, ctx, texte):
    h, mi = int(m.group('h')), int(m.group('m'))
    if h > 23 or mi > 59:
        return None
    heure = HeureLue(h, mi)
    return Lu(heure, heure.en_time().strftime('%H:%M'))


def conv_heure_ampm(m, ctx, texte):
    h, mi = int(m.group('h')), int(m.group('m') or 0)
    if not (1 <= h <= 12) or mi > 59:
        return None
    h = h % 12 + (12 if m.group('ap') == 'pm' else 0)
    heure = HeureLue(h, mi, explicite=True)
    return Lu(heure, heure.en_time().strftime('%H:%M'))


def conv_heure_midi(m, ctx, texte):
    return Lu(HeureLue(12, 0, midi=True), '12:00')


def conv_heure_ce_midi(m, ctx, texte):
    """R2-006 — « ce midi » : le « ce » lève l'ambiguïté du « midi » nu (§1.4) : 12:00 aujourd'hui."""
    return Lu(HeureLue(12, 0), '12:00')


# ---------------------------------------------------- convertisseurs : moment

def conv_moment_ce(m, ctx, texte):
    """« ce matin », « this evening », « tonight » : posent aussi le jour J."""
    mot = m.group('m')
    cle = 'soir' if ('soir' in mot or 'evening' in mot or 'tonight' in mot) else (
        'apres_midi' if ('apre' in mot or 'afternoon' in mot) else 'matin')
    return Lu((cle, True), _MOMENTS_LIBELLES[cle])


def conv_moment_nu(m, ctx, texte):
    """« matin », « soir »… nus : lus seulement selon `filtrer_contexte` (§1.4)."""
    mot = m.group('m')
    cle = 'soir' if ('soir' in mot or 'evening' in mot) else (
        'apres_midi' if ('apre' in mot or 'afternoon' in mot) else 'matin')  # « aprem » compris (R2-006)
    return Lu((cle, False), _MOMENTS_LIBELLES[cle])


# ----------------------------------------------------- convertisseurs : durée

def _duree_lue(minutes):
    if not (DUREE_MIN <= minutes <= DUREE_MAX):
        return Rejet(AlerteSaisie.DUREE_HORS_BORNES.value)
    return Lu(minutes, libelle_duree(minutes))


def conv_duree_prefixee(m, ctx, texte):
    """« pendant / durée / during » : jusqu'à 16 h ; « pour / for » : formes ≤ 6 h seulement."""
    h, mi = _lire_hm(m.group('hm'))
    minutes = h * 60 + (mi or 0)
    mot = re.match(r'[a-z]+', m.group('pre')).group()
    if mot in ('pour', 'for'):
        return _duree_lue(minutes) if minutes <= DUREE_POUR_MAX else None
    return _duree_lue(minutes)


def conv_duree_min(m, ctx, texte):
    return _duree_lue(int(m.group('n')))


def conv_duree_tilde(m, ctx, texte):
    minutes = int(m.group('n')) * (60 if m.group('u') == 'h' else 1)
    return _duree_lue(minutes)


def conv_duree_nu(m, ctx, texte):
    """`Nh` nu seulement si N ≤ 6 ; `NhMM` nu seulement si N ≤ 4."""
    h, mi = _lire_hm(m.group('hm'))
    if (mi or 0) > 59 or h < 1 or h > (6 if mi is None else 4):
        return None
    return _duree_lue(h * 60 + (mi or 0))


# --------------------------------------------------- convertisseurs : priorité

_LIBELLES_PRIORITE = {1: 'Priorité basse', 2: 'Priorité moyenne', 3: 'Priorité haute'}
_PRIORITE_PAR_P = {'1': 3, '2': 2, '3': 1}


def conv_priorite_excl(m, ctx, texte):
    """`!!` = 2, `!!!` = 3 (une seule `!` ou quatre et plus : non lu)."""
    valeur = len(m.group('x'))
    return Lu(valeur, _LIBELLES_PRIORITE[valeur])


_PRIORITE_PAR_MOT = {'haute': 3, 'high': 3, 'moyenne': 2, 'medium': 2, 'basse': 1, 'low': 1}


def conv_priorite_mot(m, ctx, texte):
    """R2-006 — `!haute` = 3, `!moyenne` = 2, `!basse` = 1 (et `!high/!medium/!low`)."""
    valeur = _PRIORITE_PAR_MOT[m.group('mot')]
    return Lu(valeur, _LIBELLES_PRIORITE[valeur])


def conv_priorite_p(m, ctx, texte):
    """`p1` = 3, `p2` = 2, `p3` = 1."""
    valeur = _PRIORITE_PAR_P[m.group('n')]
    return Lu(valeur, _LIBELLES_PRIORITE[valeur])


CONVERTISSEURS = {
    'jour_relatif': conv_jour_relatif,
    'jour_semaine': conv_jour_semaine,
    'jour_periode': conv_jour_periode,
    'jour_decalage': conv_jour_decalage,
    'jour_date_slash': conv_jour_date_slash,
    'jour_date_texte': conv_jour_date_texte,
    'jour_date_iso': conv_jour_date_iso,
    'jour_fin_mois': conv_jour_fin_mois,
    'jour_quantieme': conv_jour_quantieme,
    'heure_hm': conv_heure_hm,
    'heure_colon': conv_heure_colon,
    'heure_ampm': conv_heure_ampm,
    'heure_midi': conv_heure_midi,
    'heure_ce_midi': conv_heure_ce_midi,
    'moment_ce': conv_moment_ce,
    'moment_nu': conv_moment_nu,
    'duree_prefixee': conv_duree_prefixee,
    'duree_min': conv_duree_min,
    'duree_tilde': conv_duree_tilde,
    'duree_nu': conv_duree_nu,
    'priorite_excl': conv_priorite_excl,
    'priorite_p': conv_priorite_p,
    'priorite_mot': conv_priorite_mot,
}


# ------------------------------------------------------------ table des motifs

_DOW = '|'.join(JOURS_SEMAINE)
_ALT_MOIS = '|'.join(sorted(MOIS, key=len, reverse=True))
_HM = (r'\d{1,2}(?:h(?:\d{2})?|\s+h(?:\s+\d{2})?'
       r'|\s*(?:heures?|hours?|hrs?)(?:\s+\d{2})?)')
_JOUR_DEBUT = r"(?:(?<!\w)le\s+|(?<![\w/]))"   # « le » optionnel, sinon frontière de nombre
_PREFIXE_DUREE = r'(?P<pre>(?<!\w)(?:pendant|duree|during|pour|for)\s*:?\s+)'
_ANCRE_HEURE = r'(?P<a>(?<!\w)(?:a|at)\s+)?'


def _m(type_, regex, convertisseur):
    return Motif(type_, re.compile(regex), convertisseur)


MOTIFS = (
    # jour (§1.3) — français et anglais lus ensemble
    _m('jour', r"(?<!\w)(?P<m>aujourd'hui|aujourdhui|apres[- ]demain|demain|today|tomorrow)(?!\w)",
       'jour_relatif'),
    _m('jour', rf'(?<!\w)(?:(?:le|on|next)\s+)?(?P<j>{_DOW})(?:\s+prochain)?(?!\w)',
       'jour_semaine'),
    _m('jour', r'(?<!\w)(?P<p>(?:la\s+)?semaine\s+prochaine|next\s+week|ce\s+week[- ]?end'
       r'|this\s+week[- ]?end|fin\s+de\s+semaine|end\s+of\s+(?:the\s+)?week)(?!\w)',
       'jour_periode'),
    _m('jour', rf'(?<!\w)(?:dans|in)\s+(?P<n>\d+|{_ALT_NOMBRES_LETTRES}|an?|one)\s+'
       r'(?P<u>jours?|semaines?|mois|days?|weeks?|months?)(?!\w)', 'jour_decalage'),
    _m('jour', _JOUR_DEBUT + r'(?P<d>\d{1,2})/(?P<m>\d{1,2})(?:/(?P<y>\d{4}|\d{2}))?(?![\w/])',
       'jour_date_slash'),
    _m('jour', _JOUR_DEBUT + rf'(?P<d>\d{{1,2}})(?:er|st|nd|rd|th)?\s+(?P<mois>{_ALT_MOIS})'
       r'(?:\s+(?P<y>\d{4}))?(?![\w/])',
       'jour_date_texte'),
    _m('jour', rf'(?<!\w)(?P<mois>{_ALT_MOIS})\s+(?P<d>\d{{1,2}})(?:er|st|nd|rd|th)?'
       r'(?:,?\s+(?P<y>\d{4}))?(?![\w/:])',
       'jour_date_texte'),
    _m('jour', r'(?<![\w-])(?P<y>\d{4})-(?P<m>\d{2})-(?P<d>\d{2})(?![\w-])', 'jour_date_iso'),
    _m('jour', r'(?<!\w)(?:fin\s+d(?:e|u)\s+mois|end\s+of\s+(?:the\s+)?month)(?!\w)', 'jour_fin_mois'),
    # R2-006 — « le 25 » seul : le prochain 25, quand rien ne suit (fin, ponctuation) ou qu'une heure suit
    _m('jour', r'(?<!\w)le\s+(?P<d>\d{1,2})(?:er)?(?=\s*(?:$|[.,;!?)]|(?:a|at)\s|\d{1,2}\s*h|\d{1,2}:))',
       'jour_quantieme'),
    # heure
    _m('heure', _ANCRE_HEURE + rf'(?<![\w:.,])(?P<hm>{_HM})(?![\w:])',
       'heure_hm'),
    _m('heure', _ANCRE_HEURE + r'(?<![\w:.,])(?P<h>\d{1,2}):(?P<m>\d{2})(?![\w:])',
       'heure_colon'),
    _m('heure', _ANCRE_HEURE + r'(?<![\w:.,])(?P<h>\d{1,2})(?::(?P<m>\d{2}))?\s*(?P<ap>am|pm)(?!\w)',
       'heure_ampm'),
    _m('heure', _ANCRE_HEURE + r'(?<!\w)(?:midi|noon)(?!\w)', 'heure_midi'),
    _m('heure', r'(?<!\w)(?:ce|this)\s+(?:midi|noon)(?!\w)', 'heure_ce_midi'),
    # moment
    _m('moment', r'(?<!\w)(?P<m>ce\s+matin|cet\s+apres[- ]midi|cet\s+aprem|ce\s+soir|this\s+morning'
       r'|this\s+afternoon|this\s+evening|tonight)(?!\w)', 'moment_ce'),
    _m('moment', r'(?<!\w)(?:in\s+the\s+)?(?P<m>matin|apres[- ]midi|aprem|soir|morning|afternoon|evening)(?!\w)',
       'moment_nu'),
    # durée
    _m('duree', _PREFIXE_DUREE + rf'(?<![\w:.,])(?P<hm>{_HM})(?![\w:])', 'duree_prefixee'),
    _m('duree', r'(?:' + _PREFIXE_DUREE + r')?(?<![\w.,~])(?P<n>\d+)\s*(?:minutes?|mins?|mn)(?!\w)',
       'duree_min'),
    _m('duree', r'(?<![\w.,])~\s*(?P<n>\d+)\s*(?P<u>min|m|h)(?!\w)', 'duree_tilde'),
    _m('duree', rf'(?<![\w:.,])(?P<hm>{_HM})(?![\w:])', 'duree_nu'),
    # priorité
    _m('priorite', r'(?<!\S)(?P<x>!{2,3})(?!!)', 'priorite_excl'),
    _m('priorite', r'(?<!\S)p(?P<n>[123])(?!\w)', 'priorite_p'),
    _m('priorite', r'(?<!\S)!(?P<mot>haute|moyenne|basse|high|medium|low)(?!\w)', 'priorite_mot'),
)


def masquer_guillemets(texte):
    """Copie d'analyse dont les passages entre guillemets sont masqués (jamais lus)."""
    masque = list(normaliser(texte))
    for m in re.finditer(r'"[^"]*"|«[^»]*»|“[^”]*”', texte):
        for i in range(m.start(), m.end()):
            masque[i] = '\x00'
    return ''.join(masque)


# --------------------------------------------------------------- candidats

def candidats(masque, texte, ctx, motifs=MOTIFS, registre=None, types=None):
    """Tous les candidats convertis de `motifs`, et les alertes des lectures rejetées.

    Un texte rejeté (date impossible, durée hors bornes) reste du texte : aucun
    autre candidat ne peut le lire à sa place (« pendant 20h » ne devient pas 20:00).
    """
    registre = registre or CONVERTISSEURS
    trouves, rejets, rejetes = [], [], []
    for motif in motifs:
        if types is not None and motif.type not in types:
            continue
        conv = registre.get(motif.convertisseur)
        if conv is None:
            continue
        for m in motif.regex.finditer(masque):
            lu = conv(m, ctx, texte)
            if isinstance(lu, Rejet):
                rejets.append(lu.alerte)
                rejetes.append(m.span())
            elif lu is not None:
                trouves.append(Candidat(
                    m.start(), m.end(), motif.type, lu.valeur, lu.libelle, tuple(lu.alertes)))
    libres = [c for c in trouves
              if not any(c.debut < fin and debut < c.fin for debut, fin in rejetes)]
    return libres, rejets


def _suit_un_jour(c, masque, jours):
    """Vrai si un jeton jour finit juste avant `c`, séparé par des espaces seulement."""
    return any(j.fin < c.debut and masque[j.fin:c.debut].isspace() for j in jours)


_AVANT_MOMENT_NON_LU = re.compile(r"(?:(?<!\w)(?:du|de|le|la|au|the|of)\s+|(?<!\w)d')$")


def _moment_nu_lu(c, masque, jours):
    """§1.4 : un moment nu suit un jour, ou finit la ligne sans article devant."""
    if _suit_un_jour(c, masque, jours):
        return True
    if masque[c.fin:].strip(' .!?,;') != '':
        return False
    return not _AVANT_MOMENT_NON_LU.search(masque[:c.debut])


def filtrer_contexte(cands, masque):
    """Règles de contexte §1.4 : moments nus, midi/noon, étape après un projet."""
    jours = [c for c in cands if c.type == 'jour']
    projets = [c for c in cands if c.type == 'projet']
    gardes = []
    for c in cands:
        if c.type == 'moment' and not c.valeur[1] and not _moment_nu_lu(c, masque, jours):
            continue
        if c.type == 'heure' and c.valeur.midi and _est_midi_nu(c, masque, jours):
            continue
        if c.type == 'section' and not any(p.fin <= c.debut for p in projets):
            continue
        gardes.append(c)
    return gardes


def _est_midi_nu(c, masque, jours):
    """« midi / noon » sans « à / at » devant et sans jour juste avant : non lu."""
    avec_ancre = re.match(r'(?:a|at)\s', masque[c.debut:c.fin])
    return not (avec_ancre or _suit_un_jour(c, masque, jours))


# ------------------------------------------------------ échéances composées

_DECLENCHEUR_ECHEANCE = re.compile(r"(?<!\w)(?:pour|avant|d'ici|due|by|for|deadline)\s+")


def _heure_apres(masque, position, heures):
    """Le jeton heure le plus proche après `position`, séparé par des espaces seulement."""
    proches = [h for h in heures if h.debut > position and masque[position:h.debut].isspace()]
    return min(proches, key=lambda h: h.debut, default=None)


def _echeance_depuis(m, masque, bases):
    pos = m.end()
    jours = [c for c in bases if c.type == 'jour' and c.debut == pos]
    heures = [c for c in bases if c.type == 'heure']
    if jours:
        j = max(jours, key=lambda c: c.fin)
        h = _heure_apres(masque, j.fin, heures)
        return Candidat(m.start(), (h or j).fin, 'echeance',
                        (j.valeur, h.valeur if h else None), alertes=j.alertes)
    if any(c.type == 'duree' and c.debut == m.start() for c in bases):
        return None
    h = next((c for c in heures if c.debut == pos), None)
    if h is None:
        return None
    return Candidat(m.start(), h.fin, 'echeance', (None, h.valeur))


def composer_echeances(masque, bases):
    """« pour / avant / d'ici / due / by / for / deadline » + jour [heure], ou + heure seule."""
    trouvees = (_echeance_depuis(m, masque, bases)
                for m in _DECLENCHEUR_ECHEANCE.finditer(masque))
    return [c for c in trouvees if c is not None]


# --------------------------------------------------------------------- choix

def _cle_tri(c):
    return (c.debut, c.debut - c.fin, ORDRE_TYPES.index(c.type))


def choisir(cands):
    """§1.5 : jetons retenus (sans chevauchement) et alertes `deux_<type>`."""
    retenus, alertes = [], []
    for c in sorted(cands, key=_cle_tri):
        if any(c.debut < r.fin and r.debut < c.fin for r in retenus):
            continue
        if c.type != ETIQUETTE and any(r.type == c.type for r in retenus):
            alertes.append(alerte_deux(c.type))
            continue
        retenus.append(c)
    return sorted(retenus, key=lambda r: r.debut), alertes
