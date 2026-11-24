"""Briques HTML des actes : chacune prend des valeurs simples et rend une chaîne.

Aucune ne lit la base ni ne calcule un montant : tout chiffre affiché arrive
déjà calculé dans le ``contenu`` (une seule source par valeur).

Langue : chaque brique prend ``langue`` (``'fr'`` par défaut, ``'ar'`` pour la
traduction arabe) et lit ses mots dans ``libelles`` — aucun libellé en dur.
En arabe, ``isoler_latin`` isole ensuite chaque fragment latin ou chiffré
(référence, téléphone, montant, adresse) pour que l'algorithme bidi ne le
retourne pas.
"""
import logging
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from html import escape, unescape

from . import style
from .libelles import libelle

logger = logging.getLogger(__name__)

ESPACE_FINE = '\u202f'
INSECABLE = '\u00a0'

MOIS = ('janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet',
        'août', 'septembre', 'octobre', 'novembre', 'décembre')
# Noms des mois en usage au Maroc.
MOIS_AR = ('يناير', 'فبراير', 'مارس', 'أبريل', 'ماي', 'يونيو', 'يوليوز',
           'غشت', 'شتنبر', 'أكتوبر', 'نونبر', 'دجنبر')
DEVISES = {'fr': 'DH', 'ar': 'درهم'}
A_PRECISER = {'fr': 'à préciser', 'ar': 'يُحدَّد لاحقًا'}

# L'ordre des quatre actes : (type, titre court, sous-titre du parcours).
# Les mots arabes sont dans ``libelles`` (clés ``etape_<type>``).
PARCOURS = (
    ('contrat_installation', 'Contrat', 'à la signature'),
    ('pv_livraison', 'Livraison', 'le matériel chez vous'),
    ('pv_reception', 'Réception', 'à la fin des travaux'),
    ('cloture_garanties', 'Clôture', 'garanties et conseils'),
)


def langue_de(contenu):
    """``'ar'`` pour un contenu arabe ; ``'fr'`` sinon (clé absente comprise)."""
    return 'ar' if (contenu or {}).get('langue') == 'ar' else 'fr'


def esc(valeur):
    return escape('' if valeur is None else str(valeur), quote=True)


# ── Ce qui ne se coupe jamais (texte déjà échappé) ──────────────────────────
# « n° 31-08 » (« رقم 31.08 » en arabe), un RIB, « IF 00000000 » : coupés en
# fin de ligne, ils deviennent illisibles. Leurs espaces deviennent
# insécables (le moteur de lignes les traite nativement) et le RIB part sur sa
# propre ligne. PAS de ``white-space:nowrap`` sur un morceau de phrase :
# WeasyPrint recule alors la coupure au premier mot de la ligne (« En » resté
# seul sur sa ligne, vu en faisant la revue 1). Une référence CTR-…/DEV-… n'a besoin de rien :
# un trait d'union suivi d'un chiffre n'est jamais une coupure (UAX 14, LB25).
_NUMERO_LOI = re.compile(r'(?:n°|رقم)[\s\u00a0]*\d+(?:[-.]\d+)*')
_RIB = re.compile(r'(?<=\S)[ \u00a0]+(RIB[ \u00a0]*:[ \u00a0]*'
                  r'[\d \u00a0\u202f]*\d)')


def insecable(texte):
    """Les espaces d'un morceau qui ne doit pas se couper → insécables."""
    return texte.replace(' ', INSECABLE)


def insecables(html_echappe):
    """Rend insécables les morceaux d'un texte déjà échappé qui ne doivent
    pas se couper ; le RIB passe à la ligne."""
    sortie = _RIB.sub(lambda m: '<br>' + insecable(m.group(1)), html_echappe)
    return _NUMERO_LOI.sub(lambda m: insecable(m.group()), sortie)


def texte_libre(valeur):
    """Un texte libre du ``contenu`` (modalités, engagement) : échappé, puis
    rendu insécable là où une coupure le fausserait."""
    return insecables(esc(valeur))


