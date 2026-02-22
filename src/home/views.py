from rest_framework.viewsets import ReadOnlyModelViewSet
from rest_framework.authentication import SessionAuthentication
from .models import HomePage
from .serializers import HomeSerializer
from .permissions import IsEditorOrAdmin


class HomeViewSet(ReadOnlyModelViewSet):
    serializer_class = HomeSerializer
    queryset = HomePage.objects.all()
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsEditorOrAdmin]
