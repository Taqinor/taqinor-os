"""Briques HTML des actes : chacune prend des valeurs simples et rend une chaîne.

Aucune ne lit la base ni ne calcule un montant : tout chiffre affiché arrive
déjà calculé dans le ``contenu`` (une seule source par valeur).
"""
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from html import escape

from . import style

ESPACE_FINE = ' '
INSECABLE = ' '

MOIS = ('janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet',
        'août', 'septembre', 'octobre', 'novembre', 'décembre')
# Noms des mois en usage au Maroc.
MOIS_AR = ('يناير', 'فبراير', 'مارس', 'أبريل', 'ماي', 'يونيو', 'يوليوز',
           'غشت', 'شتنبر', 'أكتوبر', 'نونبر', 'دجنبر')
DEVISES = {'fr': 'DH', 'ar': 'درهم'}
A_PRECISER = {'fr': 'à préciser', 'ar': 'يُحدَّد لاحقًا'}

# L'ordre des quatre actes : (type, titre court, sous-titre du parcours).
PARCOURS = (
    ('contrat_installation', 'Contrat', 'à la signature'),
    ('pv_livraison', 'Livraison', 'le matériel chez vous'),
    ('pv_reception', 'Réception', 'à la fin des travaux'),
    ('cloture_garanties', 'Clôture', 'garanties et conseils'),
)


def esc(valeur):
    return escape('' if valeur is None else str(valeur), quote=True)


def _decimal(valeur):
    if valeur is None or valeur == '':
        return None
    try:
        return Decimal(str(valeur))
    except (InvalidOperation, ValueError):
        return None


def nombre(valeur, decimales=2):
    """1234567.5 → « 1 234 567,50 » (espace fine insécable, virgule)."""
    d = _decimal(valeur)
    if d is None:
        return ''
    quantum = Decimal(1).scaleb(-decimales) if decimales else Decimal(1)
    d = d.quantize(quantum, rounding=ROUND_HALF_UP)
    signe = '-' if d < 0 else ''
    entier, _, frac = f'{abs(d):f}'.partition('.')
    groupes = []
    while len(entier) > 3:
        groupes.insert(0, entier[-3:])
        entier = entier[:-3]
    groupes.insert(0, entier)
    texte = signe + ESPACE_FINE.join(groupes)
    return f'{texte},{frac}' if decimales else texte


def montant(valeur, devise=None, langue='fr'):
    """« 45 000,00 DH » (« 45 000,00 درهم » en arabe), ou « à préciser »
    quand le montant manque. Les chiffres restent les mêmes dans les deux
    langues : c'est le même montant, écrit pareil."""
    texte = nombre(valeur, 2)
    if not texte:
        return A_PRECISER.get(langue, A_PRECISER['fr'])
    devise = devise or DEVISES.get(langue, 'DH')
    return f'{texte}{INSECABLE}{devise}'


def pourcent(valeur):
    d = _decimal(valeur)
    if d is None:
        return ''
    d = d.quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)
    if d == d.to_integral_value():
        return f'{int(d)}{INSECABLE}%'
    return f'{nombre(d, 1)}{INSECABLE}%'


def _date(valeur):
    if isinstance(valeur, datetime):
        return valeur.date()
    if isinstance(valeur, date):
        return valeur
    if not valeur:
        return None
    try:
        return date.fromisoformat(str(valeur)[:10])
    except ValueError:
        return None


def date_longue(valeur, langue='fr'):
    """« 24 novembre 2026 » / « 24 نونبر 2026 » ('' si la date manque)."""
    d = _date(valeur)
    if d is None:
        return ''
    if langue == 'ar':
        return f'{d.day} {MOIS_AR[d.month - 1]} {d.year}'
    jour = '1er' if d.day == 1 else str(d.day)
    return f'{jour} {MOIS[d.month - 1]} {d.year}'


def date_courte(valeur):
    d = _date(valeur)
    return d.strftime('%d/%m/%Y') if d else ''


def _compte_ar(n, un, deux, pluriel, singulier):
    """Accord arabe du nom compté : 1, 2, 3 à 10, puis 11 et plus."""
    if n == 1:
        return un
    if n == 2:
        return deux
    if 3 <= n <= 10:
        return f'{n}{INSECABLE}{pluriel}'
    return f'{n}{INSECABLE}{singulier}'


