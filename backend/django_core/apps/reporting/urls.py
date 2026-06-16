from django.urls import path
from .views import dashboard
from .search import global_search, notifications
from .pipeline import pipeline

urlpatterns = [
    path('dashboard/', dashboard, name='reporting-dashboard'),
    path('search/', global_search, name='global-search'),
    path('notifications/', notifications, name='in-app-notifications'),
    path('pipeline/', pipeline, name='reporting-pipeline'),
]
