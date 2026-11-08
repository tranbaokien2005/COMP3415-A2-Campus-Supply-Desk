"""Operations used by the command-line order desk."""

from supplydesk.storage import JsonStore

# Request values accepted by quote() and place_order().
REGULAR = "regular"
STUDENT = "student"
CUSTOMER_TYPES = (REGULAR, STUDENT)

PICKUP = "pickup"
DELIVERY = "delivery"
EXPRESS = "express"
FULFILLMENT_OPTIONS = (PICKUP, DELIVERY, EXPRESS)

MIN_QUANTITY = 1
MAX_QUANTITY = 99

# Pricing rules. All money values are integer Canadian cents.
STUDENT_DISCOUNT_THRESHOLD_CENTS = 5000
STUDENT_DISCOUNT_PERCENT = 10
FREE_DELIVERY_THRESHOLD_CENTS = 10000
DELIVERY_FEE_CENTS = 600
EXPRESS_FEE_CENTS = 1200  # CR-01: flat fee, never waived

# Order records.
ORDER_ID_PREFIX = "ORD-"
ORDER_NUMBER_DIGITS = 4
STATUS_PLACED = "placed"
STATUS_CANCELLED = "cancelled"


def percent_of_cents(amount_cents, percent):
    """Return percent of amount_cents, rounded to the nearest cent with half a cent rounded up.

    Uses only integer arithmetic (no floats), as the spec requires for money.
    """
    return (amount_cents * percent + 50) // 100


def delivery_charge_cents(fulfillment, discounted_subtotal_cents):
    """Return the delivery charge for a fulfillment option.

    Pickup is free. Standard delivery is free from the free-delivery threshold.
    Express (CR-01) always costs the express fee, whatever the order value.
    """
    if fulfillment == EXPRESS:
        return EXPRESS_FEE_CENTS
    if fulfillment == DELIVERY and discounted_subtotal_cents < FREE_DELIVERY_THRESHOLD_CENTS:
        return DELIVERY_FEE_CENTS
    return 0


class OrderService:
    def __init__(self, state_path=".supplydesk/state.json"):
        self.store = JsonStore(state_path)

    def catalog(self):
        return self.store.load()["catalog"]

    def quote(self, customer_type, items, fulfillment=PICKUP):
        state = self.store.load()
        return self._price_request(state, customer_type, items, fulfillment)

    def place_order(self, customer_type, items, fulfillment=PICKUP):
        state = self.store.load()
        priced = self._price_request(state, customer_type, items, fulfillment)
        order = self._build_order_record(state, priced)
        self._deduct_stock(state, order["items"])
        self._save_new_order(state, order)
        return order

    def _build_order_record(self, state, priced):
        """Turn a priced request into an order with the next ID and status placed."""
        return {
            "order_id": ORDER_ID_PREFIX + str(state["next_order_number"]).zfill(ORDER_NUMBER_DIGITS),
            "status": STATUS_PLACED,
            **priced,
        }

    def _deduct_stock(self, state, lines):
        """Remove every ordered unit from the catalog stock in state."""
        for line in lines:
            for product in state["catalog"]:
                if product["product_id"] == line["product_id"]:
                    product["stock"] -= line["quantity"]

    def _save_new_order(self, state, order):
        """Append the order, advance the order number and write the save file."""
        state["next_order_number"] += 1
        state["orders"].append(order)
        self.store.save(state)

    def _price_request(self, state, customer_type, items, fulfillment):
        """Validate a request against the current state and price it.

        Shared by quote() and place_order() so both always apply the same rules.
        Returns the quote fields; it never changes state.
        """
        if customer_type not in CUSTOMER_TYPES:
            raise ValueError("Customer type must be regular or student.")
        if fulfillment not in FULFILLMENT_OPTIONS:
            raise ValueError("Fulfillment must be pickup, delivery or express.")
        if not isinstance(items, list) or not items:
            raise ValueError("An order must contain at least one item.")
        lines = []
        subtotal = 0
        requested = {}  # product_id -> total quantity across all lines
        for item in items:
            if not isinstance(item, dict):
                raise ValueError("Each item must contain a product_id and quantity.")
            product = None
            for candidate in state["catalog"]:
                if candidate["product_id"] == item.get("product_id"):
                    product = candidate
                    break
            if product is None:
                raise ValueError("Unknown product.")
            quantity = item.get("quantity")
            if type(quantity) is not int or not MIN_QUANTITY <= quantity <= MAX_QUANTITY:
                raise ValueError(
                    f"Quantity must be an integer from {MIN_QUANTITY} to {MAX_QUANTITY}."
                )
            product_id = product["product_id"]
            requested[product_id] = requested.get(product_id, 0) + quantity
            if requested[product_id] > product["stock"]:
                raise ValueError("Not enough stock for " + product["product_id"] + ".")
            line_total = product["unit_price_cents"] * quantity
            subtotal += line_total
            lines.append({
                "product_id": product["product_id"],
                "name": product["name"],
                "unit_price_cents": product["unit_price_cents"],
                "quantity": quantity,
                "line_total_cents": line_total,
            })
        discount = 0
        if customer_type == STUDENT and subtotal >= STUDENT_DISCOUNT_THRESHOLD_CENTS:
            discount = percent_of_cents(subtotal, STUDENT_DISCOUNT_PERCENT)
        # The discount is applied to merchandise only; the delivery charge is never discounted.
        delivery = delivery_charge_cents(fulfillment, subtotal - discount)
        return {
            "customer_type": customer_type,
            "fulfillment": fulfillment,
            "items": lines,
            "subtotal_cents": subtotal,
            "discount_cents": discount,
            "delivery_cents": delivery,
            "total_cents": subtotal - discount + delivery,
        }

    def list_orders(self):
        return self.store.load()["orders"]

    def get_order(self, order_id):
        state = self.store.load()
        for order in state["orders"]:
            if order["order_id"] == order_id:
                return order
        raise ValueError("Unknown order: " + order_id)

    def cancel_order(self, order_id):
        state = self.store.load()
        order = None
        for candidate in state["orders"]:
            if candidate["order_id"] == order_id:
                order = candidate
                break
        if order is None:
            raise ValueError("Unknown order: " + order_id)
        if order["status"] == STATUS_CANCELLED:
            return order
        for line in order["items"]:
            for product in state["catalog"]:
                if product["product_id"] == line["product_id"]:
                    product["stock"] += line["quantity"]
        order["status"] = STATUS_CANCELLED
        self.store.save(state)
        return order
