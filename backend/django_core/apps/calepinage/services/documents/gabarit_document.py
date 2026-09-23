"""CALX294 — le GABARIT SOCIÉTÉ des documents du module calepinage.

Le constat
==========
``core.pdf.render_pdf`` sait poser un bandeau brandé, mais il est OPT-IN et les
deux appelants du module le laissent à ``False`` ; la note de calcul n'imprime
ni logo ni raison sociale, et ``core.models.TenantTheme`` (logo, couleurs, nom
affiché) n'était lu par AUCUN rendu du module. Une pièce technique remise sans
l'identité de la société qui l'émet est une pièce anonyme.

Ce que ce module fait
=====================
* ``styles_de_societe(company)`` — la marque de la société, LUE : le thème
  white-label ``TenantTheme`` d'abord, puis le profil société
  (``apps.parametres.selectors.company_identity``) pour le NOM seulement, puis
  la raison sociale de ``Company`` ;
* ``entete_html`` / ``pied_html`` — deux éléments COURANTS
  (``position: running(...)``) que ``css_du_gabarit`` place dans les boîtes de
  marge ``@top-center`` et ``@bottom-left`` : ils se répètent donc sur CHAQUE
  page, comme l'empreinte de la note de calcul (CAL176) ;
* ``document_html(corps, ...)`` — habille un corps HTML de ce gabarit ; c'est
  l'unique chemin par lequel une pièce du lot 6 reçoit sa marque.

Zéro couleur inventée
=====================
Un thème ABSENT rend un document SANS logo et SANS couleur société : traits et
titres restent au noir/gris de la charte d'impression EXISTANTE (celle de la
note de calcul). Le profil société ne complète QUE le nom : son champ
``couleur_principale`` porte un DÉFAUT de modèle, qui n'est pas une saisie — le
reprendre ferait imprimer une couleur que personne n'a choisie. Pour la même
raison, un nom de profil resté au défaut du modèle est traité comme ABSENT.

Une couleur qui n'est pas un hexadécimal ``#rgb``/``#rrggbb`` est ABSENTE :
elle part dans une feuille CSS, où une valeur libre serait une injection. Un
logo qui n'est pas une URL ``http(s)://`` ou ``data:image/`` est ABSENT : un
simple chemin de stockage ne se résout pas au rendu, et le module n'invente
pas l'adresse qui lui manque.

Aucune marque n'est écrite ici en dur : tout nom affiché vient de la société.
"""
from __future__ import annotations

import re
from collections.abc import Mapping
from html import escape

from ..note_calcul import _pied_de_page
from ..planche import hash_court

__all__ = [
    'NOIR', 'GRIS_TEXTE', 'GRIS_TRAIT', 'GRIS_FOND', 'CHARTE_IMPRESSION',
    'CLES_STYLES', 'styles_vides', 'couleur_valide', 'logo_valide',
    'styles_de_societe', 'entete_html', 'pied_html', 'css_du_gabarit',
    'document_html',
    # CALX295 — la page de garde
    'LIBELLES_GARDE_FR', 'CHAMPS_GARDE', 'page_de_garde_html',
    'identite_du_calepinage',
    # CALX325 — conception verrouillée / archivée
    'MENTION_VERROUILLE', 'MENTION_ARCHIVE', 'DATE_NON_ENREGISTREE',
    'ETAT_COURANT', 'etat_de_conception', 'mentions_d_etat',
]

# ── La charte d'impression EXISTANTE (note de calcul, CAL176) ───────────────
#: Les SEULS codes couleur écrits dans ce module : noir et gris d'impression.
#: Toute autre couleur vient du thème de la société, ou n'existe pas.
NOIR = '#111'
GRIS_TEXTE = '#555'
GRIS_TRAIT = '#999'
GRIS_FOND = '#f2f2f2'
CHARTE_IMPRESSION = (NOIR, GRIS_TEXTE, GRIS_TRAIT, GRIS_FOND)

