from rest_framework.decorators import api_view, action
from rest_framework.response import Response
from django.contrib.auth.hashers import make_password
from .models import Product,Order, OrderItem, Payment, Delivery
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
        if order.status != 'cart':
            return Response({'error': 'Only cart orders can be checked out.'}, status=400)
        if order.total_amount <= 0:
            raise ValidationError('Cannot checkout an empty cart.')

        # Check stock but do NOT reduce stock yet
        for item in order.items.all():
            if item.product.stock_quantity < item.quantity:
                raise ValidationError(
                    f"Not enough stock for product '{item.product.name}'. "
                    f"Available: {item.product.stock_quantity}, requested: {item.quantity}"
                )

        order.status = 'checkout_pending'  # Waiting for payment
        order.save()

        # Return order summary (bill)
        serializer = self.get_serializer(order)
        return Response({
            'message': 'Order ready for payment.',
            'order': serializer.data
        }, status=200)

    
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
        product = serializer.validated_data['product']
        quantity = serializer.validated_data['quantity']

        if user.user_role != 'customer' or order.customer != user.customer:
            raise PermissionDenied('You can only add items to your own cart.')

        # ✅ Check stock before adding
        if product.stock_quantity < quantity:
            raise ValidationError(
                f"Not enough stock for '{product.name}'. "
                f"Available: {product.stock_quantity}, requested: {quantity}."
            )

        serializer.save(price=product.product_price)
        self.update_order_total(order)

    def perform_update(self, serializer):
        product = serializer.validated_data.get('product', None)
        instance = serializer.instance

        if product:
            serializer.save(price=product.price)
        else:
            serializer.save()

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



class PaymentViewSet(ModelViewSet):
    serializer_class = PaymentSerializer

    def get_queryset(self):
        user = self.request.user
        if user.user_role == 'customer':
            return Payment.objects.filter(customer=user.customer)
        return Payment.objects.all()

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        order = serializer.validated_data['order']
        user = request.user

        if order.customer != user.customer:
            return Response({'detail': 'You can only pay for your own orders.'}, status=status.HTTP_403_FORBIDDEN)

        if order.status != 'checkout_pending':
            return Response({'detail': 'Payment can only be done for orders in checkout pending status.'}, status=status.HTTP_400_BAD_REQUEST)

        if order.total_amount <= 0:
            return Response({'detail': 'Cannot create payment for order with zero total.'}, status=status.HTTP_400_BAD_REQUEST)

        payment = serializer.save(
            customer=user.customer,
            amount=order.total_amount,
            status='completed'  # Assume success for simplicity
        )

        if payment.status == 'completed':
            order.payment_status = 'paid'
            order.status = 'placed'

            for item in order.items.all():
                product = item.product
                if product.stock_quantity < item.quantity:
                    return Response(
                        {'detail': f"Not enough stock for product '{product.name}' at payment time."},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                product.stock_quantity -= item.quantity
                product.save()

            order.save()

            Delivery.objects.create(
                order=order,
                delivery_personnel=None,
                delivery_status='pending',
                delivered_date=None,
                delivery_address=order.customer.address
            )
        
        return Response(
            {'detail': 'Payment successful and order placed.', 'payment': serializer.data},
            status=status.HTTP_201_CREATED,
        )


    def perform_update(self, serializer):
        payment = serializer.save()
        order = payment.order

        if payment.status == 'completed':
            order.payment_status = 'paid'
            order.save()
        elif payment.status == 'failed':
            order.payment_status = 'failed'
            order.save()
    
    
    
    
    