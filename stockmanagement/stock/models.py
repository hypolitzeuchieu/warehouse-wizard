import uuid

from django.db import models

from authentication.models import User


class Category(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name


class SubCategory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100,unique=True)
    description = models.TextField(blank=True, null=True)

    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='subcategories')

    def __str__(self):
        return f'{self.category.name} - {self.name}'


class Product(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    image = models.ImageField(upload_to='products/', null=True, blank=True)
    quantity = models.PositiveIntegerField(default=0)
    min_quantity = models.PositiveIntegerField(default=10)
    expiry_date = models.DateTimeField(blank=True, null=True)
    is_expired = models.BooleanField(default=False)

    on_promotion = models.BooleanField(default=False)
    promotion_start_date = models.DateTimeField(blank=True, null=True)
    promotion_end_date = models.DateTimeField(blank=True, null=True)
    promo_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='products')
    subcategory = models.ForeignKey(
        SubCategory, on_delete=models.SET_NULL, null=True, blank=True,related_name='products'
    )

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.category.name})"

    def get_price(self):
        if self.on_promotion and self.promo_price is not None:
            return self.promo_price
        return self.unit_price


class Stock(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='stocks')
    subcategory = models.ForeignKey(
        SubCategory, on_delete=models.CASCADE, related_name='stocks', null=True, blank=True
    )
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='stocks')

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.quantity} units in {self.category.name}"


class StockMovement(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    MOVEMENT_TYPES = [
        ('ENTRY', 'Entry'),
        ('EXIT', 'Exit'),
        ('ADJUSTMENT', 'Adjustment'),
    ]
    movement_type = models.CharField(max_length=20, choices=MOVEMENT_TYPES)
    quantity = models.IntegerField()
    reason = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now=True)
    updated_at = models.DateTimeField(auto_now_add=True)

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    subcategory = models.ForeignKey(SubCategory, on_delete=models.CASCADE, null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.movement_type} - {self.product.name} ({self.quantity})"

    def save(self, *args, **kwargs):
        self.category = self.product.category
        self.subcategory = self.product.subcategory
        super().save(*args, **kwargs)
