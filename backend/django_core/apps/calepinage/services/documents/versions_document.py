"""CALX322 — versionner les documents produits.

LE CONSTAT
----------
Chaque appel de sortie RE-REND le document à la volée et n'en garde rien
(``views/sorties.py`` : toutes les sorties rendent des octets sans
persistance) ; seul le dossier technique dépose en GED
(``services/pack_technique.py::deposit_document``). Personne ne peut
retrouver LE PDF remis au client le mois dernier.

AUCUNE MIGRATION NEUVE — ``records.Attachment`` RÉUTILISÉ TEL QUEL
--------------------------------------------------------------------
Le lot du 23/09/2026 interdit toute migration hors celles déjà
pré-déclarées (calepinage 0011). Le binaire part donc dans
``records.Attachment`` (clé MinIO, jamais de binaire au dépôt) — LA MÊME
primitive que les photos de site (CAL52) et les pièces jointes génériques,
rattaché au calepinage par le mécanisme ContentType déjà déclaré
(``apps/calepinage/platform.py::record_targets``). Le modèle ne porte pas
de colonnes libres pour ``{code, numero, langue}`` : ces trois-là sont donc
ENCODÉS dans ``filename`` (schéma fixe, jamais un nom d'utilisateur brut —
même discipline que ``services/planche.py::nom_de_fichier``), et RELUS
depuis lui par ce module — UNE seule façon de les écrire, UNE seule de les
lire.

LE NUMÉRO, JAMAIS UN ``count()+1``
------------------------------------
Même règle que ``apps/ventes/utils/references.py`` : le prochain numéro
est le plus HAUT numéro déjà utilisé + 1. Une version supprimée ne doit
jamais faire remettre un numéro déjà remis à un client.

CE QUE CE MODULE NE FAIT PAS
-----------------------------
Il ne rend AUCUN document — ``code``/``octets`` lui arrivent déjà
PRODUITS (par ``services/rapport`` ou un futur rédacteur du lot 6). Il ne
journalise rien non plus (CALX324 le branche, une ligne à la fin
d'``enregistrer_version_document`` — cette section n'y touche pas).
"""
from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

__all__ = [
    'VersionDocumentRefuse', 'enregistrer_version_document',
    'versions_du_document', 'prochain_numero',
]

#: Le séparateur du nom de fichier encodé — jamais présent dans un ``code``
#: de document (les codes du contrat sont ``[a-z_]+``).
_SEPARATEUR = '__'
_MOTIF_NUMERO = re.compile(r'__v(\d+)__')

#: ``code -> extension`` des documents dont la production est BRANCHÉE sur
#: le versionnement (CALX322 ne branche que ``rapport_etude`` — le seul
#: document du lot 6 réellement rendu aujourd'hui, CALX297). Un document
#: futur ajoute SA ligne ici quand sa production est branchée.
EXTENSIONS_VERSIONNEES = {
    'rapport_etude': 'pdf',
}


class VersionDocumentRefuse(ValueError):
    """Refus métier — le CHAMP fautif est nommé."""

    def __init__(self, message, *, champ=''):
        super().__init__(message)
        self.champ = champ


def _content_type_calepinage():
    from django.contrib.contenttypes.models import ContentType

    from ...models import Calepinage

    return ContentType.objects.get_for_model(Calepinage)


def _nom_fichier_version(code, numero, langue, extension):
    """``<code>__v<numero>__<langue>.<ext>`` — jamais un nom d'utilisateur
    brut (même discipline que ``services/planche.py::nom_de_fichier``)."""
    langue_propre = (langue or 'fr').strip().lower() or 'fr'
    langue_propre = ''.join(c for c in langue_propre if c.isalnum()) or 'fr'
    return '%s%sv%03d%s%s.%s' % (code, _SEPARATEUR, numero, _SEPARATEUR,
                                 langue_propre, extension)


def _numero_depuis_nom(filename):
    """Le numéro encodé dans ``filename`` — ``0`` si illisible (ligne
    défensive : ne doit jamais lever pour une pièce jointe étrangère au
    schéma, ex. une photo de site CAL52 qui partagerait le préfixe)."""
    trouve = _MOTIF_NUMERO.search(filename or '')
    return int(trouve.group(1)) if trouve else 0


