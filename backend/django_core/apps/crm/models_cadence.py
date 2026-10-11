"""Modèles crm de la cadence de suivi sortis de ``models.py`` (SPL93).

Move only : ``RelanceEtape``, ``GesteRelanceAppareil``, ``MessageTemplate`` et
``PeriodeAbsence`` — corps de classes inchangés, même ``app_label`` (``crm``),
mêmes ``db_table`` : aucune migration. ``apps.crm.models`` les ré-exporte dans
son UNIQUE bloc de ré-export, TOUT EN BAS du fichier (enregistrement Django,
migrations, ``from apps.crm.models import …`` de tout le dépôt).

Règle d'architecture (SPL91) : ce module n'importe depuis ``.models`` que des
noms définis AU-DESSUS du bloc de ré-export — ``RelanceEtape`` lit ``Lead``
(FK) et ``LeadActivity.OUTCOMES`` (choices) AU CHARGEMENT (son ``Canal`` est sa
classe imbriquée, pas ``crm.Canal``), ce qui
n'est valide que parce que le ré-export est le DERNIER bloc de models.py — et
n'est JAMAIS importé avant ``apps.crm.models``.
"""
from django.conf import settings
from django.db import models

from core.models import TenantModel

from .models import Lead, LeadActivity


# ── RELANCE FOUNDATION — cadence de relance structurée par lead ──────────────
#
# Distincte du rappel UNIQUE piloté par ``Lead.relance_date``
# (``services.sync_relance_activity``, garde « un seul système de rappel ») :
# ``RelanceEtape`` matérialise un PLAN à plusieurs touches (ex. J+2/J+5/J+10/
# J+20/J+35, gabarit ``parametres.CadenceRelanceEtape``) sur UN lead donné,
# chaque étape portant son propre canal suggéré et son propre statut. Aucun
# envoi automatique (WhatsApp/email) n'est jamais déclenché depuis ce modèle —
# ce sont des RAPPELS VISUELS pour le commercial, jamais un message sortant.
#
# Intégration délibérée avec l'existant plutôt qu'un second système
# concurrent : ``crm.services.marquer_etape_relance`` fait AVANCER
# ``Lead.relance_date`` vers la prochaine étape ``a_faire`` (et retombe donc
# sur l'activité ``records.Activity`` déjà gérée par
# ``sync_relance_activity``) — le Calendrier/« Ma file » continuent de
# refléter la PROCHAINE échéance de la cadence sans dupliquer de rappel.
class RelanceEtape(TenantModel):
    """Une étape (touche) d'un plan de relance structuré, sur UN lead."""

    class Canal(models.TextChoices):
        APPEL = 'appel', 'Appel'
        WHATSAPP = 'whatsapp', 'WhatsApp'
        EMAIL = 'email', 'E-mail'
        VISITE = 'visite', 'Visite'

    class Statut(models.TextChoices):
        A_FAIRE = 'a_faire', 'À faire'
        FAIT = 'fait', 'Fait'
        # CKP1 — SAUTÉE est EXCLUSIVEMENT l'action HUMAINE « sauter » : un
        # commercial a décidé de passer cette touche, et son nom reste dessus.
        SAUTEE = 'sautee', 'Sautée'
        # CKP1 (fondateur 2026-09-10 : « plus aucun saut automatique affiché
        # comme un saut humain ») — la touche que LE MOTEUR a retirée du plan
        # parce que la cadence n'a plus lieu d'être (client joint, lead signé,
        # devis accepté, reprise d'un plan rétrodaté…). ``traite_par`` reste
        # NULL — le moteur n'est pas un humain ; le motif vit dans ``note``.
        # Sans ce statut, une cadence ARRÊTÉE parce que le client a répondu se
        # comptait comme neuf « manquements » dans les KPI d'adhérence.
        ANNULEE = 'annulee', 'Annulée (moteur)'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,  # on_delete: purge tenant
        related_name='relance_etapes')
    lead = models.ForeignKey(
        Lead, on_delete=models.CASCADE,  # on_delete: étape sans objet si le lead est supprimé
        related_name='relance_etapes')
    # MRY5 — à quelle CADENCE cette touche appartient (`contact`,
    # `apres_devis`, `reveil`, `generique`). Un lead peut porter deux plans
    # simultanément (sa prise de contact et le suivi d'un devis) : sans ce
    # champ, l'idempotence de l'initialisation les confondait en un seul.
    cadence = models.CharField(
        max_length=20, default='contact', verbose_name='Cadence')
    ordre = models.PositiveIntegerField(default=0)
    due_date = models.DateField()
    # MRY5 — échéance à la MINUTE. `due_date` reste NOT NULL et vaut la date
    # LOCALE de `due_at` : les filtres `scope=today|overdue|all` gardent leur
    # grain JOUR (aucun changement de contrat), `due_at` sert au tri et à
    # l'affichage « à HH:MM ». Les lignes créées avant MRY5 gardent NULL —
    # c'est la vérité, elles n'ont jamais porté d'heure.
    due_at = models.DateTimeField(
        null=True, blank=True, db_index=True, verbose_name='Échéance (heure)')
    canal = models.CharField(max_length=20, choices=Canal.choices)
    libelle = models.CharField(max_length=150, blank=True, default='')
    # Clé du gabarit de message à rendre pour cette touche (MRY12). Texte
    # libre, comme côté gabarit : aucune dépendance d'import vers parametres.
    template_cle = models.CharField(
        max_length=40, blank=True, default='',
        verbose_name='Clé du gabarit de message')
    # Devis suivi par cette touche (cadence `apres_devis`). FK EN CHAÎNE :
    # crm ne connaît jamais les modèles de ventes (frontière M3).
    devis = models.ForeignKey(
        'ventes.Devis',
        on_delete=models.SET_NULL,  # on_delete: étape orpheline si le devis disparaît
        null=True, blank=True, related_name='relance_etapes',
        verbose_name='Devis suivi')
    # CKP2 — l'ANCRE de la cadence : l'instant de départ depuis lequel toutes
    # les échéances du gabarit sont datées. Depuis que la cadence est RÉACTIVE
    # (une seule touche matérialisée à la fois, la suivante naît de l'issue),
    # il faut pouvoir REDATER la touche J+N des mois plus tard exactement
    # comme l'aperçu l'avait annoncée. La déduire de la première touche
    # existante dériverait (l'origine du jour même est recalée sur la fenêtre
    # d'ouverture, le départ non) : elle est donc ÉCRITE. NULL sur les lignes
    # d'avant CKP2 — c'est la vérité, et le repli lit alors la plus ancienne
    # échéance de la cadence.
    cadence_depart = models.DateTimeField(
        null=True, blank=True, verbose_name='Départ de la cadence')
    statut = models.CharField(
        max_length=10, choices=Statut.choices, default=Statut.A_FAIRE)
    note = models.TextField(blank=True, default='')
    # CAD118 (audit L3 du 21/09/2026) — L'ISSUE DE LA TOUCHE, SUR LA TOUCHE.
    # On mesurait si les touches étaient cochées, jamais si elles joignaient
    # quelqu'un : l'issue ne vivait que sur la ligne de chatter, et le seul
    # rapprochement possible était une fenêtre de DEUX MINUTES entre les deux
    # horodatages — un bricolage qui casse en silence dès qu'un traitement
    # ralentit. Écrite au MÊME instant que la ligne d'historique par
    # ``services.marquer_etape_relance``.
    #
    # Additive et sans nouvelle valeur d'énumération : les choix sont ceux de
    # ``LeadActivity.OUTCOMES``, qui reste la source de vérité du chatter.
    # Vide = touche close sans issue saisie (ou ligne d'avant CAD118) — c'est
    # la vérité, jamais un « non joint » supposé.
    outcome = models.CharField(
        max_length=20, blank=True, default='',
        choices=LeadActivity.OUTCOMES,
        verbose_name="Issue de la touche",
        help_text="Ce que la touche a donné : le client a-t-il été joint ?",
    )
    # Traçabilité de la clôture (fait/sautée) — jamais silencieuse.
    traite_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='relance_etapes_traitees')
    traite_le = models.DateTimeField(null=True, blank=True)
    # PARAM-CADENCE (décision fondateur du 25/09/2026) — la clé STABLE du
    # barreau paramétré dont le moteur a tiré cette étape (cadences
    # « Après l'appel (avant devis) » et « Visite technique » de Paramètres,
    # ``parametres.CadenceRelanceEtape.cle``). C'est par elle, jamais par le
    # libellé, que le moteur reconnaît désormais l'étape : une société peut
    # renommer « Préparer et envoyer le devis ». VIDE pour un barreau du
    # protocole, et pour les étapes posées avant la clé — celles-là restent
    # reconnues par leur libellé par défaut (``crm.cadence_config.est_etape``),
    # sans migration de données.
    cle = models.CharField(
        max_length=40, blank=True, default='', verbose_name='Clé moteur')
    # COCKPIT-CONTRÔLE (fondateur, 30/09/2026 : « voir si la commerciale a
    # fait tout ce qu'elle devait ») — les DEUX traces qui manquaient pour
    # qu'un report ne fasse plus disparaître un retard en silence.
    # ``reporter_prochaine_touche`` ÉCRASE ``due_at``/``due_date`` : sans
    # elles, une étape repoussée trois fois se lisait comme une étape du jour.
    #
    # * ``due_initial_at`` — l'échéance d'ORIGINE, posée à la création
    #   (``save`` ci-dessous ; les ``bulk_create`` la posent eux-mêmes). Un
    #   report HUMAIN ne la réécrit jamais ; un déplacement décidé par le
    #   MOTEUR (relances décalées autour d'une visite, recalage d'un débrief,
    #   filet déplacé) la déplace avec l'échéance, du même écart. NULL sur une
    #   ligne qui n'a jamais porté d'heure (d'avant MRY5) — c'est la vérité.
    # * ``nb_reports`` — combien de fois l'échéance de CETTE étape a été
    #   repoussée par un geste HUMAIN (« Reporter », « Mettre en veille »,
    #   « À rappeler le… » / « Plus tard » qui garde l'étape, rappel demandé
    #   au journal d'appel). Les déplacements du moteur ne comptent pas.
    #
    # Des FAITS montrés tels quels par le bloc « Contrôle du suivi »
    # (``controle_suivi.py``), jamais une note.
    due_initial_at = models.DateTimeField(
        null=True, blank=True, verbose_name="Échéance d'origine")
    nb_reports = models.PositiveSmallIntegerField(
        default=0, verbose_name='Reports humains')

    class Meta:
        verbose_name = 'Étape de relance'
        verbose_name_plural = 'Étapes de relance'
        ordering = ['ordre', 'due_date']
        indexes = [
            models.Index(fields=['company', 'statut', 'due_date'],
                         name='crm_relanceetape_due_idx'),
            # MRY5 — la frise de la fiche lead et l'idempotence par cadence
            # interrogent toutes deux (société, lead, cadence, statut).
            models.Index(fields=['company', 'lead', 'cadence', 'statut'],
                         name='crm_relance_lead_cad_idx'),
        ]
        constraints = [
            # ACRM55 — filet STRUCTUREL sous le verrou ACRM35 : UNE seule
            # touche À FAIRE par barreau (lead, cadence, ordre, devis) des
            # cadences à barreaux ; filets/gestes (``cle`` posée) et cadence
            # générique hors contrainte. ``devis`` vide compte comme une
            # valeur (NULLS NOT DISTINCT, Postgres ≥ 15).
            models.UniqueConstraint(
                fields=['lead', 'cadence', 'ordre', 'devis'],
                condition=models.Q(
                    statut='a_faire', cle='',
                    cadence__in=('contact', 'apres_devis', 'reveil')),
                nulls_distinct=False,
                name='crm_relance_une_ouverte_par_barreau'),
        ]

    def __str__(self):
        return (f'{self.lead_id} — {self.cadence} #{self.ordre} '
                f'({self.get_statut_display()})')

    def save(self, *args, **kwargs):
        # COCKPIT-CONTRÔLE — À LA CRÉATION, l'échéance d'origine est
        # l'échéance posée : un seul endroit pour tous les ``create()`` du
        # moteur, de la reprise et des tests. Un ``bulk_create`` ne passe pas
        # par ici : le seul du moteur (``services.initialiser_plan_relance``)
        # la pose lui-même.
        if (self._state.adding and self.due_initial_at is None
                and self.due_at is not None):
            self.due_initial_at = self.due_at
        super().save(*args, **kwargs)


