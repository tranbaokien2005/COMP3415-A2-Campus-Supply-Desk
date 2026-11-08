"""Safety-net tests for the order desk, written against FUNCTIONAL_SPEC.md.

Expected values come from the specification, not from the current code.
A failing test here marks a place where the code disagrees with the spec.
"""

import json
from pathlib import Path
import tempfile
import unittest

from supplydesk.service import OrderService


def write_save_file(path, extra_products):
    """Write a schema-version-1 save file with the initial catalog plus test products.

    Some boundaries (for example a 4,999-cent subtotal) cannot be reached with the
    bundled prices, so a few tests start from a save file that adds test products.
    """
    # A service on a path with no save file returns the bundled initial catalog.
    catalog = OrderService(Path(path).with_name("initial.json")).catalog()
    catalog.extend(dict(product) for product in extra_products)
    state = {"schema_version": 1, "next_order_number": 1, "catalog": catalog, "orders": []}
    Path(path).write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def make_product(product_id, unit_price_cents, stock=10):
    return {
        "product_id": product_id,
        "name": "Test product " + product_id,
        "unit_price_cents": unit_price_cents,
        "stock": stock,
    }


class SafetyNetTestCase(unittest.TestCase):
    """Shared setup: every test gets its own temporary save file."""

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "state.json"
        self.service = OrderService(self.path)

    def stock_of(self, product_id, service=None):
        for product in (service or self.service).catalog():
            if product["product_id"] == product_id:
                return product["stock"]
        raise AssertionError("Product not in catalog: " + product_id)

    def stock_levels(self):
        return {product["product_id"]: product["stock"] for product in self.service.catalog()}

    def save_file_bytes(self):
        return self.path.read_bytes()

    def assert_pricing(self, result, subtotal, discount, delivery, total):
        self.assertEqual(result["subtotal_cents"], subtotal)
        self.assertEqual(result["discount_cents"], discount)
        self.assertEqual(result["delivery_cents"], delivery)
        self.assertEqual(result["total_cents"], total)


