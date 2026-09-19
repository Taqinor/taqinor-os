"""FG369 — Bibliothèque de modèles de workflow pré-construits (installables).

Catalogue de DONNÉES PURES (aucun import d'app métier — ``core`` reste une
couche de fondation, contrat import-linter ``core-foundation-is-a-base-layer``)
décrivant des chaînes d'approbation prêtes à l'emploi : relance devis,
onboarding chantier, rappel garantie. Chaque modèle est un template global
(non rattaché à une société) que l'on installe en un clic pour une société
donnée — l'installation matérialise un ``WorkflowDefinition`` + ses
``WorkflowStepDefinition`` (modèles FG366 réutilisés tels quels).

Conception
----------

* **Données, pas modèles.** Le catalogue est une simple structure Python ;
  rien ici ne touche la base. L'installation (``installer_modele_workflow``)
  vit dans le même module mais ne fait que créer des lignes FG366.
* **Limites de longueur respectées.** ``code`` ≤ 64, ``nom`` (def) ≤ 120,
  ``nom`` (step) ≤ 120, ``role_requis`` ≤ 80, ``escalade_vers`` ≤ 120,
  ``type_approbation`` ∈ choix FG366 — garanti par un test de forme.
* **Idempotent.** Réinstaller un modèle déjà présent (même société + même
  ``code``) ne crée aucun doublon : on renvoie la définition existante.
* **Multi-tenant.** ``installer_modele_workflow`` impose ``company`` côté
  serveur — jamais une valeur du corps de requête ; les templates eux-mêmes
  sont globaux (sans société).
"""
import copy as _copy

from django.db import transaction

from core.models import (
    WorkflowDefinition,
    WorkflowStepDefinition,
)

__all__ = [
    'WORKFLOW_TEMPLATES',
    'liste_modeles_workflow',
    'get_modele_workflow',
    'installer_modele_workflow',
    'dupliquer_definition_workflow',
    'ModeleWorkflowInconnu',
]


# Types d'approbation valides — copiés des constantes FG369 → FG366 (pas
# d'import du modèle pour rester en données pures côté catalogue ; un test
# garantit l'alignement avec WorkflowStepDefinition.APPROBATION_CHOICES).
_AUTO = 'auto'
_MANUELLE = 'manuelle'
_ROLE = 'role'


