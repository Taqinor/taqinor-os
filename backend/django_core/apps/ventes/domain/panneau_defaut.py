"""D-ACAL-169 — LE panneau des choix AUTOMATIQUES d'une société, lu une fois.

Fondateur, 26/11/2026 : « always use 715w everywhere, and have somewhere in the stock to show the default used
pannels ». Le stock désigne UN panneau par société (``apps.stock.selectors_panneau_defaut``) ; ce module le traduit
pour les choix automatiques de ventes, avec UNE règle contre le piège des deux sources : la puissance et le produit
viennent TOUJOURS du même endroit —

* un panneau désigné UTILISABLE (non archivé, tarifé, reconnu comme panneau, nom et fiche d'accord sur le watt,
  puissance lisible) : sa puissance ET son produit — la puissance lue par CHAQUE moteur à sa façon (composition :
  le nom ; résolveur : son entrée ; C&I et pompage : la fiche), jamais un second chiffre ;
* sinon : la règle d'aujourd'hui, inchangée (``taille._AUTO_PANEL_WATT`` et le choix du catalogue à cette
  puissance) ; ``motif`` dit pourquoi au vendeur quand un panneau EST désigné mais inutilisable, et vaut ``None``
  quand aucun n'est désigné (rien n'est dit, rien ne change).

Aucune valeur de puissance n'est écrite ici : elle vient du produit désigné. Le défaut ne s'applique qu'aux
compositions NOUVELLES (création, aperçu d'un devis à naître) : chaque appelant le passe explicitement, un devis
existant ne le lit jamais.
"""
from dataclasses import dataclass, replace
import logging

logger = logging.getLogger(__name__)

#: Le panneau désigné porte une puissance que ni sa fiche ni son nom ne disent.
MOTIF_SANS_PUISSANCE = ("Le panneau désigné « {nom} » n'a pas de puissance lisible (fiche ou nom) : "
                        "les choix automatiques gardent leur règle d'aujourd'hui.")
#: Le panneau désigné est utilisable au stock, mais le moteur qui choisit ne l'accepte pas.
MOTIF_REFUSE = ("Le panneau par défaut « {nom} » n'est pas retenu par {moteur} ({raison}) : "
                "la règle d'aujourd'hui s'applique.")
#: ``source`` d'un panneau DÉSIGNÉ et utilisable au stock que le choix automatique ne peut pas retenir (puissance
#: illisible, ou refusé par le moteur qui choisit) — les autres valeurs sont celles du stock.
REFUSE = 'refuse'


@dataclass(frozen=True)
class PanneauAuto:
    """Le panneau d'un choix automatique : ``produit_id`` (``None`` = règle d'aujourd'hui), ``watt`` (sa
    puissance, sinon le repli d'aujourd'hui), ``nom``, ``motif`` (la phrase au vendeur, ou ``None``) et
    ``source`` (celle du stock, ou :data:`REFUSE`)."""

    produit_id: object = None
    watt: float = None
    nom: str = None
    motif: str = None
    source: str = 'aucun'

    @property
    def designe(self):
        return self.produit_id is not None

    def prefere(self, watt):
        """L'id du panneau par défaut quand ``watt`` est SA puissance, sinon ``None`` : une puissance tapée ou
        lue ailleurs garde la règle d'aujourd'hui (jamais la puissance d'un produit avec un autre)."""
        if not self.designe or not watt:
            return None
        try:
            return self.produit_id if int(float(watt)) == int(float(self.watt)) else None
        except (TypeError, ValueError):
            return None

    def refus(self, moteur, raison):
        """Le même choix réduit à la règle d'aujourd'hui, ``motif`` = pourquoi ``moteur`` refuse le désigné."""
        return PanneauAuto(watt=_repli(), nom=self.nom, source=REFUSE,
                           motif=MOTIF_REFUSE.format(nom=self.nom, moteur=moteur, raison=raison))

    def resume(self):
        """La forme ``contract_samples/panneau_par_defaut.json`` (cinq clés) de CE choix : ``pmax_wc`` n'est servi
        que pour un panneau que le choix automatique RETIENT — la puissance de départ d'un écran est donc
        toujours celle du produit que le serveur composera."""
        from apps.stock.selectors_panneau_defaut import MOTIF_AUCUN
        if self.designe:
            return {'produit_id': self.produit_id, 'nom': self.nom, 'pmax_wc': self.watt, 'source': self.source,
                    'motif': None}
        return {'produit_id': None, 'nom': None, 'pmax_wc': None, 'source': self.source,
                'motif': self.motif or MOTIF_AUCUN}


def _repli():
    from apps.ventes.domain.taille import _AUTO_PANEL_WATT
    return _AUTO_PANEL_WATT


