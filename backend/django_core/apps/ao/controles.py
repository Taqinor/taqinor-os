"""AOF146 — le REGISTRE des règles de cohérence croisée d'un dossier d'AO.

Un moteur de règles ENREGISTRABLES, exécuté en UNE passe. Chaque règle est une
fonction pure qui reçoit un contexte et rend zéro, une ou plusieurs anomalies.
Ajouter un invariant = décorer une fonction, jamais toucher au moteur.

**C'est une PORTE, pas un rapport.** ``pret_a_deposer`` est refusé tant qu'une
règle BLOQUANTE est rouge, et le refus cite le code de règle fautif.

Honnêteté du vert : une règle qui ne peut PAS s'exécuter (module pas encore
branché) n'est jamais silencieusement verte — elle rend un AVERTISSEMENT
``AO_REGLE_NON_DISPONIBLE``. Un dossier « tout vert » dont une partie n'a
jamais été vérifiée est plus dangereux qu'un dossier orange.
"""
from __future__ import annotations

from decimal import Decimal

__all__ = [
    'AVERTISSEMENT',
    'BLOQUANT',
    'INFO',
    'REGLES',
    'Regle',
    'executer_regles',
    'regle',
]

BLOQUANT = 'bloquant'
AVERTISSEMENT = 'avertissement'
INFO = 'info'


class Regle:
    """Une règle enregistrée : code, libellé, sévérité, fonction."""

    __slots__ = ('code', 'libelle', 'severite', 'fonction')

    def __init__(self, code, libelle, severite, fonction):
        self.code = code
        self.libelle = libelle
        self.severite = severite
        self.fonction = fonction

    def __repr__(self):  # pragma: no cover - confort de débogage
        return f'<Regle {self.code} [{self.severite}]>'


#: Registre ORDONNÉ des règles (code → Regle). L'ordre d'enregistrement est
#: l'ordre d'exécution : les invariants d'argent d'abord, ceux de forme après.
REGLES: dict[str, Regle] = {}


def regle(code, libelle, severite=BLOQUANT):
    """Décorateur d'enregistrement d'une règle de cohérence."""
    def _decorateur(fonction):
        REGLES[code] = Regle(code, libelle, severite, fonction)
        return fonction
    return _decorateur


def _anomalie(message, objet=''):
    return {'message': message, 'objet': objet}


# ── Invariants d'ARGENT ───────────────────────────────────────────────────

@regle('AO_MONTANT_UNIQUE',
       'Un seul montant : tous les bordereaux du dossier concordent')
def _montant_unique(ctx):
    """Défaut RÉEL reproduit : un bordereau FRÈRE périmé traîne dans le dépôt.

    Deux bordereaux du même appel d'offres avec des totaux TTC différents,
    c'est deux offres — et une seule sera lue par l'acheteur.
    """
    totaux = {}
    for bordereau in ctx['bordereaux']:
        totaux.setdefault(bordereau.total_ttc, []).append(bordereau)
    if len(totaux) <= 1:
        return []
    details = ' / '.join(
        f'indice {b.indice_revision} : {montant} MAD TTC'
        for montant, liste in sorted(totaux.items()) for b in liste)
    return [_anomalie(
        f'{len(ctx["bordereaux"])} bordereaux portent des montants '
        f'DIFFÉRENTS ({details}). Un seul part chez l\'acheteur : les autres '
        f'sont des fichiers frères périmés.',
        objet='bordereaux')]


@regle('AO_MONTANT_ENTETE',
       "Le montant de l'en-tête du dossier suit le bordereau")
