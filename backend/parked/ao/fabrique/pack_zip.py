"""AOF151 — ZIP de dépôt : l'exclusion est STRUCTURELLE, pas une vigilance.

Deux refus, pas un rappel
=========================
1. **Contrôle rouge → pas de ZIP.** Tant qu'un contrôle bloquant subsiste
   (AOF146), la génération est refusée AVEC son motif. Produire quand même
   « pour voir » crée un fichier qui existe, donc qui finit déposé.
2. **Visibilité → filtre par construction.** Une pièce ``interne`` ou
   ``directeur`` ne peut pas entrer dans le ZIP, **même demandée
   explicitement**. Le classeur de rentabilité est exclu parce qu'il porte
   ``visibilite='directeur'``, pas parce que quelqu'un a pensé à le retirer.

Mémoire bornée
--------------
Le pack complet (planches A3, mémoire, annexes) pèse plusieurs dizaines de Mo.
Chaque pièce est écrite **en flux, morceau par morceau**, directement dans
l'archive : à aucun moment le contenu d'une pièce entière — a fortiori du pack
entier — n'est tenu en mémoire. Un worker Celery qui sature, c'est un dépôt
qui n'a pas lieu.

Contrat d'entrée
----------------
``pieces`` : itérable de
``{'code', 'libelle', 'visibilite', 'format', 'empreinte', 'flux'}`` où
``flux`` est un CALLABLE renvoyant un itérable de blocs d'octets (jamais les
octets eux-mêmes : le contrat impose le flux).
``controle`` : le rapport d'AOF148/AOF146 — on lit ``bloquants``.
"""
from __future__ import annotations

import json
import re
import unicodedata
import zipfile

__all__ = [
    'VISIBILITE_CLIENT',
    'VISIBILITES_EXCLUES',
    'MOTS_INTERDITS',
    'NOM_MANIFESTE',
    'TAILLE_BLOC',
    'PackRefuse',
    'nom_de_fichier',
    'pieces_deposables',
    'ecrire_pack_zip',
]

VISIBILITE_CLIENT = 'client'
VISIBILITES_EXCLUES = ('interne', 'directeur')
NOM_MANIFESTE = 'MANIFESTE.json'

#: Racines réservées au directeur : elles n'ont rien à faire dans un nom de
#: fichier ni dans le manifeste d'un pli remis au maître d'ouvrage.
MOTS_INTERDITS = (
    "prix d'achat", 'prix achat', 'coût de revient', 'cout de revient',
    'marge', 'bénéfice', 'benefice', 'rentabilité', 'rentabilite',
    'maximum posable',
)

#: Taille de bloc RECOMMANDÉE aux producteurs de flux. Ce module ne l'impose
#: pas (il écrit ce qu'on lui donne, bloc par bloc) mais un producteur qui
#: rend un seul bloc de 40 Mo annule la garantie de mémoire bornée.
TAILLE_BLOC = 256 * 1024


class PackRefuse(Exception):
    """Levée quand le ZIP ne peut pas être produit — toujours avec le motif."""


def nom_de_fichier(piece, *, numero):
    """Nom normalisé en français : ``01 - Lettre de soumission.pdf``.

    Les accents sont conservés (c'est un pli français), mais les caractères
    interdits par les systèmes de fichiers sont remplacés : un ZIP qu'un poste
    Windows refuse d'extraire n'est pas un ZIP.
    """
    libelle = str(piece.get('libelle') or piece.get('code') or 'piece')
    libelle = unicodedata.normalize('NFC', libelle)
    libelle = re.sub(r'[\\/:*?"<>|\r\n\t]+', ' ', libelle)
    libelle = re.sub(r'\s+', ' ', libelle).strip(' .')
    extension = str(piece.get('format') or 'pdf').lstrip('.')
    return '{:02d} - {}.{}'.format(numero, libelle, extension)


def _verifier_etancheite(pieces):
    fautes = []
    for piece in pieces:
        texte = '{} {}'.format(piece.get('code') or '',
                               piece.get('libelle') or '').lower()
        for mot in MOTS_INTERDITS:
            if mot in texte:
                fautes.append('{} → « {} »'.format(piece.get('code'), mot))
    if fautes:
        raise PackRefuse(
            "ZIP de dépôt : intitulés réservés au directeur — {}.".format(
                ' ; '.join(fautes)))


def pieces_deposables(pieces):
    """``(retenues, exclues)`` — le filtre de visibilité, isolé et testable.

    Le filtre est appliqué ICI et nulle part ailleurs : un seul endroit à
    lire pour savoir ce qui peut sortir.
    """
    retenues, exclues = [], []
    for piece in pieces or ():
        visibilite = str(piece.get('visibilite') or VISIBILITE_CLIENT)
        if visibilite == VISIBILITE_CLIENT:
            retenues.append(piece)
        else:
            exclues.append({'code': piece.get('code'),
                            'libelle': piece.get('libelle'),
                            'visibilite': visibilite})
    return retenues, exclues


def _blocs(piece):
    flux = piece.get('flux')
    if not callable(flux):
        raise PackRefuse(
            "Pièce « {} » : `flux` doit être un CALLABLE renvoyant des blocs "
            "d'octets. Passer les octets entiers ferait tenir tout le pack en "
            "mémoire — c'est exactement ce que ce module interdit.".format(
                piece.get('code')))
    for bloc in flux():
        if bloc:
            yield bloc


def ecrire_pack_zip(destination, pieces, *, controle=None, sommaire_html=None,
                    reference_dossier='', empreinte_pack=''):
    """Écrit le ZIP de dépôt dans ``destination`` (fichier binaire ouvert).

    Renvoie le manifeste écrit (dict). Lève ``PackRefuse`` si le contrôle est
    rouge ou si un intitulé porte un mot réservé au directeur.
    """
    bloquants = list((controle or {}).get('bloquants') or ())
    if bloquants:
        motifs = ' ; '.join(
            '{} : {}'.format(ligne.get('code'), ligne.get('message'))
            for ligne in bloquants)
        raise PackRefuse(
            "ZIP de dépôt refusé — le contrôle de cohérence est rouge : "
            "{}".format(motifs))

    pieces = list(pieces or ())
    retenues, exclues = pieces_deposables(pieces)
    _verifier_etancheite(retenues)
    if not retenues:
        raise PackRefuse("ZIP de dépôt refusé : aucune pièce déposable.")

    entrees = []
    with zipfile.ZipFile(destination, 'w',
                         compression=zipfile.ZIP_DEFLATED) as archive:
        for numero, piece in enumerate(retenues, start=1):
            nom = nom_de_fichier(piece, numero=numero)
            taille = 0
            # Écriture EN FLUX : `ZipFile.open(..., 'w')` accepte des écritures
            # successives ; c'est ce qui borne la mémoire à un bloc.
            with archive.open(nom, 'w') as sortie:
                for bloc in _blocs(piece):
                    sortie.write(bloc)
                    taille += len(bloc)
            entrees.append({
                'numero': numero,
                'code': piece.get('code'),
                'libelle': piece.get('libelle'),
                'fichier': nom,
                'empreinte': piece.get('empreinte') or '',
                'octets': taille,
            })
        if sommaire_html:
            archive.writestr('00 - Sommaire.html', sommaire_html)
        manifeste = {
            'reference_dossier': reference_dossier,
            'empreinte_pack': empreinte_pack,
            'pieces': entrees,
            'exclues': len(exclues),
        }
        archive.writestr(
            NOM_MANIFESTE,
            json.dumps(manifeste, ensure_ascii=False, indent=2,
                       sort_keys=True))
    return manifeste
