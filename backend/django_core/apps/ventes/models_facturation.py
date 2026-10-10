"""Modèles d'argent de ventes (BC, notes de débit, retenues, promesses,
relances, liens de paiement, remises d'encaissement, mandats, livraisons de
BC) — déplacés tels quels de ``models.py`` par SPL149 (move only).

Même app_label (``ventes``), mêmes ``db_table`` : aucune migration. Ré-exportés
en fin de ``models.py`` (découverte Django + ``from apps.ventes.models import``).
Ce module importe ``.models`` en tête : valide parce que ``models.py`` ne
l'importe qu'en FIN, une fois ``Devis``/``LigneDevis`` définis.
"""
import datetime

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.functional import cached_property

from core.models import TenantModel

from .models import (
    Devis,
    LigneDevis,
    _default_payment_expiry,
    _default_payment_token,
)


class FactureActivity(models.Model):
    """Chatter d'une facture — même patron que DevisActivity.

    Trace les événements comptables (avoir créé, paiement encaissé) + notes
    éventuelles. Utilisateur et société posés côté serveur, jamais lus du
    corps de la requête."""
    class Kind(models.TextChoices):
        CREATION = 'creation', 'Création'
        MODIFICATION = 'modification', 'Modification'
        NOTE = 'note', 'Note'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,  # on_delete: purge tenant
        null=True, blank=True, related_name='facture_activities')
    facture = models.ForeignKey(
        'facturation.Facture', on_delete=models.CASCADE,  # on_delete: chatter sans objet si facture supprimée
        related_name='activites')
    kind = models.CharField(max_length=15, choices=Kind.choices)
    field = models.CharField(max_length=100, blank=True, null=True)
    field_label = models.CharField(max_length=150, blank=True, null=True)
    old_value = models.TextField(blank=True, null=True)
    new_value = models.TextField(blank=True, null=True)
    body = models.TextField(blank=True, null=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='facture_activities')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Activité facture'
        verbose_name_plural = 'Activités facture'
        ordering = ['-created_at']
        indexes = [models.Index(fields=['facture', '-created_at'],
                                name='ventes_factact_idx')]

    def __str__(self):
        return f"{self.facture_id} {self.kind} {self.field or ''}".strip()


class ProformaDocument(models.Model):
    """XFAC10 — trace d'une facture PRO-FORMA générée pour un devis.

    Document NON comptabilisé (aucun impact statuts/GL/numérotation des
    vraies factures) : uniquement un rendu PDF filigrané avec sa PROPRE
    séquence ``PF-`` (via ``utils/references.py``), indépendante de celle des
    factures réelles. Ce modèle sert UNIQUEMENT à garantir cette séquence
    sans collision (même mécanisme highest-used+1 que Facture/Devis) et à
    tracer les émissions dans le chatter du devis — il ne devient JAMAIS une
    facture réelle (la conversion reste `generer-facture`, inchangée)."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,  # on_delete: purge tenant
        null=True, blank=True, related_name='proforma_documents')
    reference = models.CharField(max_length=50)
    devis = models.ForeignKey(
        'Devis', on_delete=models.CASCADE,  # on_delete: proforma sans objet si devis supprimé
        related_name='proformas')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name='proformas_creees')
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Facture pro-forma'
        verbose_name_plural = 'Factures pro-forma'
        ordering = ['-date_creation']
        unique_together = [('company', 'reference')]

    def __str__(self):
        return self.reference


class FactureSource(models.Model):
    """XFAC11 — table de liaison « facture consolidée ↔ document source ».

    Une facture consolidée (`POST factures/consolider/`) regroupe PLUSIEURS
    devis/BC déjà acceptés d'un même client en UNE facture ; ``Facture.devis``
    reste nullable/unique (chaîne historique inchangée) alors que CETTE table
    trace CHAQUE document source consolidé (traçabilité multi-source), avec le
    sous-total HT de ce document dans la facture regroupée (sert au sous-titre
    « Devis DV-… » sur le PDF)."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,  # on_delete: purge tenant
        null=True, blank=True, related_name='facture_sources')
    facture = models.ForeignKey(
        'facturation.Facture', on_delete=models.CASCADE,  # on_delete: source sans objet si facture supprimée
        related_name='sources')
    devis = models.ForeignKey(
        'Devis', on_delete=models.PROTECT, related_name='factures_sources')
    sous_total_ht = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        verbose_name = 'Source de facture consolidée'
        verbose_name_plural = 'Sources de facture consolidée'
        unique_together = [('facture', 'devis')]

    def __str__(self):
        return f'{self.facture_id} ← {self.devis.reference}'


# ── CAD122 (audit L3 cadence, 21/09/2026) — démarchage à domicile ──────────
#: Délai pendant lequel AUCUN acompte ne peut être encaissé sur une commande
#: signée au domicile du client. Source : loi 31-08, art. 49 et 50 (texte
#: ONSSA). Ce n'est pas un réglage société : c'est la loi.
DELAI_RETRACTATION_DOMICILE_JOURS = 7


class AcompteAvantDelaiLegal(Exception):
    """CAD122 — encaissement d'acompte refusé : le délai légal court encore.

    Levée par ``BonCommande.verifier_encaissement_acompte``. Le message dit la
    DATE à partir de laquelle l'encaissement redevient possible — jamais un
    refus générique (règle fondateur du 08/09/2026)."""


