from rest_framework.decorators import api_view, action
from rest_framework.response import Response
from django.contrib.auth.hashers import make_password
from .models import Product,Order, OrderItem, Payment
from .serializers import *
from rest_framework.viewsets import ModelViewSet
from django.contrib.auth import authenticate
from rest_framework.authtoken.models import Token
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework import status




@api_view(['POST'])
def register(request):
    data = request.data.copy()
    raw_password = data.get('password')
    data['password'] = make_password(raw_password)

    user_serializer = UserSerializer(data=data)

    if user_serializer.is_valid():
        user = user_serializer.save()
        user_role = user.user_role

        profile_data = {
            'phone': data.get('phone'),
            'address': data.get('address')
        }

        if user_role == 'customer':
            customer_serializer = CustomerSerializer(data=profile_data)
            if customer_serializer.is_valid():
                customer_serializer.save(user=user)
                return Response({'message': 'Customer created!', 'data': customer_serializer.data}, status=201)
            else:
                return Response(customer_serializer.errors, status=400)

        elif user_role == 'supplier':
            supplier_serializer = SupplierSerializer(data=profile_data)
            if supplier_serializer.is_valid():
                supplier_serializer.save(user=user)
                return Response({'message': 'Supplier created!', 'data': supplier_serializer.data}, status=201)
            else:
                return Response(supplier_serializer.errors, status=400)

        elif user_role == 'delivery':
            delivery_serializer = DeliveryPersonnelSerializer(data=profile_data)
            if delivery_serializer.is_valid():
                delivery_serializer.save(user=user)
                return Response({'message': 'Delivery Personnel created!', 'data': delivery_serializer.data}, status=201)
            else:
                return Response(delivery_serializer.errors, status=400)

        elif user_role == 'admin':
            return Response({'error': 'Admin accounts must be created by system administrators.'}, status=403)

        else:
            return Response({'error': 'Invalid user role'}, status=400)

    else:
        return Response(user_serializer.errors, status=400)


@api_view(['POST'])
def login(request):
    email = request.data.get('email')
    password = request.data.get('password')
    
    user = authenticate(request, email=email, password=password) #if matched returns user object else None
    
    if user == None:
        return Response({'error': 'Invalid credentials!'})
    else:
        #create token
        token,_ = Token.objects.get_or_create(user=user)
        return Response(token.key)       

class ProductCategoryViewSet(ModelViewSet):
    queryset = ProductCategory.objects.all()
    serializer_class = ProductCategorySerializer
    
class ProductViewSet(ModelViewSet):
    serializer_class = ProductSerializer
    filterset_fields = ['category']
    
    def get_queryset(self):
        user = self.request.user
        
        if user.user_role == 'supplier':
            return Product.objects.filter(supplier=user.supplier)
        
        return Product.objects.all()# if customer or admin ho vane herna pauna paro sab
    
    def perform_create(self, serializer):
        user = self.request.user
        
        if user.user_role != 'supplier':
            raise PermissionDenied('Only suppliers can create products')
        
        supplier = user.supplier
        serializer.save(supplier=user.supplier)
        
    def get_object(self):
        obj = super().get_object()
        user = self.request.user
        
        if user.user_role == 'supplier' and obj.supplier.user != user:
            raise PermissionDenied('You can only view your own products')
        
        elif user.user_role != 'supplier':
            raise PermissionDenied('Only suppliers can view their own products')
        return obj
    
    def update(self, request, *args, **kwargs):
        user = request.user
        obj = self.get_object()  # This already checks supplier ownership

        if user.user_role == 'supplier' and obj.supplier != user.supplier:
            raise PermissionDenied('You can only update your own products.')

            return super().update(request, *args, **kwargs)
    
class OrderViewSet(ModelViewSet):
    serializer_class = OrderSerializer
    
    def get_queryset(self):
        user = self.request.user
        if user.user_role == 'customer':
            return Order.objects.filter(customer=user.customer)
        return Order.objects.all()

    def perform_create(self, serializer):
        user = self.request.user
        if user.user_role != 'customer':
            raise PermissionDenied('Only customers can create orders (carts).')
        
        serializer.save(
            customer=user.customer,
            status='cart',
            payment_status='pending',
            total_amount=0
        )
        
    @action(detail=True, methods=['post'])
    def checkout(self, request, pk=None):
        order = self.get_object()
        
        user = request.user

        if user.user_role != 'customer' or order.customer != user.customer:
            raise PermissionDenied('You can only checkout your own order.')

        if order.total_amount <= 0:
            raise ValidationError('Cannot checkout an empty cart.')

        if order.payment_status != 'paid':
            raise ValidationError('Please complete payment before checkout.')
        
        

        order.status = 'ordered'  # Or 'ordered', or whatever your workflow needs
                # ✅ Check and update stock for each item
        for item in order.items.all():  # Make sure your Order model uses related_name='items'
            product = item.product

            if product.stock_quantity < item.quantity:
                raise ValidationError(
                    f"Not enough stock for product '{product.name}'. "
                    f"Available: {product.stock_quantity}, requested: {item.quantity}"
                )

        # ✅ All good, reduce stock now
        for item in order.items.all():
            product = item.product
            product.stock_quantity -= item.quantity
            product.save()
        
        order.save()

        return Response({'status': 'Order placed successfully!'}, status=status.HTTP_200_OK)
    
class OrderItemViewSet(ModelViewSet):

    serializer_class = OrderItemSerializer
    
    def get_queryset(self):
        user = self.request.user
        if user.user_role == 'customer':
            return OrderItem.objects.filter(order__customer=user.customer)
        return OrderItem.objects.all()

    def perform_create(self, serializer):
        user = self.request.user
        order = serializer.validated_data['order']

        # ✅ Ensure customer owns the order
        if user.user_role != 'customer' or order.customer != user.customer:
            raise PermissionDenied('You can only add items to your own cart.')

        instance = serializer.save()
        self.update_order_total(order)

    def perform_update(self, serializer):
        instance = serializer.save()
        self.update_order_total(instance.order)

    def perform_destroy(self, instance):
        order = instance.order
        instance.delete()
        self.update_order_total(order)

    def update_order_total(self, order):
        total = sum(
            item.price * item.quantity for item in order.items.all()
        )
        order.total_amount = total
        order.save()
    

class PaymentViewSet(ModelViewSet):
    serializer_class = PaymentSerializer

    def get_queryset(self):
        user = self.request.user
        if user.user_role == 'customer':
            return Payment.objects.filter(customer=user.customer)
        return Payment.objects.all()

    def perform_create(self, serializer):
        user = self.request.user
        order = serializer.validated_data['order']

        # ✅ Ensure customer owns the order
        if order.customer != user.customer:
            raise PermissionDenied('You can only pay for your own orders.')
        if order.total_amount <= 0:
            raise ValidationError('Cannot create payment for order with zero total.')

        payment = serializer.save(customer=user.customer, amount=order.total_amount, status='completed')

        # Automatically update Order status if payment is already marked completed
        if payment.status == 'completed':
            order.payment_status = 'paid'
            order.save()

    def perform_update(self, serializer):
        payment = serializer.save()
        order = payment.order

        if payment.status == 'completed':
            order.payment_status = 'paid'
            order.save()
        elif payment.status == 'failed':
            order.payment_status = 'failed'
            order.save()
    
    
    
    
    