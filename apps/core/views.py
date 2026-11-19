import os

from django.conf import settings
from django.core import signing
from django.http import Http404
from django.views.decorators.http import require_GET

from .files import file_response, load_signed_token


@require_GET
def protected_file(request, token):
    """Imzolangan havola bo'yicha fayl. Imzo noto'g'ri, muddati o'tgan yoki fayl yo'q — 404."""
    try:
        storage_name, filename = load_signed_token(token)
    except signing.BadSignature:  # SignatureExpired ham shu turdan
        raise Http404
    full_path = os.path.normpath(os.path.join(settings.MEDIA_ROOT, storage_name))
    if not full_path.startswith(os.path.normpath(str(settings.MEDIA_ROOT)) + os.sep) or not os.path.isfile(full_path):
        raise Http404
    return file_response(storage_name, filename)
