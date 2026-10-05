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

    def __init__(self, message, *, champ='', section=''):
        super().__init__(message)
        self.champ = champ
        # ACAL132 — la SECTION à registre qui porte la clé fautive : la vue
        # répond alors ``{section: {clé: motif}}`` (contrat
        # ``parametres_calepinage.json::exemple_refus_type``).
        self.section = section


class ReglageInterdit(ReglageInvalide):
    """ACAL302 — une clé de GOUVERNANCE changée sans le droit
    ``calepinage_approuver`` : la vue répond 403 en nommant la clé."""


#: ACAL302 — le message du refus, le même pour les trois clés.
MESSAGE_GOUVERNANCE = ('Changer ce réglage exige le droit « Approuver un '
                       'calepinage ».')


def _cles_de_gouvernance():
    """``(section, clé)`` des réglages qui gouvernent l'accès et le contrôle :
    vue restreinte au responsable, approbation exigée, feu vert bureau
    d'études (défaut gravé : ``calepinage_approuver``)."""
    from ..selectors import CLE_VUE_RESTREINTE
    from .approbation import CLE_EXIGEE
    from .feu_vert import CLE_ACTIF
    from .presets import SECTION

    return ((SECTION, CLE_VUE_RESTREINTE), (SECTION, CLE_EXIGEE),
            (SECTION, CLE_ACTIF))


def _exiger_droit_de_gouvernance(avant, apres, user):
    """Refuse (``ReglageInterdit``) une clé de gouvernance dont la valeur
    STOCKÉE change sans ``calepinage_approuver``. Une valeur recopiée à
    l'identique passe ; ``user`` absent = appel système (commande, seed)."""
    if user is None:
        return
    from core.permissions import _user_has_or_legacy

    from ..permissions import CAL_APPROUVER

    for section, cle in _cles_de_gouvernance():
        ancienne = (avant.get(section) or {}).get(cle)
        nouvelle = (apres.get(section) or {}).get(cle)
        if ancienne != nouvelle and not _user_has_or_legacy(
                user, CAL_APPROUVER):
            raise ReglageInterdit(MESSAGE_GOUVERNANCE, champ=cle)


def _texte_journal(valeur):
    import json

    if valeur is None:
        return ''
    if isinstance(valeur, (dict, list, tuple)):
        return json.dumps(valeur, ensure_ascii=False, sort_keys=True)
    return str(valeur)


def _journaliser(company, user, avant, apres):
    """ACAL302 — UNE ligne ``SettingsAuditLog`` par clé effectivement
    changée (section ``calepinage``, champ ``<section>.<clé>``, avant →
    après, auteur) ; un PUT sans changement n'écrit rien."""
    from apps.parametres.models_audit import SettingsAuditLog

    for section in sorted(set(avant) | set(apres)):
        ancienne = avant.get(section) or {}
        nouvelle = apres.get(section) or {}
        if ancienne == nouvelle:
            continue
        for cle in sorted(set(ancienne) | set(nouvelle)):
            if ancienne.get(cle) == nouvelle.get(cle):
                continue
            SettingsAuditLog.log_change(
                company, user, 'calepinage', f'{section}.{cle}',
                f'Calepinage › {section} › {cle}',
                _texte_journal(ancienne.get(cle)),
                _texte_journal(nouvelle.get(cle)))


