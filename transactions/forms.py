from decimal import Decimal
from django import forms
from wallet.models import Wallet


class TransactionForm(forms.Form):
    receiver_address = forms.CharField(
        label="Receiver Wallet Address",
        max_length=66,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter 66-character receiver wallet address (starts with MC)'
        })
    )
    amount = forms.DecimalField(
        label="Amount (MYC)",
        max_digits=20,
        decimal_places=8,
        min_value=Decimal('0.00000001'),
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': '0.00000000',
            'step': '0.00000001'
        })
    )

    def __init__(self, *args, sender_wallet=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.sender_wallet = sender_wallet

    def clean_receiver_address(self):
        address = self.cleaned_data.get('receiver_address', '').strip()
        try:
            receiver_wallet = Wallet.objects.get(address=address)
        except Wallet.DoesNotExist:
            raise forms.ValidationError("Receiver wallet address does not exist.")

        if self.sender_wallet and receiver_wallet == self.sender_wallet:
            raise forms.ValidationError("Sender and receiver wallets must be different.")

        self.receiver_wallet = receiver_wallet
        return address

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount is None or amount <= Decimal('0'):
            raise forms.ValidationError("Amount must be greater than zero.")

        if self.sender_wallet and self.sender_wallet.balance < amount:
            raise forms.ValidationError(
                f"Insufficient balance. Your current balance is {self.sender_wallet.balance} MYC."
            )

        return amount
