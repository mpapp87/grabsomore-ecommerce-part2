# Grabsomore — Task 19: Django eCommerce Application Part 2

Grabsomore is a Django application for buyers and vendors. Vendors manage their stores and products; buyers browse, check out, receive invoices and review products. Part 2 also exposes an authenticated REST API.

**Task 1 submission:** [CRUD sequence diagrams for stores, products and reviews](docs/CRUD_SEQUENCE_DIAGRAMS.md). Open that link on GitHub to see the rendered diagrams. All 12 create/read/update/delete use cases are covered, including ownership checks and review verification.

## 1. Get this exact project

The public project is [mpapp87/grabsomore-ecommerce-part2](https://github.com/mpapp87/grabsomore-ecommerce-part2). The commands below clone this exact repository; no GitHub account or placeholder replacement is needed.

Install **Git** and **Python 3.12** before continuing. On macOS, check `git --version` (accept the Command Line Tools installation if prompted) and `python3.12 --version`. On Windows, check `git --version` and `py -3.12 --version`. Python 3.9 does not support this application's Django version. Python installers are available at [python.org](https://www.python.org/downloads/).

### macOS / Linux — Terminal

Run these commands from a folder where you want the downloaded project:

```bash
git clone https://github.com/mpapp87/grabsomore-ecommerce-part2.git
cd grabsomore-ecommerce-part2
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

### Windows — PowerShell

```powershell
git clone https://github.com/mpapp87/grabsomore-ecommerce-part2.git
Set-Location grabsomore-ecommerce-part2
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

If PowerShell blocks activation, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`, then retry activation. This setting applies only to the current PowerShell session.

If this public repository is already downloaded, open its root folder in your terminal and run `git pull`. Do not clone over an existing folder or discard local changes. Alternatively, use GitHub **Code → Download ZIP**, extract it, and open `grabsomore-ecommerce-part2-main` before creating the environment. If you are using the course repository or the separate coursework ZIP, open the Part 2 `AuthLog` folder containing this README instead.

Run the `manage.py` next to **this README**, not the Part 1 project or its `Example files` folder. A virtual environment keeps this project's dependencies separate from macOS system Python. Activate it again whenever you open a new terminal.

## 2. Install dependencies

Requirements include Django, Django REST Framework, Requests, mysqlclient and python-dotenv. The MySQL driver needs native prerequisites even if you use the SQLite quick start.

### macOS with Homebrew

Install [Homebrew](https://brew.sh/) first if `brew --version` reports command not found. Then run:

```bash
brew install mysql-client pkg-config
export PKG_CONFIG_PATH="$(brew --prefix mysql-client)/lib/pkgconfig"
python -m pip install -r requirements.txt
```

### Ubuntu / Debian

```bash
sudo apt-get update
sudo apt-get install -y python3-dev default-libmysqlclient-dev build-essential pkg-config
python -m pip install -r requirements.txt
```

### Windows

```powershell
python -m pip install -r requirements.txt
```

With Python 3.12, pip should use an available mysqlclient wheel. If it tries to compile instead, follow the [mysqlclient Windows instructions](https://github.com/PyMySQL/mysqlclient#install) for the MariaDB C connector/compiler. Installing a client driver does not install a database server.

## 3. Create and edit your configuration file

The application automatically reads `.env` **beside `manage.py`**. Keep real credentials in that file, not in `settings.py` or `.env.example`. `.env` is excluded from Git. Shell environment variables take precedence over the file.

Copy the supplied template **once** (do not overwrite an existing `.env` containing your settings):

macOS / Linux:

```bash
cp -n .env.example .env
nano .env
```

In nano, edit the values, press **Ctrl+O**, **Enter** to save, then **Ctrl+X** to exit. On macOS you can instead open the plain-text file using `open -e .env`.

Windows PowerShell:

```powershell
if (!(Test-Path .env)) { Copy-Item .env.example .env }
notepad .env
```

Save in Notepad with **Ctrl+S**. Keep the filename exactly `.env`, not `.env.txt`.

For a first local run, leave these two template values unchanged:

```dotenv
DB_ENGINE=sqlite
DJANGO_EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
```

This uses a local database file and prints emails in your terminal; it does not send real email. Leave the mock database/SMTP values alone until enabling those services in sections 5–6.

Replace `DJANGO_SECRET_KEY` with a generated value. Run this, copy the printed key, and paste it after `DJANGO_SECRET_KEY=` in `.env`:

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Put the key in single quotes, for example `DJANGO_SECRET_KEY='paste-the-generated-key-here'`, to preserve special characters. Keep `DJANGO_DEBUG=1` and `DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,testserver` for local development. Restart the server after changing `.env`.

`AuthLog/settings.py` imports `load_dotenv` and calls `load_dotenv(BASE_DIR / '.env')` before reading `os.environ.get`. The explicit path ensures the correct file is loaded even when you start Django from a different folder.

## 4. Create tables and start the app

From the activated environment in the Part 2 `AuthLog` folder:

```bash
python manage.py check
python manage.py migrate
python manage.py runserver
```

Wait for `Starting development server at http://127.0.0.1:8000/`, then open **http://127.0.0.1:8000/** in your browser. Keep that terminal open. **Ctrl+C** stops the server. If port 8000 is occupied, use `python manage.py runserver 8001` and open `http://127.0.0.1:8001/`.

An optional administration account is created with `python manage.py createsuperuser`; follow the username/email/password prompts and sign in at `/admin/`. A superuser is not automatically a Buyer or Vendor—register normal role accounts through the application for those workflows.

On your next visit, enter the same project folder, activate `.venv`, and run `python manage.py runserver`. When updating an existing installation, back up its database and run `python manage.py migrate`; do not delete the database. Included migrations preserve old products and add store ownership, invoices and reviews. No new model migration is required for the navigation and `.env` update.

## 5. Optional: use MySQL instead of SQLite

Use MySQL 8 or a Django-compatible MariaDB server. The following steps create a local development database. They do not copy data from an existing SQLite file.

On macOS, install/start the server (not just its client):

```bash
brew install mysql
brew services start mysql
mysql -u root -p
```

Enter your local MySQL administrator password when prompted. On a fresh installation, follow the server's installation instructions to configure the root account. On Ubuntu, install/start MySQL with `sudo apt-get install -y mysql-server`, `sudo systemctl start mysql`, then open `sudo mysql`. On Windows, install MySQL Server using its installer and open its SQL command-line client with the administrator credentials you set.

At the **MySQL prompt**, copy these SQL statements. Replace the example password with your chosen database password in the first statement that uses it:

```sql
CREATE DATABASE ecommerce_db CHARACTER SET utf8mb4;
CREATE USER 'ecommerce_user'@'localhost' IDENTIFIED BY 'change-this-local-password';
GRANT ALL PRIVILEGES ON ecommerce_db.* TO 'ecommerce_user'@'localhost';
GRANT ALL PRIVILEGES ON test_ecommerce_db.* TO 'ecommerce_user'@'localhost';
EXIT;
```

The last grant lets Django create and remove its separate test database. If the database/user already exists, reuse its existing credentials rather than repeating the CREATE statements. For a remote server, the database administrator must grant access from your machine's host.

Open `.env` using the editor commands in section 3. Replace its database block with the following, using **the same password you chose above**:

```dotenv
DB_ENGINE=mysql
DB_NAME=ecommerce_db
DB_USER=ecommerce_user
DB_PASSWORD='change-this-local-password'
DB_HOST=127.0.0.1
DB_PORT=3306
```

Save the file. Back in your normal terminal (not the MySQL prompt), run:

```bash
python manage.py check --database default
python manage.py migrate
python manage.py runserver
```

A new MySQL database starts with no accounts or products. Register new demo accounts there, or migrate your existing data separately after backing it up. To return to the original SQLite database, change `DB_ENGINE=sqlite` and restart Django.

## 6. Email: console first, then SMTP

With the default console backend, checkout invoices and password-reset links appear in the server terminal. Use this to test without email credentials.

For real email, obtain your provider's SMTP hostname, port, username, password/app password and approved sender address. Open `.env` and replace the email block:

```dotenv
DJANGO_EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.example.com
EMAIL_PORT=587
EMAIL_USE_TLS=1
EMAIL_HOST_USER=your-smtp-username
EMAIL_HOST_PASSWORD='replace-with-your-provider-password'
DEFAULT_FROM_EMAIL=your-verified-address@example.com
```

Those are mock examples: replace the host, username, password and sender with values supplied by your provider. These settings support STARTTLS (normally port 587); do not use implicit-TLS port 465 with this configuration. Save `.env`, stop the server with **Ctrl+C**, and restart it.

Register a Buyer with a real email address, complete a checkout, and check the inbox/spam folder. If delivery fails, the purchase remains saved; open **My invoices → invoice → Retry invoice email** after fixing the settings. A console-delivered invoice is already marked sent, so use a new checkout to test SMTP after switching backends. Email acceptance is not proof of inbox delivery.

Password recovery starts at `/request-password-reset/`. Enter the registered email, open the terminal-printed or emailed link, then choose a new password. Reset tokens expire after 30 minutes and are single-use.

## 7. Follow the buyer and vendor journeys

Create separate accounts through **Register**, selecting **Vendor** or **Buyer**. Use different browser sessions, or log out before switching accounts. No sample accounts or passwords are built into the project.

### Vendor

1. Open **My stores → Create store**, enter a name/description and save.
2. Click that store's name or **View this store's products**. Only its products appear.
3. Choose **Add product**, select your store, and supply its name, price and stock. You cannot select another vendor's store.
4. Open **My Products** to manage products across your own stores. Edit/delete controls are restricted to your resources. Deleting a store also removes its products and reviews; saved invoice line snapshots remain.
5. Open **My Reviews** to read all customer reviews across your stores immediately. Search by product/reviewer/comment, filter by store, and use Previous/Next for more results. Other vendors' reviews are excluded from this page.
6. Open **Web API** for direct **Store API**, **Product API** and **My Reviews API** links. You can also create resources using the browsable API as explained below.

### Buyer

1. **Vendors** lists vendors. Select a vendor to see only their stores; select a store to see only its products.
2. **Stores** starts at all stores without first selecting a vendor.
3. **Products** starts at all products without first selecting a store.
4. Open **Details & reviews** to read feedback, or choose a quantity and **Add to cart**.
5. In **Cart**, choose **Check out and email invoice**. Successful checkout checks stock, saves invoice line prices/quantities, reduces stock and clears the cart. This coursework flow records a purchase but does not collect payment.
6. **My invoices** shows only your purchases. Repeated checkout submissions reuse the invoice rather than making a second purchase.
7. On a product page choose **Write or edit my review**. A buyer has one review per product, with a 1–5 rating and a comment. **Delete my review** removes only your own review.
8. Reviews show **Verified purchase** only when that buyer has a completed invoice line for that product; otherwise they show **Unverified purchase**. A later purchase updates the displayed label automatically. Neither buyers nor vendors can submit a verified flag.

Every application page has Home/logout navigation. **Community** keeps the external Reddit feed; an unavailable external service does not prevent catalogue browsing.

## 8. Use the web API, step by step

First log in through the app at `/`. Choose **Web API** in the menu. Django REST Framework's browsable pages reuse your authenticated session and supply CSRF protection. Buyers can retrieve resources; vendors can create and manage their own stores/products. Anonymous and roleless accounts are rejected.

### Create a store through the API

1. Log in as a Vendor and choose **Web API → Store API**.
2. In the form at the bottom, enter Name and Description, then choose **POST**. If shown a Raw data form, choose `application/json` and paste:

```json
{"name":"Audio shop","description":"Audio equipment"}
```

3. A successful response shows **HTTP 201 Created** and an `id`. The server assigns your account as owner even if a different owner is submitted.
4. Open `/ecommerce/api/stores/ID/`, replacing `ID` with that returned number, to read/edit/delete the store. PUT/PATCH/DELETE require ownership.

### Add a product through the API

1. Choose **Web API → Product API**.
2. Use its form to select the store you just created, enter a name, price and stock, and choose **POST**.
3. For a Raw data form, paste this example and replace `1` with the store ID from your response:

```json
{"store":1,"name":"Headphones","description":"Open-back","price":"199.00","stock":3}
```

The ID is data returned by your own database, not a fixed sample store. Negative prices/stock and stores owned by another vendor are rejected with validation errors.

### Read resources and reviews

| Method | Endpoint | Purpose |
| --- | --- | --- |
| GET | `/ecommerce/api/vendors/` | Vendor IDs and usernames |
| GET | `/ecommerce/api/vendors/<vendor_id>/stores/` | One vendor's stores |
| GET / POST | `/ecommerce/api/stores/` | List / create stores |
| GET / PUT / PATCH / DELETE | `/ecommerce/api/stores/<id>/` | Read / update / delete a store |
| GET | `/ecommerce/api/stores/<id>/products/` | One store's products |
| GET / POST | `/ecommerce/api/products/` | List / create products |
| GET / PUT / PATCH / DELETE | `/ecommerce/api/products/<id>/` | Read / update / delete a product |
| GET | `/ecommerce/api/reviews/` | All product reviews |
| GET | `/ecommerce/api/products/<id>/reviews/` | One product's reviews |
| GET | `/ecommerce/api/my/reviews/` | Signed-in vendor's product reviews |

Replace angle-bracket IDs with IDs from the preceding API response. Review responses contain product ID, buyer username, rating, comment, date and computed `verified` status, but no private email address. The API is read-only for reviews; buyer HTML forms implement review create/update/delete. Unknown resource IDs return 404; valid resources without children return an empty list.

For a terminal client, this command prompts for the password of a Vendor account named `vendor_demo` (register that username first):

```bash
curl --user vendor_demo http://127.0.0.1:8000/ecommerce/api/my/reviews/
```

In Windows PowerShell use `curl.exe` instead of `curl`. HTTP Basic is suitable for this localhost exercise; use HTTPS when connecting to a remote server. Never embed passwords in a committed command or document.

### Verify the Reddit task locally

Open **Community** at `http://127.0.0.1:8000/ecommerce/community/`. A successful request displays titles, authors and links to the original Reddit discussions from `BuyItForLife`. The helper is in `eCommerce/functions/reddit.py` and the HTML view is in `eCommerce/views.py`.

Reddit can refuse unauthenticated requests from some networks (HTTP 403). The app displays an unavailable-feed message instead of crashing; this is not evidence of a successful live-feed test. The audit on 1 October 2026 received HTTP 403 from its network. Before resubmitting, try this page on your own computer. If it is also blocked, tell the reviewer and ask whether the tested fallback is acceptable or whether approved Reddit API credentials are required. Do not claim a fallback message proves live posts were retrieved.

## 9. Run the checks

Stop the development server or open another activated terminal in this folder, then run:

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test grabsomore eCommerce
```

Tests use an isolated database and in-memory email. They cover roles, hierarchy scoping, API ownership and CRUD, vendor review filters, buyer review deletion, checkout integrity, invoice privacy, password reset and external-feed failures. The GitHub workflow runs against SQLite and MySQL 8. `.env` loading is tested in isolation, including precedence of already-set environment variables.

## 10. Troubleshooting

| Problem | What to do |
| --- | --- |
| Repository not found when cloning | Sign in with the GitHub account that has access to the linked private course repo. Use GitHub Desktop's authenticated Clone action or download ZIP while signed in. |
| `python` not found or Django missing | Enter this project's AuthLog folder, activate `.venv`, then run `python -m pip install -r requirements.txt`. |
| `python3.12` not found | Install Python 3.12, reopen Terminal and check its version before creating `.venv`. |
| `No module named dotenv` | Install the updated requirements inside `.venv`. The package is named `python-dotenv`. |
| `.env` changes ignored | Save the file beside `manage.py`, check it is not `.env.txt`, then restart Django. Existing shell variables override file values; remove the conflicting exported variable or use a new terminal. |
| MySQL access denied | Match `.env` username/password to the account created in MySQL. Confirm the database server is running and the user can connect from your host. |
| mysqlclient build fails | Install the OS prerequisites in section 2. On macOS repeat the `PKG_CONFIG_PATH` export before pip installation. |
| No real email | The console backend only prints messages. Follow section 6 for SMTP and use a working buyer address. |
| 403 on a vendor action | Use a Vendor account and resources you own. Admin privileges alone do not assign the application's role. |
| No products/reviews | Create vendor stores/products first. Register a separate Buyer and write a review; a purchase is needed only for its verified label. |
| Styles missing locally | Keep `DJANGO_DEBUG=1` and run the development server from this project. |

## Layout and deployment notes

- `AuthLog/`: project settings and root URLs; loads `.env`.
- `grabsomore/`: registration, role assignment, login and password reset.
- `eCommerce/`: catalogue, vendor tools, reviews, cart, checkout and REST API.
- `eCommerce/templates/base.html`: shared menu and styling.
- `docs/CRUD_SEQUENCE_DIAGRAMS.md`: Task 1 sequence diagrams.
- `.env.example`: safe configuration template; `.env` is untracked.
- `requirements.txt`: required packages, including python-dotenv and mysqlclient.

For production, set `DJANGO_DEBUG=0`, a private secret key and the correct allowed hostname; use HTTPS, a production server and separately served static files (`python manage.py collectstatic`). `runserver` is for development. SMTP acceptance is not a delivery guarantee; a crash between sending and recording the timestamp can cause a duplicate on retry. This is the only README in the Part 2 application.