class GesteRelanceAppareil(TenantModel):
    """CAD178 (audit CAD86, 24/09/2026) — compteur des GESTES CLÉS de la
    cadence de relance (Fait, Reporter, Appeler, WhatsApp), PAR FAMILLE
    D'APPAREIL. Avant : la seule mesure d'usage (CAD87/CAD100) ne distinguait
    aucun appareil — aucune des quatre écrans de cadence n'avait la moindre
    trace d'usage mobile.

    Compteur JOURNALIER agrégé (jamais un événement par clic conservé
    indéfiniment, jamais l'IP ni le User-Agent brut) : la famille d'appareil
    est une classification GROSSIÈRE dérivée du User-Agent HTTP de la requête
    (``mesure_cadence.famille_appareil``), jamais stockée telle quelle. Écrit
    en BEST-EFFORT depuis les vues (``mesure_cadence.enregistrer_geste_appareil``) —
    un échec de comptage n'a jamais fait échouer le geste métier qu'il mesure.
    """

    class Geste(models.TextChoices):
        FAIT = 'fait', 'Fait'
        REPORTER = 'reporter', 'Reporter'
        APPELER = 'appeler', 'Appeler'
        WHATSAPP = 'whatsapp', 'WhatsApp'

    class FamilleAppareil(models.TextChoices):
        MOBILE = 'mobile', 'Mobile'
        TABLETTE = 'tablette', 'Tablette'
        ORDINATEUR = 'ordinateur', 'Ordinateur'
        INCONNU = 'inconnu', 'Inconnu'

    geste = models.CharField(max_length=20, choices=Geste.choices)
    famille_appareil = models.CharField(
        max_length=20, choices=FamilleAppareil.choices)
    jour = models.DateField(verbose_name='Jour (Casablanca)')
    total = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = 'Geste de relance par appareil'
        verbose_name_plural = 'Gestes de relance par appareil'
        ordering = ['-jour', 'geste', 'famille_appareil']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'geste', 'famille_appareil', 'jour'],
                name='crm_geste_appareil_unique'),
        ]
        indexes = [
            models.Index(fields=['company', 'jour'],
                         name='crm_geste_appareil_jour_idx'),
        ]

    def __str__(self):
        return (f'{self.company_id}: {self.geste}/{self.famille_appareil} '
                f'{self.jour} = {self.total}')


