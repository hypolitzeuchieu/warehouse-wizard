from __future__ import annotations

from django.contrib import admin
from notifications.models import Notification


class NotificationAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'product', 'notification_type', 'status', 'created_at')
    list_filter = ('notification_type', 'status', 'created_at')
    search_fields = ('user__username', 'product__name', 'message')
    ordering = ('-created_at',)
    readonly_fields = ('id', 'created_at')


admin.site.register(Notification, NotificationAdmin)
