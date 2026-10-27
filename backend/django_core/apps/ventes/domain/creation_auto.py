"""Le devis AUTOMATIQUE (SPL267, déplacé de ``domain/creation.py``).

Le dry-run que le vendeur approuve (``composer_devis_residentiel``), le devis
automatique depuis un lead (``build_devis_auto`` — dimensionnement, refus
motivé ; adaptateur de ``pipeline.appliquer``, origines ``auto`` / ``tunnel``),
le tunnel du site (``auto_devis_tunnel_actif``), la marque anti-doublon, la
note d'abstention et la planification Celery.

IMPORT AMONT DE ``domain/taille`` : ``composer_devis_residentiel`` porte
``panel_watt=_AUTO_PANEL_WATT`` comme VALEUR PAR DÉFAUT, évaluée à la
définition de la fonction — donc au chargement du module, avant tout pont de
bas de fichier. ``domain/taille`` est une FEUILLE : l'import ne peut pas
boucler. Les autres noms lus ailleurs dans ``domain/`` sont importés EN BAS
de ce fichier, en visant le module qui porte le corps (``creation`` pour
``_structure_demandee``, ``creation_calepinage`` pour l'arbitrage) — jamais la
façade. Déplacement pur : corps octet-identiques, prouvé par
``tests/golden/split_dm_auto.json``.

NOM DU LOGGER FIGÉ sur ``apps.ventes.services`` : des tests capturent ce nom.
"""
from decimal import Decimal
import logging

from apps.ventes.domain.taille import _AUTO_PANEL_WATT

logger = logging.getLogger("apps.ventes.services")


#: U3 — les trois scénarios batterie qu'un appelant peut demander POUR CE
#: DEVIS-LÀ, sans jamais réécrire la fiche du lead.
SCENARIOS_DEMANDABLES = ('sans', 'avec', 'les_deux')


def _ecrire_devis_auto_par_pipeline(*, company, user, lead, creer, lignes,
                                    mode_installation):
    """ADEV25 (C-ADEV-036) — le devis automatique commercial/industriel ou
    agricole est écrit par le PIPELINE, comme le résidentiel : création
    numérotée + ``appliquer(MODE_ECRIRE)`` (écrivain unique, provenance,
    instantané) sous UNE ``transaction.atomic()`` — une erreur au milieu ne
    laisse aucun devis partiel — puis ``MODE_RAFRAICHIR`` hors transaction
    (études + caches : kWc et marge interne).

    ``lignes`` : dicts ``{produit_id, designation, quantite, prix_unitaire}``
    déjà arrêtés par le moteur (jamais recomposés ici)."""
    from django.db import transaction

    from apps.ventes.domain.pipeline import MODE_ECRIRE, MODE_RAFRAICHIR
    from apps.ventes.models import Devis
    from apps.ventes.utils.company_settings import create_numbered

    composition = [
        {'produit': ligne['produit_id'],
         'designation': ligne['designation'],
         'quantite': str(ligne['quantite']),
         'prix_unitaire': str(ligne['prix_unitaire']),
         'ordre': ordre,
         # Fondateur 26/10/2026 — C&I à deux options : la ligne dit son option.
         **({'variante': ligne['variante']} if ligne.get('variante') else {})}
        for ordre, ligne in enumerate(lignes)]
    with transaction.atomic():
        devis = create_numbered(Devis, company, 'devis', creer)
        appliquer(devis, IntentionDevis(
            origine=ORIGINE_AUTO, mode=MODE_ECRIRE, company=company,
            user=user, lead=lead, mode_installation=mode_installation,
            composition=composition))
    appliquer(devis, IntentionDevis(
        origine=ORIGINE_AUTO, mode=MODE_RAFRAICHIR, company=company,
        user=user, lead=lead, mode_installation=mode_installation))
    devis.refresh_from_db()
    return devis