def _montant_entete(ctx):
    """Défaut RÉEL reproduit : l'en-tête contredit son propre addendum."""
    bordereau = ctx['bordereau']
    if bordereau is None:
        return []
    ao = ctx['appel_offre']
    anomalies = []
    if ao.montant_offre_ttc and ao.montant_offre_ttc != bordereau.total_ttc:
        anomalies.append(_anomalie(
            f"L'en-tête du dossier annonce {ao.montant_offre_ttc} MAD TTC "
            f'alors que le bordereau totalise {bordereau.total_ttc} MAD TTC.',
            objet="en-tête de l'appel d'offres"))
    if ao.montant_offre_ht and ao.montant_offre_ht != bordereau.total_ht:
        anomalies.append(_anomalie(
            f"L'en-tête du dossier annonce {ao.montant_offre_ht} MAD HT "
            f'alors que le bordereau totalise {bordereau.total_ht} MAD HT.',
            objet="en-tête de l'appel d'offres"))
    return anomalies


@regle('AO_LETTRES_RECALCULEES',
       'Le montant en lettres est RECALCULÉ, jamais stocké ni recopié')
def _lettres_recalculees(ctx):
    """Aucun champ du domaine ne STOCKE un montant en lettres.

    Un montant en lettres stocké se désynchronise de son chiffre à la première
    cascade de prix — et c'est la ligne que l'acheteur lit en premier. La règle
    est donc structurelle : la valeur est recalculée par
    ``core.nombre_lettres`` à chaque rendu.
    """
    from django.apps import apps as django_apps

    fautifs = []
    for modele in django_apps.get_app_config('ao').get_models():
        for champ in modele._meta.get_fields():
            nom = getattr(champ, 'name', '')
            if 'lettre' in nom.lower():
                fautifs.append(f'{modele.__name__}.{nom}')
    if not fautifs:
        return []
    return [_anomalie(
        'Des champs STOCKENT un montant en lettres '
        f'({", ".join(sorted(fautifs))}) : il doit être RECALCULÉ à chaque '
        'rendu par core.nombre_lettres, jamais recopié.',
        objet='modèle de données')]


@regle('AO_TOTAL_LIGNES', 'La somme des lignes égale le sous-total du bordereau')
def _total_lignes(ctx):
    bordereau = ctx['bordereau']
    if bordereau is None:
        return []
    somme = sum((ligne.montant_ht for ligne in bordereau.lignes.all()),
                Decimal('0.00')).quantize(Decimal('0.01'))
    if somme == bordereau.sous_total_ht:
        return []
    return [_anomalie(
        f'La somme des lignes ({somme} MAD HT) diffère du sous-total du '
        f'bordereau ({bordereau.sous_total_ht} MAD HT).',
        objet='bordereau')]


@regle('AO_NUMEROTATION_BORDEREAU',
       'Numérotation contiguë, aucun prix unitaire nul, unité renseignée')
def _numerotation_bordereau(ctx):
    bordereau = ctx['bordereau']
    if bordereau is None:
        return []
    anomalies = []
    lignes = list(bordereau.lignes.order_by('numero'))
    attendu = 1
    for ligne in lignes:
        if ligne.numero != attendu:
            anomalies.append(_anomalie(
                f'Numérotation du bordereau interrompue : ligne '
                f'{ligne.numero} là où {attendu} était attendu.',
                objet=f'ligne {ligne.numero}'))
        attendu = ligne.numero + 1
        if not ligne.prix_unitaire:
            anomalies.append(_anomalie(
                f'Ligne {ligne.numero} « {ligne.designation} » : prix '
                f'unitaire NUL — un bordereau à prix unitaires ne se dépose '
                f'pas avec un prix vide.',
                objet=f'ligne {ligne.numero}'))
        if not (ligne.unite or '').strip():
            anomalies.append(_anomalie(
                f'Ligne {ligne.numero} « {ligne.designation} » : unité non '
                f'renseignée.',
                objet=f'ligne {ligne.numero}'))
    return anomalies


@regle('AO_CLAUSE_RESERVE',
       'Clause de réserve présente et IDENTIQUE sur tous les bordereaux')
