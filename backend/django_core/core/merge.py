"""NTDATA18/19 — REPOINTAGE des références lors d'une fusion de fiches.

Fondation PURE : aucune app métier importée (contrat import-linter
``core-foundation-is-a-base-layer``). La fonction ne connaît que l'API
``_meta`` de Django — on lui passe deux instances du MÊME modèle et elle
déplace tout ce qui pointait la première vers la seconde.

POURQUOI CE MODULE EXISTE. Fusionner deux clients, deux fournisseurs ou deux
produits pose exactement le même problème : « ne laisser AUCUN orphelin ». Une
liste de modèles écrite à la main (« devis, factures, chantiers, tickets ») en
oublie forcément — le dépôt compte plus de trente FK vers ``crm.Client`` — et
elle vieillit mal : chaque nouvelle app qui référence un client devrait penser
à venir s'y ajouter. On parcourt donc les RELATIONS INVERSES déclarées.

CE QUE LA FONCTION NE FAIT PAS. Elle ne supprime rien, ne touche pas les
champs des deux fiches et ne décide pas laquelle survit : l'app propriétaire
garde ces décisions (et son archivage, qui lui est propre).

UNE RELATION QUI REFUSE N'EST JAMAIS TUE. Un ``UniqueConstraint`` déjà occupé
chez le survivant (sa limite de crédit, son profil de sous-traitant…) fait
échouer CETTE relation seule : elle est annulée dans son propre point de
sauvegarde et NOMMÉE dans le rapport, pour qu'un humain tranche. Le reste de
la fusion aboutit.
"""
from __future__ import annotations


def relations_inverses(modele):
    """Les relations inverses REPOINTABLES d'un modèle (FK et OneToOne).

    Les many-to-many sont exclus : leur table de liaison se traite par ajout,
    pas par déplacement, et la fusionner supposerait une règle métier (union ?
    intersection ?) que seule l'app propriétaire peut trancher.
    """
    return [
        rel for rel in modele._meta.related_objects
        if getattr(rel, 'field', None) is not None and not rel.many_to_many
    ]


def repointer_relations(source, cible):
    """Déplace vers ``cible`` tout ce qui référençait ``source``.

    ``source`` et ``cible`` sont deux instances du MÊME modèle. Renvoie
    ``(repointes, non_repointes)`` où ``repointes`` est
    ``{'<app>.<Modele>.<champ>': nombre_de_lignes}`` et ``non_repointes`` une
    liste de ``{'relation', 'motif'}``.

    À appeler DANS une transaction de l'appelant : chaque relation ouvre son
    propre point de sauvegarde pour qu'un refus n'annule pas le reste.
    """
    from django.db import IntegrityError, transaction

    repointes = {}
    non_repointes = []
    for rel in relations_inverses(type(source)):
        modele = rel.related_model
        nom_champ = rel.field.name
        etiquette = '%s.%s.%s' % (
            modele._meta.app_label, modele.__name__, nom_champ)
        try:
            with transaction.atomic():
                # ``_base_manager`` : un gestionnaire par défaut qui FILTRE
                # (soft-delete, archivés…) laisserait des lignes pointer la
                # fiche absorbée — donc des orphelins invisibles.
                n = modele._base_manager.filter(
                    **{nom_champ: source}).update(**{nom_champ: cible})
        except IntegrityError as exc:
            non_repointes.append({'relation': etiquette, 'motif': str(exc)})
            continue
        if n:
            repointes[etiquette] = repointes.get(etiquette, 0) + n
    return repointes, non_repointes


def completer_champs_vides(cible, source, champs):
    """Complète les champs VIDES de ``cible`` depuis ``source``.

    Ne remplace JAMAIS une valeur déjà saisie : dans une fusion, ce que
    l'humain a écrit sur la fiche qu'il garde fait autorité. Renvoie la liste
    des champs effectivement complétés.
    """
    completes = []
    for champ in champs:
        courant = getattr(cible, champ, None)
        if courant in (None, '', False):
            valeur = getattr(source, champ, None)
            if valeur not in (None, '', False):
                setattr(cible, champ, valeur)
                completes.append(champ)
    return completes
