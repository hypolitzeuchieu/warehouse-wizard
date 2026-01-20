"""User ViewSet for user search functionality."""

from __future__ import annotations

from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from application.dto.user_dto import UserSearchDTO
from application.use_cases.user_use_cases import SearchUsersUseCase
from infrastructure.persistence.repositories import UserRepositoryImpl
from presentation.serializers.user_serializers import UserSearchResultSerializer
from shared.views.base_viewset import BaseViewSet


class UserViewSet(BaseViewSet):
    """ViewSet for user search functionality."""

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        method="get",
        operation_summary="List/Search users",
        operation_description=(
            "List all users or search for users by email, phone number, or name. "
            "If no search parameters are provided, returns all users in the platform. "
            "Useful for finding existing users to add to a business."
        ),
        manual_parameters=[
            openapi.Parameter(
                name="q",
                in_=openapi.IN_QUERY,
                description="Search query (searches in email, phone_number, and name).",
                type=openapi.TYPE_STRING,
            ),
            openapi.Parameter(
                name="email",
                in_=openapi.IN_QUERY,
                description="Search by exact email address.",
                type=openapi.TYPE_STRING,
            ),
            openapi.Parameter(
                name="phone_number",
                in_=openapi.IN_QUERY,
                description="Search by exact phone number.",
                type=openapi.TYPE_STRING,
            ),
            openapi.Parameter(
                name="name",
                in_=openapi.IN_QUERY,
                description="Search by name (partial match).",
                type=openapi.TYPE_STRING,
            ),
            openapi.Parameter(
                name="page",
                in_=openapi.IN_QUERY,
                description="Page number (defaults to 1).",
                type=openapi.TYPE_INTEGER,
            ),
            openapi.Parameter(
                name="page_size",
                in_=openapi.IN_QUERY,
                description="Number of records per page (defaults to 20, max 100).",
                type=openapi.TYPE_INTEGER,
            ),
        ],
        responses={
            200: "List of users matching search criteria",
            400: "Bad Request",
            401: "Unauthorized",
        },
        tags=["Users"],
    )
    @action(detail=False, methods=["get"], url_path="search")
    def search(self, request: Request) -> Response:
        """Search for users by email, phone number, or name."""
        try:
            search_query = request.query_params.get("q", "").strip() or None
            email = request.query_params.get("email", "").strip() or None
            phone_number = request.query_params.get("phone_number", "").strip() or None
            name = request.query_params.get("name", "").strip() or None

            search_dto = UserSearchDTO(
                email=email,
                phone_number=phone_number,
                name=name,
                search_query=search_query,
            )

            use_case = SearchUsersUseCase(user_repository=UserRepositoryImpl())
            user_dtos = use_case.execute(search_dto)

            filter_payload = self.parse_list_filters(
                request,
                search_fields=["name", "email", "phone_number"],
                order_fields=["name", "email", "created_at"],
                default_order_field="name",
            )

            user_dtos = self.apply_filtering_to_items(
                user_dtos,
                filter_payload,
                name_fields=["name", "email", "phone_number"],
            )

            simplified_users = [
                UserSearchResultSerializer.from_dto(user_dto) for user_dto in user_dtos
            ]

            return self.paginated_response(
                request=request,
                queryset=simplified_users,
                serializer_class=UserSearchResultSerializer,
                message="Users retrieved successfully",
            )
        except Exception as e:
            return self.handle_exception(e)
