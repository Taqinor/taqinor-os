"""AOF145 — métadonnées forcées et purge des chemins sur TOUT PDF sortant.

Le trou réel
============
Les trois scripts de dépôt du 27/07 n'ont AUCUN ``savefig(metadata=…)`` et
leurs chemins de sortie contiennent « OneDrive - Atlencia » et « TAQINOR » en
dur. Un PDF déposé porte donc, dans ses propriétés, le nom du bureau
d'exécution, la version de matplotlib et l'arborescence du poste qui l'a
produit — c'est-à-dire précisément ce que la marque blanche existe pour
cacher, offert en deux clics à n'importe quel destinataire.

Ce module post-traite TOUT PDF sortant — WeasyPrint (via ``core.pdf``),
planches matplotlib ET le PDF fusionné — avec la même passe :

* ``Title``    = code du document ;
* ``Author``   = SOUMISSIONNAIRE (jamais le bureau, même hors marque blanche :
                 le pli est déposé par le soumissionnaire, point) ;
* ``Subject``  = objet du marché ;
* ``Creator`` / ``Producer`` NEUTRALISÉS (chaînes vides) — pas « TAQINOR »,
  pas « Matplotlib », pas « WeasyPrint » ;
* mots-clés et champs libres vidés, XMP purgé.

Et une VÉRIFICATION, pas seulement un nettoyage : ``verifier_absence_chemins``
relit le binaire produit et REFUSE s'il reste un chemin local ou un jeton
interdit. Les métadonnées se réécrivent ; un chemin gravé dans un flux de
contenu (un titre de figure, un pied de page matplotlib) ne se réécrit pas
sans abîmer la page — il faut alors corriger la SOURCE, et un refus explicite
est le seul moyen de l'apprendre avant le dépôt.

PyMuPDF (``fitz``) est déjà en production (``PyMuPDF==1.28.0``) et sert déjà à
la fusion GED : import fonction-local, jamais une seconde plomberie PDF.
"""
from __future__ import annotations

import re

__all__ = [
    'CHAMPS_NEUTRALISES',
    'MOTIFS_CHEMIN',
    'CheminLocalDetecte',
    'forcer_metadonnees',
    'lire_metadonnees',
    'chemins_locaux',
    'verifier_absence_chemins',
    'assainir',
]

#: Champs d'information PDF systématiquement vidés. « creator »/« producer »
#: sont les deux qui trahissent l'outil et le bureau ; les autres sont vidés
#: par principe (un champ qu'on ne remplit pas ne peut pas mentir).
CHAMPS_NEUTRALISES = ('creator', 'producer', 'keywords', 'creationDate',
                      'modDate', 'trapped', 'format', 'encryption')

#: Motifs de chemin local. Volontairement larges : un faux positif se corrige
#: en nommant le document autrement, un faux négatif part chez l'acheteur.
MOTIFS_CHEMIN = (
    r'[A-Za-z]:\\\\[^\s"\')<>]{2,}',      # C:\Users\... (échappé dans le flux)
    r'[A-Za-z]:[\\/][^\s"\')<>]{2,}',     # C:\Users\... / C:/Users/...
    r'/(?:home|Users)/[^\s"\')<>]{2,}',   # /home/... /Users/...
    r'OneDrive[ \-_][^\s"\')<>]{0,40}',   # OneDrive - <organisation>
)


class CheminLocalDetecte(Exception):
    """Levée quand un PDF sortant porte encore un chemin ou un jeton interdit."""

    def __init__(self, trouves):
        self.trouves = list(trouves)
        super().__init__(
            "PDF sortant : chemins ou jetons locaux résiduels — {}. Ils ne se "
            "réécrivent pas sans abîmer la page : corriger la SOURCE (titre de "
            "figure, pied de planche, nom de fichier imprimé).".format(
                ', '.join('« {} »'.format(t) for t in self.trouves)))


def _ouvrir(contenu):
    import fitz  # PyMuPDF — déjà en production, jamais une seconde plomberie

    if not contenu:
        raise ValueError("PDF vide : rien à post-traiter.")
    return fitz, fitz.open(stream=contenu, filetype='pdf')