def enregistrer_parametres(company, donnees, *, remplacer=False, user=None):
    """Pose les sections de ``donnees`` sur les réglages de ``company``.

    Args:
        company: la société — posée côté serveur, jamais lue de la requête.
        donnees: ``{section: objet}``. Les sections ABSENTES sont laissées
            telles quelles (mise à jour partielle) sauf si ``remplacer``.
        remplacer: ``True`` remet à ``{}`` les sections non fournies.
        user: ACAL302 — l'auteur (``request.user``) : il signe le journal
            d'audit, et changer une clé de gouvernance exige
            ``calepinage_approuver``.

    Returns:
        Le dict complet des sections admises, comme le rend le sélecteur.

    Raises:
        ReglageInvalide: section inconnue, ou section qui n'est pas un objet.
        ReglageInterdit: clé de gouvernance changée sans le droit — RIEN
            n'est écrit.
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
        # ACAL132 (D-ACAL-8) — une section À REGISTRE se FUSIONNE clé par
        # clé : les clés envoyées remplacent les stockées, une clé envoyée à
        # ``null`` est retirée, les autres sont CONSERVÉES. Fusion AVANT la
        # normalisation : la section entière (stockée + envoyée) est revalidée
        # par type, et le refus nomme la clé fautive (rien n'est écrit :
        # ``atomic``).
        if not remplacer:
            donnees = _fusionner_sections_a_registre(reglages, donnees)
        donnees = _normaliser(donnees)
        avant = {section: getattr(reglages, section) or {}
                 for section in SECTIONS_PARAMETRES}
        for section in SECTIONS_PARAMETRES:
            if section in donnees:
                setattr(reglages, section, donnees[section])
            elif remplacer:
                setattr(reglages, section, {})
        apres = {section: getattr(reglages, section) or {}
                 for section in SECTIONS_PARAMETRES}
        _exiger_droit_de_gouvernance(avant, apres, user)
        reglages.full_clean(exclude=['company'])
        reglages.save()
        _journaliser(company, user, avant, apres)

    return parametres_de_societe(company)


def _fusionner_sections_a_registre(reglages, donnees):
    """ACAL132 — ``donnees`` où chaque section à registre est FUSIONNÉE.

    ``{**stockée, **envoyée}`` : une clé absente de l'envoi garde sa valeur
    stockée, une clé envoyée à ``None`` reste ``None`` dans la fusion (le
    normaliseur la retire), une section envoyée qui n'est pas un objet est
    laissée telle quelle (le normaliseur la refuse en la nommant). Les autres
    sections gardent leur règle : la section envoyée remplace la stockée
    (leurs écrans — presets, dégagements — renvoient la section entière).
    """
    from .parametres_cles import REGISTRES

    fusion = dict(donnees)
    for section in REGISTRES:
        envoyee = donnees.get(section)
        if not isinstance(envoyee, dict):
            continue
        stockee = getattr(reglages, section, None)
        stockee = stockee if isinstance(stockee, dict) else {}
        fusion[section] = {**stockee, **envoyee}
    return fusion


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
    from .presets import SECTION as SECTION_PRESETS, normaliser_section_presets

    return {
        # CALX348 — ``presets`` ne valide QUE ``approbation_exigee`` (booléen) ;
        # toutes ses autres clés traversent inchangées.
        SECTION_PRESETS: normaliser_section_presets,
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
    """La section à registre normalisée ; tout refus d'une CLÉ porte sa
    ``section`` (ACAL132) pour que la vue la nomme dans sa section."""
    try:
        return _normaliser_cles_a_registre(section, valeur)
    except ReglageInvalide as refus:
        if not refus.section and refus.champ and refus.champ != section:
            refus.section = section
        raise


def _normaliser_cles_a_registre(section, valeur):
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
            'valeur': _valeur_declaree(brut.get('valeur'), cle, libelle,
                                       section=section),
            'source': _source_declaree(brut.get('source'), cle, libelle,
                                       SOURCES_ADMISES),
            'reference': _reference_declaree(brut.get('reference'), cle,
                                             libelle),
        }
    return propre


def _valeur_declaree(valeur, cle, libelle, *, section=''):
    """La valeur SAISIE, VALIDÉE ET NORMALISÉE selon le type de sa clé.

    Deux refus, chacun nommant la clé : le VIDE (une clé déclarée qui ne
    porte rien ne dit rien et ferait croire à un réglage) ; puis (ACAL132)
    une valeur qui ne se lit pas dans le TYPE déclaré par
    ``parametres_cles.TYPES_CLES`` — « 2,5 » devient 2.5, « abc » est refusé
    à l'écriture au lieu de faire basculer l'étape qui la lit sur un repli.
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
        valeur = valeur.strip()
    if isinstance(valeur, tuple):
        valeur = list(valeur)
    return _valeur_typee(valeur, cle, libelle, section)


