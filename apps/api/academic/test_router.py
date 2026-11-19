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


def test_controller_decorator_registers_viewset():
    from .decorators import controller

    custom_router = AcademicRouter()

    @controller("test-entities", basename="test-entity", router=custom_router)
    class SampleViewSet(ViewSet):
        permission_classes = []
        authentication_classes = []

        def list(self, request):
            return Response({"items": []})

    assert SampleViewSet._controller_prefix == "test-entities"
    patterns = [str(u.pattern) for u in custom_router.urls]
    assert "^test-entities/$" in patterns

    factory = APIRequestFactory()
    list_view = next(u.callback for u in custom_router.urls if str(u.pattern) == "^test-entities/$")
    resp = list_view(factory.get("/test-entities/"))
    assert resp.status_code == status.HTTP_200_OK
    assert resp.data == {"items": []}


def test_controller_decorator_registers_apiview():
    from rest_framework.views import APIView

    from .decorators import controller

    custom_router = AcademicRouter()

    @controller("test-standalone", basename="test-standalone-view", router=custom_router)
    class StandaloneAPIView(APIView):
        permission_classes = []
        authentication_classes = []

        def get(self, request):
            return Response({"standalone": True})

    assert StandaloneAPIView._controller_prefix == "test-standalone"
    patterns = [str(u.pattern) for u in custom_router.urls]
    assert "test-standalone/" in patterns

    factory = APIRequestFactory()
    view = next(u.callback for u in custom_router.urls if str(u.pattern) == "test-standalone/")
    resp = view(factory.get("/test-standalone/"))
    assert resp.status_code == status.HTTP_200_OK
    assert resp.data == {"standalone": True}


def test_http_verb_decorators():
    from .decorators import controller, delete, get, patch, post, put

    custom_router = AcademicRouter()

    @controller("verb-samples", basename="verb-sample", router=custom_router)
    class VerbSampleViewSet(ViewSet):
        permission_classes = []
        authentication_classes = []

        @get("custom-get", detail=False)
        def custom_get(self, request):
            return Response({"method": "GET"})

        @post("custom-post", detail=False)
        def custom_post(self, request):
            return Response({"method": "POST"}, status=status.HTTP_201_CREATED)

        @put("custom-put", detail=False)
        def custom_put(self, request):
            return Response({"method": "PUT"})

        @patch("custom-patch", detail=False)
        def custom_patch(self, request):
            return Response({"method": "PATCH"})

        @delete("custom-del", detail=False)
        def custom_del(self, request):
            return Response(status=status.HTTP_204_NO_CONTENT)

    urls = custom_router.urls
    patterns = {str(u.pattern): u.callback for u in urls}
    factory = APIRequestFactory()

    assert "^verb-samples/custom-get/$" in patterns
    get_cb = patterns["^verb-samples/custom-get/$"]
    assert get_cb(factory.get("/verb-samples/custom-get/")).data == {"method": "GET"}

    assert "^verb-samples/custom-post/$" in patterns
    post_cb = patterns["^verb-samples/custom-post/$"]
    assert (
        post_cb(factory.post("/verb-samples/custom-post/")).status_code == status.HTTP_201_CREATED
    )

    assert "^verb-samples/custom-put/$" in patterns
    put_cb = patterns["^verb-samples/custom-put/$"]
    assert put_cb(factory.put("/verb-samples/custom-put/")).data == {"method": "PUT"}

    assert "^verb-samples/custom-patch/$" in patterns
    patch_cb = patterns["^verb-samples/custom-patch/$"]
    assert patch_cb(factory.patch("/verb-samples/custom-patch/")).data == {"method": "PATCH"}

    assert "^verb-samples/custom-del/$" in patterns
    del_cb = patterns["^verb-samples/custom-del/$"]
    assert (
        del_cb(factory.delete("/verb-samples/custom-del/")).status_code
        == status.HTTP_204_NO_CONTENT
    )


def test_explicit_crud_route_decorators():
    from .decorators import controller, delete, get, patch, post

    custom_router = AcademicRouter()

    @controller("explicit-crud", basename="explicit-item", router=custom_router)
    class ExplicitCrudViewSet(ViewSet):
        permission_classes = []
        authentication_classes = []

        @get()
        def list(self, request):
            return Response({"action": "list"})

        @post()
        def create(self, request):
            return Response({"action": "create"}, status=status.HTTP_201_CREATED)

        @get("{id}")
        def retrieve(self, request, pk=None):
            return Response({"action": "retrieve", "pk": pk})

        @patch("{id}")
        def update(self, request, pk=None):
            return Response({"action": "update", "pk": pk})

        @delete("{id}")
        def destroy(self, request, pk=None):
            return Response(status=status.HTTP_204_NO_CONTENT)

        @get("{id}/stats")
        def stats(self, request, pk=None):
            return Response({"action": "stats", "pk": pk})

    urls = custom_router.urls
    patterns = {str(u.pattern): u.callback for u in urls}
    factory = APIRequestFactory()

    assert "^explicit-crud/$" in patterns
    assert "^explicit-crud/(?P<pk>[^/.]+)/$" in patterns
    assert "^explicit-crud/(?P<pk>[^/.]+)/stats/$" in patterns

    list_cb = patterns["^explicit-crud/$"]
    assert list_cb(factory.get("/explicit-crud/")).data == {"action": "list"}
    assert list_cb(factory.post("/explicit-crud/")).status_code == status.HTTP_201_CREATED

    detail_cb = patterns["^explicit-crud/(?P<pk>[^/.]+)/$"]
    assert detail_cb(factory.get("/explicit-crud/42/"), pk="42").data == {
        "action": "retrieve",
        "pk": "42",
    }
    assert detail_cb(factory.patch("/explicit-crud/42/"), pk="42").data == {
        "action": "update",
        "pk": "42",
    }
    assert (
        detail_cb(factory.delete("/explicit-crud/42/"), pk="42").status_code
        == status.HTTP_204_NO_CONTENT
    )

    stats_cb = patterns["^explicit-crud/(?P<pk>[^/.]+)/stats/$"]
    assert stats_cb(factory.get("/explicit-crud/42/stats/"), pk="42").data == {
        "action": "stats",
        "pk": "42",
    }


def test_academic_router_contains_all_decorated_controllers():
    import academic.controllers  # noqa: F401
    from academic.router import academic_router

    patterns = [str(u.pattern) for u in academic_router.urls]

    # Verify standard resource ViewSets
    expected_viewsets = [
        "^institutions/$",
        "^departments/$",
        "^terms/$",
        "^courses/$",
        "^programs/$",
        "^program-courses/$",
        "^program-memberships/$",
        "^offerings/$",
        "^instructor-assignments/$",
        "^enrollments/$",
        "^po-sets/$",
        "^program-outcome-sets/$",
        "^program-outcomes/$",
        "^syllabi/$",
        "^grades/$",
        "^grade-batches/$",
        "^assessments/$",
    ]
    for exp in expected_viewsets:
        assert exp in patterns, f"Expected {exp} in academic_router.urls"

    # Verify workspace APIViews
    expected_apiviews = [
        "workspaces/instructor/",
        "workspaces/student/",
        "workspaces/coordinator/",
    ]
    for exp in expected_apiviews:
        assert exp in patterns, f"Expected {exp} in academic_router.urls"