def _build_devis_auto_ci(*, lead, user, company, taux_tva=None,
                         journal_auto=None, target_kwc=None):
    """CIQ120 — devis automatique COMMERCIAL / INDUSTRIEL par le serveur.

    Chaîne : ``etude_ci.etudier_ci`` (entrées du lead, CIQ405 ; garde
    kWh-vs-factures) → taille retenue (ou ``target_kwc`` / la taille
    souhaitée du lead, SOUVERAINES) → composition du moteur → devis BROUILLON
    (référence ``utils/references.py``, lignes par l'écrivain unique) → étude
    v2 écrite UNE fois par le rafraîchisseur (taille donnée = les lignes).
    Tension, phases et puissance souscrite partent dans les ENTRÉES. Le type
    du lead n'est JAMAIS changé (convention 20). Aucun statut touché (#4).
    Refus ``AutoDevisError`` nommant la donnée manquante ou la cause moteur.
    """
    # APAR49 — taux absent ⇒ taux STANDARD de la société (jamais 20 codé).
    if taux_tva is None:
        from apps.ventes.utils.company_settings import tva_standard
        taux_tva = tva_standard(company)
    from apps.crm.services import resolve_client_for_lead
    from apps.ventes.domain.etude_ci import (
        entrees_pour_etude_params, etudier_ci, refus_devis_auto_ci)
    from apps.ventes.domain.etude_ci_batterie import lignes_des_options
    from apps.ventes.models import Devis

    taille = target_kwc if target_kwc not in (None, '') else getattr(
        lead, 'taille_souhaitee_kwc', None)
    corps = {'mode': lead.type_installation}
    if taille not in (None, ''):
        try:
            taille = float(taille)
        except (TypeError, ValueError):
            raise AutoDevisError('Puissance cible invalide.', field='target_kwc')
        if taille <= 0:
            raise AutoDevisError('La puissance cible doit être supérieure à zéro.',
                                 field='target_kwc')
        corps['taille_explicite_kwc'] = taille
    etude = etudier_ci(company, corps, lead=lead)
    refus = refus_devis_auto_ci(etude)
    if refus:
        raise AutoDevisError(refus[0], field=refus[1])
    # Fondateur 26/10/2026 — « sans » et « avec batterie » par défaut, comme
    # le résidentiel ; le choix du lead (``batterie_souhaitee``) restreint.
    lignes, scenario = lignes_des_options(etude, lead)
    if not any(ligne['produit_id'] for ligne in lignes):
        raise AutoDevisError('Aucun article C&I chiffré à composer.',
                             field='composition')

    client = resolve_client_for_lead(lead)
    entrees = entrees_pour_etude_params(etude.get('entrees_resolues'))
    entrees['mode'] = lead.type_installation
    if scenario:
        entrees['scenario'] = scenario

    def _create(ref):
        return Devis.objects.create(
            company=company, reference=ref, client=client, lead=lead,
            statut=Devis.Statut.BROUILLON, created_by=user,
            taux_tva=taux_tva, mode_installation=lead.type_installation,
            etude_params=entrees)

    devis = _ecrire_devis_auto_par_pipeline(
        company=company, user=user, lead=lead, creer=_create, lignes=lignes,
        mode_installation=lead.type_installation)
    if journal_auto is not None:
        # ADEV79 (D-ACI-2=a) — même forme que l'agricole : les postes « à
        # chiffrer après visite » hors total, NOMMÉS, puis les alertes de l'étude.
        alertes = [{'code': 'a_chiffrer_visite', 'champ': 'composition',
                    'message': ('« %s » à chiffrer après la visite technique : hors '
                                'total, devis estimé sous réserve de visite.' % poste)}
                   for poste in (etude.get('composition') or {}).get('a_chiffrer_visite') or []]
        alertes += [dict(a) for a in etude.get('alertes') or []
                    if a.get('niveau') in ('alerte', 'bloquant')
                    and a.get('code') != 'a_chiffrer_visite']
        journal_auto['alertes'] = alertes
    logger.info('Auto-devis C&I %s: %s kWc (lead %s, company %s)', devis.reference,
                (etude.get('taille') or {}).get('retenue_kwc'), getattr(lead, 'pk', '?'),
                getattr(company, 'id', '?'))
    return devis