# ── ACAL132 — le TYPE de chaque clé ─────────────────────────────────────────

_VRAIS = ('oui', 'vrai', 'true', '1', 'active', 'activee', 'activée')
_FAUX = ('non', 'faux', 'false', '0', 'aucune', 'sans', 'desactivee',
         'désactivée', 'inactive')

_NOMS_DE_TYPE = {
    'nombre': 'un nombre',
    'pourcentage': 'un pourcentage',
    'entier': 'un entier',
    'enum': 'un des mots admis',
    'table_mensuelle': 'un nombre unique ou douze valeurs mensuelles',
    'intervalle_annees': 'deux années « 2015-2024 » ou [2015, 2024]',
    'booleen': 'oui ou non',
    'table': 'une table (objet ou liste)',
}


def _nom_du_type_recu(valeur):
    if isinstance(valeur, bool):
        return 'booléen'
    if isinstance(valeur, (int, float)):
        return 'nombre'
    if isinstance(valeur, str):
        return 'texte'
    if isinstance(valeur, (list, tuple)):
        return 'liste'
    if isinstance(valeur, dict):
        return 'objet'
    return type(valeur).__name__


def _bornes_lisibles(declaration):
    mini, maxi = declaration.get('minimum'), declaration.get('maximum')
    if mini is not None and maxi is not None:
        return f'nombre entre {mini} et {maxi}'
    if mini is not None:
        return f'au moins {mini}'
    if maxi is not None:
        return f'au plus {maxi}'
    return ''


def _refus_de_type(valeur, cle, libelle, section, declaration, precision=''):
    """Le refus FRANÇAIS qui nomme la clé, le type reçu et le type attendu."""
    attendu = _NOMS_DE_TYPE.get(declaration.get('type'), 'une valeur lisible')
    bornes = _bornes_lisibles(declaration)
    if bornes:
        attendu = f'{attendu} ({bornes})'
    if declaration.get('valeurs'):
        attendu = f"{attendu} : {', '.join(declaration['valeurs'])}"
    message = (f'Valeur de type {_nom_du_type_recu(valeur)} reçue : '
               f'« {cle} » ({libelle}) attend {attendu}.')
    if precision:
        message = f'{message} {precision}'
    return ReglageInvalide(message, champ=cle, section=section)


def _nombre_lu(valeur):
    """Un réel FINI depuis un nombre ou un texte (« 2,5 » admis), sinon None.

    Un booléen n'est jamais un nombre ; ``nan`` / ``inf`` ne se lisent pas.
    """
    import math

    if isinstance(valeur, bool):
        return None
    if isinstance(valeur, (int, float)):
        nombre = valeur
    elif isinstance(valeur, str):
        texte = valeur.strip().replace(' ', '').replace('\u00a0', '')
        if texte.count(',') == 1 and '.' not in texte:
            texte = texte.replace(',', '.')
        try:
            nombre = float(texte)
        except ValueError:
            return None
    else:
        return None
    try:
        return nombre if math.isfinite(nombre) else None
    except OverflowError:
        return None


def _dans_les_bornes(nombre, declaration):
    mini, maxi = declaration.get('minimum'), declaration.get('maximum')
    return ((mini is None or nombre >= mini)
            and (maxi is None or nombre <= maxi))


def _nombre_borne(valeur, cle, libelle, section, declaration):
    """Un réel fini dans ses bornes ; un texte entier (« 60 ») rend un int."""
    nombre = _nombre_lu(valeur)
    if nombre is None:
        raise _refus_de_type(valeur, cle, libelle, section, declaration)
    if not _dans_les_bornes(nombre, declaration):
        raise _refus_de_type(valeur, cle, libelle, section, declaration,
                             f'Reçu : {nombre:g}, hors bornes.')
    if isinstance(valeur, str) and not any(c in valeur for c in '.,eE'):
        return int(nombre)
    return nombre


