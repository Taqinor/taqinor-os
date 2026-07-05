"""Modèles du module Portail self-service client (``apps.portail``).

Équivalent Odoo Portal. Ces modèles ont d'abord vécu dans ``apps.compta``
(FG228–233) ; ODX12 les a SORTIS de compta en préservant à l'IDENTIQUE les
tables physiques existantes (``db_table = 'compta_<model>'``) via des migrations
``SeparateDatabaseAndState`` (state-only, aucun SQL, aucune donnée déplacée).
Un shim de ré-export subsiste dans ``apps/compta/models.py`` pour le
code/migrations historiques.

Frontière cross-app (CLAUDE.md) : ``portail`` ne lit ventes/crm/sav QUE via
leurs ``selectors.py``/``services.py`` ou par référence opaque (id/texte) —
jamais d'import de leurs ``models``. Le compte portail se lie au client par une
STRING-FK ``'crm.Client'`` (référence textuelle, aucun import). Devis/factures/
chantiers/tickets sont désignés par id opaque. Tout est multi-société : chaque
modèle porte un FK ``company`` posé côté serveur (jamais lu du corps de requête).

ATTENTION surface AUTH : les mécanismes d'authentification portail (tokens/
comptes clients) sont conservés À L'IDENTIQUE — aucun élargissement d'accès.
"""
from django.db import models


# ── FG228 — Portail self-service client ────────────────────────────────────

class ComptePortailClient(models.Model):
    """Compte d'accès au portail self-service client (FG228).

    Le client consulte ses devis, factures, chantiers et tickets. Le compte se
    lie à ``crm.Client`` PAR FK (string-FK, aucun import cross-app) et réutilise
    l'email du client (pas de 2ᵉ copie d'identité, DC32). L'accès est tokenisé ;
    aucune donnée métier n'est dupliquée ici.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='comptes_portail',
        verbose_name='Société',
    )
    client = models.ForeignKey(
        'crm.Client',
        on_delete=models.CASCADE,
        related_name='comptes_portail',
        verbose_name='Client',
    )
    token_acces = models.CharField(
        max_length=64, unique=True, db_index=True,
        verbose_name="Token d'accès")
    actif = models.BooleanField(default=True, verbose_name='Actif')
    derniere_connexion = models.DateTimeField(
        null=True, blank=True, verbose_name='Dernière connexion')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Compte portail client'
        verbose_name_plural = 'Comptes portail client'
        db_table = 'compta_compteportailclient'
        ordering = ['-date_creation']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'client'],
                name='uniq_compte_portail_client',
            ),
        ]

    @property
    def email(self):
        """DC32 — l'email vient du client (source unique), jamais stocké ici."""
        return getattr(self.client, 'email', None)

    def __str__(self):
        return f'Portail {self.email or self.client_id}'


# ── FG229 — Acceptation / e-signature de devis dans le portail ─────────────