def _attachments_du_document(calepinage, code):
    from apps.records.models import Attachment

    prefixe = '%s%s' % (code, _SEPARATEUR)
    return (Attachment.objects
            .filter(content_type=_content_type_calepinage(),
                    object_id=calepinage.pk, company=calepinage.company,
                    filename__startswith=prefixe)
            .order_by('-id'))


def prochain_numero(calepinage, code):
    """Le plus HAUT numéro déjà utilisé pour (calepinage, code) + 1 —
    JAMAIS un ``count()+1`` (une version supprimée ne remet pas à zéro)."""
    if calepinage is None or not getattr(calepinage, 'pk', None):
        return 1
    numeros = [_numero_depuis_nom(a.filename)
               for a in _attachments_du_document(calepinage, code)]
    return (max(numeros) + 1) if numeros else 1


def _personne(user):
    """``{id, nom_complet}`` d'un compte, ou ``None`` — même forme que
    ``views/calepinages.py::_personne``."""
    if user is None or not getattr(user, 'pk', None):
        return None
    nom = (getattr(user, 'get_full_name', lambda: '')() or '').strip()
    return {'id': user.pk,
            'nom_complet': nom or getattr(user, 'username', '')}


def _version_depuis_attachment(attachment):
    return {
        'numero': _numero_depuis_nom(attachment.filename),
        'produit_le': attachment.created_at,
        'produit_par_utilisateur': _personne(attachment.uploaded_by),
        'attachment': attachment.pk,
    }


def versions_du_document(calepinage, code):
    """Les versions ENREGISTRÉES de ``code`` pour CE calepinage, la PLUS
    RÉCENTE d'abord — bornées à SA société (une pièce d'une autre société
    n'existe pas ici, même discipline que le reste du module)."""
    if calepinage is None or not getattr(calepinage, 'pk', None):
        return []
    return [_version_depuis_attachment(a)
            for a in _attachments_du_document(calepinage, code)]


def enregistrer_version_document(calepinage, *, code, octets, langue=None,
                                 user=None):
    """Enregistre ``octets`` comme la PROCHAINE version de ``code``.

    Raises:
        VersionDocumentRefuse: calepinage non enregistré, code manquant,
            document vide, ou refus du stockage (format/taille).
    """
    if calepinage is None or not getattr(calepinage, 'pk', None):
        raise VersionDocumentRefuse(
            'Calepinage non enregistré : aucune version ne peut être '
            'posée.', champ='calepinage')
    if not code:
        raise VersionDocumentRefuse('Code de document manquant.',
                                    champ='code')
    if not octets:
        raise VersionDocumentRefuse(
            "Document vide : rien n'est enregistré comme version.",
            champ='octets')

    from django.core.files.base import ContentFile

    from apps.records.models import Attachment
    from apps.records.storage import store_attachment

    numero = prochain_numero(calepinage, code)
    extension = EXTENSIONS_VERSIONNEES.get(code, 'pdf')
    nom = _nom_fichier_version(code, numero, langue, extension)
    fichier = ContentFile(bytes(octets), name=nom)
    donnees, erreur = store_attachment(fichier, company=calepinage.company)
    if erreur:
        raise VersionDocumentRefuse(erreur, champ='octets')

    utilisateur = user if getattr(user, 'pk', None) else None
    piece = Attachment.objects.create(
        company=calepinage.company,
        content_type=_content_type_calepinage(), object_id=calepinage.pk,
        uploaded_by=utilisateur, **donnees)

    # CALX324 branche le journal ici (une ligne, best-effort) — SEULE cette
    # ligne et l'import qu'elle nomme changent à cette étape.
    _journaliser_si_branche(calepinage, code=code, numero=numero,
                            langue=langue or 'fr', user=utilisateur)

    return {
        'numero': numero,
        'attachment': piece,
        'code': code,
        'langue': langue or 'fr',
        'produit_le': piece.created_at,
    }


def _journaliser_si_branche(calepinage, *, code, numero, langue, user):
    """CALX322 ne journalise pas encore — CALX324 remplace CE corps par un
    appel réel à ``services/journal.py`` ; aucune autre ligne du fichier ne
    bouge à cette étape."""
    return None
