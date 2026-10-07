"""CAL9 — « une seule variante retenue », par un chemin d'écriture UNIQUE.

DEUX VERROUS, PAS UN
--------------------
1. **La base.** ``CalepinageVariante`` porte
   ``UniqueConstraint(fields=['calepinage'], condition=Q(retenue=True))``
   (CAL7/CAL9) : deux variantes retenues sur un même calepinage lèvent
   ``IntegrityError``. C'est la garantie qui survit à tout — script, admin,
   requête concurrente.
2. **Le chemin d'écriture.** La contrainte seule laisserait un appelant
   naïf « corriger » le problème en passant les DEUX à faux (zéro retenue,
   c'est-à-dire un calepinage sans option choisie — l'autre moitié du bug).
   Le champ ``retenue`` n'est donc écrivable QUE depuis ce module : partout
   ailleurs (vue, sérialiseur, script), une écriture est REFUSÉE en français.

Le service de bascule lui-même (``retenir_variante``), la création et la
duplication arrivent avec CAL14 — dans CE fichier, jamais dans un autre : un
second foyer d'écriture rouvrirait exactement ce que ce garde ferme.
"""
from __future__ import annotations

import copy

# Le verrou lui-même vit dans ``apps/calepinage/garde_retenue.py`` (stdlib
# pure) : le MODÈLE doit l'interroger, et s'il importait ce service la chaîne
# ``models -> services.variantes -> apps.ventes.services -> … -> les modèles
# d'une autre app``
# ferait rougir le contrat import-linter CAL5 (mesuré). On le RÉ-EXPORTE ici :
# le chemin d'écriture unique reste le service.
from ..garde_retenue import (  # noqa: F401
    bascule_autorisee,
    bascule_en_cours,
    refuser_ecriture_directe,
)


# ---------------------------------------------------------------------------
# CAL14 — les trois écritures : créer, retenir, dupliquer.
# ---------------------------------------------------------------------------


class VarianteRefusee(ValueError):
    """Refus métier sur une variante, message français, champ fautif nommé."""

    def __init__(self, message, *, champ=''):
        super().__init__(message)
        self.champ = champ


def _nom_texte(nom):
    """ACAL277 — le nom d'une variante est un TEXTE : ``5`` ou ``['a']`` sont
    refusés en nommant ``nom`` (avant : ``AttributeError`` ⇒ 500)."""
    if nom is not None and not isinstance(nom, str):
        raise VarianteRefusee(
            "Le nom de la variante doit être un texte "
            f"(reçu : {type(nom).__name__}).", champ='nom')
    return (nom or '').strip()


def creer_variante(calepinage, *, nom, roof_layout=None, resultat=None,
                   user=None, retenir=False):
    """Crée une variante sur ``calepinage``.

    ``retenir=True`` passe par la bascule atomique : l'ancienne retenue
    repasse à faux dans la MÊME transaction — jamais deux, jamais zéro.
    """
    from django.db import transaction

    from apps.ventes.services import layout_hash

    from ..models import CalepinageVariante

    if calepinage is None or not getattr(calepinage, 'pk', None):
        raise VarianteRefusee(
            "Le calepinage n'est pas encore enregistré : impossible d'y "
            "ajouter une variante.", champ='calepinage')
    # ACAL43 — le verrou unique (devis lié figé ⇒ 409) AVANT toute écriture.
    from .verrou import verifier_ecriture_autorisee

    verifier_ecriture_autorisee(calepinage, champ='variante')
    libelle = _nom_texte(nom)
    if not libelle:
        raise VarianteRefusee(
            "Donnez un nom à la variante : c'est lui qui permet de la "
            "reconnaître dans la comparaison.", champ='nom')
    if roof_layout is not None and not isinstance(roof_layout, dict):
        raise VarianteRefusee(
            "La conception de la variante doit être un objet "
            f"(reçu : {type(roof_layout).__name__}).", champ='roof_layout')

    with transaction.atomic():
        variante = CalepinageVariante.objects.create(
            company=calepinage.company,
            calepinage=calepinage,
            nom=libelle,
            roof_layout=roof_layout,
            layout_hash=layout_hash(roof_layout) or '',
            resultat=resultat,
            cree_par=user,
        )
        # ACAL110 — la création se journalise AVEC son auteur.
        from .journal import journaliser_variante_creee

        journaliser_variante_creee(calepinage, variante=variante, user=user)
        if retenir:
            retenir_variante(variante, user=user)
    return variante