class BonCommande(models.Model):
    class Statut(models.TextChoices):
        EN_ATTENTE = 'en_attente', 'En attente'
        CONFIRME = 'confirme', 'Confirmé'
        LIVRE = 'livre', 'Livré'
        ANNULE = 'annule', 'Annulé'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,  # on_delete: purge tenant
        null=True,
        blank=True,
        related_name='bons_commande',
    )
    reference = models.CharField(max_length=50)
    devis = models.OneToOneField(
        Devis,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bon_commande',
    )
    # U12 — lien DIRECT vers le lead d'origine, snapshoté à la création depuis
    # le devis source (devis.lead). Additif/optionnel : un BC sans lead reste
    # valide, et on ne perd jamais le lien si le devis est supprimé (SET_NULL).
    # Permet « tous les documents d'un lead » sans traverser le devis (qui peut
    # passer à NULL). related_name distinct (`bons_commande_directs`) pour ne pas
    # entrer en conflit avec un futur reverse `bons_commande` côté Lead.
    lead = models.ForeignKey(
        'crm.Lead',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bons_commande_directs',
    )
    client = models.ForeignKey(
        'crm.Client',
        on_delete=models.PROTECT,
        related_name='bons_commande',
    )
    statut = models.CharField(
        max_length=20,
        choices=Statut.choices,
        default=Statut.EN_ATTENTE,
    )
    date_creation = models.DateTimeField(auto_now_add=True)
    date_livraison_prevue = models.DateField(null=True, blank=True)
    note = models.TextField(blank=True, null=True)
    # ── FG51 — Preuve de livraison (PV / signature) ───────────────────────────
    # Capturée au moment de « marquer livré » : nom du signataire, note libre,
    # horodatage et, optionnellement, une pièce jointe (PV/bon signé) stockée
    # dans MinIO via records.storage. Tout est additif et optionnel : un BC
    # livré sans preuve reste valide (la facturation n'est jamais bloquée), mais
    # `generer-facture`/`creer-facture` renvoie un avertissement doux quand
    # aucune preuve n'existe pour la tranche matériel. Forme du JSON :
    # {signataire, note, file_key, filename, signed_at}.
    pv_livraison = models.JSONField(null=True, blank=True)
    date_livraison_reelle = models.DateField(null=True, blank=True)
    # ── CAD122 (décision fondateur du 21/09/2026) — DÉMARCHAGE À DOMICILE ────
    # La visite technique se passe AU DOMICILE, après le devis, et le bon de
    # commande s'y signe PARFOIS. La loi 31-08 (texte ONSSA) définit le
    # démarchage à l'art. 45 comme la proposition d'achat au domicile « même à
    # sa demande » ; l'art. 46 liste trois exclusions, dont aucune ne couvre le
    # solaire. Le dépôt ne connaissait la rétractation qu'à l'art. 32 (vente à
    # DISTANCE). Ce marqueur — et LUI SEUL — déclenche le formalisme :
    # formulaire détachable de rétractation annexé au document, mentions de
    # l'art. 48, aucun encaissement d'acompte avant 7 jours (art. 49 et 50) et
    # signature manuscrite DATÉE de la main du client (art. 47 al. 2).
    # Faux par défaut : une signature à distance ou au bureau reste régie par
    # l'art. 32 et ne change en RIEN.
    signe_au_domicile = models.BooleanField(
        default=False,
        verbose_name='Signé au domicile du client',
        help_text="Ce bon de commande a-t-il été signé chez le client "
                  "(démarchage, loi 31-08 art. 45) ?",
    )
    date_signature_domicile = models.DateField(
        null=True, blank=True,
        verbose_name='Date écrite par le client',
        help_text="Quelle date le client a-t-il écrite de sa main à côté de "
                  "sa signature (loi 31-08 art. 47 al. 2) ?",
    )

    @property
    def has_proof_of_delivery(self):
        """FG51 — vrai si une preuve de livraison (PV/signature) est consignée."""
        pv = self.pv_livraison or {}
        return bool(pv.get('signataire') or pv.get('file_key'))

    # ── CAD122 ── le délai de rétractation du démarchage à domicile ─────────
    @property
    def date_commande_domicile(self):
        """La date qui fait courir le délai : celle ÉCRITE PAR LE CLIENT.

        L'art. 47 al. 2 de la loi 31-08 exige une signature manuscrite DATÉE
        de la main du client — c'est cette date qui fait foi. À défaut (elle
        n'a pas été saisie), on retombe sur la date de création du bon, qui ne
        peut qu'être postérieure ou égale : le délai ne se raccourcit jamais
        au détriment du client."""
        if self.date_signature_domicile:
            return self.date_signature_domicile
        return self.date_creation.date() if self.date_creation else None

    @property
    def acompte_encaissable_le(self):
        """Premier jour où l'acompte peut être encaissé, ou ``None``.

        ``None`` pour un bon signé à distance ou au bureau : l'art. 32 s'y
        applique et RIEN ne change. Pour un bon signé au domicile, c'est la
        date de commande + le délai des art. 49 et 50."""
        if not self.signe_au_domicile:
            return None
        depart = self.date_commande_domicile
        if depart is None:
            return None
        return depart + datetime.timedelta(
            days=DELAI_RETRACTATION_DOMICILE_JOURS)

    def verifier_encaissement_acompte(self, a_la_date=None):
        """Lève ``AcompteAvantDelaiLegal`` si l'acompte est encaissé trop tôt.

        Ne fait RIEN pour un bon signé à distance ou au bureau. Le message
        nomme la date à partir de laquelle l'encaissement est possible — une
        erreur qui dit seulement « refusé » n'aide personne à agir."""
        from django.utils import timezone as _tz

        seuil = self.acompte_encaissable_le
        if seuil is None:
            return
        jour = a_la_date or _tz.now().date()
        # L'appelant peut passer un instant ou une date : on compare des
        # JOURS des deux côtés (le délai est en jours, pas en heures).
        if isinstance(jour, datetime.datetime):
            jour = jour.date()
        if jour < seuil:
            raise AcompteAvantDelaiLegal(
                "Acompte non encaissable avant le "
                f"{seuil.strftime('%d/%m/%Y')} : ce bon de commande a été "
                "signé au domicile du client, et la loi 31-08 (art. 49 et "
                f"50) interdit tout encaissement pendant "
                f"{DELAI_RETRACTATION_DOMICILE_JOURS} jours à compter de la "
                "commande.")

    def save(self, *args, **kwargs):
        """U12 — snapshote le lead d'origine depuis le devis source à la création.

        Toute voie de création (action `convertir-bc`, services cross-app…)
        hérite ainsi du lien direct sans avoir à le poser à la main. On ne pose
        le lead que s'il n'est pas déjà fixé (jamais d'écrasement) et qu'un
        devis source le porte — comportement historique strictement inchangé
        pour un BC sans devis ou sans lead."""
        if self.lead_id is None:
            # Résolution INLINE (aucun import de services → préserve le contrat
            # import-linter « modèles de domaine découplés »). Un BC porte son
            # devis directement ; on hérite du lead du devis source s'il existe.
            devis = getattr(self, 'devis', None)
            lead = getattr(devis, 'lead', None) if devis is not None else None
            if lead is not None:
                self.lead = lead
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = 'Bon de Commande'
        verbose_name_plural = 'Bons de Commande'
        ordering = ['-date_creation']
        unique_together = [('company', 'reference')]

    def __str__(self):
        return self.reference

    def refresh_from_db(self, *args, **kwargs):
        # AUD115 — `reliquat_par_ligne` est mémoïsé (cached_property) pour que
        # `est_partiellement_livre` ne rejoue pas la propriété une seconde fois
        # sur chaque ligne de la liste. `livrer_partiel` relit le reliquat
        # APRÈS avoir écrit ses lignes de livraison : la relecture doit voir la
        # base, jamais le cache. On l'invalide donc ici, à la source, plutôt
        # que de compter sur chaque appelant pour y penser.
        self.__dict__.pop('reliquat_par_ligne', None)
        return super().refresh_from_db(*args, **kwargs)

    @cached_property
    def reliquat_par_ligne(self):
        """XSAL12 — quantité restant à livrer par ligne de devis source.

        Un BC sans devis (ou sans livraison partielle) renvoie une liste
        vide — comportement historique inchangé (le statut reste piloté par
        `marquer_livre` seul dans ce cas).

        AUD115 — SEULES LES LIGNES LIVRABLES SONT PARCOURUES. La boucle
        itérait TOUTES les lignes du devis et calculait `ligne.quantite -
        livre` ; or XSAL14 a rendu `LigneDevis.quantite` nullable et le
        sérialiseur neutralise quantité/prix/produit sur une ligne de
        section/note. `None - 0` levait TypeError, et la propriété étant
        exposée SANS garde sur chaque ligne de la liste, un simple intertitre
        « Kit batterie » dans un devis rendait l'écran Bons de commande de
        toute la société inaccessible. On réutilise `compte_dans_totaux`, LE
        prédicat maison déjà employé par `option_lines` et
        `reserver_stock_devis_facture` — jamais un troisième filtre."""
        if self.devis_id is None:
            return []
        cache = getattr(self, '_prefetched_objects_cache', None) or {}
        if 'livraisons' in cache:
            # AUD115 — la liste préfetche `livraisons__lignes` : on somme en
            # mémoire au lieu d'une requête d'agrégat PAR bon de commande.
            # Mêmes chiffres, à l'unité près — seul le nombre d'allers-retours
            # change.
            livre_par_ligne = {}
            for livraison in self.livraisons.all():
                for ligne_livree in livraison.lignes.all():
                    cle = ligne_livree.ligne_devis_id
                    livre_par_ligne[cle] = (
                        (livre_par_ligne.get(cle) or 0)
                        + ligne_livree.quantite_livree)
        else:
            from django.db.models import Sum
            livre_par_ligne = dict(
                LigneLivraisonBC.objects
                .filter(livraison__bon_commande=self)
                .values_list('ligne_devis_id')
                .annotate(total=Sum('quantite_livree'))
            )
        # ERR-QAC-MULTIVILLA-MATERIEL-XN — devis « ×N villas » : N kits (N=1
        # inchangé). AFAC15 — SEUL le panier VENDU (`option_lines`, même panier
        # que la facture et la sortie) est livrable : jamais l'option écartée.
        from .domain.argent import lignes_vendues
        from .multivilla import nombre_proprietes
        n_prop = nombre_proprietes(self.devis)
        out = []
        for ligne in lignes_vendues(self.devis):
            if not ligne.compte_dans_totaux or ligne.quantite is None:
                continue
            livre = livre_par_ligne.get(ligne.id) or 0
            commandee = ligne.quantite * n_prop
            out.append({
                'ligne_devis_id': ligne.id,
                'designation': ligne.designation,
                'quantite_commandee': commandee,
                'quantite_livree': livre,
                'reliquat': commandee - livre,
            })
        return out

    @property
    def est_partiellement_livre(self):
        """XSAL12 — vrai si au moins une livraison partielle existe et qu'il
        reste un reliquat (le BC n'est pas encore `livre`)."""
        if self.statut == self.Statut.LIVRE:
            return False
        reliquats = self.reliquat_par_ligne
        if not reliquats:
            return False
        any_livre = any(r['quantite_livree'] > 0 for r in reliquats)
        any_reliquat = any(r['reliquat'] > 0 for r in reliquats)
        return any_livre and any_reliquat