# ---------------------------------------------------------------------------
# Le catalogue : chaque entrée = un template global.
#
#   code            : identifiant stable (≤ 64) — sert de clé d'install + clé
#                     d'unicité (company, code) côté FG366.
#   nom             : libellé lisible (≤ 120).
#   description     : explication courte (TextField, libre).
#   steps           : liste ordonnée d'étapes ; chaque étape porte
#                     ordre / nom / type_approbation / sla_heures /
#                     role_requis / escalade_vers (mêmes champs que
#                     WorkflowStepDefinition).
#   steps[].formulaire (NTWFL31, optionnel)
#                   : formulaire dynamique NTWFL12 livré AVEC le modèle —
#                     {code, nom, schema[, champs_conditionnels]}. À
#                     l'installation, un FormulaireDefinition est matérialisé
#                     (réutilisé s'il existe déjà pour la société : jamais
#                     écrasé, les retouches de l'admin survivent) et rattaché
#                     à l'étape.
# ---------------------------------------------------------------------------
WORKFLOW_TEMPLATES = [
    {
        'code': 'relance_devis',
        'nom': 'Relance devis (suivi commercial)',
        'description': (
            "Relances échelonnées d'un devis envoyé resté sans réponse : "
            "premier rappel, relance commerciale, puis escalade responsable "
            "avant abandon."
        ),
        'steps': [
            {
                'ordre': 1,
                'nom': 'Premier rappel client (J+2)',
                'type_approbation': _MANUELLE,
                'sla_heures': 48,
                'role_requis': 'Commercial',
                'escalade_vers': 'Responsable commercial',
            },
            {
                'ordre': 2,
                'nom': 'Relance téléphonique (J+5)',
                'type_approbation': _MANUELLE,
                'sla_heures': 72,
                'role_requis': 'Commercial',
                'escalade_vers': 'Responsable commercial',
            },
            {
                'ordre': 3,
                'nom': 'Escalade responsable (J+10)',
                'type_approbation': _ROLE,
                'sla_heures': 120,
                'role_requis': 'Responsable',
                'escalade_vers': 'Administrateur',
            },
        ],
    },
    {
        'code': 'onboarding_chantier',
        'nom': 'Onboarding chantier (lancement installation)',
        'description': (
            "Étapes de démarrage d'un chantier après signature : préparation "
            "du dossier technique, planification, validation matériel et "
            "lancement des travaux."
        ),
        'steps': [
            {
                'ordre': 1,
                'nom': 'Préparation du dossier technique',
                'type_approbation': _MANUELLE,
                'sla_heures': 48,
                'role_requis': 'Bureau d’études',
                'escalade_vers': 'Responsable technique',
            },
            {
                'ordre': 2,
                'nom': 'Planification de l’intervention',
                'type_approbation': _MANUELLE,
                'sla_heures': 72,
                'role_requis': 'Responsable technique',
                'escalade_vers': 'Administrateur',
            },
            {
                'ordre': 3,
                'nom': 'Validation du matériel et du stock',
                'type_approbation': _ROLE,
                'sla_heures': 48,
                'role_requis': 'Magasinier',
                'escalade_vers': 'Responsable technique',
            },
            {
                'ordre': 4,
                'nom': 'Lancement des travaux',
                'type_approbation': _MANUELLE,
                'sla_heures': None,
                'role_requis': 'Chef de chantier',
                'escalade_vers': '',
            },
        ],
    },
    {
        'code': 'rappel_garantie',
        'nom': 'Rappel garantie (suivi après-vente)',
        'description': (
            "Suivi périodique de fin de garantie : contrôle automatique de "
            "l'échéance, prise de contact client et proposition de contrat "
            "de maintenance."
        ),
        'steps': [
            {
                'ordre': 1,
                'nom': 'Détection d’échéance de garantie',
                'type_approbation': _AUTO,
                'sla_heures': None,
                'role_requis': '',
                'escalade_vers': '',
            },
            {
                'ordre': 2,
                'nom': 'Prise de contact client',
                'type_approbation': _MANUELLE,
                'sla_heures': 168,
                'role_requis': 'Service après-vente',
                'escalade_vers': 'Responsable SAV',
            },
            {
                'ordre': 3,
                'nom': 'Proposition de contrat de maintenance',
                'type_approbation': _MANUELLE,
                'sla_heures': 336,
                'role_requis': 'Commercial',
                'escalade_vers': 'Responsable SAV',
            },
        ],
    },
    {
        # ARC10 — pilote domaine du moteur core.WorkflowDefinition : la clôture
        # d'une non-conformité (qhse) passe par ce cycle d'approbation générique.
        # Aucune référence métier ici (données pures) — c'est ``apps.qhse`` qui
        # attache une WorkflowInstance de ce modèle à sa NCR via contenttypes.
        'code': 'cloture_ncr',
        'nom': 'Clôture de non-conformité (validation QHSE)',
        'description': (
            "Validation en deux temps de la clôture d'une non-conformité : "
            "vérification par l'agent QHSE puis approbation finale du "
            "responsable QHSE avant fermeture définitive."
        ),
        'steps': [
            {
                'ordre': 1,
                'nom': 'Vérification agent QHSE',
                'type_approbation': _MANUELLE,
                'sla_heures': 48,
                'role_requis': 'Agent QHSE',
                'escalade_vers': 'Responsable QHSE',
            },
            {
                'ordre': 2,
                'nom': 'Approbation responsable QHSE',
                'type_approbation': _ROLE,
                'sla_heures': 72,
                'role_requis': 'Responsable QHSE',
                'escalade_vers': 'Administrateur',
            },
        ],
    },
    # ── NTWFL31 — modèles VERTICAUX propres au métier solaire ───────────────
    # Pure donnée de seed : les trois processus que l'exploitation réclame le
    # plus souvent, avec le formulaire de qualification qui va avec. Aucun
    # nouveau moteur — ce sont les mêmes modèles FG366 + NTWFL12.
    {
        'code': 'validation_devis_forte_remise',
        'nom': 'Validation devis forte remise',
        'description': (
            "Chaîne de validation d'un devis portant une remise "
            "exceptionnelle : justification chiffrée par le commercial, "
            "contrôle de la marge restante, puis arbitrage de la direction."
        ),
        'steps': [
            {
                'ordre': 1,
                'nom': 'Justification de la remise',
                'type_approbation': _MANUELLE,
                'sla_heures': 24,
                'role_requis': 'Commercial',
                'escalade_vers': 'Responsable commercial',
                'formulaire': {
                    'code': 'qualification_forte_remise',
                    'nom': 'Justification de forte remise',
                    'schema': [
                        {'nom': 'taux_remise_demande', 'type': 'nombre',
                         'requis': True},
                        {'nom': 'motif', 'type': 'choix', 'requis': True,
                         'options': ['Concurrence', 'Volume',
                                     'Client fidèle', 'Geste commercial']},
                        {'nom': 'concurrent_cite', 'type': 'texte',
                         'requis': False},
                        {'nom': 'marge_restante_pct', 'type': 'nombre',
                         'requis': True},
                    ],
                    'champs_conditionnels': {},
                },
            },
            {
                'ordre': 2,
                'nom': 'Contrôle de la marge',
                'type_approbation': _ROLE,
                'sla_heures': 24,
                'role_requis': 'Responsable commercial',
                'escalade_vers': 'Directeur',
            },
            {
                'ordre': 3,
                'nom': 'Arbitrage direction',
                'type_approbation': _ROLE,
                'sla_heures': 48,
                'role_requis': 'Directeur',
                'escalade_vers': 'Administrateur',
            },
        ],
    },
    {
        'code': 'onboarding_chantier_grand_compte',
        'nom': 'Onboarding chantier grand compte',
        'description': (
            "Démarrage d'un chantier grand compte : cadrage contractuel et "
            "administratif, revue technique du bureau d'études, validation "
            "des accès et de la logistique du site, puis feu vert travaux."
        ),
        'steps': [
            {
                'ordre': 1,
                'nom': 'Cadrage contractuel et administratif',
                'type_approbation': _MANUELLE,
                'sla_heures': 72,
                'role_requis': 'Responsable commercial',
                'escalade_vers': 'Directeur',
                'formulaire': {
                    'code': 'qualification_grand_compte',
                    'nom': 'Cadrage grand compte',
                    'schema': [
                        {'nom': 'interlocuteur_principal', 'type': 'texte',
                         'requis': True},
                        {'nom': 'date_demarrage_souhaitee', 'type': 'date',
                         'requis': True},
                        {'nom': 'assurance_chantier_recue', 'type': 'booleen',
                         'requis': True},
                        {'nom': 'penalites_de_retard', 'type': 'booleen',
                         'requis': True},
                        {'nom': 'detail_penalites', 'type': 'texte',
                         'requis': False},
                    ],
                    'champs_conditionnels': {
                        # Format core.rules (FG367) : un GROUPE porte « op » +
                        # « conditions », une FEUILLE porte « field » /
                        # « operator » / « value » — aucun second moteur de
                        # conditions.
                        'detail_penalites': {
                            'visible_si': {
                                'op': 'and',
                                'conditions': [
                                    {'field': 'penalites_de_retard',
                                     'operator': 'eq', 'value': True},
                                ],
                            },
                        },
                    },
                },
            },
            {
                'ordre': 2,
                'nom': 'Revue technique bureau d’études',
                'type_approbation': _MANUELLE,
                'sla_heures': 96,
                'role_requis': 'Bureau d’études',
                'escalade_vers': 'Responsable technique',
            },
            {
                'ordre': 3,
                'nom': 'Validation accès et logistique du site',
                'type_approbation': _ROLE,
                'sla_heures': 48,
                'role_requis': 'Chef de chantier',
                'escalade_vers': 'Responsable technique',
            },
            {
                'ordre': 4,
                'nom': 'Feu vert travaux',
                'type_approbation': _ROLE,
                'sla_heures': None,
                'role_requis': 'Directeur',
                'escalade_vers': '',
            },
        ],
    },
    {
        'code': 'reclamation_sav_complexe',
        'nom': 'Réclamation SAV complexe',
        'description': (
            "Traitement d'une réclamation après-vente qui dépasse le "
            "dépannage courant : qualification chiffrée du défaut, "
            "diagnostic technique sur site, puis arbitrage de la prise en "
            "charge (garantie, geste commercial ou refus motivé)."
        ),
        'steps': [
            {
                'ordre': 1,
                'nom': 'Qualification de la réclamation',
                'type_approbation': _MANUELLE,
                'sla_heures': 24,
                'role_requis': 'Service après-vente',
                'escalade_vers': 'Responsable SAV',
                'formulaire': {
                    'code': 'qualification_reclamation_sav',
                    'nom': 'Qualification de réclamation SAV',
                    'schema': [
                        {'nom': 'nature_du_defaut', 'type': 'choix',
                         'requis': True,
                         'options': ['Production en baisse',
                                     'Panne onduleur', 'Panne batterie',
                                     'Défaut de pose', 'Dégât des eaux',
                                     'Autre']},
                        {'nom': 'date_constat', 'type': 'date',
                         'requis': True},
                        {'nom': 'installation_sous_garantie',
                         'type': 'booleen', 'requis': True},
                        {'nom': 'impact_production_pct', 'type': 'nombre',
                         'requis': False},
                        {'nom': 'description_client', 'type': 'texte',
                         'requis': True},
                    ],
                    'champs_conditionnels': {},
                },
            },
            {
                'ordre': 2,
                'nom': 'Diagnostic technique sur site',
                'type_approbation': _MANUELLE,
                'sla_heures': 72,
                'role_requis': 'Technicien',
                'escalade_vers': 'Responsable technique',
            },
            {
                'ordre': 3,
                'nom': 'Arbitrage de la prise en charge',
                'type_approbation': _ROLE,
                'sla_heures': 48,
                'role_requis': 'Responsable SAV',
                'escalade_vers': 'Directeur',
            },
        ],
    },
]