class MessageTemplate(models.Model):
    """FG36 — Modèles de messages WhatsApp/SMS réutilisables en CRM.

    Chaque modèle porte un nom, une langue, un corps avec des variables
    substituables ({prenom}, {ville}, {lien}) et un flag d'archivage.
    Scoped par société ; éditable uniquement par l'admin.
    """

    class Langue(models.TextChoices):
        FR = 'fr', 'Français'
        DARIJA = 'darija', 'Darija'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,  # on_delete: donnée propre à la société — supprimée avec elle (multi-tenant)
        null=True,
        blank=True,
        related_name='crm_message_templates',
    )
    nom = models.CharField(max_length=150, verbose_name='Nom du modèle')
    langue = models.CharField(
        max_length=10, choices=Langue.choices, default=Langue.FR,
        verbose_name='Langue')
    # Variables disponibles : {prenom}, {ville}, {lien} (lien devis)
    corps = models.TextField(verbose_name='Corps du message')
    archived = models.BooleanField(default=False, verbose_name='Archivé')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='+',
    )
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['nom']
        unique_together = [('company', 'nom')]
        verbose_name = 'Modèle de message'
        verbose_name_plural = 'Modèles de messages'

    def __str__(self):
        return f"{self.nom} ({self.get_langue_display()})"

    def render(self, prenom='', ville='', lien='', lien_rdv='') -> str:
        """Substitue les variables dans le corps du modèle.

        XSAL17 — ``lien_rdv`` (lien de réservation de visite) est résolu par
        l'APPELANT (``services.resoudre_lien_rdv`` — nécessite le lead pour
        créer/retrouver le ``BookingLink``) ; ce modèle reste une simple
        substitution de chaîne. Un template SANS ``{lien_rdv}`` est rendu
        strictement inchangé (aucun paramètre supplémentaire n'y change rien)."""
        return (self.corps
                .replace('{prenom}', prenom or '')
                .replace('{ville}', ville or '')
                .replace('{lien}', lien or '')
                .replace('{lien_rdv}', lien_rdv or ''))