def modifier_variante(variante, *, nom=None, roof_layout=..., resultat=...,
                      user=None):
    """CAL21 — édite une variante SANS jamais toucher ``retenue``.

    ``retenue`` n'a qu'un seul chemin d'écriture (``retenir_variante``, garde
    ``garde_retenue``) : une édition qui pourrait la basculer ouvrirait une
    seconde porte, et c'est comme ça qu'on se retrouve avec deux retenues ou
    zéro. L'empreinte suit la conception — jamais recodée ici.

    ``roof_layout`` / ``resultat`` valent ``...`` (Ellipsis) quand l'appelant
    ne les touche pas : ``None`` est une VALEUR (« efface »), pas une absence.

    ACAL110 — seul un changement RÉEL s'écrit et se journalise (« Variante
    « X » modifiée (nom | conception) », auteur ``user``) ; un PATCH à
    l'identique n'écrit rien.
    """
    from apps.ventes.services import layout_hash

    from .layout import empreinte_document

    if variante is None or not getattr(variante, 'pk', None):
        raise VarianteRefusee(
            "Cette variante n'existe pas : impossible de la modifier.",
            champ='variante')
    # ACAL43 — le verrou unique (devis lié figé ⇒ 409) AVANT toute écriture.
    from .verrou import verifier_ecriture_autorisee

    verifier_ecriture_autorisee(variante.calepinage, champ='variante')

    champs = []
    changements = []
    if nom is not None:
        libelle = _nom_texte(nom)
        if not libelle:
            raise VarianteRefusee(
                "Donnez un nom à la variante : c'est lui qui permet de la "
                "reconnaître dans la comparaison.", champ='nom')
        if libelle != variante.nom:
            variante.nom = libelle
            champs.append('nom')
            changements.append('nom')
    if roof_layout is not ...:
        if roof_layout is not None and not isinstance(roof_layout, dict):
            raise VarianteRefusee(
                "La conception de la variante doit être un objet "
                f"(reçu : {type(roof_layout).__name__}).", champ='roof_layout')
        if (empreinte_document(roof_layout)
                != empreinte_document(variante.roof_layout)
                or (roof_layout is None) != (variante.roof_layout is None)):
            variante.roof_layout = roof_layout
            variante.layout_hash = layout_hash(roof_layout) or ''
            champs.extend(['roof_layout', 'layout_hash'])
            changements.append('conception')
            # ACAL112 — une conception changée périme sa simulation : le
            # résultat de la variante est remis à ``None`` (sauf s'il est
            # fourni dans le MÊME appel).
            if resultat is ... and variante.resultat is not None:
                variante.resultat = None
                champs.append('resultat')
    if resultat is not ... and resultat != variante.resultat:
        variante.resultat = resultat
        champs.append('resultat')

    if champs:
        variante.save(update_fields=champs + ['updated_at'])
    if changements:
        from .journal import journaliser_variante_modifiee

        journaliser_variante_modifiee(variante.calepinage, variante=variante,
                                      changements=changements, user=user)
    return variante


def supprimer_variante(variante, *, user=None):
    """CAL21 — retire une variante ; JAMAIS celle qui est retenue.

    Supprimer la retenue laisserait le calepinage sans option choisie — la
    moitié du bug que la contrainte de base ne couvre pas (elle interdit DEUX
    retenues, pas ZÉRO). Le refus nomme le geste à faire d'abord.
    """
    if variante is None or not getattr(variante, 'pk', None):
        raise VarianteRefusee(
            "Cette variante n'existe pas : impossible de la supprimer.",
            champ='variante')
    # ACAL43 — le verrou unique (devis lié figé ⇒ 409) AVANT toute écriture.
    from .verrou import verifier_ecriture_autorisee

    verifier_ecriture_autorisee(variante.calepinage, champ='variante')
    if variante.retenue:
        raise VarianteRefusee(
            f"« {variante.nom} » est la variante RETENUE : retenez-en une "
            "autre avant de la supprimer.", champ='retenue')
    calepinage, nom = variante.calepinage, variante.nom
    variante.delete()
    # ACAL110 — la suppression se journalise AVEC son auteur.
    from .journal import journaliser_variante_supprimee

    journaliser_variante_supprimee(calepinage, nom=nom, user=user)
    return True