class ModeleWorkflowInconnu(ValueError):
    """Levée quand un ``code`` ne correspond à aucun modèle du catalogue."""


def liste_modeles_workflow():
    """Retourne le catalogue (liste de dicts), sans toucher la base.

    Chaque entrée expose ``code``, ``nom``, ``description``, le nombre
    d'étapes (``nb_etapes``) et ses ``steps`` (copie défensive pour éviter
    toute mutation du catalogue global).
    """
    out = []
    for tpl in WORKFLOW_TEMPLATES:
        out.append({
            'code': tpl['code'],
            'nom': tpl['nom'],
            'description': tpl['description'],
            'nb_etapes': len(tpl['steps']),
            # Copie PROFONDE (NTWFL31) : une étape peut porter un sous-dict
            # ``formulaire`` — une copie superficielle laisserait l'appelant
            # muter le catalogue global à travers lui.
            'steps': [_copy.deepcopy(s) for s in tpl['steps']],
        })
    return out


def get_modele_workflow(code):
    """Retourne le template brut du catalogue pour ``code``.

    Lève ``ModeleWorkflowInconnu`` si le code est inconnu.
    """
    for tpl in WORKFLOW_TEMPLATES:
        if tpl['code'] == code:
            return tpl
    raise ModeleWorkflowInconnu(
        f"Modèle de workflow inconnu : « {code} »."
    )


