from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory

from .controllers.base import AcademicController, validate_payload


class ItemSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=10)
    score = serializers.IntegerField(min_value=0)
    tag = serializers.CharField(required=False, default="general")


class DecoratedSampleController(AcademicController):
    permission_classes = []
    authentication_classes = []

    @validate_payload(ItemSerializer)
    def create(self, request, *args, payload=None, **kwargs):
        return Response({"received": payload}, status=status.HTTP_201_CREATED)

    @validate_payload(ItemSerializer, partial=True)
    def partial_update(self, request, *args, pk=None, payload=None, **kwargs):
        return Response({"updated": payload, "pk": pk})

    @action(
        detail=True,
        methods=["post"],
        url_path="sub-items",
    )
    @validate_payload(
        ItemSerializer,
        merge_data=lambda self, request, pk=None: {"tag": f"parent-{pk}"},
    )
    def create_sub_item(self, request, pk=None, payload=None):
        return Response({"sub_item": payload, "pk": pk}, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["get"])
    def trigger_domain_error(self, request):
        raise DjangoValidationError("Domain validation failed.")

    @action(detail=False, methods=["get"])
    def trigger_field_domain_error(self, request):
        raise DjangoValidationError({"name": "Name is not unique."})


def test_validate_payload_valid_data():
    factory = APIRequestFactory()
    view = DecoratedSampleController.as_view({"post": "create"})

    req = factory.post("/", {"name": "Physics", "score": 100}, format="json")
    resp = view(req)
    assert resp.status_code == status.HTTP_201_CREATED
    assert resp.data == {"received": {"name": "Physics", "score": 100, "tag": "general"}}


def test_validate_payload_invalid_data():
    factory = APIRequestFactory()
    view = DecoratedSampleController.as_view({"post": "create"})

    # 'name' is too long (> 10 chars), 'score' is negative
    req = factory.post("/", {"name": "A_VERY_LONG_NAME", "score": -1}, format="json")
    resp = view(req)
    assert resp.status_code == status.HTTP_400_BAD_REQUEST
    assert "name" in resp.data
    assert "score" in resp.data


def test_validate_payload_partial_update():
    factory = APIRequestFactory()
    view = DecoratedSampleController.as_view({"patch": "partial_update"})

    # Send only 'score', 'name' should be omitted and not trigger required error
    req = factory.patch("/42/", {"score": 85}, format="json")
    resp = view(req, pk="42")
    assert resp.status_code == status.HTTP_200_OK
    assert resp.data == {"updated": {"score": 85}, "pk": "42"}


def test_validate_payload_merge_data():
    factory = APIRequestFactory()
    view = DecoratedSampleController.as_view({"post": "create_sub_item"})

    req = factory.post("/10/sub-items/", {"name": "Lab", "score": 90}, format="json")
    resp = view(req, pk="10")
    assert resp.status_code == status.HTTP_201_CREATED
    assert resp.data["sub_item"]["tag"] == "parent-10"


def test_handle_exception_catches_django_validation_error():
    factory = APIRequestFactory()
    view = DecoratedSampleController.as_view({"get": "trigger_domain_error"})

    req = factory.get("/trigger_domain_error/")
    resp = view(req)
    assert resp.status_code == status.HTTP_400_BAD_REQUEST
    assert "Domain validation failed." in str(resp.data)


def test_handle_exception_catches_django_field_validation_error():
    factory = APIRequestFactory()
    view = DecoratedSampleController.as_view({"get": "trigger_field_domain_error"})

    req = factory.get("/trigger_field_domain_error/")
    resp = view(req)
    assert resp.status_code == status.HTTP_400_BAD_REQUEST
    assert "name" in resp.data
