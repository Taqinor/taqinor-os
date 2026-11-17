"""Recalcul jetable de l'annexe A (spec 2 §3.1), grammaire TELLE QU'ÉCRITE.
Ce qui n'est pas écrit n'est PAS implémenté (pas de devinette)."""
import re, unicodedata, calendar
from datetime import date, time, datetime, timedelta

NOW = datetime(2026, 11, 17, 10, 0); J = NOW.date()
_A = 'àáâãäåçèéêëìíîïñòóôõöùúûüýÿ'
TB = str.maketrans(_A + _A.upper(), ''.join(unicodedata.normalize('NFD', c)[0] for c in _A + _A.upper()))
def norm(s): return s.translate(TB).lower()   # même longueur : positions conservées
JOURS = {'lundi':0,'mardi':1,'mercredi':2,'jeudi':3,'vendredi':4,'samedi':5,'dimanche':6,
         'monday':0,'tuesday':1,'wednesday':2,'thursday':3,'friday':4,'saturday':5,'sunday':6}
MOIS = {'janvier':1,'fevrier':2,'mars':3,'avril':4,'mai':5,'juin':6,'juillet':7,'aout':8,'septembre':9,
        'octobre':10,'novembre':11,'decembre':12}
MMM = {m.lower(): i for i, m in enumerate(calendar.month_abbr) if m}
JR = '|'.join(JOURS); MR = '|'.join(MOIS); ER = '|'.join(MMM)
def prochain_wd(wd, base=J):
    k = (wd - base.weekday()) % 7 or 7; return base + timedelta(k)   # J exclu
def sans_annee(d, m):
    c = date(J.year, m, d); return c if c >= J else date(J.year + 1, m, d)
def add_mois(d, n):
    y, m = divmod(d.month - 1 + n, 12); y += d.year; m += 1
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))
B = r'(?<![\w])'; E = r'(?![\w])'
DATE = (rf"aujourd'hui|apres-demain|demain|today|tomorrow|(?:le )?(?:{JR})(?: prochain)?|(?:next |on )?(?:{JR})"
        rf"|semaine prochaine|next week|ce week-end|this weekend|dans \d+ (?:jours?|semaines?|mois)|in \d+ (?:days?|weeks?|months?)"
        rf"|(?:le )?\d{{1,2}}/\d{{1,2}}(?:/\d{{4}})?|\d{{4}}-\d{{2}}-\d{{2}}|\d{{1,2}} (?:{MR})(?: \d{{4}})?|\d{{1,2}} (?:{ER})|(?:{ER}) \d{{1,2}}"
        rf"|fin de mois|fin de semaine|end of month|end of week")
HEURE = r"(?:a |at )?(?:\d{1,2}h\d{2}|\d{1,2}h|\d{1,2}:\d{2}(?:am|pm)?|\d{1,2}(?:am|pm))"
DUREE = r"(?:(?:pendant|duree|pour|for) )?(?:\d+ ?(?:min|mn)|~\d+m|~\d+h|\d+h\d{2}|\d+h)"
REC = (rf"(?:tous les (?:\d+ )?jours|tous les (?:{JR})s(?: et (?:{JR})s)?|chaque (?:{JR})|toutes les \d+ semaines|chaque jour ouvre|en semaine"
       rf"|chaque fin de mois|chaque mois(?: le \d{{1,2}})?|chaque (?:premier|dernier) (?:{JR})|chaque annee"
       rf"|every!?(?: \d+)? days?|every!? (?:{JR})|every!? weekday|every!? \d+ weeks|every!? month(?: on the \d{{1,2}})?|every!? year)(?: apres fait)?")