def _clause_reserve(ctx):
    anomalies = []
    clauses = set()
    for bordereau in ctx['bordereaux']:
        anomalies.extend(
            _anomalie(raison, objet=f'bordereau {bordereau.indice_revision}')
            for raison in bordereau.raisons_de_non_conformite())
        if bordereau.marche_prix_unitaires:
            clauses.add((bordereau.clause_reserve or '').strip())
    if len(clauses) > 1:
        anomalies.append(_anomalie(
            'Les bordereaux portent des clauses de réserve DIFFÉRENTES : '
            "l'acheteur lira celle du pli, pas celle qu'on croit avoir mise.",
            objet='bordereaux'))
    return anomalies


# ── Invariants TECHNIQUES ────────────────────────────────────────────────

@regle('AO_QUANTITES_PLANCHES',
       'Quantités du bordereau == engagements portés par les planches')
def _quantites_planches(ctx):
    bordereau = ctx['bordereau']
    engagement = ctx['modules_engages']
    if bordereau is None or engagement is None:
        return []
    from .models import EquipementAO, LigneBordereau

    anomalies = []
    for ligne in bordereau.lignes.filter(
            quantite_source=LigneBordereau.QuantiteSource.CALEPINAGE):
        if int(ligne.quantite) != engagement:
            anomalies.append(_anomalie(
                f'Ligne {ligne.numero} « {ligne.designation} » : '
                f'{int(ligne.quantite)} unités annoncées issues du '
                f'calepinage, alors que les planches engagent '
                f'{engagement} modules.',
                objet=f'ligne {ligne.numero}'))
    for equipement in ctx['equipements']:
        if equipement.role != EquipementAO.Role.MODULE:
            continue
        if int(equipement.quantite) != engagement:
            anomalies.append(_anomalie(
                f'Équipement « {equipement.designation} » : '
                f'{int(equipement.quantite)} modules engagés côté matériel '
                f'contre {engagement} sur les planches.',
                objet='équipement module'))
    return anomalies


@regle('AO_KWC_COHERENT',
       'Puissance annoncée == quantité de modules × puissance unitaire')
def _kwc_coherent(ctx):
    from .models import EquipementAO

    engagement = ctx['modules_engages']
    if not engagement:
        return []
    for equipement in ctx['equipements']:
        if equipement.role != EquipementAO.Role.MODULE:
            continue
        puissance_w = (equipement.caracteristiques or {}).get('puissance_w')
        if puissance_w in (None, ''):
            continue
        attendu = (Decimal(str(puissance_w)) * Decimal(engagement)
                   / Decimal('1000')).quantize(Decimal('0.001'))
        declare = ctx['puissance_kwc'].quantize(Decimal('0.001'))
        if attendu != declare:
            return [_anomalie(
                f'Puissance annoncée {declare} kWc alors que '
                f'{engagement} modules de {puissance_w} W donnent '
                f'{attendu} kWc.',
                objet='puissance installée')]
    return []


@regle('AO_REFERENCE_PRODUIT_UNIQUE',
       'Une seule référence ACTIVE par rôle d\'équipement')
def _reference_produit_unique(ctx):
    """Deux équipements ACTIFS du même rôle = deux références citées.

    C'est la trace typique d'une bascule d'équipement inachevée : l'ancienne
    référence survit dans le mémoire, la note et l'annexe.
    """
    par_role = {}
    for equipement in ctx['equipements']:
        par_role.setdefault(equipement.role, []).append(equipement)
    anomalies = []
    for role, equipements in par_role.items():
        designations = {e.designation for e in equipements if e.designation}
        if len(designations) > 1:
            anomalies.append(_anomalie(
                f'Deux références ACTIVES pour le rôle « {role} » : '
                f'{", ".join(sorted(designations))}. Une bascule '
                f"d'équipement est restée inachevée.",
                objet=f'équipement {role}'))
    return anomalies


@regle('AO_PLANCHES_CITEES',
       'Planches citées existantes et à leur indice COURANT')
