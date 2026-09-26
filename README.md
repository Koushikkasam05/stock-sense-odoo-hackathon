# StockSense - Production-Grade Inventory Management System

A high-performance, real-time inventory management and supply chain logistics platform built with Flask, PostgreSQL / SQLAlchemy 2.x, Gunicorn, and modern Vanilla JS + Bootstrap.

---
## 1. Project Title
**StockSense: Intelligent Multi-Warehouse Inventory & Real-Time Stock Tracking System**

---

## 2. Problem Statement
Modern distribution centers, manufacturing units, and e-commerce warehouses frequently suffer from:
- **Discrepancies and Inaccurate Stock Levels**: Disconnected spreadsheets and outdated inventory systems lead to phantom inventory, stockouts, or overstocking.
- **Lack of Traceability**: Movements occurring across locations without immutable audit trails create accountability voids during audits.
- **Negative Stock and Data Corruption**: Systems allowing unvalidated deductions cause downstream fulfillment failures.
- **Complex, Fragile Architecture**: Heavy client-side frameworks often introduce unnecessary bundle overhead, stale client-side caches, and high maintenance costs.

---

## 3. Solution
StockSense provides a modular, reliable, and transaction-safe inventory control platform:
- **Double-Entry Style Inventory Core**: Modelled around physical movements where every stock alteration is paired with an immutable audit log entry.
- **Strict Stock Invariants**: Negative stock prevention on all internal physical storage locations.
- **Zero-Latency Real-Time Dashboards**: Database-level aggregation queries calculating live KPIs, low-stock thresholds, and distribution summaries.
- **Multi-Warehouse & Hierarchical Locations**: Support for complex storage networks with parent-child location trees (Warehouse → Aisle / Rack → Shelf).
- **Role-Based Access Control**: Strict segregation between administrative Inventory Managers and operational Warehouse Staff.

---

## 4. Features

### 📦 Master Product & Catalogue Management
- Real-time stock status computation (`in_stock`, `low_stock`, `out_of_stock`).
- Configurable minimum reorder thresholds and units of measure (UoM).
- Duplicate SKU detection and uniqueness validation.
- One-click CSV catalogue export for offline audits.

### 🏢 Multi-Warehouse & Location Hierarchy
- Create, edit, and deactivate warehouses and locations.
- Optional parent-child nested location trees (e.g. `WH-MAIN/RACK-A/SHELF-1`).
- Dedicated location-level and warehouse-level stock balance rollups.
- System virtual location architecture (`VEND-IN`, `CUST-OUT`, `INV-LOSS`).

### 📥 Incoming Receipts (Suppliers → Internal Storage)
- Supplier delivery tracking with dynamic line items.
- Validation workflow with automated destination stock increments.
- Ledger logging with immutable `receipt` movement records.
- Duplicate validation prevention.

### 📤 Outgoing Deliveries (Internal Storage → Customers)
- Pick / Pack workflow status transitions (`Draft → Waiting → Ready → Done`).
- Atomic stock decrement upon dispatch with `InsufficientStockError` negative-stock prevention.
- Detailed customer assignment and dispatch timestamps.

### 🔄 Internal Inter-Location Transfers
- Frictionless stock transfer between warehouses or internal zones.
- Mathematical stock conservation: Company-wide stock remains strictly unchanged ($\Delta \text{Stock} = 0$).
- Paired atomic ledger entries (`transfer_out` and `transfer_in`).

### ⚖️ Physical Inventory Adjustments & Count Reconciliation
- Live calculation of count difference ($\Delta = \text{Physical Count} - \text{System Stock}$).
- Automatic inventory gain/loss ledger generation (`adjustment_gain` / `adjustment_loss`).
- Real-time system stock inspection helper for floor operators.

