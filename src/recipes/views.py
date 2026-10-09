from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import action
from rest_framework.parsers import JSONParser, MultiPartParser
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import ReadOnlyModelViewSet

from home.locales import get_requested_locale
from home.permissions import IsEditorOrAdmin

from .importer import RecipeImportError, import_recipes
from .models import RecipePage
from .serializers import BulkUploadSerializer, RecipeSerializer, load_json_upload


class RecipeViewSet(ReadOnlyModelViewSet):
    serializer_class = RecipeSerializer
    queryset = (
        RecipePage.objects.live()
        .order_by("title")
        .select_related("locale")
        .prefetch_related("ingredients")
    )
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsEditorOrAdmin]

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.action == "list":
            queryset = queryset.filter(locale=get_requested_locale(self.request))
        return queryset

    @action(
        detail=False,
        methods=["post"],
        url_path="bulk-upload",
        parser_classes=[MultiPartParser, JSONParser],
    )
    def bulk_upload(self, request: Request) -> Response:
        """
        Creates or updates recipes from a JSON file (multipart field "file")
        or a JSON request body.
        """
        upload = request.FILES.get("file")
        payload = load_json_upload(upload) if upload else request.data
        if isinstance(payload, list):
            payload = {"recipes": payload}

        serializer = BulkUploadSerializer(data=payload)
        serializer.is_valid(raise_exception=True)
        try:
            result = import_recipes(
                serializer.validated_data["recipes"], user=request.user
            )
        except RecipeImportError as error:
            return Response(error.errors, status=status.HTTP_400_BAD_REQUEST)
        return Response({"created": result.created, "updated": result.updated})
