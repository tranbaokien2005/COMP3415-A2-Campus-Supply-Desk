"""Command-line interface. Prices in JSON output are integer cents."""

import argparse
import json
from pathlib import Path
import sys

from supplydesk.service import CUSTOMER_TYPES, FULFILLMENT_OPTIONS, OrderService


def parse_item(value):
    product_id, separator, raw_quantity = value.partition(":")
    if not separator or not product_id:
        raise argparse.ArgumentTypeError("Use PRODUCT_ID:QUANTITY, for example notebook:2.")
    try:
        quantity = int(raw_quantity)
    except ValueError as error:
        raise argparse.ArgumentTypeError("Item quantity must be an integer.") from error
    return {"product_id": product_id, "quantity": quantity}


def build_parser():
    parser = argparse.ArgumentParser(description="Campus Supply Desk")
    parser.add_argument(
        "--data", type=Path, default=Path(".supplydesk/state.json"),
        help="state file path (default: .supplydesk/state.json)",
    )
    commands = parser.add_subparsers(dest="command")
    commands.add_parser("catalog", help="show products and available stock")
    for name in ("quote", "place"):
        command = commands.add_parser(name)
        command.add_argument(
            "--customer", choices=CUSTOMER_TYPES, default="regular",
            help="customer type (default: regular)",
        )
        command.add_argument(
            "--fulfillment", choices=FULFILLMENT_OPTIONS, default="pickup",
            help="pickup (free), delivery ($6.00, free from $100.00 after discount) "
                 "or express ($12.00 flat, never waived) (default: pickup)",
        )
        command.add_argument("--item", type=parse_item, action="append", required=True)
    commands.add_parser("orders", help="list orders in placement order")
    show = commands.add_parser("show", help="show one order")
    show.add_argument("order_id")
    cancel = commands.add_parser("cancel", help="cancel an order")
    cancel.add_argument("order_id")
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    service = OrderService(args.data)
    if args.command is None:
        from supplydesk.menu import run_menu
        return run_menu(service)
    try:
        if args.command == "catalog":
            result = service.catalog()
        elif args.command == "quote":
            result = service.quote(args.customer, args.item, args.fulfillment)
        elif args.command == "place":
            result = service.place_order(args.customer, args.item, args.fulfillment)
        elif args.command == "orders":
            result = service.list_orders()
        elif args.command == "show":
            result = service.get_order(args.order_id)
        else:
            result = service.cancel_order(args.order_id)
    except (ValueError, OSError, KeyError, TypeError) as error:
        print("Error: " + str(error), file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0
