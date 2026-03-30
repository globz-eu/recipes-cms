import re

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from django.conf import settings
from django.http import Http404, StreamingHttpResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from wagtail.images.models import Image

from home.permissions import IsEditorOrAdmin

_MEDIA_PREFIX = "/media/"
_S3_CHUNK_SIZE = 1024 * 1024  # 1 MB


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
@permission_classes([AllowAny])
def check_permissions(request: Request) -> Response:
    """
    Nginx auth_request endpoint that controls access to media images.

    Expects the ``X-Original-Uriget_image_file`` header to be set by Nginx with the
    originally requested media URL. The URI is resolved to an image in the
    database, then checked against the caller's permissions:

    - **200 OK** - image exists and the user is a superuser, staff, or a
      member of the Editors group.
    - **401 Unauthorized** - image exists but the user lacks the required
      role/group membership.
    - **403 Forbidden** - ``X-Original-Uri`` header is missing, the path
      cannot be mapped to a known image type, or no matching image record
      in the database.
    """
    try:
        if not request.headers.get("X-Original-Uri"):
            return Response(data={"message": "Forbidden"}, status=403)

        requested_image = get_image_file(request.headers.get("X-Original-Uri"))
        image_type = get_image_type(requested_image)

        if not image_type:
            return Response(data={"message": "Forbidden"}, status=403)

        db_image = get_db_image(requested_image, image_type)
        if not db_image:
            return Response(data={"message": "Forbidden"}, status=403)

        permission = IsEditorOrAdmin()
        if not permission.has_permission(request, None):
            return Response(data={"message": "Unauthorized"}, status=401)

        return Response(data={"message": "OK"}, status=200)

    except Exception as e:
        return Response(data={"message": str(e)}, status=400)


@api_view(["GET"])
@permission_classes([AllowAny])
def serve_media(request: Request, image_path: str) -> StreamingHttpResponse:
    """
    Stream a private S3 object to the client.

    This view is reached only after nginx has already performed the
    ``auth_request /image-auth/`` gate check, so no additional permission
    check is performed here.  The view fetches the object directly from
    the private S3 bucket via boto3 (credentials from settings) and
    streams it back in chunks, preserving the Content-Type returned by S3.

    - **200 OK** – object found and streamed.
    - **404 Not Found** – no such key in the bucket.
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