# ── Isolation bidi (arabe) ──────────────────────────────────────────────────
# Un fragment latin ou chiffré : commence et finit par une lettre latine ou un
# chiffre (ou « % » à la fin, « + » au début), peut contenir espaces, points,
# virgules, tirets, barres, @, apostrophes. Jamais de parenthèse ni de lettre
# arabe : « 98 500,00 درهم » isole « 98 500,00 » et laisse « درهم » à sa place.
_LATIN = 'A-Za-z0-9\u00c0-\u024f'
_FRAGMENT_LATIN = re.compile(
    f"\\+?[{_LATIN}](?:[{_LATIN}\u202f\u00a0 .,:/@'’_&+#–-]*[{_LATIN}%])?")
_TEXTE_ENTRE_BALISES = re.compile(r'>([^<]+)<')


def _isoler_texte(brut):
    morceaux, pos = [], 0
    for m in _FRAGMENT_LATIN.finditer(brut):
        morceaux.append(escape(brut[pos:m.start()], quote=False))
        morceaux.append(f'<span class="ltr">{escape(m.group(), quote=False)}'
                        f'</span>')
        pos = m.end()
    morceaux.append(escape(brut[pos:], quote=False))
    return ''.join(morceaux)


def isoler_latin(html):
    """Isole chaque fragment latin ou chiffré du ``<body>`` dans un
    ``<span class="ltr">`` (``unicode-bidi:isolate`` dans la feuille arabe).
    Le ``<head>`` (titre, feuille, polices) n'est pas touché."""
    tete, sep, corps = html.partition('<body')
    if not sep:
        return html
    corps = _TEXTE_ENTRE_BALISES.sub(
        lambda m: '>' + _isoler_texte(unescape(m.group(1))) + '<', corps)
    return tete + sep + corps


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


def nombre_de_dfaat(n):
    """Le nombre de paiements après « على » (génitif) : « دفعة واحدة »,
    « دفعتين », « 3 دفعات », « 12 دفعة »."""
    return _compte_ar(int(n or 0), 'دفعة واحدة', 'دفعتين', 'دفعات', 'دفعة')


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
        return insecables(esc(texte))
    return ''.join(insecables(m) if i % 2 == 0
                   else f'<strong>{insecables(m)}</strong>'
                   for i, m in enumerate(morceaux))


# ── En-tête, parcours, titre ────────────────────────────────────────────────

#: Emplacement du logo dans la bande d'en-tête, au sens du module image des
#: devis (``quote_engine.logo.CAPITALE_MM``) : « onepage » = la bande bleu nuit
#: d'un document d'une page — mot-marque et signature de marque, capitale 5 mm.
ROLE_LOGO = 'onepage'


def _marque(societe):
    """LE logo des devis dans l'en-tête bleu nuit : même module image (rogné
    au trait, détouré, encre sombre passée en blanc, couleurs vives gardées),
    même bloc et même taille que la bande d'en-tête d'un devis — lu par la
    porte de ventes (``selectors.logo_entete_html``), jamais par un import du
    moteur (règle n° 4). Le fichier téléversé n'est JAMAIS imprimé tel quel :
    sans logo exploitable (aucun, SVG, corrompu), c'est le nom de la société."""
    societe = societe or {}
    uri = societe.get('logo_uri')
    if isinstance(uri, str) and uri:
        try:
            from apps.ventes.selectors import logo_entete_html
            image = logo_entete_html(uri, variante='sombre', role=ROLE_LOGO,
                                     alt=str(societe.get('nom') or 'logo'))
            if image:
                return image
        except Exception:  # logo inexploitable : le nom, jamais une image cassée
            logger.warning('Logo de la société inexploitable : le nom est '
                           'imprimé à sa place', exc_info=True)
    return esc(societe.get('nom'))


def bandeau(contenu):
    langue = langue_de(contenu)
    societe = contenu.get('societe') or {}
    chantier = contenu.get('chantier') or {}
    lignes = [f'<b>{esc(contenu.get("reference"))}</b>']
    if chantier.get('reference'):
        lignes.append(libelle('chantier', langue,
                              ref=esc(chantier['reference'])))
    if contenu.get('date_document'):
        lignes.append(esc(date_longue(contenu['date_document'], langue)))
    return (f'<div class="bandeau"><div class="marque">{_marque(societe)}</div>'
            f'<div class="ref">{"<br>".join(lignes)}</div></div>')


def _etape(type_acte, langue):
    """(titre court, sous-titre) d'un acte dans le parcours."""
    return (libelle(f'etape_{type_acte}', langue),
            libelle(f'etape_{type_acte}_sous', langue))