def retenir_variante(variante, *, user=None, appliquer=True):
    """Bascule ``variante`` en RETENUE, atomiquement — et l'ÉCRIT comme
    conception courante (ACAL107, D-ACAL-2).

    L'ancienne retenue du même calepinage repasse à faux dans la même
    transaction : il n'y a jamais deux retenues, ni zéro, même une
    milliseconde. Dans CETTE transaction, ``enregistrer_layout`` pose
    ``variante.roof_layout`` sur le calepinage (empreinte, version
    « Variante « X » retenue », journal) : « Générer le devis », la
    resynchronisation, le chantier et l'as-built lisent tous la conception
    courante. Retenir deux fois la même variante ⇒ inchangé, aucune version,
    aucun journal.

    Args:
        user: l'auteur — posé côté serveur (vue : ``request.user``).
        appliquer: ``False`` pour l'import de projet (l'état importé EST déjà
            le document : on restaure la retenue sans réécrire la conception).

    Returns:
        La variante retenue (rafraîchie).
    """
    from django.db import transaction

    from ..models import CalepinageVariante

    if variante is None or not getattr(variante, 'pk', None):
        raise VarianteRefusee(
            "La variante n'est pas encore enregistrée : impossible de la "
            "retenir.", champ='variante')
    # ACAL43 — le verrou unique (devis lié figé ⇒ 409) AVANT toute écriture.
    from .verrou import verifier_ecriture_autorisee

    verifier_ecriture_autorisee(variante.calepinage, champ='variante')

    calepinage = variante.calepinage
    # CAL206 — feu vert bureau d'études / approbation : AVANT toute écriture.
    # C'est ICI, et nulle part ailleurs, que le refus doit vivre : c'est le
    # SEUL chemin d'écriture de « retenue » (CAL9).
    from .feu_vert import GESTE_RETENUE, verifier_avant_publication

    verifier_avant_publication(calepinage, geste=GESTE_RETENUE,
                               variante=variante)
    document = (variante.roof_layout
                if isinstance(variante.roof_layout, dict) else None)

    deja_retenue = bool(CalepinageVariante.objects
                        .filter(pk=variante.pk, retenue=True).exists())
    ancienne = (CalepinageVariante.objects
                .filter(calepinage_id=variante.calepinage_id, retenue=True)
                .exclude(pk=variante.pk)
                .first())
    with transaction.atomic():
        if not deja_retenue:
            with bascule_autorisee():
                (CalepinageVariante.objects
                 .select_for_update()
                 .filter(calepinage_id=variante.calepinage_id, retenue=True)
                 .exclude(pk=variante.pk)
                 .update(retenue=False))
                variante.retenue = True
                variante.save(update_fields=['retenue', 'updated_at'])
        if appliquer and document is not None:
            from .layout import LayoutRefuse, enregistrer_layout

            try:
                enregistrer_layout(
                    calepinage, document, user=user,
                    libelle=f'Variante « {variante.nom} » retenue')
            except LayoutRefuse as refus:
                raise VarianteRefusee(
                    str(refus), champ=refus.champ or 'roof_layout') from refus
    if not deja_retenue:
        # CAL26 — la bascule se journalise par les NOMS, AVEC son auteur.
        from .journal import journaliser_variante_retenue

        journaliser_variante_retenue(calepinage, ancienne=ancienne,
                                     nouvelle=variante, user=user)
    return variante


