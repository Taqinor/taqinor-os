"""Événements catalogue — un produit change, les devis suivent.

La resynchronisation d'un devis après modification d'un produit, le
récepteur qui l'observe et la planification asynchrone de la reprise. Le
prix d'une ligne ne suit le catalogue que si elle était AU PRIX CATALOGUE
sans remise : un prix négocié reste intouchable.

QJR76 (M3) — DÉPLACEMENT PUR depuis ``apps/ventes/services.py``, dernier de la
vague : après lui, ``services.py`` n'est plus qu'une façade de ré-exports. Les
corps sont recopiés à l'identique ; la seule retouche possible est mécanique
(`from .x` → `from ..x`, MÊME cible).

ORDRE DE CHARGEMENT : ``services.py`` importe ``domain/`` à la toute fin ; un
module de ``domain/`` importe en BAS de fichier les noms qu'il lit ailleurs, et
il vise TOUJOURS le module qui porte le corps — jamais la façade.

NOM DU LOGGER FIGÉ sur ``apps.ventes.services`` : des tests capturent ce nom.
"""
from decimal import Decimal
import logging

logger = logging.getLogger("apps.ventes.services")


# ── PVSYNC — le catalogue bouge, les devis VIVANTS suivent ───────────────────
#
# Jusqu'ici, corriger un prix ou renommer une référence dans le Stock laissait
# les devis déjà rédigés parler de l'ancien monde : le commercial rouvrait un
# brouillon de la semaine dernière et y lisait un prix que la société ne
# pratique plus. La resynchronisation de calepinage (PV18) savait déjà guérir
# un devis, mais seulement quand quelqu'un rouvrait la conception 3D — donc
# jamais pour un devis qu'on ne rouvre pas.
#
# Ce bloc rend la propagation ÉVÉNEMENTIELLE : ``stock`` annonce sur le bus M6
# qu'une référence a changé (``core.events.produit_modifie``), ``ventes`` s'y
# abonne dans son ``apps.py`` ``ready()`` et délègue à une tâche Celery. Les
# BORNES sont le sujet, et elles sont toutes dures :
#
#   1. **Seul le statut BROUILLON bouge (D-ASTK-1, 06/10/2026).** Un devis
#      ENVOYÉ reste figé au montant du PDF que le client tient : il reçoit
#      seulement une note de chatter « devis envoyé conservé ; réviser pour
#      l'appliquer ». Un devis accepté, refusé ou expiré est un document
#      CONTRACTUEL : jamais lu ici. Le statut est LU, JAMAIS écrit (règle #4)
#      — les écritures se limitent à ``LigneDevis`` et à des notes de chatter.
#   2. **Une ligne NÉGOCIÉE n'est jamais recalée.** Le prix ne suit le
#      catalogue que si la ligne portait EXACTEMENT l'ANCIEN prix catalogue et
#      aucune remise de ligne ; la désignation ne suit que si elle valait
#      exactement l'ANCIEN nom. C'est pour cela que l'événement transporte
#      l'AVANT : après l'écriture du produit, comparer au prix COURANT ne
#      prouverait plus rien. Tout écart est CONSERVÉ et DIT.
#   3. **Aucune cascade possible.** Ce chemin n'écrit jamais un ``Produit`` :
#      il ne peut donc pas ré-émettre ``produit_modifie`` (garde structurelle,
#      pas une convention — et un test la vérifie).
#   4. **Silencieux quand il n'y a rien à dire.** Zéro ligne modifiée ⇒ aucune
#      note de resynchronisation. Les notes « envoyé conservé » et « prix
#      négocié conservé » (ASTK141) sont dédoublonnées : rejouer le même
#      événement est donc un no-op complet (la tâche est at-least-once : elle
#      DOIT être idempotente).
#   5. **Une société à la fois.** La requête est cantonnée à la société de
#      l'événement — le devis d'un autre tenant n'est jamais lu, encore moins
#      réécrit.

#: Résumé FRANÇAIS d'un champ produit, pour la note de chatter.
LIBELLES_CHAMPS_PRODUIT = {
    'nom': 'désignation',
    'prix_vente': 'prix',
    'tva': 'TVA',
    'prix_fixe_ht': 'forfait fixe',
    'prix_par_panneau_ht': 'forfait par panneau',
}

#: ASTK142 — les champs de barème forfaitaire de l'événement.
CHAMPS_FORFAIT = ('prix_fixe_ht', 'prix_par_panneau_ht')


