"""CAL45 — écriture des réglages société du module Calepinage.

UNE base, sept extensions : chaque tâche suivante ÉTEND une section, elle ne
crée plus de modèle. Ce service est le SEUL chemin d'écriture des réglages —
l'endpoint ``PUT /api/django/calepinage/parametres/`` l'appellera, il ne
touchera jamais le modèle directement.

Deux refus explicites, en français et en NOMMANT la clé fautive :
  * une SECTION inconnue (on ne range pas un réglage dans un tiroir qui
    n'existe pas — le fondateur doit voir LAQUELLE) ;
  * une section qui n'est pas un objet.

La société est TOUJOURS celle passée par l'appelant (posée côté serveur),
jamais lue d'un corps de requête.
"""
from __future__ import annotations


class ReglageInvalide(ValueError):
    """Erreur métier : un réglage refusé, avec un message français.

    ``champ`` nomme la section fautive pour que l'écran puisse pointer LE
    champ concerné au lieu d'afficher un « non enregistré » générique.
    """

    def __init__(self, message, *, champ=''):
        super().__init__(message)
        self.champ = champ


def enregistrer_parametres(company, donnees, *, remplacer=False):
    """Pose les sections de ``donnees`` sur les réglages de ``company``.

    Args:
        company: la société — posée côté serveur, jamais lue de la requête.
        donnees: ``{section: objet}``. Les sections ABSENTES sont laissées
            telles quelles (mise à jour partielle) sauf si ``remplacer``.
        remplacer: ``True`` remet à ``{}`` les sections non fournies.

    Returns:
        Le dict complet des sections admises, comme le rend le sélecteur.

    Raises:
        ReglageInvalide: section inconnue, ou section qui n'est pas un objet.
    """
    from django.db import IntegrityError, transaction

    from ..models import ParametresCalepinage
    from ..selectors import SECTIONS_PARAMETRES, parametres_de_societe

    if company is None:
        raise ReglageInvalide(
            "Les réglages de calepinage sont toujours rattachés à une "
            "société : aucune société n'a été fournie.", champ='company')

    donnees = donnees or {}
    inconnues = ParametresCalepinage.sections_inconnues(donnees)
    if inconnues:
        raise ReglageInvalide(
            "Section de réglages inconnue : "
            f"« {', '.join(inconnues)} ». Sections admises : "
            f"{', '.join(SECTIONS_PARAMETRES)}.",
            champ=inconnues[0])

    for section, valeur in donnees.items():
        if not isinstance(valeur, dict):
            raise ReglageInvalide(
                f"La section « {section} » doit être un objet "
                f"(reçu : {type(valeur).__name__}).", champ=section)

    # CAL47 — une section peut avoir son PROPRE domaine de validité (contrat
    # CAL46 pour « imagerie »). Le crochet est ici, une fois : chaque section
    # qui se dote d'un normaliseur l'enregistre dans ``_normaliseurs()`` au lieu
    # d'ouvrir un second chemin d'écriture. Une section sans normaliseur passe
    # inchangée — comportement d'aujourd'hui, strictement préservé.
    donnees = _normaliser(donnees)

    with transaction.atomic():
        # `UniqueConstraint(['company'])` fait foi : on LIT d'abord, et si deux
        # requêtes concurrentes créent en même temps, la base tranche
        # (IntegrityError) et on relit la ligne gagnante — jamais deux jeux de
        # réglages pour une même société.
        reglages = ParametresCalepinage.objects.filter(
            company=company).order_by('id').first()
        if reglages is None:
            try:
                with transaction.atomic():
                    reglages = ParametresCalepinage.objects.create(
                        company=company)
            except IntegrityError:
                reglages = ParametresCalepinage.objects.filter(
                    company=company).order_by('id').first()
        for section in SECTIONS_PARAMETRES:
            if section in donnees:
                setattr(reglages, section, donnees[section])
            elif remplacer:
                setattr(reglages, section, {})
        reglages.full_clean(exclude=['company'])
        reglages.save()

    return parametres_de_societe(company)


