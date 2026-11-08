"""CR-01 Express Delivery tests.

Rules: express costs 1,200 cents and is never waived; the student discount
applies to merchandise only; pickup and standard delivery are unchanged;
any other fulfillment value is still invalid.
"""

import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from supplydesk import cli, menu
from supplydesk.service import OrderService


class ExpressTestCase(unittest.TestCase):
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

    def assert_pricing(self, result, subtotal, discount, delivery, total):
        self.assertEqual(result["subtotal_cents"], subtotal)
        self.assertEqual(result["discount_cents"], discount)
        self.assertEqual(result["delivery_cents"], delivery)
        self.assertEqual(result["total_cents"], total)


class ExpressPricingTests(ExpressTestCase):
    def test_cr01_example_regular_two_notebooks(self):
        """CR-01 example: regular express, two notebooks, totals 2,200 cents."""
        quote = self.service.quote("regular", [{"product_id": "notebook", "quantity": 2}], "express")
        self.assert_pricing(quote, subtotal=1000, discount=0, delivery=1200, total=2200)

    def test_cr01_example_student_two_hoodies(self):
        """CR-01 example: student express, two hoodies: discount on merchandise only, total 8,400."""
        quote = self.service.quote("student", [{"product_id": "hoodie", "quantity": 2}], "express")
        self.assert_pricing(quote, subtotal=8000, discount=800, delivery=1200, total=8400)

    def test_cr01_example_regular_three_hoodies(self):
        """CR-01 example: regular express, three hoodies: express not waived above 10,000, total 13,200."""
        quote = self.service.quote("regular", [{"product_id": "hoodie", "quantity": 3}], "express")
        self.assert_pricing(quote, subtotal=12000, discount=0, delivery=1200, total=13200)

    def test_express_never_waived_at_or_above_10000(self):
        """Express still costs 1,200 at exactly 10,000 and when a student order is over 10,000 after discount."""
        regular = self.service.quote("regular", [{"product_id": "bag", "quantity": 4}], "express")
        self.assert_pricing(regular, subtotal=10000, discount=0, delivery=1200, total=11200)
        student = self.service.quote("student", [{"product_id": "hoodie", "quantity": 3}], "express")
        self.assert_pricing(student, subtotal=12000, discount=1200, delivery=1200, total=12000)

    def test_pickup_and_standard_delivery_unchanged(self):
        """Adding express does not change pickup (free) or standard delivery (600, free from 10,000)."""
        items = [{"product_id": "hoodie", "quantity": 2}]
        pickup = self.service.quote("student", items, "pickup")
        self.assert_pricing(pickup, subtotal=8000, discount=800, delivery=0, total=7200)
        delivery = self.service.quote("student", items, "delivery")
        self.assert_pricing(delivery, subtotal=8000, discount=800, delivery=600, total=7800)
        free = self.service.quote("regular", [{"product_id": "hoodie", "quantity": 3}], "delivery")
        self.assert_pricing(free, subtotal=12000, discount=0, delivery=0, total=12000)


class ExpressOrderTests(ExpressTestCase):
    def test_quote_equals_placed_express_order(self):
        """For the same express request, quote() and place_order() return the same items and prices."""
        items = [{"product_id": "mug", "quantity": 2}, {"product_id": "hoodie", "quantity": 1}]
        quote = self.service.quote("student", items, "express")
        order = self.service.place_order("student", items, "express")
        for field in quote:
            self.assertEqual(order[field], quote[field], field)
        self.assertEqual(order["fulfillment"], "express")
        self.assert_pricing(order, subtotal=7000, discount=700, delivery=1200, total=7500)

    def test_express_kept_after_reopen(self):
        """An express order reloads from the save file with fulfillment and charge intact."""
        order = self.service.place_order("regular", [{"product_id": "notebook", "quantity": 2}], "express")
        reopened = OrderService(self.path)
        stored = reopened.get_order(order["order_id"])
        self.assertEqual(stored, order)
        self.assertEqual(stored["fulfillment"], "express")
        self.assert_pricing(stored, subtotal=1000, discount=0, delivery=1200, total=2200)

    def test_express_kept_after_cancel(self):
        """Cancelling an express order restores stock but keeps express and its recorded prices."""
        order = self.service.place_order("student", [{"product_id": "hoodie", "quantity": 2}], "express")
        self.assertEqual(self.stock_of("hoodie"), 3)
        cancelled = self.service.cancel_order(order["order_id"])
        self.assertEqual(cancelled["status"], "cancelled")
        self.assertEqual(cancelled["fulfillment"], "express")
        self.assert_pricing(cancelled, subtotal=8000, discount=800, delivery=1200, total=8400)
        self.assertEqual(self.stock_of("hoodie"), 5)
        self.assertEqual(OrderService(self.path).list_orders(), [cancelled])

    def test_other_fulfillment_values_rejected(self):
        """Values like "overnight", "Express" or "" raise ValueError and change no saved data."""
        self.service.place_order("regular", [{"product_id": "notebook", "quantity": 1}])
        file_before = self.path.read_bytes()
        items = [{"product_id": "notebook", "quantity": 1}]
        for value in ("overnight", "Express", ""):
            for operation in (self.service.quote, self.service.place_order):
                with self.subTest(value=value, operation=operation.__name__):
                    with self.assertRaises(ValueError):
                        operation("regular", items, value)
                    self.assertEqual(self.path.read_bytes(), file_before)
        nxt = self.service.place_order("regular", items, "express")
        self.assertEqual(nxt["order_id"], "ORD-0002")


class ExpressInterfaceTests(ExpressTestCase):
    def run_cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                status = cli.main(["--data", str(self.path), *args])
            except SystemExit as exit_:
                status = exit_.code
        return status, out.getvalue(), err.getvalue()

    def test_cli_places_express_order(self):
        """The place command accepts --fulfillment express and prints the 1,200-cent charge."""
        status, out, _ = self.run_cli("place", "--fulfillment", "express", "--item", "notebook:2")
        self.assertEqual(status, 0)
        order = json.loads(out)
        self.assertEqual(order["fulfillment"], "express")
        self.assertEqual(order["delivery_cents"], 1200)
        self.assertEqual(order["total_cents"], 2200)

    def test_cli_rejects_unknown_fulfillment_and_help_lists_express(self):
        """The CLI rejects --fulfillment overnight with a nonzero exit and its help mentions express."""
        status, _, err = self.run_cli("quote", "--fulfillment", "overnight", "--item", "notebook:2")
        self.assertNotEqual(status, 0)
        self.assertIn("express", err)
        self.assertFalse(self.path.exists())
        status, out, _ = self.run_cli("quote", "--help")
        self.assertEqual(status, 0)
        self.assertIn("express", out)

    def test_menu_prompt_offers_and_accepts_express(self):
        """The menu fulfillment prompt lists express and passes it to the service."""
        answers = iter(["student", "hoodie", "2", "", "express"])
        prompts = []

        def fake_input(prompt):
            prompts.append(prompt)
            return next(answers)

        with mock.patch("builtins.input", fake_input), contextlib.redirect_stdout(io.StringIO()):
            request = menu.read_request(self.service)
        self.assertEqual(request, ("student", [{"product_id": "hoodie", "quantity": 2}], "express"))
        self.assertIn("express", prompts[-1])
        self.assert_pricing(self.service.quote(*request), subtotal=8000, discount=800,
                            delivery=1200, total=8400)


if __name__ == "__main__":
    unittest.main()
