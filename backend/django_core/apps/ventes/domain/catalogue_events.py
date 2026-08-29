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
#   1. **Seuls les statuts BROUILLON et ENVOYÉ bougent.** Un devis accepté,
#      refusé ou expiré est un document CONTRACTUEL : le client a signé (ou vu)
#      des montants, et aucune correction de catalogue n'a le droit de les
#      réécrire. Le statut est LU, JAMAIS écrit (règle #4) — les écritures se
#      limitent à ``LigneDevis`` et à une note de chatter.
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
#      note, aucune écriture. Rejouer le même événement est donc un no-op
#      complet (la tâche est at-least-once : elle DOIT être idempotente).
#   5. **Une société à la fois.** La requête est cantonnée à la société de
#      l'événement — le devis d'un autre tenant n'est jamais lu, encore moins
#      réécrit.

#: Résumé FRANÇAIS d'un champ produit, pour la note de chatter.
LIBELLES_CHAMPS_PRODUIT = {
    'nom': 'désignation',
    'prix_vente': 'prix',
}


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


def resynchroniser_devis_pour_produit(*, produit, company, champs, user=None):
    """PVSYNC — propage un changement de RÉFÉRENCE aux devis qui l'utilisent.

    Ne touche QUE les devis ``brouillon`` et ``envoye`` de ``company`` portant
    une ligne rattachée à ``produit`` (voir les cinq bornes du bloc ci-dessus).

    Renvoie toujours le même dict :
    ``{devis_touches, lignes_modifiees, lignes_conservees, avertissements}`` —
    ``lignes_conservees`` compte les lignes laissées telles quelles parce
    qu'elles portaient un prix ou une désignation NÉGOCIÉS.
    """
    from django.db import transaction

    from apps.ventes.models import Devis, LigneDevis

    from ..activity import log_devis_resynchronisation

    ancien_nom, nouveau_nom = _valeurs_champ(champs, 'nom')
    ancien_prix_txt, nouveau_prix_txt = _valeurs_champ(champs, 'prix_vente')
    ancien_prix = _decimal_ou_none(ancien_prix_txt)
    nouveau_prix = _decimal_ou_none(nouveau_prix_txt)

    resultat = {'devis_touches': 0, 'lignes_modifiees': 0,
                'lignes_conservees': 0, 'avertissements': []}
    if company is None or produit is None:
        return resultat
    if not nouveau_nom and nouveau_prix is None:
        return resultat

    modifications = [LIBELLES_CHAMPS_PRODUIT[champ]
                     for champ in ('prix_vente', 'nom')
                     if champ in (champs or {})]

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
        for ligne in lignes:
            champs_ecrits = []
            conservee = False

            # ── Désignation : elle ne suit que si elle n'a jamais été retouchée
            if nouveau_nom and ancien_nom:
                if (ligne.designation or '') == ancien_nom:
                    ligne.designation = nouveau_nom
                    champs_ecrits.append('designation')
                elif (ligne.designation or '') != nouveau_nom:
                    conservee = True

            # ── Prix : il ne suit que si la ligne était AU PRIX CATALOGUE
            # d'avant, sans remise de ligne. Une remise ou un prix retouché
            # valent prix NÉGOCIÉ : intouchables, et on le dit.
            if nouveau_prix is not None and ancien_prix is not None:
                remise = _decimal_ou_none(ligne.remise) or Decimal('0')
                actuel = _decimal_ou_none(ligne.prix_unitaire)
                if actuel is not None and actuel == ancien_prix \
                        and remise == Decimal('0'):
                    ligne.prix_unitaire = nouveau_prix
                    champs_ecrits.append('prix_unitaire')
                elif actuel is None or actuel != nouveau_prix:
                    conservee = True

            if champs_ecrits:
                ligne.save(update_fields=champs_ecrits)
                resultat['lignes_modifiees'] += 1
                touches.setdefault(ligne.devis_id, ligne.devis)
            if conservee:
                resultat['lignes_conservees'] += 1

        # ── TRANSPARENCE D'UNE RESYNCHRO POST-ENVOI (fondateur 2026-08-18) ──
        #
        # Le périmètre reste brouillon + envoyé (décision fondateur, borne 1) :
        # un devis envoyé DOIT suivre le catalogue, sinon le commercial rappelle
        # un client avec un prix que la société ne pratique plus. Mais le client,
        # lui, tient un PDF FIGÉ au montant du jour de l'envoi pendant que sa
        # page /proposition est re-rendue en direct : sans marqueur, il pouvait
        # signer un montant différent de sa pièce jointe sans jamais l'avoir su.
        # On pose donc l'horodatage de la DERNIÈRE resynchro post-envoi (écrasé
        # à chaque passage — c'est un « depuis quand », pas un journal) et la
        # charge utile publique l'expose sous ``resync_apres_envoi``.
        # ``update_fields`` EXCLUT ``statut`` : rien ne peut partir d'ici (#4).
        from django.utils import timezone
        horodatage = timezone.now().isoformat()
        from apps.ventes.domain.etude_schema import CALEPINAGE, ecrire
        for devis in touches.values():
            if devis.statut == Devis.Statut.ENVOYE:
                # QJR62 — ÉCRIVAIN UNIQUE (fusion, jamais un remplacement).
                ecrire(devis, proprietaire=CALEPINAGE,
                       resync_apres_envoi={'date': horodatage})
            log_devis_resynchronisation(
                devis, produit=produit, modifications=modifications, user=user)
        resultat['devis_touches'] = len(touches)

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
