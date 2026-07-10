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
# {civilite} {nom} {reference} {lien} {n} {entreprise}.
# SCA25 — {entreprise} : nom de la société émettrice (CompanyProfile), résolu
# par ``render`` ; à défaut de profil nommé, retombe sur le littéral historique
# (« Taqinor », « TAQINOR » pour envoi_devis) — rendu byte-identique sans profil.
EMAIL_TEMPLATE_DEFAULTS = {
    'devis': {
        'sujet': 'Votre devis {entreprise} ({reference})',
        'corps':
            'Bonjour {civilite} {nom},\n\n'
            'Veuillez trouver votre devis {entreprise} ({reference}) au lien '
            'suivant : {lien}\n\n'
            'Cordialement,\nL\'équipe {entreprise}',
    },
    'facture': {
        'sujet': 'Votre facture {entreprise} ({reference})',
        'corps':
            'Bonjour {civilite} {nom},\n\n'
            'Veuillez trouver votre facture {entreprise} ({reference}) au lien '
            'suivant : {lien}\n\n'
            'Cordialement,\nL\'équipe {entreprise}',
    },
    'relance': {
        'sujet': 'Rappel — facture {entreprise} ({reference})',
        'corps':
            'Bonjour {civilite} {nom},\n\n'
            'Petit rappel concernant votre facture {entreprise} ({reference}) : '
            '{lien}\n\n'
            'Cordialement,\nL\'équipe {entreprise}',
    },
    'notification': {
        'sujet': 'Notification {entreprise}',
        'corps':
            'Bonjour {civilite} {nom},\n\n'
            'Vous avez une nouvelle notification concernant {reference}.\n\n'
            'Cordialement,\nL\'équipe {entreprise}',
    },
    # XSAV4 — transitions de ticket SAV (client). {lien} = lien-client FG86.
    'ticket_recu': {
        'sujet': 'Votre ticket SAV {reference} a été reçu',
        'corps':
            'Bonjour {civilite} {nom},\n\n'
            'Votre ticket SAV ({reference}) a bien été reçu par notre '
            'équipe. Suivi : {lien}\n\n'
            'Cordialement,\nL\'équipe {entreprise}',
    },
    'ticket_planifie': {
        'sujet': 'Votre intervention {reference} est planifiée',
        'corps':
            'Bonjour {civilite} {nom},\n\n'
            'Votre intervention ({reference}) est planifiée. '
            'Suivi : {lien}\n\n'
            'Cordialement,\nL\'équipe {entreprise}',
    },
    'ticket_resolu': {
        'sujet': 'Votre ticket SAV {reference} a été résolu',
        'corps':
            'Bonjour {civilite} {nom},\n\n'
            'Votre ticket SAV ({reference}) a été résolu. '
            'Suivi : {lien}\n\n'
            'Cordialement,\nL\'équipe {entreprise}',
    },
    # XFAC7 — rappel de courtoisie PRÉ-échéance (J-N avant échéance, jamais
    # après). Ton amical, distinct de la relance (qui part APRÈS échéance).
    'pre_echeance': {
        'sujet': 'Rappel amical — échéance à venir ({reference})',
        'corps':
            'Bonjour {civilite} {nom},\n\n'
            'Votre facture {entreprise} ({reference}) arrive prochainement à '
            'échéance. Vous pouvez régler dès maintenant : {lien}\n\n'
            'Merci de votre confiance,\nL\'équipe {entreprise}',
    },
    # XSTK22 — notifications client aux transitions de sa livraison.
    'livraison_en_transit': {
        'sujet': 'Votre livraison {reference} est en route',
        'corps':
            'Bonjour {civilite} {nom},\n\n'
            'Votre matériel ({reference}) est en cours d\'acheminement vers '
            'votre chantier. Suivi : {lien}\n\n'
            'Cordialement,\nL\'équipe {entreprise}',
    },
    'livraison_livree': {
        'sujet': 'Votre livraison {reference} est arrivée',
        'corps':
            'Bonjour {civilite} {nom},\n\n'
            'Votre matériel ({reference}) a été livré sur votre chantier. '
            'Suivi : {lien}\n\n'
            'Cordialement,\nL\'équipe {entreprise}',
    },
    # ZSAL5 — gabarit dédié « envoi de devis » (QJ14). Défaut = texte
    # actuellement codé en dur dans ``ventes.views.devis.envoyer_email``
    # (``{nom}`` porte déjà « Bonjour {nom}, » ou « Bonjour, » — construit
    # côté appelant — pour rester rendu BYTE-IDENTIQUE tant que la société
    # n'a rien édité). ``{civilite}`` reste disponible pour une
    # personnalisation manuelle future.
    'envoi_devis': {
        'sujet': 'Votre devis {reference}',
        'corps':
            '{nom}\n\n'
            'Veuillez trouver ci-joint votre devis {reference}.\n\n'
            'Vous pouvez également consulter et signer votre proposition en '
            'ligne :\n{lien}\n\n'
            'Nous restons à votre disposition pour toute question.\n\n'
            'Cordialement,\nL\'équipe {entreprise}',
    },
}


