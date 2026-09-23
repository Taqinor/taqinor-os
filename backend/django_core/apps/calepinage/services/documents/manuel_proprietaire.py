"""CALX316 — le MANUEL DU PROPRIÉTAIRE, depuis un gabarit société.

Le constat
==========
Le module ne produit AUCUNE pièce de remise au client. La seule mécanique de
gabarit TÉLÉVERSÉ qui existe est celle des dossiers réglementaires
(``GabaritDossierReglementaire``, CAL190, ``services/reglementaire.py``) : une
société SANS gabarit voit zéro dossier proposé, et le message qui dit quoi
téléverser — jamais un formulaire fabriqué à sa place.

Le manuel du propriétaire suit EXACTEMENT ce patron, sur le MÊME modèle
(``GabaritDossierReglementaire``, genre ``manuel``) : aucune migration neuve
n'est requise (le champ ``genre`` existe déjà, CAL190), et la discipline « rien
n'est reproduit de mémoire » s'applique à l'identique — un gabarit absent
produit ZÉRO manuel, jamais un texte de consigne inventé par ce module.

Ce que ce module fait, et ce qu'il NE fait PAS
===============================================
* le TEXTE des consignes (sécurité, arrêt…) est SAISI par la société dans les
  ``champs`` de son gabarit (``{code, libelle, type: 'texte', texte}`` — le
  même ``JSONField`` que CAL190, une clé ``texte`` en plus, jamais un nouveau
  modèle ni une nouvelle migration) ; CE MODULE NE RÉDIGE AUCUNE PROSE ;
* les DONNÉES SYSTÈME (modules et onduleurs retenus, nombre de chaînes,
  coordonnées de l'installateur) sont LUES — jamais saisies une seconde fois —
  et substituées dans le texte du gabarit partout où il écrit ``{{cle}}`` ;
* une variable ``{{cle}}`` EMPLOYÉE par le gabarit mais SANS donnée système
  correspondante s'imprime « non renseigné » — jamais un ``{{cle}}`` brut,
  jamais une valeur inventée ; une variable HORS de ``VARIABLES_SYSTEME`` est
  un gabarit invalide, refusé en la NOMMANT (même discipline que
  ``cle_calepinage`` sur les dossiers réglementaires) ;
* aucun montant : les données système lues ici ne touchent jamais
  ``Produit.prix_achat`` ni aucune grandeur de coût, et le résultat qui LES
  PORTE (chaînage, onduleurs) passe par le MÊME pare-feu que le rapport
  d'étude (``services.rapport.resultat_du_rapport``, CALX297).
"""
from __future__ import annotations

import re
from html import escape

from ..rapport import RapportRefuse

__all__ = [
    'CODE_DOCUMENT', 'GENRE_GABARIT', 'NON_RENSEIGNE', 'ManuelRefuse',
    'MESSAGE_AUCUN_GABARIT_MANUEL', 'VARIABLES_SYSTEME',
    'gabarit_manuel_actif', 'variables_systeme', 'substituer_variables',
    'construire_manuel', 'html_de_manuel', 'html_du_manuel', 'rendre_manuel',
]

#: Le code du document dans l'inventaire (contrat ``calepinage_documents``).
CODE_DOCUMENT = 'manuel_proprietaire'

#: Le ``genre`` du gabarit sur ``GabaritDossierReglementaire`` (CAL190) — même
#: modèle, même champ, AUCUNE migration neuve.
GENRE_GABARIT = 'manuel'

NON_RENSEIGNE = 'non renseigné'

#: Le message servi quand la société n'a DÉPOSÉ aucun gabarit de genre
#: « manuel » — il NOMME le genre attendu et dit quoi faire, jamais un
#: manuel fictif en attendant.
MESSAGE_AUCUN_GABARIT_MANUEL = (
    "Aucun gabarit de manuel du propriétaire n'a été déposé pour cette "
    "société (genre « manuel ») : aucun manuel n'est produit. Déposez un "
    "gabarit de genre « manuel » dans les réglages du module pour en voir "
    "apparaître un."
)

#: ``cle -> libellé FRANÇAIS`` — les SEULES variables qu'un gabarit peut
#: employer en ``{{cle}}``. Une clé hors de cette table est un gabarit
#: invalide (refus nommé) : jamais une variable qui laisserait entendre que
#: le serveur sait produire une donnée qu'il ne sait pas produire.
VARIABLES_SYSTEME = {
    'modules': 'Modules retenus (désignation)',
    'onduleurs': 'Onduleurs retenus (référence et nombre)',
    'nombre_chaines': 'Nombre de chaînes',
    'installateur_nom': "Nom de l'installateur",
    'installateur_telephone': "Téléphone de l'installateur",
    'installateur_email': "E-mail de l'installateur",
    'installateur_adresse': "Adresse de l'installateur",
}

_TOKEN = re.compile(r'\{\{\s*([a-zA-Z0-9_]+)\s*\}\}')


