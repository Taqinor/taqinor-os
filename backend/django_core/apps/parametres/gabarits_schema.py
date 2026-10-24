"""3e drainage api-fuzz (24/10/2026) — contrat PUBLIÉ des textes à placeholders
(modèles d'e-mail, modèles de message WhatsApp).

Le serveur n'accepte, dans un sujet / corps de gabarit, que des accolades qui
forment un placeholder AUTORISÉ pour la clé (``{reference}``…) : un
``{prenom}`` inconnu ou une accolade isolée répond 400 (L775, APAR12, APAR13).
Le schéma publié ne le disait pas (``string`` seul) : le fuzz envoyait des
textes « conformes » refusés. Ici le schéma dit la règle : un texte est une
suite de caractères SANS accolade ni NUL, ou de placeholders autorisés. Le
schéma est toujours au plus aussi large que le serveur (``{{`` échappé, que le
rendu accepte, n'est pas annoncé) ; le serveur, lui, n'est pas modifié.
"""
import re

from django.core.validators import RegexValidator

from core.openapi_erreurs import EXTENSION_CORPS_RESSERRE


def motif_gabarit(jetons):
    """Motif d'un texte dont les seules accolades sont les ``jetons`` donnés
    (``'{nom}'``…) — sans NUL."""
    noms = '|'.join(sorted(re.escape(j.strip('{}')) for j in jetons))
    if not noms:
        return r'^[^{}\u0000]*$'
    return r'^(?:[^{}\u0000]|\{(?:' + noms + r')\})*$'


class PublieMotif(RegexValidator):
    """PUBLIE un motif dans le schéma sans rien valider : la vue garde ses
    messages précis (placeholder inconnu, accolade isolée). Même patron que
    ``crm.champs_api.IcePublie``."""

    def __init__(self, motif):
        super().__init__(regex=motif, message='Texte invalide.', code='invalid')

    def __call__(self, value):
        return None


def corps_messages_par_cle(cles, jetons_de):
    """Extension de corps de ``PUT messages/`` : un texte FR / Darija n'a que
    les placeholders de SA clé (``jetons_de(cle)``) ; une réinitialisation
    (``reset: true``) ne lit aucun texte. Les clés qui partagent la même liste
    blanche sont regroupées en une seule branche."""
    groupes = {}
    for cle in cles:
        groupes.setdefault(frozenset(jetons_de(cle)), []).append(cle)
    branches = [{'required': ['reset'],
                 'properties': {'reset': {'enum': [True]}}}]
    for jetons, liste in groupes.items():
        motif = {'pattern': motif_gabarit(jetons)}
        branches.append({'properties': {
            'cle': {'enum': sorted(liste)},
            'corps_fr': dict(motif), 'corps_darija': dict(motif)}})
    return {EXTENSION_CORPS_RESSERRE: {'anyOf': branches}}
