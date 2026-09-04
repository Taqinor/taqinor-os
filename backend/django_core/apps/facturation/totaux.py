"""AUD105/AUD106/AUD107 — LE propriétaire unique de la chaîne d'argent des
documents client : HT brut → remise globale → TVA par taux → TTC.

MODULE SANS MODÈLE, DÉLIBÉRÉMENT. Le mixin est consommé par ``Facture`` et
``Avoir`` (``apps.facturation.models``) ET par ``NoteDebit``
(``apps.ventes.models``). Le vivre ici, dans un module qui n'importe AUCUN
modèle, permet à ``apps.ventes.models`` de l'importer en tête de fichier sans
toucher l'ordre de chargement des applications (``apps.ventes.models``
n'importe ``apps.facturation.models`` qu'en BAS de fichier, à dessein).
"""


class TotauxDocumentMixin:
    """LE SEUL PROPRIÉTAIRE de la chaîne HT → remise globale → TVA par taux →
    TTC, partagé par ``Facture``, ``Avoir`` et ``NoteDebit``.

    POURQUOI IL EXISTE. La chaîne était implémentée trois fois. Seule
    ``Facture`` honorait ``remise_globale`` (QX1) ; ``Avoir`` et ``NoteDebit``
    sommaient les lignes BRUTES. Conséquences chiffrées et réelles : sur une
    facture remisée à 15 %, l'avoir TOTAL créditait le brut (20 400 TTC
    facturés, 24 000 TTC crédités — 3 600 MAD offerts au client) et la note de
    débit majorait le client sur un montant NON remisé. ``Avoir.remise_globale``
    existait pourtant depuis sa migration d'origine : jamais lu, jamais posé —
    un champ d'argent MORT sur un document client, qui donnait l'illusion que
    la remise était gérée.

    Le document hôte doit exposer : ``lignes`` (avec ``total_ht`` et
    ``taux_tva_effectif``), ``remise_globale``, ``taux_tva`` et le triplet de
    montants FIGÉS ``montant_ht``/``montant_tva``/``montant_ttc`` (nullable —
    un avoir/une note sur facture de tranche fige ses montants comme la
    facture).

    Un document SANS remise globale (le défaut, 0) ou à montants figés garde la
    sémantique historique « total = somme des lignes », au bit près.

    Le mixin ne déclare AUCUN champ : il ne modifie donc pas l'état de
    migration des modèles qui l'adoptent.
    """

    @property
    def _remise_globale_active(self):
        """QX1 — vrai si une remise globale doit être appliquée aux totaux.

        Ne s'applique JAMAIS à un document à montants figés (tranche
        d'échéancier) et seulement si ``remise_globale`` > 0."""
        from decimal import Decimal
        if self.montant_ht is not None:
            return False
        return (getattr(self, 'remise_globale', None) or Decimal('0')) > 0

    def _canonique(self):
        """La chaîne canonique QX1 sur les lignes de CE document."""
        from apps.ventes.selectors import _canonical_totaux
        return _canonical_totaux(
            self.lignes.all(),
            remise_globale_pct=self.remise_globale,
            fallback_taux=self.taux_tva)

    @property
    def total_ht(self):
        # Montant figé (tranche d'échéancier) → tel quel. Sinon : somme des
        # lignes, NETTE de la remise globale quand elle est active.
        if self.montant_ht is not None:
            return self.montant_ht
        if self._remise_globale_active:
            return self._canonique()['ht_net']
        return sum(ligne.total_ht for ligne in self.lignes.all())

    @property
    def tva_par_taux(self):
        """Ventilation de la TVA par taux (10 % / 20 %), réconciliée au centime.

        Mono-taux (tout l'historique et les documents de tranche) → un seul
        panier, formule d'origine, rendu strictement inchangé. Taux mixtes →
        un panier par taux, chaque TVA arrondie au centime, dont la somme est
        le total TVA. DC23 — délègue au selector unique ``tva_buckets`` ; QX1 —
        remise globale active → la TVA est calculée sur le HT NET."""
        if self._remise_globale_active:
            return self._canonique()['tva_par_taux']
        from apps.ventes.selectors import tva_buckets
        frozen = None
        if self.montant_tva is not None:
            frozen = (self.taux_tva, self.total_ht, self.montant_tva)
        return tva_buckets(
            self.lignes.all(), fallback_taux=self.taux_tva, frozen=frozen)

    @property
    def total_tva(self):
        if self.montant_tva is not None:
            return self.montant_tva
        from decimal import Decimal
        return sum((b['montant'] for b in self.tva_par_taux), Decimal('0'))

    @property
    def total_ttc(self):
        if self.montant_ttc is not None:
            return self.montant_ttc
        if self._remise_globale_active:
            return self._canonique()['ttc']
        return self.total_ht + self.total_tva

    @property
    def totaux_affichage(self):
        """AUD105 — LA CHAÎNE IMPRIMABLE : ``{ht_brut, remise, ht_net,
        tva_par_taux, ttc}``, seule source des documents client.

        Les gabarits imprimaient « Sous-total HT » = ``total_ht`` puis
        « Remise globale (X %) » = ``total_ht × remise / 100``. Or ``total_ht``
        EST le HT NET dès qu'une remise globale est active (QX1) : le document
        affichait un net étiqueté « Sous-total » puis lui appliquait le
        pourcentage une SECONDE fois — double décompte, et une chaîne imprimée
        qui ne retombait sur aucun total de la page. UN GABARIT NE RECALCULE
        JAMAIS UN POURCENTAGE : il lit ces trois valeurs.

        Sans remise globale active, ``ht_brut == ht_net`` et ``remise`` vaut 0
        — rendu strictement inchangé."""
        from decimal import Decimal
        if self._remise_globale_active:
            totaux = self._canonique()
            return {
                'ht_brut': totaux['ht_brut'], 'remise': totaux['remise'],
                'ht_net': totaux['ht_net'],
                'tva_par_taux': totaux['tva_par_taux'], 'ttc': totaux['ttc'],
            }
        ht = self.total_ht
        return {
            'ht_brut': ht, 'remise': Decimal('0'), 'ht_net': ht,
            'tva_par_taux': self.tva_par_taux, 'ttc': self.total_ttc,
        }
