"""Écritures/orchestration du répertoire ``Tiers`` (ARC17/18/19/56).

Point d'entrée WRITE que les autres apps consomment (crm/stock/compta/rh) sans
importer ``tiers.models`` : ``tiers`` reste une couche fondation (contrat
import-linter ``tiers-is-a-base-layer``). ``company`` est TOUJOURS un argument
explicite posé par l'appelant côté serveur — jamais lue d'un corps de requête
ici.

Ponts additifs (ARC18/19/56) : chaque modèle historique (crm.Client,
stock.Fournisseur, compta.Partenaire, rh.DossierEmploye, crm.Lead) reçoit un
FK nullable ``tiers`` (string-FK ``'tiers.Tiers'``). L'identité reste MAÎTRE
côté modèle historique pour l'instant — ``tiers`` n'en est qu'un MIROIR
one-way (pont réversible ; la bascule write-path est la DÉCISION ARC21,
flag-gatée OFF par défaut). Les helpers ci-dessous dédupent par email/ICE
company-scopés et posent les drapeaux de rôle.
"""
from .models import Tiers

# Champs d'identité miroités depuis un modèle historique vers son Tiers. Chaque
# appelant fournit ceux qu'il possède ; les absents restent inchangés/vides.
_CHAMPS_IDENTITE = (
    'type_tiers', 'prenom', 'raison_sociale',
    'telephone', 'whatsapp', 'email', 'adresse', 'ville',
    'gps_lat', 'gps_lng',
    'ice', 'rc', 'identifiant_fiscal', 'cin', 'rib',
)


def creer_tiers(*, company, nom, **champs):
    """Crée un ``Tiers`` pour une société donnée.

    ``company`` et ``nom`` sont obligatoires ; les autres champs
    (coordonnées, identifiants légaux, rôles, type) sont optionnels et
    passés tels quels au modèle.
    """
    return Tiers.objects.create(company=company, nom=nom, **champs)


def _norm(value):
    """Clé de rapprochement : chaîne épurée, minuscules (email/ICE). Vide si
    la valeur ne porte aucun caractère significatif."""
    return str(value or '').strip().lower()


def find_tiers_by_dedup(*, company, email='', ice=''):
    """Cherche un ``Tiers`` EXISTANT de la société par email OU ICE (dédup
    company-scopée). Renvoie le premier trouvé, ou ``None``.

    La déduplication est STRICTEMENT bornée à la société (deux sociétés
    partageant un même email/ICE gardent des Tiers séparés — jamais de fuite
    inter-tenant). ICE prioritaire (identifiant légal fort) ; à défaut email.
    """
    email_n = _norm(email)
    ice_n = _norm(ice)
    qs = Tiers.objects.filter(company=company)
    if ice_n:
        hit = qs.filter(ice__iexact=ice_n).first()
        if hit is not None:
            return hit
    if email_n:
        return qs.filter(email__iexact=email_n).first()
    return None