### 📊 Real-Time Operations Dashboard & Stock Alerts
- Real-time KPIs: Total Products, In Stock, Low Stock, Out of Stock, Pending Receipts, Pending Deliveries, Scheduled Transfers.
- Warehouse and Category distribution summaries powered by SQL aggregations.
- Interactive multi-criteria filters (by document type, status, location, warehouse, SKU, and date range).

### 🔒 Enterprise Security & Auditability
- Salted Bcrypt password hashing.
- 6-digit OTP-based secure password reset with automatic expiration.
- Role-based authorization (`@manager_required` vs standard staff).
- Security headers with `HttpOnly`, `SameSite=Lax` session cookies.

---

## 5. Architecture

```text
                               +----------------------------------+
                               |     Web Browser / Client UI      |
                               | (Bootstrap 5.3 + Vanilla JS)     |
                               +-----------------+----------------+
                                                 |
                                         HTTPS / REST / HTML
                                                 |
                               +-----------------v----------------+
                               |    Gunicorn WSGI Application     |
                               +-----------------+----------------+
                                                 |
                               +-----------------v----------------+
                               |     Flask Application Factory    |
                               |      (app/__init__.py)           |
                               +--------+---------------+---------+
                                        |               |
               +------------------------+               +------------------------+
               |                                                                 |
+--------------v---------------+                               +-----------------v--------------+
|       Blueprints / Routes    |                               |         Service Layer          |
| - auth_bp       - receipts_bp|                               | - AuthService    - StockService |
| - dashboard_bp  - transfers_bp|<---------------------------->| - ProductService - ReceiptServ  |
| - products_bp   - deliver_bp |                               | - TransferServ   - DeliveryServ |
| - warehouses_bp - ledger_bp  |                               | - AdjustService  - DashboardServ|
+--------------+---------------+                               +-----------------+--------------+
               |                                                                 |
               |                                                                 |
               +------------------------+               +------------------------+
                                        |               |
                               +--------v---------------v---------+
                               |    SQLAlchemy 2.x ORM Models    |
                               |  - User         - StockPicking   |
                               |  - Product      - StockMove      |
                               |  - Location     - StockQuant     |
                               |  - Warehouse    - StockLedger    |
                               +----------------+-----------------+
                                                |
                               +----------------v-----------------+
                               |    PostgreSQL 15+ Database       |
                               | (ACID Transactions & Constraints)|
                               +----------------------------------+
```

---

## 6. Technology Stack

- **Backend Web Framework**: Python 3.12, Flask 3.0.3
- **WSGI Production Server**: Gunicorn 22.0.0
- **Database ORM**: SQLAlchemy 2.1.1, Flask-SQLAlchemy 3.1.1
- **Schema Migrations**: Alembic, Flask-Migrate 4.1.0
- **Database Engine**: PostgreSQL 15+ (Production) / SQLite (Local Fast Dev)
- **Authentication & Security**: Flask-Login, Bcrypt, Python-Dotenv
- **Frontend & Styling**: Jinja2 Templates, Bootstrap 5.3, Bootstrap Icons, Vanilla JS (No Node.js/React overhead)
- **Containerization**: Docker multi-stage build

---

## 7. Database Design

```mermaid
erDiagram
    USERS ||--o{ STOCK_PICKINGS : creates
    USERS ||--o{ STOCK_LEDGER_ENTRIES : operates
    WAREHOUSES ||--o{ LOCATIONS : contains
    LOCATIONS ||--o{ LOCATIONS : parent_child
    LOCATIONS ||--o{ STOCK_QUANTS : stores
    PRODUCTS ||--o{ STOCK_QUANTS : balances
    PRODUCT_CATEGORIES ||--o{ PRODUCTS : categorizes
    STOCK_PICKINGS ||--o{ STOCK_MOVES : contains
    PRODUCTS ||--o{ STOCK_MOVES : items
    PRODUCTS ||--o{ STOCK_LEDGER_ENTRIES : tracks
    LOCATIONS ||--o{ STOCK_LEDGER_ENTRIES : records
```