def _normaliseurs():
    """``{section: normaliseur}`` — les sections qui ont leur propre domaine.

    Import FONCTION-LOCAL : ``services/site.py`` importe ``ReglageInvalide``
    de ce module ; le résoudre au chargement ferait un cycle.
    """
    from .degagements import (
        SECTION as SECTION_DEGAGEMENTS, normaliser_section_degagements,
    )
    from .gabarits import (
        SECTION as SECTION_GABARITS,
        normaliser_section_gabarits_disposition,
    )
    from .lestage import (
        SECTION as SECTION_LESTAGE, normaliser_section_lestage,
    )
    from .site import SECTION as SECTION_IMAGERIE, normaliser_section_imagerie
    from .zones_reglementaires import (
        SECTION as SECTION_ZONES, normaliser_section_zones_types,
    )

    from .parametres_cles import (
        SECTION_ELECTRIQUE_SOCIETE, SECTION_SIMULATION,
    )

    return {
        SECTION_IMAGERIE: normaliser_section_imagerie,
        SECTION_ZONES: normaliser_section_zones_types,
        SECTION_DEGAGEMENTS: normaliser_section_degagements,
        SECTION_GABARITS: normaliser_section_gabarits_disposition,
        SECTION_LESTAGE: normaliser_section_lestage,
        # CALX145 — les deux sections à REGISTRE : leurs clés sont déclarées
        # une par une dans ``parametres_cles.py`` et chaque valeur porte sa
        # provenance. Même crochet que les cinq autres, aucun second chemin
        # d'écriture.
        SECTION_SIMULATION: _normaliser_section_simulation,
        SECTION_ELECTRIQUE_SOCIETE: _normaliser_section_electrique_societe,
    }


def _normaliser(donnees):
    """Applique le normaliseur de chaque section fournie qui en a un.

    Une section SANS normaliseur traverse inchangée : ajouter un domaine de
    validité à une section ne change RIEN aux six autres.
    """
    normaliseurs = _normaliseurs()
    concernees = [s for s in donnees if s in normaliseurs]
    if not concernees:
        return donnees
    donnees = dict(donnees)
    for section in concernees:
        donnees[section] = normaliseurs[section](donnees[section])
    return donnees


# ── CALX145 — les deux sections À REGISTRE ──────────────────────────────────
#
# Les cinq normaliseurs précédents connaissent CHACUN le vocabulaire de leur
# section. Les deux sections ouvertes par CALX145 n'ont pas ce luxe : leurs
# clés arrivent une par une, au fil des étapes de la chaîne de pertes et des
# contrôles électriques. Leur domaine de validité est donc DÉCLARATIF — le
# registre append-only ``services/parametres_cles.py`` — et la règle de saisie
# est la même pour toutes : ``{valeur, source, reference}``.
#
# Trois refus, chacun NOMMANT le champ fautif (jamais un « non enregistré »
# générique) : clé hors registre, valeur sans provenance admise, valeur vide.

def _normaliser_section_simulation(valeur):
    """La section ``simulation`` VALIDÉE — ``{}`` si rien n'est saisi."""
    from .parametres_cles import SECTION_SIMULATION

    return _normaliser_section_a_registre(SECTION_SIMULATION, valeur)


def _normaliser_section_electrique_societe(valeur):
    """La section ``electrique_societe`` VALIDÉE, même discipline."""
    from .parametres_cles import SECTION_ELECTRIQUE_SOCIETE

    return _normaliser_section_a_registre(SECTION_ELECTRIQUE_SOCIETE, valeur)