def _valeurs_champ(champs, nom_champ):
    """``(avant, après)`` d'un champ du payload d'événement, ou ``(None, None)``.

    Le payload transporte des CHAÎNES (il traverse une file Celery) ; on ne les
    convertit pas ici, chaque appelant sait ce qu'il attend.
    """
    paire = (champs or {}).get(nom_champ)
    if not isinstance(paire, (list, tuple)) or len(paire) != 2:
        return None, None
    return paire[0], paire[1]


def _decimal_ou_none(valeur):
    """``Decimal`` d'une chaîne du payload — ``None`` si elle n'en est pas un."""
    if valeur in (None, ''):
        return None
    try:
        return Decimal(str(valeur))
    except (TypeError, ValueError, ArithmeticError):
        return None


def _ecarter_valeurs_perimees(produit, nouveau_prix, nouveau_nom):
    """ASTK140 — ``(prix, nom)`` du payload encore COURANTS, ``None`` sinon.

    Relit le produit EN BASE (jamais l'instance reçue, qui peut dater de
    l'émission) et compare chaque « après » à la valeur courante : un écart
    prouve qu'une écriture plus récente a suivi — l'événement est périmé pour
    ce champ, son propre événement (plus récent) fera foi.
    """
    if nouveau_prix is None and not nouveau_nom:
        return nouveau_prix, nouveau_nom
    courant = (type(produit)._default_manager
               .filter(pk=getattr(produit, 'pk', None))
               .values('prix_vente', 'nom').first())
    if courant is None:
        return None, None
    reference = getattr(produit, 'sku', None) or getattr(produit, 'pk', '?')
    if nouveau_prix is not None:
        prix_courant = _decimal_ou_none(courant.get('prix_vente'))
        if prix_courant != nouveau_prix:
            logger.info(
                'PVSYNC: événement périmé ignoré pour le prix du produit %s '
                '(payload %s, catalogue courant %s).',
                reference, nouveau_prix, prix_courant)
            nouveau_prix = None
    if nouveau_nom and (courant.get('nom') or '') != nouveau_nom:
        logger.info(
            'PVSYNC: événement périmé ignoré pour la désignation du produit '
            '%s (payload %r, catalogue courant %r).',
            reference, nouveau_nom, courant.get('nom'))
        nouveau_nom = None
    return nouveau_prix, nouveau_nom


def _etendus_courants(produit, champs):
    """ASTK142 — ``(tva, forfait)`` encore COURANTS (fraîcheur d'ASTK140).

    ``tva`` = ``(ancienne, nouvelle)`` Decimals ou ``None`` ; ``forfait`` =
    ``{champ: (ancien, nouveau)}`` des champs de barème dont l'« après » vaut
    encore la valeur en base. Un « après » périmé est ignoré (journalisé).
    """
    paires = {nom: _valeurs_champ(champs, nom)
              for nom in ('tva',) + CHAMPS_FORFAIT}
    if not any(n is not None for _a, n in paires.values()):
        return None, {}
    courant = (type(produit)._default_manager
               .filter(pk=getattr(produit, 'pk', None))
               .values('tva', *CHAMPS_FORFAIT).first())
    if courant is None:
        return None, {}
    reference = getattr(produit, 'sku', None) or getattr(produit, 'pk', '?')
    gardes = {}
    for nom, (ancien, nouveau) in paires.items():
        if nouveau is None:
            continue
        nouveau_dec = _decimal_ou_none(nouveau)
        if nouveau_dec is None or (
                _decimal_ou_none(courant.get(nom)) != nouveau_dec):
            logger.info(
                'PVSYNC: événement périmé ignoré pour %s du produit %s '
                '(payload %s, catalogue courant %s).',
                nom, reference, nouveau, courant.get(nom))
            continue
        gardes[nom] = (_decimal_ou_none(ancien), nouveau_dec)
    return gardes.get('tva'), {n: gardes[n] for n in CHAMPS_FORFAIT
                               if n in gardes}