def parcours(type_acte, langue='fr'):
    types = [t for t, _, _ in PARCOURS]
    rang = types.index(type_acte)
    etapes = []
    for i, type_i in enumerate(types):
        titre_i, sous = _etape(type_i, langue)
        classe = 'ici' if i == rang else ('fait' if i < rang else '')
        etapes.append(
            f'<div class="etape {classe}"><span class="n">{i + 1}</span>'
            f'<span>{esc(titre_i)}<small>{esc(sous)}</small></span></div>')
    return f'<div class="parcours">{"".join(etapes)}</div>'


def titre(type_acte, h1, chapeau, reference='', langue='fr'):
    rang = [t for t, _, _ in PARCOURS].index(type_acte) + 1
    court = _etape(type_acte, langue)[0]
    surtitre = libelle('surtitre', langue, rang=rang, court=esc(court))
    # La référence de l'en-tête courant (pages 2 et suivantes) : ``string-set``
    # n'est lu que sur un élément MIS EN PAGE — d'où un élément visible de
    # hauteur nulle, jamais un ``display:none`` (revue 1, R7).
    return (f'<div class="titre"><div class="surtitre">{surtitre}</div>'
            f'<div class="reference-courante">{esc(reference)}'
            f'</div><h1>{esc(h1)}</h1><p class="chapeau">{chapeau}</p></div>')


def h2(texte, intro=''):
    bloc = f'<h2>{style.etoile_svg()}{esc(texte)}</h2>'
    if intro:
        bloc += f'<p class="intro">{intro}</p>'
    return bloc


# ── Cartes de l'essentiel ───────────────────────────────────────────────────

def carte(libelle_carte, valeur, detail='', *, forte=False, large=False):
    classes = 'carte' + (' forte' if forte else '') + (' large' if large else '')
    det = f'<div class="det">{detail}</div>' if detail else ''
    return (f'<div class="{classes}"><div class="lbl">{esc(libelle_carte)}</div>'
            f'<div class="val">{valeur}</div>{det}</div>')


def cartes(*blocs):
    return f'<div class="cartes">{"".join(b for b in blocs if b)}</div>'


# ── Frise de paiement ───────────────────────────────────────────────────────

ETATS_TRANCHE = {
    'regle': 'Réglé',
    'exigible': 'À régler',
    'a_venir': 'À venir',
}


def _mot_etat(etat, langue):
    if etat not in ETATS_TRANCHE:
        etat = 'a_venir'
    return libelle(f'etat_{etat}', langue)


def frise(echeancier, *, avec_etats=False, langue='fr'):
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
            mot = _mot_etat(etat, langue)
            if etat == 'regle' and tr.get('regle_le'):
                mot = libelle('regle_le', langue, mot=mot,
                              date=date_longue(tr['regle_le'], langue))
            bloc_etat = f'<div class="etat">{esc(mot)}</div>'
        note = (f'<div class="note">{esc(tr["note"])}</div>'
                if tr.get('note') else '')
        jalons.append(
            f'<div class="{classe}"><div class="tete">'
            f'<span class="pastille">{i + 1}</span><span class="trait"></span>'
            f'</div><div class="quand">{esc(tr.get("exigibilite"))}</div>'
            f'<div class="quoi">{esc(tr.get("libelle"))}</div>'
            f'<div class="combien">'
            f'{esc(montant(tr.get("montant_ttc"), langue=langue))}'
            f'{petit}</div>{bloc_etat}{note}</div>')
    return f'<div class="frise">{"".join(jalons)}</div>'


# ── Parties ─────────────────────────────────────────────────────────────────

def _lignes(*valeurs):
    return '<br>'.join(esc(v) for v in valeurs if v)


def _identifiants_societe(societe, *, cnss=True, langue='fr'):
    paires = [('id_rc', societe.get('rc')), ('id_ice', societe.get('ice')),
              ('id_if', societe.get('identifiant_fiscal')),
              ('id_patente', societe.get('patente'))]
    if cnss:
        paires.append(('id_cnss', societe.get('cnss')))
    # Libellé et numéro liés par une espace insécable : « IF 00000000 » ne se
    # coupe jamais en fin de ligne.
    return ' · '.join(f'{libelle(k, langue)}{INSECABLE}{v}'
                      for k, v in paires if v)