TYPES = [
    ('recurrence', REC), ('rappel', rf"(?:rappelle-moi|rappel|remind(?: me)?)(?: (?:{DATE}))? {HEURE}"),
    ('echeance', rf"(?:pour|avant|d'ici|due|by|for|deadline) (?:(?:{DATE})(?: {HEURE})?|{HEURE})"),
    ('duree', DUREE), ('heure', HEURE), ('date', DATE),
    ('moment', r"ce matin|cet apres-midi|apres-midi|ce soir|matin|soir|this morning|morning|afternoon|tonight|this evening"),
    ('un_jour', r"un jour$|someday"), ('projet', r"#[a-z][\w-]*"), ('section', r"/[a-z]\w*"),
    ('priorite', r"!!!|!!|p[123]"), ('etiquette', r"%[a-z]\w*")]


def val_date(s):
    s = re.sub(r'^(le |on |next )', '', s)
    if s in ("aujourd'hui", 'today'): return J
    if s in ('demain', 'tomorrow'): return J + timedelta(1)
    if s == 'apres-demain': return J + timedelta(2)
    if s in ('semaine prochaine', 'week'): return prochain_wd(0)
    if s in ('ce week-end', 'this weekend'): return prochain_wd(5)
    if s in ('fin de mois', 'end of month'): return date(J.year, J.month, calendar.monthrange(J.year, J.month)[1])
    if s in ('fin de semaine', 'end of week'): return prochain_wd(4)
    m = re.match(rf'({JR})(?: prochain)?$', s)
    if m: return prochain_wd(JOURS[m.group(1)])
    m = re.match(r'(?:dans|in) (\d+) (\w+)', s)
    if m:
        n, u = int(m.group(1)), m.group(2)
        return J + timedelta(n) if u[0] in 'jd' else J + timedelta(7 * n) if u[0] in 'sw' else add_mois(J, n)
    m = re.match(r'(\d{1,2})/(\d{1,2})(?:/(\d{4}))?$', s)
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), m.group(3)
        return date(int(y), mo, d) if y else sans_annee(d, mo)
    m = re.match(r'(\d{4})-(\d{2})-(\d{2})$', s)
    if m: return date(*map(int, m.groups()))
    m = re.match(rf'(\d{{1,2}}) ({MR}|{ER})', s) or re.match(rf'({ER}) (\d{{1,2}})', s)
    if m:
        a, b = m.groups(); (d, mo) = (a, b) if a.isdigit() else (b, a)
        return sans_annee(int(d), MOIS.get(mo) or MMM[mo])
    return ('?', s)


def val_heure(s):
    s = re.sub(r'^(a |at )', '', s)
    m = re.match(r'(\d{1,2})(?:h(\d{2})?|:(\d{2}))?(am|pm)?$', s)
    h, mi = int(m.group(1)), int(m.group(2) or m.group(3) or 0)
    if m.group(4) == 'pm' and h < 12: h += 12
    return h, mi


def nu(s):
    m = re.fullmatch(r'(\d{1,2})h(\d{2})?', s); return None if not m else int(m.group(1))


