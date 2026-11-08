# Campus Supply Desk: Functional Requirements

Use these requirements when designing tests and evaluating the application's behavior. The starter implementation may not satisfy every requirement.

For your System Understanding Note, inspect the implementation and explain the system in your own words, supported by references to its files, components, and execution flow.

## Scope boundaries

- Each order has status `placed` or `cancelled`.
- Shipping workflows, payment processing, taxes, authentication, and customer personal information are outside scope.
- Only one running instance should use a given save file at a time.
- These limits are deliberate. You are not expected to add the excluded features.
- A later client change request may extend these requirements.

## Catalog

Each product has a stable product ID, display name, unit price in integer Canadian cents, and a nonnegative available-stock quantity.

A new save file starts with these products:

- **Notebook**
  - Product ID: `notebook`
  - Unit price: 500 cents ($5.00 CAD)
  - Initial stock: 20

- **Pen pack**
  - Product ID: `pen-pack`
  - Unit price: 750 cents ($7.50 CAD)
  - Initial stock: 10

- **Campus hoodie**
  - Product ID: `hoodie`
  - Unit price: 4,000 cents ($40.00 CAD)
  - Initial stock: 5

- **Campus mug**
  - Product ID: `mug`
  - Unit price: 1,500 cents ($15.00 CAD)
  - Initial stock: 8

- **Canvas bag**
  - Product ID: `bag`
  - Unit price: 2,500 cents ($25.00 CAD)
  - Initial stock: 4

Viewing the catalog returns current stock without changing it. Catalog editing is outside the initial interface.

## Requests and validation

The service provides these operations:

```python
quote(customer_type, items, fulfillment="pickup")
place_order(customer_type, items, fulfillment="pickup")
```

Both operations require:

- Customer type: exactly `regular` or `student`.
- Fulfillment: exactly `pickup`, `delivery` or `express` (see CR-01). Any other value, including different capitalisation, is invalid.
- Items: a nonempty list of dictionaries, each containing `product_id` and `quantity`.
- A valid product ID for every item.
- An integer quantity from 1 through 99 inclusive for each item. Booleans, fractional numbers, and numeric strings are not valid quantities when calling the service directly.
- Sufficient stock for the complete request. If a product appears on multiple lines, its combined quantity must not exceed its available stock.

Duplicate product lines may remain separate in the results.

Both quoting and placement check current stock. A quote does not reserve stock, so placement must check stock again.

An invalid service request raises `ValueError`. It must not change saved orders, stock, or the next order number. Earlier successful operations remain saved.

### Input through the menu and individual commands

The menu and command-line parser convert typed quantities into integers before calling the service. For example, typing `2` is valid, even though passing the string `"2"` directly to the service is not.

- The menu defaults to `regular` and `pickup` when those prompts are left blank.
- Individual commands use the same defaults when the corresponding options are omitted.
- A rejected individual command reports an error and exits with a nonzero status.
- The menu reports errors and remains available for another attempt.

## Prices

All service calculations and stored monetary values use integer Canadian cents.

1. Each line subtotal is the unit price multiplied by the quantity. The order subtotal is the sum of all line subtotals.
2. A student receives a 10% discount when the subtotal is at least 5,000 cents ($50.00). Regular customers receive no discount.
3. Round the discount to the nearest whole cent, with half a cent rounded upward. Do not use binary floating-point values for money calculations.
4. Pickup is free.
5. Delivery costs 600 cents ($6.00). Delivery is free when the subtotal minus the discount is at least 10,000 cents ($100.00).
6. Express delivery (CR-01) always costs 1,200 cents ($12.00). It is never waived, whatever the order value.
7. The student discount applies to merchandise only. It is calculated from the subtotal and never reduces the delivery or express charge.
8. Total = subtotal minus discount plus delivery charge. No taxes or other charges apply.

Examples—all amounts below are in cents:

- Regular pickup, two notebooks: subtotal 1,000; discount 0; delivery 0; total 1,000.
- Student delivery, two hoodies: subtotal 8,000; discount 800; delivery 600; total 7,800.
- Regular delivery, three hoodies: subtotal 12,000; discount 0; delivery 0; total 12,000.
- Regular express, two notebooks: subtotal 1,000; discount 0; delivery 1,200; total 2,200.
- Student express, two hoodies: subtotal 8,000; discount 800; delivery 1,200; total 8,400.
- Regular express, three hoodies: subtotal 12,000; discount 0; delivery 1,200; total 13,200.

These rules apply identically to quotes and placed orders.

## Change request CR-01: Express delivery

- `express` is a third fulfillment option, accepted by the service, the individual commands (`--fulfillment express`) and the menu fulfillment prompt.
- Express costs a flat 1,200 cents and is never waived. The student discount applies to merchandise only.
- Pickup and standard delivery pricing are unchanged.
- Express orders store `fulfillment: "express"` and the 1,200-cent charge in `delivery_cents`. Both are kept after reopening and after cancellation.

## Quotes

A quote returns:

- Customer type and fulfillment option.
- Item lines containing the product ID, name, unit price, quantity, and line subtotal.
- Order subtotal, discount, delivery charge, and total.

A quote must not create or modify a save file, reserve stock, create an order, or use an order ID.

If the catalog, stock, and request remain unchanged, a quote and a subsequent placed order must contain the same pricing and item information.

## Placement and history

A successful placement:

- Validates the complete request before changing saved data.
- Deducts all ordered units from stock.
- Assigns an order ID, starting at `ORD-0001` and increasing by one for each successful placement.
- Records status `placed` and a snapshot of the items and prices.
- Saves the updated stock and order to the selected save file.

Order retrieval and history follow these rules:

- `get_order(order_id)` returns the matching order. An unknown ID raises `ValueError`.
- `list_orders()` returns all orders in their original placement order, including cancelled orders.
- Reopening the application with the same save file preserves history and stock.
- Historical prices remain as recorded when the order was placed. They are not recalculated from current catalog prices.
- Cancelling an order does not make its ID available for reuse.

## Cancellation

Cancelling a placed order restores each ordered unit to stock and changes the order's status to `cancelled`.

The order remains in history with its original items and totals.

Cancelling an already cancelled order returns the existing cancelled order without changing stock, prices, or history again.

An unknown order ID raises `ValueError` without changing saved data.

## Saved data and scope limits

The bundled JSON catalog supplies the initial data only when the selected save file does not exist.

A malformed or unreadable save file must produce an error rather than silently reset orders and stock.

Save files generated by the application use schema version 1. The following are outside the initial requirements:

- Converting files from other schema versions.
- Supporting multiple instances writing to the same file simultaneously.
- Guaranteeing recovery after a crash during saving.
- Supporting arbitrary manual edits to save-file contents.

## Interactive interface

Running the following command opens the interactive menu:

```sh
python -m supplydesk
```

The menu provides catalog viewing, quotes, placement, history, lookup, and cancellation through the same service operations used by individual commands.

Menu behavior:

- Display money in Canadian dollars. Service calculations and stored values remain in integer cents.
- Default to `regular` and `pickup` when those prompts are left blank.
- Finish collecting items when the product-ID prompt is left blank.
- Require a `y` confirmation before placing or cancelling an order. Declining must leave saved data unchanged.
- Report invalid requests and return to the main menu. If quantity text cannot be converted to an integer, ask the user to re-enter the item.
- Exit when the user chooses `0`, reaches the end of input, or presses `Ctrl+C`.

Individual commands retain their documented JSON output and exit statuses. Unlike the menu, individual placement and cancellation commands act immediately without asking for confirmation.