def _normaliser_section_a_registre(section, valeur):
    """Une section dont les clés ADMISES sont déclarées au registre.

    Args:
        section: ``'simulation'`` ou ``'electrique_societe'``.
        valeur: la section telle que l'appelant l'envoie.

    Returns:
        ``{}`` quand rien n'est saisi — ÉQUIVALENCE : aucune étape ne change
        de comportement, chacune reste omise en nommant ce qui lui manque —
        sinon les seules clés saisies, chacune
        ``{'valeur', 'source', 'reference'}``.

    Raises:
        ReglageInvalide: message FRANÇAIS nommant la clé fautive.
    """
    from .parametres_cles import SOURCES_ADMISES, registre

    if valeur is None:
        return {}
    if not isinstance(valeur, dict):
        raise ReglageInvalide(
            f"La section « {section} » doit être un objet "
            f"(reçu : {type(valeur).__name__}).", champ=section)
    if not valeur:
        return {}

    declarations = registre(section)
    inconnues = sorted(set(valeur) - set(declarations))
    if inconnues:
        raise ReglageInvalide(
            f"Réglage inconnu dans « {section} » : "
            f"« {', '.join(inconnues)} ». Clés admises : "
            f"{', '.join(sorted(declarations))}.",
            champ=inconnues[0])

    propre = {}
    for cle, brut in valeur.items():
        libelle = declarations[cle][0]
        if brut is None:
            # Clé retirée : on revient au « non saisi », donc au comportement
            # d'aujourd'hui. Rien n'est stocké, rien n'est deviné.
            continue
        if not isinstance(brut, dict):
            raise ReglageInvalide(
                f"« {libelle} » se saisit avec sa provenance : "
                '{"valeur": …, "source": …, "reference": "…"} '
                f"(reçu : {type(brut).__name__}).", champ=cle)
        surplus = sorted(set(brut) - {'valeur', 'source', 'reference'})
        if surplus:
            raise ReglageInvalide(
                f"« {libelle} » n'accepte que « valeur », « source » et "
                f"« reference » (reçu en plus : {', '.join(surplus)}).",
                champ=cle)
        propre[cle] = {
            'valeur': _valeur_declaree(brut.get('valeur'), cle, libelle),
            'source': _source_declaree(brut.get('source'), cle, libelle,
                                       SOURCES_ADMISES),
            'reference': _reference_declaree(brut.get('reference'), cle,
                                             libelle),
        }
    return propre


def _valeur_declaree(valeur, cle, libelle):
    """La valeur SAISIE — un nombre, un texte ou une table, jamais du vide.

    Le registre ne dit pas de quel TYPE est une valeur : une tolérance est un
    nombre, un mode est un mot, les coefficients thermiques par type de pose
    sont une table. Ce qui est refusé ici, c'est le VIDE : une clé déclarée
    qui ne porte rien ne dit rien et ferait croire à un réglage.
    """
    vide = (valeur is None
            or (isinstance(valeur, str) and not valeur.strip())
            or (isinstance(valeur, (dict, list, tuple)) and not valeur))
    if vide:
        raise ReglageInvalide(
            f"« {libelle} » doit porter une valeur : une clé déclarée sans "
            "valeur ne règle rien. Retirez-la pour revenir au comportement "
            "d'aujourd'hui.", champ=cle)
    if isinstance(valeur, str):
        return valeur.strip()
    if isinstance(valeur, tuple):
        return list(valeur)
    return valeur


def _source_declaree(source, cle, libelle, admises):
    """La PROVENANCE, obligatoire : sans elle, la valeur est refusée."""
    if not isinstance(source, str) or not source.strip():
        raise ReglageInvalide(
            f"« {libelle} » doit porter sa provenance « source » : aucune "
            "valeur n'est admise sans elle. Provenances admises : "
            f"{', '.join(admises)}.", champ=cle)
    source = source.strip()
    if source not in admises:
        raise ReglageInvalide(
            f"« {libelle} » : provenance « {source} » inconnue. Provenances "
            f"admises : {', '.join(admises)}.", champ=cle)
    return source


def _reference_declaree(reference, cle, libelle):
    """La référence du texte ou de la décision — un texte, jamais autre chose.

    Elle peut rester VIDE (une valeur arrêtée par la société se défend par sa
    provenance ``societe``), mais elle ne peut pas être autre chose qu'un
    texte : une référence numérique ne se relit pas.
    """
    if reference is None:
        return ''
    if not isinstance(reference, str):
        raise ReglageInvalide(
            f"« {libelle} » : la référence doit être un texte "
            f"(reçu : {type(reference).__name__}).", champ=cle)
    return reference.strip()
