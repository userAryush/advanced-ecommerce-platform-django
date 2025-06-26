
from django.urls import path,include
from .views import ProductViewSet, register, login

urlpatterns = [
    path('products-set/',ProductViewSet.as_view({'get':'list','post':'create'})),
    path('register/',register),
    path('login/',login)

]