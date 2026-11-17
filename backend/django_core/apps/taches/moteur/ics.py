"""Lecture ICS pure, lecteur MAISON minimal (reference/regles.md §11, donnees.md invariant 35).

Lit VEVENT, DTSTART, DTEND, DURATION, UID, SUMMARY, STATUS, en `Z`, en fuseau nommé
(`TZID`, noms Windows de Microsoft 365 compris), en heure flottante et en journée
entière (`VALUE=DATE`). `RRULE` n'est pas lu en v1 : seule l'occurrence de `DTSTART`
apparaît. Bibliothèque standard seule, aucune base, aucun réseau, aucune horloge.
"""
import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .sollicitations import Fenetre

FUSEAU_SOCIETE = 'Africa/Casablanca'
MAX_EVENEMENTS = 2000

# Noms de fuseau Windows (Microsoft 365) vers leur nom IANA.
FUSEAUX_WINDOWS = {
    'UTC': 'UTC',
    'GMT Standard Time': 'Europe/London',
    'Greenwich Standard Time': 'Atlantic/Reykjavik',
    'Morocco Standard Time': 'Africa/Casablanca',
    'W. Europe Standard Time': 'Europe/Berlin',
    'Romance Standard Time': 'Europe/Paris',
    'Central Europe Standard Time': 'Europe/Budapest',
    'Central European Standard Time': 'Europe/Warsaw',
    'E. Europe Standard Time': 'Europe/Chisinau',
    'Eastern Standard Time': 'America/New_York',
    'Central Standard Time': 'America/Chicago',
    'Mountain Standard Time': 'America/Denver',
    'Pacific Standard Time': 'America/Los_Angeles',
    'Arab Standard Time': 'Asia/Riyadh',
    'Arabian Standard Time': 'Asia/Dubai',
}


class IcsIllisible(ValueError):
    """Pas de `BEGIN:VCALENDAR` : état `illisible`."""


class IcsTropGrand(ValueError):
    """Plus de 2 000 événements : état `trop_grande`."""


@dataclass(frozen=True)
class RendezVousPur:
    """Un rendez-vous d'agenda externe (regles.md §0.1) ; heures locales sans fuseau."""
    cle: str
    agenda_id: int
    titre: str
    debut: datetime
    fin: datetime
    journee_entiere: bool


def _lignes_depliees(texte):
    """RFC 5545 : une ligne qui commence par une espace ou une tabulation continue la précédente."""
    lignes = []
    for brute in texte.replace('\r\n', '\n').replace('\r', '\n').split('\n'):
        if brute[:1] in (' ', '\t') and lignes:
            lignes[-1] += brute[1:]
        elif brute:
            lignes.append(brute)
    return lignes


def _propriete(ligne):
    """`NOM;PARAM=x:valeur` -> (NOM, {PARAM: x}, valeur)."""
    gauche, sep, valeur = ligne.partition(':')
    if not sep:
        return None
    morceaux = gauche.split(';')
    params = {}
    for morceau in morceaux[1:]:
        cle, _, val = morceau.partition('=')
        params[cle.upper()] = val.strip('"')
    return morceaux[0].upper(), params, valeur


def _evenements_bruts(lignes):
    """Une liste de dicts {NOM: (params, valeur)} par VEVENT (première occurrence gardée)."""
    courant, resultat = None, []
    for ligne in lignes:
        marque = ligne.strip().upper()
        if marque == 'BEGIN:VEVENT':
            courant = {}
        elif marque == 'END:VEVENT':
            if courant is not None:
                resultat.append(courant)
            courant = None
        elif courant is not None:
            prop = _propriete(ligne)
            if prop and prop[0] not in courant:
                courant[prop[0]] = (prop[1], prop[2])
    return resultat


def _zone(nom):
    """Fuseau demandé ; un nom inconnu retombe sur `None` (lu en heure locale), y compris un nom
    qui désigne un dossier de tzdata (`TZID=America` : `PermissionError`/`IsADirectoryError`)."""
    try:
        return ZoneInfo(FUSEAUX_WINDOWS.get(nom, nom))
    except (ZoneInfoNotFoundError, ValueError, OverflowError, OSError):
        return None


def _lire_date_heure(valeur, params, local):
    """Valeur DTSTART/DTEND -> (datetime local sans fuseau, journee_entiere)."""
    valeur = valeur.strip()
    if params.get('VALUE') == 'DATE' or ('T' not in valeur and len(valeur) == 8):
        return datetime.strptime(valeur[:8], '%Y%m%d'), True
    utc = valeur.endswith('Z')
    naif = datetime.strptime(valeur.rstrip('Z'), '%Y%m%dT%H%M%S')
    if utc:
        zone = timezone.utc
    else:
        zone = _zone(params['TZID']) if 'TZID' in params else None
    if zone is None:
        return naif, False
    return naif.replace(tzinfo=zone).astimezone(local).replace(tzinfo=None), False


