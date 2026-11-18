from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory
from rest_framework.viewsets import ViewSet

from .router import AcademicRouter


class MultiMethodSampleViewSet(ViewSet):
    permission_classes = []
    authentication_classes = []

    @action(detail=True, methods=["get"], url_path="items", url_name="items")
    def list_items(self, request, pk=None):
        return Response({"action": "list_items", "pk": pk})

    @action(detail=True, methods=["post"], url_path="items", url_name="items")
    def create_item(self, request, pk=None):
        return Response({"action": "create_item", "pk": pk}, status=status.HTTP_201_CREATED)

    @action(
        detail=True,
        methods=["patch"],
        url_path=r"items/(?P<child_pk>[^/.]+)",
        url_name="item-detail",
    )
    def update_item(self, request, pk=None, child_pk=None):
        return Response({"action": "update_item", "pk": pk, "child_pk": child_pk})

    @action(
        detail=True,
        methods=["delete"],
        url_path=r"items/(?P<child_pk>[^/.]+)",
        url_name="item-detail",
    )
    def delete_item(self, request, pk=None, child_pk=None):
        return Response(status=status.HTTP_204_NO_CONTENT)


def test_academic_router_merges_multi_method_actions():
    router = AcademicRouter()
    router.register("samples", MultiMethodSampleViewSet, basename="sample")

    urls = router.urls
    url_patterns = [str(u.pattern) for u in urls]

    # Verify that duplicate regex patterns are not created
    items_pattern = "^samples/(?P<pk>[^/.]+)/items/$"
    assert url_patterns.count(items_pattern) == 1

    child_pattern = "^samples/(?P<pk>[^/.]+)/items/(?P<child_pk>[^/.]+)/$"
    assert url_patterns.count(child_pattern) == 1

    factory = APIRequestFactory()

    # Find the view callback for items_pattern
    items_view = next(u.callback for u in urls if str(u.pattern) == items_pattern)

    # Test GET dispatches to list_items
    get_req = factory.get("/samples/42/items/")
    get_resp = items_view(get_req, pk="42")
    assert get_resp.status_code == status.HTTP_200_OK
    assert get_resp.data == {"action": "list_items", "pk": "42"}

    # Test POST dispatches to create_item
    post_req = factory.post("/samples/42/items/")
    post_resp = items_view(post_req, pk="42")
    assert post_resp.status_code == status.HTTP_201_CREATED
    assert post_resp.data == {"action": "create_item", "pk": "42"}

    # Test PUT is not allowed (405)
    put_req = factory.put("/samples/42/items/")
    put_resp = items_view(put_req, pk="42")
    assert put_resp.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    # Find the view callback for child_pattern
    child_view = next(u.callback for u in urls if str(u.pattern) == child_pattern)

    # Test PATCH dispatches to update_item
    patch_req = factory.patch("/samples/42/items/99/")
    patch_resp = child_view(patch_req, pk="42", child_pk="99")
    assert patch_resp.status_code == status.HTTP_200_OK
    assert patch_resp.data == {"action": "update_item", "pk": "42", "child_pk": "99"}

    # Test DELETE dispatches to delete_item
    del_req = factory.delete("/samples/42/items/99/")
    del_resp = child_view(del_req, pk="42", child_pk="99")
    assert del_resp.status_code == status.HTTP_204_NO_CONTENT
