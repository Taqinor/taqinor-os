"""NTMIG23 — catalogue des playbooks d'implémentation prêts-à-l'emploi.

Contenu SEUL (aucune écriture, aucun import Django) : la commande
``seed_playbooks`` le dépose société par société dans ``kb`` via
``kb.services`` — jamais un import de ``kb.models`` depuis ici.

Chaque playbook suit la MÊME ossature en six phases, parce qu'un déploiement
raté l'est presque toujours pour la même raison : une phase sautée. Les six
sont donc identiques d'un module à l'autre —

1. ``prerequis``   — ce qui doit exister AVANT de commencer ;
2. ``reglages``    — les réglages ``parametres`` à poser ;
3. ``roles``       — les rôles et accès à créer ;
4. ``donnees``     — les données de référence à charger (kits de migration) ;
5. ``recette``     — les tests d'acceptation à faire valider par le client ;
6. ``golive``      — la bascule et son suivi.

Les libellés restent GÉNÉRIQUES et sans chiffre inventé : ce sont des
checklists que l'intégrateur adapte, pas une documentation produit.
"""

# Clé de graine stockée dans les ``tags`` de l'article : c'est l'identité
# STABLE du playbook. Un fondateur qui renomme « Déploiement Ventes » en
# « Go-live Ventes » ne doit pas provoquer la re-création d'un doublon au
# prochain passage du seeder — le titre n'est donc jamais la clé.
PREFIXE_GRAINE = 'seed:playbook:'
CATEGORIE = "Playbooks d'implémentation"

# Ossature commune : (clé de phase, titre de phase).
PHASES = (
    ('prerequis', 'Prérequis'),
    ('reglages', 'Réglages à poser'),
    ('roles', 'Rôles & accès'),
    ('donnees', 'Données de référence'),
    ('recette', "Tests d'acceptation"),
    ('golive', 'Go-live & suivi'),
)