def _forme_capital(societe, langue):
    return ' '.join(x for x in (
        societe.get('forme_juridique'),
        (libelle('au_capital', langue, capital=societe['capital_social'])
         if societe.get('capital_social') else '')) if x)


def partie_societe(societe, role=None, langue='fr'):
    role = role or libelle('installateur', langue)
    forme = _forme_capital(societe, langue)
    represente = (libelle('representee_par', langue,
                          nom=societe['representant'])
                  if societe.get('representant') else '')
    lignes = _lignes(forme, societe.get('adresse'),
                     _identifiants_societe(societe, langue=langue), represente)
    court = esc(societe.get('nom_court') or societe.get('nom'))
    return (f'<div class="partie"><div class="lbl">{esc(role)}</div>'
            f'<div class="nom">{esc(societe.get("nom"))}</div>{lignes}'
            f'<div class="ci-apres">{libelle("ci_apres", langue, nom=court)}'
            f'</div></div>')


def _cin(client, langue):
    """« CIN BK000000 », ou la ligne à remplir au stylo (texte brut)."""
    if client.get('cin'):
        return f'{libelle("id_cin", langue)}{INSECABLE}{client["cin"]}'
    return libelle('cin_a_remplir', langue)


def partie_client(client, role=None, langue='fr'):
    role = role or libelle('le_client', langue)
    entreprise = client.get('type') == 'entreprise'
    if entreprise:
        ident = ' · '.join(f'{libelle(k, langue)}{INSECABLE}{v}' for k, v in (
            ('id_rc', client.get('rc')), ('id_ice', client.get('ice')),
            ('id_if', client.get('if_fiscal'))) if v)
        represente = (libelle('representee_par', langue,
                              nom=client['representant'])
                      if client.get('representant') else '')
    else:
        ident = _cin(client, langue)
        represente = ''
    contact = ' · '.join(x for x in (client.get('telephone'),
                                     client.get('email')) if x)
    return (f'<div class="partie"><div class="lbl">{esc(role)}</div>'
            f'<div class="nom">{esc(client.get("nom_complet"))}</div>'
            f'{_lignes(ident, client.get("adresse"), contact, represente)}'
            f'<div class="ci-apres">{libelle("ci_apres_client", langue)}'
            f'</div></div>')


def parties(contenu):
    langue = langue_de(contenu)
    societe = partie_societe(contenu.get('societe') or {}, langue=langue)
    client = partie_client(contenu.get('client') or {}, langue=langue)
    return f'<div class="parties">{societe}{client}</div>'


# ── Tableaux ────────────────────────────────────────────────────────────────

def _th(cle, langue, classe=''):
    attr = f' class="{classe}"' if classe else ''
    return f'<th{attr}>{libelle(cle, langue)}</th>'


def tableau_materiel(lignes, *, avec_series=False, langue='fr'):
    if not lignes:
        return ''
    tete = (_th('th_designation', langue) + _th('th_marque', langue)
            + (_th('th_serie', langue) if avec_series else '')
            + _th('th_quantite', langue, 'n'))
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


def tableau_garanties(garanties, *, avec_dates=False, langue='fr'):
    if not garanties:
        return ''
    plus_long = max([int(g.get('duree_mois') or 0) for g in garanties] or [0])
    tete = (_th('th_garanti', langue) + _th('th_duree', langue)
            + (_th('th_jusquau', langue) if avec_dates else '')
            + _th('th_couvre', langue))
    corps = []
    for g in garanties:
        mois = int(g.get('duree_mois') or 0)
        duree = g.get('duree_libelle') or duree_mois(mois, langue)
        barre = ''
        if mois and plus_long:
            largeur = max(6, round(100 * mois / plus_long))
            barre = f'<div class="barre"><i style="width:{largeur}%"></i></div>'
        garant = (f'<small>{esc(g["garant"])}</small>'
                  if g.get('garant') else '')
        fin = (f'<td class="nb">{esc(date_longue(g.get("fin"), langue))}</td>'
               if avec_dates else '')
        corps.append(
            f'<tr><td><b>{esc(g.get("designation"))}</b>{garant}</td>'
            f'<td><div class="duree">{esc(duree)}</div>{barre}</td>{fin}'
            f'<td>{esc(g.get("detail") or "")}</td></tr>')
    classe = 'garanties dates' if avec_dates else 'garanties'
    return (f'<table class="{classe}"><thead><tr>{tete}</tr></thead>'
            f'<tbody>{"".join(corps)}</tbody></table>')


