"""Interactive terminal adapter; business rules remain in OrderService."""


def money(cents):
    return f"${cents // 100}.{cents % 100:02d}"


def show_catalog(products):
    print("\nProduct ID       Name                     Price     Stock")
    for product in products:
        print(f"{product['product_id']:<16} {product['name']:<24} "
              f"{money(product['unit_price_cents']):>8} {product['stock']:>8}")


def show_order(order):
    print("\n" + order.get("order_id", "Quote") + " - " + order.get("status", "not placed"))
    print(f"Customer: {order['customer_type']} | Fulfillment: {order['fulfillment']}")
    for line in order['items']:
        print(f"  {line['name']} x {line['quantity']}: {money(line['line_total_cents'])}")
    for label, key in (("Subtotal", "subtotal_cents"), ("Discount", "discount_cents"),
                       ("Delivery", "delivery_cents"), ("Total", "total_cents")):
        print(f"{label}: {money(order[key])}")


def read_request(service):
    show_catalog(service.catalog())
    print("Enter product IDs from the table. Blank product ID finishes the item list.")
    customer = input("Customer type [regular/student] (Enter = regular): ").strip() or "regular"
    items = []
    while True:
        product_id = input("Product ID (Enter = finish): ").strip()
        if not product_id:
            break
        raw = input("Quantity: ").strip()
        try:
            quantity = int(raw)
        except ValueError:
            print("Please enter a whole number. Re-enter this item.")
            continue
        items.append({"product_id": product_id, "quantity": quantity})
    fulfillment = input(
        "Fulfillment [pickup/delivery/express] (Enter = pickup): "
    ).strip() or "pickup"
    return customer, items, fulfillment


def run_menu(service):
    print("Campus Supply Desk | All prices are CAD. Orders are saved automatically.")
    while True:
        try:
            print("\n1. View products and stock\n2. Get a quote\n3. Place an order"
                  "\n4. View order history\n5. Find an order\n6. Cancel an order\n0. Exit")
            choice = input("Choose an option: ").strip()
            if choice == "0":
                print("Goodbye.")
                return 0
            if choice == "1":
                show_catalog(service.catalog())
            elif choice in ("2", "3"):
                request = read_request(service)
                if choice == "2":
                    show_order(service.quote(*request))
                    print("Quote only: no stock reserved and no order created.")
                else:
                    show_order(service.quote(*request))
                    if input("Place this order? [y/N]: ").strip().lower() == "y":
                        show_order(service.place_order(*request))
                    else:
                        print("Order not placed.")
            elif choice == "4":
                orders = service.list_orders()
                if not orders:
                    print("No orders yet.")
                for order in orders:
                    show_order(order)
            elif choice == "5":
                show_order(service.get_order(input("Order ID: ").strip()))
            elif choice == "6":
                order_id = input("Order ID to cancel: ").strip()
                if input("Cancel this order? [y/N]: ").strip().lower() == "y":
                    show_order(service.cancel_order(order_id))
                else:
                    print("Cancellation abandoned.")
            else:
                print("Choose a number from 0 to 6.")
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            return 0
        except (ValueError, OSError, KeyError, TypeError) as error:
            print(f"Error: {error}")
            print("Returning to the menu. Check your input or state file before retrying.")
