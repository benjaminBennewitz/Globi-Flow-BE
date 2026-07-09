# apps/knowledge/urls.py

"""URLs für die Wissensbasis."""

from django.urls import path
from apps.knowledge.views import KnowledgeDetailView, KnowledgeListCreateView, KnowledgeResetView

urlpatterns = [
    path('knowledge/', KnowledgeListCreateView.as_view(), name='knowledge-list'),
    path('knowledge/reset/', KnowledgeResetView.as_view(), name='knowledge-reset'),
    path('knowledge/<str:laborwert_key>/', KnowledgeDetailView.as_view(), name='knowledge-detail'),
]
