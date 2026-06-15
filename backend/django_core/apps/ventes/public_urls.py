from django.urls import path
from .public_views import public_document

urlpatterns = [
    path('document/<str:token>/', public_document, name='public-document'),
]