def _valeur_typee(valeur, cle, libelle, section):
    """``valeur`` lue dans le type déclaré de ``cle`` — ou le refus nommé."""
    from .parametres_cles import type_de_cle

    declaration = type_de_cle(section, cle)
    genre = declaration.get('type')
    if genre in ('nombre', 'pourcentage'):
        return _nombre_borne(valeur, cle, libelle, section, declaration)
    if genre == 'entier':
        nombre = _nombre_lu(valeur)
        if nombre is None or not float(nombre).is_integer():
            raise _refus_de_type(valeur, cle, libelle, section, declaration)
        if not _dans_les_bornes(nombre, declaration):
            raise _refus_de_type(valeur, cle, libelle, section, declaration,
                                 f'Reçu : {nombre:g}, hors bornes.')
        return int(nombre)
    if genre == 'enum':
        mot = valeur.strip().lower() if isinstance(valeur, str) else None
        if mot not in declaration.get('valeurs', ()):
            raise _refus_de_type(valeur, cle, libelle, section, declaration)
        return mot
    if genre == 'booleen':
        return _booleen(valeur, cle, libelle, section, declaration)
    if genre == 'intervalle_annees':
        return _intervalle_annees(valeur, cle, libelle, section, declaration)
    if genre == 'table_mensuelle':
        return _table_mensuelle(valeur, cle, libelle, section, declaration)
    if genre == 'table':
        if not isinstance(valeur, (dict, list)):
            raise _refus_de_type(valeur, cle, libelle, section, declaration)
        return valeur
    # Clé sans type déclaré : la garde de test l'interdit ; rien n'est deviné.
    return valeur


def _booleen(valeur, cle, libelle, section, declaration):
    if isinstance(valeur, bool):
        return valeur
    if isinstance(valeur, (int, float)) and valeur in (0, 1):
        return bool(valeur)
    mot = valeur.strip().lower() if isinstance(valeur, str) else None
    if mot in _VRAIS:
        return True
    if mot in _FAUX:
        return False
    raise _refus_de_type(valeur, cle, libelle, section, declaration)


def _intervalle_annees(valeur, cle, libelle, section, declaration):
    """``[début, fin]`` depuis « 2015-2024 » ou ``[2015, 2024]``."""
    morceaux = ()
    if isinstance(valeur, list) and len(valeur) == 2:
        morceaux = valeur
    elif isinstance(valeur, str) and '-' in valeur[1:]:
        coupure = valeur.index('-', 1)
        morceaux = (valeur[:coupure], valeur[coupure + 1:])
    bornes = []
    for morceau in morceaux:
        nombre = _nombre_lu(morceau)
        if nombre is None or not float(nombre).is_integer():
            break
        bornes.append(int(nombre))
    if len(bornes) != 2 or bornes[0] > bornes[1]:
        raise _refus_de_type(valeur, cle, libelle, section, declaration)
    return bornes


def _table_mensuelle(valeur, cle, libelle, section, declaration):
    """Un nombre (les douze mois), douze valeurs, ou un objet keyé 1…12.

    Une valeur mensuelle peut porter sa propre provenance
    (``{valeur, source}``, albédo) : seule sa ``valeur`` est lue et bornée.
    """
    def _mois(brut):
        if isinstance(brut, dict):
            if 'valeur' not in brut:
                raise _refus_de_type(brut, cle, libelle, section, declaration)
            return {**brut, 'valeur': _nombre_borne(
                brut['valeur'], cle, libelle, section, declaration)}
        return _nombre_borne(brut, cle, libelle, section, declaration)

    if isinstance(valeur, list):
        if len(valeur) != 12:
            raise _refus_de_type(
                valeur, cle, libelle, section, declaration,
                f'Reçu : {len(valeur)} valeurs, douze attendues.')
        return [_mois(brut) for brut in valeur]
    if isinstance(valeur, dict):
        if {str(k) for k in valeur} != {str(r) for r in range(1, 13)}:
            raise _refus_de_type(valeur, cle, libelle, section, declaration,
                                 'Les clés attendues sont les mois 1 à 12.')
        return {str(k): _mois(v) for k, v in valeur.items()}
    return _nombre_borne(valeur, cle, libelle, section, declaration)


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