#: Les clés d'une marque société — toujours présentes, ``''`` quand absentes.
CLES_STYLES = ('nom_affiche', 'logo_url', 'couleur_primaire',
               'couleur_secondaire')

_COULEUR = re.compile(r'^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$')
_SCHEMAS_LOGO = ('https://', 'http://', 'data:image/')
_CARACTERES_REFUSES_LOGO = ('"', "'", '<', '>', '\\', ' ', '\n', '\r', '\t')

#: Sentinelle « lire en base » — distingue « non fourni » de ``None``.
_LIRE = object()


def styles_vides():
    """Une marque VIDE : aucune clé ne manque, aucune ne vaut quoi que ce soit."""
    return {cle: '' for cle in CLES_STYLES}


def couleur_valide(valeur):
    """``valeur`` si c'est un hexadécimal ``#rgb``/``#rrggbb``, sinon ``''``."""
    texte = str(valeur or '').strip()
    return texte if _COULEUR.match(texte) else ''


def logo_valide(valeur):
    """``valeur`` si c'est une URL d'image imprimable, sinon ``''``."""
    texte = str(valeur or '').strip()
    if not texte or any(c in texte for c in _CARACTERES_REFUSES_LOGO):
        return ''
    return texte if texte.lower().startswith(_SCHEMAS_LOGO) else ''


def _attr(source, cle):
    """Lit ``cle`` sur un dict OU un objet (instance de modèle) — ``''`` sinon."""
    if source is None:
        return ''
    valeur = (source.get(cle) if isinstance(source, Mapping)
              else getattr(source, cle, None))
    if valeur is None:
        return ''
    return str(valeur).strip()


def _theme_de(company):
    """Le ``TenantTheme`` de la société, ou ``None`` — ne lève jamais."""
    if company is None:
        return None
    try:
        from core.models import TenantTheme

        return TenantTheme.objects.filter(company=company).first()
    except Exception:  # noqa: BLE001 — un logo ne fait jamais tomber une pièce
        return None


def _defaut_nom_profil():
    """Le défaut DÉCLARÉ par le modèle pour ``CompanyProfile.nom`` (introspection)."""
    try:
        from apps.parametres.models_company import CompanyProfile

        return CompanyProfile._meta.get_field('nom').default
    except Exception:  # noqa: BLE001
        return None


def _profil_de(company):
    """L'identité du profil société (``company_identity``), ou ``{}``.

    Un nom égal au défaut du modèle n'est pas une saisie : il est vidé, pour
    que la raison sociale de ``Company`` prenne le relais.
    """
    if company is None:
        return {}
    try:
        from apps.parametres.selectors import company_identity

        profil = dict(company_identity(company) or {})
    except Exception:  # noqa: BLE001
        return {}
    nom = (profil.get('nom') or '').strip()
    if nom and nom == _defaut_nom_profil():
        profil['nom'] = ''
    return profil


def styles_de_societe(company, *, theme=_LIRE, profil=_LIRE):
    """La marque à imprimer : ``{nom_affiche, logo_url, couleur_primaire,
    couleur_secondaire}``, chaque clé à ``''`` quand rien n'est saisi.

    ``company`` est une ``authentication.Company`` — ou, pour les essais sans
    base, un dictionnaire ``{'theme': …, 'profil': …}`` déjà lu
    (``styles_de_societe({})`` rend une marque vide). ``theme``/``profil``
    permettent à l'appelant qui les a déjà lus de ne pas les relire.

    Repli CHAMP PAR CHAMP : le nom affiché du thème, sinon le nom du profil,
    sinon la raison sociale ; logo et couleurs viennent du thème SEUL.
    """
    raison_sociale = ''
    if isinstance(company, Mapping):
        theme = company.get('theme') if theme is _LIRE else theme
        profil = company.get('profil') if profil is _LIRE else profil
    else:
        if theme is _LIRE:
            theme = _theme_de(company)
        if profil is _LIRE:
            profil = _profil_de(company)
        raison_sociale = _attr(company, 'nom')
    profil = profil or {}
    return {
        'nom_affiche': (_attr(theme, 'nom_affichage') or _attr(profil, 'nom')
                        or raison_sociale),
        'logo_url': logo_valide(_attr(theme, 'logo_url')),
        'couleur_primaire': couleur_valide(_attr(theme, 'couleur_primaire')),
        'couleur_secondaire': couleur_valide(
            _attr(theme, 'couleur_secondaire')),
    }


