# apps/knowledge/urls.py

"""URLs für die Wissensbasis."""

from django.urls import path
from apps.knowledge.views import KnowledgeDetailView, KnowledgeListCreateView

urlpatterns = [
    path('knowledge/', KnowledgeListCreateView.as_view(), name='knowledge-list'),
    path('knowledge/<str:laborwert_key>/', KnowledgeDetailView.as_view(), name='knowledge-detail'),
]