class AcceptationDevisPortail(models.Model):
    """Acceptation en ligne d'un devis depuis le portail client (FG229).

    Le client choisit une option (variante chiffrée) puis signe en saisissant
    son nom ; on horodate et on capture l'IP comme preuve légère (loi 53-05 :
    une signature nominative suffit pour un devis solaire résidentiel/PME). Le
    devis est désigné par son id (jamais par import du modèle ``ventes`` —
    cross-app via service/string-id) ; cet enregistrement matérialise
    l'acceptation côté OS sans dupliquer le devis. Une e-signature certifiée
    (Yousign, gated G7) reste optionnelle et hors périmètre ici.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='acceptations_devis_portail',
        verbose_name='Société',
    )
    devis_id = models.PositiveIntegerField(verbose_name='Id du devis')
    option_choisie = models.CharField(
        max_length=120, blank=True, default='',
        verbose_name='Option choisie')
    nom_signataire = models.CharField(
        max_length=200, verbose_name='Nom du signataire')
    signature_ip = models.GenericIPAddressField(
        null=True, blank=True, verbose_name='IP de signature')
    accepte = models.BooleanField(default=False, verbose_name='Accepté')
    signe_le = models.DateTimeField(
        null=True, blank=True, verbose_name='Signé le')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créée le')

    class Meta:
        verbose_name = 'Acceptation de devis (portail)'
        verbose_name_plural = 'Acceptations de devis (portail)'
        db_table = 'compta_acceptationdevisportail'
        ordering = ['-date_creation']

    def __str__(self):
        return f'Acceptation devis #{self.devis_id} — {self.nom_signataire}'


# ── FG230 — Paiement en ligne des factures (portail) ───────────────────────

class PaiementFacturePortail(models.Model):
    """Intention de paiement en ligne d'une facture depuis le portail (FG230).

    Le client clique « payer » (CMI carte ou virement) ; on enregistre une
    intention de paiement scopée société, puis le rapprochement la passe de
    ``initie`` à ``paye`` (manuel pour le virement, automatique via webhook CMI
    quand l'intégration est branchée). Tant que la passerelle CMI est OFF
    (``CMI_ENABLED``, défaut), aucun appel réseau payant n'est émis : l'intention
    reste ``initie`` avec une référence locale. La facture est désignée par son
    id (cross-app — jamais d'import du modèle ``ventes``).
    """
    class Methode(models.TextChoices):
        CARTE = 'carte', 'Carte (CMI)'
        VIREMENT = 'virement', 'Virement'

    class Statut(models.TextChoices):
        INITIE = 'initie', 'Initié'
        PAYE = 'paye', 'Payé'
        ECHOUE = 'echoue', 'Échoué'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='paiements_facture_portail',
        verbose_name='Société',
    )
    facture_id = models.PositiveIntegerField(verbose_name='Id de la facture')
    montant = models.DecimalField(
        max_digits=14, decimal_places=2, default=0,
        verbose_name='Montant (MAD)')
    methode = models.CharField(
        max_length=8, choices=Methode.choices, default=Methode.CARTE,
        verbose_name='Méthode')
    statut = models.CharField(
        max_length=8, choices=Statut.choices, default=Statut.INITIE,
        verbose_name='Statut')
    reference = models.CharField(
        max_length=64, blank=True, default='',
        verbose_name='Référence de transaction')
    paye_le = models.DateTimeField(
        null=True, blank=True, verbose_name='Payé le')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Paiement de facture (portail)'
        verbose_name_plural = 'Paiements de facture (portail)'
        db_table = 'compta_paiementfactureportail'
        ordering = ['-date_creation']

    def __str__(self):
        return f'Paiement facture #{self.facture_id} ({self.statut})'


# ── FG231 — Dépôt de documents / factures ONEE par le client ───────────────

class DocumentClientPortail(models.Model):
    """Document téléversé par le client depuis le portail (FG231).

    Le client dépose ses factures ONEE (ou autre justificatif) pour affiner
    l'étude solaire — l'app y lit la consommation. Scopé société ; lié au client
    par id (cross-app, jamais d'import crm) et, optionnellement, au lead. Le
    fichier va dans le stockage objet (MinIO/S3) ; aucun prix/marge ici.
    """
    class TypeDoc(models.TextChoices):
        FACTURE_ONEE = 'facture_onee', 'Facture ONEE'
        PLAN = 'plan', 'Plan / schéma'
        AUTRE = 'autre', 'Autre'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='documents_client_portail',
        verbose_name='Société',
    )
    client_id = models.PositiveIntegerField(verbose_name='Id du client')
    lead_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Id du lead')
    type_document = models.CharField(
        max_length=14, choices=TypeDoc.choices, default=TypeDoc.FACTURE_ONEE,
        verbose_name='Type de document')
    libelle = models.CharField(
        max_length=200, blank=True, default='', verbose_name='Libellé')
    fichier = models.FileField(
        upload_to='compta/portail_docs/', null=True, blank=True,
        verbose_name='Fichier')
    traite = models.BooleanField(
        default=False, verbose_name='Traité (intégré à l\'étude)')
    date_depot = models.DateTimeField(
        auto_now_add=True, verbose_name='Déposé le')

    class Meta:
        verbose_name = 'Document client (portail)'
        verbose_name_plural = 'Documents client (portail)'
        db_table = 'compta_documentclientportail'
        ordering = ['-date_depot']

    def __str__(self):
        return f'{self.get_type_document_display()} — client #{self.client_id}'


# ── FG232 — Suivi d'avancement du chantier côté client (timeline) ──────────

class JalonChantierPortail(models.Model):
    """Jalon d'avancement d'un chantier exposé au client dans le portail (FG232).

    Timeline lecture-seule côté client : étude → commande → livraison →
    installation → mise en service → réception. Chaque jalon porte un libellé,
    un ordre, un état atteint/non-atteint et une date. Le chantier est désigné
    par son id (cross-app — jamais d'import ``installations``). Scopé société ;
    aucune donnée financière n'est exposée ici.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='jalons_chantier_portail',
        verbose_name='Société',
    )
    chantier_id = models.PositiveIntegerField(verbose_name='Id du chantier')
    libelle = models.CharField(max_length=120, verbose_name='Jalon')
    ordre = models.PositiveIntegerField(default=0, verbose_name='Ordre')
    atteint = models.BooleanField(default=False, verbose_name='Atteint')
    date_jalon = models.DateField(
        null=True, blank=True, verbose_name='Date du jalon')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Jalon de chantier (portail)'
        verbose_name_plural = 'Jalons de chantier (portail)'
        db_table = 'compta_jalonchantierportail'
        ordering = ['chantier_id', 'ordre', 'id']

    def __str__(self):
        return f'Chantier #{self.chantier_id} — {self.libelle}'


# ── FG233 — Ouverture de ticket SAV depuis le portail ──────────────────────

class DemandeTicketPortail(models.Model):
    """Demande de ticket SAV/garantie ouverte par le client via le portail
    (FG233).

    Le client décrit un problème ; on enregistre la demande scopée société,
    puis le SAV la prend en charge en créant le vrai ticket (app ``sav``, via
    son service — jamais d'import de ses modèles ici). ``ticket_id`` référence
    le ticket SAV créé (cross-app par id). Le client suit l'état de sa demande
    en lecture depuis le portail.
    """
    class Statut(models.TextChoices):
        SOUMISE = 'soumise', 'Soumise'
        PRISE_EN_CHARGE = 'prise_en_charge', 'Prise en charge'
        RESOLUE = 'resolue', 'Résolue'
        REFUSEE = 'refusee', 'Refusée'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='demandes_ticket_portail',
        verbose_name='Société',
    )
    client_id = models.PositiveIntegerField(verbose_name='Id du client')
    chantier_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Id du chantier')
    sujet = models.CharField(max_length=200, verbose_name='Sujet')
    description = models.TextField(
        blank=True, default='', verbose_name='Description')
    statut = models.CharField(
        max_length=16, choices=Statut.choices, default=Statut.SOUMISE,
        verbose_name='Statut')
    ticket_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Id du ticket SAV créé')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créée le')

    class Meta:
        verbose_name = 'Demande de ticket SAV (portail)'
        verbose_name_plural = 'Demandes de ticket SAV (portail)'
        db_table = 'compta_demandeticketportail'
        ordering = ['-date_creation']

    def __str__(self):
        return f'Demande SAV #{self.client_id} — {self.sujet}'