class AffectationPaiement(models.Model):
    """XFAC1 — ventilation d'un paiement (avance/trop-perçu) sur UNE facture.

    Un même ``Paiement`` non affecté peut porter plusieurs lignes
    d'affectation (réparti sur N factures ouvertes du même client). La somme
    des affectations d'un paiement ne peut jamais dépasser son montant (garde
    posée côté service — jamais de sur-affectation)."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,  # on_delete: purge tenant
        null=True, blank=True, related_name='affectations_paiement')
    paiement = models.ForeignKey(
        'facturation.Paiement', on_delete=models.CASCADE,  # on_delete: affectation sans objet si paiement supprimé
        related_name='affectations')
    facture = models.ForeignKey(
        'facturation.Facture', on_delete=models.CASCADE,  # on_delete: affectation sans objet si facture supprimée
        related_name='affectations_paiement')
    montant = models.DecimalField(max_digits=12, decimal_places=2)
    date_affectation = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name='affectations_effectuees')

    class Meta:
        verbose_name = 'Affectation de paiement'
        verbose_name_plural = 'Affectations de paiement'
        ordering = ['-date_affectation']

    def __str__(self):
        return f'{self.montant} MAD — {self.paiement_id} → {self.facture.reference}'


from apps.facturation.totaux import TotauxDocumentMixin  # noqa: E402


class NoteDebit(TotauxDocumentMixin, models.Model):
    """ZFAC4 — note de débit : pendant de l'``Avoir`` qui MAJORE une facture
    déjà émise (surfacturation régularisée, complément non prévu) au lieu de
    la réduire. Miroir structurel d'``Avoir`` (mêmes champs), référence
    préfixée ``ND-`` (jamais ``AVO-``)."""
    class Statut(models.TextChoices):
        BROUILLON = 'brouillon', 'Brouillon'
        EMISE = 'emise', 'Émise'
        ANNULEE = 'annulee', 'Annulée'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,  # on_delete: purge tenant
        null=True, blank=True, related_name='notes_debit')
    reference = models.CharField(max_length=50)
    facture = models.ForeignKey(
        'facturation.Facture', on_delete=models.PROTECT, related_name='notes_debit')
    client = models.ForeignKey(
        'crm.Client', on_delete=models.PROTECT, related_name='notes_debit')
    statut = models.CharField(
        max_length=20, choices=Statut.choices, default=Statut.BROUILLON)
    motif = models.TextField(blank=True, default='')
    date_emission = models.DateField(auto_now_add=True)
    taux_tva = models.DecimalField(max_digits=5, decimal_places=2, default=20.00)
    # AUD107 — miroir du champ de Facture/Avoir. La note de débit N'AVAIT
    # AUCUN champ de remise globale : son chemin de repli « facture entière »
    # recopiait les lignes 1:1 (produit, quantité, P.U., remise DE LIGNE, taux
    # TVA) sans jamais la remise globale du document, et sa propriété
    # ``total_ht`` sommait ces lignes. Une pénalité de retard adossée à une
    # facture remisée à 15 % majorait donc le client sur le montant NON remisé.
    remise_globale = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        help_text='Remise globale (%) reprise de la facture d\'origine.')
    # Montants figés (chemin simple, sans lignes détaillées) — utilisés quand
    # aucune ligne n'est fournie.
    montant_ht = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True)
    montant_tva = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True)
    montant_ttc = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name='notes_debit_creees')
    fichier_pdf = models.CharField(max_length=500, blank=True, null=True)
    # ATOT6 (C-ATOT-004) — ventilation TVA par taux ``[{taux, base_ht,
    # montant}]`` (chaînes) recopiée AU PRORATA de la facture d'origine
    # (``totaux.ventilation_document_fige``) quand celle-ci est ventilée
    # (tranche à taux mixtes, CIQ215) : le document porte autant de paniers
    # que sa facture, jamais le « taux mélangé ». Vide = comportement d'hier.
    ventilation_tva = models.JSONField(
        null=True, blank=True, verbose_name='Ventilation TVA par taux')

    class Meta:
        verbose_name = 'Note de débit'
        verbose_name_plural = 'Notes de débit'
        ordering = ['-date_emission', '-id']
        unique_together = [('company', 'reference')]

    def __str__(self):
        return self.reference

    # AUD107 — les totaux viennent de ``TotauxDocumentMixin``
    # (``apps.facturation.models``), seul propriétaire de la chaîne
    # HT → remise globale → TVA par taux → TTC, partagé avec Facture (AUD105)
    # et Avoir (AUD106). C'était le MIROIR EXACT du défaut de l'Avoir : seul le
    # chemin de repli « facture SANS lignes » utilisait la propriété
    # remise-aware de la facture ; le chemin normal, qui est le cas courant, ne
    # le faisait jamais.


class LigneNoteDebit(models.Model):
    note_debit = models.ForeignKey(
        NoteDebit, on_delete=models.CASCADE,  # on_delete: composant du parent
        related_name='lignes')
    produit = models.ForeignKey(
        'stock.Produit', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='lignes_note_debit')
    designation = models.CharField(max_length=255)
    quantite = models.DecimalField(max_digits=10, decimal_places=2)
    prix_unitaire = models.DecimalField(max_digits=10, decimal_places=2)
    remise = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    taux_tva = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True)

    class Meta:
        verbose_name = 'Ligne de note de débit'
        verbose_name_plural = 'Lignes de note de débit'

    @property
    def total_ht(self):
        # Jumeau exact du 500 latent de LigneFacture (remise int par défaut →
        # Decimal * float lève TypeError sur une ligne fraîchement créée).
        from decimal import Decimal
        remise = Decimal(str(self.remise or 0))
        return self.quantite * self.prix_unitaire * (1 - remise / 100)

    @property
    def taux_tva_effectif(self):
        return (self.taux_tva if self.taux_tva is not None
                else self.note_debit.taux_tva)


class RetenueSubie(models.Model):
    """XFAC4 — Retenue à la source SUBIE par NOUS sur une facture client
    (RAS TVA / RAS honoraires, réforme TVA 2024) : un client (État, grande
    entreprise) retient un pourcentage de notre facture et ne nous verse que le
    net — la facture reste juridiquement soldée (payé + retenue + avoirs =
    TTC) mais on trace la créance d'attestation de retenue à recevoir.

    Miroir de ``compta.RetenueSource`` (FG139 — RAS que NOUS retenons sur nos
    fournisseurs) mais côté RECETTE : ici c'est le CLIENT qui retient sur ce
    qu'il nous doit. Snapshot figé (base/taux/montant) au moment de la saisie.
    """
    class TypeRetenue(models.TextChoices):
        RAS_TVA = 'ras_tva', 'RAS TVA'
        RAS_IS = 'ras_is', 'RAS IS'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,  # on_delete: purge tenant
        null=True, blank=True, related_name='retenues_subies')
    facture = models.ForeignKey(
        'facturation.Facture', on_delete=models.CASCADE,  # on_delete: retenue sans objet si facture supprimée
        related_name='retenues_subies')
    # Paiement qui a déclenché la constatation de la retenue (le paiement
    # partiel + la retenue soldent ensemble la facture). Optionnel : la
    # retenue peut être saisie avant ou après le paiement lui-même.
    paiement = models.ForeignKey(
        'facturation.Paiement', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='retenues_subies')
    type_retenue = models.CharField(
        max_length=10, choices=TypeRetenue.choices, default=TypeRetenue.RAS_TVA)
    taux = models.DecimalField(max_digits=5, decimal_places=2)
    base = models.DecimalField(max_digits=12, decimal_places=2)
    montant = models.DecimalField(max_digits=12, decimal_places=2)
    attestation_recue = models.BooleanField(default=False)
    attestation_date = models.DateField(null=True, blank=True)
    attestation_fichier = models.CharField(max_length=500, blank=True, null=True)
    note = models.TextField(blank=True, default='')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name='retenues_subies_creees')
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Retenue à la source subie'
        verbose_name_plural = 'Retenues à la source subies'
        ordering = ['-date_creation']

    def __str__(self):
        return f'RAS {self.montant} MAD — {self.facture.reference}'


class AbandonCreance(TenantModel):
    """AFAC34 (C-AFAC-030, D-AFAC-C6 option a) — un abandon de créance est un
    ENREGISTREMENT daté, cumulable et réversible (miroir de ``RetenueSubie``),
    plus un champ unique écrasé à chaque geste. ``Facture.abandon_montant``
    reste la SOMME des abandons actifs (``annule_le`` vide), tenue à jour par
    le service ``abandonner_solde_facture`` / ``reprendre_abandon_creance`` :
    ``decomposition_du``/``montant_du`` la lisent sans requête de plus. La
    reprise est MANUELLE, jamais automatique (D-AFAC-C6).

    SCA4 — hérite du socle ``core.models.TenantModel`` (timestamps) ; ``company``
    est redéclaré (motif ARC1) pour garder ``null=True`` + son ``related_name``."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,  # on_delete: purge tenant
        null=True, blank=True, related_name='abandons_creance')
    facture = models.ForeignKey(
        'facturation.Facture', on_delete=models.CASCADE,  # on_delete: abandon sans objet si facture supprimée
        related_name='abandons_creance')
    montant = models.DecimalField(max_digits=12, decimal_places=2)
    motif = models.CharField(max_length=20, blank=True, default='')
    auto = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        blank=True, related_name='abandons_creance_crees')
    date_abandon = models.DateTimeField(default=timezone.now)
    annule_le = models.DateTimeField(null=True, blank=True)
    annule_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        blank=True, related_name='abandons_creance_repris')
    motif_reprise = models.TextField(blank=True, default='')

    class Meta:
        verbose_name = 'Abandon de créance'
        verbose_name_plural = 'Abandons de créance'
        ordering = ['date_abandon', 'id']

    def __str__(self):
        return f'Abandon {self.montant} MAD — {self.facture.reference}'