class PricingRulesTests(SafetyNetTestCase):
    def test_spec_example_regular_pickup_two_notebooks(self):
        """Spec example: regular pickup of two notebooks totals 1,000 cents."""
        quote = self.service.quote("regular", [{"product_id": "notebook", "quantity": 2}], "pickup")
        self.assert_pricing(quote, subtotal=1000, discount=0, delivery=0, total=1000)

    def test_spec_example_student_delivery_two_hoodies(self):
        """Spec example: student delivery of two hoodies gets 800 off plus 600 delivery."""
        quote = self.service.quote("student", [{"product_id": "hoodie", "quantity": 2}], "delivery")
        self.assert_pricing(quote, subtotal=8000, discount=800, delivery=600, total=7800)

    def test_spec_example_regular_delivery_three_hoodies(self):
        """Spec example: regular delivery of three hoodies is 12,000 with free delivery."""
        quote = self.service.quote("regular", [{"product_id": "hoodie", "quantity": 3}], "delivery")
        self.assert_pricing(quote, subtotal=12000, discount=0, delivery=0, total=12000)

    def test_student_subtotal_4999_gets_no_discount(self):
        """A student subtotal of 4,999 cents is below the 5,000 threshold: no discount."""
        write_save_file(self.path, [make_product("price-4999", 4999)])
        quote = self.service.quote("student", [{"product_id": "price-4999", "quantity": 1}])
        self.assert_pricing(quote, subtotal=4999, discount=0, delivery=0, total=4999)

    def test_student_subtotal_exactly_5000_gets_discount(self):
        """A student subtotal of exactly 5,000 cents ("at least 5,000") gets 10% off."""
        quote = self.service.quote("student", [{"product_id": "bag", "quantity": 2}])
        self.assert_pricing(quote, subtotal=5000, discount=500, delivery=0, total=4500)

    def test_student_subtotal_5001_gets_discount_rounded(self):
        """A student subtotal of 5,001 cents gets 10% off, 500.1 rounded to 500."""
        write_save_file(self.path, [make_product("price-5001", 5001)])
        quote = self.service.quote("student", [{"product_id": "price-5001", "quantity": 1}])
        self.assert_pricing(quote, subtotal=5001, discount=500, delivery=0, total=4501)

    def test_student_delivery_free_at_exactly_10000_after_discount(self):
        """Student delivery is free when subtotal minus discount is exactly 10,000 cents."""
        write_save_file(self.path, [make_product("price-11111", 11111)])
        quote = self.service.quote(
            "student", [{"product_id": "price-11111", "quantity": 1}], "delivery"
        )
        self.assert_pricing(quote, subtotal=11111, discount=1111, delivery=0, total=10000)

    def test_regular_delivery_free_at_exactly_10000(self):
        """Regular delivery is free when the (undiscounted) total is exactly 10,000 cents."""
        quote = self.service.quote(
            "regular",
            [{"product_id": "hoodie", "quantity": 2}, {"product_id": "notebook", "quantity": 4}],
            "delivery",
        )
        self.assert_pricing(quote, subtotal=10000, discount=0, delivery=0, total=10000)

    def test_delivery_charged_when_discount_drops_below_10000(self):
        """Delivery uses the discounted amount: subtotal 11,110 minus 1,111 is 9,999, so 600 applies."""
        write_save_file(self.path, [make_product("price-11110", 11110)])
        quote = self.service.quote(
            "student", [{"product_id": "price-11110", "quantity": 1}], "delivery"
        )
        self.assert_pricing(quote, subtotal=11110, discount=1111, delivery=600, total=10599)

    def test_regular_customer_never_gets_discount(self):
        """Regular customers get no discount even when the subtotal is well above 5,000."""
        quote = self.service.quote(
            "regular",
            [{"product_id": "bag", "quantity": 2}, {"product_id": "hoodie", "quantity": 1}],
        )
        self.assert_pricing(quote, subtotal=9000, discount=0, delivery=0, total=9000)
        order = self.service.place_order("regular", [{"product_id": "bag", "quantity": 2}])
        self.assert_pricing(order, subtotal=5000, discount=0, delivery=0, total=5000)


class ValidationTests(SafetyNetTestCase):
    def setUp(self):
        super().setUp()
        # One earlier successful order, so there is saved data that must survive rejections.
        self.service.place_order("regular", [{"product_id": "notebook", "quantity": 1}])
        self.file_before = self.save_file_bytes()
        self.stock_before = self.stock_levels()

    def assert_rejected_without_side_effects(self, customer_type, items, fulfillment="pickup"):
        for operation in (self.service.quote, self.service.place_order):
            with self.subTest(operation=operation.__name__):
                with self.assertRaises(ValueError):
                    operation(customer_type, items, fulfillment)
                self.assertEqual(self.save_file_bytes(), self.file_before)
                self.assertEqual(self.stock_levels(), self.stock_before)
        # The next order number was not consumed by the rejected requests.
        order = self.service.place_order("regular", [{"product_id": "mug", "quantity": 1}])
        self.assertEqual(order["order_id"], "ORD-0002")

    def test_invalid_customer_type_rejected(self):
        """A customer type other than regular/student raises ValueError and changes nothing."""
        self.assert_rejected_without_side_effects("staff", [{"product_id": "notebook", "quantity": 1}])

    def test_invalid_fulfillment_rejected(self):
        """A fulfillment other than pickup/delivery raises ValueError and changes nothing."""
        self.assert_rejected_without_side_effects(
            "regular", [{"product_id": "notebook", "quantity": 1}], "courier"
        )

    def test_empty_items_rejected(self):
        """An empty item list raises ValueError and changes nothing."""
        self.assert_rejected_without_side_effects("regular", [])

    def test_unknown_product_rejected(self):
        """An unknown product ID raises ValueError and changes nothing."""
        self.assert_rejected_without_side_effects("regular", [{"product_id": "laptop", "quantity": 1}])

    def test_quantity_zero_rejected(self):
        """Quantity 0 is below the 1-99 range: ValueError and nothing changes."""
        self.assert_rejected_without_side_effects("regular", [{"product_id": "notebook", "quantity": 0}])

    def test_quantity_100_rejected(self):
        """Quantity 100 is above the 1-99 range: ValueError and nothing changes."""
        self.assert_rejected_without_side_effects("regular", [{"product_id": "notebook", "quantity": 100}])

    def test_quantity_numeric_string_rejected(self):
        """The string "2" is not a valid service quantity: ValueError and nothing changes."""
        self.assert_rejected_without_side_effects("regular", [{"product_id": "notebook", "quantity": "2"}])

    def test_quantity_float_rejected(self):
        """The float 2.0 is not a valid service quantity: ValueError and nothing changes."""
        self.assert_rejected_without_side_effects("regular", [{"product_id": "notebook", "quantity": 2.0}])

    def test_quantity_boolean_rejected(self):
        """The boolean True is not a valid service quantity: ValueError and nothing changes."""
        self.assert_rejected_without_side_effects("regular", [{"product_id": "notebook", "quantity": True}])


