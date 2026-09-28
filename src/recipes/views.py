from rest_framework.authentication import SessionAuthentication
from rest_framework.viewsets import ReadOnlyModelViewSet

from home.permissions import IsEditorOrAdmin

from .models import RecipePage
from .serializers import RecipeSerializer


class RecipeViewSet(ReadOnlyModelViewSet):
    serializer_class = RecipeSerializer
    queryset = RecipePage.objects.live().order_by("title")
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsEditorOrAdmin]
