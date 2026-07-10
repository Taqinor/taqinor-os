class TenantMixin:
    """
    Filters querysets to the current user's company.
    Superusers WITH a company are scoped to that company (ERP usage).
    Superusers WITHOUT a company see all data (platform-level admin).
    """
    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.company_id:
            return qs.filter(company=user.company)
        if user.is_superuser:
            return qs
        return qs.none()

    def perform_create(self, serializer):
        serializer.save(company=self.request.user.company)

    def perform_update(self, serializer):
        # Un utilisateur tenant : la société est forcée côté serveur (jamais lue
        # du corps) — identique à avant, et elle vaut déjà celle de l'instance
        # scopée par ``get_queryset``. Un superuser SANS société (acteur
        # plateforme supporté, cf. docstring) NE doit PAS voir ``company=None``
        # écrasé sur la ligne éditée : sur un modèle à ``company`` nullable la
        # ligne se détacherait de son tenant (elle disparaîtrait des listes
        # scopées), et sur un modèle NON-NULL cela lèverait IntegrityError (500).
        # On préserve alors la société PROPRE de l'objet.
        if self.request.user.company_id:
            serializer.save(company=self.request.user.company)
        else:
            serializer.save()