class StockHistoryCancellationTests(SafetyNetTestCase):
    def test_duplicate_lines_exceeding_stock_rejected(self):
        """Two lines of one product whose combined quantity exceeds stock raise ValueError."""
        self.service.place_order("regular", [{"product_id": "notebook", "quantity": 1}])
        file_before = self.save_file_bytes()
        items = [{"product_id": "bag", "quantity": 3}, {"product_id": "bag", "quantity": 2}]
        for operation in (self.service.quote, self.service.place_order):
            with self.subTest(operation=operation.__name__):
                with self.assertRaises(ValueError):
                    operation("regular", items)
                self.assertEqual(self.save_file_bytes(), file_before)
                self.assertEqual(self.stock_of("bag"), 4)

    def test_stock_never_goes_negative(self):
        """No sequence of placements, including split duplicate lines, drives stock below zero."""
        attempts = [
            [{"product_id": "bag", "quantity": 4}],
            [{"product_id": "bag", "quantity": 1}],
            [{"product_id": "mug", "quantity": 5}, {"product_id": "mug", "quantity": 4}],
            [{"product_id": "hoodie", "quantity": 3}, {"product_id": "hoodie", "quantity": 3}],
        ]
        for items in attempts:
            try:
                self.service.place_order("regular", items)
            except ValueError:
                pass
        for product_id, stock in self.stock_levels().items():
            self.assertGreaterEqual(stock, 0, product_id + " stock went negative")
        self.assertEqual(self.stock_of("bag"), 0)

    def test_order_ids_increase_and_are_never_reused(self):
        """Order IDs start at ORD-0001, increase by one, and a cancelled ID is not reused."""
        first = self.service.place_order("regular", [{"product_id": "notebook", "quantity": 1}])
        second = self.service.place_order("regular", [{"product_id": "notebook", "quantity": 1}])
        self.service.cancel_order(second["order_id"])
        third = self.service.place_order("regular", [{"product_id": "notebook", "quantity": 1}])
        self.assertEqual(
            [first["order_id"], second["order_id"], third["order_id"]],
            ["ORD-0001", "ORD-0002", "ORD-0003"],
        )
        ids = [order["order_id"] for order in self.service.list_orders()]
        self.assertEqual(ids, ["ORD-0001", "ORD-0002", "ORD-0003"])

    def test_history_keeps_cancelled_orders(self):
        """list_orders keeps cancelled orders in placement order with original items and totals."""
        first = self.service.place_order("student", [{"product_id": "hoodie", "quantity": 2}], "delivery")
        second = self.service.place_order("regular", [{"product_id": "mug", "quantity": 1}])
        self.service.cancel_order(first["order_id"])
        history = self.service.list_orders()
        self.assertEqual([order["order_id"] for order in history], ["ORD-0001", "ORD-0002"])
        self.assertEqual(history[0]["status"], "cancelled")
        self.assertEqual(history[0]["items"], first["items"])
        self.assert_pricing(history[0], subtotal=8000, discount=800, delivery=600, total=7800)
        self.assertEqual(history[1], second)

    def test_cancelling_twice_does_not_restore_stock_again(self):
        """A second cancel returns the cancelled order without changing stock or history."""
        order = self.service.place_order("regular", [{"product_id": "pen-pack", "quantity": 3}])
        first_cancel = self.service.cancel_order(order["order_id"])
        self.assertEqual(self.stock_of("pen-pack"), 10)
        history_after_first = self.service.list_orders()
        second_cancel = self.service.cancel_order(order["order_id"])
        self.assertEqual(second_cancel, first_cancel)
        self.assertEqual(second_cancel["status"], "cancelled")
        self.assertEqual(self.stock_of("pen-pack"), 10)
        self.assertEqual(self.service.list_orders(), history_after_first)

    def test_unknown_order_id_raises_value_error(self):
        """get_order and cancel_order with an unknown ID raise ValueError and change nothing."""
        self.service.place_order("regular", [{"product_id": "notebook", "quantity": 1}])
        file_before = self.save_file_bytes()
        with self.assertRaises(ValueError):
            self.service.get_order("ORD-9999")
        with self.assertRaises(ValueError):
            self.service.cancel_order("ORD-9999")
        self.assertEqual(self.save_file_bytes(), file_before)

    def test_data_survives_reopening(self):
        """A new service on the same save file sees the same history, stock and next order ID."""
        self.service.place_order("regular", [{"product_id": "notebook", "quantity": 3}])
        second = self.service.place_order("student", [{"product_id": "bag", "quantity": 2}])
        self.service.cancel_order(second["order_id"])
        history = self.service.list_orders()
        stock = self.stock_levels()

        reopened = OrderService(self.path)
        self.assertEqual(reopened.list_orders(), history)
        self.assertEqual(
            {product["product_id"]: product["stock"] for product in reopened.catalog()}, stock
        )
        self.assertEqual(self.stock_of("notebook", reopened), 17)
        third = reopened.place_order("regular", [{"product_id": "mug", "quantity": 1}])
        self.assertEqual(third["order_id"], "ORD-0003")

    def test_malformed_save_file_raises_instead_of_resetting(self):
        """A malformed save file makes operations raise an error and is left untouched."""
        self.path.write_text('{"orders": [ this is not json', encoding="utf-8")
        file_before = self.save_file_bytes()
        operations = {
            "catalog": lambda: self.service.catalog(),
            "list_orders": lambda: self.service.list_orders(),
            "quote": lambda: self.service.quote("regular", [{"product_id": "notebook", "quantity": 1}]),
            "place_order": lambda: self.service.place_order(
                "regular", [{"product_id": "notebook", "quantity": 1}]
            ),
        }
        for name, operation in operations.items():
            with self.subTest(operation=name):
                with self.assertRaises(Exception):
                    operation()
                self.assertEqual(self.save_file_bytes(), file_before)

    def test_past_orders_keep_recorded_prices(self):
        """After a catalog price change, existing orders still show the prices recorded at placement."""
        order = self.service.place_order("regular", [{"product_id": "notebook", "quantity": 2}])
        # Simulate a catalog price change (no interface edits the catalog).
        state = json.loads(self.path.read_text(encoding="utf-8"))
        for product in state["catalog"]:
            if product["product_id"] == "notebook":
                product["unit_price_cents"] = 900
        self.path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")

        reopened = OrderService(self.path)
        new_quote = reopened.quote("regular", [{"product_id": "notebook", "quantity": 2}])
        self.assertEqual(new_quote["subtotal_cents"], 1800)  # the price change took effect
        stored = reopened.get_order(order["order_id"])
        self.assertEqual(stored["items"][0]["unit_price_cents"], 500)
        self.assertEqual(stored["items"][0]["line_total_cents"], 1000)
        self.assert_pricing(stored, subtotal=1000, discount=0, delivery=0, total=1000)
        self.assertEqual(reopened.list_orders()[0], order)


