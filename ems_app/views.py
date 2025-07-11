from rest_framework.decorators import api_view, action
from rest_framework.response import Response
from django.contrib.auth.hashers import make_password
from .models import Product,Order, OrderItem, Payment, Delivery, Notification
from .serializers import *
from rest_framework.viewsets import ModelViewSet
from django.contrib.auth import authenticate
from rest_framework.authtoken.models import Token
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework import status
from .utils import create_notification


# this is for supplier or admin to create a unique category under which products related to that will exists.
class ProductCategoryViewSet(ModelViewSet):
    queryset = ProductCategory.objects.all()
    serializer_class = ProductCategorySerializer
    search_fields = ['category_name']


    #overriding the create function so that if the user tries to create the similar category he gets an error with the existing category id so that it will be easier for him to find out the category 
    # def perform_create(self, serializer):
    #     # extracting the category_name that user is trying to create
    #     category_name = serializer.validated_data.get('category_name')
        
    #     # Check if category already exists
    #     try:
    #         existing_category = ProductCategory.objects.get(category_name=category_name)
    #     except ProductCategory.DoesNotExist:
    #         existing_category = None
    #     # or simply use filter to avoid try except
    #     # existing_category = ProductCategory.objects.filter(category_name=category_name).first()
        
    #     if existing_category:
    #         raise ValidationError(
    #             {"detail": f"Category '{category_name}' already exists Use this id {existing_category.id} for this category!!"}
    #         )

    #     # if not overriden drf would have called this to save incoming data without checking any extra conditions
    #     serializer.save()
            
    
class ProductViewSet(ModelViewSet):
    serializer_class = ProductSerializer
    search_fields = ['product_name','product_price','category__category_name']
    filterset_fields = ['product_name','category__category_name']
    
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
                f"Not enough stock for '{product.product_name}'. "
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


from .utils import send_notification_email
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
                        {'detail': f"Not enough stock for product '{product.product_name}' at payment time."},
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
            subject = f"Order #{order.id} Confirmation"
            body = (
                f"Dear {user.full_name},\n\n"
                f"Your order #{order.id} has been placed successfully.\n"
                f"We will notify you when it is shipped.\n\n"
                f"Order Total: ${order.total_amount}\n\n"
                f"Thank you for shopping with us!"
            )

            send_notification_email(subject, body, [user.email])
        
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
    
    

    
class NotificationViewSet(ModelViewSet):
    serializer_class = NotificationSerializer


    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user).order_by('-created_at')

    @action(detail=True, methods=['post'])
    def mark_as_read(self, request, pk=None):
        notification = self.get_object()
        notification.is_read = True
        notification.save()
        return Response({'detail': 'Notification marked as read.'})    
    
    