@transaction.atomic
def installer_modele_workflow(company, code):
    """Installe (idempotemment) le modèle ``code`` pour ``company``.

    Crée un ``WorkflowDefinition`` (FG366) + ses ``WorkflowStepDefinition`` à
    partir du template du catalogue. ``company`` est IMPOSÉ côté serveur (jamais
    issu d'un corps de requête). Si une définition de même ``code`` existe déjà
    pour cette société, rien n'est créé : la définition existante est renvoyée
    (idempotence, pas de doublon).

    Retourne ``(definition, created)`` où ``created`` indique si l'installation
    a effectivement matérialisé une nouvelle définition.

    Lève ``ModeleWorkflowInconnu`` si ``code`` n'est pas au catalogue.
    """
    tpl = get_modele_workflow(code)

    existing = WorkflowDefinition.objects.filter(
        company=company, code=code).first()
    if existing is not None:
        return existing, False

    definition = WorkflowDefinition.objects.create(
        company=company,
        code=tpl['code'],
        nom=tpl['nom'],
        description=tpl['description'],
        actif=True,
    )
    for step in tpl['steps']:
        WorkflowStepDefinition.objects.create(
            definition=definition,
            ordre=step['ordre'],
            nom=step['nom'],
            type_approbation=step['type_approbation'],
            sla_heures=step['sla_heures'],
            role_requis=step.get('role_requis', ''),
            escalade_vers=step.get('escalade_vers', ''),
            formulaire=_materialiser_formulaire(company, step.get('formulaire')),
        )
    return definition, True


def _materialiser_formulaire(company, spec):
    """NTWFL31 — ``FormulaireDefinition`` d'une étape de modèle (ou ``None``).

    ``spec`` est le sous-dict ``formulaire`` du catalogue
    (``{code, nom, schema[, champs_conditionnels]}``) ou ``None`` (l'étape
    n'en porte pas — cas de tous les modèles antérieurs, comportement
    strictement inchangé).

    Un formulaire de même ``code`` DÉJÀ présent pour la société est RÉUTILISÉ
    tel quel : réinstaller un modèle n'écrase jamais les retouches qu'un admin
    a faites à son formulaire (et ne crée aucun doublon — ``(company, code)``
    est unique)."""
    if not spec:
        return None
    from core.models import FormulaireDefinition

    existant = FormulaireDefinition.objects.filter(
        company=company, code=spec['code']).first()
    if existant is not None:
        return existant
    return FormulaireDefinition.objects.create(
        company=company,
        code=spec['code'],
        nom=spec['nom'],
        schema=_copy.deepcopy(spec.get('schema') or []),
        champs_conditionnels=_copy.deepcopy(
            spec.get('champs_conditionnels') or {}),
        actif=True,
    )


