"""CALX62 — une série météo horaire DÉPOSÉE PAR LA SOCIÉTÉ, à la place de PVGIS.

LE CONSTAT
----------
``services/pvgis_serie.py`` est la seule source météo du module, et
``services/chaine_pertes.py`` ne reçoit que sa forme : aucun import de série
météo n'existe (``services/consommation.py`` n'importe que des COURBES DE
CHARGE, ce qui est l'autre bout du problème). Une société qui possède ses
propres mesures — station au sol, fichier d'un fournisseur, export d'un
logiciel tiers — n'a aujourd'hui aucun moyen de les faire entrer.

LA PARITÉ
---------
PVsyst importe des fichiers météo CSV/TXT et pose une règle dure :
« only POA or GHI can be imported at the same time »
(https://www.pvsyst.com/help/meteo-database/custom-meteo-files/index.html).
HelioScope charge un fichier météo par Condition Set
(https://help-center.helioscope.com/hc/en-us/articles/19218896242323-Weather-Data-Sources).

CE QUE CE SERVICE ACCEPTE, ET CE QU'IL REFUSE
---------------------------------------------
Un CSV à colonnes NOMMÉES. Deux colonnes sont obligatoires :

* ``horodatage`` — un instant ISO 8601 avec son FUSEAU EXPLICITE
  (``2021-01-15T13:00:00+01:00`` ou ``…Z``). Un horodatage sans fuseau est
  REFUSÉ en nommant sa ligne : une heure sans fuseau se décale d'une heure en
  silence, et une production décalée d'une heure est une production fausse
  (D-CALX 15 dit déjà la même chose du côté du site).
* ``gi_w_m2`` — l'irradiance GLOBALE SUR LE PLAN des modules. Un fichier qui
  ne porte que l'irradiance globale HORIZONTALE (``ghi_w_m2`` / ``gh_w_m2``)
  est REFUSÉ **en nommant cette colonne** : passer de l'horizontal au plan
  demande un modèle de transposition que ce module n'a pas (CALX198), et le
  supposer fabriquerait une irradiance qui n'a été ni mesurée ni calculée
  (D-CALX 7). C'est exactement la règle « POA ou GHI, pas les deux » de PVsyst,
  vue du côté qui nous intéresse.

Cinq colonnes sont FACULTATIVES et entrent telles quelles quand elles sont
là : ``gb_i_w_m2``, ``gd_i_w_m2``, ``gr_i_w_m2`` (les trois composantes, sans
lesquelles les étapes IAM/ombrage s'omettent avec le motif UNIQUE du module),
``t2m_c`` et ``ws10m`` (le modèle thermique).

LE PAS EST MESURÉ, JAMAIS SUPPOSÉ. Les écarts sont lus sur les INSTANTS
ABSOLUS (horodatage + fuseau), ce qui rend un changement d'heure inoffensif :
un fichier en heure locale qui « saute » une heure au printemps reste régulier
une fois ramené à l'instant. Tout écart autre qu'une heure pleine, un doublon
ou un fichier désordonné sont REFUSÉS en nommant la ligne fautive — une série
trouée produirait une année de production incomplète qui aurait l'air entière.

LA PROVENANCE EST PUBLIÉE, PAS DEVINÉE. Le bloc ``meteo`` rendu porte
``service='fichier'``, le ``fournisseur`` SAISI, le nom du fichier, son
empreinte SHA-256, sa taille, son nombre de lignes et l'horodatage de lecture.
Rien de ce qu'un fichier ne déclare pas n'est rempli : ni base de rayonnement
PVGIS, ni altitude, ni coordonnées, ni horizon — ces clés restent ``null``, et
``null`` s'y lit « non publié ».

CE SERVICE N'ÉCRIT RIEN et ne parle à aucune base : il LIT un fichier et rend
la forme de ``ClientPvgis.serie_irradiance`` (CALX150), pour que la chaîne de
pertes reçoive exactement ce qu'elle reçoit de PVGIS.
"""
from __future__ import annotations

import datetime
import hashlib

from .chaine_pertes import PLAFOND_FENETRE_ANNEES
from .pvgis_serie import (
    BASE_HEURE_UTC,
    COLONNES_COMPOSANTES,
    CONVENTION_AZIMUT,
    MOTIF_COMPOSANTES_ABSENTES,
)
# Le bloc ``serie_horaire`` du contrat CALX142 a UN seul constructeur
# (``pvgis_serie._bloc_serie``) : la borne d'une année, la clé ``tronquee`` et
# l'ordre des colonnes y sont décidés une fois. Le réécrire ici donnerait deux
# blocs libres de diverger — ce que le contrat interdit. L'import est privé et
# ASSUMÉ : s'il disparaît, la CI le dit tout de suite, à l'import.
from .pvgis_serie import _bloc_serie, _pas_minutes

