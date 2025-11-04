import json
from decimal import Decimal

from .forms import ModalPaymentForm
from .forms import PaymentForm
from .. import PaymentError
from .. import PaymentStatus
from .. import RedirectNeeded
from ..core import BasicProvider


class Methods:
    CREATE_CARD = 'cards.create'
    GET_VERIFY_CODE = 'cards.get_verify_code'
    CARD_VERIFY = 'cards.verify'

    CARD_CHECK = 'cards.check'
    CARD_REMOVE = 'cards.remove'

    CREATE_RECEIPT = 'receipts.create'
    PAY_RECEIPT = 'receipts.pay'
    CHECK_RECEIPT = 'receipts.check'
    CANCEL_RECEIPT = 'receipts.cancel'

    client_methods = [CREATE_CARD, GET_VERIFY_CODE, CARD_VERIFY]


class PaymeProvider(BasicProvider):
    """Provider backend using `payme <https://payme.uz>`_.

    This backend does not support fraud detection.

    :param merchant_id: Merchant ID assigned by Payme.
    :param secret_key: Secret key assigned by Payme.
    :param image: Your logo.
    """

    form_class = ModalPaymentForm

    def __init__(self, api_url, merchant_id, secret_key, image="", **kwargs):
        self.api_url = api_url
        self.merchant_id = merchant_id
        self.secret_key = secret_key
        self.image = image
        super().__init__(**kwargs)

    def get_form(self, payment, data=None):
        if payment.status == PaymentStatus.WAITING:
            payment.change_status(PaymentStatus.INPUT)
        form = self.form_class(data=data, payment=payment, provider=self)

        if form.is_valid():
            form.save()
            raise RedirectNeeded(payment.get_success_url())
        return form

    def capture(self, payment, amount=None):
        amount = int((amount or payment.total) * 100)
        charge = stripe.Charge.retrieve(payment.transaction_id)
        try:
            charge.capture(amount=amount)
        except stripe.InvalidRequestError:
            payment.change_status(PaymentStatus.REFUNDED)
            raise PaymentError("Payment already refunded")
        payment.attrs.capture = json.dumps(charge)
        return Decimal(amount) / 100

    def release(self, payment):
        charge = stripe.Charge.retrieve(payment.transaction_id)
        charge.refund()
        payment.attrs.release = json.dumps(charge)

    def refund(self, payment, amount=None):
        amount = int((amount or payment.total) * 100)
        charge = stripe.Charge.retrieve(payment.transaction_id)
        charge.refund(amount=amount)
        payment.attrs.refund = json.dumps(charge)
        return Decimal(amount) / 100


class StripeCardProvider(StripeProvider):
    """Provider backend using `Stripe <https://stripe.com/>`_, form-based.

    This backend implements payments using `Stripe <https://stripe.com/>`_ but
    the credit card data is collected by your site.

    Parameters are the same as  :class:`~StripeProvider`.
    """

    form_class = PaymentForm
