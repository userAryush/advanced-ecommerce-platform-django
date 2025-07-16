
from django.urls import path,include
from .views import ProductViewSet, ProductCategoryViewSet,OrderViewSet,OrderItemViewSet,PaymentViewSet
from .utils import  register, login,check_all_products_for_low_stock,group_id,admin_dashboard_analytics,supplier_dashboard_analytics,update_delivery_as_delivered

urlpatterns = [
    path('product-category-set/',ProductCategoryViewSet.as_view({'get':'list','post':'create'})),
    path('products-set/',ProductViewSet.as_view({'get':'list','post':'create'})),
    path('products-set/<int:pk>/',ProductViewSet.as_view({'get':'retrieve','put':'update','delete':'destroy'})),
    path('order-set/',OrderViewSet.as_view({'get':'list','post':'create'})),
    path('order-item-set/',OrderItemViewSet.as_view({'get':'list','post':'create'})),
    path('order-item-set/<int:pk>/',OrderItemViewSet.as_view({'get':'retrieve','put':'update','delete':'destroy'})),
    path('payment-set/',PaymentViewSet.as_view({'post':'create'})),
    path('order-set/<int:pk>/checkout/', OrderViewSet.as_view({'post': 'checkout'})),
    path('register/',register),
    path('login/',login),
    path('check-stock/',check_all_products_for_low_stock),
    path('group-listing/',group_id),
    path('admin-dashboard-analytics/',admin_dashboard_analytics),
    path('supplier-dashboard-analytics/',supplier_dashboard_analytics),
    path('deliveries/<int:delivery_pk>/update-status-delivered/', update_delivery_as_delivered),

]