def analyser(texte):
    t = norm(texte); masque = t
    for q in re.finditer(r'"[^"]*"|«[^»]*»|“[^”]*”', t):
        masque = masque[:q.start()] + ' ' * (q.end() - q.start()) + masque[q.end():]
    cands = []
    for typ, mot in TYPES:
        fin_mot = r'(?![\w!])' if typ == 'priorite' else E
        for m in re.finditer(B + '(?:' + mot + ')' + fin_mot, masque):
            s = m.group(0)
            if typ == 'heure':
                n = nu(re.sub(r'^(a |at )', '', s))
                if n is not None and not s.startswith(('a ', 'at ')) and not 7 <= n <= 23: continue
            if typ == 'duree':
                n = nu(re.sub(r'^(pendant|duree|pour|for) ', '', s))
                if n is not None and n > 6: continue
            cands.append((m.start(), -(m.end() - m.start()), m.end(), typ, s))
    cands.sort(); pris, vus, alertes, fin = [], set(), [], -1
    for st, _, en, typ, s in cands:
        if st < fin: continue
        if typ in vus: alertes.append('deux_' + typ); continue
        pris.append((typ, s, st, en)); vus.add(typ); fin = en
    r = {typ: s for typ, s, st, en in pris}
    titre = texte
    for typ, s, st, en in sorted(pris, key=lambda x: -x[2]):
        titre = titre[:st] + titre[en:]
    out = {'titre': re.sub(r'\s+', ' ', titre).strip()}
    if 'date' in r: out['jour'] = val_date(r['date'])
    if 'heure' in r:
        h, mi = val_heure(r['heure'])
        mo = r.get('moment', '')
        if ('apres' in mo or 'soir' in mo or mo in ('tonight', 'this evening', 'afternoon')) and 1 <= h <= 11: h += 12
        out['heure'] = f'{h:02d}:{mi:02d}'
        if 'jour' not in out and not mo.startswith(('ce', 'cet', 'this', 'tonight')):
            out['jour'] = J if time(h % 24, mi) > NOW.time() else J + timedelta(1)
    if 'moment' in r:
        out['moment'] = r['moment']
        if r['moment'].startswith(('ce ', 'cet ', 'this', 'tonight')): out.setdefault('jour', J)
    for k in ('echeance', 'duree', 'recurrence', 'rappel', 'projet', 'section', 'priorite', 'etiquette', 'un_jour'):
        if k in r: out[k] = r[k]
    if alertes: out['alertes'] = alertes
    return out


PHRASES = """Appeler Karim demain|Call Karim tomorrow|Envoyer le devis lundi #Polydesign|Relancer banque lundi prochain
Send invoice next monday|Payer CNSS dans 3 jours|Review contract in 3 days|Réunion fournisseur 25/11 à 15h|Rapport TVA fin de mois !!!
Rapport TVA pour fin de mois|Préparer offre ce soir|Lire contrat demain matin|Call supplier at 3pm|Point équipe 9h|Écrire article 2h
Trier emails 30 min|Prepare slides for 2h|Dossier subvention pour vendredi|Finish report due friday 15:00|Préparer visite jeudi pour vendredi
Arroser plantes tous les 2 jours|Rapport hebdo chaque lundi #Polydesign|Check bank every weekday|Payer loyer chaque mois le 5
Changer filtre tous les 3 mois après fait|Water plants every! 3 days|Acheter câbles #Maison /Achats %magasin|Maquette #SiteWeb !!
Plan lancement #Nouveau_site p1|Lire « Demain dès l'aube »|Rappeler Ali 5/6|Meeting 3/1|Appeler Karim demain rappel 9h
Envoyer rapport monthly|Remise 10% pour facture #12 !|Dîner ce soir 9h|Apprendre l'arabe classique un jour|Fix bug Nov 25 at 10am|Inventaire ce week-end"""
EXTRA = """Appeler aujourd’hui|Train 6h30 demain|Réunion à 15 h|Payer le 1er décembre|Déjeuner à midi|Call at 15:30
Rapport pour 9h|Rapport pour 6h|Sport en semaine|Préparer le soir de gala|Lire Demain dès l'aube|Réunion lundi
Envoyer mail mardi soir 8h|Relancer client vendredi pour lundi|Call May 5|Point demain 14h30 pendant 1h
Payer facture le 31/11|Faire devis 2h demain 15h|Ranger garage ce weekend|Réunion du matin|Arroser every 2 days|Voir Ali pour 3/12 à 9h"""

if __name__ == '__main__':
    for i, p in enumerate(PHRASES.replace('\n', '|').split('|'), 1):
        print(f'A{i:<2}', p, '->', analyser(p))
    print('--- hors annexe')
    for p in EXTRA.replace('\n', '|').split('|'):
        try:
            print('  ', p, '->', analyser(p))
        except Exception as e:
            print('  ', p, '-> EXCEPTION', type(e).__name__, e)
