"""
FG311 — RFQ multi-fournisseurs & comparatif d'offres.

``RFQ`` (Request For Quotation, « demande de prix ») consulte PLUSIEURS
fournisseurs (``stock.Fournisseur``, string-FK) avant de choisir, typiquement à
partir d'une demande d'achat approuvée (``DemandeAchat``, FG310, même app, lien
optionnel). Chaque réponse fournisseur est une ``RFQOffre`` (montant, délai,
validité, retenue éventuelle). Le COMPARATIF (offre la moins chère / la plus
rapide / retenue) se lit via ``selectors.rfq_comparatif`` — aucune donnée
dénormalisée.

Le choix d'une offre (``retenue``) prépare le BCF mais ne le crée PAS ici (le BCF
matériel reste géré par ``stock``). Cross-app : ``stock.Fournisseur`` en
string-FK uniquement — aucun import du modèle ``stock`` au chargement.

Cycle de vie PROPRE (brouillon → envoyée → clôturée), distinct des autres couches
de statut de l'OS. Additif & multi-tenant : FK ``company`` posée côté serveur.
"""
import secrets

from django.conf import settings
from django.db import models


def _default_rfq_token():
    """XPUR20/21 — jeton public long et imprévisible (même patron que
    ``Ticket.share_token`` FG86), UN par (RFQ, fournisseur)."""
    return secrets.token_urlsafe(32)


class RFQ(models.Model):
    """FG311 — demande de prix consultant plusieurs fournisseurs.

    Multi-tenant : société posée côté serveur. Référence ``RFQ-YYYYMM-NNNN``
    anti-collision (jamais count()+1)."""

    class Statut(models.TextChoices):
        BROUILLON = 'brouillon', 'Brouillon'
        ENVOYEE = 'envoyee', 'Envoyée'
        CLOTUREE = 'cloturee', 'Clôturée'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='installations_rfqs')
    reference = models.CharField(max_length=50)
    objet = models.CharField(max_length=255)
    # Demande d'achat d'origine (optionnelle, même app).
    demande = models.ForeignKey(
        'installations.DemandeAchat', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='rfqs')
    date_limite_reponse = models.DateField(null=True, blank=True)
    statut = models.CharField(
        max_length=20, choices=Statut.choices, default=Statut.BROUILLON)
    # YPROC6 — BCF brouillon créé chez le fournisseur dont l'offre a été
    # retenue (adjudication). String-FK, nullable = comportement historique
    # inchangé (aucune adjudication encore faite pour cette RFQ).
    bon_commande = models.ForeignKey(
        'achats.BonCommandeFournisseur', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='installations_rfqs')
    note = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='installations_rfqs_creees')
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Demande de prix (RFQ)'
        verbose_name_plural = 'Demandes de prix (RFQ)'
        ordering = ['-date_creation']
        unique_together = [('company', 'reference')]
        indexes = [
            models.Index(fields=['company', 'statut'],
                         name='idx_rfq_co_statut'),
        ]

    def __str__(self):
        return f'{self.reference} · {self.objet}'


class RFQOffre(models.Model):
    """FG311 — réponse d'un fournisseur à une RFQ : montant HT, délai, validité,
    et le drapeau ``retenue`` (offre choisie). UNE seule offre retenue par RFQ
    (garanti côté serveur). Montants INTERNES."""

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='installations_rfq_offres')
    rfq = models.ForeignKey(
        RFQ, on_delete=models.CASCADE, related_name='offres')
    # Fournisseur consulté (string-FK vers stock). PROTECT inutile : SET_NULL
    # conserve l'historique d'offre même si le fournisseur disparaît.
    fournisseur = models.ForeignKey(
        'stock.Fournisseur', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='installations_rfq_offres')
    # Repli texte quand le fournisseur n'est pas catalogué.
    fournisseur_nom_libre = models.CharField(
        max_length=255, blank=True, null=True)
    montant_ht = models.DecimalField(
        max_digits=12, decimal_places=2, default=0)
    delai_jours = models.PositiveIntegerField(null=True, blank=True)
    validite_jours = models.PositiveIntegerField(null=True, blank=True)
    retenue = models.BooleanField(default=False)
    note = models.TextField(blank=True, null=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Offre RFQ'
        verbose_name_plural = 'Offres RFQ'
        ordering = ['montant_ht', 'id']
        indexes = [
            models.Index(fields=['company', 'rfq'],
                         name='idx_rfqo_co_rfq'),
        ]

    def __str__(self):
        nom = self.fournisseur_nom_libre or self.fournisseur_id
        return f'{nom} · {self.montant_ht}'


class RFQConsultation(models.Model):
    """XPUR20/21 — un fournisseur CONSULTÉ pour une RFQ (invité à répondre),
    distinct de ``RFQOffre`` (créée seulement quand il répond). Porte le jeton
    public unique par (RFQ, fournisseur) utilisé par la page de réponse SANS
    LOGIN (XPUR21) et la traçabilité d'envoi email/WhatsApp (XPUR20).

    Un fournisseur SANS email ni téléphone catalogué peut quand même être
    consulté (les boutons d'envoi sont grisés côté frontend) — la relance ne
    cible que les non-répondants (``a_repondu=False``) avant
    ``rfq.date_limite_reponse``. Additif & multi-tenant : société posée côté
    serveur, jamais depuis le corps de la requête."""

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='installations_rfq_consultations')
    rfq = models.ForeignKey(
        RFQ, on_delete=models.CASCADE, related_name='consultations')
    # Fournisseur consulté (string-FK vers stock, jamais d'import de modèle).
    fournisseur = models.ForeignKey(
        'stock.Fournisseur', on_delete=models.CASCADE,
        related_name='installations_rfq_consultations')
    token = models.CharField(
        max_length=64, unique=True, default=_default_rfq_token,
        editable=False)
    revoque = models.BooleanField(default=False)
    # Traçabilité d'envoi PAR CANAL — jamais un envoi automatique WhatsApp
    # (manuel-first, cohérent avec la politique existante) : on trace
    # seulement que le lien a été OUVERT/COPIÉ pour le brouillon wa.me.
    email_envoye_le = models.DateTimeField(null=True, blank=True)
    whatsapp_envoye_le = models.DateTimeField(null=True, blank=True)
    derniere_relance_le = models.DateTimeField(null=True, blank=True)
    nb_relances = models.PositiveIntegerField(default=0)
    # Offre soumise par ce fournisseur (posée quand il répond, XPUR21).
    offre = models.ForeignKey(
        RFQOffre, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='consultation_source')
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Consultation RFQ'
        verbose_name_plural = 'Consultations RFQ'
        ordering = ['-date_creation']
        unique_together = [('rfq', 'fournisseur')]
        indexes = [
            models.Index(fields=['company', 'rfq'],
                         name='idx_rfqc_co_rfq'),
            models.Index(fields=['token'], name='idx_rfqc_token'),
        ]

    def __str__(self):
        return f'RFQ#{self.rfq_id} · fournisseur#{self.fournisseur_id}'

    @property
    def a_repondu(self):
        return self.offre_id is not None

    def expire(self):
        """XPUR21 — vrai si la date limite de réponse de la RFQ est dépassée."""
        from django.utils import timezone
        limite = self.rfq.date_limite_reponse
        if limite is None:
            return False
        return timezone.localdate() > limite

    @property
    def is_valid(self):
        return not self.revoque and not self.expire()
