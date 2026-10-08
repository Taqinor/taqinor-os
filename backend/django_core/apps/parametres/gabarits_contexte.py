"""NTEXT19 — contexte de placeholders d'un ``GabaritDocumentCustom``.

Construit, pour UNE cible (chantier / client / ticket / objet personnalisé) et
UN identifiant, le dictionnaire de variables offert au gabarit. Trois règles
non négociables :

1. **Jamais d'import de modèle cross-app.** Chaque cible est résolue par le
   ``selectors.py`` de l'app propriétaire (``installations`` / ``crm`` / ``sav``)
   — ``customfields`` est une app FONDATION, son import direct est autorisé
   (même précédent que ``automation.actions._create_custom_record``).
2. **Liste blanche de placeholders.** Seules les clés déclarées ici sortent :
   un gabarit ne peut pas aspirer un objet entier. Aucune donnée de prix
   d'achat ni de marge n'est exposée (garde explicite
   :data:`CLES_INTERDITES`, testée).
3. **Dégradation propre.** Objet introuvable (ou d'une autre société) →
   ``None`` : l'appelant répond 404 en français, jamais une trace.
"""
import logging

logger = logging.getLogger(__name__)

__all__ = ['CLES_INTERDITES', 'construire_contexte', 'cibles_supportees',
           'contexte_demonstration', 'apercu_contexte', 'EXEMPLES']

#: Fragments de nom qu'un placeholder ne portera JAMAIS (donnée interne).
CLES_INTERDITES = ('prix_achat', 'marge', 'cout_achat')


def _texte(valeur):
    """Valeur rendue en texte sûr pour un placeholder (jamais ``None``)."""
    if valeur is None:
        return ''
    return str(valeur)


def _propre(contexte):
    """Retire toute clé de prix d'achat / marge (garde de dernier recours)."""
    return {
        cle: valeur for cle, valeur in contexte.items()
        if not any(mot in cle.lower() for mot in CLES_INTERDITES)
    }


def _contexte_chantier(company, cible_id):
    from apps.installations.selectors import installation_scoped

    chantier = installation_scoped(company, cible_id)
    if chantier is None:
        return None
    return _champs_chantier(chantier)


def _champs_chantier(chantier):
    """APAR33 — clés d'un chantier (pur : même source pour le rendu réel et
    pour la vérification des clés d'EXEMPLES)."""
    client = getattr(chantier, 'client', None)
    return {
        'reference': _texte(getattr(chantier, 'reference', '')),
        'statut': _texte(getattr(chantier, 'statut', '')),
        'date_debut': _texte(getattr(chantier, 'date_debut', '')),
        'date_fin': _texte(getattr(chantier, 'date_fin', '')),
        'site_ville': _texte(getattr(chantier, 'site_ville', '')),
        'site_adresse': _texte(getattr(chantier, 'site_adresse', '')),
        'client_nom': _texte(client) if client is not None else '',
        'puissance_kwc': _texte(getattr(chantier, 'puissance_kwc', '')),
    }


def _contexte_client(company, cible_id):
    from apps.crm.selectors import get_company_client

    client = get_company_client(company, cible_id)
    if client is None:
        return None
    return _champs_client(client)


def _champs_client(client):
    """APAR33 — clés d'un client (pur)."""
    return {
        'nom': _texte(getattr(client, 'nom', '')),
        'prenom': _texte(getattr(client, 'prenom', '')),
        'email': _texte(getattr(client, 'email', '')),
        'telephone': _texte(getattr(client, 'telephone', '')),
        'ville': _texte(getattr(client, 'ville', '')),
        'adresse': _texte(getattr(client, 'adresse', '')),
        'ice': _texte(getattr(client, 'ice', '')),
    }


def _contexte_ticket(company, cible_id):
    from apps.sav.selectors import ticket_scoped

    ticket = ticket_scoped(company, cible_id)
    if ticket is None:
        return None
    return _champs_ticket(ticket)


def _champs_ticket(ticket):
    """APAR33 — clés d'un ticket SAV (pur)."""
    client = getattr(ticket, 'client', None)
    return {
        'reference': _texte(getattr(ticket, 'reference', '')),
        'statut': _texte(getattr(ticket, 'statut', '')),
        'priorite': _texte(getattr(ticket, 'priorite', '')),
        'type': _texte(getattr(ticket, 'type', '')),
        'description': _texte(getattr(ticket, 'description', '')),
        'client_nom': _texte(client) if client is not None else '',
    }


def _contexte_objet_custom(company, cible_id):
    # ``customfields`` est une app FONDATION : import direct autorisé.
    from apps.customfields.models import CustomRecord

    record = (CustomRecord.objects
              .filter(company=company, pk=cible_id)
              .select_related('objet').first())
    if record is None:
        return None
    contexte = {
        'id': _texte(record.pk),
        'objet_code': _texte(getattr(record.objet, 'code', '')),
        'objet_libelle': _texte(getattr(record.objet, 'libelle', '')),
    }
    donnees = record.data if isinstance(record.data, dict) else {}
    for cle, valeur in donnees.items():
        contexte[str(cle)] = _texte(valeur)
    return contexte