def forcer_metadonnees(contenu, *, code_document, soumissionnaire,
                       objet_marche=''):
    """Réécrit les métadonnées et purge le XMP. Renvoie les nouveaux octets.

    ``soumissionnaire`` est la raison sociale qui DÉPOSE le pli — c'est elle
    qui devient ``Author``, y compris (et surtout) quand la marque blanche est
    active. Passer le bureau d'exécution ici est le bug que ce module existe
    pour rendre impossible : la valeur est fournie par l'appelant, qui la tient
    de ``identite_de_garde`` (AOF139) et non de la company propriétaire.
    """
    if not str(soumissionnaire or '').strip():
        raise ValueError(
            "Aucun soumissionnaire fourni : l'auteur d'un PDF sortant ne peut "
            "pas être laissé au hasard (il retomberait sur l'outil ou sur le "
            "bureau d'exécution).")
    _fitz, document = _ouvrir(contenu)
    try:
        metadonnees = {champ: '' for champ in CHAMPS_NEUTRALISES}
        metadonnees.update({
            'title': str(code_document or ''),
            'author': str(soumissionnaire),
            'subject': str(objet_marche or ''),
        })
        document.set_metadata(metadonnees)
        # XMP : second jeu de métadonnées, invisible des lecteurs courants,
        # et c'est justement là que les outils gravent leur signature.
        try:
            document.del_xml_metadata()
        except AttributeError:  # pragma: no cover - API ancienne
            document.set_xml_metadata('')
        return document.tobytes(garbage=4, deflate=True)
    finally:
        document.close()


def lire_metadonnees(contenu):
    """Métadonnées effectives du PDF (dict), pour contrôle et tests."""
    _fitz, document = _ouvrir(contenu)
    try:
        return dict(document.metadata or {})
    finally:
        document.close()


def _texte_lisible(contenu):
    """Métadonnées + XMP + texte de toutes les pages, en une seule chaîne.

    C'est le seul périmètre où les motifs GÉNÉRIQUES de chemin ont un sens :
    appliqués aux octets bruts d'un PDF déflaté, un motif aussi court que
    ``X:/ab`` se déclenche sur du bruit de compression et le détecteur devient
    inutilisable en trois dossiers.
    """
    _fitz, document = _ouvrir(contenu)
    try:
        morceaux = [str(valeur)
                    for valeur in (document.metadata or {}).values() if valeur]
        for page in document:
            morceaux.append(page.get_text())
        try:
            xml = document.get_xml_metadata()
        except Exception:
            xml = ''
        if xml:
            morceaux.append(str(xml))
        return '\n'.join(morceaux)
    finally:
        document.close()


def chemins_locaux(contenu, *, jetons_interdits=()):
    """Chemins locaux et jetons interdits encore présents dans le PDF.

    Deux périmètres, délibérément différents :
      * motifs génériques de chemin → texte LISIBLE (métadonnées, XMP, pages) ;
      * jetons littéraux fournis par l'appelant (nom du bureau, organisation
        OneDrive…) → texte lisible ET octets bruts, parce que le dictionnaire
        ``/Info`` d'un PDF n'est pas compressé et survit à une réécriture
        incomplète.
    """
    texte = _texte_lisible(contenu)
    brut = contenu.decode('latin-1', 'ignore')
    trouves = []
    for motif in MOTIFS_CHEMIN:
        for occurrence in re.finditer(motif, texte):
            valeur = occurrence.group(0).strip()
            if valeur not in trouves:
                trouves.append(valeur)
    for jeton in jetons_interdits or ():
        jeton = str(jeton or '')
        if not jeton:
            continue
        motif = re.escape(jeton)
        if (re.search(motif, texte, re.IGNORECASE)
                or re.search(motif, brut, re.IGNORECASE)):
            if jeton not in trouves:
                trouves.append(jeton)
    return trouves


def verifier_absence_chemins(contenu, *, jetons_interdits=()):
    """Porte : lève ``CheminLocalDetecte`` si un chemin/jeton subsiste."""
    trouves = chemins_locaux(contenu, jetons_interdits=jetons_interdits)
    if trouves:
        raise CheminLocalDetecte(trouves)
    return True


def assainir(contenu, *, code_document, soumissionnaire, objet_marche='',
             jetons_interdits=()):
    """Passe complète : forcer les métadonnées PUIS vérifier le résultat.

    L'ordre compte — vérifier avant d'écrire signalerait des chemins que la
    réécriture allait justement supprimer, et l'opérateur apprendrait à
    ignorer l'alerte.
    """
    propre = forcer_metadonnees(contenu, code_document=code_document,
                                soumissionnaire=soumissionnaire,
                                objet_marche=objet_marche)
    verifier_absence_chemins(propre, jetons_interdits=jetons_interdits)
    return propre
