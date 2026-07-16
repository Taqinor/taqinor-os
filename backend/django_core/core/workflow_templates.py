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
            'steps': [dict(s) for s in tpl['steps']],
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
        )
    return definition, True
