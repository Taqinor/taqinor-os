"""NTAPI36 — traduction des références d'articles pour un partenaire EDI.

Le registre (``models.PartenaireEdi``) dit QUI est le partenaire et COMMENT
traduire les codes ; ce module porte la traduction elle-même, dans les DEUX
sens, sous une forme que les générateurs/parseurs EDI consomment sans les
connaître :

* ``traduire_lignes`` — SORTIE (export INVOIC/810) : remplace chaque SKU
  interne par le code du partenaire ;
* ``resoudre_sku`` — ENTRÉE (import ORDERS/850) : retrouve le SKU interne
  depuis le code du partenaire.

LA RÈGLE QUI COMPTE : un SKU absent du mapping n'est JAMAIS bloquant. On
renvoie le SKU interne tel quel ET un avertissement listé. Refuser l'export
entier pour un article accessoire non mappé bloquerait une facture complète,
alors qu'un code non reconnu côté partenaire se règle par un échange humain en
aval — c'est exactement ce que demande le critère d'acceptation NTAPI36
(« absence de mapping = SKU brut + warning »).

Périmètre : ce module ne GÉNÈRE aucun message EDI et ne transmet rien. Les
générateurs INVOIC/ORDERS/X12 (NTAPI33/34/35) le CONSOMMENT quand ils seront
construits ; sans eux, ce registre reste inerte.
"""
from __future__ import annotations


def partenaire_pour(company, identifiant):
    """Partenaire ACTIF d'une société par son GLN/DUNS, ou ``None``.

    Scopé société : un identifiant appartenant à une autre société n'est jamais
    résolu (il n'y a donc aucun moyen de traduire avec le mapping d'autrui)."""
    from .models import PartenaireEdi

    if not identifiant:
        return None
    return PartenaireEdi.objects.filter(
        company=company, identifiant=identifiant, actif=True).first()


def traduire_lignes(partenaire, lignes):
    """SORTIE — traduit les SKU internes en codes partenaire.

    ``lignes`` : itérable de dicts portant au moins ``sku``. Renvoie
    ``(lignes_traduites, avertissements)`` où chaque ligne traduite gagne
    ``code_article`` (le code servi dans le message) et ``code_mappe`` (booléen
    disant si la traduction a eu lieu). Les lignes d'origine ne sont JAMAIS
    mutées — un générateur qui rejoue le même lot doit repartir des mêmes
    données.

    ``partenaire`` à ``None`` (aucun partenaire déclaré) : chaque SKU est servi
    brut, avec un avertissement — même politique que le mapping absent.
    """
    traduites = []
    avertissements = []
    for ligne in lignes or []:
        source = dict(ligne or {})
        sku = source.get('sku') or ''
        code = partenaire.code_pour_sku(sku) if partenaire is not None else None
        if code:
            source['code_article'] = code
            source['code_mappe'] = True
        else:
            # SKU brut + avertissement — jamais un refus d'export.
            source['code_article'] = sku
            source['code_mappe'] = False
            avertissements.append(
                f"SKU « {sku} » sans code partenaire : le SKU interne est "
                f"envoyé tel quel.")
        traduites.append(source)
    return traduites, avertissements


def resoudre_sku(partenaire, code_partenaire):
    """ENTRÉE — retrouve le SKU interne depuis un code partenaire.

    Renvoie ``(sku, avertissement_ou_None)``. Sans correspondance, on renvoie
    le code REÇU tel quel plus un avertissement : c'est au pipeline d'import
    (NTAPI34) de décider — il liste les lignes non appariées sans bloquer les
    autres, et n'invente JAMAIS de montant ni de produit.
    """
    if partenaire is not None:
        sku = partenaire.sku_pour_code(code_partenaire)
        if sku:
            return sku, None
    return code_partenaire, (
        f"Code partenaire « {code_partenaire} » inconnu du mapping : aucune "
        f"correspondance SKU interne.")
