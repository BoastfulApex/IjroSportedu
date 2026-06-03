from django.contrib import admin
from .models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ["task"]


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display  = ["number", "title", "date", "is_confirmed", "created_by", "created_at"]
    list_filter   = ["is_confirmed", "date"]
    search_fields = ["number", "title"]
    inlines       = [OrderItemInline]