__all__ = [
    'COLONNE_HORODATAGE', 'COLONNE_IRRADIANCE_PLAN', 'COLONNES_FACULTATIVES',
    'COLONNES_HORIZONTALES', 'LIGNES_MAX', 'MOTIF_HORIZONTAL_SEUL',
    'OCTETS_MAX', 'PAS_ATTENDU_MINUTES', 'SEPARATEURS', 'MeteoFichierRefuse',
    'lire_serie_meteo',
]

#: La colonne d'instant, obligatoire.
COLONNE_HORODATAGE = 'horodatage'

#: L'irradiance globale SUR LE PLAN, obligatoire.
COLONNE_IRRADIANCE_PLAN = 'gi_w_m2'

#: Les colonnes qui entrent telles quelles si elles sont là.
COLONNES_FACULTATIVES = COLONNES_COMPOSANTES + ('t2m_c', 'ws10m')

#: Les noms sous lesquels une irradiance HORIZONTALE circule. Les reconnaître
#: sert à REFUSER en nommant la colonne, jamais à la transposer.
COLONNES_HORIZONTALES = ('ghi_w_m2', 'gh_w_m2', 'g_h_w_m2', 'ghi')

#: Le pas attendu : l'heure pleine. Le pas réel est MESURÉ, celui-ci est ce
#: que la chaîne sait consommer (CALX142 raisonne au pas horaire).
PAS_ATTENDU_MINUTES = 60

#: La borne de lignes, DÉRIVÉE du calendrier et du plafond de fenêtre déjà
#: arrêté par la chaîne (``chaine_pertes.PLAFOND_FENETRE_ANNEES``) : dix
#: années bissextiles au pas horaire. Ce n'est pas un chiffre choisi ici.
LIGNES_MAX = 366 * 24 * PLAFOND_FENETRE_ANNEES

#: La borne d'OCTETS, dérivée de la précédente : 160 octets par ligne de
#: mesure — une marge large sur les huit colonnes du format. Elle existe pour
#: qu'un dépôt démesuré soit refusé AVANT d'être lu en mémoire, pas pour
#: décrire une quelconque grandeur physique.
OCTETS_MAX = LIGNES_MAX * 160

#: Les séparateurs admis. Le point-virgule est celui des exports du module
#: (``services/export_csv.py``) ; la virgule est celui des exports anglo-saxons.
SEPARATEURS = (';', ',')

MOTIF_HORIZONTAL_SEUL = (
    "Ce fichier ne porte que l'irradiance globale HORIZONTALE "
    '(colonne « {colonne} ») : la chaîne de pertes a besoin de l\'irradiance '
    'sur le PLAN des modules (colonne « {attendue} »). La transposition '
    'horizontal → plan n\'est pas disponible dans ce module (elle demande le '
    'modèle à une diode, tâche CALX198) : aucune irradiance de plan n\'est '
    'supposée à partir de l\'horizontale. Exportez la série en irradiance de '
    'plan (POA), ou laissez PVGIS la calculer.'
)

MOTIF_SANS_FUSEAU = (
    "L'horodatage de la ligne {ligne} (« {valeur} ») ne déclare aucun fuseau "
    "horaire : ajoutez le décalage explicite (par exemple « +01:00 » ou "
    '« Z »). Une heure sans fuseau se décale d\'une heure en silence, et une '
    'production décalée d\'une heure est une production fausse.'
)


class MeteoFichierRefuse(ValueError):
    """Un fichier météo refusé, avec son motif FRANÇAIS et le champ à pointer.

    ``champ`` porte le nom de la COLONNE fautive (ou ``fichier`` quand c'est le
    dépôt lui-même) et ``ligne`` le numéro de ligne du fichier, à partir de 1,
    en-tête compris — de quoi ouvrir le fichier au bon endroit.
    """

    def __init__(self, message, *, champ='', ligne=None):
        super().__init__(message)
        self.champ = champ
        self.ligne = ligne
        self.motif = message


