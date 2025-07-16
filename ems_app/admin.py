from django.contrib import admin
from .models import *

# Register your models here.

admin.site.register(User)
admin.site.register(Supplier)
admin.site.register(Customer)
admin.site.register(DeliveryPersonnel)
admin.site.register(Product)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['id', 'customer', 'status', 'created_at']  # attributes to show in the list view
    list_filter = ['status']  
admin.site.register(Order, OrderAdmin)
# admin.site.register(OrderItem)
admin.site.register(Payment)
admin.site.register(Delivery)
