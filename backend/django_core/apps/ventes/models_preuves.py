"""Champs de PREUVE du lien public (L3 lien, 24/10/2026) — mixins ABSTRAITS.

``DevisSignature`` (``models.py``) hérite de :class:`PreuveSignatureB2B` :
tout ce que l'acceptation en ligne d'un devis commercial / industriel doit
garder en plus du nom tapé — l'e-mail du signataire et son attestation de
pouvoir (ADEV95). Champs ADDITIFS : vides sur toute signature antérieure et
hors C&I (comportement inchangé). Aucun statut nouveau (règle #4).

Module séparé parce que ``models.py`` est un fichier-mur (≥ 2 000 lignes, garde
C20) : les champs vivent ici, la table reste celle de ``DevisSignature``.
"""
from django.db import models


class PreuveSignatureB2B(models.Model):
    """ADEV95 — identité et pouvoir du SIGNATAIRE d'une entreprise.

    * ``signataire_email`` — l'adresse du signataire déclarée à l'acceptation
      (destinataire de la confirmation, ADEV99) ;
    * ``pouvoir_engager`` — le signataire a coché « j'agis en la qualité
      indiquée et j'ai le pouvoir d'engager la société ».
    """

    #: ADEV96 — v2 + les chiffres de l'étude C&I que la page et le PDF montrent
    #: (``domain.modifiabilite.figures_etude_scellees`` de la ``synthese_ci``).
    CONTENT_HASH_V3 = 3
    #: La version du payload dont sont scellées les NOUVELLES signatures
    #: (``DevisSignature.compute_content_hash`` ; v1 = QJ10, v2 = QJR144).
    CONTENT_HASH_VERSION = CONTENT_HASH_V3

    signataire_email = models.EmailField(
        max_length=254, blank=True, default='',
        verbose_name='E-mail du signataire (entreprise)')
    pouvoir_engager = models.BooleanField(
        default=False,
        verbose_name="Le signataire atteste du pouvoir d'engager la société")
    # ADEV96 — SHA-256 des OCTETS du PDF signé figé (``signed_pdf_key``), posé
    # une fois par ``cycle_vie._store_signed_pdf`` : le certificat dit quel
    # fichier exact a été remis. Vide sur les signatures antérieures.
    signed_pdf_sha256 = models.CharField(
        max_length=64, blank=True, default='',
        verbose_name='Empreinte SHA-256 du PDF signé')
    # ADEV99 — langue de la page au moment de signer (fr/en/ar) : la
    # confirmation part en anglais quand la proposition était lue en anglais.
    langue_page = models.CharField(
        max_length=5, blank=True, default='',
        verbose_name='Langue de la page à la signature')

    # ADEV96 / C (revue du 24/10/2026) — les chiffres de l'étude C&I SCELLÉS,
    # tels qu'ils ont été lus À L'ACCEPTATION : ``{"etude": <figures>}``
    # (``<figures>`` = ``modifiabilite.figures_etude_scellees`` normalisé par
    # :meth:`figures_canoniques`, ``null`` hors C&I). La vérification rejoue le
    # sceau v3 depuis CE champ, jamais en relançant le moteur : une évolution
    # du moteur après la signature ne rend plus le sceau irreproductible.
    # ``NULL`` = signature antérieure à ce champ (voir ``verifier_contenu``).
    figures_scellees = models.JSONField(
        null=True, blank=True,
        verbose_name="Chiffres de l'étude C&I scellés à la signature")

    class Meta:
        abstract = True

    @staticmethod
    def figures_canoniques(figures):
        """La forme CANONIQUE des chiffres scellés : l'aller-retour JSON du
        sceau (``sort_keys``, ``default=str`` — un ``Decimal`` devient son
        texte). Le JSON de cette forme est, à l'octet, celui que le sceau v3
        hache : stockée dans :attr:`figures_scellees`, elle reproduit le sceau.
        """
        import json
        return json.loads(json.dumps(
            figures, sort_keys=True, ensure_ascii=False, default=str))

    def figures_du_sceau(self):
        """``(True, figures)`` quand la signature porte ses chiffres scellés ;
        ``(False, None)`` pour une signature antérieure à ce champ (l'appelant
        domaine relit alors l'étude — chemin de compatibilité)."""
        stocke = self.figures_scellees
        if isinstance(stocke, dict) and 'etude' in stocke:
            return True, stocke['etude']
        return False, None

    def figures_a_rejouer(self, figures_relues=None):
        """Les chiffres que la vérification rejoue dans la part v3 : ceux
        STOCKÉS sur la signature font foi ; à défaut (signature antérieure au
        champ), ``figures_relues`` — l'étude relue par l'appelant domaine."""
        stockees, figures = self.figures_du_sceau()
        return figures if stockees else figures_relues

    @classmethod
    def _suffixe_sceau_etude(cls, figures, version):
        """ADEV96 — la part ÉTUDE du payload v3 (``''`` avant v3 : les
        empreintes v1/v2 déjà posées se reproduisent à l'octet).

        ``figures`` — les chiffres scellés de l'étude C&I
        (``domain.modifiabilite.figures_etude_scellees``), FOURNIS par
        l'appelant : lus frais à l'acceptation, relus de
        :attr:`figures_scellees` à la vérification — UNE fonction pour les
        deux. ``None`` (hors C&I) donne ``etude=null``. Ce module
        n'importe RIEN de la couche domaine : ``ventes.models`` le charge en
        tête, et le contrat import-linter « Core domain models stay
        decoupled » interdit toute arête modèles → domaine (qui atteint
        crm/stock/sav/installations par les services)."""
        if (version or cls.CONTENT_HASH_VERSION) < cls.CONTENT_HASH_V3:
            return ''
        import json
        return (f"|v{cls.CONTENT_HASH_V3}|etude="
                f"{json.dumps(figures, sort_keys=True, ensure_ascii=False, default=str)}")


class SuiviLienPublic(models.Model):
    """ADEV98 — le signal d'ouverture FIABLE du lien public (``ShareLink``).

    Le rendu serveur de la page (``X-Proposition-Rendu: ssr``) n'est plus
    compté comme une lecture humaine : un scanner de messagerie (SafeLinks,
    Proofpoint, Mimecast…) qui pré-charge le lien déclenchait compteur, note
    et notification. Il est seulement daté ici, en APERÇU, sans chatter ni
    notification ; la lecture humaine vient du beacon de la page
    (``proposal/<token>/vu/``) après quelques secondes de visibilité."""

    apercu_le = models.DateTimeField(
        null=True, blank=True,
        verbose_name='Dernier aperçu serveur (sans lecture humaine)')

    class Meta:
        abstract = True
