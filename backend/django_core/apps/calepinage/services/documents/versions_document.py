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
PRODUITS (par la vue de remise, ``views/remise_document.py``, qui appelle
les MÊMES fonctions que les GET).

CALX324 — LE FIL DU CALEPINAGE
-------------------------------
Chaque enregistrement RÉUSSI journalise UNE ligne
(``services/journal.py::journaliser_document_produit``) — best-effort,
comme le reste du chatter (``journal._ecrire`` avale déjà ses propres
échecs). Un enregistrement REFUSÉ n'appelle jamais le journal : un refus
n'est pas un événement de remise.

ACAL222 — LA REMISE EST EXPLICITE (C-ACAL-121)
-----------------------------------------------
Un ``GET rapport-etude.pdf`` n'écrit plus RIEN : trois clics de lecture
créaient trois versions et trois objets MinIO. Une version naît seulement
d'un ``POST remettre-document``, sous VERROU DE LIGNE du calepinage (deux
remises simultanées ⇒ deux numéros distincts), DÉDOUBLONNÉE sur l'empreinte
des entrées (``services/empreinte_livrable.py``, ACAL221) : remettre deux fois
sans geste rend la même version. L'empreinte (16 hex) est encodée dans le nom
— ``<code>__v<NNN>__<langue>__<empreinte16>.<ext>`` — et une version dont
l'empreinte n'est plus celle des entrées courantes est publiée
``perimee: true`` ; un ancien nom SANS empreinte reste lisible, périmé.
"""
from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

__all__ = [
    'VersionDocumentRefuse', 'enregistrer_version_document',
    'versions_du_document', 'prochain_numero', 'empreinte_courante',
    'TAILLE_EMPREINTE',
]

#: Le séparateur du nom de fichier encodé — jamais présent dans un ``code``
#: de document (les codes du contrat sont ``[a-z_]+``).
_SEPARATEUR = '__'
_MOTIF_NUMERO = re.compile(r'__v(\d+)__')

#: ACAL222 — le nom COMPLET d'une version : code, numéro, langue, empreinte
#: des entrées (absente sur les noms d'avant ACAL222), extension.
_MOTIF_NOM = re.compile(
    r'^(?P<code>[a-z0-9_]+)__v(?P<numero>\d+)__(?P<langue>[a-z0-9]+)'
    r'(?:__(?P<empreinte>[0-9a-f]{16}))?\.(?P<extension>[a-z0-9]+)$')

#: Les caractères de l'empreinte des entrées encodés dans le nom.
TAILLE_EMPREINTE = 16

#: Les types que le magasin générique sait vérifier par octets magiques
#: (``records.storage.store_attachment``) ; les autres livrables (JSON, SVG)
#: produits PAR LE SERVEUR passent par ``store_export_result`` (même bucket).
_MIMES_VERIFIES = ('application/pdf', 'image/png', 'image/jpeg',
                   'image/webp')


class VersionDocumentRefuse(ValueError):
    """Refus métier — le CHAMP fautif est nommé."""

    def __init__(self, message, *, champ=''):
        super().__init__(message)
        self.champ = champ


def _content_type_calepinage():
    from django.contrib.contenttypes.models import ContentType

    from ...models import Calepinage

    return ContentType.objects.get_for_model(Calepinage)


def _langue_propre(langue):
    langue_propre = (langue or 'fr').strip().lower() or 'fr'
    return ''.join(c for c in langue_propre if c.isalnum()) or 'fr'


def _empreinte_courte(empreinte):
    """Les :data:`TAILLE_EMPREINTE` premiers caractères hex, ou ``None``."""
    texte = ''.join(c for c in str(empreinte or '').lower()
                    if c in '0123456789abcdef')
    if len(texte) < TAILLE_EMPREINTE:
        return None
    return texte[:TAILLE_EMPREINTE]


def _nom_fichier_version(code, numero, langue, extension, empreinte=None):
    """``<code>__v<numero>__<langue>[__<empreinte16>].<ext>`` — jamais un nom
    d'utilisateur brut (même discipline que
    ``services/planche.py::nom_de_fichier``)."""
    courte = _empreinte_courte(empreinte)
    suffixe = '%s%s' % (_SEPARATEUR, courte) if courte else ''
    return '%s%sv%03d%s%s%s.%s' % (code, _SEPARATEUR, numero, _SEPARATEUR,
                                   _langue_propre(langue), suffixe,
                                   extension)


def _numero_depuis_nom(filename):
    """Le numéro encodé dans ``filename`` — ``0`` si illisible (ligne
    défensive : ne doit jamais lever pour une pièce jointe étrangère au
    schéma, ex. une photo de site CAL52 qui partagerait le préfixe)."""
    trouve = _MOTIF_NUMERO.search(filename or '')
    return int(trouve.group(1)) if trouve else 0


def _lire_nom(filename):
    """``{numero, langue, empreinte}`` relus du nom, ou ``None``."""
    trouve = _MOTIF_NOM.match(filename or '')
    if trouve is None:
        return None
    return {'numero': int(trouve.group('numero')),
            'langue': trouve.group('langue'),
            'empreinte': trouve.group('empreinte')}


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


def _sections_du_document(calepinage, code):
    """La sélection de sections que le rendu de ``code`` applique (le rapport
    d'étude lit celle de la SOCIÉTÉ, CALX307) — ``None`` = toutes."""
    if code != 'rapport_etude':
        return None
    from ...selectors import parametres_de_societe
    from ..rapport.sections_societe import sections_retenues

    try:
        return sections_retenues(
            parametres_de_societe(getattr(calepinage, 'company', None)))
    except Exception:  # noqa: BLE001 — réglage refusé : le rendu le dira
        return None


def empreinte_courante(calepinage, code, langue=None):
    """ACAL222 — l'empreinte (16 hex) des entrées que ``code`` lirait
    AUJOURD'HUI dans ``langue`` (``empreinte_livrable``, ACAL221)."""
    from ..empreinte_livrable import empreinte_des_entrees

    return _empreinte_courte(empreinte_des_entrees(
        calepinage, _langue_propre(langue),
        _sections_du_document(calepinage, code)))


def _version_depuis_attachment(attachment, courante_pour):
    lu = _lire_nom(attachment.filename) or {}
    empreinte = lu.get('empreinte')
    # Un ancien nom SANS empreinte ne prouve rien : il est périmé.
    perimee = True
    if empreinte:
        perimee = empreinte != courante_pour(lu.get('langue'))
    return {
        'numero': _numero_depuis_nom(attachment.filename),
        'produit_le': attachment.created_at,
        'produit_par_utilisateur': _personne(attachment.uploaded_by),
        'attachment': attachment.pk,
        'empreinte': empreinte,
        'perimee': perimee,
    }


def versions_du_document(calepinage, code):
    """Les versions REMISES de ``code`` pour CE calepinage, la PLUS RÉCENTE
    d'abord — bornées à SA société (une pièce d'une autre société n'existe
    pas ici, même discipline que le reste du module). Chaque version publie
    son ``empreinte`` et ``perimee`` (ACAL222)."""
    if calepinage is None or not getattr(calepinage, 'pk', None):
        return []
    pieces = list(_attachments_du_document(calepinage, code))
    if not pieces:
        return []
    cache = {}

    def courante_pour(langue):
        if langue not in cache:
            try:
                cache[langue] = empreinte_courante(calepinage, code, langue)
            except Exception:  # noqa: BLE001 — non prouvée courante = périmée
                logger.exception(
                    'ACAL222 : empreinte courante illisible (calepinage %s, '
                    '%s)', calepinage.pk, code)
                cache[langue] = None
        return cache[langue]

    return [_version_depuis_attachment(a, courante_pour) for a in pieces]


def _stocker(octets, nom, *, mime, extension, company):
    """Dépose les octets dans le magasin générique ; ``(donnees, erreur)``."""
    from django.core.files.base import ContentFile

    if mime in _MIMES_VERIFIES:
        from apps.records.storage import store_attachment

        return store_attachment(ContentFile(bytes(octets), name=nom),
                                company=company)
    import uuid

    from apps.records.storage import store_export_result

    cle = store_export_result(
        bytes(octets), company_id=company,
        job_id='calepinage-%s' % uuid.uuid4().hex, ext=extension,
        content_type=mime)
    return {'file_key': cle, 'filename': nom, 'size': len(octets),
            'mime': mime}, None


def _deja_remise(calepinage, code, langue, empreinte):
    """La version la plus récente de (code, langue), si elle porte DÉJÀ
    ``empreinte`` — sinon ``None``."""
    if not empreinte:
        return None
    for piece in _attachments_du_document(calepinage, code):
        lu = _lire_nom(piece.filename)
        if lu is None or lu['langue'] != langue:
            continue
        return piece if lu['empreinte'] == empreinte else None
    return None


def enregistrer_version_document(calepinage, *, code, octets, langue=None,
                                 user=None, empreinte=None, extension='pdf',
                                 mime='application/pdf'):
    """Enregistre ``octets`` comme la PROCHAINE version de ``code``.

    ACAL222 — sous VERROU DE LIGNE du calepinage : le numéro est relu et posé
    dans la même transaction (deux remises simultanées ⇒ deux numéros) ; une
    ``empreinte`` égale à celle de la dernière version de la même langue rend
    CETTE version (``deja_remise: True``), sans copie ni ligne de fil.

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

    from django.db import transaction

    from apps.records.models import Attachment

    from ...models import Calepinage

    langue_propre = _langue_propre(langue)
    courte = _empreinte_courte(empreinte)
    utilisateur = user if getattr(user, 'pk', None) else None
    with transaction.atomic():
        # Le verrou SÉRIALISE les remises d'un même calepinage : le numéro
        # relu ici ne peut pas être pris par une transaction concurrente.
        list(Calepinage._base_manager.select_for_update()
             .filter(pk=calepinage.pk).values_list('pk', flat=True))
        existante = _deja_remise(calepinage, code, langue_propre, courte)
        if existante is not None:
            return {
                'numero': _numero_depuis_nom(existante.filename),
                'attachment': existante,
                'code': code,
                'langue': langue_propre,
                'empreinte': courte,
                'produit_le': existante.created_at,
                'deja_remise': True,
            }
        numero = prochain_numero(calepinage, code)
        nom = _nom_fichier_version(code, numero, langue_propre, extension,
                                   courte)
        donnees, erreur = _stocker(octets, nom, mime=mime,
                                   extension=extension,
                                   company=calepinage.company)
        if erreur:
            raise VersionDocumentRefuse(erreur, champ='octets')
        donnees = dict(donnees, filename=nom)
        piece = Attachment.objects.create(
            company=calepinage.company,
            content_type=_content_type_calepinage(), object_id=calepinage.pk,
            uploaded_by=utilisateur, **donnees)

    # CALX324 — une ligne de fil, best-effort (jamais après un refus, jamais
    # pour une remise dédoublonnée).
    _journaliser_si_branche(calepinage, code=code, numero=numero,
                            langue=langue_propre, user=utilisateur,
                            empreinte=courte)

    return {
        'numero': numero,
        'attachment': piece,
        'code': code,
        'langue': langue_propre,
        'empreinte': courte,
        'produit_le': piece.created_at,
        'deja_remise': False,
    }


def _journaliser_si_branche(calepinage, *, code, numero, langue, user,
                            empreinte=None):
    """CALX324 — une ligne de fil portant l'EMPREINTE DES ENTRÉES de la
    version remise (ACAL222 — plus le seul ``layout_hash``), jamais un résumé
    de son contenu. Best-effort : ``services/journal.py`` avale déjà ses
    propres échecs (``_ecrire``) — cet appel ne peut donc pas casser un
    enregistrement de version déjà réussi."""
    from ..journal import journaliser_document_produit

    texte = 'entrées %s' % empreinte if empreinte else ''
    version_moteur = getattr(calepinage, 'version_moteur', '') or ''
    if version_moteur:
        texte = ('%s · moteur %s' % (texte, version_moteur) if texte
                 else 'moteur %s' % version_moteur)
    journaliser_document_produit(
        calepinage, code=code, numero=numero, langue=langue,
        empreinte=texte, user=user)
