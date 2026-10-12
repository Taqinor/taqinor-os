"""ENF11 — lecture TYPÉE des entrées que le CRM laissait passer en silence.

Le fuzz API (Schemathesis) a relevé deux familles de défauts sur les routes du
CRM :

* un paramètre de requête déclaré ``integer`` / ``date`` recevait « null » ou
  « abc » et la vue répondait 200 en le remplaçant par un défaut — le contrat
  dit « entier », le serveur disait « n'importe quoi » ;
* un corps JSON dont une valeur n'est pas du texte (liste, objet, nombre)
  faisait lever ``.strip()`` dans la vue : 500 au lieu d'un 400.

Ce module est la SEULE porte de ces deux contrôles : chaque refus est un 400
français qui NOMME le champ fautif (règle maison).
"""
import re

from rest_framework.exceptions import ValidationError

_ENTIER = re.compile(r'^[+-]?\d+$')


def entier_param(request, nom, defaut=None, *, mini=None, maxi=None,
                 tolerant=False):
    """Valeur entière du paramètre de requête ``nom``.

    Absent ou vide → ``defaut``. Non entier (« null », « abc », « 2.5 ») → 400
    nommant le paramètre. ``mini``/``maxi`` BORNENT (clamp) sans refuser : le
    schéma annonce un entier, pas une plage.

    ``tolerant=True`` : contrat TOLÉRANT (fenêtres ``?jours=`` des agrégats
    KPI, MRY19/MRY21/CAD87 — « jours invalide retombe sur le défaut ») : une
    valeur non entière vaut ``defaut`` au lieu d'un 400. Le schéma de ces
    paramètres l'annonce honnêtement (``schema_docs.P_JOURS`` : entier OU
    texte) — jamais un ``integer`` strict que le serveur ne tiendrait pas."""
    brut = request.query_params.get(nom)
    if brut is None or str(brut).strip() == '':
        return defaut
    brut = str(brut).strip()
    if not _ENTIER.match(brut):
        if tolerant:
            return defaut
        raise ValidationError({nom: 'Un nombre entier est attendu.'})
    valeur = int(brut)
    if mini is not None:
        valeur = max(mini, valeur)
    if maxi is not None:
        valeur = min(maxi, valeur)
    return valeur


def date_param(request, nom):
    """Date ISO (AAAA-MM-JJ) du paramètre ``nom`` ; ``None`` si absent.

    Une date invalide → 400 nommant le paramètre (avant : ignorée)."""
    import datetime

    brut = request.query_params.get(nom)
    if brut is None or str(brut).strip() == '':
        return None
    try:
        return datetime.date.fromisoformat(str(brut).strip())
    except ValueError:
        raise ValidationError(
            {nom: 'Date invalide (AAAA-MM-JJ attendu).'})


def booleen_param(donnees, nom):
    """Booléen JSON STRICT du corps (``true``/``false``) ; absent → ``False``.

    Avant, ``bool({})`` ou ``bool("x")`` valaient ``False``/``True`` sans
    erreur : le contrat dit ``boolean``, le serveur disait « n'importe quoi »."""
    valeur = donnees.get(nom)
    if valeur is None:
        return False
    if not isinstance(valeur, bool):
        raise ValidationError({nom: 'Un booléen est attendu.'})
    return valeur


def liste_ids(donnees, nom='ids'):
    """Liste d'identifiants entiers OBLIGATOIRE du corps (peut être vide).

    Absente, non liste, ou contenant autre chose que des entiers → 400 nommant
    le champ (avant : ``id__in`` recevait n'importe quoi → 500)."""
    from .fiche_bulk import coerce_id_list

    brut = donnees.get(nom)
    if brut is None:
        raise ValidationError({nom: 'Ce champ est obligatoire.'})
    try:
        return coerce_id_list(brut)
    except ValueError:
        raise ValidationError({nom: 'Une liste d\'identifiants entiers est attendue.'})


def verifier_corps_texte(request, champs):
    """400 si le corps n'est pas un objet ou si l'un de ``champs`` n'est ni
    absent, ni ``null``, ni du texte.

    Les vues lisent ces champs par ``(request.data.get(x) or '').strip()`` :
    une liste ou un objet y levait ``AttributeError`` (500)."""
    donnees = request.data
    if not hasattr(donnees, 'get'):
        raise ValidationError({'detail': 'Un objet JSON est attendu.'})
    erreurs = {}
    for champ in champs:
        valeur = donnees.get(champ)
        if valeur is not None and not isinstance(valeur, str):
            erreurs[champ] = 'Un texte est attendu.'
    if erreurs:
        raise ValidationError(erreurs)


class CorpsTexteMixin:
    """Mixin de ViewSet : contrôle les champs texte de CHAQUE écriture, APRÈS
    authentification, permissions et débit (un anonyme reçoit son 401).

    Déclarer ``champs_texte`` = les clés lues comme du texte par les actions."""

    champs_texte = ()

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if request.method in ('POST', 'PUT', 'PATCH'):
            verifier_corps_texte(request, self.champs_texte)