def attacher_ou_creer_tiers(*, company, nom, roles=None,
                            email='', ice='', tiers_existant=None, **champs):
    """Rattache (dédup email/ICE company-scopée) ou crée un ``Tiers`` miroir
    pour un enregistrement historique, et pose ses drapeaux de rôle.

    - ``company``/``nom`` obligatoires (``company`` posée serveur).
    - ``roles`` : itérable de drapeaux à FORCER à True parmi ``is_client``,
      ``is_fournisseur``, ``is_partenaire``, ``is_soustraitant`` (jamais remis
      à False — un tiers cumule ses rôles au fil des ponts).
    - ``email``/``ice`` servent à la fois à la dédup ET sont miroités.
    - ``tiers_existant`` : le ``Tiers`` DÉJÀ lié à l'enregistrement (si présent
      et dans la bonne société) — réutilisé en PRIORITÉ pour ne JAMAIS créer un
      2ᵉ Tiers à chaque nouvelle sauvegarde d'un enregistrement sans clé de
      dédup (email/ICE vides). Évite la prolifération d'orphelins.
    - ``**champs`` : autres champs d'identité (``_CHAMPS_IDENTITE``) miroités
      s'ils sont fournis non vides (jamais d'écrasement par une valeur vide —
      l'identité reste maître côté modèle historique).

    Renvoie ``(tiers, cree)`` : le ``Tiers`` et un booléen (True si créé).
    Aucune duplication : un second appel pour le même enregistrement réutilise
    son Tiers déjà lié (ou le retrouve par email/ICE) et se contente de
    compléter/poser les rôles.
    """
    roles = tuple(roles or ())
    # Priorité au Tiers déjà lié (même société) — évite un doublon à chaque
    # save d'un enregistrement sans clé de dédup.
    tiers = None
    if tiers_existant is not None \
            and getattr(tiers_existant, 'company_id', None) == company.id:
        tiers = tiers_existant
    if tiers is None:
        tiers = find_tiers_by_dedup(company=company, email=email, ice=ice)
    cree = False

    # Ne miroiter que les valeurs non vides fournies (l'historique reste maître).
    a_poser = {'email': email, 'ice': ice}
    a_poser.update(champs)
    a_poser = {
        k: v for k, v in a_poser.items()
        if k in _CHAMPS_IDENTITE and v not in (None, '')
    }

    if tiers is None:
        tiers = Tiers.objects.create(
            company=company, nom=nom or '', **a_poser)
        cree = True
        dirty = []
    else:
        dirty = []
        # Complète les champs VIDES du miroir (jamais d'écrasement d'une valeur
        # déjà renseignée — on ne fait que remplir les trous).
        for champ, val in a_poser.items():
            if not getattr(tiers, champ, ''):
                setattr(tiers, champ, val)
                dirty.append(champ)
        if not tiers.nom and nom:
            tiers.nom = nom
            dirty.append('nom')

    # Pose (jamais ne retire) les drapeaux de rôle demandés.
    for role in roles:
        if role in ('is_client', 'is_fournisseur',
                    'is_partenaire', 'is_soustraitant') \
                and not getattr(tiers, role, False):
            setattr(tiers, role, True)
            dirty.append(role)

    # Persiste les champs modifiés en mémoire. Sur le chemin CREATE, le
    # ``Tiers.objects.create`` ci-dessus n'a PAS posé les rôles (ils sont
    # calculés après) : il faut donc les sauvegarder ici aussi, sinon un Tiers
    # fraîchement créé garderait ses drapeaux de rôle à False en base.
    if dirty:
        tiers.save(update_fields=list(dict.fromkeys(dirty)))
    return tiers, cree


# ── ARC21 — Bascule write-path (DÉCISION founder-gated, OFF par défaut) ──────
#
# Voir docs/decisions/ARC21-tiers-source-ecriture.md. Le mécanisme est LIVRÉ
# mais DÉSACTIVÉ : avec le flag OFF, ``identite_source_est_tiers()`` renvoie
# False et ``ecrire_identite`` est un NO-OP strict (comportement byte-identique
# à aujourd'hui — l'historique reste maître, Tiers n'est qu'un miroir ARC18/19).

def identite_source_est_tiers() -> bool:
    """True si ``Tiers`` est la SOURCE d'écriture de l'identité (flag
    ``TIERS_SOURCE_ECRITURE`` ON). False par défaut → historique maître."""
    from django.conf import settings
    return bool(getattr(settings, 'TIERS_SOURCE_ECRITURE', False))


def ecrire_identite(*, company, tiers, champs):
    """ARC21 — Point d'écriture UNIQUE de l'identité (mode transition).

    Avec le flag OFF (défaut) : NO-OP total — renvoie ``False`` sans rien
    écrire (le modèle historique reste l'unique chemin d'écriture, exactement
    comme aujourd'hui). Aucun effet de bord, aucune requête.

    Avec le flag ON : met à jour l'identité sur ``Tiers`` (source) — les
    modèles historiques appliquent ensuite le miroir lecture chez eux. Écriture
    company-scopée (``tiers`` doit appartenir à ``company``, sinon NO-OP).
    Renvoie ``True`` si une écriture a eu lieu, ``False`` sinon.
    """
    if not identite_source_est_tiers():
        return False  # flag OFF — comportement byte-identique à aujourd'hui.
    if tiers is None or tiers.company_id != getattr(company, 'id', None):
        return False
    a_ecrire = {
        k: v for k, v in (champs or {}).items()
        if k in _CHAMPS_IDENTITE or k == 'nom'
    }
    if not a_ecrire:
        return False
    for champ, val in a_ecrire.items():
        setattr(tiers, champ, val)
    tiers.save(update_fields=list(a_ecrire.keys()))
    return True