### Core table
1. `users`: User identity, Bcrypt password hashes, and roles (`inventory_manager`, `warehouse_staff`).
2. `otp_tokens`: Short-lived single-use verification codes for password resets.
3. `product_categories`: Categorization grouping for SKU catalogue.
4. `products`: Master product table with SKU uniqueness and reorder points.
5. `warehouses`: Physical facilities with active state toggling.
6. `locations`: Specific storage bins, racks, internal zones, and virtual system endpoints (`vendor`, `customer`, `loss`).
7. `stock_quants`: Real-time stock balance records indexed by `(product_id, location_id)`.
8. `stock_pickings`: Header documents for operational receipts, deliveries, transfers, and adjustments.
9. `stock_moves`: Line-item demand and quantities executed under pickings.
10. `stock_ledger_entries`: Append-only, immutable transaction ledger logging every physical quantity delta.
11. `notifications`: In-app actionable alert notices.

---

## 8.  Installation
### Prerequisites
- Python 3.10+ (Python 3.12 recommended)
- Git
- PostgreSQL (or SQLite for local dev)

### Clone & Virtual Environment Setup
```bash
# Clone the repository
git clone https://github.com/yourusername/stocksense.git
cd stocksense

# Create and activate virtual environment
python -m venv venv

# On Linux/macOS:
source venv/bin/activate

# On Windows (PowerShell):
.\venv\Scripts\Activate.ps1
```

### Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

---

## 9. PostgreSQL Setup

1. Create a dedicated PostgreSQL database and user:
```sql
CREATE USER stocksense_user WITH PASSWORD 'securepassword123';
CREATE DATABASE stocksense_db OWNER stocksense_user;
GRANT ALL PRIVILEGES ON DATABASE stocksense_db TO stocksense_user;
```

2. Configure your connection string in `.env`:
```env
DATABASE_URL=postgresql+psycopg2://stocksense_user:securepassword123@localhost:5432/stocksense_db
```

---

## 10. Environment Variables

Copy the example template to create your `.env` file:
```bash
cp .env.example .env
```

| Variable | Description | Default / Example |
| :--- | :--- | :--- |
| `FLASK_APP` | Application entrypoint | `wsgi.py` |
| `FLASK_ENV` | Application environment (`development` / `production`) | `production` |
| `SECRET_KEY` | Cryptographic secret for signing sessions | Random 32+ char string |
| `DATABASE_URL` | PostgreSQL or SQLite database connection URI | `postgresql+psycopg2://user:pass@host:5432/db` |
| `PORT` | Listening port for web server | `5000` |
| `MAIL_SERVER` | SMTP host for OTP password reset emails | `smtp.gmail.com` |
| `MAIL_PORT` | SMTP port | `587` |
| `MAIL_USE_TLS` | SMTP TLS flag | `True` |
| `MAIL_USERNAME` | SMTP account username | `user@example.com` |
| `MAIL_PASSWORD` | SMTP app password | `app_password_here` |
| `DEFAULT_LOW_STOCK_THRESHOLD` | Default threshold for low stock alert | `10` |
| `OTP_EXPIRY_MINUTES` | Expiration window for password reset OTP | `10` |

---

## 11. Migration Commands

StockSense uses Flask-Migrate (Alembic) for schema management:

```bash
# Initialize migrations (already initialized in repo)
flask db init

# Generate a new migration script
flask db migrate -m "Description of changes"

# Apply migrations to database
flask db upgrade

# Rollback last migration
flask db downgrade
```

---

## 12. Seed-Data Command

To populate realistic multi-warehouse demo data (warehouses, location hierarchies, categorized products, stock balances, sample operations, and user accounts):

```bash
python seed.py
```

### Default Demo Credentials:
- **Inventory Manager**:
  - Username: `manager`
  - Password: `password123`
  - Access: Full administrative rights (Warehouse/Location CRUD, Product creation/editing, Adjustments, Transfers, Reports)