class PromessePaiement(models.Model):
    """XFAC5 — engagement client tracé (« je paie le 15 ») qui SUSPEND les
    relances automatiques de la facture jusqu'à ``date_promise``. Le job beat
    (``scheduled.py relance_reminders``) marque la promesse ``rompue`` si la
    date passe sans encaissement suffisant et reprend les relances avec un
    flag « promesse rompue »."""
    class Statut(models.TextChoices):
        EN_COURS = 'en_cours', 'En cours'
        TENUE = 'tenue', 'Tenue'
        ROMPUE = 'rompue', 'Rompue'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,  # on_delete: donnée propre à la société — supprimée avec elle (multi-tenant)
        null=True, blank=True, related_name='promesses_paiement')
    facture = models.ForeignKey(
        'facturation.Facture', on_delete=models.CASCADE,  # on_delete: promesse sans objet si facture supprimée
        related_name='promesses_paiement')
    montant_promis = models.DecimalField(max_digits=12, decimal_places=2)
    date_promise = models.DateField()
    note = models.TextField(blank=True, default='')
    statut = models.CharField(
        max_length=10, choices=Statut.choices, default=Statut.EN_COURS)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name='promesses_paiement_creees')
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Promesse de paiement'
        verbose_name_plural = 'Promesses de paiement'
        ordering = ['-date_creation']

    def __str__(self):
        return (f'Promesse {self.montant_promis} MAD le {self.date_promise} '
                f'— {self.facture.reference}')


