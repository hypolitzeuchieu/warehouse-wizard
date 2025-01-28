from rest_framework.routers import DefaultRouter

from reports.views import ReportsViewSet


router = DefaultRouter()
router.register(r'report', ReportsViewSet, basename='report-inventory')

urlpatterns = router.urls
