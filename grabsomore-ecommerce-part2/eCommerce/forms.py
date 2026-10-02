"""Model forms ensure vendors can edit only allowed product fields."""

from django import forms

from .models import Product, Store, Review


class StoreForm(forms.ModelForm):
    """Edit store details while assigning ownership on the server."""

    class Meta:
        """Specify the editable model fields."""
        model = Store
        fields = ('name', 'description')


class ProductForm(forms.ModelForm):
    """Restrict product changes to stores owned by the current vendor."""

    class Meta:
        """Specify the editable model fields."""
        model = Product
        fields = ('store', 'name', 'description', 'price', 'stock')

    def __init__(self, *args, owner, **kwargs):
        """Limit the product form store choices to the current vendor’s stores."""
        super().__init__(*args, **kwargs)
        self.fields['store'].queryset = Store.objects.filter(owner=owner)

    def clean_price(self):
        """Reject a negative price before saving the product."""
        price = self.cleaned_data['price']
        if price < 0:
            raise forms.ValidationError('Price must not be negative.')
        return price


class ReviewForm(forms.ModelForm):
    """Accept review text and rating; buyer and verification are server controlled."""

    class Meta:
        """Expose only the fields a buyer may supply."""
        model = Review
        fields = ('rating', 'comment')