class ParametrageRelanceClient(models.Model):
    """ZFAC8 — réglage PAR CLIENT du responsable de relance + du mode
    (auto/manuel), lu par ``scheduled.relance_reminders``. En mode
    ``manuel``, le cron n'envoie AUCUNE relance automatique pour ce client
    (il apparaît seulement dans la liste manuelle de son responsable).
    Défaut = ``auto`` → comportement historique inchangé pour tout client
    non paramétré (absence de ligne = auto)."""
    class Mode(models.TextChoices):
        AUTO = 'auto', 'Automatique'
        MANUEL = 'manuel', 'Manuel'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,  # on_delete: purge tenant
        null=True, blank=True, related_name='parametrages_relance')
    client = models.OneToOneField(
        'crm.Client', on_delete=models.CASCADE,  # on_delete: paramétrage sans objet si client supprimé
        related_name='parametrage_relance')
    responsable = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,  # on_delete: responsable de relance informatif — le paramétrage survit à son départ
        null=True, blank=True, related_name='clients_relance_responsable')
    mode = models.CharField(
        max_length=10, choices=Mode.choices, default=Mode.AUTO)
    prochaine_relance_manuelle = models.DateField(null=True, blank=True)

    class Meta:
        verbose_name = 'Paramétrage de relance client'
        verbose_name_plural = 'Paramétrages de relance client'

    def __str__(self):
        return f'{self.client_id} — {self.mode}'