# ---------------------------------------------------------------------------
# NTEXT39 — contexte de DÉMONSTRATION (aperçu de mise en page).
#
# Aucune requête base, aucune donnée réelle : des valeurs d'exemple, par cible,
# pour vérifier la mise en page d'un gabarit AVANT de l'utiliser. APAR33 : un
# placeholder que le rendu réel ne servira pas n'est plus rempli d'une valeur
# inventée — il reste vide (comme au rendu) et l'aperçu le SIGNALE.
# ---------------------------------------------------------------------------

#: Valeurs d'exemple par cible (mêmes clés que les résolveurs réels ci-dessus).
EXEMPLES = {
    'chantier': {
        'reference': 'CH-2026-0042',
        'statut': 'En cours',
        'date_debut': '01/03/2026',
        'date_fin': '15/03/2026',
        'site_ville': 'Casablanca',
        'site_adresse': '12, rue de l’Exemple',
        'client_nom': 'Société Exemple SARL',
        'puissance_kwc': '12,5',
    },
    'client': {
        'nom': 'Exemple',
        'prenom': 'Amina',
        'email': 'contact@exemple.ma',
        'telephone': '+212 6 00 00 00 00',
        'ville': 'Rabat',
        'adresse': '5, avenue de la Démonstration',
        'ice': '000000000000000',
    },
    'ticket': {
        'reference': 'SAV-2026-0007',
        'statut': 'Ouvert',
        'priorite': 'Haute',
        'type': 'Panne onduleur',
        'description': "Exemple de description d'intervention.",
        'client_nom': 'Société Exemple SARL',
    },
    'objet_custom': {
        'id': '1',
        'objet_code': 'exemple',
        'objet_libelle': 'Objet de démonstration',
    },
}


#: Cibles à schéma DYNAMIQUE : leurs clés (champs ``customfields``) ne sont
#: connues qu'avec une fiche réelle — l'aperçu y garde une valeur d'exemple
#: générique plutôt qu'un faux avertissement.
CIBLES_SCHEMA_DYNAMIQUE = ('objet_custom',)


def _envelopper(cible, contexte):
    """Même enveloppe que le rendu réel : clés plates ET ``{cible: {...}}``
    (``{{ reference }}`` comme ``{{ chantier.reference }}``)."""
    return {**contexte, cible: dict(contexte)}


def _connue(nom, cible, base):
    """Vrai si le placeholder ``nom`` est servi par l'enveloppe du rendu réel."""
    parts = str(nom).split('.')
    if len(parts) == 1:
        return parts[0] in base
    return len(parts) == 2 and parts[0] == cible and parts[1] in base


def apercu_contexte(cible, variables=None):
    """APAR33 — contexte d'APERÇU + avertissements.

    Le contexte a la MÊME enveloppe que :func:`construire_contexte` (clés
    plates + ``{cible: {...}}``), alimentée par :data:`EXEMPLES` (mêmes clés
    que les résolveurs). Une variable que le rendu réel ne servira jamais
    (faute de frappe, ``{{ clien_nom }}``) n'est plus « inventée » : elle reste
    vide dans l'aperçu comme au rendu, et un avertissement la signale. La garde
    ``_propre`` s'applique comme au rendu réel.

    Retourne ``(contexte, avertissements)``.
    """
    cle = (cible or '').strip().lower()
    base = dict(EXEMPLES.get(cle, {}))
    avertissements = []
    for nom in variables or []:
        if _connue(nom, cle, base):
            continue
        if cle in CIBLES_SCHEMA_DYNAMIQUE:
            racine = str(nom).split('.')[-1]
            base.setdefault(racine, f'Exemple {racine.replace("_", " ")}')
            continue
        avertissements.append(f'variable inconnue : {nom}')
    base = _propre(base)
    return _envelopper(cle, base), avertissements


def contexte_demonstration(cible, variables=None):
    """Jeu de valeurs de DÉMONSTRATION pour ``cible`` (jamais une vraie fiche).

    APAR33 — enveloppe du rendu réel, sans valeur inventée pour une variable
    inconnue (voir :func:`apercu_contexte`, qui rend aussi les avertissements).
    """
    return apercu_contexte(cible, variables)[0]


#: Registre FERMÉ cible → constructeur de contexte.
RESOLVEURS = {
    'chantier': _contexte_chantier,
    'client': _contexte_client,
    'ticket': _contexte_ticket,
    'objet_custom': _contexte_objet_custom,
}


def cibles_supportees():
    return sorted(RESOLVEURS)


def construire_contexte(cible, company, cible_id):
    """Contexte de placeholders pour ``cible``/``cible_id``, ou ``None``.

    ``None`` quand la cible n'est pas supportée, quand l'objet n'existe pas, ou
    quand il appartient à une autre société (les selectors sont tous scopés).
    Ne lève jamais : une app absente/en erreur dégrade en ``None``.
    """
    resolveur = RESOLVEURS.get((cible or '').strip().lower())
    if resolveur is None or not cible_id:
        return None
    try:
        contexte = resolveur(company, cible_id)
    except Exception:  # pragma: no cover - défensif (app absente, id illisible)
        logger.warning('gabarits: contexte %s indisponible', cible,
                       exc_info=True)
        return None
    if contexte is None:
        return None
    contexte = _propre(contexte)
    # Deux écritures pour le même contenu : ``{{ reference }}`` (plat) et
    # ``{{ chantier.reference }}`` (préfixé par la cible, comme les exemples
    # de gabarit NTEXT18). Aucune donnée supplémentaire n'est exposée.
    return _envelopper((cible or '').strip().lower(), contexte)
