"""FG3 — Bibliothèque de modèles d'automatisation (presets sans-code).

Un modèle est un jeu de valeurs préremplissant la création d'une règle.
L'UI peut les afficher dans un sélecteur « Créer depuis un modèle » et
préremplir le formulaire — jamais de création automatique de règles.

Chaque modèle porte :
  - id        : identifiant stable (ne change pas)
  - nom       : libellé FR lisible
  - description : explication courte de ce que fait la règle
  - trigger_type / trigger_config / action_type / action_config :
    valeurs exactes pour la règle AutomationRule
  - requires_approval : True si l'action exige une approbation par défaut

Les libellés sont en FRANÇAIS ; les clés techniques suivent le modèle EN.
"""

AUTOMATION_TEMPLATES = [
    {
        'id': 'whatsapp_on_devis_accepte',
        'nom': "Lien WhatsApp à l'acceptation d'un devis",
        'description': (
            "Prépare un lien WhatsApp vers le client dès qu'un devis est "
            "accepté (le lien s'ouvre dans WhatsApp Web — pas d'envoi "
            "automatique)."
        ),
        'trigger_type': 'devis_accepted',
        'trigger_config': {},
        'action_type': 'send_whatsapp',
        'action_config': {
            'message': 'Bonjour {client_nom}, votre devis a été accepté. '
                       'Merci de votre confiance !',
        },
        'requires_approval': False,
    },
    {
        'id': 'assign_lead_on_new',
        'nom': 'Assigner un nouveau lead au responsable par défaut',
        'description': (
            "Assigne automatiquement un lead qui vient de passer à l'étape "
            'NEW au premier responsable disponible de la société.'
        ),
        'trigger_type': 'lead_stage_change',
        'trigger_config': {'stage': 'NEW'},
        'action_type': 'assign_record',
        'action_config': {},
        'requires_approval': False,
    },
    {
        'id': 'activity_on_devis_signe',
        'nom': 'Créer une activité de suivi à la signature',
        'description': (
            "Crée une activité « Préparer la commande matériel » quand un "
            "lead passe à l'étape SIGNED."
        ),
        'trigger_type': 'lead_stage_change',
        'trigger_config': {'stage': 'SIGNED'},
        'action_type': 'create_activity',
        'action_config': {'body': 'Préparer la commande matériel pour ce chantier.'},
        'requires_approval': False,
    },
    {
        'id': 'email_on_facture_overdue',
        'nom': 'Email de relance pour facture en retard',
        'description': (
            'Envoie un email au client quand une facture passe en retard '
            '(nécessite un email configuré côté serveur).'
        ),
        'trigger_type': 'facture_overdue',
        'trigger_config': {},
        'action_type': 'send_email',
        'action_config': {
            'subject': 'Facture en retard – {reference}',
            'body': (
                'Bonjour {client_nom},\n\n'
                'Votre facture {reference} est en attente de règlement.\n\n'
                'Merci de procéder au paiement dans les meilleurs délais.\n\n'
                "Cordialement,\nL'équipe Taqinor"
            ),
        },
        'requires_approval': False,
    },
    {
        'id': 'ticket_sav_on_warranty_expiring',
        'nom': 'Créer un ticket SAV préventif avant expiration de garantie',
        'description': (
            "Crée un ticket SAV de type préventif quand la garantie d'un "
            'équipement expire dans les 90 prochains jours.'
        ),
        'trigger_type': 'warranty_expiring',
        'trigger_config': {},
        'action_type': 'create_sav_ticket',
        'action_config': {
            'type': 'preventif',
            'description': (
                'Visite préventive avant expiration de garantie – '
                '{produit_nom} ({numero_serie}).'
            ),
        },
        'requires_approval': True,
    },
    {
        'id': 'activity_on_maintenance_due',
        'nom': 'Activité de relance visite de maintenance',
        'description': (
            'Crée une activité « Planifier la visite de maintenance » '
            'quand un contrat de maintenance est dû.'
        ),
        'trigger_type': 'maintenance_due',
        'trigger_config': {},
        'action_type': 'create_activity',
        'action_config': {'body': 'Planifier la visite de maintenance préventive.'},
        'requires_approval': False,
    },
    {
        'id': 'alert_on_stock_low',
        'nom': 'Alerte stock bas',
        'description': (
            "Crée une activité « Commander du stock » quand un produit "
            "passe sous son seuil d'alerte."
        ),
        'trigger_type': 'stock_below_threshold',
        'trigger_config': {},
        'action_type': 'create_activity',
        'action_config': {
            'body': "Commander du stock : le produit est sous le seuil d'alerte.",
        },
        'requires_approval': False,
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# NTEXT33 — CATALOGUE de recettes INSTALLABLES (distinct d'AUTOMATION_TEMPLATES
# ci-dessus, qui ne fait que préremplir un formulaire). Une recette listée ici
# est MATÉRIALISÉE par ``installer_modele`` en une VRAIE ``AutomationRule``
# (multi-étapes via ``steps`` — NTEXT4/NTEXT6/NTEXT7 réutilisés, jamais un
# second moteur d'automatisation). ``parametres_requis`` liste les clés que
# l'appelant DOIT fournir à l'installation (ex. ``user_id`` pour une
# assignation) — l'installation refuse (erreur FR) s'il en manque.
CATALOGUE_MODELES = [
    {
        'code': 'relance_j3_devis_sans_reponse',
        'nom': 'Relance J+3 devis sans réponse',
        'description': (
            "Envoie un email de relance 3 jours après la date de validité "
            "d'un devis resté sans réponse (déclencheur générique "
            "« échéance de champ », champ date_validite du devis)."
        ),
        'trigger_type': 'date_echeance_champ',
        'trigger_config': {
            'model': 'ventes.devis', 'champ': 'date_validite',
            'offset_jours': 3,
        },
        'steps': [
            {'action_type': 'send_email', 'action_config': {
                'subject': 'Votre devis {reference} — toujours disponible ?',
                'body': (
                    'Bonjour {client_nom},\n\nVotre devis {reference} '
                    "est-il toujours d'actualité ? N'hésitez pas à nous "
                    'contacter pour toute question.\n\nCordialement.'
                ),
            }},
        ],
        'requires_approval': False,
    },
    {
        'code': 'alerte_stock_bas_bcf',
        'nom': 'Alerte stock bas → BCF',
        'description': (
            "Crée une activité « Préparer un Bon de Commande Fournisseur » "
            "dès qu'un produit passe sous son seuil d'alerte (préparation "
            'manuelle du BCF — aucune commande fournisseur automatique).'
        ),
        'trigger_type': 'stock_below_threshold',
        'trigger_config': {},
        'steps': [
            {'action_type': 'create_activity', 'action_config': {
                'body': 'Préparer un Bon de Commande Fournisseur : produit '
                        "sous le seuil d'alerte.",
            }},
        ],
        'requires_approval': False,
    },
    {
        'code': 'nouveau_lead_assignation',
        'nom': 'Nouveau lead → assignation',
        'description': (
            "Assigne automatiquement un nouveau lead au responsable désigné "
            "à l'installation (paramètre requis : user_id)."
        ),
        'trigger_type': 'lead_stage_change',
        'trigger_config': {'stage': 'NEW'},
        'steps': [
            {'action_type': 'assign_record', 'action_config': {}},
        ],
        'requires_approval': False,
        'parametres_requis': ['user_id'],
    },
]


def modele_par_code(code):
    """NTEXT33 — le modèle installable désigné par ``code``, ou ``None``."""
    for modele in CATALOGUE_MODELES:
        if modele.get('code') == code:
            return modele
    return None


class ParametreManquant(ValueError):
    """NTEXT33 — un paramètre requis par la recette n'a pas été fourni à
    l'installation. Aucun effet de bord : levée AVANT toute création."""


def installer_modele(company, code, *, params=None):
    """NTEXT33 — matérialise le modèle ``code`` en une VRAIE
    ``AutomationRule`` (+ ``AutomationStep`` s'il y en a plus d'une) pour
    ``company``. IDEMPOTENT : ``get_or_create`` sur ``(company, nom)`` — une
    ré-installation ne duplique pas la règle. Renvoie ``(rule, cree)`` ;
    ``rule`` est ``None`` si ``code`` est inconnu (``cree`` alors ``False``).
    """
    from .models import AutomationRule, AutomationStep

    modele = modele_par_code(code)
    if modele is None:
        return None, False

    params = dict(params or {})
    requis = modele.get('parametres_requis') or []
    manquants = [p for p in requis if not params.get(p)]
    if manquants:
        raise ParametreManquant(
            f"Paramètre(s) requis manquant(s) pour installer "
            f"« {modele['nom']} » : {', '.join(manquants)}.")

    steps = [dict(s) for s in modele.get('steps') or []]
    if steps and requis:
        # Les paramètres requis alimentent le PREMIER step (seul cas actuel
        # du catalogue — une future recette à plusieurs cibles paramétrées
        # étendrait ce mapping, jamais en dur ailleurs).
        steps[0] = {
            'action_type': steps[0]['action_type'],
            'action_config': {**steps[0].get('action_config', {}),
                              **{p: params[p] for p in requis}},
        }
    premiere = steps[0] if steps else {
        'action_type': modele.get('action_type', 'create_activity'),
        'action_config': modele.get('action_config') or {},
    }

    rule, cree = AutomationRule.objects.get_or_create(
        company=company, nom=modele['nom'],
        defaults={
            'trigger_type': modele['trigger_type'],
            'trigger_config': dict(modele.get('trigger_config') or {}),
            'action_type': premiere['action_type'],
            'action_config': dict(premiere.get('action_config') or {}),
            'requires_approval': modele.get('requires_approval', False),
        })
    if cree:
        for idx, step in enumerate(steps[1:], start=2):
            AutomationStep.objects.create(
                rule=rule, ordre=idx, action_type=step['action_type'],
                action_config=dict(step.get('action_config') or {}))
    return rule, cree
