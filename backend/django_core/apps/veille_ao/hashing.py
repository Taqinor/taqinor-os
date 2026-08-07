"""VAO11 — l'empreinte d'un avis : le filet de dédoublonnage de niveau 2.

Patron éprouvé du dépôt : ``apps.ventes.services.layout_hash`` — un blob JSON
canonique (clés triées, séparateurs compacts) passé en SHA-256. Même méthode
ici, pour la même raison : deux soumissions du MÊME fait doivent produire la
MÊME chaîne, indépendamment de la casse, des accents, des espaces et de
l'ordre d'écriture.

Pourquoi DEUX niveaux et pas un seul
------------------------------------
Le **niveau 1** est l'identité propre du portail
(``ref_consultation`` + ``org_acronyme``, lue directement dans l'URL de
détail) : stable, exacte, et c'est la contrainte d'unicité en base.

Le **niveau 2** — cette empreinte — est le FILET, pour les deux cas où le
niveau 1 est aveugle :

* **un avis RECTIFIÉ peut ressortir avec un NOUVEL identifiant de portail**
  (nouvelle consultation, même marché) — le niveau 1 le verrait comme neuf ;
* **une saisie manuelle ou un import de fichier n'a AUCUN identifiant de
  portail** — le niveau 1 n'a alors rien à comparer.

Une collision de niveau 2 sans collision de niveau 1 ne crée pas de doublon :
elle **met à jour** l'avis existant et journalise la rectification.

Pourquoi la RÉFÉRENCE reste dans l'empreinte (et pourquoi on ne fusionne PAS
sur « acheteur + date limite » seuls) : sur le portail, un même acheteur
publie couramment plusieurs LOTS distincts qui ferment le même jour. Une
empreinte réduite à l'acheteur et à la date les fusionnerait en un seul avis
— une perte de données bien pire que le doublon qu'elle prétend éviter. Deux
avis du même acheteur, même date, mais de références différentes restent donc
deux avis (test explicite).
"""
from __future__ import annotations

import hashlib
import json
import unicodedata


def normaliser_texte(valeur):
    """Casse, accents, ponctuation d'espacement et espaces multiples
    neutralisés — un même fait doit s'écrire d'une seule façon.
    """
    if not valeur:
        return ''
    decompose = unicodedata.normalize('NFKD', str(valeur))
    sans_accent = ''.join(
        c for c in decompose if not unicodedata.combining(c))
    return ' '.join(sans_accent.lower().split())


def normaliser_date(valeur):
    """Une date/heure rendue en chaîne stable, ou '' si absente.

    Une date limite absente ne doit pas empêcher le dédoublonnage : elle
    contribue simplement une chaîne vide, et l'empreinte repose alors sur la
    référence et l'acheteur.
    """
    if valeur in (None, ''):
        return ''
    if hasattr(valeur, 'isoformat'):
        return valeur.isoformat()
    return normaliser_texte(valeur)


def empreinte_avis(reference='', acheteur='', date_limite=None):
    """Empreinte SHA-256 de ``(référence + acheteur + date limite)``.

    Renvoie ``''`` quand il n'y a AUCUNE matière à empreindre — un avis sans
    référence ni acheteur ne doit jamais fusionner avec un autre avis vide
    (une empreinte de vide serait un aimant à faux doublons).
    """
    canonique = {
        'reference': normaliser_texte(reference),
        'acheteur': normaliser_texte(acheteur),
        'date_limite': normaliser_date(date_limite),
    }
    if not canonique['reference'] and not canonique['acheteur']:
        return ''
    blob = json.dumps(canonique, sort_keys=True, separators=(',', ':'),
                      default=str)
    return hashlib.sha256(blob.encode('utf-8')).hexdigest()


def empreinte_pour_avis(avis):
    """L'empreinte d'une instance ``AvisMarche`` (sauvegardée ou non).

    La « référence » retenue est la première renseignée parmi la référence
    d'avis et la référence de consultation : c'est ce qu'un humain lirait.
    """
    reference = avis.reference_avis or avis.ref_consultation or ''
    return empreinte_avis(reference, avis.acheteur, avis.date_limite_remise)