def duree_mois(mois, langue='fr'):
    """24 → « 2 ans » ; 18 → « 18 mois » ; None → ''. En arabe : « سنتان »,
    « 5 سنوات », « 30 سنة », « 18 شهرًا »."""
    try:
        mois = int(mois)
    except (TypeError, ValueError):
        return ''
    if mois <= 0:
        return ''
    if langue == 'ar':
        if mois % 12 == 0:
            return _compte_ar(mois // 12, 'سنة واحدة', 'سنتان', 'سنوات', 'سنة')
        return _compte_ar(mois, 'شهر واحد', 'شهران', 'أشهر', 'شهرًا')
    if mois % 12 == 0:
        ans = mois // 12
        return f'{ans}{INSECABLE}an' + ('s' if ans > 1 else '')
    return f'{mois}{INSECABLE}mois'


def paragraphes(textes):
    """Liste de paragraphes → HTML. Une ligne qui commence par « - » devient
    une puce ; ``**gras**`` devient du gras ; tout le reste est échappé."""
    sortie, puces = [], []

    def vider():
        if puces:
            sortie.append('<ul>' + ''.join(f'<li>{p}</li>' for p in puces)
                          + '</ul>')
            puces.clear()

    for bloc in textes or []:
        for ligne in str(bloc).split('\n'):
            ligne = ligne.strip()
            if not ligne:
                continue
            if ligne.startswith('- '):
                puces.append(_gras(ligne[2:]))
            else:
                vider()
                sortie.append(f'<p>{_gras(ligne)}</p>')
    vider()
    return ''.join(sortie)


def _gras(texte):
    morceaux = esc(texte).split('**')
    if len(morceaux) < 3 or len(morceaux) % 2 == 0:
        return esc(texte)
    return ''.join(m if i % 2 == 0 else f'<strong>{m}</strong>'
                   for i, m in enumerate(morceaux))


# ── En-tête, parcours, titre ────────────────────────────────────────────────

def _marque(societe):
    uri = (societe or {}).get('logo_uri')
    if uri:
        try:
            from apps.ventes.quote_engine import logo as _logo
            b64 = _logo.societe_b64(uri, 'sombre')
            if b64:
                return (f'<img src="data:image/png;base64,{b64}" '
                        f'alt="{esc(societe.get("nom"))}">')
        except Exception:  # logo illisible : le nom, jamais une image cassée
            pass
    return esc((societe or {}).get('nom'))


def bandeau(contenu):
    societe = contenu.get('societe') or {}
    chantier = contenu.get('chantier') or {}
    lignes = [f'<b>{esc(contenu.get("reference"))}</b>']
    if chantier.get('reference'):
        lignes.append(f'Chantier {esc(chantier["reference"])}')
    if contenu.get('date_document'):
        lignes.append(esc(date_longue(contenu['date_document'])))
    return (f'<div class="bandeau"><div class="marque">{_marque(societe)}</div>'
            f'<div class="ref">{"<br>".join(lignes)}</div></div>')


def parcours(type_acte):
    rang = [t for t, _, _ in PARCOURS].index(type_acte)
    etapes = []
    for i, (_, titre, sous) in enumerate(PARCOURS):
        classe = 'ici' if i == rang else ('fait' if i < rang else '')
        etapes.append(
            f'<div class="etape {classe}"><span class="n">{i + 1}</span>'
            f'<span>{esc(titre)}<small>{esc(sous)}</small></span></div>')
    return f'<div class="parcours">{"".join(etapes)}</div>'


def titre(type_acte, h1, chapeau, reference=''):
    rang = [t for t, _, _ in PARCOURS].index(type_acte) + 1
    court = PARCOURS[rang - 1][1]
    return (f'<div class="titre"><div class="surtitre">Acte {rang} sur 4 · '
            f'{esc(court)}</div><div class="reference-cachee">{esc(reference)}'
            f'</div><h1>{esc(h1)}</h1><p class="chapeau">{chapeau}</p></div>')


def h2(texte, intro=''):
    bloc = f'<h2>{style.etoile_svg()}{esc(texte)}</h2>'
    if intro:
        bloc += f'<p class="intro">{intro}</p>'
    return bloc


# ── Cartes de l'essentiel ───────────────────────────────────────────────────

def carte(libelle, valeur, detail='', *, forte=False, large=False):
    classes = 'carte' + (' forte' if forte else '') + (' large' if large else '')
    det = f'<div class="det">{detail}</div>' if detail else ''
    return (f'<div class="{classes}"><div class="lbl">{esc(libelle)}</div>'
            f'<div class="val">{valeur}</div>{det}</div>')


def cartes(*blocs):
    return f'<div class="cartes">{"".join(b for b in blocs if b)}</div>'


# ── Frise de paiement ───────────────────────────────────────────────────────

ETATS_TRANCHE = {
    'regle': 'Réglé',
    'exigible': 'À régler',
    'a_venir': 'À venir',
}


def frise(echeancier, *, avec_etats=False):
    """La frise des tranches. ``avec_etats`` : pastille + mot d'état (les actes
    2 à 4) ; sans (le contrat), seulement quand et combien."""
    jalons = []
    for i, tr in enumerate(echeancier or []):
        etat = tr.get('statut') or 'a_venir'
        classe = f'jalon {etat}' if avec_etats else 'jalon'
        pct = pourcent(tr.get('pourcentage'))
        petit = f' <small>· {pct}</small>' if pct else ''
        bloc_etat = ''
        if avec_etats:
            mot = ETATS_TRANCHE.get(etat, ETATS_TRANCHE['a_venir'])
            if etat == 'regle' and tr.get('regle_le'):
                mot = f'{mot} le {date_courte(tr["regle_le"])}'
            bloc_etat = f'<div class="etat">{esc(mot)}</div>'
        note = (f'<div class="note">{esc(tr["note"])}</div>'
                if tr.get('note') else '')
        jalons.append(
            f'<div class="{classe}"><div class="tete">'
            f'<span class="pastille">{i + 1}</span><span class="trait"></span>'
            f'</div><div class="quand">{esc(tr.get("exigibilite"))}</div>'
            f'<div class="quoi">{esc(tr.get("libelle"))}</div>'
            f'<div class="combien">{esc(montant(tr.get("montant_ttc")))}'
            f'{petit}</div>{bloc_etat}{note}</div>')
    return f'<div class="frise">{"".join(jalons)}</div>'


# ── Parties ─────────────────────────────────────────────────────────────────

def _lignes(*valeurs):
    return '<br>'.join(esc(v) for v in valeurs if v)


def _identifiants_societe(societe, *, cnss=True):
    paires = [('RC', societe.get('rc')), ('ICE', societe.get('ice')),
              ('IF', societe.get('identifiant_fiscal')),
              ('Patente', societe.get('patente'))]
    if cnss:
        paires.append(('CNSS', societe.get('cnss')))
    return ' · '.join(f'{k} {v}' for k, v in paires if v)


def partie_societe(societe, role="L'installateur"):
    forme = ' '.join(x for x in (
        societe.get('forme_juridique'),
        (f'au capital de {societe["capital_social"]}'
         if societe.get('capital_social') else '')) if x)
    represente = (f'Représentée par {societe["representant"]}'
                  if societe.get('representant') else '')
    lignes = _lignes(forme, societe.get('adresse'),
                     _identifiants_societe(societe), represente)
    court = esc(societe.get('nom_court') or societe.get('nom'))
    return (f'<div class="partie"><div class="lbl">{esc(role)}</div>'
            f'<div class="nom">{esc(societe.get("nom"))}</div>{lignes}'
            f'<div class="ci-apres">ci-après « {court} »</div></div>')


def partie_client(client, role='Le client'):
    entreprise = client.get('type') == 'entreprise'
    if entreprise:
        ident = ' · '.join(f'{k} {v}' for k, v in (
            ('RC', client.get('rc')), ('ICE', client.get('ice')),
            ('IF', client.get('if_fiscal'))) if v)
        represente = (f'Représentée par {client["representant"]}'
                      if client.get('representant') else '')
    else:
        ident = f'CIN {client["cin"]}' if client.get('cin') else 'CIN : ……………………'
        represente = ''
    contact = ' · '.join(x for x in (client.get('telephone'),
                                     client.get('email')) if x)
    return (f'<div class="partie"><div class="lbl">{esc(role)}</div>'
            f'<div class="nom">{esc(client.get("nom_complet"))}</div>'
            f'{_lignes(ident, client.get("adresse"), contact, represente)}'
            f'<div class="ci-apres">ci-après « le Client »</div></div>')


def parties(contenu):
    return (f'<div class="parties">{partie_societe(contenu.get("societe") or {})}'
            f'{partie_client(contenu.get("client") or {})}</div>')


# ── Tableaux ────────────────────────────────────────────────────────────────

def tableau_materiel(lignes, *, avec_series=False):
    if not lignes:
        return ''
    tete = '<th>Désignation</th><th>Marque</th><th class="n">Quantité</th>'
    if avec_series:
        tete = ('<th>Désignation</th><th>Marque</th><th>N° de série</th>'
                '<th class="n">Quantité</th>')
    corps = []
    for lg in lignes:
        serie = (f'<td>{esc(lg.get("numeros_serie") or "")}</td>'
                 if avec_series else '')
        corps.append(
            f'<tr><td><b>{esc(lg.get("designation"))}</b></td>'
            f'<td>{esc(lg.get("marque") or "")}</td>{serie}'
            f'<td class="n">{esc(lg.get("quantite"))}</td></tr>')
    return (f'<table><thead><tr>{tete}</tr></thead><tbody>{"".join(corps)}'
            f'</tbody></table>')


def tableau_garanties(garanties, *, avec_dates=False):
    if not garanties:
        return ''
    plus_long = max([int(g.get('duree_mois') or 0) for g in garanties] or [0])
    tete = '<th>Ce qui est garanti</th><th>Durée</th><th>Ce que cela couvre</th>'
    if avec_dates:
        tete = ('<th>Ce qui est garanti</th><th>Durée</th>'
                '<th>Jusqu\'au</th><th>Ce que cela couvre</th>')
    corps = []
    for g in garanties:
        mois = int(g.get('duree_mois') or 0)
        duree = g.get('duree_libelle') or duree_mois(mois)
        barre = ''
        if mois and plus_long:
            largeur = max(6, round(100 * mois / plus_long))
            barre = f'<div class="barre"><i style="width:{largeur}%"></i></div>'
        garant = (f'<small>{esc(g["garant"])}</small>'
                  if g.get('garant') else '')
        fin = (f'<td class="nb">{esc(date_courte(g.get("fin")))}</td>'
               if avec_dates else '')
        corps.append(
            f'<tr><td><b>{esc(g.get("designation"))}</b>{garant}</td>'
            f'<td><div class="duree">{esc(duree)}</div>{barre}</td>{fin}'
            f'<td>{esc(g.get("detail") or "")}</td></tr>')
    classe = 'garanties dates' if avec_dates else 'garanties'
    return (f'<table class="{classe}"><thead><tr>{tete}</tr></thead>'
            f'<tbody>{"".join(corps)}</tbody></table>')


def tableau_paiements(paiements, total):
    if not paiements:
        return ''
    corps = ''.join(
        f'<tr><td>{esc(date_longue(p.get("date")))}</td>'
        f'<td>{esc(p.get("libelle") or "")}</td>'
        f'<td>{esc(p.get("mode") or "")}</td>'
        f'<td class="n">{esc(montant(p.get("montant")))}</td></tr>'
        for p in paiements)
    return (f'<table><thead><tr><th>Date</th><th>Objet</th><th>Mode</th>'
            f'<th class="n">Montant</th></tr></thead><tbody>{corps}'
            f'<tr class="total"><td colspan="3">Total réglé</td>'
            f'<td class="n">{esc(montant(total))}</td></tr></tbody></table>')


# ── Articles, encadrés, cases ───────────────────────────────────────────────

def articles(liste):
    blocs = []
    for i, art in enumerate(liste or []):
        blocs.append(
            f'<div class="article"><div class="marge">'
            f'<div class="num">Article {i + 1}</div>'
            f'<h3>{esc(art.get("titre"))}</h3></div>'
            f'<div class="texte">{paragraphes(art.get("paragraphes"))}</div>'
            f'</div>')
    return ''.join(blocs)


def encadre(libelle, html_interieur, sorte=''):
    return (f'<div class="encadre {sorte}"><div class="lbl">{esc(libelle)}'
            f'</div>{html_interieur}</div>')


def cases(liste):
    """Cases à cocher : ``[{texte, cochee}]``. Une case cochée dans l'ERP
    s'imprime pleine ; une case vide reste à cocher au stylo."""
    lignes = []
    for c in liste or []:
        cochee = bool(c.get('cochee'))
        lignes.append(
            f'<div class="case{" oui" if cochee else ""}">'
            f'<i>{"✓" if cochee else ""}</i>'
            f'<span>{_gras(c.get("texte") or "")}</span></div>')
    return f'<div class="cases">{"".join(lignes)}</div>'


def lignes_a_ecrire(nombre_lignes=3):
    return '<div class="lignes">' + '<i></i>' * nombre_lignes + '</div>'


# ── Signatures ──────────────────────────────────────────────────────────────

def _boite_signature(libelle, qui, mention, signature=None):
    interieur = (f'<div class="lbl">{esc(libelle)}</div>'
                 f'<div class="qui">{esc(qui)}</div>')
    if signature and signature.get('image'):
        interieur += (f'<img class="trace" src="{esc(signature["image"])}" '
                      f'alt="signature">')
    if signature and signature.get('signe_le'):
        par = signature.get('nom') or qui
        interieur += (f'<div class="sceau">Signé le '
                      f'{esc(date_longue(signature["signe_le"]))}</div>'
                      f'<div class="preuve">par {esc(par)}'
                      f'{esc(signature.get("preuve") or "")}</div>')
    elif mention:
        interieur += f'<div class="mention">{mention}</div>'
    return f'<div class="cellule"><div class="boite">{interieur}</div></div>'


def signatures(contenu, *, mention_client, client_signe=True,
               exemplaires=True):
    societe = contenu.get('societe') or {}
    client = contenu.get('client') or {}
    sig = contenu.get('signatures') or {}
    lieu = esc(contenu.get('lieu')) or '<span class="trou">&nbsp;</span>'
    quand = (esc(date_longue(contenu.get('date_document')))
             or '<span class="trou">&nbsp;</span>')
    fait = f'Fait à {lieu}, le {quand}'
    if exemplaires and client_signe:
        fait += ', en deux exemplaires originaux, un pour chaque partie'
    boites = []
    if client_signe:
        boites.append(_boite_signature(
            'Le client', client.get('nom_complet'), mention_client,
            sig.get('client')))
    boites.append(_boite_signature(
        f'Pour {societe.get("nom_court") or societe.get("nom") or ""}',
        societe.get('representant') or societe.get('nom'),
        'Signature et cachet', sig.get('societe')))
    classe = 'sig'
    if not client_signe:
        classe = 'sig seule'
        boites.append('<div class="cellule"></div>')
    return (f'<div class="signatures"><p class="fait-a">{fait}.</p>'
            f'<div class="{classe}">{"".join(boites)}</div></div>')


# ── Pied ────────────────────────────────────────────────────────────────────

def pied(contenu, *, paraphes=True):
    societe = contenu.get('societe') or {}
    tete = ' '.join(x for x in (
        societe.get('nom'), societe.get('forme_juridique'),
        (f'au capital de {societe["capital_social"]}'
         if societe.get('capital_social') else '')) if x)
    ligne2 = ' · '.join(x for x in (
        societe.get('adresse'), societe.get('telephone'),
        societe.get('email'), societe.get('site_web')) if x)
    bloc_paraphes = ''
    if paraphes:
        bloc_paraphes = (
            '<div class="paraphes">'
            '<div class="paraphe"><span>Client</span><i></i></div>'
            '<div class="paraphe"><span>Société</span><i></i></div></div>')
    return (f'<div class="pied"><div class="pied-in"><div class="pied-legal">'
            f'<b>{esc(tete)}</b><br>'
            f'{esc(_identifiants_societe(societe, cnss=False))}'
            f'<br>{esc(ligne2)}</div><div class="pied-droite">{bloc_paraphes}'
            f'<div class="folio"><b>{esc(contenu.get("reference"))}</b>'
            f'<i></i></div>'
            f'</div></div></div>')
