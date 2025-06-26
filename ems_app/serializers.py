from .models import Product, User, Supplier, Customer,DeliveryPersonnel
from rest_framework.serializers import ModelSerializer

class ProductSerializer(ModelSerializer):
    class Meta:
        model = Product
        fields = '__all__'
class UserSerializer(ModelSerializer):
    class Meta:
        model = User
        fields = ['username','email','password','full_name','user_role']
        
class CustomerSerializer(ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = Customer
        fields = ['id', 'phone', 'address', 'user']
        
class SupplierSerializer(ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = Supplier
        fields = ['id', 'phone', 'address', 'user']
        
class DeliveryPersonnelSerializer(ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = DeliveryPersonnel
        fields = ['id', 'phone', 'address', 'user']