def aucun_panneau_auto():
    """Le choix d'aujourd'hui, sans rien dire (aucun panneau désigné, ou un appelant qui n'en veut pas)."""
    return PanneauAuto(watt=_repli())


def panneau_auto(company):
    """Le :class:`PanneauAuto` de ``company`` (UNE lecture : le résumé du stock). ``None`` ⇒ aucun désigné."""
    if company is None:
        return aucun_panneau_auto()
    from apps.stock.selectors_panneau_defaut import AUCUN, DESIGNE, resume_panneau_par_defaut

    try:
        resume = resume_panneau_par_defaut(company)
    except Exception:  # noqa: BLE001 — stock illisible : règle d'aujourd'hui, jamais une panne (D-ENF22-BLE001)
        logger.warning('D-ACAL-169 : panneau par défaut illisible pour %r', company, exc_info=True)
        return aucun_panneau_auto()
    if resume.get('source') == DESIGNE:
        if resume.get('pmax_wc'):
            return PanneauAuto(produit_id=resume['produit_id'], watt=resume['pmax_wc'], nom=resume.get('nom'),
                               source=DESIGNE)
        return PanneauAuto(watt=_repli(), nom=resume.get('nom'), source=REFUSE,
                           motif=MOTIF_SANS_PUISSANCE.format(nom=resume.get('nom')))
    source = resume.get('source') or AUCUN
    return PanneauAuto(watt=_repli(), source=source, motif=None if source == AUCUN else resume.get('motif'))


def panneau_auto_composition(company, *, reglages=None, gamme_nom_devis=None):
    """Le :class:`PanneauAuto` que la COMPOSITION résidentielle accepte : le désigné doit être, comme tout panneau
    qu'elle compose, au catalogue de la société (``reglages.catalogue``), tarifé, hors pompage, classé panneau par
    son nom, et de la marque épinglée s'il y en a une. Refusé ⇒ la règle d'aujourd'hui (puissance ET produit) et
    la phrase qui dit pourquoi — jamais la puissance du désigné avec un autre produit."""
    auto = panneau_auto(company)
    if not auto.designe:
        return auto
    from apps.ventes.domain.catalogue import _has_price, _marque_correspond, classer_produit, est_article_pompage
    if reglages is None:
        from apps.ventes.domain.etape_composer import reglages_de_composition
        reglages = reglages_de_composition(company, gamme_nom_devis)
    produit = next((p for p in reglages.catalogue or () if getattr(p, 'pk', None) == auto.produit_id), None)
    if (produit is None or not _has_price(produit) or est_article_pompage(produit)
            or classer_produit(getattr(produit, 'nom', '') or '') != 'panneau'):
        return auto.refus('la composition', "il n'est pas parmi les panneaux tarifés qu'elle compose")
    marque = str((reglages.marques or {}).get('panneau') or '').strip()
    if marque and not _marque_correspond(produit, marque):
        return auto.refus('la composition', 'la marque épinglée des panneaux est « %s »' % marque)
    # Contrat du stock : chaque moteur prend le watt de SA lecture du produit — la composition lit le NOM
    # (``catalogue._parse_watt``), à défaut la puissance du stock (nom et fiche ne se contredisent jamais).
    from apps.ventes.domain.catalogue import _parse_watt
    return replace(auto, watt=_parse_watt(getattr(produit, 'nom', '') or '') or auto.watt)


def panneaux_de_la_taille(company, taille_kwc):
    """Une puissance DEMANDÉE (kWc) en panneaux du panneau automatique : ``(panneaux, watt)``, la conversion
    unique ``taille._residential_panel_count`` à la puissance du même panneau."""
    from apps.ventes.domain.taille import _residential_panel_count
    watt = panneau_auto_composition(company).watt
    return _residential_panel_count(taille_kwc=taille_kwc, panel_watt=watt), watt


def choisir_avec_defaut(auto, candidats, accepte, *, moteur, raison):
    """C&I et pompage — ``(candidat retenu ou None, motif)`` parmi ``candidats`` ``[(cle, produit, specs)]`` :
    le panneau désigné s'il y figure ET que ``accepte(cle)`` (l'acceptation propre au moteur), sinon ``None``
    (l'appelant applique sa règle d'aujourd'hui) avec la phrase qui dit pourquoi (``raison`` quand le moteur le
    refuse ; ``None`` sans désigné, ou le motif du stock quand le désigné est inutilisable)."""
    if auto is None or not auto.designe:
        return None, getattr(auto, 'motif', None)
    for candidat in candidats:
        if getattr(candidat[1], 'pk', None) == auto.produit_id:
            if accepte(candidat[0]):
                return candidat, None
            return None, auto.refus(moteur, raison).motif
    return None, auto.refus(moteur, "absent de ses panneaux au catalogue").motif