def _duree(valeur):
    """`PT1H30M`, `P1D`, `P1W`, `-PT15M` -> timedelta (None si illisible)."""
    m = re.fullmatch(r'([+-])?P(?:(\d+)W)?(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?', valeur.strip())
    if not m:
        return None
    signe, semaines, jours, heures, minutes, secondes = m.groups()
    total = timedelta(weeks=int(semaines or 0), days=int(jours or 0), hours=int(heures or 0),
                      minutes=int(minutes or 0), seconds=int(secondes or 0))
    return -total if signe == '-' else total


def _texte_ics(valeur):
    """Retire les échappements `\\,` `\\;` `\\n` `\\\\`."""
    return (valeur.replace('\\n', '\n').replace('\\N', '\n').replace('\\,', ',')
            .replace('\\;', ';').replace('\\\\', '\\'))


def _fin(props, debut, entiere, local):
    """Fin lue de DTEND, sinon DURATION ; sans l'un ni l'autre 0 min (un jour si date seule)."""
    if 'DTEND' in props:
        params, valeur = props['DTEND']
        return _lire_date_heure(valeur, params, local)[0]
    if 'DURATION' in props:
        duree = _duree(props['DURATION'][1])
        if duree is not None:
            return debut + duree
    return debut + (timedelta(days=1) if entiere else timedelta(0))


def _cle(agenda_id, props):
    uid = props.get('UID', ({}, ''))[1]
    debut = props['DTSTART'][1]
    empreinte = hashlib.sha256((uid + debut).encode('utf-8')).hexdigest()[:8]
    return f'{agenda_id}-{empreinte}'


def _dans_la_fenetre(debut, fin, du, au):
    """Chevauche les jours [du, au] (bornes comprises) ; un instant nul compte à son jour."""
    borne_debut = datetime.combine(du, datetime.min.time())
    borne_fin = datetime.combine(au + timedelta(days=1), datetime.min.time())
    if debut >= borne_fin:
        return False
    if fin > debut:
        return fin > borne_debut
    return debut >= borne_debut


def _rendez_vous(props, agenda_id, local):
    if 'DTSTART' not in props or props.get('STATUS', ({}, ''))[1].strip().upper() == 'CANCELLED':
        return None
    params, valeur = props['DTSTART']
    try:
        debut, entiere = _lire_date_heure(valeur, params, local)
        fin = _fin(props, debut, entiere, local)
    except (ValueError, OverflowError, OSError):
        return None  # un événement illisible (ou hors calendrier) est ignoré, jamais une erreur à l'écran
    titre = _texte_ics(props.get('SUMMARY', ({}, ''))[1])
    return RendezVousPur(_cle(agenda_id, props), agenda_id, titre, debut, max(fin, debut), entiere)


def lire_evenements(texte, du, au, agenda_id=0, fuseau=FUSEAU_SOCIETE):
    """Événements du calendrier `texte` qui touchent les jours [du, au], dans l'ordre de début.

    `RendezVousPur` aux heures locales de `fuseau`. Lève `IcsIllisible` sans
    `BEGIN:VCALENDAR`, `IcsTropGrand` au-delà de 2 000 événements.
    """
    lignes = _lignes_depliees(texte)
    if not any(ligne.strip().upper() == 'BEGIN:VCALENDAR' for ligne in lignes):
        raise IcsIllisible('BEGIN:VCALENDAR absent')
    bruts = _evenements_bruts(lignes)
    if len(bruts) > MAX_EVENEMENTS:
        raise IcsTropGrand(f'{len(bruts)} événements')
    local = ZoneInfo(fuseau)
    trouves = (_rendez_vous(props, agenda_id, local) for props in bruts)
    gardes = [r for r in trouves if r and _dans_la_fenetre(r.debut, r.fin, du, au)]
    return tuple(sorted(gardes, key=lambda r: (r.debut, r.cle)))


def _intervalle_du_jour(rdv, jour, fenetre):
    """Intervalle du rendez-vous coupé au jour ET aux heures de travail, ou `None`."""
    debut_travail = datetime.combine(jour, fenetre.debut)
    fin_travail = datetime.combine(jour, fenetre.fin)
    debut, fin = max(rdv.debut, debut_travail), min(rdv.fin, fin_travail)
    return (debut, fin) if fin > debut else None


def _fusionner(intervalles):
    fusion = []
    for debut, fin in sorted(intervalles):
        if fusion and debut <= fusion[-1][1]:
            fusion[-1] = (fusion[-1][0], max(fusion[-1][1], fin))
        else:
            fusion.append((debut, fin))
    return fusion


def minutes_rendez_vous(evenements, jour, fenetre):
    """Minutes de rendez-vous horodatés de `jour`, unies et bornées aux heures de travail.

    La journée entière vaut 0 ; jamais négatif. `fenetre` : `Fenetre(debut, fin)`.
    """
    coupes = (_intervalle_du_jour(rdv, jour, fenetre) for rdv in evenements if not rdv.journee_entiere)
    fusion = _fusionner([c for c in coupes if c])
    total = sum((fin - debut for debut, fin in fusion), timedelta(0))
    return max(0, int(total.total_seconds() // 60))


__all__ = ('RendezVousPur', 'Fenetre', 'IcsIllisible', 'IcsTropGrand', 'lire_evenements',
           'minutes_rendez_vous')