# ── Les deux éléments courants ──────────────────────────────────────────────

def entete_html(styles, *, titre=''):
    """L'en-tête courant (logo, nom affiché, titre de la pièce), ou ``''``.

    Placé dans la boîte ``@top-center`` par ``css_du_gabarit`` : il se répète
    sur chaque page. Rien n'est imprimé pour une valeur absente — ni balise
    vide, ni texte de remplacement.
    """
    styles = styles or {}
    nom = str(styles.get('nom_affiche') or '').strip()
    morceaux = []
    logo = logo_valide(styles.get('logo_url'))
    if logo:
        morceaux.append('<img class="gabarit-logo" src="%s" alt="%s">'
                        % (escape(logo, quote=True),
                           escape(nom or 'logo', quote=True)))
    if nom:
        morceaux.append('<span class="gabarit-nom">%s</span>' % escape(nom))
    titre = str(titre or '').strip()
    if titre:
        morceaux.append('<span class="gabarit-titre">%s</span>'
                        % escape(titre))
    if not morceaux:
        return ''
    return '<div class="gabarit-entete">%s</div>' % ''.join(morceaux)


def pied_html(provenance, *, mentions=(), etat=None):
    """Le pied courant : l'empreinte (entrée · moteur · date), puis les mentions.

    L'empreinte reprend la graphie de la note de calcul (``_pied_de_page``) :
    une troisième façon d'écrire la même empreinte serait une troisième vérité.
    Les ``mentions`` (repli de langue…) puis celles de l'``etat`` de la
    conception (CALX325 : verrouillée, archivée) s'impriment une fois
    chacune, dans l'ordre reçu, sans doublon.
    """
    lignes = []
    empreinte = _pied_de_page(provenance or {})
    if empreinte:
        lignes.append(empreinte)
    for mention in list(mentions or ()) + mentions_d_etat(etat):
        texte = str(mention or '').strip()
        if texte and texte not in lignes:
            lignes.append(texte)
    if not lignes:
        return ''
    return '<div class="gabarit-pied">%s</div>' % ''.join(
        '<div>%s</div>' % escape(ligne) for ligne in lignes)


