"""XPLT21 — Softphone VoIP intégré (SIP/WebRTC, gated).

FG208 livre déjà le click-to-call `tel:` + un journal d'appels MANUEL ; ce
module ajoute le VRAI softphone in-app : interface fournisseur SWAPPABLE
(pattern `apps.monitoring.providers` — NoOp par défaut, AUCUNE dépendance ni
comportement nouveau tant qu'une société n'a rien configuré) + le journal
d'appel automatique (durée/issue posés à la clôture).

Company-scopée (`core.models.TenantModel`), additive. Aucun secret SIP en
clair au-delà d'un JSONField `identifiants` — même motif que
`monitoring.MonitoringConfig.credentials` (crédentials PAR société/PAR
utilisateur, jamais lues du corps de requête ailleurs que dans ce module).
"""
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db import models

from core.models import TenantModel


class VoipParametres(TenantModel):
    """Configuration VoIP D'UNE société — une ligne par société (singleton).

    `actif=False` (défaut) = comportement d'aujourd'hui inchangé : AUCUN
    bouton d'appel, AUCUN appel possible (voir `services.est_actif`). Choisir
    un `fournisseur` sans le configurer (`serveur_sip` vide) reste un no-op
    sûr — jamais d'appel réseau sans identifiants.
    """
    class Fournisseur(models.TextChoices):
        NOOP = 'noop', 'Aucun (softphone désactivé)'
        SIP_GENERIQUE = 'sip_generique', 'SIP/WebRTC générique'

    company = models.OneToOneField(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='voip_parametres')
    fournisseur = models.CharField(
        max_length=20, choices=Fournisseur.choices, default=Fournisseur.NOOP)
    actif = models.BooleanField(default=False, verbose_name='Actif')
    serveur_sip = models.CharField(max_length=255, blank=True, default='')
    # Configuration additionnelle libre (identifiants globaux du serveur SIP,
    # jamais des identifiants PAR utilisateur — voir VoipIdentifiantUtilisateur
    # ci-dessous). Vide par défaut.
    configuration = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = 'Paramètres VoIP'
        verbose_name_plural = 'Paramètres VoIP'

    def __str__(self):
        return f'VoIP {self.company_id} ({self.fournisseur})'

    @property
    def est_configure(self):
        """Actif ET un serveur SIP renseigné (fournisseur ≠ noop) — sinon le
        softphone reste inerte quelle que soit la valeur de `actif`."""
        return bool(
            self.actif and self.fournisseur != self.Fournisseur.NOOP
            and self.serveur_sip)


class VoipIdentifiantUtilisateur(TenantModel):
    """Identifiants SIP PAR utilisateur (Paramètres) — une ligne par
    (société, utilisateur). Jamais partagés entre utilisateurs, jamais lus du
    corps de requête pour un autre utilisateur que soi-même (voir vue)."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='voip_identifiants')
    utilisateur = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='voip_identifiant')
    identifiant_sip = models.CharField(max_length=120, blank=True, default='')
    # Secret SIP — même motif que `monitoring.MonitoringConfig.credentials`
    # (JSON opaque, jamais exposé en lecture au-delà du propriétaire/admin).
    secret = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = 'Identifiant VoIP utilisateur'
        verbose_name_plural = 'Identifiants VoIP utilisateur'
        indexes = [
            models.Index(fields=['company', 'utilisateur']),
        ]

    def __str__(self):
        return f'{self.utilisateur_id} @ {self.company_id}'


class Appel(TenantModel):
    """Un appel VoIP (sortant ou entrant), journalisé automatiquement.

    La cible métier (lead/client résolu depuis le numéro) est référencée en
    GÉNÉRIQUE (`content_type`/`object_id`, framework Django — jamais un
    import des `models` d'une app métier) : `apps.crm` est lu EXCLUSIVEMENT
    via ses sélecteurs/services publics (`find_client_by_phone`,
    `find_lead_by_phone` — voir `services.py`), jamais `apps.crm.models`.
    """
    class Direction(models.TextChoices):
        SORTANT = 'sortant', 'Sortant'
        ENTRANT = 'entrant', 'Entrant'

    class Statut(models.TextChoices):
        INITIE = 'initie', 'Initié'
        SONNANT = 'sonnant', 'Sonnant'
        EN_COURS = 'en_cours', 'En cours'
        TERMINE = 'termine', 'Terminé'
        MANQUE = 'manque', 'Manqué'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='voip_appels')
    direction = models.CharField(max_length=10, choices=Direction.choices)
    numero = models.CharField(max_length=40, verbose_name='Numéro (brut)')
    numero_normalise = models.CharField(max_length=40, blank=True, default='')

    # Cible résolue (lead/client) — nullable : un numéro sans correspondance
    # reste un appel journalisé, juste sans fiche à ouvrir.
    content_type = models.ForeignKey(
        ContentType, on_delete=models.SET_NULL, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)

    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='voip_appels')

    statut = models.CharField(
        max_length=10, choices=Statut.choices, default=Statut.INITIE)
    # Issue libre posée à la clôture (répondu / sans réponse / messagerie…) —
    # texte libre plutôt qu'une énumération fermée, comme les autres modules
    # « issue »/notes de ce dépôt.
    issue = models.CharField(max_length=100, blank=True, default='')

    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    duree_secondes = models.PositiveIntegerField(null=True, blank=True)

    fournisseur = models.CharField(max_length=20, blank=True, default='')
    external_call_id = models.CharField(max_length=120, blank=True, default='')

    class Meta:
        verbose_name = 'Appel VoIP'
        verbose_name_plural = 'Appels VoIP'
        ordering = ['-started_at', '-id']
        indexes = [
            models.Index(fields=['company', 'started_at']),
            models.Index(fields=['company', 'content_type', 'object_id']),
        ]

    def __str__(self):
        return f'{self.get_direction_display()} {self.numero} ({self.statut})'