def build_devis_auto(*, lead, user, company, taux_tva=None,
                     remise_globale=Decimal('0'), target_kwc=None,
                     scenario=None, etude_extra=None, plafond_toit=None,
                     journal_auto=None, origine=None,
                     structure_produit_id=None, structure_type=None):
    """Crée un devis RÉSIDENTIEL automatiquement dimensionné depuis la fiche lead.

    Dimensionne le champ PV par le MOTEUR HORAIRE (ordre fondateur du
    29/08/2026 : « ALL sizing should go through the new sizing tool ») — sauf
    si une PUISSANCE est demandée (``target_kwc``, sinon la taille souhaitée du
    lead), auquel cas cette puissance est souveraine. Puis compose PAR DÉFAUT
    la forme DEUX OPTIONS
    (« sans batterie » ET « avec batterie » — U2 ; un ``batterie_souhaitee``
    explicite du lead, « avec » ou « sans », reste souverain et compose cette
    option-là seule) et confie la création à ``pipeline.appliquer``
    (sélection catalogue, numérotation anti-collision, devis ``brouillon``). Lève
    ``AutoDevisError`` (→ 422) si le marché n'est pas résidentiel ou si aucune
    donnée de dimensionnement n'est exploitable — l'agent demande alors la donnée
    plutôt que de produire un devis vide. Ne change aucun statut (règle #4).

    ``origine`` (QJR96) — laquelle des deux origines SANS COMMERCIAL DANS LA
    BOUCLE demande ce devis : ``'auto'`` (LE DÉFAUT — le bouton « devis
    automatique » de la fiche lead) ou ``'tunnel'`` (le webhook du site, cf.
    :func:`creer_devis_automatique_depuis_lead`). Elle NE DÉCIDE AUCUNE LIGNE :
    les deux traversent le même pipeline, avec les mêmes entrées et le même
    composeur — elle NOMME seulement d'où vient la demande.

    Trois réglages POUR CE DEVIS-LÀ (U3), qui ne réécrivent JAMAIS la fiche du
    lead — c'est un choix ponctuel du commercial, pas une correction du lead :

    * ``target_kwc`` — puissance cible demandée (EZ5) ; passe devant la taille
      souhaitée du lead ET devant le dimensionnement du moteur.
    * ``scenario`` — ``'sans'`` / ``'avec'`` / ``'les_deux'`` ; passe devant le
      ``batterie_souhaitee`` du lead. Absent : c'est le lead qui décide, et son
      silence vaut « les deux » (U2).
    * ``etude_extra`` — clés d'étude à FUSIONNER dans ``etude_params`` (les
      factures mensuelles réelles du contrat PACT10, par exemple). Elles
      complètent ce que la construction a déjà écrit, sans jamais écraser le
      scénario arrêté ci-dessus.
    * ``structure_produit_id`` / ``structure_type`` (STKCAT8/STKCAT9) — la
      STRUCTURE du kit. Absents (LE DÉFAUT), c'est LE LEAD qui décide : son
      ``structure_produit`` épinglé d'abord, sa préférence acier/aluminium
      ensuite, l'acier historique à défaut (cf. :func:`_structure_demandee`).
      Fournis, ils passent devant le lead sans jamais réécrire sa fiche —
      comme les trois réglages ci-dessus.

    AUTO-PIPELINE (26/08/2026) — deux paramètres de plus, tous deux OPTIONNELS
    et sans effet quand ils sont absents (l'endpoint ``/devis/auto/`` est donc
    inchangé) :

    * ``plafond_toit`` — borne PHYSIQUE dure en panneaux (cf.
      ``plafond_physique_du_contour``). Elle ne peut que RÉDUIRE : jamais une
      cible relevée, jamais un chiffre ajouté au devis.
    * ``journal_auto`` — dict que l'appelant fournit pour recevoir ce qui s'est
      décidé sans lui (``plafond_applique``, ``panneaux_avant_plafond``,
      ``contour_client``), afin de pouvoir l'écrire NOIR SUR BLANC dans
      l'historique du lead. Rien n'y est écrit s'il n'est pas fourni.

    Et, quand le lead porte un tracé de toit, le layout du devis embarque
    désormais ce tracé comme VRAIE zone de calepinage
    (``zone_toit_depuis_contour``) : l'écran 3D ouvre sur le toit du client,
    déjà pavé, au lieu d'une carte vierge.
    """
    # APAR49 — taux absent ⇒ taux STANDARD de la société (jamais 20 codé).
    if taux_tva is None:
        from apps.ventes.utils.company_settings import tva_standard
        taux_tva = tva_standard(company)
    marche = (getattr(lead, 'type_installation', '') or '').lower()
    if marche in ('commercial', 'industriel'):
        # CIQ120 — le C&I passe par LE moteur serveur (D-CIQ-0), origine
        # « auto » seulement : le tunnel du site reste refusé pour le C&I.
        if (origine or ORIGINE_AUTO) != ORIGINE_AUTO:
            raise AutoDevisError(
                "Le devis automatique depuis le site n'est pas ouvert au "
                "commercial et à l'industriel : le commercial le lance depuis "
                "la fiche lead.", field='type_installation')
        return _build_devis_auto_ci(lead=lead, user=user, company=company,
                                    taux_tva=taux_tva, journal_auto=journal_auto,
                                    target_kwc=target_kwc)
    if marche == 'agricole':
        # AGR124 — l'agricole passe par LE moteur serveur (D-AGR-1), origine
        # « auto » seulement : le tunnel du site reste refusé.
        if (origine or ORIGINE_AUTO) != ORIGINE_AUTO:
            raise AutoDevisError(
                "Le devis automatique depuis le site n'est pas ouvert à "
                "l'agricole : le commercial le lance depuis la fiche lead.",
                field='type_installation')
        return _build_devis_auto_agricole(
            lead=lead, user=user, company=company, taux_tva=taux_tva,
            journal_auto=journal_auto, target_kwc=target_kwc)
    if marche and marche != 'residentiel':
        raise AutoDevisError(
            "L'auto-devis ne gère que le résidentiel pour l'instant. Pour "
            "l'industriel/commercial ou l'agricole, utilisez l'écran générateur "
            "de devis.",
            field='type_installation')

    # Le corps résidentiel vit dans ``creation_auto_residentiel`` (déplacé tel quel).
    return _build_devis_auto_residentiel(
        lead=lead, user=user, company=company, taux_tva=taux_tva,
        remise_globale=remise_globale, target_kwc=target_kwc,
        scenario=scenario, etude_extra=etude_extra, plafond_toit=plafond_toit,
        journal_auto=journal_auto, origine=origine,
        structure_produit_id=structure_produit_id,
        structure_type=structure_type)