# Placeholders autorisés par clé (parité avec ``MessageTemplate``). On valide au
# sérialiseur qu'un sujet/corps ne référence QUE ces tokens-là.
EMAIL_TEMPLATE_PLACEHOLDERS = {
    'devis': ['{civilite}', '{nom}', '{reference}', '{lien}', '{entreprise}'],
    'facture': ['{civilite}', '{nom}', '{reference}', '{lien}', '{entreprise}'],
    'relance': ['{civilite}', '{nom}', '{reference}', '{lien}', '{entreprise}'],
    'notification': [
        '{civilite}', '{nom}', '{reference}', '{lien}', '{n}', '{entreprise}'],
    'ticket_recu': [
        '{civilite}', '{nom}', '{reference}', '{lien}', '{entreprise}'],
    'ticket_planifie': [
        '{civilite}', '{nom}', '{reference}', '{lien}', '{entreprise}'],
    'ticket_resolu': [
        '{civilite}', '{nom}', '{reference}', '{lien}', '{entreprise}'],
    'pre_echeance': [
        '{civilite}', '{nom}', '{reference}', '{lien}', '{entreprise}'],
    'livraison_en_transit': [
        '{civilite}', '{nom}', '{reference}', '{lien}', '{entreprise}'],
    'livraison_livree': [
        '{civilite}', '{nom}', '{reference}', '{lien}', '{entreprise}'],
    # ZSAL5 — {validite} en plus (date limite de validité du devis).
    # XSAL17 — {lien_rdv} : lien de réservation de visite, résolu au moment
    # de l'envoi (apps.crm.services.resoudre_lien_rdv / public_booking_url).
    'envoi_devis': [
        '{civilite}', '{nom}', '{reference}', '{lien}', '{validite}',
        '{lien_rdv}', '{entreprise}'],
}

# SCA25 — littéral de repli du placeholder {entreprise} quand la société n'a
# pas de profil nommé : le littéral HISTORIQUE de chaque clé (casse préservée)
# pour un rendu byte-identique à l'existant sans profil.
_ENTREPRISE_FALLBACKS = {'envoi_devis': 'TAQINOR'}
_ENTREPRISE_FALLBACK_DEFAULT = 'Taqinor'


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
        # XSAV4 — notifications client aux transitions du ticket SAV.
        TICKET_RECU = 'ticket_recu', 'Ticket SAV reçu'
        TICKET_PLANIFIE = 'ticket_planifie', 'Ticket SAV planifié'
        TICKET_RESOLU = 'ticket_resolu', 'Ticket SAV résolu'
        # XFAC7 — rappel de courtoisie PRÉ-échéance (J-N avant échéance).
        PRE_ECHEANCE = 'pre_echeance', 'Rappel pré-échéance'
        # XSTK22 — notifications client aux transitions de livraison.
        LIVRAISON_EN_TRANSIT = 'livraison_en_transit', 'Livraison en transit'
        LIVRAISON_LIVREE = 'livraison_livree', 'Livraison livrée'
        # ZSAL5 — gabarit dédié « envoi de devis » (distinct de DEVIS, encore
        # inutilisé par l'action d'envoi).
        ENVOI_DEVIS = 'envoi_devis', 'Envoi de devis'

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

        SCA25 — ``{entreprise}`` est résolu ICI (sauf si l'appelant le fournit) :
        nom du profil société (``parametres.selectors.company_identity``), sinon
        littéral historique de la clé — un tenant nommé voit SON nom, une société
        sans profil garde le rendu d'aujourd'hui.
        """
        tpl = cls.get_template(company, cle)
        if 'entreprise' not in context:
            nom = ''
            try:
                from apps.parametres.selectors import company_identity
                nom = (company_identity(company).get('nom') or '').strip()
            except Exception:  # pragma: no cover — best-effort, jamais bloquant
                nom = ''
            context['entreprise'] = nom or _ENTREPRISE_FALLBACKS.get(
                cle, _ENTREPRISE_FALLBACK_DEFAULT)
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
