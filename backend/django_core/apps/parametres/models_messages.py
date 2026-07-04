"""Modèles de message WhatsApp éditables (``MessageTemplate``).

Domaine « Messages & relances ». Extrait de l'ancien ``models.py`` sans aucun
changement de champ, de ``Meta`` ou de nom de table — la table reste
``parametres_messagetemplate`` (split sans migration)."""
from django.db import models


# Modèles de message WhatsApp éditables (Paramètres → Messages). Placeholders
# supportés : {civilite} {nom} {reference} {lien} {n}. Le défaut s'applique tant
# que l'entreprise n'a pas enregistré sa propre version (rien ne change sinon).
MESSAGE_TEMPLATE_DEFAULTS = {
    'devis_unique':
        'Bonjour {civilite} {nom}, voici votre devis Taqinor '
        '({reference}) : {lien}',
    'devis_multi_entete':
        'Bonjour {civilite} {nom}, voici vos {n} devis Taqinor :',
    'devis_multi_ligne':
        '{reference} : {lien}',
    'facture':
        'Bonjour {civilite} {nom}, voici votre facture Taqinor '
        '({reference}) : {lien}',
    'relance':
        'Bonjour {civilite} {nom}, petit rappel concernant votre facture '
        'Taqinor ({reference}) : {lien}',
    # XSAV4 — transitions de ticket SAV (client). {lien} = lien-client FG86.
    'ticket_recu':
        'Bonjour {civilite} {nom}, votre ticket SAV {reference} a bien été '
        'reçu par notre équipe. Suivi : {lien}',
    'ticket_planifie':
        'Bonjour {civilite} {nom}, votre intervention {reference} est '
        'planifiée. Suivi : {lien}',
    'ticket_resolu':
        'Bonjour {civilite} {nom}, votre ticket SAV {reference} a été '
        'résolu. Suivi : {lien}',
    # XSTK22 — notifications client aux transitions de livraison.
    'livraison_en_transit':
        'Bonjour {civilite} {nom}, votre matériel {reference} est en route '
        'vers votre chantier. Suivi : {lien}',
    'livraison_livree':
        'Bonjour {civilite} {nom}, votre matériel {reference} a été livré '
        'sur votre chantier. Suivi : {lien}',
}


class MessageTemplate(models.Model):
    """Un modèle de message WhatsApp éditable, par entreprise et par clé.

    Deux variantes de langue : Français (`corps_fr`) et Darija (`corps_darija`).
    La Darija retombe sur le FR tant qu'elle est vide.
    """
    class Cle(models.TextChoices):
        DEVIS_UNIQUE = 'devis_unique', 'Devis (un seul)'
        DEVIS_MULTI_ENTETE = 'devis_multi_entete', 'Devis (plusieurs) — en-tête'
        DEVIS_MULTI_LIGNE = 'devis_multi_ligne', 'Devis (plusieurs) — ligne'
        FACTURE = 'facture', 'Facture'
        RELANCE = 'relance', 'Rappel de paiement'
        # XSAV4 — notifications client aux transitions du ticket SAV.
        TICKET_RECU = 'ticket_recu', 'Ticket SAV reçu'
        TICKET_PLANIFIE = 'ticket_planifie', 'Ticket SAV planifié'
        TICKET_RESOLU = 'ticket_resolu', 'Ticket SAV résolu'
        # XSTK22 — notifications client aux transitions de livraison.
        LIVRAISON_EN_TRANSIT = 'livraison_en_transit', 'Livraison en transit'
        LIVRAISON_LIVREE = 'livraison_livree', 'Livraison livrée'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='message_templates',
    )
    cle = models.CharField(max_length=40, choices=Cle.choices)
    corps_fr = models.TextField(blank=True, default='')
    corps_darija = models.TextField(blank=True, default='')

    class Meta:
        unique_together = [('company', 'cle')]
        ordering = ['cle']

    def __str__(self):
        return f'{self.company_id}:{self.cle}'

    @classmethod
    def get_corps(cls, company, cle, langue='fr'):
        """Corps du message pour (company, cle, langue), défaut si absent.

        La Darija vide retombe sur le FR ; le FR vide retombe sur le défaut.
        """
        row = cls.objects.filter(company=company, cle=cle).first()
        default = MESSAGE_TEMPLATE_DEFAULTS.get(cle, '')
        if row is None:
            return default
        if langue == 'darija' and row.corps_darija.strip():
            return row.corps_darija
        return row.corps_fr.strip() or default