# Par playbook : clé, titre, résumé, puis les étapes de chacune des 6 phases.
PLAYBOOKS = (
    {
        'cle': 'crm_ventes',
        'titre': 'Déploiement module CRM & Ventes',
        'resume': "Mise en service du pipeline commercial et du devis client.",
        'etapes': {
            'prerequis': [
                'Société créée et coordonnées légales renseignées',
                "Périmètre validé avec le client (qui vend quoi, à qui)",
                'Export source disponible (leads, clients, devis)',
            ],
            'reglages': [
                'Taux de TVA par défaut',
                'Conditions de paiement et mentions du devis',
                'Numérotation des devis et factures',
                'Modèle de PDF de devis vérifié sur un cas réel',
            ],
            'roles': [
                'Créer les commerciaux et leur responsable',
                'Vérifier ce que chaque palier voit du pipeline',
                "Vérifier qu'aucun profil non autorisé ne voit les marges",
            ],
            'donnees': [
                'Charger le catalogue produits (kit de migration)',
                'Charger les clients (kit de migration)',
                'Charger les leads et leur étape de pipeline',
                'Réconcilier les comptages avant de déclarer le lot chargé',
            ],
            'recette': [
                'Créer un lead, le qualifier, générer son devis',
                "Faire relire le PDF de devis par le client",
                'Vérifier le passage devis → commande → facture',
            ],
            'golive': [
                'Figer la date de bascule avec le client',
                "Geler les saisies dans l'ancien outil",
                'Passer le projet de migration en terminé (réconcilié)',
                'Point de suivi à J+7',
            ],
        },
    },
    {
        'cle': 'stock_achats',
        'titre': 'Déploiement module Stock & Achats',
        'resume': 'Mise en service du catalogue, des dépôts et des achats.',
        'etapes': {
            'prerequis': [
                'Liste des dépôts et emplacements arrêtée',
                'Liste des fournisseurs et de leurs conditions',
                'Inventaire de départ figé à une date connue',
            ],
            'reglages': [
                'Unités de mesure et arrondis',
                'Règles de réapprovisionnement et seuils',
                'Politique de valorisation du stock',
            ],
            'roles': [
                'Créer les magasiniers et les acheteurs',
                "Vérifier qui a le droit de valider une commande d'achat",
            ],
            'donnees': [
                'Charger les fournisseurs (kit de migration)',
                'Charger les articles et leurs prix',
                "Charger l'inventaire de départ",
                'Réconcilier les quantités avant de déclarer le lot chargé',
            ],
            'recette': [
                "Passer une commande d'achat de bout en bout",
                'Réceptionner partiellement puis totalement',
                'Vérifier un mouvement de stock et sa traçabilité',
            ],
            'golive': [
                "Arrêter les entrées/sorties dans l'ancien outil",
                "Recompter un échantillon d'articles après bascule",
                'Point de suivi à J+7',
            ],
        },
    },
    {
        'cle': 'chantiers',
        'titre': 'Déploiement module Chantiers & Installations',
        'resume': "Mise en service du suivi de chantier et des interventions.",
        'etapes': {
            'prerequis': [
                'Typologie des chantiers arrêtée avec le client',
                'Équipes terrain identifiées',
                'Chantiers en cours à reprendre listés',
            ],
            'reglages': [
                'Étapes de chantier et jalons',
                'Modèles de rapports terrain et de PV de réception',
                'Règles de planification des équipes',
            ],
            'roles': [
                'Créer les chefs de chantier et les techniciens',
                "Vérifier l'accès mobile des équipes terrain",
            ],
            'donnees': [
                'Charger les chantiers en cours et leur avancement',
                'Charger les équipements posés',
                'Réconcilier avant de déclarer le lot chargé',
            ],
            'recette': [
                'Créer un chantier, le planifier, le clôturer',
                'Produire un rapport terrain depuis un téléphone',
                'Faire signer un PV de réception',
            ],
            'golive': [
                'Basculer les chantiers en cours en une seule fois',
                'Former les équipes terrain à la saisie mobile',
                'Point de suivi à J+7',
            ],
        },
    },
    {
        'cle': 'sav',
        'titre': 'Déploiement module SAV & Maintenance',
        'resume': "Mise en service des tickets, contrats et interventions SAV.",
        'etapes': {
            'prerequis': [
                'Catalogue des types de panne arrêté',
                'Engagements de délai (SLA) validés par le client',
                'Contrats de maintenance en cours listés',
            ],
            'reglages': [
                'Canaux de réception des demandes',
                'Délais de prise en charge et de résolution',
                'Modèles de réponse et de rapport d’intervention',
            ],
            'roles': [
                'Créer les techniciens SAV et le superviseur',
                'Vérifier ce que le client voit sur le portail',
            ],
            'donnees': [
                'Charger le parc installé et ses garanties',
                'Charger les contrats de maintenance en cours',
                'Réconcilier avant de déclarer le lot chargé',
            ],
            'recette': [
                'Ouvrir un ticket depuis le portail client',
                "Planifier et clôturer une intervention",
                'Vérifier le décompte des droits du contrat',
            ],
            'golive': [
                'Rediriger le canal de réception des demandes',
                "Traiter les tickets ouverts de l'ancien outil",
                'Point de suivi à J+7',
            ],
        },
    },
    {
        'cle': 'compta',
        'titre': 'Déploiement module Comptabilité',
        'resume': 'Mise en service du plan comptable et des écritures.',
        'etapes': {
            'prerequis': [
                'Plan comptable du client obtenu',
                "Date de reprise des à-nouveaux arrêtée avec l'expert-comptable",
                'Exercices et périodes à ouvrir définis',
            ],
            'reglages': [
                'Journaux et comptes de contrepartie',
                'Régime et périodicité de TVA',
                'Règles de lettrage et de rapprochement bancaire',
            ],
            'roles': [
                'Créer le comptable et le valideur',
                "Vérifier qui peut clôturer une période",
            ],
            'donnees': [
                'Charger le plan comptable',
                'Charger les à-nouveaux à la date de reprise',
                'Charger les tiers et leurs soldes',
                'Réconcilier les TOTAUX, pas seulement les comptages',
            ],
            'recette': [
                'Saisir et valider une écriture de bout en bout',
                'Rapprocher un relevé bancaire',
                'Sortir un grand livre et un balance de contrôle',
            ],
            'golive': [
                "Faire valider les soldes de reprise par l'expert-comptable",
                'Clôturer la période de bascule',
                'Point de suivi à J+7',
            ],
        },
    },
    {
        'cle': 'rh_paie',
        'titre': 'Déploiement module RH & Paie',
        'resume': "Mise en service des dossiers salariés et de la paie.",
        'etapes': {
            'prerequis': [
                'Effectif et contrats en cours listés',
                'Éléments de paie récurrents recensés',
                'Dernier bulletin de paie de référence récupéré',
            ],
            'reglages': [
                'Calendrier de paie et périodes',
                'Rubriques de paie et cotisations',
                'Règles de congés et absences',
            ],
            'roles': [
                'Créer le gestionnaire RH et le valideur',
                'Vérifier que les données de paie restent invisibles des autres paliers',
            ],
            'donnees': [
                'Charger les dossiers salariés',
                'Charger les soldes de congés',
                'Charger les éléments de paie récurrents',
                'Réconcilier avant de déclarer le lot chargé',
            ],
            'recette': [
                'Produire un bulletin et le comparer au bulletin de référence',
                'Poser puis valider une demande de congé',
                "Vérifier l'export destiné à la déclaration sociale",
            ],
            'golive': [
                'Choisir un mois de bascule sans rattrapage en cours',
                'Faire valider le premier cycle de paie par le client',
                'Point de suivi au cycle suivant',
            ],
        },
    },
)


def cle_graine(cle):
    """Tag d'identité stable d'un playbook seedé."""
    return f'{PREFIXE_GRAINE}{cle}'


def structure_pour(definition):
    """Construit la ``contenu_structure`` canonique d'un playbook du catalogue.

    Les clés d'étape sont dérivées de la phase (``prerequis.1``…) : elles sont
    donc uniques dans le playbook — deux étapes de même clé feraient MENTIR la
    progression d'une instance (NTMIG22).
    """
    etapes_par_phase = definition['etapes']
    phases = []
    for cle_phase, titre_phase in PHASES:
        libelles = etapes_par_phase.get(cle_phase) or []
        phases.append({
            'cle': cle_phase,
            'titre': titre_phase,
            'etapes': [
                {'cle': f'{cle_phase}.{index}', 'libelle': libelle}
                for index, libelle in enumerate(libelles, start=1)
            ],
        })
    return phases


def corps_pour(definition):
    """Corps texte de l'article : le résumé + les phases en clair.

    Un playbook reste un article kb ORDINAIRE : il doit rester lisible dans la
    recherche plein texte et à l'impression, pas seulement dans l'écran qui
    sait dessiner des cases à cocher.
    """
    lignes = [definition['resume'], '']
    for phase in structure_pour(definition):
        lignes.append(f"## {phase['titre']}")
        for etape in phase['etapes']:
            lignes.append(f"- [ ] {etape['libelle']}")
        lignes.append('')
    return '\n'.join(lignes).strip() + '\n'
