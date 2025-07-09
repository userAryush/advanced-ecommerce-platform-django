from django.db import models
from django.contrib.auth.models import AbstractUser
from base.models import BaseModel
import uuid    
# Create your models here.

class User(AbstractUser):
    email = models.EmailField(max_length=255, unique=True)
    full_name = models.CharField(max_length=255)
    username = models.CharField(max_length=100,unique= True)
    ROLE_CHOICES = [
        ('admin','Admin'),
        ('supplier','Supplier'),
        ('customer','Customer'),
        ('delivery','Delivery'),
    ]
    user_role = models.CharField(choices=ROLE_CHOICES,max_length=30)
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'full_name', 'user_role']
    def __str__(self):
        return f"{self.id}. {self.full_name} ({self.user_role})"


class Customer(BaseModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    phone = models.CharField(max_length=20)
    address = models.TextField()

    def __str__(self):
        return f"{self.id}. {self.user.full_name}"


class Supplier(BaseModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    phone = models.CharField(max_length=20)
    address = models.TextField()

    def __str__(self):
        return f"{self.id}. {self.user.full_name}"


class DeliveryPersonnel(BaseModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    phone = models.CharField(max_length=20)
    address = models.TextField()

    def __str__(self):
        return f"{self.id}. {self.user.full_name}"

class ProductCategory(BaseModel):
    category_name = models.CharField(max_length=255)
    category_description = models.TextField()
    def __str__(self):
        return self.category_name
    
class Product(BaseModel):
    supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL,null=True)
    product_name = models.CharField(max_length=255)
    product_description = models.TextField()
    product_price = models.DecimalField(max_digits=10, decimal_places=2)
    product_image = models.ImageField(upload_to='products/')
    stock_quantity = models.IntegerField()
    category = models.ForeignKey(ProductCategory, on_delete=models.SET_NULL,null=True)

    def __str__(self):
        return f"{self.id}. {self.product_name} - {self.category.category_name} from {self.supplier.user.username}"

class Order(BaseModel):
    STATUS_CHOICES = [
        ('cart', 'cart'),
        ('ordered', 'ordered'),
        ('shipped', 'Shipped'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
    ]

    PAYMENT_CHOICES = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('failed', 'Failed'),
    ]

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    order_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(choices=STATUS_CHOICES, max_length=20)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_status = models.CharField(choices=PAYMENT_CHOICES, max_length=20)

    def __str__(self):
        return f"Order #{self.id} by {self.customer.user.full_name} status={self.status}, payment={self.payment_status} {self.order_date}"

class OrderItem(BaseModel):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)  # kept to record the price for later when the price of the same product might change . This i will extract from product

    def __str__(self):
        return f"{self.product.product_name} x {self.quantity}"


class Delivery(BaseModel):
    DELIVERY_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('assigned', 'Assigned'),
        ('in_transit', 'In Transit'),
        ('delivered', 'Delivered'),
    ]

    order = models.OneToOneField(Order, on_delete=models.CASCADE)
    delivery_personnel = models.ForeignKey(DeliveryPersonnel, on_delete=models.SET_NULL, null=True)
    delivery_status = models.CharField(choices=DELIVERY_STATUS_CHOICES, max_length=20)
    assigned_date = models.DateTimeField(auto_now_add=True)
    delivered_date = models.DateTimeField(null=True, blank=True)
    delivery_address = models.TextField(default="Kathmandu")

    def __str__(self):
        return f"Delivery for Order #{self.order.id}, status: {self.delivery_status}. Personnel: {self.delivery_personnel.user.username} Address: {self.delivery_address}"


class Notification(BaseModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Notification for {self.user.email} - {self.created_at}"


class Payment(BaseModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.OneToOneField(Order, on_delete=models.CASCADE)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    payment_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=[
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ], default='pending')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_gateway = models.CharField(max_length=50, blank=True, null=True)
    transaction_id = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return f"Payment for Order #{self.order.id} - {self.status}"