def css_du_gabarit(styles, *, format_page='A4'):
    """La feuille du gabarit : boîtes de marge, pagination, typographie.

    La couleur primaire de la société souligne l'en-tête et les titres ; sans
    thème, ce sont le noir et le gris de la charte d'impression.
    """
    styles = styles or {}
    primaire = couleur_valide(styles.get('couleur_primaire')) or NOIR
    secondaire = couleur_valide(styles.get('couleur_secondaire')) or GRIS_TRAIT
    return ''.join([
        '@page{size:', format_page, ';margin:24mm 14mm 20mm 14mm;',
        '@top-center{content:element(gabarit-entete);vertical-align:bottom;}',
        '@bottom-left{content:element(gabarit-pied);vertical-align:top;}',
        '@bottom-right{content:"page " counter(page) " / " counter(pages);',
        'font-size:7pt;color:', GRIS_TEXTE, ';}}',
        '.gabarit-entete{position:running(gabarit-entete);width:100%;',
        'border-bottom:0.6mm solid ', primaire, ';padding-bottom:1.5mm;',
        'font-size:8pt;color:', NOIR, ';}',
        '.gabarit-logo{max-height:11mm;max-width:40mm;vertical-align:middle;',
        'margin-right:3mm;}',
        '.gabarit-nom{font-weight:bold;margin-right:3mm;}',
        '.gabarit-titre{color:', GRIS_TEXTE, ';}',
        '.gabarit-pied{position:running(gabarit-pied);font-size:7pt;color:',
        GRIS_TEXTE, ';border-top:0.2mm solid ', secondaire,
        ';padding-top:1mm;}',
        'body{font-family:"DejaVu Sans",Arial,sans-serif;font-size:9pt;',
        'color:', NOIR, ';}',
        'h1{font-size:15pt;margin:0 0 2mm 0;color:', primaire, ';}',
        'h2{font-size:11pt;margin:6mm 0 2mm 0;border-bottom:0.4mm solid ',
        primaire, ';}',
        'table{width:100%;border-collapse:collapse;margin-bottom:2mm;}',
        'th,td{border:0.2mm solid ', GRIS_TRAIT, ';padding:1.2mm;',
        'text-align:left;vertical-align:top;}',
        'th{background:', GRIS_FOND, ';font-weight:bold;}',
        '.note{color:', GRIS_TEXTE, ';font-size:8pt;}',
    ])


def document_html(corps, *, titre, styles=None, provenance=None, mentions=(),
                  langue='fr', css='', etat=None):
    """Un document HTML AUTONOME habillé du gabarit société.

    Les deux éléments courants sont posés EN TÊTE du ``<body>`` : un élément
    courant ne paraît qu'à partir de la page où il est rencontré, il doit donc
    précéder tout contenu. ``css`` est la feuille propre à la pièce, ajoutée
    APRÈS celle du gabarit. ``etat`` (CALX325, ``etat_de_conception``) fait
    porter au pied de CHAQUE page la mention « verrouillée »/« archivée ».
    """
    styles = styles or styles_vides()
    return ''.join([
        '<!doctype html><html lang="', escape(langue or 'fr', quote=True),
        '"><head><meta charset="utf-8"><title>', escape(titre or ''),
        '</title><style>', css_du_gabarit(styles), css or '',
        '</style></head><body>',
        entete_html(styles, titre=titre),
        pied_html(provenance, mentions=mentions, etat=etat),
        corps or '',
        '</body></html>',
    ])


# ═══════════════════════════════════════════════════════════════════════════
# CALX295 — LA PAGE DE GARDE : identité société et projet
# ═══════════════════════════════════════════════════════════════════════════
#
# ``construire_note_calcul`` rangeait une identité dans la note sans que
# ``html_de_note_calcul`` ne l'imprime NULLE PART : la pièce sortait sans nom
# de société, sans client, sans date. La garde imprime ce qui est CONNU, et
# BARRE ce qui ne l'est pas : une valeur absente reste visible comme absente
# (son libellé barré, « non renseigné »), jamais remplacée par un texte qui
# aurait l'air d'une donnée.

#: Libellés français de la garde. ``page_de_garde_html(libelles=…)`` accepte
#: la table d'une autre langue (CALX296), clé par clé.
LIBELLES_GARDE_FR = {
    'titre_defaut': 'Document technique du calepinage',
    'societe': 'Société',
    'projet': 'Projet',
    'client': 'Client',
    'adresse': 'Adresse du site',
    'ville': 'Ville',
    'produit_le': 'Date de production',
    'empreinte': "Empreinte d'entrée",
    'version_moteur': 'Version du moteur',
    'non_renseigne': 'non renseigné',
}

#: Les lignes de la garde, dans l'ordre d'impression.
CHAMPS_GARDE = ('societe', 'projet', 'client', 'adresse', 'ville',
                'produit_le', 'empreinte', 'version_moteur')


def _texte(valeur):
    """Une valeur imprimable, ou ``''`` — ``None`` n'est jamais écrit."""
    if valeur is None:
        return ''
    return str(valeur).strip()


