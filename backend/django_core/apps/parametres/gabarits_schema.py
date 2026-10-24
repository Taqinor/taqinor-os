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

from drf_spectacular.extensions import OpenApiSerializerFieldExtension

from core.champs_stricts import ChaineStricte
from core.openapi_erreurs import EXTENSION_CORPS_RESSERRE


def motif_gabarit(jetons):
    """Motif d'un texte dont les seules accolades sont les ``jetons`` donnés
    (``'{nom}'``…) — sans NUL."""
    noms = '|'.join(sorted(re.escape(j.strip('{}')) for j in jetons))
    if not noms:
        return r'^[^{}\u0000]*$'
    return r'^(?:[^{}\u0000]|\{(?:' + noms + r')\})*$'


class TexteGabarit(ChaineStricte):
    """``ChaineStricte`` dont le motif de REQUÊTE est celui du gabarit
    (``motif_requete``) ; validation et schéma de LECTURE inchangés (la vue garde
    ses messages précis : placeholder inconnu, accolade isolée)."""

    motif_requete = None


def promouvoir_texte_gabarit(champ, motif):
    """Promeut SUR PLACE un ``ChaineStricte`` construit en ``TexteGabarit``
    (réaffectation de ``__class__`` : arguments d'origine conservés, même patron
    que ``core.serializers.scope_related_field``)."""
    if type(champ) is ChaineStricte:
        champ.__class__ = TexteGabarit
        champ.motif_requete = motif
    return champ


class _TexteGabaritSchema(OpenApiSerializerFieldExtension):
    target_class = 'apps.parametres.gabarits_schema.TexteGabarit'
    priority = 1  # devant l'extension générique de ChaineStricte (sans NUL)

    def map_serializer_field(self, auto_schema, direction):
        schema = auto_schema._map_serializer_field(
            self.target, direction, bypass_extensions=True)
        if direction == 'request' and schema.get('type') == 'string':
            schema = dict(schema)
            schema['pattern'] = self.target.motif_requete
        return schema


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