def tableau_paiements(paiements, total, langue='fr'):
    if not paiements:
        return ''
    corps = ''.join(
        f'<tr><td>{esc(date_longue(p.get("date"), langue))}</td>'
        f'<td>{esc(p.get("libelle") or "")}</td>'
        f'<td>{esc(p.get("mode") or "")}</td>'
        f'<td class="n">{esc(montant(p.get("montant"), langue=langue))}</td>'
        f'</tr>' for p in paiements)
    tete = (_th('th_date', langue) + _th('th_objet', langue)
            + _th('th_mode', langue) + _th('th_montant', langue, 'n'))
    return (f'<table><thead><tr>{tete}</tr></thead><tbody>{corps}'
            f'<tr class="total"><td colspan="3">'
            f'{libelle("total_regle", langue)}</td>'
            f'<td class="n">{esc(montant(total, langue=langue))}</td></tr>'
            f'</tbody></table>')


# ── Articles, encadrés, cases ───────────────────────────────────────────────

# Un article court ne se coupe pas entre deux pages (revue 1, R8) : au plus
# trois paragraphes et 480 signes (six lignes environ, en arabe comme en
# français) : un bloc insécable plus long laissait jusqu'à 50 mm de blanc en
# bas de page. Au-delà, orphelines et veuves (2) évitent la ligne isolée.
ARTICLE_COURT_PARAGRAPHES = 3
ARTICLE_COURT_SIGNES = 480


def _court(art):
    textes = [str(p) for p in art.get('paragraphes') or []]
    return (len(textes) <= ARTICLE_COURT_PARAGRAPHES
            and sum(len(t) for t in textes) <= ARTICLE_COURT_SIGNES)


def articles(liste, langue='fr', annexes=None):
    """Les articles, titre en marge. ``annexes`` : ``{cle: html}`` ajouté au
    bas de la colonne de l'article ``cle`` (la carte du service après-vente
    sous « Qui appeler »)."""
    annexes = annexes or {}
    blocs = []
    for i, art in enumerate(liste or []):
        classe = 'article court' if _court(art) else 'article'
        blocs.append(
            f'<div class="{classe}"><div class="marge">'
            f'<div class="num">{libelle("article", langue, n=i + 1)}</div>'
            f'<h3>{esc(art.get("titre"))}</h3></div>'
            f'<div class="texte">{paragraphes(art.get("paragraphes"))}'
            f'{annexes.get(art.get("cle"), "")}</div></div>')
    return ''.join(blocs)


def bloc_insecable(html_interieur):
    """Un bloc qui ne se coupe pas entre deux pages (titre + frise + encadré
    du montant). Un bloc, jamais un flex : WeasyPrint pousse à la page
    suivante un conteneur flex insécable même quand il tient."""
    return f'<div class="insecable">{html_interieur}</div>'


def encadre_montant(libelle_encadre, chiffre, explication, sorte=''):
    """L'encadré d'un montant : son libellé et le chiffre d'un côté, ce qu'il
    veut dire de l'autre (une table : jamais un flex insécable) — la place
    d'une ligne gagnée sur les procès-verbaux. Sans explication, le chiffre
    seul, comme un encadré ordinaire."""
    tete = f'<div class="lbl">{esc(libelle_encadre)}</div>'
    if not explication:
        return f'<div class="encadre montant {sorte}">{tete}{chiffre}</div>'
    return (f'<div class="encadre montant {sorte}"><div class="deux">'
            f'<div class="chiffre">{tete}{chiffre}</div>'
            f'<div class="explication">{explication}</div></div></div>')


def encadre(libelle_encadre, html_interieur, sorte=''):
    return (f'<div class="encadre {sorte}"><div class="lbl">'
            f'{esc(libelle_encadre)}</div>{html_interieur}</div>')


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


def a_remplir(texte):
    """Un libellé dont les points de suspension (« ………… ») sont à remplir au
    stylo : échappé, puis chaque suite de points devient un trait pointillé
    sur lequel on écrit."""
    return re.sub('…{2,}', '<span class="a-remplir"></span>', esc(texte))


def lignes_a_ecrire(nombre_lignes=3):
    return '<div class="lignes">' + '<i></i>' * nombre_lignes + '</div>'


# ── Signatures ──────────────────────────────────────────────────────────────