def page_de_garde_html(identite, site, provenance, styles, *, libelles=None):
    """La page de garde : UN ``<h1>``, puis une table identité / empreinte.

    Args:
        identite: ``{titre_document, projet, client, produit_le}`` — composée
            par ``identite_du_calepinage`` ; aucune clé n'est obligatoire.
        site: le contexte géographique (``selectors.contexte_geographique`` :
            ``adresse``, ``ville``) — des données de SITE, jamais recalculées.
        provenance: ``{hash_entree, version_moteur}`` — l'empreinte est
            imprimée COURTE (``planche.hash_court``, la graphie des planches).
        styles: la marque (``styles_de_societe``) — nom affiché et logo.
        libelles: la table de libellés d'une autre langue (CALX296).

    La garde se termine par un saut de page : le corps de la pièce commence
    toujours sur la page suivante.
    """
    identite = identite if isinstance(identite, Mapping) else {}
    site = site if isinstance(site, Mapping) else {}
    provenance = provenance if isinstance(provenance, Mapping) else {}
    styles = styles if isinstance(styles, Mapping) else {}
    textes = dict(LIBELLES_GARDE_FR)
    textes.update({cle: valeur for cle, valeur in (libelles or {}).items()
                   if _texte(valeur)})

    valeurs = {
        'societe': _texte(styles.get('nom_affiche')),
        'projet': _texte(identite.get('projet')),
        'client': _texte(identite.get('client')),
        'adresse': _texte(site.get('adresse')),
        'ville': _texte(site.get('ville')),
        'produit_le': _texte(identite.get('produit_le')),
        'empreinte': hash_court(_texte(provenance.get('hash_entree')
                                       or provenance.get('entree_hash'))),
        'version_moteur': _texte(provenance.get('version_moteur')),
    }
    lignes = []
    for champ in CHAMPS_GARDE:
        libelle = escape(textes[champ])
        valeur = valeurs[champ]
        if valeur:
            lignes.append('<tr><th>%s</th><td>%s</td></tr>'
                          % (libelle, escape(valeur)))
        else:
            lignes.append('<tr class="absent"><th><s>%s</s></th><td>%s</td>'
                          '</tr>' % (libelle, escape(textes['non_renseigne'])))

    titre = _texte(identite.get('titre_document')) or textes['titre_defaut']
    logo = logo_valide(styles.get('logo_url'))
    bloc_logo = ('<p class="garde-logo"><img src="%s" alt="%s"></p>'
                 % (escape(logo, quote=True),
                    escape(valeurs['societe'] or 'logo', quote=True))
                 if logo else '')
    return ('<section class="page-de-garde" '
            'style="break-after:page;page-break-after:always;">'
            '%s<h1>%s</h1><table class="garde">%s</table></section>'
            % (bloc_logo, escape(titre), ''.join(lignes)))


def identite_du_calepinage(calepinage, *, titre_document='', moment=None):
    """L'identité d'une pièce : projet, client et date de production — LUS.

    Le client est lu par les sélecteurs du CRM (``client_label``, sinon le
    lead d'origine), bornés à la société du calepinage — jamais un import de
    ``apps.crm.models``. ``moment`` est fourni par l'appelant pour un rendu
    reproductible ; à défaut, c'est l'heure LOCALE du serveur (aware), jamais
    un constructeur naïf.
    """
    company = getattr(calepinage, 'company', None)
    client = ''
    try:
        from apps.crm.selectors import client_label, get_company_lead

        client = _texte(client_label(
            company, getattr(calepinage, 'client_id', None)))
        if not client:
            lead = get_company_lead(company,
                                    getattr(calepinage, 'lead_id', None))
            if lead is not None:
                client = ' '.join(filter(None, (
                    _texte(getattr(lead, 'prenom', '')),
                    _texte(getattr(lead, 'nom', '')))))
    except Exception:  # noqa: BLE001 — une garde sans client reste une garde
        client = ''
    if moment is None:
        from django.utils import timezone

        moment = timezone.localtime(timezone.now())
    return {
        'titre_document': _texte(titre_document),
        'projet': _texte(getattr(calepinage, 'titre', '')),
        'client': client,
        'produit_le': moment.strftime('%d/%m/%Y'),
    }


