import functools
import re

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from django.conf import settings
from django.http import Http404, StreamingHttpResponse
from rest_framework import permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import PermissionDenied
from rest_framework.request import Request
from wagtail.images.models import Image

from home.permissions import IsEditorOrAdmin

_MEDIA_PREFIX = "/media/"
_S3_CHUNK_SIZE = 1024 * 1024  # 1 MiB


class MediaAccessPermission(permissions.BasePermission):
    """
    Permission class that controls access to media images.

    - **403 Forbidden** - path cannot be mapped to a known image type, or no
      matching image record in the database.
    - **401 Unauthorized** - image exists but the user is not authenticated.
    - **403 Forbidden** - image exists but the authenticated user lacks the
      required role/group membership.
    """

    def has_permission(self, request: Request, view) -> bool:  # type: ignore[override]
        image_path = view.kwargs.get("image_path", "")
        image_type = get_image_type(image_path)
        if not image_type:
            raise PermissionDenied()

        if not get_db_image(image_path, image_type):
            raise PermissionDenied()

        return IsEditorOrAdmin().has_permission(request, view)


@functools.lru_cache(maxsize=1)
def _get_s3_client():
    return boto3.client(
        "s3",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        endpoint_url=settings.AWS_S3_ENDPOINT_URL,
        region_name=settings.AWS_S3_REGION_NAME,
        config=Config(
            signature_version=settings.AWS_S3_SIGNATURE_VERSION,
            s3={"addressing_style": settings.AWS_S3_ADDRESSING_STYLE},
        ),
    )


@api_view(["GET"])
@permission_classes([MediaAccessPermission])
def serve_media(request: Request, image_path: str) -> StreamingHttpResponse:
    """
    Stream a private S3 object to the client.

    Permission is enforced by ``MediaAccessPermission`` before any S3 call is
    made.  The view fetches the object directly from the private S3 bucket via
    boto3 (credentials from settings) and streams it back in chunks,
    preserving the Content-Type returned by S3.

    - **200 OK** - object found and streamed.
    - **404 Not Found** - no such key in the bucket.
    """
    s3_client = _get_s3_client()
    try:
        obj = s3_client.get_object(
            Bucket=settings.AWS_STORAGE_BUCKET_NAME,
            Key=image_path,
        )
    except ClientError as exc:
        if exc.response["Error"]["Code"] in ("NoSuchKey", "404"):
            raise Http404
        raise

    content_type = obj.get("ContentType", "application/octet-stream")

    def _iter_body():
        body = obj["Body"]
        while chunk := body.read(_S3_CHUNK_SIZE):
            yield chunk

    return StreamingHttpResponse(_iter_body(), content_type=content_type)


def get_image_file(image_url: str) -> str:
    """
    Extract the storage object key from the nginx-facing media URL.

    The ``X-Original-URI`` from nginx is always ``/media/<key>``.  Stripping
    the ``/media/`` prefix gives the bare object key (e.g.
    ``images/foo.jpg``) which matches the value stored in the database
    ``file`` field regardless of whether the storage backend is the local
    filesystem or an S3-compatible service.
    """
    if image_url.startswith(_MEDIA_PREFIX):
        return image_url[len(_MEDIA_PREFIX) :]
    return image_url


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


def get_db_image(requested_image: str, image_type: str) -> bool:
    """
    Get the image from the database.
    """
    RenditionModel = Image.get_rendition_model()

    match image_type:
        case "rendition":
            try:
                RenditionModel.objects.get(file=requested_image).image
                return True
            except RenditionModel.DoesNotExist:
                return False

        case "original":
            try:
                Image.objects.get(file=requested_image)
                return True
            except Image.DoesNotExist:
                return False

    return False
