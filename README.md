# Campus Supply Desk

This program is intentionally imperfect. Your assignment is to understand, test, and improve it—not to rewrite it.

**Before using generative AI, submit Checkpoint A as required by the assignment.**

Use the official assignment handout and D2L instructions for assessed tasks, deadlines, and submission requirements. Read [FUNCTIONAL_SPEC.md](FUNCTIONAL_SPEC.md) for the expected application behavior.

## 1. Getting started

### Requirements

- Python **3.10 or newer**.
- No additional packages or database are needed.
- Running the application does not require internet access.

### Open the application folder

1. On this repository's GitHub page, select **Code**, choose **HTTPS**, and copy the repository URL.
2. In a terminal, type `git clone ` followed by the copied URL, then press Enter. Git must be installed to clone the repository.
3. Open the newly created repository folder in VS Code using **File > Open Folder**.
4. Check that the folder contains `README.md`, `supplydesk`, and `tests`.

Alternatively, select **Code > Download ZIP**, extract it, and open the folder containing those same files.

All commands below must be run from this folder.

### Open a terminal

**Windows:** In File Explorer, click the address bar, type `cmd`, and press Enter.

**VS Code:** Open the application folder, then select **Terminal → New Terminal**.

### Check Python and launch the menu

Run:

```sh
python --version
```

The version should be 3.10 or newer. Then run:

```sh
python -m supplydesk
```

You should see:

```text
1. View products and stock
2. Get a quote
3. Place an order
4. View order history
5. Find an order
6. Cancel an order
0. Exit
```

Type an option number and press Enter. The program will guide you through the remaining steps.

- Prices are displayed in Canadian dollars.
- Quotes do not create orders or reserve stock.
- Placement and cancellation require confirmation.
- Choose `0` to exit. You can also press `Ctrl+C`.

If your system uses `py -3` on Windows or `python3` on macOS/Linux, substitute that for `python` in the commands throughout this README.

## 2. Try your first quote

Start the menu:

```sh
python -m supplydesk
```

Then:

1. Choose **2 — Get a quote**.
2. Enter `regular` for the customer type.
3. Enter `notebook` for the product ID.
4. Enter `2` for the quantity.
5. Press Enter without typing another product ID to finish adding items.
6. Press Enter at the fulfillment prompt to use `pickup`. The other options are `delivery` and `express`.

With sufficient stock available, the quote should show a **$10.00 total**.

No order has been placed. To purchase items, choose **3 — Place an order** from the menu and follow the prompts.

## 3. Running the tests

From the folder containing `README.md`, `supplydesk`, and `tests`, run:

```sh
python -m unittest discover -s tests -v
```

The supplied tests should finish with:

```text
Ran 4 tests

OK
```

These four tests are a starting point. **Passing them does not mean every required behavior is correct.** You will add meaningful tests as part of the assignment.

The supplied tests use temporary files and do not change your saved orders or stock.

## 4. Saved data and practice sessions

The program automatically saves orders and stock levels in `.supplydesk/state.json`. When you close and reopen it, you continue where you left off.

Simply viewing products or requesting a quote does not create a save file.

### Start a fresh practice session

To experiment without affecting your normal session, start the menu with a separate save file:

```sh
python -m supplydesk --data .supplydesk/practice.json
```

- **The first time you use this filename**, the program starts with full stock and no orders.
- **If you use the same filename again**, it loads your saved practice orders and stock. It does not reset them.

For another fresh session, choose a new filename:

```sh
python -m supplydesk --data .supplydesk/practice2.json
```

You do not need to create these files yourself. The program creates them when you first place an order. Think of each filename as a separate save slot.

### Return to your normal session

Run:

```sh
python -m supplydesk
```

This uses the normal `.supplydesk/state.json` save file again.

Avoid running two instances that change the same save file simultaneously.

## 5. Repository guide

- **`FUNCTIONAL_SPEC.md`** — Intended business behavior and application scope.
- **`supplydesk/cli.py`** — Individual command handling and entry point for the menu.
- **`supplydesk/menu.py`** — Interactive prompts and readable output.
- **`supplydesk/service.py`** — Quotes, orders, inventory operations, and cancellation.
- **`supplydesk/storage.py`** — Loading and saving local JSON data.
- **`supplydesk/catalog.json`** — Initial products, prices, and stock for a new session.
- **`tests/test_smoke.py`** — Four starter tests.

The menu and individual commands use the same service and saved data. When a later requirement affects available choices or displayed information, review both interfaces.

Keep meaningful Git history as you work. Cloning already creates a Git repository; do not run `git init` again. If you downloaded a ZIP instead, you can initialize a repository from the application folder:

```sh
git init
```

## 6. Optional: individual commands

You can perform operations directly instead of using the menu. These commands are useful for repeatable examples and testing.

### View products and request quotes

```sh
python -m supplydesk catalog
python -m supplydesk quote --customer regular --item notebook:2
python -m supplydesk quote --customer student --fulfillment delivery --item hoodie:2
python -m supplydesk quote --customer student --fulfillment express --item hoodie:2
```

Fulfillment options: `pickup` (free), `delivery` ($6.00, free when the order is at least $100.00 after discount) and `express` ($12.00 flat, never waived).

Use repeated `--item` options for multiple items:

```sh
python -m supplydesk quote --customer student --item hoodie:1 --item mug:1
```

### Place, inspect, and cancel an order

```sh
python -m supplydesk place --customer regular --item mug:1
python -m supplydesk orders
python -m supplydesk show ORD-0001
python -m supplydesk cancel ORD-0001
```

Replace `ORD-0001` with the actual ID returned when you place your order.

Unlike the interactive menu, individual `place` and `cancel` commands perform the action immediately without asking for confirmation.

Individual commands display JSON. Prices are expressed in cents: for example, `"total_cents": 1000` means **CAD $10.00**.

Successful commands return exit status `0`. Rejected input returns exit status `2` and an error message.

### Use a practice save file

Put `--data` and the filename **before** the operation:

```sh
python -m supplydesk --data .supplydesk/practice.json place --item notebook:2
python -m supplydesk --data .supplydesk/practice.json orders
```

These commands use the same orders and stock as the interactive menu opened with that filename.

### View command help

```sh
python -m supplydesk --help
python -m supplydesk quote --help
```