# ═══════════════════════════════════════════════════════════════════════════
# CALX325 — la pièce DIT qu'elle vient d'une conception verrouillée/archivée
# ═══════════════════════════════════════════════════════════════════════════
#
# Le verrou de lecture seule (``services/verrou.py``) et l'archivage
# (``services/archivage.py``) existent, mais aucun document ne les
# mentionnait : une pièce d'un calepinage archivé se téléchargeait sans rien
# qui la distingue d'une pièce courante. La mention vient de l'état RÉEL servi
# par ces deux services — jamais d'un drapeau recopié dans le document — et
# elle ne REFUSE rien : une pièce d'archive reste consultable.

#: Les deux mentions, avec leur date (ou l'aveu qu'elle n'est pas enregistrée).
MENTION_VERROUILLE = ('Conception verrouillée depuis le {date} (devis lié '
                      'envoyé) : pièce produite en lecture seule.')
MENTION_ARCHIVE = ('Conception archivée le {date} : pièce d\'archive, '
                   'consultable, qui ne décrit pas une conception en cours.')
DATE_NON_ENREGISTREE = 'date non enregistrée'

#: L'état d'une conception COURANTE : aucune mention.
ETAT_COURANT = {'verrouille': False, 'verrouille_le': '', 'archive': False,
                'archive_le': ''}


def _date_lisible(moment):
    """``jj/mm/aaaa`` à l'heure LOCALE d'un instant aware, ou ``''``."""
    if moment is None:
        return ''
    try:
        from django.utils import timezone

        return timezone.localtime(moment).strftime('%d/%m/%Y')
    except (ValueError, TypeError, AttributeError):
        return ''


def etat_de_conception(calepinage):
    """``{verrouille, verrouille_le, archive, archive_le}`` — LU, jamais recopié.

    * verrouillé : ``services.verrou.est_verrouille`` (devis lié envoyé, sans
      déverrouillage tracé) ; la date est celle de l'ENVOI du devis lié ;
    * archivé : ``services.archivage.est_archive`` (entrée ACTIVE de la
      corbeille plateforme) ; la date est celle de l'archivage.

    Un calepinage non enregistré est courant, sans lecture en base.
    """
    etat = dict(ETAT_COURANT)
    if calepinage is None or not getattr(calepinage, 'pk', None):
        return etat
    from ..archivage import est_archive
    from ..verrou import est_verrouille

    if est_verrouille(calepinage):
        etat['verrouille'] = True
        etat['verrouille_le'] = _date_lisible(getattr(
            getattr(calepinage, 'devis', None), 'date_envoi', None))
    if est_archive(calepinage):
        from apps.trash.selectors import entree_active

        entree = entree_active(calepinage)
        etat['archive'] = True
        etat['archive_le'] = _date_lisible(getattr(entree, 'supprime_le',
                                                   None))
    return etat


def mentions_d_etat(etat):
    """Les mentions du pied pour ``etat`` — ``[]`` pour une conception courante.

    Verrouillée ET archivée ⇒ les DEUX mentions, une fois chacune.
    """
    if not isinstance(etat, Mapping):
        return []
    mentions = []
    if etat.get('verrouille'):
        mentions.append(MENTION_VERROUILLE.format(
            date=_texte(etat.get('verrouille_le')) or DATE_NON_ENREGISTREE))
    if etat.get('archive'):
        mentions.append(MENTION_ARCHIVE.format(
            date=_texte(etat.get('archive_le')) or DATE_NON_ENREGISTREE))
    return mentions
