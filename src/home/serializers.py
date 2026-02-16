from rest_framework import serializers
from .models import HomePage

class HomeSerializer(serializers.ModelSerializer):
    class Meta:
        model = HomePage
        fields = ["title", "description"]