class PaymentLink(models.Model):
    """FG53 — lien « Payer en ligne » d'une facture.

    Scaffolding swappable (cf. monitoring/providers) : un fournisseur de
    paiement est sélectionné par clé ; le DÉFAUT est NoOp (« manuel »), sans
    dépendance ni appel réseau ni coût. Le lien public expose le minimum (montant
    dû, référence facture) et un webhook idempotent enregistre un ``Paiement``
    quand le fournisseur confirme l'encaissement. Tant qu'aucun fournisseur réel
    n'est configuré, le lien reste un squelette inerte : aucune passerelle live
    n'est câblée ici.

    Le jeton est long/imprévisible/expirant (30 j), comme ShareLink. Aucune
    donnée interne (prix d'achat/marge) n'est jamais exposée."""

    class Statut(models.TextChoices):
        EN_ATTENTE = 'en_attente', 'En attente'
        PAYE = 'paye', 'Payé'
        EXPIRE = 'expire', 'Expiré'
        ANNULE = 'annule', 'Annulé'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,  # on_delete: purge tenant
        related_name='payment_links')
    facture = models.ForeignKey(
        'facturation.Facture', on_delete=models.CASCADE,  # on_delete: lien sans objet si facture supprimée
        related_name='payment_links')
    token = models.CharField(
        max_length=64, unique=True, default=_default_payment_token,
        editable=False)
    # Clé du fournisseur (registre payments.providers). 'noop' = défaut inerte.
    provider = models.CharField(max_length=40, default='noop')
    # Montant CONSTATÉ à la création (trace de ce qui était dû ce jour-là).
    # AUD136 — ce n'est PAS ce que le client paie : le montant encaissé est
    # DÉRIVÉ de `facture.montant_du` à l'instant du paiement (voir
    # `montant_a_payer` ci-dessous et `record_payment_from_link`). Un lien créé
    # avec un montant erroné, ou une facture réglée entre-temps, ne peut donc
    # pas encaisser un chiffre périmé.
    montant = models.DecimalField(max_digits=12, decimal_places=2)
    statut = models.CharField(
        max_length=20, choices=Statut.choices, default=Statut.EN_ATTENTE)
    # Référence retournée par le fournisseur (idempotence du webhook).
    provider_ref = models.CharField(max_length=200, blank=True, default='')
    paiement = models.ForeignKey(
        'facturation.Paiement', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='payment_links')
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(default=_default_payment_expiry)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Lien de paiement'
        verbose_name_plural = 'Liens de paiement'
        ordering = ['-created_at']
        indexes = [models.Index(fields=['token'])]
        constraints = [
            # AUD136 — UN SEUL lien EN ATTENTE par facture, garanti en base.
            # `create_payment_link` réutilisait déjà un lien valide, mais rien
            # n'empêchait deux liens actifs (course, écriture directe, ré-émission
            # à volonté) sur la même facture.
            models.UniqueConstraint(
                fields=['facture'],
                condition=models.Q(statut='en_attente'),
                name='uniq_paymentlink_actif_par_facture'),
        ]

    def __str__(self):
        return f'PaymentLink {self.token[:8]}… ({self.facture.reference})'

    @property
    def is_valid(self):
        return (self.statut == self.Statut.EN_ATTENTE
                and self.expires_at > timezone.now())

    @property
    def montant_a_payer(self):
        """AUD136 — le montant RÉELLEMENT dû, à l'instant où on le demande.

        ``montant`` est la trace de ce qui était dû à la création ; l'afficher
        au client (page publique) après un règlement partiel lui réclamait un
        chiffre périmé. Le webhook borne déjà l'encaissement à ce reste dû —
        c'est la même valeur, exposée au même endroit.

        AFAC24 (C-AFAC-019) — « à payer maintenant » = ``montant_exigible``
        (CIQ214 : ``montant_du`` − retenue de garantie non libérée), le même
        chiffre que la lettre de relance et l'e-mail. Le webhook, lui, reste
        borné à ``montant_du`` (une retenue payée volontairement est acceptée)."""
        from decimal import Decimal

        facture = self.facture
        reste = getattr(facture, 'montant_exigible', None)
        return reste if reste is not None else Decimal('0')