class ManuelRefuse(RapportRefuse):
    """Le manuel refuse de sortir, et il NOMME la donnée en cause.

    Sous-classe de ``RapportRefuse`` (même interface ``champ``) : l'aperçu
    HTML (CALX323, ``views/documents.py::apercu_document``) le capture donc
    sans devoir rouvrir sa liste de refus connus.
    """


def gabarit_manuel_actif(company):
    """Le gabarit ACTIF de genre « manuel » de la société, ou ``None``.

    Lecture PURE, bornée société par le filtre — jamais une écriture. Un
    gabarit ``None`` est traduit en refus NOMMÉ par ``construire_manuel``,
    jamais ici : cette fonction ne fait QUE lire.
    """
    if company is None:
        return None
    from ...models import GabaritDossierReglementaire

    return (GabaritDossierReglementaire.objects
            .filter(company=company, genre=GENRE_GABARIT, actif=True)
            .order_by('intitule', 'id')
            .first())


def _designation_onduleurs(onduleurs):
    """« 1 × ONDULEUR-ESSAI-1 » par onduleur RÉFÉRENCÉ — jamais un sans nom."""
    lignes = []
    for onduleur in onduleurs or ():
        if not isinstance(onduleur, dict):
            continue
        reference = str(onduleur.get('reference') or '').strip()
        if not reference:
            continue
        nombre = onduleur.get('nombre')
        lignes.append('%s × %s' % (nombre, reference)
                      if isinstance(nombre, (int, float)) else reference)
    return '; '.join(lignes)


def _designation_modules(calepinage):
    """La désignation du module RETENU (CAL243) — ``''`` sans devis lié.

    Lue depuis ``equipements_du_calepinage`` (la MÊME source que l'annexe des
    fiches du rapport, CALX299) : jamais une seconde façon de nommer le
    module retenu.
    """
    company = getattr(calepinage, 'company', None)
    if not getattr(calepinage, 'pk', None) or company is None:
        return ''
    from ..equipements import equipements_du_calepinage

    try:
        equipements = equipements_du_calepinage(calepinage) or {}
    except Exception:  # noqa: BLE001 — le manuel n'exige pas de devis lié
        return ''
    bloc = equipements.get('panneau') if isinstance(equipements, dict) \
        else None
    return str((bloc or {}).get('designation') or '').strip()


def variables_systeme(calepinage, *, resultat=None):
    """Les valeurs RÉELLES des clés de ``VARIABLES_SYSTEME`` — jamais devinées.

    Une donnée absente vaut ``''`` (``substituer_variables`` l'imprime
    « non renseigné ») : ce n'est jamais cette fonction qui invente un texte.
    """
    from apps.parametres.selectors import company_identity

    resultat = resultat if isinstance(resultat, dict) else {}
    electrique = resultat.get('electrique') or {}
    chainage = electrique.get('chainage') or {}
    nombre_chaines = chainage.get('chaines')
    identite = company_identity(getattr(calepinage, 'company', None))
    return {
        'modules': _designation_modules(calepinage),
        'onduleurs': _designation_onduleurs(electrique.get('onduleurs')),
        'nombre_chaines': (str(int(nombre_chaines))
                           if isinstance(nombre_chaines, (int, float))
                           else ''),
        'installateur_nom': identite.get('nom') or '',
        'installateur_telephone': identite.get('telephone') or '',
        'installateur_email': identite.get('email') or '',
        'installateur_adresse': identite.get('adresse') or '',
    }


def substituer_variables(texte, variables):
    """Remplace chaque ``{{cle}}`` de ``texte`` (déjà échappé HTML) par sa
    valeur, échappée. AUCUN ``{{...}}`` ne subsiste jamais dans la sortie :

    * une clé DÉCLARÉE (``VARIABLES_SYSTEME``) sans valeur imprime
      ``NON_RENSEIGNE`` — jamais un texte inventé ;
    * une clé INCONNUE fait REFUSER tout le document, en la NOMMANT : un
      gabarit qui emploie une variable que le serveur ne sait pas produire
      ne doit jamais imprimer un texte qui aurait l'air d'une donnée.
    """
    variables = variables or {}
    echappe = escape(str(texte or ''))

    def _remplacer(correspondance):
        cle = correspondance.group(1)
        if cle not in VARIABLES_SYSTEME:
            raise ManuelRefuse(
                "Le gabarit du manuel emploie une variable inconnue : "
                "« %s ». Variables admises : %s."
                % (cle, ', '.join(sorted(VARIABLES_SYSTEME))), champ='champs')
        valeur = str(variables.get(cle) or '').strip()
        return escape(valeur) if valeur else NON_RENSEIGNE

    return _TOKEN.sub(_remplacer, echappe)


def _sections_du_gabarit(gabarit, variables):
    """``[{code, libelle, texte}]`` — un champ SANS texte n'imprime rien."""
    sections = []
    for champ in list(getattr(gabarit, 'champs', None) or ()):
        if not isinstance(champ, dict):
            continue
        texte = str(champ.get('texte') or '').strip()
        if not texte:
            continue
        code = str(champ.get('code') or '').strip()
        libelle = str(champ.get('libelle') or code).strip()
        sections.append({'code': code, 'libelle': libelle,
                         'texte': substituer_variables(texte, variables)})
    return sections


