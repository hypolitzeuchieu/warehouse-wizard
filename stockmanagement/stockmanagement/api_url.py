from __future__ import annotations

from django.urls import include
from django.urls import path
from drf_yasg import openapi
from drf_yasg.generators import OpenAPISchemaGenerator
from drf_yasg.views import get_schema_view
from rest_framework.permissions import AllowAny


class CustomSchemaGenerator(OpenAPISchemaGenerator):
    def get_operation(self, view, path, prefix, method, components, request):
        """
        Override to handle errors in parser classes
        """
        try:
            return super().get_operation(view, path, prefix, method, components, request)
        except AttributeError as e:
            if "has no attribute 'media_type'" in str(e):
                # If there's an error with media_type, try to fix it
                # This is a workaround and should be used cautiously
                view.parser_classes = []
                return super().get_operation(view, path, prefix, method, components, request)
            raise


schema_view = get_schema_view(
    openapi.Info(
        title='Stock Management',
        default_version='v1',
        description='Documentation of API',
        # terms_of_service='https://www.google.com/policies/terms/',
        contact=openapi.Contact(email='hypolitdu13@gmail.com'),
        license=openapi.License(name='All right reserved'),
    ),
    public=True,
    permission_classes=[AllowAny],
    authentication_classes=[],
    generator_class=CustomSchemaGenerator,
)

urlpatterns = [
    path('v1/', include('authentication.urls')),
    path('v1/', include('stock.urls')),
    path('v1/', include('reports.urls')),
    path('v1/', include('notifications.urls')),
    path('v1/', include('dashboard.urls')),
    path(
        'v1/docs/',
        schema_view.with_ui('swagger', cache_timeout=0),
        name='schema-swagger-ui',
    ),
    path('v1/redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
]
