from django.urls import include, path
from drf_yasg import openapi
from drf_yasg.views import get_schema_view
from rest_framework import permissions
from rest_framework_simplejwt.authentication import JWTAuthentication


schema_view = get_schema_view(
    openapi.Info(
        title="Stock Management",
        default_version='v1',
        description="Documentation of API",
        terms_of_service="https://www.google.com/policies/terms/",
        contact=openapi.Contact(email=''),
        license=openapi.License(name='All right reserved'),
    ),
    public=True,
    permission_classes=[permissions.AllowAny,],
    authentication_classes=[JWTAuthentication],
)


urlpatterns = [
    path('v1/', include('authentication.urls')),
    path('v1/', include('inventory.urls')),
    path('v1/', include('product.urls')),
    path('v1/', include('reports.urls')),
    path('v1/', include('sales.urls')),
    path('docs/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
]