#: Sentinelle « lire en base » — distingue « non fourni » (essai qui force
#: l'absence de gabarit avec ``gabarit=None``) de « valeur par défaut ».
_LIRE = object()


def construire_manuel(calepinage, *, resultat=None, gabarit=_LIRE,
                      styles=None, identite=None, site=None, etat=None):
    """Le manuel, prêt à mettre en page — ou un refus NOMMÉ.

    Args:
        calepinage: le pivot (société, client, titre, résultat stocké).
        resultat: déjà lu par l'appelant (essai pur) — sinon LU ici via
            ``services.rapport.resultat_du_rapport`` (même pare-feu de
            montants que le rapport d'étude).
        gabarit: le gabarit DÉJÀ lu (essai pur, ``None`` pour forcer
            l'absence) — sinon ``gabarit_manuel_actif(company)``.
        styles / identite / site / etat: déjà lus par l'appelant — sinon LUS
            ici (mêmes lectures que le rapport d'étude, CALX297).

    Raises:
        ManuelRefuse: aucun gabarit de genre « manuel » déposé (champ
            ``gabarit``), ou une variable inconnue dans son texte (champ
            ``champs``).
        RapportRefuse: aucun résultat enregistré, ou une clé de coût dans le
            résultat (mêmes refus que le rapport d'étude).
    """
    company = getattr(calepinage, 'company', None)
    if gabarit is _LIRE:
        gabarit = gabarit_manuel_actif(company)
    if gabarit is None:
        raise ManuelRefuse(MESSAGE_AUCUN_GABARIT_MANUEL, champ='gabarit')

    if resultat is None:
        from ..rapport import resultat_du_rapport

        resultat, _stocke = resultat_du_rapport(calepinage)
    else:
        from ..rapport import verifier_etancheite

        if not isinstance(resultat, dict) or not resultat:
            from ..rapport import SANS_RESULTAT

            raise RapportRefuse(SANS_RESULTAT, champ='resultat')
        verifier_etancheite(resultat)

    variables = variables_systeme(calepinage, resultat=resultat)
    sections = _sections_du_gabarit(gabarit, variables)

    from .gabarit_document import (
        etat_de_conception, identite_du_calepinage, styles_de_societe,
    )

    if styles is None:
        styles = styles_de_societe(company)
    if identite is None:
        identite = identite_du_calepinage(
            calepinage, titre_document='Manuel du propriétaire')
    if site is None:
        from ... import selectors

        site = selectors.contexte_geographique(calepinage)
    if etat is None:
        etat = etat_de_conception(calepinage)

    return {
        'code': CODE_DOCUMENT,
        'gabarit_intitule': gabarit.intitule,
        'variables': variables,
        'sections': sections,
        'identite': dict(identite or {}),
        'site': dict(site or {}),
        'styles': dict(styles or {}),
        'provenance': {
            'hash_entree': (resultat.get('hash_entree')
                            or resultat.get('entree_hash') or ''),
            'version_moteur': resultat.get('version_moteur') or '',
        },
        'etat': dict(etat or {}),
    }


#: La feuille propre au manuel — mêmes gris que la charte d'impression.
CSS_MANUEL = (
    '.section-manuel{margin-bottom:4mm;}'
    '.section-manuel .texte{white-space:pre-wrap;}'
)


def html_de_manuel(manuel):
    """Le manuel en HTML AUTONOME habillé du gabarit société."""
    from .gabarit_document import document_html, page_de_garde_html

    corps = [page_de_garde_html(manuel['identite'], manuel['site'],
                                manuel['provenance'], manuel['styles'])]
    for section in manuel['sections']:
        corps.append(
            '<section class="section-manuel" data-section="%s"><h2>%s</h2>'
            '<div class="texte">%s</div></section>'
            % (escape(section['code'] or 'section', quote=True),
               escape(section['libelle']), section['texte']))
    return document_html(
        ''.join(corps), titre='Manuel du propriétaire',
        styles=manuel['styles'], provenance=manuel['provenance'],
        langue='fr', css=CSS_MANUEL, etat=manuel.get('etat'))


def html_du_manuel(calepinage, *, langue=None, **options):
    """L'UNIQUE mise en page du manuel — le PDF et l'aperçu (CALX323) la
    partagent. ``langue`` est accepté pour la forme commune à
    ``services.documents.mise_en_page`` : le manuel n'est servi qu'en
    français (aucun gabarit RTL, CALX296)."""
    return html_de_manuel(construire_manuel(calepinage, **options))


def rendre_manuel(calepinage, *, company=None, **options):
    """Octets PDF du manuel, via ``core.pdf.render_pdf`` (ARC11)."""
    from core.pdf import render_pdf

    return render_pdf(html=html_du_manuel(calepinage, **options),
                      company=company or getattr(calepinage, 'company', None))
