from rest_framework.viewsets import ReadOnlyModelViewSet
from .models import HomePage
from .serializers import HomeSerializer

class HomeViewSet(ReadOnlyModelViewSet):
    serializer_class = HomeSerializer
    queryset = HomePage.objects.all()
