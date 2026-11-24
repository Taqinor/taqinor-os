"""ADEV131 (D-ACAL-97) — le résultat RANGÉ du moteur unique de conception.

Une ligne = UNE version de la conception d'UN porteur : le lead, ou le
calepinage quand il n'y a pas de lead (réponse du fondateur, Q3 du
23/11/2026). Forme : ``contract_samples/conception_lead.json`` ; conception :
``docs/audits/l5-calepinage/controles/C4-un-seul-moteur.md`` §4.

* une seule version ``courante`` par porteur (contraintes conditionnelles) ;
* ``version`` = plus haut numéro utilisé + 1 sous point de sauvegarde, avec
  reprise sur collision — jamais ``count()+1`` (règle de numérotation du
  dépôt, ``core/numbering.py``) ;
* la société vient du porteur (le lead), jamais d'un corps de requête ;
* rien n'est supprimé : une nouvelle version passe l'ancienne à
  ``courante=False`` (journal relu par version).

L'écrivain métier est ``conception/service.py::relancer`` (ADEV135) ; ce
modèle ne porte que la primitive de rangement :meth:`ConceptionLead.ranger`.
Aucun prix d'achat ni marge n'y entre (garde récursive de l'écrivain).
"""
from django.conf import settings
from django.db import IntegrityError, models, transaction
from django.db.models import Max, Q
from django.utils import timezone

from core.models import TenantModel
from core.numbering import MAX_ATTEMPTS


class ConceptionLead(TenantModel):
    """Une version rangée de la conception d'un lead (ou d'un calepinage)."""

    class Etat(models.TextChoices):
        COMPLET = 'complet', 'Complet'
        REFUS = 'refus', 'Refus'

    lead = models.ForeignKey(
        'crm.Lead', null=True, blank=True,
        on_delete=models.CASCADE,  # on_delete: le résultat calculé n'a pas de sens sans son lead (D-ACAL-97)
        related_name='+')
    #: Porteur sans lead (dossier client seul) ET calepinage dont la pose a servi.
    calepinage_id = models.PositiveIntegerField(null=True, blank=True, db_index=True)
    version = models.PositiveIntegerField()
    courante = models.BooleanField(default=True)
    etat = models.CharField(max_length=10, choices=Etat.choices)
    refus = models.JSONField(null=True, blank=True)
    marche = models.CharField(max_length=20, blank=True, default='')
    option_retenue = models.CharField(max_length=5, blank=True, default='')
    valeurs = models.JSONField(default=dict, blank=True)
    blocs = models.JSONField(default=dict, blank=True)
    entrees_utilisees = models.JSONField(default=dict, blank=True)
    suppositions = models.JSONField(default=list, blank=True)
    empreinte = models.CharField(max_length=64)
    empreinte_pose = models.CharField(max_length=64, blank=True, default='')
    niveau_regles = models.PositiveSmallIntegerField()
    version_moteur = models.CharField(max_length=32)
    declencheur = models.JSONField(default=dict, blank=True)
    calcule_le = models.DateTimeField(default=timezone.now)
    calcule_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL,  # on_delete: l'auteur part, la version calculée reste (None = tâche du moteur)
        related_name='+')

    class Meta:
        verbose_name = 'Conception (moteur unique)'
        verbose_name_plural = 'Conceptions (moteur unique)'
        db_table = 'ventes_conceptionlead'
        ordering = ['-version']
        constraints = [
            models.CheckConstraint(
                condition=Q(lead__isnull=False) | Q(calepinage_id__isnull=False),
                name='conceptionlead_porteur_requis'),
            models.UniqueConstraint(
                fields=['lead'], condition=Q(courante=True, lead__isnull=False),
                name='uniq_conceptionlead_lead_courante'),
            models.UniqueConstraint(
                fields=['calepinage_id'],
                condition=Q(courante=True, lead__isnull=True, calepinage_id__isnull=False),
                name='uniq_conceptionlead_calepinage_courante'),
            models.UniqueConstraint(
                fields=['lead', 'version'], condition=Q(lead__isnull=False),
                name='uniq_conceptionlead_lead_version'),
            models.UniqueConstraint(
                fields=['calepinage_id', 'version'], condition=Q(lead__isnull=True),
                name='uniq_conceptionlead_calepinage_version'),
        ]

    def __str__(self):
        porteur = f'lead {self.lead_id}' if self.lead_id else f'calepinage {self.calepinage_id}'
        return f'Conception {porteur} v{self.version}'

    @classmethod
    def ranger(cls, *, lead=None, calepinage_id=None, company=None, sauf_empreinte=None, garde=None, **champs):
        """Range la version SUIVANTE du porteur et la rend seule courante.

        Porteur = ``lead`` (sa société fait foi : une ``company`` différente
        est refusée), sinon ``calepinage_id`` avec la ``company`` du
        calepinage, lue par l'appelant. ``version`` = plus haut utilisé + 1,
        sous point de sauvegarde ; une collision concurrente (contrainte
        unique) reprend avec le numéro suivant.

        ``sauf_empreinte`` (relecture m1) : relu SOUS VERROU des versions du
        porteur — si la courante porte déjà cette empreinte (deux relances
        simultanées des mêmes entrées), elle est rendue telle quelle et rien
        n'est écrit. L'instance rendue porte ``ecrite`` (``True`` = rangée ici).

        ``garde`` (relecture E3 B1(b), Q5) : ``callable(deja)`` appelé SOUS LA
        MÊME transaction, après le verrou des versions et avant toute écriture ;
        faux ⇒ rien n'est écrit et ``None`` est rendu (lead effacé entre-temps,
        version plus récente déjà rangée)."""
        if lead is not None:
            if company is not None and getattr(company, 'pk', company) != lead.company_id:
                raise ValueError('La société de la conception vient du lead.')
            company, porteur = lead.company, {'lead': lead}
        elif calepinage_id is not None and company is not None:
            porteur = {'lead__isnull': True, 'calepinage_id': calepinage_id}
        else:
            raise ValueError('Une conception est portée par un lead ou un calepinage (avec sa société).')
        for tentative in range(MAX_ATTEMPTS):
            try:
                with transaction.atomic():
                    deja = cls.objects.filter(company=company, **porteur)
                    list(deja.select_for_update().values_list('pk', flat=True))
                    if sauf_empreinte is not None:
                        courante = deja.filter(courante=True).first()
                        if courante is not None and courante.empreinte == sauf_empreinte:
                            courante.ecrite = False
                            return courante
                    if garde is not None and not garde(deja):
                        return None
                    haut = deja.aggregate(haut=Max('version'))['haut'] or 0
                    deja.filter(courante=True).update(courante=False)
                    version = cls.objects.create(
                        company=company, lead=lead, calepinage_id=calepinage_id,
                        version=haut + 1, courante=True, **champs)
                    version.ecrite = True
                    return version
            except IntegrityError:
                if tentative == MAX_ATTEMPTS - 1:
                    raise
        return None  # pragma: no cover — la boucle rend ou lève