def resynchroniser_devis_pour_produit(*, produit, company, champs, user=None):
    """PVSYNC — propage un changement de RÉFÉRENCE aux devis qui l'utilisent.

    Ne RÉÉCRIT que les devis ``brouillon`` de ``company`` portant une ligne
    rattachée à ``produit`` ; un devis ``envoye`` reste figé et reçoit une
    note (D-ASTK-1 — voir les cinq bornes du bloc ci-dessus).

    Renvoie toujours le même dict :
    ``{devis_touches, lignes_modifiees, lignes_conservees, avertissements}`` —
    ``lignes_conservees`` compte les lignes laissées telles quelles parce
    qu'elles portaient un prix ou une désignation NÉGOCIÉS.
    """
    from django.db import transaction

    from apps.ventes.models import Devis, LigneDevis

    from ..activity import (
        log_devis_catalogue_envoye_conserve, log_devis_prix_negocie_conserve,
        log_devis_resynchronisation)
    from .lignes import prix_negocie

    ancien_nom, nouveau_nom = _valeurs_champ(champs, 'nom')
    ancien_prix_txt, nouveau_prix_txt = _valeurs_champ(champs, 'prix_vente')
    ancien_prix = _decimal_ou_none(ancien_prix_txt)
    nouveau_prix = _decimal_ou_none(nouveau_prix_txt)

    resultat = {'devis_touches': 0, 'lignes_modifiees': 0,
                'lignes_conservees': 0, 'avertissements': []}
    if company is None or produit is None:
        return resultat

    # ── ASTK140 — FRAÎCHEUR : un événement PÉRIMÉ est ignoré. Deux
    # corrections rapprochées (1 000 → 10 000 puis 10 000 → 1 000) peuvent
    # être traitées dans le DÉSORDRE par la file : sans garde, l'événement le
    # plus ancien, joué en dernier, ré-imposait 10 000 alors que le catalogue
    # vaut 1 000. Le produit est donc RELU en base : un « après » du payload
    # qui ne vaut plus la valeur courante n'est pas appliqué (journalisé).
    nouveau_prix, nouveau_nom = _ecarter_valeurs_perimees(
        produit, nouveau_prix, nouveau_nom)
    # ASTK142 — TVA et barème forfaitaire (mêmes bornes, même fraîcheur).
    tva_paire, forfait = _etendus_courants(produit, champs)
    if (not nouveau_nom and nouveau_prix is None and tva_paire is None
            and not forfait):
        return resultat

    # Seuls les champs encore COURANTS (ASTK140) sont annoncés au chatter.
    encore_courants = {'prix_vente': nouveau_prix is not None,
                       'nom': bool(nouveau_nom),
                       'tva': tva_paire is not None,
                       'prix_fixe_ht': 'prix_fixe_ht' in forfait,
                       'prix_par_panneau_ht': 'prix_par_panneau_ht' in forfait}
    modifications = [LIBELLES_CHAMPS_PRODUIT[champ]
                     for champ in ('prix_vente', 'nom', 'tva') + CHAMPS_FORFAIT
                     if champ in (champs or {}) and encore_courants[champ]]

    with transaction.atomic():
        lignes = list(
            LigneDevis.objects
            .select_related('devis')
            .filter(produit=produit,
                    type_ligne=LigneDevis.TypeLigne.PRODUIT,
                    devis__company=company,
                    devis__statut__in=(Devis.Statut.BROUILLON,
                                       Devis.Statut.ENVOYE))
            .order_by('devis_id', 'id'))

        touches = {}
        # ASTK141 (D-ASTK-1) — un devis ENVOYÉ reste FIGÉ : il ne reçoit
        # qu'une note « devis envoyé conservé » par champ qui l'aurait fait
        # bouger. {devis_id: (devis, {'prix': bool, 'nom': bool})}.
        envoyes_conserves = {}
        forfaits_brouillons = {}
        for ligne in lignes:
            envoye = ligne.devis.statut == Devis.Statut.ENVOYE
            champs_ecrits = []
            conservee = False
            prix_conserve = False
            suivrait = {'prix': False, 'nom': False, 'tva': False,
                        'forfait': False}

            # ── ASTK142 — TVA : seule une ligne AU TAUX de l'ancienne TVA
            # catalogue suit ; vide (taux du devis) ou différent = intouché.
            if tva_paire is not None:
                ancienne_tva, nouvelle_tva = tva_paire
                if (ancienne_tva is not None and ancienne_tva != nouvelle_tva
                        and _decimal_ou_none(ligne.taux_tva) == ancienne_tva):
                    if envoye:
                        suivrait['tva'] = True
                    else:
                        ligne.taux_tva = nouvelle_tva
                        champs_ecrits.append('taux_tva')
            # ── ASTK142 — barème forfaitaire : retarifé par DEVIS plus bas.
            if forfait:
                from .lignes import porte_bareme_par_panneau
                if porte_bareme_par_panneau(ligne.produit):
                    if envoye:
                        suivrait['forfait'] = True
                    else:
                        forfaits_brouillons.setdefault(
                            ligne.devis_id, ligne.devis)

            # ── Désignation : elle ne suit que si elle n'a jamais été retouchée
            if nouveau_nom and ancien_nom:
                if (ligne.designation or '') == ancien_nom:
                    if envoye:
                        suivrait['nom'] = True
                    else:
                        ligne.designation = nouveau_nom
                        champs_ecrits.append('designation')
                elif (ligne.designation or '') != nouveau_nom:
                    conservee = True

            # ── Prix : il ne suit que si la ligne était AU PRIX CATALOGUE
            # d'avant, sans remise de ligne ni ``prix_manuel``. QJR555 — LA
            # définition unique du prix NÉGOCIÉ (``lignes.prix_negocie``) :
            # intouchable, et on le dit (une ligne ``prix_manuel`` compte
            # toujours comme conservée).
            if nouveau_prix is not None and ancien_prix is not None:
                if not prix_negocie(ligne, prix_reference=ancien_prix):
                    if envoye:
                        suivrait['prix'] = True
                    else:
                        ligne.prix_unitaire = nouveau_prix
                        champs_ecrits.append('prix_unitaire')
                elif (getattr(ligne, 'prix_manuel', False)
                      or _decimal_ou_none(ligne.prix_unitaire)
                      != nouveau_prix):
                    conservee = True
                    prix_conserve = True

            if envoye:
                if conservee:
                    resultat['lignes_conservees'] += 1
                if any(suivrait.values()):
                    _devis, drapeaux = envoyes_conserves.setdefault(
                        ligne.devis_id,
                        (ligne.devis, {'prix': False, 'nom': False,
                                       'tva': False, 'forfait': False}))
                    for cle, vrai in suivrait.items():
                        drapeaux[cle] = drapeaux[cle] or vrai
                continue

            if champs_ecrits:
                ligne.save(update_fields=champs_ecrits)
                resultat['lignes_modifiees'] += 1
                touches.setdefault(ligne.devis_id, ligne.devis)
            if conservee:
                resultat['lignes_conservees'] += 1
            if prix_conserve:
                # ASTK141 — le prix négocié conservé est DIT, et persisté au
                # chatter du brouillon (une note par ligne, rejeu idempotent).
                log_devis_prix_negocie_conserve(
                    ligne.devis, ligne=ligne, ancien=ancien_prix,
                    nouveau=nouveau_prix, user=user)

        # ── ASTK142 — retarifage au barème des BROUILLONS (fonction unique
        # ``lignes.retarifer_forfaits_par_panneau`` ; abstentions DITES).
        if forfaits_brouillons:
            from .lignes import retarifer_forfaits_par_panneau
            from ..activity import log_devis_forfait_abstention
            for devis in forfaits_brouillons.values():
                avant = dict(devis.lignes.values_list('id', 'prix_unitaire'))
                messages = retarifer_forfaits_par_panneau(devis)
                apres = dict(devis.lignes.values_list('id', 'prix_unitaire'))
                bouges = [i for i in avant if avant[i] != apres.get(i)]
                if bouges:
                    resultat['lignes_modifiees'] += len(bouges)
                    touches.setdefault(devis.id, devis)
                for message in messages:
                    log_devis_forfait_abstention(
                        devis, produit=produit, message=message, user=user)

        # ── D-ASTK-1 (fondateur 06/10/2026, remplace la décision 18/08) ──
        #
        # Seuls les BROUILLONS suivent le catalogue. Un devis ENVOYÉ est le
        # PDF que le client tient : sa page /proposition et son /proposal
        # doivent rester au montant envoyé. Aucune ligne réécrite, aucun
        # marqueur ``resync_apres_envoi`` posé (il reste null pour ces cas) ;
        # le commercial lit une note au chatter et RÉVISE s'il veut appliquer
        # le nouveau prix. ``consigner_correction_apres_envoi`` /
        # ``fin_de_geste_devis`` ne sont donc plus appelés d'ici.
        for devis, drapeaux in envoyes_conserves.values():
            log_devis_catalogue_envoye_conserve(
                devis, produit=produit,
                prix=((ancien_prix, nouveau_prix) if drapeaux['prix']
                      else None),
                nom=(ancien_nom, nouveau_nom) if drapeaux['nom'] else None,
                tva=tva_paire if drapeaux['tva'] else None,
                forfait=forfait if drapeaux['forfait'] else None,
                user=user)

        from apps.ventes.domain.historique_config import instantane_de_geste
        from apps.ventes.domain.verrou_devis import toucher
        for devis in touches.values():
            # QJR545 — la ligne est sauvée en ``update_fields`` : le jeton
            # d'édition du devis (``updated_at``) avance explicitement, sinon
            # un vendeur ouvert avant la resynchro l'écraserait sans le savoir.
            toucher(devis)
            # QJR550 — UN instantané par devis resynchronisé.
            instantane_de_geste(devis, user=user)
            log_devis_resynchronisation(
                devis, produit=produit, modifications=modifications, user=user)
        resultat['devis_touches'] = len(touches)

    if envoyes_conserves:
        resultat['avertissements'].append(
            "%d devis envoyé(s) conservé(s) au prix du jour de l'envoi : "
            "réviser pour appliquer le catalogue." % len(envoyes_conserves))

    if resultat['lignes_conservees']:
        resultat['avertissements'].append(
            '%d ligne(s) de devis portaient un prix ou une désignation '
            'personnalisés : elles ont été CONSERVÉES telles quelles.'
            % resultat['lignes_conservees'])

    if resultat['devis_touches']:
        logger.info(
            'PVSYNC: produit %s modifié (%s) — %d devis resynchronisé(s), '
            '%d ligne(s) recalée(s), %d ligne(s) négociée(s) conservée(s), '
            'société %s',
            getattr(produit, 'sku', None) or getattr(produit, 'pk', '?'),
            ', '.join(modifications) or '—', resultat['devis_touches'],
            resultat['lignes_modifiees'], resultat['lignes_conservees'],
            getattr(company, 'id', '?'))
    return resultat


