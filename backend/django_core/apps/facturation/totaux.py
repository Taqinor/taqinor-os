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
    def _figee(self):
        """Vrai pour un document à montants FIGÉS (tranche d'échéancier) —
        ``montant_ht`` posé. Ces montants ne repassent JAMAIS par le noyau
        canonique : ils SONT le total, tel quel."""
        return self.montant_ht is not None

    def _canonique(self):
        """La chaîne canonique QX1 sur les lignes de CE document.

        ERR-QAH-VENTES-FACTURE-HT-NON-ARRONDI — appelée pour TOUT document
        non figé, remise globale nulle INCLUSE : ``_canonical_totaux`` avec
        ``remise_globale_pct=0`` quantifie quand même le HT au centime
        (``ht_net = q(ht_brut)``) et calcule la TVA sur cette base ARRONDIE
        — exactement ce que ``Devis.total_ht``/``total_tva`` consultent déjà
        pour CHAQUE facture, remisée ou non. Avant ce correctif, une facture
        SANS remise globale (le cas courant) retombait sur une somme brute
        jamais quantifiée (``sum(ligne.total_ht ...)``) et sur
        ``tva_buckets`` calculant la TVA sur cette même base brute — deux
        chaînes d'arrondi divergentes pour le même document selon qu'il
        portait une remise globale ou non."""
        from apps.ventes.selectors import _canonical_totaux
        return _canonical_totaux(
            self.lignes.all(),
            remise_globale_pct=self.remise_globale,
            fallback_taux=self.taux_tva)

    @property
    def total_ht(self):
        # Montant figé (tranche d'échéancier) → tel quel. Sinon : TOUJOURS
        # le noyau canonique (remise globale ou non, cf. ``_canonique``).
        if self._figee:
            return self.montant_ht
        return self._canonique()['ht_net']

    @property
    def tva_par_taux(self):
        """Ventilation de la TVA par taux (10 % / 20 %), réconciliée au centime.

        Document figé (montant_tva posé, tranche d'échéancier) → panier
        unique, formule d'origine, rendu strictement inchangé. Sinon →
        TOUJOURS le noyau canonique (``_canonique``) : la TVA se calcule sur
        le HT NET déjà arrondi au centime, remise globale ou non (ERR-QAH-
        VENTES-FACTURE-HT-NON-ARRONDI)."""
        if self.montant_tva is not None:
            from apps.ventes.selectors import tva_buckets
            frozen = (self.taux_tva, self.total_ht, self.montant_tva)
            return tva_buckets(
                self.lignes.all(), fallback_taux=self.taux_tva, frozen=frozen)
        return self._canonique()['tva_par_taux']

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
        return self._canonique()['ttc']

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

        Document figé, ou sans remise globale → ``ht_brut == ht_net`` et
        ``remise`` vaut 0 (le noyau canonique le rend déjà pour une remise
        nulle) — rendu strictement inchangé."""
        from decimal import Decimal
        if self._figee:
            ht = self.total_ht
            return {
                'ht_brut': ht, 'remise': Decimal('0'), 'ht_net': ht,
                'tva_par_taux': self.tva_par_taux, 'ttc': self.total_ttc,
            }
        totaux = self._canonique()
        return {
            'ht_brut': totaux['ht_brut'], 'remise': totaux['remise'],
            'ht_net': totaux['ht_net'],
            'tva_par_taux': totaux['tva_par_taux'], 'ttc': totaux['ttc'],
        }