def auto_devis_tunnel_actif(company):
    """La société veut-elle des devis automatiques depuis le tunnel ?

    Réglage de société (``parametres.CompanyProfile.devis_auto_depuis_tunnel``),
    ACTIF par défaut — c'est le flux que le fondateur a demandé. Une société
    qui n'a pas encore de profil hérite donc du défaut, jamais d'un « non »
    silencieux ; un profil illisible vaut « non » (on ne crée pas de document
    sur une lecture ratée).
    """
    try:
        from apps.parametres.models import CompanyProfile
        profil = CompanyProfile.objects.filter(company=company).first()
    except Exception:  # noqa: BLE001 — table absente / migration en cours (D-ENF22-BLE001)
        logger.warning(
            'Auto-devis: profil de société illisible (company %s) — '
            'création automatique désactivée par prudence.',
            getattr(company, 'pk', '?'))
        return False
    if profil is None:
        return True
    return bool(getattr(profil, 'devis_auto_depuis_tunnel', True))


_MARQUE_AUTO_DEVIS = 'ventes.auto_devis'


def _liberer_marque_auto_devis(company, lead_id):
    """F5 — RELÂCHE la marque d'achèvement d'un lead dont la création a échoué.

    ``dedupe_event`` pose sa ligne AVANT le travail — c'est ce qui lui permet
    de départager deux workers simultanés. Mais laissée en place après un
    échec, cette même ligne devient une porte fermée DÉFINITIVEMENT : un lead
    sans facture aujourd'hui, ou un catalogue momentanément incomplet, et plus
    jamais personne — ni un rejeu, ni un appel manuel du service — ne pourrait
    lui créer son devis automatique. La marque doit donc dire « c'est FAIT »,
    pas « ça a été tenté ».

    Best-effort et silencieuse sur erreur : elle est appelée depuis des
    chemins d'exception, et ne doit jamais masquer l'erreur d'origine.
    """
    try:
        from core.idempotency import ProcessedWebhookEvent
        ProcessedWebhookEvent.objects.filter(
            company=company, source=_MARQUE_AUTO_DEVIS,
            event_id=str(lead_id)).delete()
    except Exception:  # noqa: BLE001 — jamais au-dessus de l'erreur d'origine (D-ENF22-BLE001)
        logger.warning(
            'Auto-devis: marque de dédup non relâchée pour le lead %s — un '
            'prochain essai sera refusé.', lead_id, exc_info=True)