# ── CAD-B ── CAD35 — PÉRIODE D'ABSENCE DÉCLARÉE ──────────────────────────────
#
# Rien ne suspendait les cadences quand la personne qui les tient est absente.
# En régime RÉACTIF les touches naissent quand même, elles échoient pendant le
# congé, et `selectors._a_lheure` comptait un manquement pour chacune : le
# cockpit accusait quelqu'un d'être en retard pendant ses vacances.
#
# VERSION MINIMALE, SANS NOUVEAU MOTEUR (21/09/2026) : déclarer la période
# suffit à (a) ne plus imputer de retard d'adhérence sur ses jours et (b) la
# rendre visible dans le cockpit. AUCUNE touche n'est supprimée, aucune n'est
# avancée, aucune n'est décalée : le décalage reste un geste humain, au cas par
# cas (« Mettre en veille »). Le digest du matin continue de partir — une
# absence neutralise une MESURE, elle n'éteint pas le suivi.
class PeriodeAbsence(TenantModel):
    """Une période d'absence déclarée (congé, arrêt, formation) — d'une
    personne, ou de la société entière quand ``utilisateur`` est vide."""

    class Motif(models.TextChoices):
        CONGE = 'conge', 'Congé'
        ARRET = 'arret', 'Arrêt maladie'
        FORMATION = 'formation', 'Formation'
        AUTRE = 'autre', 'Autre'

    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,  # on_delete: absence sans objet sans la personne
        null=True, blank=True, related_name='crm_absences',
        verbose_name='Personne absente',
        help_text='Qui est absent ? Laisser vide pour une fermeture qui '
                  'concerne toute la société.')
    date_debut = models.DateField(
        verbose_name='Premier jour',
        help_text='À partir de quel jour, ce jour-là compris ?')
    date_fin = models.DateField(
        verbose_name='Dernier jour',
        help_text='Jusqu’à quel jour, ce jour-là compris ?')
    motif = models.CharField(
        max_length=10, choices=Motif.choices, default=Motif.CONGE,
        verbose_name='Motif',
        help_text='Congé, arrêt maladie, formation, ou autre ?')
    # Remède (1) du round 2 : la COUVERTURE par défaut — quelqu'un reprend les
    # dossiers. Le champ NOMME cette personne ; la reprise elle-même reste un
    # geste humain (aucune réassignation automatique n'est posée ici).
    remplacant = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,  # on_delete: la période survit au départ du remplaçant
        null=True, blank=True, related_name='crm_absences_couvertes',
        verbose_name='Reprise des dossiers',
        help_text='Qui reprend les dossiers pendant cette absence ?')
    note = models.TextField(
        blank=True, default='', verbose_name='Note',
        help_text='Quelque chose à savoir pour la reprise ?')

    class Meta:
        verbose_name = 'Période d’absence'
        verbose_name_plural = 'Périodes d’absence'
        ordering = ['-date_debut', 'utilisateur_id']
        indexes = [
            models.Index(fields=['company', 'date_debut', 'date_fin'],
                         name='crm_absence_periode_idx'),
        ]

    def clean(self):
        from django.core.exceptions import ValidationError
        if (self.date_debut and self.date_fin
                and self.date_fin < self.date_debut):
            # Règle fondateur du 08/09 : l'erreur désigne LE champ fautif et
            # dit quoi corriger, jamais un refus générique.
            raise ValidationError({
                'date_fin': 'Le dernier jour d’absence ne peut pas précéder '
                            'le premier jour. Corrigez « Dernier jour ».'})

    def couvre(self, jour):
        """``jour`` (date locale) tombe-t-il dans cette absence, bornes
        comprises ?"""
        if jour is None or self.date_debut is None or self.date_fin is None:
            return False
        return self.date_debut <= jour <= self.date_fin

    def __str__(self):
        qui = self.utilisateur_id or 'société'
        return f'{qui} — {self.date_debut} → {self.date_fin}'