# ---------------------------------------------------------------------------
# NTWFL27 — duplication ad-hoc d'un processus DÉJÀ personnalisé.
#
# Le catalogue ci-dessus sert de point de départ NEUF. Il ne répond pas au
# besoin inverse : « je repars de MON processus existant, déjà adapté à ma
# société, pour en faire une variante ». D'où cette duplication profonde —
# étapes ET formulaires rattachés —, qui produit une copie strictement
# INDÉPENDANTE : éditer la copie (ou son formulaire) ne touche jamais
# l'original. La copie naît en BROUILLON (``actif=False``) pour qu'elle ne
# puisse pas être démarrée par erreur avant d'avoir été relue.
# ---------------------------------------------------------------------------

_SUFFIXE_COPIE = 'copie'
_MAX_TENTATIVES_CODE = 500


def _code_copie_libre(model, company, code_source, longueur_max=64):
    """Premier code libre ``<source>-copie`` / ``<source>-copie-N``.

    Le marqueur est TOUJOURS conservé entier : c'est la base qui est tronquée
    pour tenir dans ``longueur_max`` (un code tronqué qui perdrait son
    « -copie » redeviendrait indistinguable de l'original)."""
    n = 1
    while n <= _MAX_TENTATIVES_CODE:
        marqueur = (f'-{_SUFFIXE_COPIE}' if n == 1
                    else f'-{_SUFFIXE_COPIE}-{n}')
        candidat = code_source[:longueur_max - len(marqueur)] + marqueur
        if not model.objects.filter(company=company, code=candidat).exists():
            return candidat
        n += 1
    raise ValueError(
        "Impossible de dériver un code de copie libre pour "
        f"« {code_source} »."
    )


def _nom_copie(nom_source, longueur_max):
    """``<nom> (copie)``, tronqué sur le NOM pour garder la mention visible."""
    mention = ' (copie)'
    return nom_source[:longueur_max - len(mention)] + mention


@transaction.atomic
def dupliquer_definition_workflow(definition):
    """NTWFL27 — copie profonde et INDÉPENDANTE de ``definition``.

    Copie la définition, TOUTES ses étapes (avec leurs gardes de transition,
    groupes parallèles, SLA et calendrier ouvré) et, pour chaque formulaire
    dynamique rattaché, un formulaire COPIÉ propre à la nouvelle définition.
    Un même formulaire réutilisé par plusieurs étapes n'est copié QU'UNE fois
    (les étapes de la copie le partagent, comme dans l'original).

    La copie appartient à la même société, porte un ``code`` auto-suffixé libre
    et naît ``actif=False`` (brouillon). Retourne la nouvelle définition."""
    from core.models import FormulaireDefinition

    company = definition.company
    copie = WorkflowDefinition.objects.create(
        company=company,
        code=_code_copie_libre(WorkflowDefinition, company, definition.code),
        nom=_nom_copie(definition.nom, 120),
        description=definition.description,
        actif=False,
    )

    formulaires_copies = {}
    for step in definition.steps.order_by('ordre', 'id'):
        source = step.formulaire
        if source is not None and source.pk not in formulaires_copies:
            formulaires_copies[source.pk] = FormulaireDefinition.objects.create(
                company=source.company,
                code=_code_copie_libre(
                    FormulaireDefinition, source.company, source.code),
                nom=_nom_copie(source.nom, 160),
                schema=_copy.deepcopy(source.schema),
                champs_conditionnels=_copy.deepcopy(
                    source.champs_conditionnels),
                actif=source.actif,
            )
        WorkflowStepDefinition.objects.create(
            definition=copie,
            ordre=step.ordre,
            nom=step.nom,
            type_approbation=step.type_approbation,
            sla_heures=step.sla_heures,
            role_requis=step.role_requis,
            escalade_vers=step.escalade_vers,
            calendrier_ouvre=step.calendrier_ouvre,
            condition_transition=_copy.deepcopy(step.condition_transition),
            etape_alternative_si_echec=step.etape_alternative_si_echec,
            groupe_parallele=step.groupe_parallele,
            formulaire=(None if source is None
                        else formulaires_copies[source.pk]),
        )
    return copie
