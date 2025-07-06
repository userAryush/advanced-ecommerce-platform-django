
from django.urls import path,include
from .views import ProductViewSet, register, login, ProductCategoryViewSet,OrderViewSet,OrderItemViewSet,PaymentViewSet

urlpatterns = [
    path('product-category-set/',ProductCategoryViewSet.as_view({'get':'list','post':'create'})),
    path('products-set/',ProductViewSet.as_view({'get':'list','post':'create'})),
    path('order-set/',OrderViewSet.as_view({'get':'list','post':'create'})),
    path('order-item-set/',OrderItemViewSet.as_view({'get':'list','post':'create'})),
    path('payment-set/',PaymentViewSet.as_view({'get':'list','post':'create'})),
    path('products-set/<int:pk>/',ProductViewSet.as_view({'get':'retrieve','put':'update','delete':'destroy'})),
    path('order-set/<int:pk>/checkout/', OrderViewSet.as_view({'post': 'checkout'})),
    path('register/',register),
    path('login/',login)

]