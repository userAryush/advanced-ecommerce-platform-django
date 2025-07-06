from .models import Product, User, Supplier, Customer,DeliveryPersonnel,Order,OrderItem,ProductCategory, Payment
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
        
class OrderSerializer(ModelSerializer):
    class Meta:
        model = Order
        fields = '__all__'
        read_only_fields = ['customer','total_amount','status','payment_status']
        
class OrderItemSerializer(ModelSerializer):
    class Meta:
        model = OrderItem
        fields = '__all__'
        
class ProductCategorySerializer(ModelSerializer):
    class Meta:
        model = ProductCategory
        fields = '__all__'
        
class PaymentSerializer(ModelSerializer):
    class Meta:
        model = Payment
        fields = '__all__'
        
        read_only_fields = ['customer', 'amount', 'status']