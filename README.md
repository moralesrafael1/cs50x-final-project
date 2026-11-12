# Meridian
#### Video Demo: https://youtu.be/Fp48_2O37jo
#### Description:

Meridian is a web application that turns a photo of a Brazilian fiscal receipt into structured, item-level financial data. Instead of typing expenses into a spreadsheet, the user photographs the receipt and Meridian extracts the store name, the purchase date and every product with its quantity, unit price and total. The data is saved to the user's account and shown in a personal dashboard.

Manual data entry is the main reason people give up on tracking expenses, and thermal paper fades within months. Meridian removes that friction while keeping the detail that matters: not just how much was spent, but on what.

The app uses Python and Flask, SQLite through the CS50 library, Jinja2 templates, and plain HTML, CSS and JavaScript. Text recognition runs locally with Tesseract OCR, and a large language model served by Groq interprets the noisy OCR text and returns JSON.

## How it works

When a receipt is uploaded, the image is read in memory and never saved to disk. Tesseract extracts the text in Portuguese after the photo's rotation is corrected. Only this text, never the image, is sent to the LLM with a strict prompt describing the expected JSON. Python then validates the answer, converts money to integer cents, saves the receipt and its items in a single transaction, and redirects the user to the new receipt's page.

## Files

**`app.py`** is the controller. It defines every route (landing page, registration, login, dashboard, upload, receipt detail and account), small query helpers for the dashboard, and three Jinja filters that format currency, dates and quantities for display.

**`functions.py`** contains the `login_required` decorator, the `error` helper and the OCR pipeline. Before calling Tesseract, Pillow reads the uploaded bytes in memory, corrects EXIF orientation so sideways phone photos are upright, and converts the image to grayscale to improve text contrast. The extracted Portuguese text is then sent to the LLM, and its response is parsed and validated against expected types and required fields.

**`llm_config.py`** holds the LLM configuration and system prompt, reading the API key and model name from `.env`.

**`meridian.db`** is the SQLite database that persists all application data across three normalized tables: `users` (account credentials and profile records), `receipts` (the header of each purchase, storing the store name, purchase date and total amount in cents) and `receipt_items` (each line item's description, quantity, unit price and total price). The tables are linked in a relational chain (`users` → `receipts` → `receipt_items`) through foreign keys with `ON DELETE CASCADE` enabled, ensuring that deleting a receipt or an account automatically removes all dependent records without leaving orphaned items behind.

**`templates/`** contains the views: `layout.html` (shared header and navigation), `index.html` (landing page), `login.html` and `register.html`, `home.html` (dashboard with summary cards, a monthly chart and every receipt), `upload.html`, `receipt.html` (one receipt, item by item), `account.html` and `error.html`.

**`static/`** contains the stylesheets and two scripts: `auth.js` (password strength meter) and `upload.js` (image preview and drag-and-drop).

**`requirements.txt`** lists the Python dependencies required to run the application, including Flask, `cs50`, `pytesseract`, `Pillow`, `python-dotenv` and `openai`.

## Design decisions

**Hybrid OCR.** Vision models could read the photo directly, but I chose to run Tesseract on my own server and send only text. This protects the user's privacy and is far cheaper. The trade-off is OCR noise, such as an `S` read as a `5`, which the prompt addresses explicitly.

**Never trust the AI.** The model's output is treated as untrusted input. Every field is validated before reaching the database, image formats are detected from the file's bytes rather than its name, and every SQL query uses placeholders.

**Money as integer cents.** Floating-point numbers cannot represent most decimals exactly, so sums would accumulate errors. Values are converted to cents with `round()`, because `19.99 * 100` evaluates to `1998.9999999999998`, and formatted as reais only when displayed.

**Replaceable provider.** Groq follows the OpenAI API format and the model name lives in `.env`. When the original model was retired during development, switching required configuration, not code.

## How to run

Install the dependencies with `pip install -r requirements.txt`, install Tesseract with the Portuguese language pack, create a `.env` file with `SECRET_KEY`, `GROQ_API_KEY` and `TESSERACT_CMD`, ensure the pre-configured `meridian.db` database is in the project root, and run `flask run`.

## Acknowledgments

In line with CS50's academic honesty policy, I used Gemini as a mentor during development. It helped me with:

- **Code design:** reviewing the trade-offs behind the design decisions described above.
- **Database schema:** structuring a normalized relational model (`users` → `receipts` → `receipt_items`) instead of storing receipts in a single flat table, and enforcing referential integrity with foreign keys and `ON DELETE CASCADE` so deleting a receipt automatically removes its items without leaving orphaned records.
- **The system prompt:** the most challenging problem of the project was that the AI's readings of the same receipt varied from one attempt to another. The assistant helped me refine the system prompt, with an explicit output format, data delimited by tags and rules for unreadable fields, to make the results more consistent.
- **Pillow and Tesseract:** learning how to use both libraries together, from correcting the photo's rotation and converting it to grayscale, to installing the Portuguese language pack and configuring Tesseract on Windows.