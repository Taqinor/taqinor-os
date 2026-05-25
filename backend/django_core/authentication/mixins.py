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
        serializer.save(company=self.request.user.company)