# ── XFSM19 — Rapprochement des encaissements terrain par technicien ─────────
# FG124 (compta.Caisse/MouvementCaisse) couvre les DÉPENSES de caisse ; rien
# ne réconcilie les espèces/chèques COLLECTÉS SUR LE TERRAIN par un
# technicien contre les factures — critique dans le résidentiel marocain
# cash. Les Paiement lus/rapprochés ici vivent DÉJÀ dans ventes (même app,
# import direct) : aucune frontière cross-app n'est franchie par ce modèle.
class RemiseEncaissement(models.Model):
    """Déclaration + clôture d'une collecte d'encaissements terrain.

    Le technicien déclare sa collecte du jour (des ``Paiement`` déjà
    enregistrés, mode espèces/chèque) ; le responsable la clôture avec un
    bordereau PDF. ``montant_declare`` vs la somme des lignes donne l'écart —
    jamais silencieux (alerté si ≠ 0)."""
    class Statut(models.TextChoices):
        OUVERTE = 'ouverte', 'Ouverte'
        CLOTUREE = 'cloturee', 'Clôturée'
        VALIDEE = 'validee', 'Validée'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,  # on_delete: purge tenant
        related_name='remises_encaissement')
    technicien = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name='remises_encaissement')
    reference = models.CharField(max_length=50, blank=True, default='')
    date_collecte = models.DateField()
    montant_declare = models.DecimalField(
        max_digits=12, decimal_places=2,
        help_text=(
            'Montant total déclaré par le technicien pour cette '
            'collecte (avant rapprochement des lignes).'))
    statut = models.CharField(
        max_length=15, choices=Statut.choices, default=Statut.OUVERTE)
    note = models.TextField(blank=True, default='')
    fichier_pdf = models.CharField(max_length=500, blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name='remises_encaissement_creees')
    date_creation = models.DateTimeField(auto_now_add=True)
    cloture_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        blank=True, related_name='remises_encaissement_cloturees')
    date_cloture = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Remise d\'encaissement terrain'
        verbose_name_plural = 'Remises d\'encaissement terrain'
        ordering = ['-date_collecte', '-id']
        # ATOT12 (C-ATOT-019) — deux remises d'une société ne portent jamais
        # le même numéro : sans cette contrainte, le retry de
        # `create_with_reference` ne pouvait jamais jouer (aucune
        # IntegrityError). Référence vide (historique) hors contrainte.
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'reference'],
                condition=~models.Q(reference=''),
                name='uniq_remiseencaissement_reference_par_societe'),
        ]

    def __str__(self):
        return f'Remise {self.reference or self.id} — {self.technicien}'

    @property
    def montant_lignes(self):
        from decimal import Decimal
        return sum(
            (ligne.paiement.montant for ligne in self.lignes.select_related(
                'paiement').all()), Decimal('0'))

    @property
    def ecart(self):
        return self.montant_declare - self.montant_lignes


class LigneRemiseEncaissement(models.Model):
    """Une ligne = un ``Paiement`` (espèces/chèque) rattaché à cette remise.

    AUD135 — l'unicité était déclarée ``unique_together [('remise','paiement')]``,
    donc PAR REMISE : rien n'empêchait le même Paiement d'apparaître dans N
    remises, et ``RemiseEncaissement.montant_lignes`` le comptait dans chacune
    (le même chèque de 15 000 déclaré dans deux bordereaux ⇒ 15 000 de trop au
    rapprochement de caisse). La contrainte porte désormais sur ``paiement``
    SEUL : un encaissement appartient à AU PLUS UNE remise, garanti en base.

    AUD135 — le verrou post-clôture annoncé ici n'existait nulle part :
    ``cloturer`` ne changeait que le statut et aucun service ne l'appliquait.
    Il est maintenant RÉEL (``save``/``delete`` ci-dessous), pas une promesse
    de docstring."""
    remise = models.ForeignKey(
        RemiseEncaissement, on_delete=models.CASCADE,  # on_delete: composant du parent
        related_name='lignes')
    paiement = models.ForeignKey(
        'facturation.Paiement', on_delete=models.PROTECT,
        related_name='lignes_remise_encaissement')

    class Meta:
        verbose_name = 'Ligne de remise d\'encaissement'
        verbose_name_plural = 'Lignes de remise d\'encaissement'
        constraints = [
            models.UniqueConstraint(
                fields=['paiement'],
                name='uniq_ligne_remise_par_paiement'),
        ]

    def _garde_remise_ouverte(self, verbe):
        """AUD135 — le verrou post-clôture, réellement appliqué."""
        from django.core.exceptions import ValidationError as DjangoValidationError

        statut = getattr(self.remise, 'statut', None)
        if statut and statut != RemiseEncaissement.Statut.OUVERTE:
            raise DjangoValidationError(
                f'Remise {self.remise.reference or self.remise_id} '
                f'{self.remise.get_statut_display().lower()} : ses lignes sont '
                f'verrouillées, impossible de les {verbe}.')

    def save(self, *args, **kwargs):
        self._garde_remise_ouverte('modifier')
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        self._garde_remise_ouverte('supprimer')
        return super().delete(*args, **kwargs)

    def __str__(self):
        return f'{self.remise_id} — paiement {self.paiement_id}'


# ── XCTR22 — Mandat de paiement récurrent (tokenisation carte) ──────────────
# Key-gated OFF par défaut : tant qu'aucun mandat actif n'existe pour un
# client (le cas par défaut, aucun fournisseur de tokenisation n'étant câblé),
# rien ne change au cycle de facturation récurrente existant (XCTR5/XCTR20).
class MandatPaiement(models.Model):
    """Mandat de prélèvement carte (tokenisation), proposé depuis le portail
    client (XCTR14). AUCUN PAN n'est jamais stocké — seul un token OPAQUE du
    fournisseur (+ 4 derniers chiffres/expiration pour l'affichage)."""
    class Statut(models.TextChoices):
        ACTIF = 'actif', 'Actif'
        EXPIRE = 'expire', 'Expiré'
        REVOQUE = 'revoque', 'Révoqué'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,  # on_delete: purge tenant
        related_name='mandats_paiement')
    client = models.ForeignKey(
        'crm.Client', on_delete=models.PROTECT,
        related_name='mandats_paiement')
    provider = models.CharField(max_length=40, default='noop')
    # Token OPAQUE renvoyé par le fournisseur — jamais un PAN.
    token = models.CharField(max_length=200, blank=True, default='')
    derniers_chiffres = models.CharField(max_length=4, blank=True, default='')
    expiration_mois = models.CharField(
        max_length=7, blank=True, default='',
        help_text='MM/AAAA, affichage seulement.')
    statut = models.CharField(
        max_length=10, choices=Statut.choices, default=Statut.ACTIF)
    # Loi 09-08 — consentement horodaté explicite du client à la tokenisation.
    consentement_horodate = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Mandat de paiement récurrent'
        verbose_name_plural = 'Mandats de paiement récurrent'
        ordering = ['-created_at']

    def __str__(self):
        return f'Mandat {self.client_id} ({self.get_statut_display()})'

    @property
    def is_actif(self):
        return self.statut == self.Statut.ACTIF and bool(self.token)


