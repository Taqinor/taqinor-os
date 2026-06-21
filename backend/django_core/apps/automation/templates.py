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
        'nom': 'Lien WhatsApp à l'acceptation d'un devis',
        'description': (
            'Prépare un lien WhatsApp vers le client dès qu'un devis est '
            'accepté (le lien s'ouvre dans WhatsApp Web — pas d'envoi '
            'automatique).'
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
            'Assigne automatiquement un lead qui vient de passer à l'étape '
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
            'Crée une activité « Préparer la commande matériel » quand un '
            'lead passe à l'étape SIGNED.'
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
                'Cordialement,\nL'équipe Taqinor'
            ),
        },
        'requires_approval': False,
    },
    {
        'id': 'ticket_sav_on_warranty_expiring',
        'nom': 'Créer un ticket SAV préventif avant expiration de garantie',
        'description': (
            'Crée un ticket SAV de type préventif quand la garantie d'un '
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
            'Crée une activité « Commander du stock » quand un produit '
            'passe sous son seuil d'alerte.'
        ),
        'trigger_type': 'stock_below_threshold',
        'trigger_config': {},
        'action_type': 'create_activity',
        'action_config': {
            'body': 'Commander du stock : le produit est sous le seuil d'alerte.',
        },
        'requires_approval': False,
    },
]
