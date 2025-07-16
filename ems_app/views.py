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
from rest_framework.permissions import DjangoModelPermissions


# this is for supplier or admin to create a unique category under which products related to that will exists.
class ProductCategoryViewSet(ModelViewSet):
    queryset = ProductCategory.objects.all()
    serializer_class = ProductCategorySerializer
    search_fields = ['category_name']
    permission_classes = [DjangoModelPermissions]


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
    permission_classes = [DjangoModelPermissions]    
    def get_queryset(self):
        user = self.request.user
        
        if user.user_role == 'supplier':
            return Product.objects.filter(supplier=user.supplier)
        
        return Product.objects.all()# if customer or admin ho vane herna pauna paro sab
    
    def perform_create(self, serializer):
        user = self.request.user
        # if user.user_role != 'supplier':
        #     raise PermissionDenied('Only suppliers can create products')   # now have set groups and permission instead of this now the permission check is handled before calling this perform_Create function
        current_logged_supplier = user.supplier  # so that the product will be created with logged supplier only
        serializer.save(supplier=current_logged_supplier)
        
    # for retrive , update and delete get_object uses get_queryset where i have already filtered out suppliers products so even if other supplier tries to access others product then he fails to do so as the get_queryset returns only his products and API will respond with a 404 error   {"detail": "No Product matches the given query."}
        
   
class OrderViewSet(ModelViewSet):
    serializer_class = OrderSerializer
    permission_classes = [DjangoModelPermissions]   
    
    # customer gets to see their order only and admin gets to see all other users cant through groups and permission 
    def get_queryset(self):
        user = self.request.user
        if user.user_role == 'customer':
            return Order.objects.filter(customer=user.customer)
        # admin shoudlnt be able to see pending orders
        
        elif user.user_role == 'admin':
            allowed_status = ['ordered', 'shipped', 'delivered', 'cancelled']
            return Order.objects.filter(status__in=allowed_status)
        
        return Order.objects.none()

    def perform_create(self, serializer):
        user = self.request.user
        # if user.user_role != 'customer':
        #     raise PermissionDenied('Only customers can create orders.')
        serializer.save(customer=user.customer,status='cart',payment_status='pending',total_amount=0  )
    
    @action(detail=True, methods=['post'])
    def checkout(self, request, pk=None):
        order = self.get_object()
        user = request.user

        if user.user_role != 'customer' or order.customer != user.customer:
            raise PermissionDenied('You can only checkout your own order!!')
        if order.status != 'cart':
            return Response({'error': 'Only cart orders can be checked out.'}, status=400)
        if order.total_amount <= 0:
            raise ValidationError('Cannot checkout an empty cart.')

        # Check stock but do NOT reduce stock yet
        for item in order.items.all():
            if item.product.stock_quantity < item.quantity:
                raise ValidationError( f"Not enough stock for product '{item.product.name}'. "f"Available: {item.product.stock_quantity}, requested: {item.quantity}")

        order.status = 'checkout_pending'  # Waiting for payment
        order.save()

        # Return order like a bill
        serializer = self.get_serializer(order)
        return Response({'message': 'Order ready for payment.','order': serializer.data}, status=200)

    
class OrderItemViewSet(ModelViewSet):

    serializer_class = OrderItemSerializer
    permission_classes = [DjangoModelPermissions]   
    def get_queryset(self):
        user = self.request.user
        if user.user_role == 'customer':
            return OrderItem.objects.filter(order__customer=user.customer, order__status='cart' )
        else:
            return OrderItem.objects.none()
       

    def perform_create(self, serializer):
        user = self.request.user
        order = serializer.validated_data['order']
        product = serializer.validated_data['product']
        quantity = serializer.validated_data['quantity']

        if user.user_role != 'customer' or order.customer != user.customer:
            raise PermissionDenied('You can only add items to your own cart.')

        # Check stock before adding
        if product.stock_quantity < quantity:
            raise ValidationError(
                f"Not enough stock for '{product.product_name}'. "
                f"Available product at the moment: {product.stock_quantity}, you requested for: {quantity}."
            )

        serializer.save(price=product.product_price)
        self.update_order_total(order)

    def perform_update(self, serializer):
        # here aba if product nei change garo vane tyo aaune vo product ma else itll be none with same product
        product = serializer.validated_data.get('product', None)
        instance = serializer.instance

        if product:
            # if new product chaneko cha vane you need to update the price
            serializer.save(price=product.price)
        else:
            serializer.save()

        self.update_order_total(instance.order)


    def perform_destroy(self, instance):
        order = instance.order
        if order.status != 'cart':
            raise PermissionDenied('You can only remove items from your cart before checkout.')
        instance.delete()
        self.update_order_total(order)

    def update_order_total(self, order):
        total = 0 

        # Loop through each item in the order
        for item in order.items.all():
            item_total = item.price * item.quantity  # Calculate total for this item
            total += item_total  # Add it to the overall total

        # Update the order's total_amount
        order.total_amount = total

        order.save()
    
from .utils import send_notification_email
class PaymentViewSet(ModelViewSet):
    serializer_class = PaymentSerializer
    permission_classes = [DjangoModelPermissions]
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
    permission_classes = [DjangoModelPermissions]

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user).order_by('-created_at')  
    
    