def _planches_citees(ctx):
    from . import services

    return [_anomalie(item['message'], objet=item['code_document'])
            for item in services.citations_perimees(ctx['appel_offre'])]


@regle('AO_FICHES_ANNEXES',
       'Chaque équipement actif porte sa fiche technique',
       severite=AVERTISSEMENT)
def _fiches_annexes(ctx):
    return [
        _anomalie(
            f'Équipement « {equipement.designation} » sans fiche technique '
            f'annexée.',
            objet=f'équipement {equipement.role}')
        for equipement in ctx['equipements']
        if equipement.fiche_technique_id is None
    ]


@regle('AO_ARTEFACT_PERIME',
       'Aucun artefact périmé dans le pack (empreinte divergente)')
def _artefact_perime(ctx):
    """Défaut RÉEL reproduit : le « LISEZ-MOI » figé resté dans le dépôt.

    Une pièce produite sous une empreinte de contexte ANTÉRIEURE décrit un
    autre état du dossier. Elle est périmée, quelle que soit sa fraîcheur
    apparente.
    """
    courante = ctx['empreinte']
    anomalies = []
    for piece in ctx['pieces']:
        if not piece.empreinte_source:
            continue
        if piece.empreinte_source != courante:
            anomalies.append(_anomalie(
                f'Pièce {piece.code} « {piece.libelle} » : produite sous '
                f'l\'empreinte {piece.empreinte_source[:8]} alors que le '
                f'dossier est à {courante[:8]} — artefact PÉRIMÉ.',
                objet=f'pièce {piece.code}'))
    return anomalies


# ── Invariants ADMINISTRATIFS et de RELEVÉ ───────────────────────────────

@regle('AO_PIECES_OBLIGATOIRES',
       'Pièces obligatoires présentes et non expirées à la remise des plis')
def _pieces_obligatoires(ctx):
    from . import services

    dossier = ctx['dossier']
    anomalies = [
        _anomalie(
            f'Pièce obligatoire absente : {piece.code} « {piece.libelle} ».',
            objet=f'pièce {piece.code}')
        for piece in dossier.pieces_obligatoires_manquantes()
    ]
    for controle in services.controler_pieces_administratives(dossier):
        if controle['severite'] == services.SEVERITE_BLOQUANT:
            anomalies.append(_anomalie(
                controle['message'], objet='pièce administrative'))
    return anomalies


@regle('AO_OBSTACLES_NON_MESURES',
       'Aucun obstacle « lu sur plan » ou « deviné » encore actif')
def _obstacles_non_mesures(ctx):
    from .models import ObstacleAO

    anomalies = []
    for toiture in ctx['toitures']:
        non_mesures = toiture.obstacles.filter(actif=True).exclude(
            provenance__in=list(ObstacleAO.PROVENANCES_ENGAGEABLES))
        for obstacle in non_mesures:
            anomalies.append(_anomalie(
                f'Toiture {toiture.code_document or toiture.pk} : obstacle '
                f'« {obstacle.repere or obstacle.pk} » de provenance '
                f'{obstacle.provenance} encore ACTIF — le plan ne peut pas '
                f'être engageant.',
                objet=f'obstacle {obstacle.repere or obstacle.pk}'))
    return anomalies


@regle('AO_COTES_A_CONFIRMER',
       'Les cotes « à confirmer » sont reportées dans la section dédiée',
       severite=AVERTISSEMENT)
def _cotes_a_confirmer(ctx):
    from .models import StatutCote

    anomalies = []
    for toiture in ctx['toitures']:
        for chaine in toiture.chaines_cotes.all():
            for segment in (chaine.segments or []):
                if segment.get('statut') == StatutCote.A_CONFIRMER:
                    anomalies.append(_anomalie(
                        f'Chaîne « {chaine.libelle} » : le segment '
                        f'« {segment.get("libelle", "")} » est À CONFIRMER À '
                        f"L'EXÉCUTION et doit figurer dans la section dédiée.",
                        objet=f'chaîne {chaine.libelle}'))
    return anomalies


