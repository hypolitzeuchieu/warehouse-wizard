from rest_framework.response import Response
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from typing import Any, Optional, Dict


class StockResponseMixin:
    """
    Mixin for standardized API responses in stock management system
    """

    def success_response(
            self,
            data: Any = None,
            message: str = "Operation successful",
            status_code: int = status.HTTP_200_OK
    ) -> Response:
        """
        Standard success response
        """
        return Response({
            "success": True,
            "message": message,
            "data": data
        }, status=status_code)

    def created_response(
            self,
            data: Any = None,
            message: str = "Resource created successfully"
    ) -> Response:
        """
        Response for resource creation
        """
        return self.success_response(
            data=data,
            message=message,
            status_code=status.HTTP_201_CREATED
        )

    def updated_response(
            self,
            data: Any = None,
            message: str = "Resource updated successfully"
    ) -> Response:
        """
        Response for resource update
        """
        return self.success_response(
            data=data,
            message=message,
            status_code=status.HTTP_200_OK
        )

    def deleted_response(
            self,
            message: str = "Resource deleted successfully"
    ) -> Response:
        """
        Response for resource deletion
        """
        return self.success_response(
            data=None,
            message=message,
            status_code=status.HTTP_204_NO_CONTENT
        )

    def paginated_response(
            self,
            queryset: Any,
            serializer_class: Any,
            request: Any,
            context: Optional[Dict] = None,
            message: str = "Data retrieved successfully"
    ) -> Response:
        """
        Standardized paginated response
        """
        paginator = PageNumberPagination()
        page_size = request.query_params.get('page_size', 10)
        paginator.page_size = page_size
        page = paginator.paginate_queryset(queryset, request)

        serializer = serializer_class(
            page,
            many=True,
            context=context or {}
        )

        return Response({
            "success": True,
            "message": message,
            "data": serializer.data,
            "pagination": {
                "next": paginator.get_next_link(),
                "previous": paginator.get_previous_link(),
                "count": paginator.page.paginator.count,
                "current_page": paginator.page.number,
                "total_pages": paginator.page.paginator.num_pages,
                "page_size": int(page_size)
            }
        })

    def error_response(
            self,
            code: str,
            message: str,
            details: Optional[Dict] = None,
            status_code: int = status.HTTP_400_BAD_REQUEST
    ) -> Response:
        """
        Standard error response
        """
        return Response({
            "success": False,
            "error": {
                "code": code,
                "message": message,
                "details": details or {}
            }
        }, status=status_code)

    def validation_error_response(
            self,
            serializer_errors: Any
    ) -> Response:
        """
        Specialized response for validation errors
        """
        # Convert DRF validation errors to simplified format
        errors = {}
        if isinstance(serializer_errors, dict):
            for field, error_list in serializer_errors.items():
                if isinstance(error_list, list):
                    errors[field] = error_list[0] if error_list else ""
                else:
                    errors[field] = str(error_list)
        elif isinstance(serializer_errors, list):
            errors = {"non_field_errors": serializer_errors[0]}
        else:
            errors = {"error": str(serializer_errors)}

        return self.error_response(
            code="VALIDATION_FAILED",
            message="Input validation failed",
            details={"fields": errors},
            status_code=status.HTTP_400_BAD_REQUEST
        )

    def not_found_response(
            self,
            resource: str = "Resource"
    ) -> Response:
        """
        Standard response for not found errors
        """
        return self.error_response(
            code="NOT_FOUND",
            message=f"{resource} not found",
            status_code=status.HTTP_404_NOT_FOUND
        )

    def permission_denied_response(
            self,
            message: str = "You don't have permission to perform this action"
    ) -> Response:
        """
        Response for permission errors
        """
        return self.error_response(
            code="PERMISSION_DENIED",
            message=message,
            status_code=status.HTTP_403_FORBIDDEN
        )

    def authentication_failed_response(
            self,
            message: str = "Authentication failed"
    ) -> Response:
        """
        Response for authentication failures
        """
        return self.error_response(
            code="AUTHENTICATION_FAILED",
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED
        )

    def internal_error_response(
            self,
            error: Exception
    ) -> Response:
        """
        Response for unexpected internal errors
        """
        logger = getattr(self, 'logger', None)
        if logger:
            logger.error(f"Internal server error: {str(error)}")

        return self.error_response(
            code="INTERNAL_ERROR",
            message="An unexpected error occurred",
            details={"error": str(error)},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