- **Warehouse Staff**:
  - Username: `staff`
  - Password: `password123`
  - Access: Daily operations (Receipts, Deliveries, Transfers, Ledger inspection)

---

## 13. Run Instructions

### Development Server
```bash
python run.py
```
Visit: `http://127.0.0.1:5000`

### Production Server (Gunicorn)
```bash
gunicorn -c gunicorn.conf.py wsgi:app
```

---

## 14. Test Instructions

StockSense includes an automated test suite verifying authentication, operations, invariants, ledger auditing, and an end-to-end 19-step simulation.

```bash
# Run all tests
python -m pytest -v

# Run specific test suite
python -m pytest tests/test_e2e_simulation.py -v
python -m pytest tests/test_transfers.py -v
```

---

## 15. Deployment Instructions (Render / Cloud)

### Option A: Direct Web Service on Render
1. Create a **PostgreSQL Database** on Render:
   - Copy the **Internal Database URL**.
2. Create a **Web Service** on Render connected to this repository:
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt && python seed.py`
   - **Start Command**: `gunicorn -c gunicorn.conf.py wsgi:app`
3. Set Environment Variables in Render Dashboard:
   - `DATABASE_URL`: Your PostgreSQL database URL
   - `SECRET_KEY`: A cryptographically secure random string
   - `FLASK_ENV`: `production`
   - `SESSION_COOKIE_SECURE`: `True`

### Option B: Docker Deployment
```bash
# Build Docker image
docker build -t stocksense:latest .

# Run Docker container
docker run -d -p 5000:5000 \
  -e DATABASE_URL="postgresql+psycopg2://user:pass@host:5432/stocksense_db" \
  -e SECRET_KEY="your-secret-key" \
  stocksense:latest
```

---

## 16. Demo Workflow (19-Step Verification)

1. **Login**: Authenticate as `manager` / `password123`.
2. **Dashboard**: View live aggregate KPIs and stock status breakdown.
3. **Create Product**: Navigate to **Products → Add Product**, create `Steel Rod 20mm` with Min Threshold = 80.
4. **Receive Goods**: Navigate to **Operations → Receipts → New Receipt**, receive 100 units into `Main Warehouse / Stock Floor`. Validate receipt.
5. **Verify Stock**: Confirm product stock is now `100.0`.
6. **Internal Transfer**: Navigate to **Transfers → New Transfer**, transfer 30 units from `Main Stock` to `Production Floor`. Validate transfer.
7. **Verify Invariant**: Observe `Main Stock` = 70.0, `Production Floor` = 30.0, Total Stock = 100.0 ($\Delta = 0$).
8. **Deliver Goods**: Navigate to **Deliveries → New Delivery**, deliver 20 units to customer from `Main Stock`. Validate delivery.
9. **Verify Stock**: Confirm `Main Stock` = 50.0, Total Stock = 80.0.
10. **Physical Adjustment**: Navigate to **Adjustments → New Adjustment**, record physical count of 47 units at `Main Stock`.
11. **Verify Variance**: Observe $-3.0$ adjustment applied (`Main Stock` = 47.0, Total Stock = 77.0).
12. **Audit Ledger**: Open **Stock Ledger** and verify all 5 distinct audit records (`receipt`, `transfer_out`, `transfer_in`, `delivery`, `adjustment_loss`).
13. **Low-Stock Alert**: Inspect dashboard to see `Steel Rod 20mm` automatically flagged under Low Stock alerts ($77.0 \le 80.0$).
14. **Staff Permissions**: Log in as `staff` / `password123` and verify that warehouse and catalogue administrative routes are denied.

---

## 17. Future Enhancements
- Barcode & QR Code scanner integration for rapid mobile receiving and picking.
- Multi-currency purchase valuation and FIFO / Weighted-Average Costing (WAC) calculations.
- Automated reorder purchasing triggers via webhooks and external vendor APIs.
- Real-time WebSocket push notifications for multi-operator stock locking.