def on_produit_modifie(sender, produit, company, champs, user=None, **kwargs):
    """PVSYNC — récepteur du bus M6, câblé dans ``VentesConfig.ready()``.

    Il ne fait RIEN lui-même : il planifie la resynchronisation APRÈS le commit
    de la requête stock (``transaction.on_commit``) et la confie à Celery. Deux
    raisons, toutes deux dures :

    * un magasinier qui corrige un prix ne doit pas attendre que N devis soient
      relus — l'écran stock répond immédiatement ;
    * tant que la transaction du produit n'est pas commitée, la nouvelle valeur
      n'existe pas encore pour le worker : lancer la tâche avant le commit
      resynchroniserait sur l'ANCIEN prix (et sur une écriture qui peut encore
      être annulée).

    Best-effort de bout en bout : un bus ou un courtier en panne ne fait jamais
    échouer l'enregistrement du produit.
    """
    from django.db import transaction

    produit_id = getattr(produit, 'pk', None)
    company_id = getattr(company, 'pk', None)
    if not produit_id or not company_id or not champs:
        return
    user_id = getattr(user, 'pk', None)

    def _planifier():
        planifier_resynchronisation_produit(
            produit_id, company_id, champs, user_id)

    transaction.on_commit(_planifier)


def planifier_resynchronisation_produit(produit_id, company_id, champs,
                                        user_id=None):
    """PVSYNC — met la resynchronisation en file, ou la joue EN LIGNE à défaut.

    Le repli en ligne n'est pas un luxe : sans courtier joignable, une
    propagation silencieusement perdue laisserait des devis faux sans que
    personne ne le sache. On est déjà APRÈS le commit (appelé depuis
    ``on_commit``), donc jouer la tâche ici n'ouvre aucune transaction imbriquée.
    """
    from ..tasks import task_resync_devis_apres_produit_modifie

    try:
        task_resync_devis_apres_produit_modifie.delay(
            produit_id, company_id, champs, user_id)
        return
    except Exception as exc:  # noqa: BLE001 — courtier indisponible
        logger.warning(
            'PVSYNC: file Celery indisponible (%s) — resynchronisation du '
            'produit %s jouée en ligne.', exc, produit_id)
    try:
        task_resync_devis_apres_produit_modifie(
            produit_id, company_id, champs, user_id)
    except Exception:  # noqa: BLE001 — jamais bloquant pour l'écriture stock
        logger.exception(
            'PVSYNC: resynchronisation en ligne du produit %s échouée.',
            produit_id)
