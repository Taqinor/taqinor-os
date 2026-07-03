"""FG17 — Modèles d'e-mail éditables (``EmailTemplate``).

Domaine « Messages & relances », volet e-mail. Parité avec les modèles WhatsApp
(``MessageTemplate``) : par société et par clé (``cle``), un SUJET éditable
(``sujet``) et un CORPS éditable (``corps``) qui supportent les mêmes
placeholders que les modèles WhatsApp (``{civilite}`` ``{nom}`` ``{reference}``
``{lien}`` ``{n}``). Tant que la société n'a pas enregistré sa propre version,
le défaut s'applique — rien ne change sinon.

Choix « nouveau modèle plutôt qu'extension de ``MessageTemplate`` » : la table
WhatsApp (``parametres_messagetemplate``) est déjà peuplée et n'a ni champ
``sujet`` ni notion de canal ; lui ajouter un discriminant + ``sujet`` toucherait
sa contrainte d'unicité et son API existante. Un modèle dédié est UNE migration
additive, sans risque pour la table existante. Le fichier est gardé séparé
(indépendance des lanes) et enregistré via ``apps.py`` ``ready()`` — ``models.py``
n'est pas touché. Cette couche RENDU ne change aucun statut.

NB : l'action e-mail de l'app automation continue d'utiliser son sujet codé en
dur pour l'instant — le câblage est volontairement laissé à une autre lane ;
ici on fournit seulement le modèle + l'API + l'aide ``get_template`` /
``render``.
"""
from django.db import models


# Sujet + corps par défaut pour chaque clé. Le défaut s'applique tant que la
# société n'a pas personnalisé. Placeholders supportés (parité WhatsApp) :
# {civilite} {nom} {reference} {lien} {n}.
EMAIL_TEMPLATE_DEFAULTS = {
    'devis': {
        'sujet': 'Votre devis Taqinor ({reference})',
        'corps':
            'Bonjour {civilite} {nom},\n\n'
            'Veuillez trouver votre devis Taqinor ({reference}) au lien '
            'suivant : {lien}\n\n'
            'Cordialement,\nL\'équipe Taqinor',
    },
    'facture': {
        'sujet': 'Votre facture Taqinor ({reference})',
        'corps':
            'Bonjour {civilite} {nom},\n\n'
            'Veuillez trouver votre facture Taqinor ({reference}) au lien '
            'suivant : {lien}\n\n'
            'Cordialement,\nL\'équipe Taqinor',
    },
    'relance': {
        'sujet': 'Rappel — facture Taqinor ({reference})',
        'corps':
            'Bonjour {civilite} {nom},\n\n'
            'Petit rappel concernant votre facture Taqinor ({reference}) : '
            '{lien}\n\n'
            'Cordialement,\nL\'équipe Taqinor',
    },
    'notification': {
        'sujet': 'Notification Taqinor',
        'corps':
            'Bonjour {civilite} {nom},\n\n'
            'Vous avez une nouvelle notification concernant {reference}.\n\n'
            'Cordialement,\nL\'équipe Taqinor',
    },
    # XFAC7 — rappel de courtoisie PRÉ-échéance (J-N avant échéance, jamais
    # après). Ton amical, distinct de la relance (qui part APRÈS échéance).
    'pre_echeance': {
        'sujet': 'Rappel amical — échéance à venir ({reference})',
        'corps':
            'Bonjour {civilite} {nom},\n\n'
            'Votre facture Taqinor ({reference}) arrive prochainement à '
            'échéance. Vous pouvez régler dès maintenant : {lien}\n\n'
            'Merci de votre confiance,\nL\'équipe Taqinor',
    },
}


# Placeholders autorisés par clé (parité avec ``MessageTemplate``). On valide au
# sérialiseur qu'un sujet/corps ne référence QUE ces tokens-là.
EMAIL_TEMPLATE_PLACEHOLDERS = {
    'devis': ['{civilite}', '{nom}', '{reference}', '{lien}'],
    'facture': ['{civilite}', '{nom}', '{reference}', '{lien}'],
    'relance': ['{civilite}', '{nom}', '{reference}', '{lien}'],
    'notification': ['{civilite}', '{nom}', '{reference}', '{lien}', '{n}'],
    'pre_echeance': ['{civilite}', '{nom}', '{reference}', '{lien}'],
}


class EmailTemplate(models.Model):
    """Un modèle d'e-mail éditable, par société et par clé.

    Parité avec ``MessageTemplate`` (WhatsApp) mais côté e-mail : un ``sujet``
    en plus du ``corps``. Additif : la table est vide par défaut ; chaque ligne
    est la version personnalisée d'une clé existante. Le défaut
    (``EMAIL_TEMPLATE_DEFAULTS``) s'applique tant qu'aucune ligne n'est posée.
    """

    class Cle(models.TextChoices):
        DEVIS = 'devis', 'Devis'
        FACTURE = 'facture', 'Facture'
        RELANCE = 'relance', 'Rappel de paiement'
        NOTIFICATION = 'notification', 'Notification'
        # XFAC7 — rappel de courtoisie PRÉ-échéance (J-N avant échéance).
        PRE_ECHEANCE = 'pre_echeance', 'Rappel pré-échéance'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='email_templates',
    )
    cle = models.CharField(max_length=40, choices=Cle.choices)
    sujet = models.CharField(max_length=255, blank=True, default='')
    corps = models.TextField(blank=True, default='')

    class Meta:
        # app_label explicite : ce module n'est pas importé par ``models.py``
        # (gardé séparé pour l'indépendance des lanes) ; il est chargé via
        # ``apps.py`` ready(). L'étiquette d'app reste « parametres ».
        app_label = 'parametres'
        unique_together = [('company', 'cle')]
        ordering = ['cle']
        verbose_name = "Modèle d'e-mail"
        verbose_name_plural = "Modèles d'e-mail"

    def __str__(self):
        return f'{self.company_id}:{self.cle}'

    @classmethod
    def get_template(cls, company, cle):
        """Renvoie ``{'sujet', 'corps'}`` pour (company, cle), défaut si absent.

        Aide destinée à l'action e-mail de l'automation (câblage dans une autre
        lane) : un sujet/corps vide retombe sur le défaut de la clé.
        """
        default = EMAIL_TEMPLATE_DEFAULTS.get(cle, {'sujet': '', 'corps': ''})
        row = None
        if company is not None:
            row = cls.objects.filter(company=company, cle=cle).first()
        if row is None:
            return {'sujet': default['sujet'], 'corps': default['corps']}
        return {
            'sujet': row.sujet.strip() or default['sujet'],
            'corps': row.corps.strip() or default['corps'],
        }

    @classmethod
    def render(cls, company, cle, **context):
        """Sujet + corps de (company, cle) avec les placeholders substitués.

        Substitution tolérante : un placeholder absent du ``context`` est laissé
        tel quel (jamais de ``KeyError``) — l'appelant fournit ce qu'il a.
        """
        tpl = cls.get_template(company, cle)
        return {
            'sujet': _safe_format(tpl['sujet'], context),
            'corps': _safe_format(tpl['corps'], context),
        }


def _safe_format(text, context):
    """``str.format``-like qui laisse intacts les tokens absents du contexte."""
    class _Default(dict):
        def __missing__(self, key):
            return '{' + key + '}'
    return (text or '').format_map(_Default(context))