def _octets(fichier):
    """Le contenu du dépôt, en octets — ou un refus qui nomme le champ."""
    if fichier is None:
        raise MeteoFichierRefuse(
            'Aucun fichier météo déposé : ajoutez un CSV dans le champ '
            '« fichier ».', champ='fichier')
    if isinstance(fichier, bytes):
        contenu = fichier
    elif isinstance(fichier, str):
        contenu = fichier.encode('utf-8')
    else:
        contenu = fichier.read()
        if isinstance(contenu, str):
            contenu = contenu.encode('utf-8')
    if not contenu:
        raise MeteoFichierRefuse(
            'Le fichier météo déposé est vide : aucune série ne peut en être '
            'lue.', champ='fichier')
    if len(contenu) > OCTETS_MAX:
        raise MeteoFichierRefuse(
            'Ce fichier dépasse {0} Mo : un CSV météo au pas horaire ne pèse '
            'jamais autant. Vérifiez le format exporté.'.format(
                OCTETS_MAX // (1024 * 1024)), champ='fichier')
    return contenu


def _texte(contenu):
    """Le texte du fichier, BOM retiré — ou un refus qui le dit."""
    for encodage in ('utf-8-sig', 'cp1252'):
        try:
            return contenu.decode(encodage)
        except UnicodeDecodeError:
            continue
    raise MeteoFichierRefuse(
        "Le fichier météo n'est pas un texte lisible (ni UTF-8, ni Windows-1252) : "
        "ce n'est probablement pas un CSV. Exportez-le en CSV avant de le "
        'déposer.', champ='fichier')


def _lignes_utiles(texte):
    """Les lignes non vides, avec leur NUMÉRO dans le fichier d'origine."""
    return [(rang, ligne) for rang, ligne in enumerate(texte.splitlines(), 1)
            if ligne.strip()]


def _entete(lignes):
    """``(separateur, titres, rang)`` de l'en-tête — ou un refus qui le nomme.

    L'en-tête est la PREMIÈRE ligne non vide qui porte la colonne
    d'horodatage : un fichier peut être précédé d'un cartouche de provenance,
    comme les exports du module en produisent un.
    """
    for rang, ligne in lignes:
        for separateur in SEPARATEURS:
            titres = [case.strip().strip('"').lower()
                      for case in ligne.split(separateur)]
            if COLONNE_HORODATAGE in titres:
                return separateur, titres, rang
    raise MeteoFichierRefuse(
        'Aucune colonne « {0} » dans ce fichier : la première ligne doit '
        'NOMMER ses colonnes (séparateur « ; » ou « , »), et porter au '
        'minimum « {0} » et « {1} ».'.format(
            COLONNE_HORODATAGE, COLONNE_IRRADIANCE_PLAN),
        champ=COLONNE_HORODATAGE)


def _verifier_irradiance(titres):
    """La colonne d'irradiance de PLAN est là — ou le refus NOMME l'autre."""
    if COLONNE_IRRADIANCE_PLAN in titres:
        return
    for horizontale in COLONNES_HORIZONTALES:
        if horizontale in titres:
            raise MeteoFichierRefuse(
                MOTIF_HORIZONTAL_SEUL.format(
                    colonne=horizontale, attendue=COLONNE_IRRADIANCE_PLAN),
                champ=horizontale)
    raise MeteoFichierRefuse(
        'Aucune colonne « {0} » dans ce fichier : sans irradiance sur le plan '
        'des modules, la chaîne de pertes ne peut pas démarrer. Aucune valeur '
        "n'est supposée à sa place.".format(COLONNE_IRRADIANCE_PLAN),
        champ=COLONNE_IRRADIANCE_PLAN)


def _nombre(valeur, *, colonne, ligne, obligatoire=False):
    """Un nombre, décimale « . » ou « , » — ou ``None`` / un refus nommé."""
    texte = str(valeur or '').strip().strip('"')
    if not texte:
        if obligatoire:
            raise MeteoFichierRefuse(
                'La colonne « {0} » est vide à la ligne {1} : une heure sans '
                'irradiance laisserait un trou dans la série. Complétez la '
                'ligne ou retirez-la.'.format(colonne, ligne),
                champ=colonne, ligne=ligne)
        return None
    try:
        return float(texte.replace(',', '.'))
    except ValueError:
        raise MeteoFichierRefuse(
            'La colonne « {0} » de la ligne {1} n\'est pas un nombre (lu : '
            '« {2} »).'.format(colonne, ligne, texte),
            champ=colonne, ligne=ligne)


def _instant(valeur, *, ligne):
    """L'instant ISO du fichier, fuseau EXPLICITE exigé."""
    texte = str(valeur or '').strip().strip('"')
    if not texte:
        raise MeteoFichierRefuse(
            'La colonne « {0} » est vide à la ligne {1}.'.format(
                COLONNE_HORODATAGE, ligne),
            champ=COLONNE_HORODATAGE, ligne=ligne)
    normalise = texte[:-1] + '+00:00' if texte.endswith(('Z', 'z')) else texte
    try:
        moment = datetime.datetime.fromisoformat(normalise)
    except ValueError:
        raise MeteoFichierRefuse(
            'L\'horodatage de la ligne {0} (« {1} ») n\'est pas une date ISO '
            '8601 (attendu : « 2021-01-15T13:00:00+01:00 »).'.format(
                ligne, texte),
            champ=COLONNE_HORODATAGE, ligne=ligne)
    if moment.utcoffset() is None:
        raise MeteoFichierRefuse(
            MOTIF_SANS_FUSEAU.format(ligne=ligne, valeur=texte),
            champ=COLONNE_HORODATAGE, ligne=ligne)
    return moment


def _verifier_calendrier(moments):
    """Doublons, désordre et pas non horaire — chacun NOMME sa ligne."""
    precedent = None
    for ligne, moment in moments:
        if precedent is not None:
            minutes = round(
                (moment - precedent[1]).total_seconds() / 60.0)
            if minutes == 0:
                raise MeteoFichierRefuse(
                    'La ligne {0} répète l\'instant de la ligne {1} : deux '
                    'mesures pour la même heure ne peuvent pas être départagées '
                    'sans choisir à la place de la société.'.format(
                        ligne, precedent[0]),
                    champ=COLONNE_HORODATAGE, ligne=ligne)
            if minutes < 0:
                raise MeteoFichierRefuse(
                    'La ligne {0} remonte dans le temps par rapport à la ligne '
                    '{1} : le fichier doit être trié par horodatage '
                    'croissant.'.format(ligne, precedent[0]),
                    champ=COLONNE_HORODATAGE, ligne=ligne)
            if minutes != PAS_ATTENDU_MINUTES:
                raise MeteoFichierRefuse(
                    'Le pas entre les lignes {0} et {1} est de {2} minutes : '
                    'la chaîne attend une série au pas horaire, sans trou. Une '
                    'heure manquante produirait une année incomplète qui aurait '
                    "l'air entière.".format(precedent[0], ligne, minutes),
                    champ=COLONNE_HORODATAGE, ligne=ligne)
        precedent = (ligne, moment)


def _bloc_meteo_fichier(*, fournisseur, nom_fichier, contenu, lignes_lues,
                        annees, decalages, obtenue_le):
    """Le bloc ``meteo`` du contrat CALX143, vu d'un FICHIER.

    Les clés que seul PVGIS pourrait renseigner (base de rayonnement, base
    météo, URL, altitude, horizon) restent ``null`` : un fichier ne les
    déclare pas, et les remplir d'une valeur plausible reviendrait à inventer
    la provenance de la série.
    """
    return {
        'service': 'fichier',
        'base_rayonnement': None,
        'base_demandee': None,
        'base_meteo': None,
        'mode': None,
        'fenetre_annees': ('{0}-{1}'.format(annees[0], annees[-1])
                           if annees else None),
        'annees': list(annees),
        'point': {'lat': None, 'lon': None, 'altitude_m': None},
        'horizon': {'origine': 'aucun', 'hauteur_max_deg': None,
                    'base_horizon': None},
        'url': None,
        'obtenue_le': obtenue_le,
        'depuis_cache': False,
        'convention_azimut': CONVENTION_AZIMUT,
        'heure': {
            # Le fichier déclare un décalage par ligne : on publie ceux qu'on
            # a RÉELLEMENT lus. Quand ils valent tous zéro, la base est UTC ;
            # sinon elle reste nulle — décider entre heure standard et heure
            # légale à la place de la société serait une supposition, et
            # CALX59 sait ré-indexer sur le fuseau SAISI du site.
            'base': BASE_HEURE_UTC if decalages == [0] else None,
            'fuseau_site': None,
            'decalage_minutes': list(decalages),
        },
        # CALX62 — les deux clés que le contrat CALX143 annonce pour une série
        # de fichier, SAISIES (le fournisseur) ou MESURÉES (le fichier).
        'fournisseur': fournisseur or None,
        'fichier': {
            'nom': nom_fichier or None,
            'octets': len(contenu),
            'lignes': lignes_lues,
            'empreinte_sha256': hashlib.sha256(contenu).hexdigest(),
        },
    }


def lire_serie_meteo(fichier, *, fournisseur='', nom_fichier='',
                     obtenue_le=None):
    """La série météo d'un fichier déposé, à la forme de ``serie_irradiance``.

    Args:
        fichier: le fichier déposé (objet à ``.read()``, octets ou texte).
        fournisseur: le fournisseur SAISI par la société — il est publié tel
            quel dans ``meteo.fournisseur``, jamais déduit du contenu.
        nom_fichier: le nom du dépôt, publié dans ``meteo.fichier.nom``.
        obtenue_le: l'horodatage de lecture (les tests le figent). À défaut,
            l'instant de l'appel, en UTC.

    Returns:
        dict — ``service`` (``'fichier'``), ``points``,
        ``composantes_disponibles``, ``motif_composantes``, ``serie_horaire``
        (le bloc CALX142), ``meteo`` (le bloc CALX143), ``annees``, ``url``
        (``None`` : aucune requête n'a été faite) et ``depuis_cache``
        (``False``).

    Raises:
        MeteoFichierRefuse: colonne obligatoire absente, irradiance seulement
            horizontale, horodatage sans fuseau ou illisible, calendrier
            troué / désordonné / en doublon, fichier vide ou trop long. Le
            motif est en français et nomme la colonne (et la ligne).
    """
    contenu = _octets(fichier)
    lignes = _lignes_utiles(_texte(contenu))
    separateur, titres, rang_entete = _entete(lignes)
    _verifier_irradiance(titres)

    corps = [(rang, ligne) for rang, ligne in lignes if rang > rang_entete]
    if not corps:
        raise MeteoFichierRefuse(
            'Ce fichier ne porte que son en-tête : aucune heure de mesure à '
            'lire.', champ='fichier')
    if len(corps) > LIGNES_MAX:
        raise MeteoFichierRefuse(
            'Ce fichier porte {0} lignes de mesure, au-delà des {1} admises '
            '({2} années au pas horaire). Découpez la série avant de la '
            'déposer.'.format(len(corps), LIGNES_MAX, PLAFOND_FENETRE_ANNEES),
            champ='fichier')

    points = []
    moments = []
    decalages = set()
    for rang, ligne in corps:
        cases = ligne.split(separateur)
        lue = {titre: (cases[index] if index < len(cases) else '')
               for index, titre in enumerate(titres)}
        moment = _instant(lue.get(COLONNE_HORODATAGE), ligne=rang)
        moments.append((rang, moment))
        decalages.add(int(moment.utcoffset().total_seconds() // 60))
        point = {
            # La série est indexée sur l'heure ÉCRITE dans le fichier ; le
            # décalage réellement employé part dans ``meteo.heure``, pour que
            # la chaîne (CALX59) sache sur quoi elle travaille.
            'annee': moment.year, 'mois': moment.month, 'jour': moment.day,
            'heure': moment.hour,
            COLONNE_IRRADIANCE_PLAN: _nombre(
                lue.get(COLONNE_IRRADIANCE_PLAN),
                colonne=COLONNE_IRRADIANCE_PLAN, ligne=rang,
                obligatoire=True),
            # ``h_sun_deg`` appartient à la réponse PVGIS : un fichier ne la
            # porte pas, elle reste nulle plutôt que d'être calculée ici.
            'h_sun_deg': None,
        }
        for colonne in COLONNES_FACULTATIVES:
            point[colonne] = (_nombre(lue.get(colonne), colonne=colonne,
                                      ligne=rang)
                              if colonne in titres else None)
        points.append(point)

    _verifier_calendrier(moments)

    mesure = _pas_minutes(points)
    if mesure is not None and mesure != PAS_ATTENDU_MINUTES:
        raise MeteoFichierRefuse(
            'Le pas mesuré de ce fichier est de {0} minutes : la chaîne '
            'attend une série au pas horaire.'.format(mesure),
            champ=COLONNE_HORODATAGE)

    annees = sorted({point['annee'] for point in points})
    disponibles = all(
        all(point[colonne] is not None for colonne in COLONNES_COMPOSANTES)
        for point in points)
    horodatage = obtenue_le or datetime.datetime.now(
        datetime.timezone.utc).replace(microsecond=0).isoformat()

    return {
        'service': 'fichier',
        'points': points,
        'composantes_disponibles': disponibles,
        'motif_composantes': (None if disponibles
                              else MOTIF_COMPOSANTES_ABSENTES),
        'serie_horaire': _bloc_serie(points, annees, None,
                                     composantes=disponibles),
        'meteo': _bloc_meteo_fichier(
            fournisseur=fournisseur, nom_fichier=nom_fichier,
            contenu=contenu, lignes_lues=len(points), annees=annees,
            decalages=sorted(decalages), obtenue_le=horodatage),
        'annees': annees,
        # Aucune requête n'a été faite : il n'y a ni URL ni cache à publier.
        'url': None,
        'depuis_cache': False,
    }