class RefactoringGuardTests(SafetyNetTestCase):
    REQUESTS = [
        ("regular", [{"product_id": "notebook", "quantity": 2}], "pickup"),
        ("student", [{"product_id": "hoodie", "quantity": 2}], "delivery"),
        (
            "student",
            [
                {"product_id": "mug", "quantity": 2},
                {"product_id": "pen-pack", "quantity": 3},
                {"product_id": "mug", "quantity": 1},
            ],
            "delivery",
        ),
    ]
    PRICE_FIELDS = (
        "customer_type",
        "fulfillment",
        "items",
        "subtotal_cents",
        "discount_cents",
        "delivery_cents",
        "total_cents",
    )

    def test_quote_and_place_order_agree(self):
        """For the same request and stock, quote() and place_order() return the same items and prices."""
        for customer_type, items, fulfillment in self.REQUESTS:
            with self.subTest(customer_type=customer_type, items=items, fulfillment=fulfillment):
                quote = self.service.quote(customer_type, items, fulfillment)
                order = self.service.place_order(customer_type, items, fulfillment)
                for field in self.PRICE_FIELDS:
                    self.assertEqual(order[field], quote[field], field)

    def test_place_order_returns_full_order_deducts_stock_and_saves(self):
        """place_order returns every order field, deducts stock and persists both to the save file."""
        order = self.service.place_order(
            "student",
            [{"product_id": "hoodie", "quantity": 1}, {"product_id": "mug", "quantity": 2}],
            "delivery",
        )
        self.assertEqual(
            order,
            {
                "order_id": "ORD-0001",
                "status": "placed",
                "customer_type": "student",
                "fulfillment": "delivery",
                "items": [
                    {
                        "product_id": "hoodie",
                        "name": "Campus hoodie",
                        "unit_price_cents": 4000,
                        "quantity": 1,
                        "line_total_cents": 4000,
                    },
                    {
                        "product_id": "mug",
                        "name": "Campus mug",
                        "unit_price_cents": 1500,
                        "quantity": 2,
                        "line_total_cents": 3000,
                    },
                ],
                "subtotal_cents": 7000,
                "discount_cents": 700,
                "delivery_cents": 600,
                "total_cents": 6900,
            },
        )
        self.assertTrue(self.path.exists())
        reopened = OrderService(self.path)
        self.assertEqual(self.stock_of("hoodie", reopened), 4)
        self.assertEqual(self.stock_of("mug", reopened), 6)
        self.assertEqual(self.stock_of("notebook", reopened), 20)
        self.assertEqual(reopened.get_order("ORD-0001"), order)

    def test_quote_creates_no_save_file_and_uses_no_order_id(self):
        """quote() never creates or changes a save file, reserves stock, or consumes an order ID."""
        items = [{"product_id": "bag", "quantity": 4}]
        self.service.quote("regular", items)
        self.assertFalse(self.path.exists())
        self.assertEqual(self.stock_of("bag"), 4)

        first = self.service.place_order("regular", [{"product_id": "notebook", "quantity": 1}])
        self.assertEqual(first["order_id"], "ORD-0001")
        file_before = self.save_file_bytes()
        self.service.quote("student", items, "delivery")
        self.assertEqual(self.save_file_bytes(), file_before)
        self.assertEqual(self.service.list_orders(), [first])

        second = self.service.place_order("regular", items)
        self.assertEqual(second["order_id"], "ORD-0002")


if __name__ == "__main__":
    unittest.main()