class TentativeDebitMandat(models.Model):
    """XCTR22 — file d'exceptions/dunning du débit automatique par mandat.

    Une ligne par TENTATIVE de débit (succès ou échec) sur une période de
    facturation donnée — garde anti double-débit : jamais deux débits
    RÉUSSIS pour le même ``(mandat, periode)``."""
    class Statut(models.TextChoices):
        REUSSI = 'reussi', 'Réussi'
        ECHEC = 'echec', 'Échec'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,  # on_delete: purge tenant
        related_name='tentatives_debit_mandat')
    mandat = models.ForeignKey(
        MandatPaiement, on_delete=models.CASCADE,  # on_delete: tentative sans objet si mandat supprimé
        related_name='tentatives')
    periode = models.CharField(max_length=20)
    statut = models.CharField(max_length=10, choices=Statut.choices)
    motif_echec = models.CharField(max_length=255, blank=True, default='')
    paiement = models.ForeignKey(
        'facturation.Paiement', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='tentatives_debit_mandat')
    date_tentative = models.DateTimeField(auto_now_add=True)
    prochaine_retentative = models.DateField(null=True, blank=True)

    class Meta:
        verbose_name = 'Tentative de débit (mandat)'
        verbose_name_plural = 'Tentatives de débit (mandat)'
        ordering = ['-date_tentative']

    def __str__(self):
        return f'{self.mandat_id} / {self.periode} — {self.statut}'


class LivraisonBC(models.Model):
    """XSAL12 — Livraison partielle d'un bon de commande client.

    Une ligne par événement de livraison (ex. « panneaux livrés le 3 juin »).
    Le décompte réel par ligne de BC vit sur ``LigneLivraisonBC`` ; le solde
    (reliquat) et le passage automatique à ``livre`` sont calculés à la
    demande depuis l'ensemble des livraisons du BC — jamais stockés en dur
    pour rester toujours cohérents avec ``LigneDevis.quantite`` source."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,  # on_delete: purge tenant
        related_name='livraisons_bc')
    bon_commande = models.ForeignKey(
        BonCommande, on_delete=models.CASCADE,  # on_delete: livraison sans objet si BC supprimé
        related_name='livraisons')
    date_livraison = models.DateField()
    note = models.CharField(max_length=255, blank=True, default='')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        blank=True, related_name='livraisons_bc_creees')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Livraison (BC)'
        verbose_name_plural = 'Livraisons (BC)'
        ordering = ['-date_livraison', '-created_at']

    def __str__(self):
        return f'Livraison {self.bon_commande_id} du {self.date_livraison}'


class LigneLivraisonBC(models.Model):
    """XSAL12 — Quantité livrée pour une ligne de devis donnée, dans une
    livraison partielle. ``ligne_devis`` référence la ligne du devis source
    du BC (même app, FK directe autorisée)."""
    livraison = models.ForeignKey(
        LivraisonBC, on_delete=models.CASCADE,  # on_delete: composant du parent
        related_name='lignes')
    ligne_devis = models.ForeignKey(
        LigneDevis, on_delete=models.CASCADE,  # on_delete: décompte sans objet si ligne devis supprimée
        related_name='lignes_livraison_bc')
    quantite_livree = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        verbose_name = 'Ligne de livraison (BC)'
        verbose_name_plural = 'Lignes de livraison (BC)'

    def __str__(self):
        return f'{self.livraison_id} / ligne {self.ligne_devis_id} = {self.quantite_livree}'


class FacturePenalite(TenantModel):
    """AFAC50 (C-AFAC-040 a) — liaison DURABLE entre une facture d'origine et
    LA facture de pénalités de retard émise pour un niveau de relance :
    ``facturer-penalites`` est idempotent par (facture, niveau). Une facture
    de pénalités ANNULÉE libère le niveau (la liaison est re-pointée sur la
    nouvelle) ; un niveau supérieur ouvre une nouvelle liaison.

    SCA4 — hérite du socle ``core.models.TenantModel`` (timestamps) ; ``company``
    est redéclaré (motif ARC1) pour garder ``null=True`` + son ``related_name``."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,  # on_delete: purge tenant
        null=True, blank=True, related_name='factures_penalite')
    facture_origine = models.ForeignKey(
        'facturation.Facture', on_delete=models.CASCADE,  # on_delete: liaison sans objet si facture d'origine supprimée
        related_name='liaisons_penalite')
    niveau = models.PositiveIntegerField()
    facture_penalite = models.ForeignKey(
        'facturation.Facture', on_delete=models.PROTECT,
        related_name='liaisons_penalite_source')
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Facture de pénalités'
        verbose_name_plural = 'Factures de pénalités'
        constraints = [
            models.UniqueConstraint(
                fields=['facture_origine', 'niveau'],
                name='uniq_facture_penalite_par_niveau'),
        ]

    def __str__(self):
        return f'Pénalités {self.facture_origine_id} / niveau {self.niveau}'