def corps_note_refus_auto_devis(exc):
    """Le CORPS de la note d'abstention — pur, testable sans base.

    Il NOMME le motif : le champ que le moteur a trouvé manquant, et le
    message français qu'il oppose déjà au commercial sur l'écran de devis.
    C'est délibérément le MÊME texte des deux côtés : un lead refusé et un
    devis refusé le sont pour la même raison, et la lire deux fois formulée
    autrement ferait croire à deux problèmes.

    Le corps est DÉTERMINISTE (aucune date, aucun compteur) — c'est ce qui
    permet à la garde anti-répétition de reconnaître le même motif d'un rejeu
    à l'autre.
    """
    champ = getattr(exc, 'field', None) or 'donnée manquante'
    message = (str(exc) or '').strip()
    corps = ('Devis automatique NON créé depuis le tunnel — le '
             'dimensionnement s\'abstient (%s).' % champ)
    if message:
        corps += ' Motif : %s' % message
    corps += (' Complétez la fiche puis créez le devis à la main : rien n\'a '
              'été écrit sur ce lead.')
    return corps


def _noter_refus_auto_devis(company, lead_id, lead, exc):
    """Pose la note d'abstention. BEST-EFFORT : ne remonte jamais.

    Un chemin d'observabilité n'a pas le droit de transformer une abstention
    (cas normal) en erreur : l'appelant rend ``None`` dans les deux cas.
    """
    try:
        from apps.crm.services import ajouter_note_lead_si_nouvelle
        ajouter_note_lead_si_nouvelle(
            company=company, lead_id=lead_id,
            user=getattr(lead, 'owner', None),
            body=corps_note_refus_auto_devis(exc))
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant (D-ENF22-BLE001)
        logger.warning(
            'Auto-devis: note d\'abstention non posée sur le lead %s.',
            lead_id, exc_info=True)