@regle('AO_PIECES_HORS_CONTROLE',
       'Les pièces FOURNIES sont signalées hors contrôle, avec leur motif',
       severite=INFO)
def _pieces_hors_controle(ctx):
    """AOF149 — ce qui n'est pas fabriqué n'est JAMAIS présumé vert.

    Ces pièces ne sont pas des anomalies : elles sont HORS du périmètre des
    invariants. Les taire donnerait un dossier « tout vert » dont un tiers
    n'a jamais été vérifié — plus dangereux qu'un dossier orange.
    """
    hors = [p for p in ctx['pieces'] if p.etat_controle == 'hors_controle']
    if not hors:
        return []
    return [_anomalie(
        f'{len(hors)} pièce(s) HORS CONTRÔLE (non produites par la fabrique, '
        f'donc non vérifiées par les invariants) : '
        + ' ; '.join(
            f'{p.code} « {p.libelle} » — {p.motif or "motif manquant"}'
            for p in hors) + '.',
        objet='pièces hors contrôle')]


@regle('AO_HORS_CONTROLE_SANS_MOTIF',
       'Une pièce hors contrôle DOIT dire pourquoi elle y échappe')
def _hors_controle_sans_motif(ctx):
    anomalies = []
    for piece in ctx['pieces']:
        for raison in piece.raisons_hors_controle():
            anomalies.append(_anomalie(raison, objet=f'pièce {piece.code}'))
    return anomalies


@regle('AO_SANITISATION',
       'Aucun mot bloquant de sanitisation dans les rendus client')
def _sanitisation(ctx):
    """Branché sur ``fabrique.sanitisation`` (AOF143) dès qu'il existe.

    Tant que le module n'est pas là, la règle rend un AVERTISSEMENT explicite
    — jamais un vert silencieux (cf. l'honnêteté du vert, en tête de module).
    """
    try:
        from .fabrique import sanitisation  # noqa: F401
    except ImportError:
        return [_anomalie(
            'Règle de sanitisation NON EXÉCUTÉE : le module '
            'apps.ao.fabrique.sanitisation (AOF143) n\'est pas encore '
            'branché. Ce point du dossier n\'a donc PAS été vérifié.',
            objet='sanitisation')]
    anomalies = []
    for texte, objet in ctx.get('textes_client', ()):
        for mot in sanitisation.mots_bloquants(texte):
            anomalies.append(_anomalie(
                f'Mot bloquant « {mot} » trouvé dans {objet}.', objet=objet))
    return anomalies


def executer_regles(contexte, *, codes=None):
    """Exécute le registre en UNE passe. Renvoie la liste des anomalies.

    Chaque anomalie porte ``code_regle``, ``severite``, ``message``, ``objet``.
    Une règle qui LÈVE est convertie en anomalie ``AO_REGLE_EN_ERREUR`` plutôt
    qu'en passe interrompue : une exception ne doit jamais rendre un dossier
    faussement vert.
    """
    resultats = []
    for code, item in REGLES.items():
        if codes is not None and code not in codes:
            continue
        try:
            anomalies = item.fonction(contexte) or []
        except Exception as exc:  # noqa: BLE001 — jamais un vert par accident
            resultats.append({
                'code_regle': 'AO_REGLE_EN_ERREUR',
                'severite': AVERTISSEMENT,
                'message': (
                    f'La règle « {code} » n\'a pas pu s\'exécuter '
                    f'({exc.__class__.__name__}) : ce point du dossier n\'a '
                    f'PAS été vérifié.'),
                'objet': code,
            })
            continue
        for anomalie in anomalies:
            resultats.append({
                'code_regle': code,
                'severite': item.severite,
                'message': anomalie['message'],
                'objet': anomalie.get('objet', ''),
            })
    return resultats