def _boite_signature(libelle_boite, qui, mention, signature=None, langue='fr',
                     ident=''):
    interieur = (f'<div class="lbl">{esc(libelle_boite)}</div>'
                 f'<div class="qui">{esc(qui)}</div>')
    if ident:
        interieur += f'<div class="ident">{esc(ident)}</div>'
    if signature and signature.get('image'):
        interieur += (f'<img class="trace" src="{esc(signature["image"])}" '
                      f'alt="{esc(libelle("alt_signature", langue))}">')
    if signature and signature.get('signe_le'):
        par = signature.get('nom') or qui
        quand = esc(date_longue(signature['signe_le'], langue))
        interieur += (f'<div class="sceau">'
                      f'{libelle("signe_le", langue, date=quand)}</div>'
                      f'<div class="preuve">'
                      f'{libelle("signe_par", langue, nom=esc(par))}'
                      f'{esc(signature.get("preuve") or "")}</div>')
    elif mention:
        interieur += f'<div class="mention">{mention}</div>'
    return f'<div class="cellule"><div class="boite">{interieur}</div></div>'


def signatures(contenu, *, mention_client, client_signe=True,
               exemplaires=True):
    langue = langue_de(contenu)
    societe = contenu.get('societe') or {}
    client = contenu.get('client') or {}
    sig = contenu.get('signatures') or {}
    lieu = esc(contenu.get('lieu')) or '<span class="trou">&nbsp;</span>'
    quand = (esc(date_longue(contenu.get('date_document'), langue))
             or '<span class="trou">&nbsp;</span>')
    fait = libelle('fait_a', langue, lieu=lieu, quand=quand)
    if exemplaires and client_signe:
        fait += libelle('exemplaires', langue)
    boites = []
    if client_signe:
        # Sous le nom du client particulier, son numéro de CIN (ou la ligne à
        # remplir) : qui signe est identifié dans le cadre même (revue 1, R5).
        ident = ('' if client.get('type') == 'entreprise'
                 else _cin(client, langue))
        boites.append(_boite_signature(
            libelle('le_client', langue), client.get('nom_complet'),
            mention_client, sig.get('client'), langue, ident))
    boites.append(_boite_signature(
        libelle('pour_societe', langue,
                nom=societe.get('nom_court') or societe.get('nom') or ''),
        societe.get('representant') or societe.get('nom'),
        libelle('signature_cachet', langue), sig.get('societe'), langue))
    classe = 'sig'
    if not client_signe:
        classe = 'sig seule'
        boites.append('<div class="cellule"></div>')
    return (f'<div class="signatures"><p class="fait-a">{fait}.</p>'
            f'<div class="{classe}">{"".join(boites)}</div></div>')


# ── Pied ────────────────────────────────────────────────────────────────────

def pied(contenu, *, paraphes=True):
    langue = langue_de(contenu)
    societe = contenu.get('societe') or {}
    tete = ' '.join(x for x in (
        societe.get('nom'), _forme_capital(societe, langue)) if x)
    # Quatre lignes voulues (identité, identifiants, adresse, contact), dont
    # chaque élément est insécable : la ligne se coupe ENTRE deux éléments,
    # jamais au milieu d'un numéro de téléphone.

    def ligne(*valeurs):
        return ' · '.join(insecable(esc(v)) for v in valeurs if v)
    lignes_legales = [x for x in (
        f'<b>{esc(tete)}</b>',
        esc(_identifiants_societe(societe, cnss=False, langue=langue)),
        esc(societe.get('adresse') or ''),
        ligne(societe.get('telephone'), societe.get('email'),
              societe.get('site_web'))) if x]
    bloc_paraphes = ''
    if paraphes:
        bloc_paraphes = (
            '<div class="paraphes">'
            f'<div class="paraphe"><span>{libelle("paraphe_client", langue)}'
            '</span><i></i></div>'
            f'<div class="paraphe"><span>{libelle("paraphe_societe", langue)}'
            '</span><i></i></div></div>')
    return (f'<div class="pied"><div class="pied-in"><div class="pied-legal">'
            f'{"<br>".join(lignes_legales)}'
            f'</div><div class="pied-droite">{bloc_paraphes}'
            f'<div class="folio"><b>{esc(contenu.get("reference"))}</b>'
            f'<i></i></div>'
            f'</div></div></div>')