def creer_devis_automatique_depuis_lead(*, lead_id, company_id):
    """AUTO-PIPELINE — le devis brouillon d'un lead arrivé du tunnel.

    Rend le ``Devis`` créé, ou ``None`` — et ``None`` n'est JAMAIS une erreur :
    c'est le cas normal quand le lead n'a pas de quoi être chiffré. LES PORTES,
    dans l'ordre, et aucune n'est nouvelle :

    1. **Société / lead lisibles** — lecture cross-app par
       ``crm.selectors.get_company_lead`` (jamais ``crm.models``).
    2. **Réglage de société** — ``auto_devis_tunnel_actif``.
    3. **IDEMPOTENCE — un lead, un devis**, en DEUX gardes distinctes, car
       elles n'attrapent pas la même chose :

       a. une lecture « ce lead porte-t-il déjà un devis ? » — elle couvre le
          cas courant (webhook re-livré plus tard, tâche rejouée après coup,
          devis déjà saisi à la main par un commercial) ;
       b. une MARQUE D'ACHÈVEMENT en base
          (``core.idempotency.dedupe_event``, contrainte d'unicité sur
          ``(company, source, event_id)``) — elle seule départage deux
          exécutions SIMULTANÉES, que la lecture (a) laisserait passer
          ensemble. Il n'y a ici NI transaction englobante, NI
          ``select_for_update`` : c'est la contrainte d'unicité qui arbitre,
          et le perdant de l'insertion abandonne sans rien créer.

       La marque n'est gardée QUE si un devis a réellement été créé : tout
       échec la relâche (voir ``_liberer_marque_auto_devis``), sans quoi un
       lead non chiffrable aujourd'hui — facture manquante, catalogue
       incomplet — resterait définitivement fermé à un appel ultérieur.
    4. **Assez de donnée RÉELLE** — c'est ``build_devis_auto`` qui tranche,
       avec EXACTEMENT les portes qu'il oppose déjà au commercial
       (``AutoDevisError`` : marché non résidentiel, aucune facture d'hiver ni
       taille souhaitée, marque épinglée absente du stock). Un lead incomplet
       ou parasite ne reçoit donc rien du tout, et surtout pas un devis vide.

    Le tracé du client, s'il existe, entre dans le layout du devis
    (``zone_toit_depuis_contour``) et borne physiquement la taille
    (``plafond_physique_du_contour``). Sans tracé : un devis automatique
    ordinaire, sans calepinage — le comportement d'aujourd'hui.
    """
    from django.db import transaction

    from apps.crm.selectors import get_company_lead
    from authentication.models import Company
    from core.idempotency import dedupe_event

    from ..models import Devis

    company = Company.objects.filter(pk=company_id).first()
    if company is None:
        return None
    if not auto_devis_tunnel_actif(company):
        logger.info(
            'Auto-devis: désactivé pour la société %s — lead %s non chiffré.',
            company_id, lead_id)
        return None

    lead = get_company_lead(company, lead_id)
    if lead is None:
        return None

    # PORTE 3a — un lead qui porte déjà un devis (automatique OU saisi à la
    # main) n'en reçoit jamais un second.
    if Devis.objects.filter(company=company, lead=lead).exists():
        logger.info(
            'Auto-devis: le lead %s porte déjà un devis — rien créé.', lead_id)
        return None

    # PORTE 3b — LA COURSE. Deux livraisons simultanées du même webhook, ou un
    # rejeu Celery concurrent (``acks_late``), peuvent franchir la porte 3a
    # ensemble : seule une contrainte d'unicité en base les départage. C'est
    # EXACTEMENT la primitive que le webhook utilise déjà pour ses propres
    # rejeux (``core.idempotency.dedupe_event``) — on ne s'en réinvente pas une
    # seconde. Perdant = on ne crée rien, en silence : l'autre worker s'en
    # charge.
    if not dedupe_event(company=company, source=_MARQUE_AUTO_DEVIS,
                        event_id=str(lead_id)):
        logger.info(
            'Auto-devis: création déjà en cours/faite pour le lead %s '
            '(dédup) — rien créé.', lead_id)
        return None

    journal_auto = {}
    # Le ``try`` couvre TOUT ce qui suit la pose de la marque — y compris les
    # lectures catalogue/géométrie — et il ENVELOPPE la transaction (et non
    # l'inverse) : un refus de dimensionnement doit défaire ce que la
    # construction aurait pu commencer, jamais laisser un devis à moitié écrit.
    # F5 — chaque sortie en échec RELÂCHE la marque : elle atteste d'un devis
    # CRÉÉ, jamais d'une tentative.
    try:
        # Lectures pures (catalogue + géométrie du tracé) — hors transaction.
        produit_panneau, _societe = _panneau_pour_calepinage(
            {'panelWatt': _AUTO_PANEL_WATT}, company=company, devis=None)
        plafond = plafond_physique_du_contour(
            contour_client_lnglat(lead), produit_panneau)
        with transaction.atomic():
            devis = build_devis_auto(
                lead=lead,
                # Le devis est attribué au commercial qui possède le lead
                # quand il y en a un, à personne sinon — jamais à un
                # utilisateur inventé pour la circonstance.
                user=getattr(lead, 'owner', None),
                company=company, plafond_toit=plafond,
                journal_auto=journal_auto,
                # QJR96 — L'ORIGINE DÉCLARÉE AU PIPELINE. Le tunnel n'est pas un
                # autre moteur : c'est le MÊME geste, demandé par le webhook du
                # site au lieu du bouton d'un commercial. Elle ne décide aucune
                # ligne — elle NOMME la demande, pour le journal et pour les
                # propriétaires d'étude.
                origine=ORIGINE_TUNNEL)
    except AutoDevisError as exc:
        _liberer_marque_auto_devis(company, lead_id)
        logger.info(
            'Auto-devis: lead %s non chiffrable (%s) — aucun devis créé.',
            lead_id, exc.field or 'donnée manquante')
        # ── F6 (revue Fable, 29/08/2026) — UN REFUS SE VOIT SUR LE LEAD ──
        #
        # Le refus ne laissait qu'une ligne de journal serveur. Côté
        # commercial, le lead arrivait NU, sans devis et sans un mot — alors
        # que la veille les mêmes leads en recevaient un. Le silence se lisait
        # comme une panne ; c'est une ABSTENTION, et elle a un motif nommable.
        #
        # UNE FOIS PAR MOTIF, JAMAIS PAR REJEU : le refus relâche la marque de
        # dédup (une donnée manquante aujourd'hui ne ferme pas le lead pour
        # toujours), si bien qu'une re-livraison du webhook rejoue le même
        # refus. ``ajouter_note_lead_si_nouvelle`` (apps.crm.services — la
        # frontière cross-app, jamais ``crm.models``) ne repose pas un corps
        # identique ; un motif DIFFÉRENT, lui, mérite bien sa note.
        _noter_refus_auto_devis(company, lead_id, lead, exc)
        return None
    except Exception:
        _liberer_marque_auto_devis(company, lead_id)
        raise

    # ── LA BOUCLE DE VÉRIFICATION DU COMMERCIAL ───────────────────────────
    # Le devis porte le lead : il apparaît donc DÉJÀ dans la liste des devis et
    # sur la fiche du lead. Ce qui manquait, c'est le REÇU daté qui dit d'où il
    # sort et qu'il attend une relecture. Note d'historique (chatter existant,
    # aucun mécanisme neuf), best-effort : un devis créé ne doit jamais être
    # remis en cause par une note qui échoue.
    corps = (
        'Devis automatique créé depuis le tunnel — à vérifier : %s.'
        % devis.reference)
    if journal_auto.get('contour_client'):
        corps += (
            ' Le calepinage part du tracé du client (%d points) : ouvrez '
            '« Concevoir la toiture (3D) » pour le contrôler.'
            % journal_auto['contour_client'])
    if journal_auto.get('plafond_applique'):
        corps += (
            ' Taille ramenée de %d à %d panneaux : la surface du tracé du '
            'client ne peut physiquement pas en porter davantage.'
            % (journal_auto['panneaux_avant_plafond'],
               journal_auto['plafond_applique']))
    try:
        from apps.crm.services import ajouter_note_lead
        ajouter_note_lead(company=company, lead_id=lead_id,
                          user=getattr(lead, 'owner', None), body=corps)
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant (D-ENF22-BLE001)
        logger.warning(
            'Auto-devis %s: note d\'historique échouée sur le lead %s.',
            devis.reference, lead_id, exc_info=True)

    logger.info('Auto-devis %s créé automatiquement pour le lead %s '
                '(company %s).', devis.reference, lead_id, company_id)
    return devis


