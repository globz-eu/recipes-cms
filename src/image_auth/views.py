import re

from django.conf import settings
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from wagtail.images import get_image_model
from wagtail.images.models import Image
from wagtail.permission_policies.collections import CollectionPermissionPolicy

from experience.models import Character


@api_view(["GET"])
@permission_classes([AllowAny])
def check_permissions(request: Request) -> Response:
    """
    A view to check if the user has permission to view images. All users are allowed to view images
    that are referenced by a live page or in approved collections. Only authenticated users can
    view images not referenced by a live page or in approved collections.
    The requested image is passed in the "X-Original-Uri" header.
    """
    try:
        if not request.headers.get("X-Original-Uri"):
            return Response(data={"message": "Bad Request"}, status=400)

        requested_image = get_image_file(request.headers.get("X-Original-Uri"))
        image_type = get_image_type(requested_image)

        if not image_type:
            return Response(data={"message": "Bad Request"}, status=400)

        db_image = get_db_image(requested_image, image_type)
        if not db_image:
            return Response(data={"message": "Not found"}, status=404)

        if len(db_image.get_referenced_live_pages()) > 0:
            return Response({"message": "OK"}, status=200)

        characters_approved_collections = (
            Character.objects.all()
            .values_list("approved_collection_id", flat=True)
            .distinct()
        )

        if db_image.collection_id in list(characters_approved_collections):
            return Response({"message": "OK"}, status=200)

        if request.user.is_authenticated:
            permission_policy = CollectionPermissionPolicy(
                get_image_model(), auth_model=Image
            )
            if permission_policy.user_has_any_permission_for_instance(
                request.user,
                ["change", "add", "delete", "choose"],
                db_image,
            ):
                return Response(data={"message": "OK"}, status=200)
            else:
                return Response(data={"message": "Unauthorized"}, status=401)

        return Response(data={"message": "Unauthorized"}, status=401)

    except Exception as e:
        return Response(data={"message": str(e)}, status=400)


def get_image_file(image_url: str) -> str:
    """
    Get the original image file path from the image URL.
    """
    return image_url.replace(settings.MEDIA_URL, "")


def get_image_type(image: str) -> str | None:
    """
    Check whether the image is a rendition or an original image.
    """
    if re.match(r"^images/", image):
        return "rendition"
    elif re.match(r"^original_images/", image):
        return "original"
    else:
        return None


def get_db_image(requested_image: str, image_type: str) -> str | None:
    """
    Get the image from the database.
    """
    Image = get_image_model()
    RenditionModel = Image.get_rendition_model()

    match image_type:
        case "rendition":
            try:
                db_image = RenditionModel.objects.get(file=requested_image).image
                return db_image
            except RenditionModel.DoesNotExist:
                return None

        case "original":
            try:
                db_image = Image.objects.get(file=requested_image)
                return db_image
            except Image.DoesNotExist:
                return None