#: ACAL117 (C-ACAL-011, C-ACAL-090) — LA règle de copie, UNE constante pour
#: Dupliquer, le modèle (``modeles.creer_depuis_modele`` /
#: ``creation.demarrer_depuis_modele``) et l'import de projet : la conception
#: et ses postes de pertes. JAMAIS : ``resultat`` (production d'un autre toit
#: + saisies de site), ``roof_image``, ``approbation``, ``devis``,
#: ``appel_offre_id`` ; les variantes copiées naissent NON retenues et SANS
#: résultat.
CHAMPS_COPIES = ('roof_layout', 'layout_hash', 'version_moteur', 'pertes')


def dupliquer(calepinage, *, user=None, titre='', avec_variantes=True,
              roof_layout=...):
    """Recopie la conception (et les variantes) vers un NOUVEAU calepinage.

    Le duplicata reste dans la MÊME société et garde le rattachement
    lead/client (sinon il violerait la contrainte « lead ou client »), mais
    il ne porte NI ``devis`` NI ``appel_offre_id`` : dupliquer une conception
    ne réquisitionne pas le devis de l'original.

    CALX35 — ``avec_variantes`` vaut ``True`` par DÉFAUT : c'est le
    comportement du service depuis CAL14, et la décision D12 exige qu'un
    réglage neuf ne change rien pour un appelant qui ne le passe pas. À
    ``False``, seule la conception suit : aucune variante n'est recopiée.

    ACAL117 — ce qui est copié est :data:`CHAMPS_COPIES` (conception +
    pertes) ; aucun résultat (re-simulable), aucune variante retenue, aucun
    rendu ; une version « Conception d'origine (copie de #C) » est déposée.
    ``roof_layout`` (facultatif) remplace la conception copiée (modèle
    translaté sur le repère du lead cible, D-ACAL-15).
    """
    from django.db import transaction

    from apps.ventes.services import layout_hash

    from ..models import Calepinage, CalepinageVariante
    from .versions import enregistrer_version

    if calepinage is None or not getattr(calepinage, 'pk', None):
        raise VarianteRefusee(
            "Le calepinage à dupliquer n'est pas enregistré.",
            champ='calepinage')

    copies = {champ: copy.deepcopy(getattr(calepinage, champ, None))
              for champ in CHAMPS_COPIES}
    if roof_layout is not ...:
        copies['roof_layout'] = roof_layout
        copies['layout_hash'] = layout_hash(roof_layout) or ''
    copies['layout_hash'] = copies['layout_hash'] or ''
    copies['version_moteur'] = copies['version_moteur'] or ''
    copies['pertes'] = (copies['pertes']
                        if isinstance(copies['pertes'], list) else [])

    with transaction.atomic():
        copie = Calepinage.objects.create(
            company=calepinage.company,
            lead_id=calepinage.lead_id,
            client_id=calepinage.client_id,
            titre=(titre or '').strip() or _titre_de_copie(calepinage),
            statut=Calepinage.Statut.BROUILLON,
            cree_par=user,
            **copies,
        )
        sources = ((CalepinageVariante.objects
                    .filter(calepinage=calepinage).order_by('id'))
                   if avec_variantes else CalepinageVariante.objects.none())
        for source in sources:
            CalepinageVariante.objects.create(
                company=copie.company,
                calepinage=copie,
                nom=source.nom,
                roof_layout=source.roof_layout,
                layout_hash=source.layout_hash or '',
                resultat=None,
                retenue=False,
                cree_par=user,
            )
        # CYC-G2-03 — la copie porte SA version d'origine (historique non
        # vide, restaurable), sans résultat gelé.
        if copie.roof_layout is not None:
            enregistrer_version(
                copie, user=user,
                libelle=f"Conception d'origine (copie de #{calepinage.pk})",
                resultat=None, meme_empreinte_admise=True)
    return copie


def _titre_de_copie(calepinage):
    """« <titre> (copie) » — dérivé de la donnée, jamais d'un nom figé."""
    titre = (getattr(calepinage, 'titre', '') or '').strip()
    return f'{titre} (copie)' if titre else 'Calepinage (copie)'