def planifier_devis_automatique_pour_lead(lead_id, company_id):
    """Met la création du devis automatique EN FILE — jamais en ligne.

    Point d'entrée cross-app : ``apps.crm`` appelle CETTE fonction (règle
    services.py), et rien d'autre de ``ventes``.

    Contrairement à ``planifier_resynchronisation_produit`` (PVSYNC), il n'y a
    ici **aucun repli en ligne**, et c'est délibéré : le webhook du site est
    une surface PUBLIQUE dont le temps de réponse est un engagement, alors que
    la composition + l'étude horaire se comptent en secondes. Un courtier
    injoignable fait donc simplement retomber ce lead-là sur le chemin
    d'aujourd'hui — le commercial crée son devis à la main — ce qui est un
    dégradé acceptable ; un webhook qui met cinq secondes à répondre ne l'est
    pas. L'échec est journalisé, jamais avalé en silence.
    """
    from ..tasks import task_devis_automatique_depuis_lead

    try:
        task_devis_automatique_depuis_lead.apply_async(
            args=[lead_id, company_id], retry=False)
    except Exception as exc:  # noqa: BLE001 — courtier indisponible (D-ENF22-BLE001)
        logger.warning(
            'Auto-devis: file Celery indisponible (%s) — le lead %s n\'aura '
            'pas de devis automatique (création manuelle inchangée).',
            exc, lead_id)


# ── PONTS M3 : noms hébergés ailleurs ────────────────────────────────────────
# Imports EN BAS DE FICHIER, visant le module qui PORTE chaque corps.
from apps.ventes.domain.geometrie import (  # noqa: E402 — fin de module (anti-cycle) (D-ENF22)
    _panneau_pour_calepinage,
    contour_client_lnglat,
    plafond_physique_du_contour,
)
from apps.ventes.domain.pipeline import (  # noqa: E402 — fin de module (anti-cycle) (D-ENF22)
    ORIGINE_AUTO,
    ORIGINE_TUNNEL,
    IntentionDevis,
    appliquer,
)
from apps.ventes.domain.taille import (  # noqa: E402 — fin de module (anti-cycle) (D-ENF22)
    AutoDevisError,
)
from apps.ventes.domain.creation_auto_residentiel import (  # noqa: E402,F401 — fin de module (anti-cycle) ; composer_devis_residentiel ré-exporté (D-ENF22)
    _build_devis_auto_residentiel,
    composer_devis_residentiel,
)
from apps.ventes.domain.creation_auto_agricole import (  # noqa: E402 — fin de module (anti-cycle) (D-ENF22)
    _build_devis_auto_agricole,
)
